"""
Compatibility wrapper for legacy BucketManager, now backed by StorageManager.
"""

from typing import Any, Dict, List, Optional, Union
from polymer_extractor.utils.logging import Logger
try:
    from polymer_extractor.storage.storage_manager import StorageManager as _StorageManager  # type: ignore
except Exception:  # pragma: no cover - fallback for local tooling
    from .storage_manager import StorageManager as _StorageManager  # type: ignore

logger = Logger()


class BucketManager(_StorageManager):
    """Deprecated: use StorageManager. This class proxies to StorageManager.

    Methods keep the legacy names but delegate to the new storage layer.
    """

    def __init__(self):
        super().__init__()
        logger.warning("BucketManager is deprecated. Use StorageManager instead.", source="bucket_manager")

    # --- Legacy API (compat) ---
    # Keep signatures used by existing tests/callers.

    def create_bucket(self, bucket_name: str, *_: str) -> dict:  # ignore extra args like label/description
        res = super().create_bucket(bucket_name)
        logger.info(f"Created bucket '{bucket_name}'", source="bucket_manager")
        return res

    def upload_file(self, bucket: str, local_path: str) -> dict:
        import os
        dest_key = f"{bucket}/{os.path.basename(local_path)}"
        res = super().upload_from_path(local_path, dest_key)
        logger.info(f"Uploaded file '{os.path.basename(local_path)}'", source="bucket_manager")
        return res

    def list_files(self, bucket: str):
        return super().list_resources(bucket)

    def download_file(self, bucket: str, file_id: str, dest_local_path: str) -> bool:
        key = file_id if file_id.startswith(f"{bucket}/") else f"{bucket}/{file_id}"
        ok = super().download_to_path(key, dest_local_path)
        if ok:
            logger.info(f"Downloaded file '{file_id}'", source="bucket_manager")
        return ok

    def delete_file(self, bucket: str, file_id: str) -> bool:
        key = file_id if file_id.startswith(f"{bucket}/") else f"{bucket}/{file_id}"
        ok = super().delete_resource(key)
        if ok:
            logger.info(f"Deleted file '{file_id}'", source="bucket_manager")
        return ok

    def file_exists(self, bucket: str, file_id: str) -> bool:
        key = file_id if file_id.startswith(f"{bucket}/") else f"{bucket}/{file_id}"
        return super().resource_exists(key)

    def get_file_metadata(self, bucket: str, file_id: str) -> dict:
        key = file_id if file_id.startswith(f"{bucket}/") else f"{bucket}/{file_id}"
        return super().get_resource_metadata(key)

    def delete_bucket(self, bucket_name: str) -> bool:
        ok = super().delete_bucket(bucket_name)
        if ok:
            logger.info(f"Deleted bucket '{bucket_name}'", source="bucket_manager")
        return ok

