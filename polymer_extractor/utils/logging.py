# polymer_extractor/utils/logging.py

import inspect
import json
import os
import traceback
from datetime import datetime
from typing import Optional, Dict

from appwrite.client import Client
from appwrite.exception import AppwriteException
from appwrite.id import ID
from appwrite.services.databases import Databases

from polymer_extractor.utils.paths import LOGS_DIR, APPWRITE_LOGS_COLLECTION


class Logger:
    """
    Centralized logging system for Polymer NLP.
    Handles category-specific local logs and Appwrite synced logs.

    On initialization, ensures the Appwrite logs collection and local log files exist.
    """

    LOG_CATEGORIES = ["system", "api", "user"]

    def __init__(self):
        """
        Initialize the logger.
        Ensures Appwrite log collection and local category log files exist.
        """
        os.makedirs(LOGS_DIR, exist_ok=True)

        # Set local log files per category
        self.local_log_files = {
            category: os.path.join(LOGS_DIR, f"{category}.log")
            for category in self.LOG_CATEGORIES
        }

        # Initialize Appwrite client
        self.client = Client()
        self.client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
        self.client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
        self.client.set_key(os.getenv("APPWRITE_API_KEY"))

        self.databases = Databases(self.client)
        self.database_id = os.getenv("APPWRITE_DATABASE_ID")
        self.collection_id = APPWRITE_LOGS_COLLECTION

        try:
            self._ensure_appwrite_log_collection()
        except Exception as e:
            print(f"[Logger Init ERROR] Failed to initialize Appwrite log collection: {e}")

        # Ensure all local log files exist
        for category, path in self.local_log_files.items():
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    f.write("")  # Create empty log file

    def _ensure_appwrite_log_collection(self) -> None:
        """
        Check if Appwrite logs collection exists. If not, create it with all required attributes.
        """
        try:
            self.databases.get_collection(self.database_id, self.collection_id)
        except AppwriteException as e:
            if e.code == 404:
                self.databases.create_collection(
                    database_id=self.database_id,
                    collection_id=self.collection_id,
                    name="System Logs",
                    document_security=False
                )
                # Define attributes
                attributes = [
                    ("timestamp", "string", False),
                    ("level", "string", False),
                    ("message", "string", False),
                    ("source", "string", False),
                    ("event_type", "string", False),
                    ("user_action", "boolean", False),
                    ("context", "string", True),
                    ("stack_trace", "string", True),
                    ("file_name", "string", False),
                    ("line_number", "integer", False),
                    ("local_log_file", "string", False),
                    ("synced_to_appwrite", "boolean", False),
                    ("log_id", "string", False)  # Added log_id attribute
                ]
                for attr_name, attr_type, is_nullable in attributes:
                    if attr_type == "string":
                        self.databases.create_string_attribute(
                            database_id=self.database_id,
                            collection_id=self.collection_id,
                            key=attr_name,
                            size=2048,  # Specify size for string attributes
                            required=not is_nullable
                        )
                    elif attr_type == "integer":
                        self.databases.create_integer_attribute(
                            database_id=self.database_id,
                            collection_id=self.collection_id,
                            key=attr_name,
                            required=not is_nullable
                        )
                    elif attr_type == "boolean":
                        self.databases.create_boolean_attribute(
                            database_id=self.database_id,
                            collection_id=self.collection_id,
                            key=attr_name,
                            required=not is_nullable
                        )
            else:
                raise

    def _write_to_local(self, entry: Dict, category: str) -> None:
        """
        Append log entry to the appropriate local log file.

        Parameters
        ----------
        entry : dict
            Log entry data.
        category : str
            Log category (system, api, user).
        """
        log_file = self.local_log_files.get(category, self.local_log_files["system"])
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _sync_to_appwrite(self, entry: Dict) -> Optional[str]:
        """
        Sync log entry to Appwrite.

        Returns
        -------
        str or None
            Document ID if synced successfully.
        """
        try:
            # Ensure context is a valid string
            if isinstance(entry.get("context"), dict):
                entry["context"] = json.dumps(entry["context"], ensure_ascii=False)

            # Truncate message to fit 512 char limit
            if entry.get("message") and len(entry["message"]) > 512:
                entry["message"] = entry["message"][:509] + "..."

            # Ensure all string fields are within limits
            string_fields = ["source", "event_type", "file_name", "local_log_file"]
            for field in string_fields:
                if entry.get(field) and len(str(entry[field])) > 512:
                    entry[field] = str(entry[field])[:509] + "..."

            entry["log_id"] = ID.unique()  # Generate unique log ID
            response = self.databases.create_document(
                database_id=self.database_id,
                collection_id=self.collection_id,
                document_id=entry["log_id"],
                data=entry
            )
            return response['$id']
        except AppwriteException as e:
            print(f"[Logger Sync ERROR] Failed to sync log to Appwrite: {e}")
            return None

    def log(self, level: str, message: str, source: str,
            category: str = "system", event_type: str = "general",
            user_action: bool = False, context: Optional[Dict] = None,
            error: Optional[Exception] = None) -> None:
        """
        Create a log entry and handle local & Appwrite logging.

        Parameters
        ----------
        level : str
            Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL').
        message : str
            Human-readable message.
        source : str
            Origin module/component.
        category : str, optional
            Log file category (system, api, user). Defaults to 'system'.
        event_type : str, optional
            Event category. Defaults to 'general'.
        user_action : bool, optional
            True if triggered by user. Defaults to False.
        context : dict, optional
            Extra context info.
        error : Exception, optional
            Exception for stack trace.
        """
        if category not in self.LOG_CATEGORIES:
            category = "system"  # Default to system if unknown

        frame = inspect.stack()[1]
        file_name = os.path.basename(frame.filename)
        line_number = frame.lineno
        timestamp = datetime.now().isoformat() + "Z"

        stack_trace = traceback.format_exc() if error else ""
        full_stack_trace = traceback.format_exc() if error else None
        entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
            "source": source,
            "event_type": event_type,
            "user_action": user_action,
            "context": context or {},
            "stack_trace": full_stack_trace,
            "file_name": file_name,
            "line_number": line_number,
            "local_log_file": self.local_log_files[category],
            "synced_to_appwrite": False,
            "log_id": None
        }

        truncated_stack_trace = (stack_trace[:500] + "...") if len(stack_trace) > 500 else stack_trace
        cloud_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
            "source": source,
            "event_type": event_type,
            "user_action": user_action,
            "context": context or {},
            "stack_trace": truncated_stack_trace,
            "file_name": file_name,
            "line_number": line_number,
            "local_log_file": self.local_log_files[category],
            "synced_to_appwrite": False,
            "log_id": None
        }

        self._write_to_local(entry, category)
        log_id = self._sync_to_appwrite(cloud_entry)
        if log_id:
            entry["synced_to_appwrite"] = True
            entry["log_id"] = log_id

        # Append updated entry with sync info
        self._write_to_local(entry, category)

    # Shortcut methods
    def info(self, message: str, source: str, **kwargs):
        self.log("INFO", message, source, **kwargs)

    def error(self, message: str, source: str, error=None, **kwargs):
        self.log("ERROR", message, source, error=error, **kwargs)

    def debug(self, message: str, source: str, **kwargs):
        self.log("DEBUG", message, source, **kwargs)

    def warning(self, message: str, source: str, **kwargs):
        self.log("WARNING", message, source, **kwargs)

    def critical(self, message: str, source: str, **kwargs):
        self.log("CRITICAL", message, source, **kwargs)
