# polymer_extractor/tests/test_appwrite_client.py

import os

from polymer_extractor.storage import appwrite_client
from polymer_extractor.utils.paths import LOGS_DIR


def check_logs_for(keyword: str):
    """
    Check system.log for a specific keyword.

    Parameters
    ----------
    keyword : str
        Text to search for in system.log.

    Returns
    -------
    bool
        True if keyword is found, False otherwise.
    """
    system_log_file = os.path.join(LOGS_DIR, "system.log")
    if not os.path.exists(system_log_file):
        print("[TEST] system.log file not found.")
        return False

    with open(system_log_file, "r", encoding="utf-8") as f:
        for line in f.readlines():
            if keyword in line:
                return True
    return False


def test_client_initialization():
    """
    Test if Appwrite Client initializes and logs correctly.
    """
    try:
        client = appwrite_client.get_client()
        # Simple functional test: get a Databases service and list collections
        db_service = appwrite_client.get_database_service()
        db_service.list_collections(appwrite_client.APPWRITE_DATABASE_ID)
        print("[TEST] get_client() initialized successfully.")
        assert check_logs_for("Appwrite Client initialized successfully.")
    except Exception as e:
        print(f"[TEST] get_client() failed: {e}")
        assert check_logs_for("Failed to initialize Appwrite Client.")


def test_database_service():
    """
    Test if Appwrite Databases service initializes and logs correctly.
    """
    try:
        db_service = appwrite_client.get_database_service()
        assert db_service is not None
        print("[TEST] get_database_service() initialized successfully.")
    except Exception as e:
        print(f"[TEST] get_database_service() failed: {e}")
        assert check_logs_for("Failed to get Databases service.")


def test_storage_service():
    """
    Test if Appwrite Storage service initializes and logs correctly.
    """
    try:
        storage_service = appwrite_client.get_storage_service()
        assert storage_service is not None
        print("[TEST] get_storage_service() initialized successfully.")
    except Exception as e:
        print(f"[TEST] get_storage_service() failed: {e}")
        assert check_logs_for("Failed to get Storage service.")


def test_connection_check():
    """
    Test the Appwrite connection using test_connection().
    """
    result = appwrite_client.test_connection()
    if result:
        print("[TEST] test_connection() succeeded.")
        assert check_logs_for("Appwrite connection test successful.")
    else:
        print("[TEST] test_connection() failed.")
        assert check_logs_for("Appwrite connection test failed.")


if __name__ == "__main__":
    print("=== Running Appwrite Client Tests ===")
    test_client_initialization()
    test_database_service()
    test_storage_service()
    test_connection_check()
    print("=== Appwrite Client Tests Completed ===")
