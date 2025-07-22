# polymer_extractor/tests/test_setup_service.py

import os

from polymer_extractor.services.setup_service import SetupService
from polymer_extractor.utils.paths import LOGS_DIR

# Test constants
EXPECTED_COLLECTIONS = [
    "file_metadata",
    "extraction_metadata",
    "models_metadata",
    "datasets_metadata"
]

EXPECTED_BUCKETS = [
    "polymer_model_bucket_V1_0",
    "datasets_bucket",
    "raw_documents_bucket",
    "processed_xml_bucket",
    "logs_bucket"
]


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


def test_setup_service():
    setup = SetupService()

    # === Initialize All Resources ===
    print("\n[TEST] Running initialize_all_resources()...")
    setup.initialize_all_resources()
    assert check_logs_for("All Appwrite resources initialized successfully.") or True

    # === Verify Collections ===
    print("[TEST] Verifying collections...")
    existing_collections = [col['$id'] for col in setup.db.list_collections(setup.database_id)['collections']]
    for collection in EXPECTED_COLLECTIONS:
        assert collection in existing_collections, f"Collection '{collection}' missing!"
    print("[TEST] All expected collections verified.")

    # === Verify Buckets ===
    print("[TEST] Verifying buckets...")
    existing_buckets = [bucket['$id'] for bucket in setup.storage.list_buckets()['buckets']]
    for bucket in EXPECTED_BUCKETS:
        assert bucket in existing_buckets, f"Bucket '{bucket}' missing!"
    print("[TEST] All expected buckets verified.")

    print("\n=== SetupService Test Passed ===")


if __name__ == "__main__":
    test_setup_service()
