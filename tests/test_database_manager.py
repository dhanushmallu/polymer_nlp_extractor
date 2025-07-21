# polymer_extractor/tests/test_database_manager.py

import os
from appwrite.exception import AppwriteException
from polymer_extractor.storage.appwrite_client import get_database_id
from polymer_extractor.storage.database_manager import DatabaseManager
from polymer_extractor.utils.paths import LOGS_DIR

# Test constants
TEST_COLLECTION = "test_collection"
TEST_DOCUMENT_DATA = {
    "title": "Test Document Title",
    "is_active": True,
    "count": 1
}

UPDATED_DOCUMENT_DATA = {
    "title": "Updated Document Title",
    "is_active": False,
    "count": 2
}

APPWRITE_DATABASE_ID = get_database_id()


def check_logs_for(keyword: str) -> bool:
    """
    Check system.log for a specific keyword.
    """
    system_log_file = os.path.join(LOGS_DIR, "system.log")
    if not os.path.exists(system_log_file):
        print("[TEST] system.log not found.")
        return False

    with open(system_log_file, "r", encoding="utf-8") as f:
        return any(keyword in line for line in f.readlines())


def test_database_manager():
    dbm = DatabaseManager()

    # === Collection Tests ===
    print("\n[TEST] Creating test collection...")
    try:
        dbm.create_collection(TEST_COLLECTION, "Test Collection")
        assert check_logs_for(f"Created collection '{TEST_COLLECTION}'")
    except Exception as e:
        print(f"[ERROR] Create collection failed: {e}")

    print("[TEST] Listing collections...")
    collections = dbm.list_collections()
    assert any(c['$id'] == TEST_COLLECTION for c in collections)

    # === Attribute Tests ===
    print("[TEST] Creating string attribute...")
    dbm.create_attribute(TEST_COLLECTION, "string", "title", size=255, required=True)
    assert check_logs_for("Created string attribute 'title'")

    print("[TEST] Creating boolean attribute...")
    dbm.create_attribute(TEST_COLLECTION, "boolean", "is_active", required=False, default=True)
    assert check_logs_for("Created boolean attribute 'is_active'")

    print("[TEST] Creating integer attribute...")
    dbm.create_attribute(TEST_COLLECTION, "integer", "count", required=False, default=0)
    assert check_logs_for("Created integer attribute 'count'")

    # === Document Tests ===
    print("[TEST] Creating document...")
    doc = dbm.create_document(TEST_COLLECTION, TEST_DOCUMENT_DATA)
    doc_id = doc['$id']
    assert check_logs_for("Created document in")

    print("[TEST] Fetching document...")
    fetched_doc = dbm.get_document(TEST_COLLECTION, doc_id)
    assert fetched_doc['title'] == "Test Document Title"

    print("[TEST] Updating document...")
    dbm.update_document(TEST_COLLECTION, doc_id, UPDATED_DOCUMENT_DATA)
    updated_doc = dbm.get_document(TEST_COLLECTION, doc_id)
    assert updated_doc['title'] == "Updated Document Title"
    assert updated_doc['count'] == 2

    print("[TEST] Listing documents...")
    docs = dbm.list_documents(TEST_COLLECTION)
    assert any(d['$id'] == doc_id for d in docs)

    print("[TEST] Deleting document...")
    dbm.delete_document(TEST_COLLECTION, doc_id)
    assert check_logs_for("Deleted document")

    # === Cleanup ===
    print("[TEST] Deleting test collection...")
    try:
        dbm.delete_collection(TEST_COLLECTION)
        assert check_logs_for(f"Deleted collection '{TEST_COLLECTION}'")
    except AppwriteException as e:
        if e.code == 404:
            print("[TEST] Collection already deleted.")

    print("\n=== All DatabaseManager Tests Passed ===")


if __name__ == "__main__":
    test_database_manager()
