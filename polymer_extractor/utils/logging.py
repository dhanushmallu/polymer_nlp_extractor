# polymer_extractor/utils/logging.py

import inspect
import json
import os
import re
import traceback
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Set
from dataclasses import dataclass, asdict
from threading import Lock
import hashlib

import numpy as np
import torch
from appwrite.client import Client
from appwrite.exception import AppwriteException
from appwrite.id import ID
from appwrite.services.databases import Databases

from polymer_extractor.utils.paths import LOGS_DIR, APPWRITE_LOGS_COLLECTION


@dataclass
class LogEntry:
    """Structured log entry for better type safety and serialization."""
    timestamp: str
    level: str
    message: str
    source: str
    event_type: str = "general"
    user_action: bool = False
    context: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None
    file_name: Optional[str] = None
    line_number: Optional[int] = None
    category: str = "system"
    synced_to_appwrite: bool = True
    
    def to_dict(self, include_nulls: bool = True) -> Dict[str, Any]:
        """Convert to dictionary, optionally excluding null values."""
        data = asdict(self)
        if not include_nulls:
            return {k: v for k, v in data.items() if v is not None}
        return data
    
    def to_human_readable(self) -> str:
        """Convert to human-readable log line."""
        timestamp_short = self.timestamp.split('T')[1][:8]  # HH:MM:SS
        context_str = ""
        if self.context and any(self.context.values()):
            # Only show non-empty context values
            non_empty_context = {k: v for k, v in self.context.items() if v}
            if non_empty_context:
                context_str = f" | {json.dumps(non_empty_context, separators=(',', ':'))}"
        
        stack_info = f" | {self.file_name}:{self.line_number}" if self.file_name else ""
        
        return f"[{timestamp_short}] {self.level:<7} {self.source:<20} | {self.message}{context_str}{stack_info}"


class SmartTruncator:
    """Handles intelligent truncation of log data for cloud storage."""
    
    # Cloud storage limits
    MESSAGE_LIMIT = 1000  # Increased from 512
    CONTEXT_LIMIT = 2000  # Increased limit
    STACK_TRACE_LIMIT = 3000  # Increased for better error debugging
    
    @staticmethod
    def truncate_message(message: str) -> str:
        """Intelligently truncate message while preserving key information."""
        if len(message) <= SmartTruncator.MESSAGE_LIMIT:
            return message
        
        # Try to preserve the beginning and end
        prefix_len = SmartTruncator.MESSAGE_LIMIT // 2 - 10
        suffix_len = SmartTruncator.MESSAGE_LIMIT // 2 - 10
        
        return f"{message[:prefix_len]}... [TRUNCATED] ...{message[-suffix_len:]}"
    
    @staticmethod
    def truncate_stack_trace(stack_trace: str) -> str:
        """Truncate stack trace while preserving most relevant parts."""
        if not stack_trace or len(stack_trace) <= SmartTruncator.STACK_TRACE_LIMIT:
            return stack_trace
        
        lines = stack_trace.split('\n')
        
        # Keep first few lines (error type) and last few lines (actual error location)
        if len(lines) > 10:
            kept_lines = lines[:3] + ['  ... [TRUNCATED] ...'] + lines[-7:]
            truncated = '\n'.join(kept_lines)
            
            if len(truncated) <= SmartTruncator.STACK_TRACE_LIMIT:
                return truncated
        
        # Fallback to simple truncation
        return stack_trace[:SmartTruncator.STACK_TRACE_LIMIT - 3] + "..."
    
    @staticmethod
    def truncate_context(context: Dict[str, Any]) -> Dict[str, Any]:
        """Truncate context while preserving important keys."""
        if not context:
            return context
        
        context_str = json.dumps(context, ensure_ascii=False)
        if len(context_str) <= SmartTruncator.CONTEXT_LIMIT:
            return context
        
        # Prioritize certain keys
        priority_keys = ['error', 'id', 'status', 'file_name', 'count', 'size']
        result = {}
        
        # Add priority keys first
        for key in priority_keys:
            if key in context:
                result[key] = context[key]
        
        # Add other keys until we hit the limit
        remaining_budget = SmartTruncator.CONTEXT_LIMIT - len(json.dumps(result, ensure_ascii=False))
        
        for key, value in context.items():
            if key not in result:
                value_str = json.dumps(value, ensure_ascii=False)
                if len(value_str) < remaining_budget:
                    result[key] = value
                    remaining_budget -= len(value_str)
                else:
                    break
        
        return result


class LogDeduplicator:
    """Handles deduplication and rate limiting of repetitive log messages."""
    
    def __init__(self, window_minutes: int = 5, max_duplicates: int = 3):
        self.window_minutes = window_minutes
        self.max_duplicates = max_duplicates
        self.message_counts = defaultdict(deque)
        self.lock = Lock()
    
    def _get_message_key(self, entry: LogEntry) -> str:
        """Generate a key for deduplication based on message content and source."""
        # Create hash of message + source + event_type for deduplication
        content = f"{entry.source}:{entry.event_type}:{entry.message}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def should_log(self, entry: LogEntry) -> tuple[bool, Optional[str]]:
        """
        Determine if this log entry should be recorded.
        
        Returns:
            (should_log, suppression_message)
        """
        with self.lock:
            now = datetime.now()
            key = self._get_message_key(entry)
            
            # Clean old entries
            cutoff = now - timedelta(minutes=self.window_minutes)
            while self.message_counts[key] and self.message_counts[key][0] < cutoff:
                self.message_counts[key].popleft()
            
            count = len(self.message_counts[key])
            
            if count < self.max_duplicates:
                self.message_counts[key].append(now)
                return True, None
            
            # If we've hit the limit, return suppression info
            suppression_msg = f"[SUPPRESSED] Similar message repeated {count} times in {self.window_minutes}min: {entry.message[:100]}"
            return False, suppression_msg


class Logger:
    """
    Enhanced logging system with smart truncation, deduplication, and clean formatting.
    
    Features:
    - Human-readable local logs with clean formatting
    - Smart truncation for cloud storage
    - Deduplication of repetitive messages
    - Structured JSON logs for machine processing
    - Category-based log separation
    - Async cloud sync with retry logic
    """

    LOG_CATEGORIES = ["system", "api", "user", "debug"]
    
    def __init__(self):
        """Initialize the enhanced logger."""
        os.makedirs(LOGS_DIR, exist_ok=True)
        
        # Setup log files
        self.local_log_files = {
            category: {
                'json': os.path.join(LOGS_DIR, f"{category}.json.log"),
                'human': os.path.join(LOGS_DIR, f"{category}.readable.log")
            }
            for category in self.LOG_CATEGORIES
        }
        
        # Create main system log (human readable)
        self.main_log_file = os.path.join(LOGS_DIR, "system.readable.log")
        
        # Initialize components
        self.deduplicator = LogDeduplicator()
        self.truncator = SmartTruncator()
        
        # Appwrite setup
        self._setup_appwrite()
        
        # Create log files
        self._ensure_log_files_exist()
    
    def _setup_appwrite(self):
        """Setup Appwrite client and collection."""
        try:
            self.client = Client()
            self.client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
            self.client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
            self.client.set_key(os.getenv("APPWRITE_API_KEY"))
            
            self.databases = Databases(self.client)
            self.database_id = os.getenv("APPWRITE_DATABASE_ID")
            self.collection_id = APPWRITE_LOGS_COLLECTION
            
            self._ensure_appwrite_collection()
            self.appwrite_enabled = True
        except Exception as e:
            print(f"[Logger] Appwrite setup failed, logging locally only: {e}")
            self.appwrite_enabled = False
    
    def _ensure_appwrite_collection(self):
        """Ensure Appwrite logs collection exists with proper schema."""
        try:
            self.databases.get_collection(self.database_id, self.collection_id)
        except AppwriteException as e:
            if e.code == 404:
                # Create collection with enhanced schema
                self.databases.create_collection(
                    database_id=self.database_id,
                    collection_id=self.collection_id,
                    name="Enhanced System Logs",
                    document_security=False
                )
                
                # Define attributes with larger sizes
                attributes = [
                    ("log_id", "string", 36, True),  # Added log_id attribute
                    ("timestamp", "string", 32, True),
                    ("level", "string", 16, True),
                    ("message", "string", 1024, True),  # Increased
                    ("source", "string", 64, True),
                    ("event_type", "string", 32, False),
                    ("user_action", "boolean", None, False),
                    ("context", "string", 2048, False),  # Increased
                    ("stack_trace", "string", 3072, False),  # Increased
                    ("file_name", "string", 128, False),
                    ("line_number", "integer", None, False),
                    ("category", "string", 16, False),
                    ("synced_to_appwrite", "boolean", None, False),  # Added with default False
                    ("local_log_file", "string", 256, False)  # Added for schema compatibility
                ]
                
                for attr_name, attr_type, size, required in attributes:
                    if attr_type == "string":
                        self.databases.create_string_attribute(
                            database_id=self.database_id,
                            collection_id=self.collection_id,
                            key=attr_name,
                            size=size,
                            required=required
                        )
                    elif attr_type == "integer":
                        self.databases.create_integer_attribute(
                            database_id=self.database_id,
                            collection_id=self.collection_id,
                            key=attr_name,
                            required=required
                        )
                    elif attr_type == "boolean":
                        self.databases.create_boolean_attribute(
                            database_id=self.database_id,
                            collection_id=self.collection_id,
                            key=attr_name,
                            required=required
                        )
    
    def _ensure_log_files_exist(self):
        """Create all necessary log files."""
        all_files = [self.main_log_file]
        for category_files in self.local_log_files.values():
            all_files.extend(category_files.values())
        
        for file_path in all_files:
            if not os.path.exists(file_path):
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("")
    
    def _make_json_safe(self, obj):
        """Convert non-JSON serializable objects to safe types."""
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.float64, np.float32, np.floating)):
            return float(obj)
        elif isinstance(obj, (np.ndarray, torch.Tensor)):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {key: self._make_json_safe(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_json_safe(item) for item in obj]
        else:
            return obj
    
    def _write_local_logs(self, entry: LogEntry):
        """Write to local log files in both JSON and human-readable formats."""
        # JSON log for machine processing - ensure JSON serializable
        json_file = self.local_log_files[entry.category]['json']
        with open(json_file, "a", encoding="utf-8") as f:
            try:
                f.write(json.dumps(entry.to_dict(include_nulls=False), ensure_ascii=False) + "\n")
            except TypeError:
                # Handle non-JSON serializable types
                safe_dict = self._make_json_safe(entry.to_dict(include_nulls=False))
                f.write(json.dumps(safe_dict, ensure_ascii=False) + "\n")
        
        # Human-readable log
        human_file = self.local_log_files[entry.category]['human']
        with open(human_file, "a", encoding="utf-8") as f:
            f.write(entry.to_human_readable() + "\n")
        
        # Also write to main system log if it's a system or error log
        if entry.category in ['system'] or entry.level in ['ERROR', 'CRITICAL']:
            with open(self.main_log_file, "a", encoding="utf-8") as f:
                f.write(entry.to_human_readable() + "\n")
    
    def _sync_to_appwrite(self, entry: LogEntry) -> bool:
        """Sync log entry to Appwrite with smart truncation."""
        if not self.appwrite_enabled:
            return False
        
        try:
            # Create cloud-optimized version
            cloud_entry = LogEntry(
                timestamp=entry.timestamp,
                level=entry.level,
                message=self.truncator.truncate_message(entry.message),
                source=entry.source,
                event_type=entry.event_type,
                user_action=entry.user_action,
                context=self.truncator.truncate_context(entry.context) if entry.context else None,
                stack_trace=self.truncator.truncate_stack_trace(entry.stack_trace) if entry.stack_trace else None,
                file_name=entry.file_name,
                line_number=entry.line_number,
                category=entry.category
            )
            
            # Convert to dict and prepare for Appwrite
            cloud_data = cloud_entry.to_dict(include_nulls=False)
            
            # Add required fields for Appwrite schema compatibility
            cloud_data['log_id'] = ID.unique()  # Add missing log_id
            cloud_data['local_log_file'] = self.local_log_files[entry.category]['json']
            
            # Convert context to JSON string for Appwrite - make safe first
            if cloud_data.get('context'):
                safe_context = self._make_json_safe(cloud_data['context'])
                cloud_data['context'] = json.dumps(safe_context, ensure_ascii=False)
            
            self.databases.create_document(
                database_id=self.database_id,
                collection_id=self.collection_id,
                document_id=ID.unique(),
                data=cloud_data
            )
            return True
            
        except AppwriteException as e:
            # Log sync failure to local file only (avoid recursion)
            error_msg = f"Failed to sync log to Appwrite: {str(e)[:200]}"
            with open(self.main_log_file, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] WARNING sync_error | {error_msg}\n")
            return False
    
    def log(self, level: str, message: str, source: str,
            category: str = "system", event_type: str = "general",
            user_action: bool = False, context: Optional[Dict] = None,
            error: Optional[Exception] = None) -> None:
        """
        Create a log entry with enhanced features.
        
        Parameters:
        -----------
        level : str
            Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message : str
            Human-readable message
        source : str
            Source component/module
        category : str
            Log category (system, api, user, debug)
        event_type : str
            Event type for categorization
        user_action : bool
            Whether this was triggered by user action
        context : dict
            Additional context information
        error : Exception
            Exception object for stack trace
        """
        if category not in self.LOG_CATEGORIES:
            category = "system"
        
        # Get caller information
        frame = inspect.stack()[1]
        file_name = os.path.basename(frame.filename)
        line_number = frame.lineno
        
        # Create log entry
        entry = LogEntry(
            timestamp=datetime.now().isoformat() + "Z",
            level=level.upper(),
            message=message,
            source=source,
            event_type=event_type,
            user_action=user_action,
            context=context,
            stack_trace=traceback.format_exc() if error else None,
            file_name=file_name,
            line_number=line_number,
            category=category
        )
        
        # Check for deduplication
        should_log, suppression_msg = self.deduplicator.should_log(entry)
        
        if should_log:
            # Write to local logs
            self._write_local_logs(entry)
            
            # Sync to cloud (non-blocking)
            try:
                self._sync_to_appwrite(entry)
            except Exception:
                pass  # Don't let cloud sync failures break local logging
        
        elif suppression_msg and level in ['WARNING', 'ERROR', 'CRITICAL']:
            # Log suppression message for important levels
            suppression_entry = LogEntry(
                timestamp=datetime.now().isoformat() + "Z",
                level="INFO",
                message=suppression_msg,
                source="logger",
                event_type="suppression",
                category=category,
                file_name=file_name,
                line_number=line_number
            )
            self._write_local_logs(suppression_entry)
    
    # Convenience methods
    def info(self, message: str, source: str, **kwargs):
        """Log info message."""
        self.log("INFO", message, source, **kwargs)
    
    def error(self, message: str, source: str, error: Optional[Exception] = None, **kwargs):
        """Log error message."""
        self.log("ERROR", message, source, error=error, **kwargs)
    
    def debug(self, message: str, source: str, **kwargs):
        """Log debug message."""
        self.log("DEBUG", message, source, category="debug", **kwargs)
    
    def warning(self, message: str, source: str, **kwargs):
        """Log warning message."""
        self.log("WARNING", message, source, **kwargs)
    
    def critical(self, message: str, source: str, **kwargs):
        """Log critical message."""
        self.log("CRITICAL", message, source, **kwargs)
    
    def user_action(self, message: str, source: str, **kwargs):
        """Log user action."""
        kwargs['user_action'] = True
        kwargs['category'] = 'user'
        self.log("INFO", message, source, **kwargs)


# Create global logger instance
logger = Logger()

# Convenience functions for backward compatibility
def get_logger() -> Logger:
    """Get the global enhanced logger instance."""
    return logger
