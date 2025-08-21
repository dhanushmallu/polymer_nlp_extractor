"""Storage package exports and compatibility shims."""

try:
	from polymer_extractor.storage.storage_client import StorageClient, get_storage_client  # type: ignore # noqa: F401
	from polymer_extractor.storage.storage_manager import StorageManager, get_storage_manager  # type: ignore # noqa: F401
except Exception:  # pragma: no cover - fallback for local tooling
	from .storage_client import StorageClient, get_storage_client  # type: ignore # noqa: F401
	from .storage_manager import StorageManager, get_storage_manager  # type: ignore # noqa: F401
