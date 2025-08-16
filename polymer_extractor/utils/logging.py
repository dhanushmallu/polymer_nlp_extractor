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
    timestamp: str = ""
    level: str = "INFO"
    message: str = ""
    source: str = ""
    event_type: str = "general"
    user_action: bool = False
    context: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None
    file_name: Optional[str] = None
    line_number: Optional[int] = None
    category: str = "system"
    synced_to_appwrite: bool = False  # Default to False to avoid sync errors
    
    def to_dict(self, include_nulls: bool = True) -> Dict[str, Any]:
        """Convert to dictionary, optionally excluding null values."""
        data = asdict(self)
        if not include_nulls:
            return {k: v for k, v in data.items() if v is not None}
        return data
    
    def to_human_readable(self) -> str:
        """Convert to human-readable log line with clean formatting."""
        timestamp_short = self.timestamp.split('T')[1][:8] if 'T' in self.timestamp else self.timestamp[:8]
        context_str = ""
        if self.context and any(self.context.values()):
            context_items = [f"{k}={v}" for k, v in self.context.items() if v]
            if context_items:
                context_str = f" | {', '.join(context_items)}"
        
        stack_info = f" | `{self.file_name}`:{self.line_number}" if self.file_name else ""
        
        # Clean stack trace - remove visual artifacts and format file paths
        clean_message = self.message
        if self.stack_trace:
            # Clean stack trace artifacts - remove common control characters
            import re
            clean_trace = self.stack_trace.replace("^^^^", "")
            # Remove any invisible control characters that might cause formatting issues
            clean_trace = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', clean_trace)
            # Add backticks to file paths
            clean_trace = re.sub(r'(/[\w/.-]+\.py)', r'`\1`', clean_trace)
            clean_message += f"\nStack trace:\n{clean_trace}"
        
        return f"[{timestamp_short}] {self.level:<7} {self.source:<20} | {clean_message}{context_str}{stack_info}"


class SmartTruncator:
    """Handles intelligent truncation of log data for cloud storage."""
    
    # Cloud storage limits
    MESSAGE_LIMIT = 1000  # Increased from 512
    CONTEXT_LIMIT = 2000  # Increased limit
    STACK_TRACE_LIMIT = 3000  # Increased for better error debugging
    
    @staticmethod
    def truncate_message(message: str) -> str:
        """Truncate message to fit cloud storage limits."""
        if len(message) <= SmartTruncator.MESSAGE_LIMIT:
            return message
        return message[:SmartTruncator.MESSAGE_LIMIT - 3] + "..."
    
    @staticmethod
    def truncate_stack_trace(stack_trace: str) -> str:
        """Truncate stack trace intelligently."""
        if not stack_trace or len(stack_trace) <= SmartTruncator.STACK_TRACE_LIMIT:
            return stack_trace or ""
        
        lines = stack_trace.split('\n')
        if len(lines) <= 10:
            return stack_trace[:SmartTruncator.STACK_TRACE_LIMIT - 3] + "..."
        
        # Keep first 5 and last 5 lines for context
        truncated = lines[:5] + ['  ... (truncated) ...'] + lines[-5:]
        result = '\n'.join(truncated)
        
        if len(result) > SmartTruncator.STACK_TRACE_LIMIT:
            return result[:SmartTruncator.STACK_TRACE_LIMIT - 3] + "..."
        return result
    
    @staticmethod
    def truncate_context(context: Dict[str, Any]) -> Dict[str, Any]:
        """Truncate context dictionary intelligently."""
        if not context:
            return {}
        
        result = {}
        current_size = 0
        
        for key, value in context.items():
            # Convert value to string for size calculation
            str_value = str(value)
            item_size = len(key) + len(str_value) + 10  # Extra for JSON formatting
            
            if current_size + item_size > SmartTruncator.CONTEXT_LIMIT:
                result["_truncated"] = True
                break
            
            # Truncate individual values if too long
            if len(str_value) > 200:
                result[key] = str_value[:197] + "..."
            else:
                result[key] = value
            
            current_size += item_size
        
        return result
    
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
            message_key = self._get_message_key(entry)
            now = datetime.now()
            
            # Clean old entries outside the window
            window_start = now - timedelta(minutes=self.window_minutes)
            timestamps = self.message_counts[message_key]
            
            while timestamps and timestamps[0] < window_start:
                timestamps.popleft()
            
            # Check if we should suppress this message
            if len(timestamps) >= self.max_duplicates:
                suppression_msg = f"Suppressed duplicate message (seen {len(timestamps)} times in {self.window_minutes}min)"
                return False, suppression_msg
            
            # Add this timestamp
            timestamps.append(now)
            return True, None
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
        
        # Setup log files - single structured format per category
        self.local_log_files = {
            category: os.path.join(LOGS_DIR, f"{category}.log")
            for category in self.LOG_CATEGORIES
        }
        
        # Create main system log
        self.main_log_file = os.path.join(LOGS_DIR, "system.log")
        
        # Initialize components
        self.deduplicator = LogDeduplicator()
        self.truncator = SmartTruncator()
        
        # Database setup - use universal DatabaseManager for both Appwrite and PostgreSQL
        self._setup_database()
        
        # Create log files
        self._ensure_log_files_exist()
    
    def _setup_database(self):
        """Setup universal database manager for logging."""
        try:
            from polymer_extractor.storage.database_manager import DatabaseManager
            self.database_manager = DatabaseManager()
            self.database_enabled = True
            
            # Check if we have any database backends available
            if not self.database_manager.postgres_client and not self.database_manager.appwrite_db:
                self.database_enabled = False
                print("[DATABASE_SETUP] No database backends available")
            else:
                print(f"[DATABASE_SETUP] Database manager initialized (PostgreSQL: {self.database_manager.postgres_client is not None}, Appwrite: {self.database_manager.appwrite_db is not None})")
                
        except Exception as e:
            self.database_enabled = False
            print(f"[DATABASE_SETUP_ERROR] {e}")
    
    def _setup_appwrite(self):
        """Legacy method - kept for compatibility but now handled by universal database manager."""
        # This method is kept for backward compatibility but functionality moved to _setup_database
        pass
    
    def _ensure_appwrite_collection(self):
        """Ensure Appwrite logs collection exists with proper schema."""
        if not self.appwrite_enabled:
            return
        try:
            # This would normally check/create collection schema
            # Simplified for now to avoid collection setup complexity
            pass
        except AppwriteException as e:
            print(f"[APPWRITE_COLLECTION_ERROR] {e}")
    
    def _make_json_safe(self, obj):
        """Convert non-JSON serializable objects to safe types."""
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.float64, np.float32, np.floating)):
            return float(obj)
        elif isinstance(obj, (np.ndarray, torch.Tensor)):
            return f"<{type(obj).__name__} shape={getattr(obj, 'shape', 'unknown')}>"
        elif isinstance(obj, dict):
            return {k: self._make_json_safe(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_json_safe(item) for item in obj]
        else:
            return str(obj)
    
    def _ensure_log_files_exist(self):
        """Create all necessary log files."""
        all_files = [self.main_log_file] + list(self.local_log_files.values())
        
        for file_path in all_files:
            if not os.path.exists(file_path):
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("")  # Create empty file
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
        """Write to local log files in structured human-readable format."""
        # Single structured log file per category
        log_file = self.local_log_files[entry.category]
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry.to_human_readable() + "\n")
        
        # Also write to main system log if it's a system or error log
        if entry.category in ['system'] or entry.level in ['ERROR', 'CRITICAL']:
            with open(self.main_log_file, "a", encoding="utf-8") as f:
                f.write(entry.to_human_readable() + "\n")
    
    def _sync_to_database(self, entry: LogEntry) -> bool:
        """Sync log entry to database using universal database manager."""
        if not self.database_enabled:
            return False
            
        try:
            # Create log document for database storage
            log_doc = {
                "timestamp": entry.timestamp or datetime.now(),
                "level": entry.level or "INFO",
                "message": self.truncator.truncate_message(entry.message or ""),
                "source": entry.source or "unknown",
                "event_type": entry.event_type or "general",
                "user_action": bool(entry.user_action),
                "context": json.dumps(self.truncator.truncate_context(entry.context or {})),
                "stack_trace": self.truncator.truncate_stack_trace(entry.stack_trace or ""),
                "file_name": entry.file_name or "",
                "line_number": entry.line_number or 0,
                "log_category": entry.category or "system"
            }
            
            # Use universal database manager to create record
            result = self.database_manager.create_record("system_logs", log_doc)
            return bool(result and result.get("primary"))
            
        except Exception as e:
            # Disable database on any sync error to prevent spam
            self.database_enabled = False
            print(f"[DATABASE_SYNC_ERROR] Failed to sync log to database: {e}")
            return False
    
    def log(self, level: str, message: str, source: str,
            category: str = "system", event_type: str = "general",
            user_action: bool = False, context: Optional[Dict] = None,
            error: Optional[Exception] = None, extra: Optional[Dict] = None) -> None:
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
        extra : dict
            Additional context information (alias for context)
        """
        if category not in self.LOG_CATEGORIES:
            category = "system"
        
        # Merge extra into context if provided
        if extra and context:
            # Merge extra into context
            merged_context = {**context, **extra}
        elif extra:
            # Use extra as context
            merged_context = extra
        elif context:
            # Use context as is
            merged_context = context
        else:
            merged_context = None
        
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
            context=merged_context,
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
            
            # Sync to database (non-blocking)
            try:
                self._sync_to_database(entry)
            except Exception:
                pass  # Don't let database sync failures break local logging
        
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
