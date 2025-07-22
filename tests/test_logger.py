# polymer_extractor/tests/test_logger.py

import json
import os
import time

from polymer_extractor.utils.logging import Logger
from polymer_extractor.utils.paths import LOGS_DIR


def test_logger_initialization():
    """
    Test if Logger initializes correctly:
    - Local log files created
    - Appwrite collection check runs without error
    """
    logger = Logger()
    for category in logger.LOG_CATEGORIES:
        log_file = os.path.join(LOGS_DIR, f"{category}.log")
        assert os.path.exists(log_file), f"Missing log file: {log_file}"
    print("[TEST] Logger initialization passed.")


def test_local_logging():
    """
    Test if a log entry is written to the correct local file.
    """
    logger = Logger()
    logger.info("This is a test INFO log", source="test_local_logging", category="system")
    logger.error("This is a test ERROR log", source="test_local_logging", error=Exception("Test error"), category="api")
    logger.debug("This is a test DEBUG log", source="test_local_logging", category="user")

    for category in logger.LOG_CATEGORIES:
        log_file = os.path.join(LOGS_DIR, f"{category}.log")
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) > 0, f"No log entries in {log_file}"
            last_entry = json.loads(lines[-1])
            assert "timestamp" in last_entry
            assert "level" in last_entry
            assert "message" in last_entry
            assert "file_name" in last_entry
            assert "line_number" in last_entry
            print(f"[TEST] Log entry verified in {category}.log")

    print("[TEST] Local logging passed.")


def test_appwrite_sync():
    """
    Test if log entries sync to Appwrite (if Appwrite is configured).
    """
    logger = Logger()
    logger.info("Appwrite sync test log", source="test_appwrite_sync", category="system")
    time.sleep(2)  # Wait for potential async sync

    # Check if last entry in system.log shows synced_to_appwrite = True
    log_file = os.path.join(LOGS_DIR, "system.log")
    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        last_entry = json.loads(lines[-1])
        if os.getenv("APPWRITE_API_KEY"):
            assert last_entry["synced_to_appwrite"] is True, "Log not synced to Appwrite"
            print("[TEST] Appwrite sync verified.")
        else:
            print("[TEST] Appwrite API key not set. Skipping sync test.")


if __name__ == "__main__":
    print("=== Running Logger Tests ===")
    test_logger_initialization()
    test_local_logging()
    test_appwrite_sync()
    print("=== All Logger Tests Completed ===")
