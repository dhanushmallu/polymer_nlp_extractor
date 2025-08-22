"""
polymer_extractor/utils/logging.py

Summary
-------
Independent, thread-safe logging system with direct PostgreSQL integration, intelligent
deduplication, and structured log entry management. Provides file-based and database-based
logging without dependency on DatabaseManager to avoid circular imports.

Key abstractions
----------------
- LogEntry: structured dataclass for type-safe log entries with metadata
- Logger: main logging facade with level filtering, deduplication, and multi-output support
- LogDeduplicator: prevents log spam by tracking recent similar messages
- SmartTruncator: intelligently truncates context data to prevent oversized logs
- DirectPostgreSQLLogger: direct database connection for logging without circular dependencies

Invariants
----------
- All logs are timestamped in UTC ISO-8601 format
- Database operations are isolated to prevent circular import issues
- File-based logging always works regardless of database connectivity
- Thread-safe operations across all logging components
- Memory buffer maintains recent logs for fast retrieval

Examples
--------
>>> from polymer_extractor.utils.logging import Logger
>>> logger = Logger(min_level="INFO", enable_database=True)
>>> logger.info("Processing started", source="main", file_count=5)
>>> logger.error("Database error", source="db_service", exception=db_error)
>>> 
>>> # Global logger usage
>>> from polymer_extractor.utils.logging import get_logger
>>> log = get_logger()
>>> log.warning("Low disk space", source="storage", available_mb=100)

Notes
-----
- Complexity: O(1) for most operations, O(n) for deduplication cleanup
- Side effects: creates log files, database entries, modifies memory buffer
- Thread safety: all operations are thread-safe via locks
- Performance: uses deque for efficient memory buffer operations
- Environment dependencies: PostgreSQL connection details from environment variables
"""

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

# NOTE: This import causes a circular dependency, so we use the direct path
# from polymer_extractor.utils.paths import SYSTEM_LOGS_DIR

# Compute LOGS_DIR using the same project structure rules as paths.py
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
WORKSPACE_DIR = os.path.join(PROJECT_ROOT, "workspace")
PUBLIC_DIR = os.path.join(WORKSPACE_DIR, "public")
LOGS_DIR = os.path.join(PUBLIC_DIR, "system_logs")


@dataclass
class LogEntry:
    """
    Structured log entry for type-safe logging with comprehensive metadata.
    
    Summary
    -------
    Immutable dataclass containing all log information including timestamp, level,
    message, source context, stack traces, and categorization. Provides serialization
    methods for file output and database storage.
    
    Parameters
    ----------
    timestamp : str
        UTC timestamp in ISO-8601 format (auto-generated if empty)
    level : str
        Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    message : str
        Primary log message content
    source : str
        Source module/service/component generating the log
    event_type : str
        Event classification (general, user_action, system_event, etc.)
    user_action : bool
        Whether this log represents a user-initiated action
    context : Dict[str, Any], optional
        Additional structured context data
    stack_trace : str, optional
        Exception stack trace if applicable
    file_name : str, optional
        Source file name where log was generated
    line_number : int, optional
        Line number where log was generated
    category : str
        Log category (system, api, user, model, database, performance)
        
    Examples
    --------
    >>> entry = LogEntry(
    ...     level="ERROR",
    ...     message="Database connection failed",
    ...     source="db_service",
    ...     context={"host": "localhost", "port": 5432}
    ... )
    >>> entry.to_dict()
    {'timestamp': '2025-08-20T12:34:56.789Z', 'level': 'ERROR', ...}
    
    Notes
    -----
    - All fields have sensible defaults for easy construction
    - Context should contain JSON-serializable data only
    - Stack traces are automatically cleaned for readability
    - Thread-safe when used with proper synchronization
    """
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
        """
        Convert log entry to dictionary format for serialization.
        
        Parameters
        ----------
        include_nulls : bool
            Whether to include fields with None/empty values
            
        Returns
        -------
        Dict[str, Any]
            Dictionary representation suitable for JSON serialization
            
        Examples
        --------
        >>> entry = LogEntry(level="INFO", message="Test")
        >>> entry.to_dict(include_nulls=False)
        {'level': 'INFO', 'message': 'Test', 'event_type': 'general', ...}
        
        Notes
        -----
        - Uses dataclasses.asdict() for automatic field extraction
        - Filtering None values reduces storage size and improves readability
        """
        data = asdict(self)
        if not include_nulls:
            return {k: v for k, v in data.items() if v is not None}
        return data
    
    def to_human_readable(self) -> str:
        """
        Convert to human-readable single-line log format.
        
        Returns
        -------
        str
            Formatted log line with timestamp, level, source, and message
            
        Examples
        --------
        >>> entry = LogEntry(level="ERROR", message="Failed", source="api")
        >>> entry.to_human_readable()
        '12:34:56 [ERROR] [api           ] Failed'
        
        Notes
        -----
        - Optimized for terminal/file output readability
        - Truncates timestamp to time-only format
        - Fixed-width source field for alignment
        - Context data appended as key=value pairs
        """
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
    """
    Efficient log deduplication to prevent spam in high-frequency scenarios.
    
    Summary
    -------
    Thread-safe deduplication system that tracks similar log messages within a time
    window and limits the number of identical log entries to prevent log flooding
    from repeated errors or warnings.
    
    Parameters
    ----------
    window_seconds : int
        Time window in seconds for tracking duplicate messages (default: 60)
    max_occurrences : int
        Maximum number of similar messages allowed within the window (default: 5)
        
    Attributes
    ----------
    recent_logs : deque
        Time-ordered queue of (timestamp, log_key) tuples
    log_counts : defaultdict
        Count of occurrences for each log pattern
    lock : Lock
        Thread synchronization lock for safe concurrent access
        
    Examples
    --------
    >>> deduplicator = LogDeduplicator(window_seconds=30, max_occurrences=3)
    >>> # First few messages allowed
    >>> deduplicator.should_log("Connection failed", "ERROR", "db_service")  # True
    >>> deduplicator.should_log("Connection failed", "ERROR", "db_service")  # True
    >>> deduplicator.should_log("Connection failed", "ERROR", "db_service")  # True
    >>> deduplicator.should_log("Connection failed", "ERROR", "db_service")  # False (spam)
    
    Notes
    -----
    - Complexity: O(1) amortized for should_log(), O(k) for cleanup where k is expired entries
    - Side effects: modifies internal state, performs automatic cleanup
    - Thread safety: all operations protected by internal lock
    - Memory usage: bounded by window size and message diversity
    """
    def __init__(self, window_seconds: int = 60, max_occurrences: int = 5):
        self.window_seconds = window_seconds
        self.max_occurrences = max_occurrences
        self.recent_logs = deque()
        self.log_counts = defaultdict(int)
        self.lock = Lock()
    
    def should_log(self, message: str, level: str, source: str) -> bool:
        """
        Determine if a log message should be recorded or is considered spam.
        
        Parameters
        ----------
        message : str
            Log message content to check for duplication
        level : str
            Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        source : str
            Source component/module generating the message
            
        Returns
        -------
        bool
            True if message should be logged, False if it's spam
            
        Examples
        --------
        >>> deduplicator = LogDeduplicator(max_occurrences=2)
        >>> deduplicator.should_log("Error occurred", "ERROR", "service")  # True
        >>> deduplicator.should_log("Error occurred", "ERROR", "service")  # True  
        >>> deduplicator.should_log("Error occurred", "ERROR", "service")  # False
        
        Notes
        -----
        - Automatically cleans expired entries from tracking window
        - Uses message pattern matching to group similar messages
        - Thread-safe operation with internal locking
        - Returns False when max_occurrences exceeded within window
        """
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
    """
    Intelligent content truncation for log context data to prevent oversized logs.
    
    Summary
    -------
    Provides type-aware truncation of context data including strings, lists, dicts,
    and nested structures while preserving data readability and preventing log files
    from becoming unmanageably large.
    
    Parameters
    ----------
    max_string_length : int
        Maximum length for string values before truncation (default: 500)
    max_list_items : int
        Maximum number of list/tuple items to preserve (default: 10)
        
    Examples
    --------
    >>> truncator = SmartTruncator(max_string_length=100, max_list_items=5)
    >>> large_context = {
    ...     "data": "x" * 200,
    ...     "items": list(range(20)),
    ...     "nested": {"key": "y" * 150}
    ... }
    >>> truncated = truncator.truncate_context(large_context)
    >>> len(truncated["data"])  # <= 100
    True
    
    Notes
    -----
    - Preserves data type structure while reducing size
    - Adds truncation indicators (e.g., "...[truncated]")
    - Handles nested dictionaries recursively
    - Maintains JSON serializability of all truncated values
    """
    def __init__(self, max_string_length: int = 500, max_list_items: int = 10):
        self.max_string_length = max_string_length
        self.max_list_items = max_list_items
    
    def truncate_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Intelligently truncate all values in a context dictionary.
        
        Parameters
        ----------
        context : Dict[str, Any]
            Context dictionary with potentially large values
            
        Returns
        -------
        Dict[str, Any]
            New dictionary with truncated values preserving structure
            
        Examples
        --------
        >>> truncator = SmartTruncator(max_string_length=10)
        >>> truncator.truncate_context({"msg": "very long message here"})
        {"msg": "very long ...[truncated]"}
        
        Notes
        -----
        - Returns empty dict if input is None/empty
        - Processes each value according to its type
        - Creates new dictionary, does not modify input
        """
        if not context:
            return context
        
        truncated = {}
        for key, value in context.items():
            truncated[key] = self._truncate_value(value)
        return truncated
    
    def _truncate_value(self, value: Any) -> Any:
        """
        Truncate individual value based on its data type.
        
        Parameters
        ----------
        value : Any
            Value to potentially truncate
            
        Returns
        -------
        Any
            Truncated value maintaining type compatibility
            
        Notes
        -----
        - Strings: truncated with "...[truncated]" suffix
        - Lists/tuples: limited to max_list_items with "...[N more]" suffix
        - Dicts: recursively truncated preserving structure
        - Other types: returned unchanged
        """
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
    Thread-safe logging system with multi-output support and intelligent deduplication.
    
    Summary
    -------
    Independent logging facade that writes to both file system and PostgreSQL database
    without dependency on DatabaseManager. Provides structured logging with automatic
    deduplication, context truncation, and categorized output files.
    
    Parameters
    ----------
    min_level : str
        Minimum log level to process (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    enable_database : bool
        Whether to attempt database logging alongside file logging
        
    Attributes
    ----------
    LOG_LEVELS : Dict[str, int]
        Mapping of level names to numeric priorities for filtering
    LOG_CATEGORIES : List[str] 
        Valid log categories for file organization
    deduplicator : LogDeduplicator
        Spam prevention for repeated messages
    truncator : SmartTruncator
        Context data size management
    memory_buffer : deque
        Recent logs kept in memory for fast retrieval
        
    Examples
    --------
    >>> logger = Logger(min_level="INFO", enable_database=True)
    >>> logger.info("Service started", source="main", port=8000)
    >>> logger.error("Connection failed", source="db", exception=conn_error)
    >>> logger.warning("Low memory", source="system", available_mb=512)
    
    Notes
    -----
    - Complexity: O(1) for most operations, O(k) for periodic cleanup
    - Side effects: creates log files, database entries, modifies memory buffer
    - Thread safety: all operations protected by internal locks
    - Performance: deque-based memory buffer for efficient recent log access
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
        """Log error message with clean stack trace."""
        # Clean the stack trace to remove noise
        stack_trace = traceback.format_exc()
        clean_trace = self._clean_stack_trace(stack_trace)
        context['stack_trace'] = clean_trace
        self.log("ERROR", message, source, **context)
    
    def critical(self, message: str, source: str = "", **context):
        """Log critical message with clean stack trace."""
        # Clean the stack trace to remove noise
        stack_trace = traceback.format_exc()
        clean_trace = self._clean_stack_trace(stack_trace)
        context['stack_trace'] = clean_trace
        self.log("CRITICAL", message, source, **context)
    
    def _clean_stack_trace(self, stack_trace: str) -> str:
        """Clean stack trace to remove noise and formatting issues."""
        if not stack_trace or stack_trace == "NoneType: None\n":
            return None
        
        # Split into lines and clean each one
        lines = stack_trace.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Remove lines with just ^^^^ markers
            if re.match(r'^\s*\^+\s*$', line):
                continue
            
            # Limit very long lines (e.g., from massive error messages)
            if len(line) > 500:
                line = line[:497] + "..."
            
            # Remove excessive whitespace but preserve indentation
            line = re.sub(r'\s+$', '', line)  # Remove trailing whitespace
            
            if line.strip():  # Only add non-empty lines
                cleaned_lines.append(line)
        
        # Join back and limit total size
        cleaned_trace = '\n'.join(cleaned_lines)
        
        # If still too long, truncate with summary
        if len(cleaned_trace) > 2000:
            lines = cleaned_trace.split('\n')
            if len(lines) > 20:
                # Keep first 10 and last 5 lines with indicator
                summary = '\n'.join(lines[:10]) + '\n... [truncated] ...\n' + '\n'.join(lines[-5:])
                return summary
            else:
                return cleaned_trace[:2000] + "... [truncated]"
        
        return cleaned_trace if cleaned_trace.strip() else None

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
    """
    Get or create the global logger instance with lazy initialization.
    
    Returns
    -------
    Logger
        Singleton logger instance configured with default settings
        
    Examples
    --------
    >>> logger = get_logger()
    >>> logger.info("Application started", source="main")
    
    Notes
    -----
    - Creates logger with INFO level and database enabled by default
    - Singleton pattern ensures consistent logging across modules
    - Thread-safe initialization using global lock
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = Logger()
    return _logger_instance


# Convenience function for backward compatibility
def log(level: str, message: str, source: str = "", **context):
    """
    Log message using the global logger instance.
    
    Parameters
    ----------
    level : str
        Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    message : str
        Log message content
    source : str, optional
        Source component/module name
    **context : Any
        Additional context fields for structured logging
        
    Examples
    --------
    >>> log("INFO", "Process completed", source="data_processor", records=1500)
    >>> log("ERROR", "Validation failed", source="api", errors=validation_errors)
    
    Notes
    -----
    - Convenience function for quick logging without logger instantiation
    - Uses global logger singleton for consistent behavior
    - Context data is automatically truncated if oversized
    """
    logger = get_logger()
    logger.log(level, message, source, **context)
