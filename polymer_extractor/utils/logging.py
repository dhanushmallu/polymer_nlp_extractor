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
import psycopg2
import psycopg2.extras

import numpy as np
import torch

from polymer_extractor.utils.paths import LOGS_DIR


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
    
    def to_dict(self, include_nulls: bool = True) -> Dict[str, Any]:
        """Convert to dictionary, optionally excluding null values."""
        data = asdict(self)
        if not include_nulls:
            return {k: v for k, v in data.items() if v is not None}
        return data
    
    def to_human_readable(self) -> str:
        """Convert to human-readable log line with clean formatting."""
        timestamp_short = self.timestamp.split('T')[1][:8] if 'T' in self.timestamp else self.timestamp[:8]
        level_colored = f"[{self.level:5}]"
        source_info = f"{self.source}" if self.source else "system"
        
        # Basic format: [TIME] [LEVEL] [SOURCE] MESSAGE
        base_line = f"{timestamp_short} {level_colored} [{source_info:15}] {self.message}"
        
        # Add context if available
        if self.context:
            context_str = ", ".join([f"{k}={v}" for k, v in self.context.items() if k != "details"])
            if context_str:
                base_line += f" | {context_str}"
        
        return base_line


class LogDeduplicator:
    """Efficient deduplication to prevent log spam."""
    def __init__(self, window_seconds: int = 60, max_occurrences: int = 5):
        self.window_seconds = window_seconds
        self.max_occurrences = max_occurrences
        self.recent_logs = deque()
        self.log_counts = defaultdict(int)
        self.lock = Lock()
    
    def should_log(self, message: str, level: str, source: str) -> bool:
        """Check if log should be recorded or is spam."""
        with self.lock:
            now = datetime.now()
            log_key = f"{level}:{source}:{self._get_message_pattern(message)}"
            
            # Clean old entries
            cutoff_time = now - timedelta(seconds=self.window_seconds)
            while self.recent_logs and self.recent_logs[0][0] < cutoff_time:
                old_timestamp, old_key = self.recent_logs.popleft()
                self.log_counts[old_key] -= 1
                if self.log_counts[old_key] <= 0:
                    del self.log_counts[old_key]
            
            # Check current count
            current_count = self.log_counts[log_key]
            if current_count >= self.max_occurrences:
                return False
            
            # Record this log
            self.recent_logs.append((now, log_key))
            self.log_counts[log_key] += 1
            return True
    
    def _get_message_pattern(self, message: str) -> str:
        """Extract pattern from message to group similar logs."""
        # Remove numbers, IDs, timestamps to group similar messages
        pattern = re.sub(r'\d+', 'N', message)
        pattern = re.sub(r'[a-f0-9]{8,}', 'ID', pattern)  # Remove hex IDs
        return pattern[:100]  # Limit length


class SmartTruncator:
    """Smart content truncation for log context."""
    def __init__(self, max_string_length: int = 500, max_list_items: int = 10):
        self.max_string_length = max_string_length
        self.max_list_items = max_list_items
    
    def truncate_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Truncate context values intelligently."""
        if not context:
            return context
        
        truncated = {}
        for key, value in context.items():
            truncated[key] = self._truncate_value(value)
        return truncated
    
    def _truncate_value(self, value: Any) -> Any:
        """Truncate individual value based on type."""
        if isinstance(value, str):
            if len(value) > self.max_string_length:
                return value[:self.max_string_length] + "..."
        elif isinstance(value, (list, tuple)):
            if len(value) > self.max_list_items:
                truncated_list = list(value)[:self.max_list_items]
                truncated_list.append(f"... and {len(value) - self.max_list_items} more items")
                return truncated_list
        elif isinstance(value, dict):
            if len(value) > self.max_list_items:
                items = list(value.items())[:self.max_list_items]
                truncated_dict = dict(items)
                truncated_dict["..."] = f"and {len(value) - self.max_list_items} more keys"
                return truncated_dict
        
        return value


class DirectPostgreSQLLogger:
    """Direct PostgreSQL connection for logging to avoid circular dependencies."""
    
    def __init__(self):
        self.connection = None
        self.enabled = False
        self._setup_connection()
    
    def _setup_connection(self):
        """Setup direct PostgreSQL connection."""
        try:
            # Get connection details from environment
            self.connection = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=os.getenv("POSTGRES_PORT", "5432"),
                database=os.getenv("POSTGRES_DB", "polymer_extractor"),
                user=os.getenv("POSTGRES_USER", "postgres"),
                password=os.getenv("POSTGRES_PASSWORD", "password")
            )
            self.connection.autocommit = True
            self.enabled = True
            print("[LOGGING] Direct PostgreSQL connection established")
            
            # Ensure system_logs table exists
            self._ensure_table_exists()
            
        except Exception as e:
            self.enabled = False
            print(f"[LOGGING] PostgreSQL connection failed: {e}")
    
    def _ensure_table_exists(self):
        """Ensure system_logs table exists."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS system_logs (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        level VARCHAR(20) NOT NULL,
                        message TEXT NOT NULL,
                        source VARCHAR(255),
                        event_type VARCHAR(100) DEFAULT 'general',
                        user_action BOOLEAN DEFAULT false,
                        context JSONB,
                        stack_trace TEXT,
                        file_name VARCHAR(255),
                        line_number INTEGER,
                        category VARCHAR(50) DEFAULT 'system',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes if they don't exist
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON system_logs(timestamp);
                    CREATE INDEX IF NOT EXISTS idx_logs_level ON system_logs(level);
                    CREATE INDEX IF NOT EXISTS idx_logs_source ON system_logs(source);
                    CREATE INDEX IF NOT EXISTS idx_logs_event_type ON system_logs(event_type);
                    CREATE INDEX IF NOT EXISTS idx_logs_category ON system_logs(category);
                """)
                
        except Exception as e:
            print(f"[LOGGING] Failed to ensure system_logs table: {e}")
    
    def log_to_database(self, log_entry: LogEntry):
        """Log entry directly to PostgreSQL."""
        if not self.enabled or not self.connection:
            return
        
        try:
            with self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute("""
                    INSERT INTO system_logs (
                        timestamp, level, message, source, event_type, user_action,
                        context, stack_trace, file_name, line_number, category
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    log_entry.timestamp,
                    log_entry.level,
                    log_entry.message,
                    log_entry.source,
                    log_entry.event_type,
                    log_entry.user_action,
                    json.dumps(log_entry.context) if log_entry.context else None,
                    log_entry.stack_trace,
                    log_entry.file_name,
                    log_entry.line_number,
                    log_entry.category
                ))
                
        except Exception as e:
            print(f"[LOGGING] Failed to write to database: {e}")
    
    def pause_database_operations(self):
        """Pause database operations for clean installs."""
        if self.connection:
            try:
                self.connection.close()
            except:
                pass
        self.enabled = False
        print("[LOGGING] Database operations paused")
    
    def resume_database_operations(self):
        """Resume database operations after clean install."""
        self._setup_connection()
        if self.enabled:
            print("[LOGGING] Database operations resumed")
    
    def reset_database_table(self):
        """Reset system_logs table (for clean installs)."""
        if not self.enabled or not self.connection:
            return
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("DROP TABLE IF EXISTS system_logs CASCADE")
                print("[LOGGING] system_logs table dropped")
            
            self._ensure_table_exists()
            print("[LOGGING] system_logs table recreated")
            
        except Exception as e:
            print(f"[LOGGING] Failed to reset system_logs table: {e}")


class Logger:
    """
    Independent logging system with direct PostgreSQL integration.
    
    Removed dependency on DatabaseManager to avoid circular imports.
    Provides file-based and database-based logging with intelligent deduplication.
    """
    
    LOG_LEVELS = {
        'DEBUG': 10,
        'INFO': 20,
        'WARNING': 30,
        'ERROR': 40,
        'CRITICAL': 50
    }
    
    LOG_CATEGORIES = ['system', 'api', 'user', 'model', 'database', 'performance']
    
    def __init__(self, min_level: str = "INFO", enable_database: bool = True):
        # Prevent circular import
        self.min_level = self.LOG_LEVELS.get(min_level.upper(), 20)
        self.enable_database = enable_database
        
        # Thread safety
        self.lock = Lock()
        
        # In-memory buffer for recent logs
        self.memory_buffer = deque(maxlen=1000)
        
        # Category-specific file handles
        self.category_files = {
            category: os.path.join(LOGS_DIR, f"{category}.log")
            for category in self.LOG_CATEGORIES
        }
        
        # Create main system log
        self.main_log_file = os.path.join(LOGS_DIR, "system.log")
        
        # Initialize components
        self.deduplicator = LogDeduplicator()
        self.truncator = SmartTruncator()
        
        # Database setup - direct PostgreSQL connection
        self.postgres_logger = DirectPostgreSQLLogger()
        
        # Create log files
        self._ensure_log_files_exist()

    def _ensure_log_files_exist(self):
        """Ensure all log files and directories exist."""
        os.makedirs(LOGS_DIR, exist_ok=True)
        
        # Touch all category log files
        for log_file in self.category_files.values():
            if not os.path.exists(log_file):
                with open(log_file, 'w') as f:
                    f.write(f"# Log file created: {datetime.now().isoformat()}\n")
        
        # Touch main system log
        if not os.path.exists(self.main_log_file):
            with open(self.main_log_file, 'w') as f:
                f.write(f"# System log created: {datetime.now().isoformat()}\n")

    def _write_to_files(self, log_entry: LogEntry):
        """Write log entry to appropriate files."""
        with self.lock:
            formatted_line = log_entry.to_human_readable() + "\n"
            
            # Write to category-specific file
            category_file = self.category_files.get(log_entry.category, self.main_log_file)
            try:
                with open(category_file, 'a', encoding='utf-8') as f:
                    f.write(formatted_line)
            except Exception as e:
                print(f"[LOGGING_ERROR] Failed to write to {category_file}: {e}")
            
            # Also write to main system log
            if category_file != self.main_log_file:
                try:
                    with open(self.main_log_file, 'a', encoding='utf-8') as f:
                        f.write(formatted_line)
                except Exception as e:
                    print(f"[LOGGING_ERROR] Failed to write to main log: {e}")

    def _write_to_database(self, log_entry: LogEntry):
        """Write log entry to database if enabled."""
        if self.enable_database and self.postgres_logger.enabled:
            try:
                self.postgres_logger.log_to_database(log_entry)
            except Exception as e:
                print(f"[LOGGING_ERROR] Database write failed: {e}")

    def _should_log(self, level: str, message: str, source: str) -> bool:
        """Check if log should be recorded based on level and deduplication."""
        if self.LOG_LEVELS.get(level, 0) < self.min_level:
            return False
        
        return self.deduplicator.should_log(message, level, source)

    def _get_caller_info(self, skip_frames: int = 2) -> tuple:
        """Get caller file name and line number."""
        try:
            frame = inspect.currentframe()
            for _ in range(skip_frames):
                frame = frame.f_back
                if frame is None:
                    break
            
            if frame:
                return os.path.basename(frame.f_code.co_filename), frame.f_lineno
        except:
            pass
        return None, None

    def _make_json_safe(self, obj):
        """Convert object to JSON-safe format."""
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, (list, tuple)):
            return [self._make_json_safe(item) for item in obj]
        elif isinstance(obj, dict):
            return {str(key): self._make_json_safe(value) for key, value in obj.items()}
        elif hasattr(obj, '__dict__'):
            return self._make_json_safe(obj.__dict__)
        elif isinstance(obj, (np.ndarray, torch.Tensor)):
            return f"<{type(obj).__name__} shape={obj.shape}>"
        else:
            return str(obj)

    def log(self, level: str, message: str, source: str = "", event_type: str = "general", 
            user_action: bool = False, category: str = "system", **context):
        """
        Main logging method.
        
        Parameters
        ----------
        level : str
            Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message : str
            Log message
        source : str, optional
            Source component
        event_type : str, optional
            Type of event being logged
        user_action : bool, optional
            Whether this is a user-initiated action
        category : str, optional
            Log category for file organization
        **context
            Additional context data
        """
        level = level.upper()
        
        if not self._should_log(level, message, source):
            return
        
        # Get caller info
        file_name, line_number = self._get_caller_info()
        
        # Create log entry
        log_entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level=level,
            message=message,
            source=source or "unknown",
            event_type=event_type,
            user_action=user_action,
            context=self.truncator.truncate_context(self._make_json_safe(context)) if context else None,
            stack_trace=None,
            file_name=file_name,
            line_number=line_number,
            category=category
        )
        
        # Add to memory buffer
        self.memory_buffer.append(log_entry)
        
        # Write to files
        self._write_to_files(log_entry)
        
        # Write to database
        self._write_to_database(log_entry)

    # Convenience methods
    def debug(self, message: str, source: str = "", **context):
        """Log debug message."""
        self.log("DEBUG", message, source, **context)
    
    def info(self, message: str, source: str = "", **context):
        """Log info message."""
        self.log("INFO", message, source, **context)
    
    def warning(self, message: str, source: str = "", **context):
        """Log warning message."""
        self.log("WARNING", message, source, **context)
    
    def error(self, message: str, source: str = "", **context):
        """Log error message with stack trace."""
        context['stack_trace'] = traceback.format_exc()
        self.log("ERROR", message, source, **context)
    
    def critical(self, message: str, source: str = "", **context):
        """Log critical message with stack trace."""
        context['stack_trace'] = traceback.format_exc()
        self.log("CRITICAL", message, source, **context)

    # Database management methods for clean installs
    def pause_database_logging(self):
        """Pause database logging operations."""
        if self.postgres_logger:
            self.postgres_logger.pause_database_operations()
    
    def resume_database_logging(self):
        """Resume database logging operations."""
        if self.postgres_logger:
            self.postgres_logger.resume_database_operations()
    
    def reset_database_logs(self):
        """Reset database log table (for clean installs)."""
        if self.postgres_logger:
            self.postgres_logger.reset_database_table()
    
    def initialize_database_table(self):
        """Initialize database table (for setup operations)."""
        if self.postgres_logger:
            self.postgres_logger._ensure_table_exists()

    # Query methods
    def get_recent_logs(self, count: int = 100, level: str = None, source: str = None) -> list:
        """Get recent logs from memory buffer."""
        logs = list(self.memory_buffer)
        
        if level:
            logs = [log for log in logs if log.level == level.upper()]
        
        if source:
            logs = [log for log in logs if source.lower() in log.source.lower()]
        
        return logs[-count:]
    
    def get_log_stats(self) -> dict:
        """Get logging statistics."""
        recent_logs = list(self.memory_buffer)
        
        level_counts = defaultdict(int)
        source_counts = defaultdict(int)
        
        for log in recent_logs:
            level_counts[log.level] += 1
            source_counts[log.source] += 1
        
        return {
            "total_recent_logs": len(recent_logs),
            "level_distribution": dict(level_counts),
            "top_sources": dict(list(source_counts.items())[:10]),
            "database_enabled": self.postgres_logger.enabled if self.postgres_logger else False,
            "log_files": self.category_files
        }


# Global logger instance
_logger_instance = None

def get_logger() -> Logger:
    """Get or create global logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = Logger()
    return _logger_instance


# Convenience function for backward compatibility
def log(level: str, message: str, source: str = "", **context):
    """Log message using global logger."""
    logger = get_logger()
    logger.log(level, message, source, **context)
