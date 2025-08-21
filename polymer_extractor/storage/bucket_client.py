"""
Compatibility shim: bucket_client now re-exports the new storage client.

Prefer using polymer_extractor.storage.storage_client instead.
"""

from typing import Any, Dict, List
from polymer_extractor.utils.logging import Logger
import importlib


def _load_storage():
    try:
        mod = importlib.import_module("polymer_extractor.storage.storage_client")
    except Exception:  # pragma: no cover
        mod = importlib.import_module(".storage_client", package=__package__)
    return mod.StorageClient, mod.get_storage_client


_StorageClient, _get_storage_client = _load_storage()

# Public aliases
BucketClient = _StorageClient


def get_bucket_client():
    return _get_storage_client()

logger = Logger()


# Backward-compat convenience
def get_storage_service():
    logger.warning(
        "get_storage_service() is deprecated. Use get_bucket_client() instead.",
        source="bucket_client",
    )
    return get_bucket_client()


def get_client():
    logger.warning(
        "get_client() is deprecated. Use get_bucket_client() instead.",
        source="bucket_client",
    )
    return get_bucket_client()


def get_database_service():
    logger.warning(
        "get_database_service() is deprecated. Database functionality moved to database_manager.py",
        source="bucket_client",
    )
    raise NotImplementedError("Database functionality moved to database_manager.py")


def get_database_id():
    logger.warning(
        "get_database_id() is deprecated. Database functionality moved to database_manager.py",
        source="bucket_client",
    )
    raise NotImplementedError("Database functionality moved to database_manager.py")


def test_connection() -> bool:
    logger.warning(
        "test_connection() is deprecated. Use get_bucket_client().test_connection() instead.",
        source="bucket_client",
    )
    client = get_bucket_client()
    result = client.test_connection()
    return result.get("success", False) if isinstance(result, dict) else bool(result)
