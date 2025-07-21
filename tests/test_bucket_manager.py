# polymer_extractor/tests/test_bucket_manager.py

import os
from appwrite.exception import AppwriteException
from polymer_extractor.storage.bucket_manager import BucketManager
from polymer_extractor.utils.paths import WORKSPACE_DIR, LOGS_DIR

# Test constants
TEST_BUCKET = "test_bucket_manager"
DUMMY_FILE_NAME = "dummy_research_paper.pdf"
DUMMY_FILE_PATH = os.path.join(WORKSPACE_DIR, "public", "grobid", DUMMY_FILE_NAME)
DOWNLOADED_FILE_NAME = "downloaded_dummy_research_paper.pdf"
DOWNLOADED_FILE_PATH = os.path.join(WORKSPACE_DIR, DOWNLOADED_FILE_NAME)


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


def test_bucket_manager():
    manager = BucketManager()

    # === Create Test Bucket ===
    print("\n[TEST] Creating test bucket...")
    try:
        manager.create_bucket(TEST_BUCKET, "Test Bucket Manager")
        assert check_logs_for(f"Created bucket '{TEST_BUCKET}'")
    except Exception as e:
        print(f"[ERROR] Failed to create bucket: {e}")

    # === Upload Dummy File ===
    print("[TEST] Uploading dummy file...")
    uploaded_file = manager.upload_file(TEST_BUCKET, DUMMY_FILE_PATH)
    file_id = uploaded_file['$id']
    assert check_logs_for(f"Uploaded file '{DUMMY_FILE_NAME}'")

    # === List Files ===
    print("[TEST] Listing files in bucket...")
    files = manager.list_files(TEST_BUCKET)
    assert any(f['$id'] == file_id for f in files)

    # === Download File ===
    print("[TEST] Downloading file...")
    manager.download_file(TEST_BUCKET, file_id, DOWNLOADED_FILE_PATH)
    assert os.path.exists(DOWNLOADED_FILE_PATH)
    assert check_logs_for(f"Downloaded file '{file_id}'")

    # === Delete File ===
    print("[TEST] Deleting file...")
    manager.delete_file(TEST_BUCKET, file_id)
    assert check_logs_for(f"Deleted file '{file_id}'")

    # === Delete Bucket ===
    print("[TEST] Deleting test bucket...")
    try:
        manager.delete_bucket(TEST_BUCKET)
        assert check_logs_for(f"Deleted bucket '{TEST_BUCKET}'")
    except AppwriteException as e:
        if e.code == 404:
            print("[TEST] Bucket already deleted.")

    # === Cleanup Downloaded File ===
    if os.path.exists(DOWNLOADED_FILE_PATH):
        os.remove(DOWNLOADED_FILE_PATH)

    print("\n=== All BucketManager Tests Passed ===")


if __name__ == "__main__":
    test_bucket_manager()
