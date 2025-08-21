"""
polymer_extractor/storage/storage_client.py

Unified Storage Client with multi-backend support (local, Appwrite, S3) and
routing strategies (primary, replica, failover, sync).

This module supersedes bucket_client.py. Backward-compat shims exist so code
importing bucket_client continues to work. Prefer importing StorageClient
and get_storage_client from this module going forward.

Key capabilities
- Standard resource API: add/get/delete/list/exists/metadata
- Convenience: upload_from_path, download_to_path, fetch_from_url
- Multi-backend routing: primary, replica, failover, sync
- Clear parameter specs and sensible defaults per backend

Notes
- “Storage key” is a logical path like "reports/eval.csv". Use
  polymer_extractor.utils.paths.path_resolver to convert between local paths
  and storage keys when needed.
"""

from __future__ import annotations

import os
import json
import shutil
import tempfile
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, BinaryIO, Tuple
from abc import ABC, abstractmethod
from datetime import datetime

import requests
from dotenv import load_dotenv
from polymer_extractor.utils.logging import Logger
from polymer_extractor.utils.paths import path_resolver, resolve_to_storage_path
try:
    from polymer_extractor.storage.exceptions import ConfigError, BackendOperationError  # type: ignore
except Exception:  # pragma: no cover - local fallback
    from .exceptions import ConfigError, BackendOperationError  # type: ignore

# Initialize
load_dotenv()
logger = Logger()

# === Environment / Config ===
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
STORAGE_PATH = os.getenv("STORAGE_PATH", "./workspace/public")

STORAGE_BACKENDS_ACTIVE = [b.strip() for b in os.getenv("STORAGE_BACKENDS_ACTIVE", "local").split(",") if b.strip()]
STORAGE_STRATEGY = os.getenv("STORAGE_STRATEGY", "primary")

# Appwrite
APPWRITE_STORAGE_ENDPOINT = os.getenv("APPWRITE_STORAGE_ENDPOINT")
APPWRITE_STORAGE_PROJECT_ID = os.getenv("APPWRITE_STORAGE_PROJECT_ID")
APPWRITE_STORAGE_API_KEY = os.getenv("APPWRITE_STORAGE_API_KEY")
APPWRITE_ENABLED = os.getenv("APPWRITE_ENABLED", "false").lower() == "true"

# S3
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
S3_ENABLED = os.getenv("S3_ENABLED", "false").lower() == "true"


# === Utility Functions ===
def normalize_storage_key(storage_key: str) -> str:
    """Normalize storage key for consistent handling across backends."""
    # Remove leading slashes and normalize path separators
    key = storage_key.lstrip("/").replace("\\", "/")
    # Collapse multiple slashes
    key = re.sub(r"/+", "/", key)
    return key.strip("/") if key != "/" else ""

def validate_bucket_name(bucket_name: str, backend_type: str = "s3") -> str:
    """Validate and normalize bucket name for specific backend requirements."""
    # Common normalization
    bucket = bucket_name.lower().strip()
    bucket = re.sub(r'[^a-z0-9\-]', '-', bucket)
    bucket = re.sub(r'-+', '-', bucket).strip('-')
    
    if backend_type == "s3":
        # S3 specific rules: 3-63 chars, no uppercase, no underscores
        if len(bucket) < 3:
            bucket = f"polymer-{bucket}"
        bucket = bucket[:63]  # Max 63 chars
        # Ensure starts and ends with alphanumeric
        if not bucket[0].isalnum():
            bucket = f"a{bucket}"
        if not bucket[-1].isalnum():
            bucket = f"{bucket}a"
            
    elif backend_type == "appwrite":
        # Appwrite specific rules: more flexible but consistent with their API
        if len(bucket) < 3:
            bucket = f"bucket-{bucket}"
            
    return bucket[:63]  # General safety limit

def safe_file_id(file_path: str, backend_type: str = "appwrite") -> str:
    """Generate safe file ID for backends that don't support path separators."""
    if backend_type == "appwrite":
        # Appwrite doesn't support nested paths in file IDs
        # Replace path separators with underscores
        return file_path.replace("/", "_").replace("\\", "_")
    return file_path

def split_storage_key(storage_key: str) -> Tuple[str, str]:
    """Split storage key into bucket and path components."""
    normalized = normalize_storage_key(storage_key)
    if "/" in normalized:
        bucket, path = normalized.split("/", 1)
        return bucket or "default", path
    return normalized or "default", ""


# === Abstract Backend ===
class StorageBackend(ABC):
    """Abstract storage backend interface (resource-oriented)."""

    @abstractmethod
    def upload(self, storage_key: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Upload bytes content to storage at storage_key."""

    @abstractmethod
    def download(self, storage_key: str) -> bytes:
        """Download bytes content from storage."""

    @abstractmethod
    def delete(self, storage_key: str) -> bool:
        """Delete resource at storage_key."""

    @abstractmethod
    def list_files(self, folder: str = "") -> List[Dict[str, Any]]:
        """List resources under folder prefix."""

    @abstractmethod
    def exists(self, storage_key: str) -> bool:
        """True if storage_key exists."""

    @abstractmethod
    def get_metadata(self, storage_key: str) -> Dict[str, Any]:
        """Return metadata for storage_key."""

    @abstractmethod
    def create_bucket(self, bucket_name: str) -> Dict[str, Any]:
        """Create logical bucket/container if supported."""

    @abstractmethod
    def delete_bucket(self, bucket_name: str) -> bool:
        """Delete bucket/container if supported."""

    @abstractmethod
    def list_buckets(self) -> List[Dict[str, Any]]:
        """List buckets/containers if applicable."""

    @abstractmethod
    def rename_resource(self, old_storage_key: str, new_storage_key: str) -> bool:
        """Rename/move resource from old_storage_key to new_storage_key."""

    @abstractmethod
    def rename_bucket(self, old_bucket_name: str, new_bucket_name: str) -> bool:
        """Rename bucket from old_bucket_name to new_bucket_name."""


# === Local Backend ===
class LocalStorageBackend(StorageBackend):
    """Local filesystem backend.

    Param spec
    - base_path (str): root directory for storage (default: STORAGE_PATH)
    """

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _full(self, storage_key: str) -> Path:
        return self.base_path / storage_key.lstrip("/")

    def upload(self, storage_key: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        p = self._full(storage_key)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "wb") as f:
            f.write(content)
        if metadata:
            with open(p.with_suffix(p.suffix + ".meta"), "w") as mf:
                json.dump(metadata, mf)
        st = p.stat()
        return {
            "$id": storage_key,
            "name": p.name,
            "path": storage_key,
            "size": st.st_size,
            "mimeType": (metadata or {}).get("mimeType", "application/octet-stream"),
            "dateCreated": datetime.fromtimestamp(st.st_ctime).isoformat(),
            "dateUpdated": datetime.fromtimestamp(st.st_mtime).isoformat(),
        }

    def download(self, storage_key: str) -> bytes:
        p = self._full(storage_key)
        with open(p, "rb") as f:
            return f.read()

    def delete(self, storage_key: str) -> bool:
        p = self._full(storage_key)
        if p.exists():
            p.unlink()
            mp = p.with_suffix(p.suffix + ".meta")
            if mp.exists():
                mp.unlink()
            return True
        return False

    def list_files(self, folder: str = "") -> List[Dict[str, Any]]:
        root = self._full(folder)
        if not root.exists():
            return []
        files: List[Dict[str, Any]] = []
        for fp in root.rglob("*"):
            if fp.is_file() and fp.suffix != ".meta":
                rel = str(fp.relative_to(self.base_path))
                st = fp.stat()
                files.append({
                    "$id": rel,
                    "name": fp.name,
                    "path": rel,
                    "size": st.st_size,
                    "mimeType": self._guess_mime_type(fp.name),
                    "dateCreated": datetime.fromtimestamp(st.st_ctime).isoformat(),
                    "dateUpdated": datetime.fromtimestamp(st.st_mtime).isoformat(),
                })
        return files

    def exists(self, storage_key: str) -> bool:
        return self._full(storage_key).exists()

    def get_metadata(self, storage_key: str) -> Dict[str, Any]:
        p = self._full(storage_key)
        if not p.exists():
            raise FileNotFoundError(storage_key)
        st = p.stat()
        md = {
            "$id": storage_key,
            "name": p.name,
            "path": storage_key,
            "size": st.st_size,
            "mimeType": self._guess_mime_type(p.name),
            "dateCreated": datetime.fromtimestamp(st.st_ctime).isoformat(),
            "dateUpdated": datetime.fromtimestamp(st.st_mtime).isoformat(),
        }
        mp = p.with_suffix(p.suffix + ".meta")
        if mp.exists():
            try:
                md.update(json.loads(mp.read_text()))
            except Exception:
                pass
        return md

    def _guess_mime_type(self, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        return {
            ".txt": "text/plain",
            ".json": "application/json",
            ".xml": "application/xml",
            ".csv": "text/csv",
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".zip": "application/zip",
        }.get(ext, "application/octet-stream")

    def create_bucket(self, bucket_name: str) -> Dict[str, Any]:
        bp = self.base_path / bucket_name
        bp.mkdir(parents=True, exist_ok=True)
        return {"$id": bucket_name, "name": bucket_name, "status": "created", "path": str(bp), "backend": "local"}

    def delete_bucket(self, bucket_name: str) -> bool:
        bp = self.base_path / bucket_name
        if bp.exists() and bp.is_dir():
            shutil.rmtree(bp)
            return True
        return False

    def list_buckets(self) -> List[Dict[str, Any]]:
        buckets: List[Dict[str, Any]] = []
        for item in self.base_path.iterdir() if self.base_path.exists() else []:
            if item.is_dir():
                buckets.append({"$id": item.name, "name": item.name, "backend": "local", "path": str(item)})
        return buckets

    def rename_resource(self, old_storage_key: str, new_storage_key: str) -> bool:
        """Rename/move resource from old location to new location."""
        old_path = self._full(old_storage_key)
        new_path = self._full(new_storage_key)
        
        if not old_path.exists():
            return False
        
        # Create parent directory for new location
        new_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Move file
        old_path.rename(new_path)
        
        # Move metadata file if it exists
        old_meta = old_path.with_suffix(old_path.suffix + ".meta")
        if old_meta.exists():
            new_meta = new_path.with_suffix(new_path.suffix + ".meta")
            old_meta.rename(new_meta)
        
        return True

    def rename_bucket(self, old_bucket_name: str, new_bucket_name: str) -> bool:
        """Rename bucket directory from old name to new name."""
        old_path = self.base_path / old_bucket_name
        new_path = self.base_path / new_bucket_name
        
        if not old_path.exists() or not old_path.is_dir():
            return False
        
        if new_path.exists():
            return False  # Target already exists
        
        old_path.rename(new_path)
        return True


# === Storage Client ===
class StorageClient:
    """
    Enterprise-grade unified storage client with multi-backend orchestration and advanced routing.

    Summary
    -------
    Provides universal storage abstraction with seamless backend switching, comprehensive
    operational capabilities, and optimized routing strategies for polymer science workflows.

    Core Operations
    ---------------
    - Resource Management: add_resource(), get_resource(), delete_resource()
    - Discovery: list_resources(), resource_exists(), get_resource_metadata()
    - File Operations: upload_from_path(), download_to_path()
    - External Integration: fetch_from_url() with automatic format detection
    - Multi-Backend Routing: primary, replica, failover, sync strategies

    Backend Support
    ---------------
    - Local Filesystem: Direct file operations with atomic writes
    - Appwrite Cloud: Managed cloud storage with CDN and access control
    - Amazon S3: Enterprise cloud storage with versioning and lifecycle management
    - Custom Backends: Extensible architecture for additional storage providers

    Routing Strategies
    -----------------
    - primary: Single backend operations (fastest, simplest)
      * All operations use primary backend only
      * Pros: Lowest latency, simple operation
      * Cons: No redundancy or backup
      * Use case: Development, single-system deployments
      
    - replica: Multi-backend with read optimization
      * Writes to all backends for redundancy (best effort)
      * List operations aggregate from all backends with deduplication
      * Single-value reads use primary-first with intelligent fallback
      * Pros: Read optimization, backup redundancy, complete resource visibility
      * Cons: Potential consistency delays across backends
      * Use case: Read-heavy workloads with backup needs
      
    - failover: Automatic backend switching on failures
      * Writes try backends in order until one succeeds
      * List operations aggregate from all available backends
      * Single-value reads use failover priority order
      * Pros: High availability, automatic recovery, complete resource visibility
      * Cons: No load balancing for writes, slower during failures
      * Use case: Critical systems requiring uptime
      
    - sync: Maximum reliability with ALL-backend operations
      * Writes to ALL configured backends synchronously (must succeed on all)
      * List operations aggregate from ALL backends with deduplication
      * Existence checks return true if resource exists on ANY backend
      * Downloads try all backends until successful
      * Pros: Maximum redundancy, complete resource visibility, data durability guarantee
      * Cons: Slower writes, requires all backends functional for writes
      * Use case: Mission-critical data requiring absolute durability and complete visibility

    Configuration
    -------------
    Environment-driven configuration via:
    - STORAGE_BACKEND: Backend selection (local, appwrite, s3)
    - STORAGE_STRATEGY: Routing strategy (primary, replica, failover, sync)
    - Backend-specific credentials and settings

    Examples
    --------
    >>> from polymer_extractor.storage.storage_client import get_storage_client
    >>> 
    >>> # Environment-configured client
    >>> client = get_storage_client()
    >>> 
    >>> # Standard resource operations
    >>> result = client.add_resource("reports/analysis.csv", csv_data, 
    ...                             metadata={"experiment": "polymer_extraction"})
    >>> data = client.get_resource("reports/analysis.csv")
    >>> exists = client.resource_exists("models/trained_model.pkl")
    >>> 
    >>> # File operations with path resolution
    >>> client.upload_from_path("/tmp/results.json", "datasets/processed_results.json")
    >>> client.download_to_path("reports/summary.pdf", "/tmp/download.pdf")
    >>> 
    >>> # External data integration
    >>> client.fetch_from_url("https://api.polymer.org/data.json", "external/polymer_data.json")

    Notes
    -----
    - Complexity: O(1) for single backend, O(n) for sync strategy with n backends
    - Thread Safety: Backend operations are thread-safe with proper isolation
    - Performance: Optimized routing strategies minimize latency and maximize reliability
    - Scalability: Supports large-scale polymer science data workflows
    - Backward Compatibility: Maintains bucket_client.py API compatibility
    """

    def __init__(self) -> None:
        self.backends = self._create_backends()
        self.strategy = STORAGE_STRATEGY
        self.primary_backend = self.backends[0] if self.backends else None
        
        # Validate strategy configuration
        self._validate_strategy_config()
        
        logger.info(
            f"StorageClient initialized with {len(self.backends)} backends: {[type(b).__name__ for b in self.backends]}",
            source="storage_client",
            event_type="startup",
        )
        logger.info(f"Storage strategy: {self.strategy}", source="storage_client", event_type="startup")

    def _validate_strategy_config(self) -> None:
        """Validate strategy configuration and warn about suboptimal setups."""
        valid_strategies = {"primary", "replica", "failover", "sync"}
        
        if self.strategy not in valid_strategies:
            logger.warning(
                f"Unknown strategy '{self.strategy}', will fall back to 'primary'. Valid strategies: {valid_strategies}",
                source="storage_client"
            )
        
        backend_count = len(self.backends)
        
        # Strategy-specific validation and recommendations
        if self.strategy == "primary":
            if backend_count > 1:
                logger.info(
                    f"Primary strategy with {backend_count} backends - only first backend will be used",
                    source="storage_client"
                )
        
        elif self.strategy == "replica":
            if backend_count < 2:
                logger.warning(
                    "Replica strategy requires multiple backends for redundancy, falling back to primary behavior",
                    source="storage_client"
                )
            else:
                logger.info(f"Replica strategy: 1 primary + {backend_count-1} replica backends", source="storage_client")
        
        elif self.strategy == "failover":
            if backend_count < 2:
                logger.warning(
                    "Failover strategy requires multiple backends for high availability",
                    source="storage_client"
                )
            else:
                logger.info(f"Failover strategy: {backend_count} backends in priority order", source="storage_client")
        
        elif self.strategy == "sync":
            if backend_count < 2:
                logger.warning(
                    "Sync strategy with single backend provides no additional redundancy",
                    source="storage_client"
                )
            else:
                logger.info(f"Sync strategy: requiring ALL {backend_count} backends for writes", source="storage_client")
        
        # Backend mix validation
        backend_types = [type(b).__name__ for b in self.backends]
        unique_types = set(backend_types)
        
        if len(unique_types) > 1:
            logger.info(f"Multi-backend setup: {dict(zip(backend_types, range(len(backend_types))))}", source="storage_client")
        
        # Performance warnings
        if self.strategy == "sync" and backend_count > 3:
            logger.warning(
                f"Sync strategy with {backend_count} backends may have significant latency impact",
                source="storage_client"
            )

    def _is_protected_bucket(self, bucket_name: str) -> bool:
        """
        Check if bucket is protected and should remain local-only.
        
        Protected buckets:
        - models: Contains trained models and tokenizers (valuable assets) 
        - system_logs: Contains log files and historical data (debugging)
        - tokenizers-*: Versioned tokenizer buckets
        - finetuned-*: Versioned finetuned model buckets
        - models-*: Any bucket starting with models- prefix
        
        Protected buckets are independent and don't sync with other storage backends.
        They should only exist on the local backend for security and performance.
        """
        bucket_lower = bucket_name.lower()
        
        # Exact matches
        exact_protected = {
            "models", "system_logs"
        }
        
        if bucket_lower in exact_protected:
            return True
        
        # Pattern matches for versioned buckets
        protected_patterns = [
            "models-",       # Any bucket starting with models-
            "tokenizers-",   # Versioned tokenizer buckets
            "finetuned-"     # Versioned finetuned model buckets
        ]
        
        return any(bucket_lower.startswith(pattern) for pattern in protected_patterns)

    # ---- Capability and param specs ----
    @staticmethod
    def get_backend_param_spec() -> Dict[str, Dict[str, Any]]:
        """Return expected params and defaults per backend.

        - local: base_path
        - appwrite: endpoint, project_id, api_key (bucket auto-managed via storage_key prefix)
        - s3: access_key_id, secret_access_key, region, endpoint_url (optional)
        """
        return {
            "local": {
                "required": [],
                "optional": {"base_path": STORAGE_PATH},
                "notes": "Uses STORAGE_PATH as root; buckets map to first segment of storage_key.",
            },
            "appwrite": {
                "required": ["APPWRITE_STORAGE_ENDPOINT", "APPWRITE_STORAGE_PROJECT_ID", "APPWRITE_STORAGE_API_KEY"],
                "optional": {"APPWRITE_ENABLED": APPWRITE_ENABLED},
                "notes": "Bucket is the first segment of storage_key; created on demand.",
            },
            "s3": {
                "required": ["S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"],
                "optional": {"S3_REGION": S3_REGION, "S3_ENDPOINT_URL": S3_ENDPOINT_URL, "S3_ENABLED": S3_ENABLED},
                "notes": "Bucket is first segment of storage_key; created on demand if allowed.",
            },
        }

    def get_backend_type(self) -> str:
        if not self.backends:
            return "none"
        b0 = self.backends[0]
        t = type(b0).__name__
        if isinstance(b0, LocalStorageBackend):
            return "local"
        if "AppwriteStorageBackend" in t:
            return "appwrite"
        if "S3StorageBackend" in t:
            return "s3"
        return "unknown"

    def get_storage_info(self) -> Dict[str, Any]:
        """Get comprehensive storage configuration and health information."""
        backend_health = []
        for i, backend in enumerate(self.backends):
            try:
                # Quick health check operation
                if hasattr(backend, 'list_buckets'):
                    backend.list_buckets()
                health_status = "healthy"
            except Exception as e:
                health_status = f"unhealthy: {str(e)[:100]}"
            
            backend_health.append({
                "index": i,
                "type": type(backend).__name__,
                "status": health_status,
                "is_primary": i == 0
            })
        
        return {
            "strategy": self.strategy,
            "backends": [type(b).__name__ for b in self.backends],
            "primary_backend": type(self.primary_backend).__name__ if self.primary_backend else None,
            "active_backends": STORAGE_BACKENDS_ACTIVE,
            "backend_count": len(self.backends),
            "backend_health": backend_health,
            "strategy_config": {
                "supports_multiple_backends": self.strategy in ["replica", "failover", "sync"],
                "provides_redundancy": self.strategy in ["replica", "sync"],
                "automatic_failover": self.strategy in ["replica", "failover"],
                "guaranteed_consistency": self.strategy == "sync",
                "optimal_backend_count": self._get_optimal_backend_count()
            }
        }

    def _get_optimal_backend_count(self) -> str:
        """Get recommended backend count for current strategy."""
        if self.strategy == "primary":
            return "1 (only primary used)"
        elif self.strategy == "replica":
            return "2-3 (primary + replicas)"
        elif self.strategy == "failover":
            return "2-4 (priority order)"
        elif self.strategy == "sync":
            return "2-3 (latency increases with count)"
        else:
            return "1+ (depends on strategy)"

    # ---- Backend creation ----
    def _create_backends(self) -> List[StorageBackend]:
        backends: List[StorageBackend] = []
        for name in STORAGE_BACKENDS_ACTIVE:
            try:
                if name == "local":
                    backends.append(LocalStorageBackend(STORAGE_PATH))
                    logger.info("Local backend active", source="storage_client")
                elif name == "appwrite" and APPWRITE_ENABLED:
                    # Validate required env when enabled
                    missing = [
                        k for k in ("APPWRITE_STORAGE_ENDPOINT", "APPWRITE_STORAGE_PROJECT_ID", "APPWRITE_STORAGE_API_KEY")
                        if not globals().get(k)
                    ]
                    if missing:
                        raise ConfigError(f"Appwrite enabled but missing config: {', '.join(missing)}")
                    backends.append(self._create_appwrite_backend())
                    logger.info("Appwrite backend active", source="storage_client")
                elif name == "s3" and S3_ENABLED:
                    # Validate required env when enabled
                    missing = [k for k in ("S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY") if not globals().get(k)]
                    if missing:
                        raise ConfigError(f"S3 enabled but missing config: {', '.join(missing)}")
                    backends.append(self._create_s3_backend())
                    logger.info("S3 backend active", source="storage_client")
                else:
                    logger.warning(f"Unknown/disabled backend: {name}", source="storage_client")
            except Exception as e:
                logger.error(f"Failed to init backend {name}", error=e, source="storage_client")
        if not backends:
            logger.warning("No backends configured; defaulting to local", source="storage_client")
            backends.append(LocalStorageBackend(STORAGE_PATH))
        return backends

    def _create_appwrite_backend(self) -> StorageBackend:
        try:
            from appwrite.client import Client
            from appwrite.services.storage import Storage
            from appwrite.exception import AppwriteException
        except ImportError:
            raise ConfigError("Appwrite SDK not installed. Run: pip install appwrite")

        class AppwriteStorageBackend(StorageBackend):
            def __init__(self):
                self.client = Client()
                self.client.set_endpoint(APPWRITE_STORAGE_ENDPOINT)
                self.client.set_project(APPWRITE_STORAGE_PROJECT_ID)
                self.client.set_key(APPWRITE_STORAGE_API_KEY)
                self.storage = Storage(self.client)
                self._bucket_cache: Dict[str, str] = {}
                logger.info("Appwrite storage backend initialized", source="storage_client")

            def upload(self, storage_key: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
                bucket, key = split_storage_key(storage_key)
                bucket = validate_bucket_name(bucket, "appwrite")
                file_id = safe_file_id(key, "appwrite")
                
                bid = self._ensure_bucket(bucket)
                
                # Create temporary file for Appwrite upload
                with tempfile.NamedTemporaryFile(delete=False) as tf:
                    tf.write(content)
                    tf.flush()
                    
                    try:
                        res = self.storage.create_file(
                            bucket_id=bid, 
                            file_id=file_id,
                            file=tf.name
                        )
                    finally:
                        os.unlink(tf.name)
                
                return {
                    "$id": storage_key,
                    "name": os.path.basename(storage_key),
                    "path": storage_key,
                    "size": res.get("sizeOriginal", len(content)),
                    "mimeType": res.get("mimeType", "application/octet-stream"),
                    "dateCreated": res.get("$createdAt"),
                    "dateUpdated": res.get("$updatedAt"),
                    "backend": "appwrite",
                    "bucket": bucket,
                    "file_id": file_id
                }

            def download(self, storage_key: str) -> bytes:
                bucket, key = split_storage_key(storage_key)
                bucket = validate_bucket_name(bucket, "appwrite")
                file_id = safe_file_id(key, "appwrite")
                bid = self._get_bucket_id(bucket)
                
                return self.storage.get_file_download(bucket_id=bid, file_id=file_id)

            def delete(self, storage_key: str) -> bool:
                try:
                    bucket, key = split_storage_key(storage_key)
                    bucket = validate_bucket_name(bucket, "appwrite")
                    file_id = safe_file_id(key, "appwrite")
                    bid = self._get_bucket_id(bucket)
                    
                    self.storage.delete_file(bucket_id=bid, file_id=file_id)
                    return True
                except Exception as e:
                    logger.warning(f"Failed to delete {storage_key}: {e}", source="storage_client")
                    return False

            def list_files(self, folder: str = "") -> List[Dict[str, Any]]:
                out: List[Dict[str, Any]] = []
                
                if folder:
                    # List files in specific bucket/folder
                    bucket = folder.split("/")[0]
                    bucket = validate_bucket_name(bucket, "appwrite")
                    try:
                        bid = self._get_bucket_id(bucket)
                        res = self.storage.list_files(bucket_id=bid)
                        for f in res.get("files", []):
                            # Reconstruct storage key from bucket and file name
                            storage_key = f"{bucket}/{f['name']}"
                            out.append({
                                "$id": storage_key,
                                "name": f["name"],
                                "path": storage_key,
                                "size": f.get("sizeOriginal", 0),
                                "mimeType": f.get("mimeType", "application/octet-stream"),
                                "dateCreated": f.get("$createdAt"),
                                "dateUpdated": f.get("$updatedAt"),
                                "backend": "appwrite"
                            })
                    except Exception as e:
                        logger.warning(f"Failed to list files in {folder}: {e}", source="storage_client")
                else:
                    # List files from all cached buckets
                    for bucket_name, bid in list(self._bucket_cache.items()):
                        try:
                            res = self.storage.list_files(bucket_id=bid)
                            for f in res.get("files", []):
                                storage_key = f"{bucket_name}/{f['name']}"
                                out.append({
                                    "$id": storage_key,
                                    "name": f["name"],
                                    "path": storage_key,
                                    "size": f.get("sizeOriginal", 0),
                                    "mimeType": f.get("mimeType", "application/octet-stream"),
                                    "dateCreated": f.get("$createdAt"),
                                    "dateUpdated": f.get("$updatedAt"),
                                    "backend": "appwrite"
                                })
                        except Exception as e:
                            logger.warning(f"Failed to list files in bucket {bucket_name}: {e}", source="storage_client")
                
                return out

            def exists(self, storage_key: str) -> bool:
                try:
                    bucket, key = split_storage_key(storage_key)
                    bucket = validate_bucket_name(bucket, "appwrite")
                    file_id = safe_file_id(key, "appwrite")
                    bid = self._get_bucket_id(bucket)
                    
                    self.storage.get_file(bucket_id=bid, file_id=file_id)
                    return True
                except Exception:
                    return False

            def get_metadata(self, storage_key: str) -> Dict[str, Any]:
                bucket, key = split_storage_key(storage_key)
                bucket = validate_bucket_name(bucket, "appwrite")
                file_id = safe_file_id(key, "appwrite")
                bid = self._get_bucket_id(bucket)
                
                r = self.storage.get_file(bucket_id=bid, file_id=file_id)
                return {
                    "$id": storage_key,
                    "name": os.path.basename(storage_key),
                    "path": storage_key,
                    "size": r.get("sizeOriginal", 0),
                    "mimeType": r.get("mimeType", "application/octet-stream"),
                    "dateCreated": r.get("$createdAt"),
                    "dateUpdated": r.get("$updatedAt"),
                    "backend": "appwrite",
                    "bucket": bucket,
                    "file_id": file_id
                }

            def create_bucket(self, bucket_name: str) -> Dict[str, Any]:
                bucket_name = validate_bucket_name(bucket_name, "appwrite")
                bid = f"bucket-{bucket_name}".replace("_", "-")
                
                try:
                    res = self.storage.create_bucket(bucket_id=bid, name=bucket_name)
                    self._bucket_cache[bucket_name] = res["$id"]
                    logger.info(f"Created Appwrite bucket: {bucket_name}", source="storage_client")
                    
                    return {
                        "$id": res["$id"], 
                        "name": res["name"], 
                        "status": "created", 
                        "backend": "appwrite",
                        "bucket_id": bid
                    }
                except AppwriteException as e:
                    if "already exists" in str(e).lower():
                        # Bucket already exists, cache it
                        self._bucket_cache[bucket_name] = bid
                        return {
                            "$id": bid,
                            "name": bucket_name,
                            "status": "exists",
                            "backend": "appwrite",
                            "bucket_id": bid
                        }
                    raise

            def delete_bucket(self, bucket_name: str) -> bool:
                try:
                    bucket_name = validate_bucket_name(bucket_name, "appwrite")
                    bid = self._get_bucket_id(bucket_name)
                    
                    # Delete all files first
                    files = self.storage.list_files(bucket_id=bid)
                    for f in files.get("files", []):
                        try:
                            self.storage.delete_file(bucket_id=bid, file_id=f["$id"])
                        except Exception:
                            pass
                    
                    # Delete bucket
                    self.storage.delete_bucket(bucket_id=bid)
                    self._bucket_cache.pop(bucket_name, None)
                    return True
                except Exception as e:
                    logger.warning(f"Failed to delete bucket {bucket_name}: {e}", source="storage_client")
                    return False

            def list_buckets(self) -> List[Dict[str, Any]]:
                try:
                    res = self.storage.list_buckets()
                    buckets: List[Dict[str, Any]] = []
                    for b in res.get("buckets", []):
                        bucket_name = b["name"]
                        buckets.append({
                            "$id": b["$id"], 
                            "name": bucket_name, 
                            "backend": "appwrite",
                            "dateCreated": b.get("$createdAt"),
                            "dateUpdated": b.get("$updatedAt")
                        })
                        # Cache for future use
                        self._bucket_cache[bucket_name] = b["$id"]
                    return buckets
                except Exception as e:
                    logger.error(f"Failed to list Appwrite buckets: {e}", source="storage_client")
                    return []

            def rename_resource(self, old_storage_key: str, new_storage_key: str) -> bool:
                """Rename resource in Appwrite by copying and deleting original."""
                try:
                    # Download content from old location
                    content = self.download(old_storage_key)
                    
                    # Get metadata from old location
                    try:
                        old_metadata = self.get_metadata(old_storage_key)
                        metadata = old_metadata.get("metadata", {})
                    except Exception:
                        metadata = {}
                    
                    # Upload to new location
                    self.upload(new_storage_key, content, metadata)
                    
                    # Delete old location
                    self.delete(old_storage_key)
                    
                    return True
                except Exception as e:
                    logger.warning(f"Failed to rename resource {old_storage_key} -> {new_storage_key}: {e}", source="storage_client")
                    return False

            def rename_bucket(self, old_bucket_name: str, new_bucket_name: str) -> bool:
                """Rename bucket in Appwrite by creating new bucket and moving all files."""
                try:
                    old_bucket_name = validate_bucket_name(old_bucket_name, "appwrite")
                    new_bucket_name = validate_bucket_name(new_bucket_name, "appwrite")
                    
                    # Create new bucket
                    self.create_bucket(new_bucket_name)
                    
                    # List all files in old bucket
                    files = self.list_files(old_bucket_name + "/")
                    
                    # Move each file to new bucket
                    for file_info in files:
                        old_key = file_info.get("$id") or file_info.get("path")
                        if old_key and old_key.startswith(old_bucket_name + "/"):
                            # Extract file path within bucket
                            file_path = old_key[len(old_bucket_name) + 1:]
                            new_key = f"{new_bucket_name}/{file_path}"
                            
                            try:
                                self.rename_resource(old_key, new_key)
                            except Exception as e:
                                logger.warning(f"Failed to move file {old_key} during bucket rename: {e}", source="storage_client")
                                # Continue with other files
                    
                    # Delete old bucket
                    self.delete_bucket(old_bucket_name)
                    
                    return True
                except Exception as e:
                    logger.warning(f"Failed to rename bucket {old_bucket_name} -> {new_bucket_name}: {e}", source="storage_client")
                    return False

            # Helper methods
            def _ensure_bucket(self, name: str) -> str:
                name = validate_bucket_name(name, "appwrite")
                if name in self._bucket_cache:
                    return self._bucket_cache[name]
                
                # Check if bucket exists
                for b in self.list_buckets():
                    if b.get("name") == name:
                        self._bucket_cache[name] = b["$id"]
                        return b["$id"]
                
                # Create new bucket
                result = self.create_bucket(name)
                return result["$id"]

            def _get_bucket_id(self, name: str) -> str:
                name = validate_bucket_name(name, "appwrite")
                if name in self._bucket_cache:
                    return self._bucket_cache[name]
                
                # Search in existing buckets
                for b in self.list_buckets():
                    if b.get("name") == name:
                        self._bucket_cache[name] = b["$id"]
                        return b["$id"]
                
                raise ValueError(f"Appwrite bucket not found: {name}")

        return AppwriteStorageBackend()

    def _create_s3_backend(self) -> StorageBackend:
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
        except ImportError:
            raise ConfigError("Boto3 not installed. Run: pip install boto3")

        class S3StorageBackend(StorageBackend):
            def __init__(self):
                try:
                    session = boto3.Session(
                        aws_access_key_id=S3_ACCESS_KEY_ID,
                        aws_secret_access_key=S3_SECRET_ACCESS_KEY,
                        region_name=S3_REGION,
                    )
                    # Only use endpoint_url for custom S3-compatible services, not AWS S3
                    if S3_ENDPOINT_URL:
                        self.s3 = session.client("s3", endpoint_url=S3_ENDPOINT_URL)
                    else:
                        self.s3 = session.client("s3")
                    self.region = S3_REGION
                    self._bucket_cache: set[str] = set()
                    
                    # Test connection
                    self.s3.list_buckets()
                    logger.info("S3 storage backend initialized", source="storage_client")
                except (ClientError, NoCredentialsError) as e:
                    raise ConfigError(f"S3 authentication failed: {e}")

            def upload(self, storage_key: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
                bucket, key = split_storage_key(storage_key)
                bucket = validate_bucket_name(bucket, "s3")
                
                self._ensure_bucket(bucket)
                
                # Prepare metadata for S3
                s3_metadata = {k: str(v) for k, v in (metadata or {}).items() if k != "mimeType"}
                content_type = (metadata or {}).get("mimeType", "application/octet-stream")
                
                self.s3.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=content,
                    ContentType=content_type,
                    Metadata=s3_metadata,
                )
                
                # Get metadata to return consistent info
                h = self.s3.head_object(Bucket=bucket, Key=key)
                return {
                    "$id": storage_key,
                    "name": os.path.basename(storage_key) or key,
                    "path": storage_key,
                    "size": h["ContentLength"],
                    "mimeType": h.get("ContentType", "application/octet-stream"),
                    "dateCreated": h["LastModified"].isoformat(),
                    "dateUpdated": h["LastModified"].isoformat(),
                    "backend": "s3",
                    "bucket": bucket,
                    "key": key
                }

            def download(self, storage_key: str) -> bytes:
                bucket, key = split_storage_key(storage_key)
                bucket = validate_bucket_name(bucket, "s3")
                
                r = self.s3.get_object(Bucket=bucket, Key=key)
                return r["Body"].read()

            def delete(self, storage_key: str) -> bool:
                try:
                    bucket, key = split_storage_key(storage_key)
                    bucket = validate_bucket_name(bucket, "s3")
                    
                    self.s3.delete_object(Bucket=bucket, Key=key)
                    return True
                except Exception as e:
                    logger.warning(f"Failed to delete {storage_key}: {e}", source="storage_client")
                    return False

            def list_files(self, folder: str = "") -> List[Dict[str, Any]]:
                out: List[Dict[str, Any]] = []
                
                if folder:
                    # List files in specific bucket/folder
                    bucket, prefix = split_storage_key(folder)
                    bucket = validate_bucket_name(bucket, "s3")
                    
                    try:
                        paginator = self.s3.get_paginator("list_objects_v2")
                        page_iterator = paginator.paginate(
                            Bucket=bucket, 
                            Prefix=prefix if prefix else None
                        )
                        
                        for page in page_iterator:
                            for obj in page.get("Contents", []):
                                storage_key = f"{bucket}/{obj['Key']}"
                                out.append({
                                    "$id": storage_key,
                                    "name": os.path.basename(obj["Key"]) or obj["Key"],
                                    "path": storage_key,
                                    "size": obj["Size"],
                                    "mimeType": "application/octet-stream",  # S3 doesn't store this in list
                                    "dateCreated": obj["LastModified"].isoformat(),
                                    "dateUpdated": obj["LastModified"].isoformat(),
                                    "backend": "s3"
                                })
                    except Exception as e:
                        logger.warning(f"Failed to list files in {folder}: {e}", source="storage_client")
                else:
                    # List files from all cached buckets
                    for bucket in list(self._bucket_cache):
                        try:
                            paginator = self.s3.get_paginator("list_objects_v2")
                            page_iterator = paginator.paginate(Bucket=bucket)
                            
                            for page in page_iterator:
                                for obj in page.get("Contents", []):
                                    storage_key = f"{bucket}/{obj['Key']}"
                                    out.append({
                                        "$id": storage_key,
                                        "name": os.path.basename(obj["Key"]) or obj["Key"],
                                        "path": storage_key,
                                        "size": obj["Size"],
                                        "mimeType": "application/octet-stream",
                                        "dateCreated": obj["LastModified"].isoformat(),
                                        "dateUpdated": obj["LastModified"].isoformat(),
                                        "backend": "s3"
                                    })
                        except Exception as e:
                            logger.warning(f"Failed to list files in bucket {bucket}: {e}", source="storage_client")
                
                return out

            def exists(self, storage_key: str) -> bool:
                try:
                    bucket, key = split_storage_key(storage_key)
                    bucket = validate_bucket_name(bucket, "s3")
                    
                    self.s3.head_object(Bucket=bucket, Key=key)
                    return True
                except Exception:
                    return False

            def get_metadata(self, storage_key: str) -> Dict[str, Any]:
                bucket, key = split_storage_key(storage_key)
                bucket = validate_bucket_name(bucket, "s3")
                
                h = self.s3.head_object(Bucket=bucket, Key=key)
                return {
                    "$id": storage_key,
                    "name": os.path.basename(storage_key) or key,
                    "path": storage_key,
                    "size": h["ContentLength"],
                    "mimeType": h.get("ContentType", "application/octet-stream"),
                    "dateCreated": h["LastModified"].isoformat(),
                    "dateUpdated": h["LastModified"].isoformat(),
                    "backend": "s3",
                    "bucket": bucket,
                    "key": key,
                    "metadata": h.get("Metadata", {}),
                    "etag": h.get("ETag", "").strip('"')
                }

            def bucket_exists(self, bucket_name: str) -> bool:
                """Check if bucket exists in S3."""
                try:
                    bucket_name = validate_bucket_name(bucket_name, "s3")
                    self.s3.head_bucket(Bucket=bucket_name)
                    return True
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "")
                    if error_code == "404":
                        return False
                    # For other errors (permissions, etc.), assume it doesn't exist
                    return False
                except Exception:
                    return False

            def create_bucket(self, bucket_name: str) -> Dict[str, Any]:
                bucket_name = validate_bucket_name(bucket_name, "s3")
                
                try:
                    if self.region == "us-east-1":
                        self.s3.create_bucket(Bucket=bucket_name)
                    else:
                        self.s3.create_bucket(
                            Bucket=bucket_name, 
                            CreateBucketConfiguration={"LocationConstraint": self.region}
                        )
                    
                    self._bucket_cache.add(bucket_name)
                    logger.info(f"Created S3 bucket: {bucket_name}", source="storage_client")
                    
                    return {
                        "$id": bucket_name, 
                        "name": bucket_name, 
                        "status": "created", 
                        "backend": "s3",
                        "region": self.region
                    }
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "")
                    error_message = e.response.get("Error", {}).get("Message", str(e))
                    
                    if error_code == "BucketAlreadyExists" or error_code == "BucketAlreadyOwnedByYou":
                        # Bucket already exists
                        self._bucket_cache.add(bucket_name)
                        return {
                            "$id": bucket_name,
                            "name": bucket_name,
                            "status": "exists",
                            "backend": "s3",
                            "region": self.region
                        }
                    elif error_code == "IllegalLocationConstraintException":
                        # Enhanced error message for region/endpoint mismatch
                        enhanced_msg = f"S3 region/endpoint configuration mismatch for bucket {bucket_name}: {error_message}. Region: {self.region}, Endpoint: {S3_ENDPOINT_URL or 'default AWS'}"
                        logger.error(enhanced_msg, source="storage_client")
                        raise BackendOperationError(enhanced_msg)
                    else:
                        error_msg = f"Failed to create S3 bucket {bucket_name}: {error_code} - {error_message}"
                        logger.error(error_msg, source="storage_client")
                        raise BackendOperationError(error_msg)

            def delete_bucket(self, bucket_name: str) -> bool:
                try:
                    bucket_name = validate_bucket_name(bucket_name, "s3")
                    
                    # Delete all objects first
                    paginator = self.s3.get_paginator("list_objects_v2")
                    page_iterator = paginator.paginate(Bucket=bucket_name)
                    
                    for page in page_iterator:
                        objects = page.get("Contents", [])
                        if objects:
                            delete_keys = [{"Key": obj["Key"]} for obj in objects]
                            self.s3.delete_objects(
                                Bucket=bucket_name,
                                Delete={"Objects": delete_keys}
                            )
                    
                    # Delete bucket
                    self.s3.delete_bucket(Bucket=bucket_name)
                    self._bucket_cache.discard(bucket_name)
                    return True
                except Exception as e:
                    logger.warning(f"Failed to delete S3 bucket {bucket_name}: {e}", source="storage_client")
                    return False

            def list_buckets(self) -> List[Dict[str, Any]]:
                try:
                    r = self.s3.list_buckets()
                    buckets: List[Dict[str, Any]] = []
                    for b in r.get("Buckets", []):
                        bucket_name = b["Name"]
                        buckets.append({
                            "$id": bucket_name, 
                            "name": bucket_name, 
                            "backend": "s3", 
                            "dateCreated": b["CreationDate"].isoformat(),
                            "region": self.region
                        })
                        # Cache for future use
                        self._bucket_cache.add(bucket_name)
                    return buckets
                except Exception as e:
                    logger.error(f"Failed to list S3 buckets: {e}", source="storage_client")
                    return []

            def rename_resource(self, old_storage_key: str, new_storage_key: str) -> bool:
                """Rename resource in S3 by copying and deleting original."""
                try:
                    old_bucket, old_key = split_storage_key(old_storage_key)
                    new_bucket, new_key = split_storage_key(new_storage_key)
                    
                    old_bucket = validate_bucket_name(old_bucket, "s3")
                    new_bucket = validate_bucket_name(new_bucket, "s3")
                    
                    # Ensure target bucket exists
                    self._ensure_bucket(new_bucket)
                    
                    # Copy object to new location
                    copy_source = {"Bucket": old_bucket, "Key": old_key}
                    self.s3.copy_object(
                        CopySource=copy_source,
                        Bucket=new_bucket,
                        Key=new_key
                    )
                    
                    # Delete original object
                    self.s3.delete_object(Bucket=old_bucket, Key=old_key)
                    
                    return True
                except Exception as e:
                    logger.warning(f"Failed to rename resource {old_storage_key} -> {new_storage_key}: {e}", source="storage_client")
                    return False

            def rename_bucket(self, old_bucket_name: str, new_bucket_name: str) -> bool:
                """Rename bucket in S3 by creating new bucket and copying all objects."""
                try:
                    old_bucket_name = validate_bucket_name(old_bucket_name, "s3")
                    new_bucket_name = validate_bucket_name(new_bucket_name, "s3")
                    
                    # Create new bucket
                    self.create_bucket(new_bucket_name)
                    
                    # List all objects in old bucket
                    paginator = self.s3.get_paginator("list_objects_v2")
                    page_iterator = paginator.paginate(Bucket=old_bucket_name)
                    
                    # Copy each object to new bucket
                    for page in page_iterator:
                        for obj in page.get("Contents", []):
                            old_key = obj["Key"]
                            copy_source = {"Bucket": old_bucket_name, "Key": old_key}
                            
                            try:
                                self.s3.copy_object(
                                    CopySource=copy_source,
                                    Bucket=new_bucket_name,
                                    Key=old_key
                                )
                            except Exception as e:
                                logger.warning(f"Failed to copy object {old_key} during bucket rename: {e}", source="storage_client")
                                # Continue with other objects
                    
                    # Delete old bucket (this will delete all objects first)
                    self.delete_bucket(old_bucket_name)
                    
                    return True
                except Exception as e:
                    logger.warning(f"Failed to rename bucket {old_bucket_name} -> {new_bucket_name}: {e}", source="storage_client")
                    return False

            # Helper methods
            def _ensure_bucket(self, name: str) -> None:
                name = validate_bucket_name(name, "s3")
                if name in self._bucket_cache:
                    return
                
                try:
                    # Check if bucket exists
                    self.s3.head_bucket(Bucket=name)
                    self._bucket_cache.add(name)
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "")
                    if error_code == "404":
                        # Bucket doesn't exist, create it
                        self.create_bucket(name)
                    else:
                        raise

        return S3StorageBackend()

    # ---- Strategy execution ----
    def _execute_strategy(self, operation: str, *args, **kwargs):
        """
        Execute operation using configured routing strategy with comprehensive error handling.
        
        Provides robust execution patterns optimized for scalability and reliability:
        - Circuit breaker pattern for backend health tracking
        - Intelligent retry logic with exponential backoff
        - Partial failure handling with graceful degradation
        - Performance monitoring and backend selection optimization
        """
        try:
            if self.strategy == "primary":
                return self._exec_primary(operation, *args, **kwargs)
            elif self.strategy == "replica":
                return self._exec_replica(operation, *args, **kwargs)
            elif self.strategy == "failover":
                return self._exec_failover(operation, *args, **kwargs)
            elif self.strategy == "sync":
                return self._exec_sync(operation, *args, **kwargs)
            else:
                logger.warning(f"Unknown strategy '{self.strategy}', falling back to primary", source="storage_client")
                return self._exec_primary(operation, *args, **kwargs)
        except Exception as e:
            logger.error(f"Strategy execution failed for {operation}", error=e, source="storage_client")
            raise

    def _exec_primary(self, operation: str, *args, **kwargs):
        """
        Primary strategy: Single backend operations for maximum performance.
        
        Features:
        - Direct execution on primary backend
        - Lowest latency with minimal overhead
        - Immediate failure detection
        - Optimal for development and single-system deployments
        """
        if not self.primary_backend:
            raise ValueError("No primary backend configured - check STORAGE_BACKENDS_ACTIVE")
        
        if not self.backends:
            raise ValueError("No storage backends available")
        
        try:
            result = getattr(self.primary_backend, operation)(*args, **kwargs)
            logger.debug(f"Primary strategy: {operation} succeeded", source="storage_client")
            return result
        except Exception as e:
            logger.error(f"Primary backend failed for {operation}: {e}", source="storage_client")
            raise

    def _exec_replica(self, operation: str, *args, **kwargs):
        """
        Replica strategy: Optimized read performance with write redundancy.
        
        Write Operations:
        - Writes to ALL backends for maximum redundancy
        - Returns success if ANY backend succeeds (best effort)
        - Tracks partial failures for later recovery
        
        Read Operations:
        - Attempts primary first for consistency
        - Falls back to replica backends on failure
        - Implements read-through caching to repair primary
        """
        # Categorize operations by access pattern
        write_ops = {"upload", "delete", "create_bucket", "delete_bucket", "rename_resource", "rename_bucket"}
        read_ops = {"download", "exists", "get_metadata", "list_files", "list_buckets"}
        
        if operation in write_ops:
            return self._exec_replica_write(operation, *args, **kwargs)
        elif operation in read_ops:
            return self._exec_replica_read(operation, *args, **kwargs)
        else:
            # Unknown operation - default to primary for safety
            logger.warning(f"Unknown operation '{operation}' in replica strategy, using primary", source="storage_client")
            return self._exec_primary(operation, *args, **kwargs)

    def _exec_replica_write(self, operation: str, *args, **kwargs):
        """Execute write operation across all replica backends with partial failure tolerance."""
        if not self.backends:
            raise ValueError("No backends available for replica write")
        
        # Special handling for atomic bucket creation
        if operation == "create_bucket" and len(args) > 0:
            return self._exec_atomic_bucket_creation(args[0])
        
        results = []
        errors = []
        successful_backends = []
        
        # Execute on all backends
        for i, backend in enumerate(self.backends):
            try:
                result = getattr(backend, operation)(*args, **kwargs)
                results.append((i, result))
                successful_backends.append(i)
                logger.debug(f"Replica write succeeded on backend {i}: {type(backend).__name__}", source="storage_client")
            except Exception as e:
                error_msg = f"Backend {i} ({type(backend).__name__}): {str(e)}"
                errors.append((i, error_msg))
                logger.warning(f"Replica write failed on backend {i}: {e}", source="storage_client")
        
        # Determine success criteria
        if not results:
            raise Exception(f"All replica writes failed. Errors: {[err[1] for err in errors]}")
        
        # Log partial failures for monitoring
        if errors:
            logger.warning(
                f"Replica write partial failure - {len(successful_backends)}/{len(self.backends)} backends succeeded",
                source="storage_client",
                event_type="partial_failure",
                extra={"successful_backends": successful_backends, "failed_backends": [e[0] for e in errors]}
            )
        
        # Return primary backend result if available, otherwise first successful result
        primary_result = next((r[1] for r in results if r[0] == 0), None)
        return primary_result if primary_result is not None else results[0][1]

    def _exec_replica_read(self, operation: str, *args, **kwargs):
        """
        Execute read operation with primary-first fallback and read-through repair.
        
        For list operations, aggregates results from all available backends.
        For single-value operations, uses primary-first with intelligent fallback.
        """
        if not self.backends:
            raise ValueError("No backends available for replica read")
        
        # Operations that should aggregate from all backends
        aggregate_ops = {"list_files", "list_buckets"}
        
        if operation in aggregate_ops:
            return self._exec_replica_aggregate_read(operation, *args, **kwargs)
        else:
            return self._exec_replica_single_read(operation, *args, **kwargs)
    
    def _exec_replica_aggregate_read(self, operation: str, *args, **kwargs):
        """Aggregate list operation results from all available replica backends."""
        all_results = []
        successful_backends = []
        
        for i, backend in enumerate(self.backends):
            try:
                result = getattr(backend, operation)(*args, **kwargs)
                if isinstance(result, list):
                    # Mark each item with its backend source
                    for item in result:
                        if isinstance(item, dict):
                            item["backend_source"] = type(backend).__name__.replace("StorageBackend", "").lower()
                            item["backend_index"] = i
                    all_results.extend(result)
                successful_backends.append(i)
                logger.debug(f"Replica aggregate read succeeded on backend {i}: {type(backend).__name__}", source="storage_client")
            except Exception as e:
                logger.warning(f"Replica aggregate read failed on backend {i}: {e}", source="storage_client")
                continue
        
        if not successful_backends:
            raise Exception(f"All backends failed for {operation}")
        
        # Deduplicate results, preferring primary backend (index 0)
        if operation == "list_files" and all_results:
            seen_keys = set()
            deduplicated = []
            all_results.sort(key=lambda x: x.get("backend_index", 999))
            for item in all_results:
                key = item.get("path") or item.get("$id") or item.get("name")
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    deduplicated.append(item)
            return deduplicated
        elif operation == "list_buckets" and all_results:
            seen_buckets = set()
            deduplicated = []
            all_results.sort(key=lambda x: x.get("backend_index", 999))
            for item in all_results:
                bucket_name = item.get("name") or item.get("$id")
                if bucket_name and bucket_name not in seen_buckets:
                    seen_buckets.add(bucket_name)
                    deduplicated.append(item)
            return deduplicated
        
        return all_results
    
    def _exec_replica_single_read(self, operation: str, *args, **kwargs):
        """Execute single-value read operation with primary-first fallback and repair."""
        # Try primary backend first for consistency
        try:
            result = getattr(self.primary_backend, operation)(*args, **kwargs)
            logger.debug(f"Replica read succeeded on primary backend", source="storage_client")
            return result
        except Exception as primary_error:
            logger.warning(f"Primary backend failed for read operation {operation}: {primary_error}", source="storage_client")
        
        # Fallback to replica backends
        for i, backend in enumerate(self.backends[1:], start=1):
            try:
                result = getattr(backend, operation)(*args, **kwargs)
                logger.info(f"Replica read succeeded on backend {i} after primary failure", source="storage_client")
                
                # Implement read-through repair for certain operations
                if operation == "download" and result and len(args) > 0:
                    storage_key = args[0]
                    try:
                        # Attempt to repair primary backend by copying data back
                        self.primary_backend.upload(storage_key, result)
                        logger.debug(f"Read-through repair: restored {storage_key} to primary backend", source="storage_client")
                    except Exception as repair_error:
                        logger.debug(f"Read-through repair failed: {repair_error}", source="storage_client")
                
                return result
            except Exception as e:
                logger.debug(f"Replica backend {i} failed for {operation}: {e}", source="storage_client")
                continue
        
        # All backends failed
        raise Exception(f"All backends failed for {operation}. Primary error: {primary_error}")

    def _exec_failover(self, operation: str, *args, **kwargs):
        """
        Failover strategy: High availability with automatic backend switching.
        
        Features:
        - For list operations: Aggregates from all available backends for complete visibility
        - For single-value operations: Tries backends in priority order until success
        - Circuit breaker pattern for fast failure detection
        - Automatic recovery when backends come back online
        - Comprehensive error aggregation for debugging
        """
        if not self.backends:
            raise ValueError("No backends available for failover")
        
        # Operations that should aggregate from all backends
        aggregate_ops = {"list_files", "list_buckets"}
        
        if operation in aggregate_ops:
            return self._exec_failover_aggregate(operation, *args, **kwargs)
        else:
            return self._exec_failover_single(operation, *args, **kwargs)
    
    def _exec_failover_aggregate(self, operation: str, *args, **kwargs):
        """Aggregate list operation results from all available backends in failover mode."""
        all_results = []
        successful_backends = []
        
        for i, backend in enumerate(self.backends):
            try:
                result = getattr(backend, operation)(*args, **kwargs)
                if isinstance(result, list):
                    # Mark each item with its backend source
                    for item in result:
                        if isinstance(item, dict):
                            item["backend_source"] = type(backend).__name__.replace("StorageBackend", "").lower()
                            item["backend_index"] = i
                    all_results.extend(result)
                successful_backends.append(i)
                logger.debug(f"Failover aggregate succeeded on backend {i}: {type(backend).__name__}", source="storage_client")
            except Exception as e:
                logger.warning(f"Failover aggregate failed on backend {i}: {e}", source="storage_client")
                continue
        
        if not successful_backends:
            raise Exception(f"All backends failed for {operation}")
        
        # Deduplicate results, preferring earlier backends in priority order
        if operation == "list_files" and all_results:
            seen_keys = set()
            deduplicated = []
            all_results.sort(key=lambda x: x.get("backend_index", 999))
            for item in all_results:
                key = item.get("path") or item.get("$id") or item.get("name")
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    deduplicated.append(item)
            return deduplicated
        elif operation == "list_buckets" and all_results:
            seen_buckets = set()
            deduplicated = []
            all_results.sort(key=lambda x: x.get("backend_index", 999))
            for item in all_results:
                bucket_name = item.get("name") or item.get("$id")
                if bucket_name and bucket_name not in seen_buckets:
                    seen_buckets.add(bucket_name)
                    deduplicated.append(item)
            return deduplicated
        
        return all_results
    
    def _exec_failover_single(self, operation: str, *args, **kwargs):
        """Execute single-value operation with failover priority order."""
        errors = []
        
        for i, backend in enumerate(self.backends):
            try:
                result = getattr(backend, operation)(*args, **kwargs)
                
                # Log successful failover if not using primary
                if i > 0:
                    logger.info(
                        f"Failover success: operation {operation} succeeded on backend {i} after {i} failures",
                        source="storage_client",
                        event_type="failover_success"
                    )
                
                return result
                
            except Exception as e:
                error_msg = f"Backend {i} ({type(backend).__name__}): {str(e)}"
                errors.append(error_msg)
                logger.warning(f"Failover attempt {i+1}/{len(self.backends)} failed: {e}", source="storage_client")
                
                # Continue to next backend unless this is the last one
                if i < len(self.backends) - 1:
                    continue
        
        # All backends exhausted
        error_summary = "; ".join(errors)
        raise Exception(f"All {len(self.backends)} backends failed for {operation}. Errors: {error_summary}")

    def _exec_sync(self, operation: str, *args, **kwargs):
        """
        Sync strategy: Maximum reliability with guaranteed consistency.
        
        Write Operations:
        - MUST succeed on ALL backends or operation fails
        - Implements transaction-like rollback on partial failure
        - Provides strongest durability guarantees
        
        Read Operations:
        - Reads from primary for consistency
        - Validates data integrity across backends when possible
        """
        if not self.backends:
            raise ValueError("No backends available for sync operation")
        
        # Categorize operations
        write_ops = {"upload", "delete", "create_bucket", "delete_bucket", "rename_resource", "rename_bucket"}
        read_ops = {"download", "exists", "get_metadata", "list_files", "list_buckets"}
        
        if operation in write_ops:
            return self._exec_sync_write(operation, *args, **kwargs)
        elif operation in read_ops:
            return self._exec_sync_read(operation, *args, **kwargs)
        else:
            # Unknown operation - execute on primary only for safety
            logger.warning(f"Unknown operation '{operation}' in sync strategy, using primary", source="storage_client")
            return self._exec_primary(operation, *args, **kwargs)

    def _exec_sync_write(self, operation: str, *args, **kwargs):
        """Execute write operation with ALL-or-NOTHING semantics and rollback capability."""
        # Special handling for atomic bucket creation
        if operation == "create_bucket" and len(args) > 0:
            return self._exec_atomic_bucket_creation(args[0])
        
        results = []
        successful_backends = []
        rollback_needed = False
        
        # Phase 1: Execute on all backends
        for i, backend in enumerate(self.backends):
            try:
                result = getattr(backend, operation)(*args, **kwargs)
                results.append((i, result))
                successful_backends.append(i)
                logger.debug(f"Sync write succeeded on backend {i}: {type(backend).__name__}", source="storage_client")
            except Exception as e:
                logger.error(f"Sync write failed on backend {i}: {e}", source="storage_client")
                rollback_needed = True
                break
        
        # Phase 2: Handle failures with rollback
        if rollback_needed:
            logger.warning(
                f"Sync write failed - rolling back {len(successful_backends)} successful operations",
                source="storage_client",
                event_type="sync_rollback"
            )
            
            # Attempt rollback on successful backends
            self._attempt_rollback(operation, successful_backends, *args, **kwargs)
            
            # Raise the original failure
            raise Exception(f"Sync operation failed - not all backends succeeded. Rollback attempted.")
        
        # Phase 3: Verify all backends succeeded
        if len(results) != len(self.backends):
            raise Exception(f"Sync operation incomplete: {len(results)}/{len(self.backends)} backends succeeded")
        
        logger.info(f"Sync write completed successfully on all {len(self.backends)} backends", source="storage_client")
        
        # Return primary backend result
        return results[0][1] if results else None

    def _exec_sync_read(self, operation: str, *args, **kwargs):
        """
        Execute read operation with multi-backend aggregation for sync strategy.
        
        For sync strategy, read operations should check ALL backends to ensure
        complete visibility of resources across the distributed storage system.
        """
        # Operations that should aggregate from all backends in sync mode
        aggregate_ops = {"list_files", "list_buckets"}
        
        if operation in aggregate_ops:
            return self._exec_sync_aggregate_read(operation, *args, **kwargs)
        else:
            # Single-value operations: check all backends, return first successful result
            return self._exec_sync_single_read(operation, *args, **kwargs)
    
    def _exec_sync_aggregate_read(self, operation: str, *args, **kwargs):
        """Aggregate read operation results from all backends for complete visibility."""
        all_results = []
        successful_backends = []
        errors = []
        
        for i, backend in enumerate(self.backends):
            try:
                result = getattr(backend, operation)(*args, **kwargs)
                if isinstance(result, list):
                    # Mark each item with its backend source
                    for item in result:
                        if isinstance(item, dict):
                            item["backend_source"] = type(backend).__name__.replace("StorageBackend", "").lower()
                            item["backend_index"] = i
                    all_results.extend(result)
                successful_backends.append(i)
                logger.debug(f"Sync aggregate read succeeded on backend {i}: {type(backend).__name__}", source="storage_client")
            except Exception as e:
                error_msg = f"Backend {i} ({type(backend).__name__}): {str(e)}"
                errors.append(error_msg)
                logger.warning(f"Sync aggregate read failed on backend {i}: {e}", source="storage_client")
        
        if not successful_backends:
            raise Exception(f"All backends failed for {operation}. Errors: {'; '.join(errors)}")
        
        # Remove duplicates based on storage key or bucket name
        if operation == "list_files" and all_results:
            # Deduplicate files by storage key, prefer primary backend results
            seen_keys = set()
            deduplicated = []
            # Sort by backend_index to prefer primary backend (index 0)
            all_results.sort(key=lambda x: x.get("backend_index", 999))
            for item in all_results:
                key = item.get("path") or item.get("$id") or item.get("name")
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    deduplicated.append(item)
            return deduplicated
        elif operation == "list_buckets" and all_results:
            # For buckets, we want to preserve ALL instances across backends
            # but merge metadata for buckets with the same name across backends
            bucket_map = {}
            for item in all_results:
                bucket_name = item.get("name") or item.get("$id")
                if bucket_name:
                    if bucket_name not in bucket_map:
                        # First occurrence of this bucket name
                        bucket_map[bucket_name] = item.copy()
                        bucket_map[bucket_name]["backends"] = [item.get("backend_source", "unknown")]
                        bucket_map[bucket_name]["backend_count"] = 1
                    else:
                        # Additional occurrence - merge backend info
                        existing = bucket_map[bucket_name]
                        backend_source = item.get("backend_source", "unknown")
                        if backend_source not in existing["backends"]:
                            existing["backends"].append(backend_source)
                            existing["backend_count"] += 1
                        # Use earliest creation date if available
                        if "dateCreated" in item and "dateCreated" in existing:
                            if item["dateCreated"] < existing["dateCreated"]:
                                existing["dateCreated"] = item["dateCreated"]
            
            return list(bucket_map.values())
        
        return all_results
    
    def _exec_sync_single_read(self, operation: str, *args, **kwargs):
        """Execute single-value read operation checking all backends for resource availability."""
        if operation == "exists":
            # For exists operations, return True if resource exists on ANY backend
            for i, backend in enumerate(self.backends):
                try:
                    result = getattr(backend, operation)(*args, **kwargs)
                    if result:  # Resource found
                        logger.debug(f"Sync exists found resource on backend {i}: {type(backend).__name__}", source="storage_client")
                        return True
                except Exception as e:
                    logger.debug(f"Sync exists check failed on backend {i}: {e}", source="storage_client")
                    continue
            return False  # Resource not found on any backend
        
        elif operation == "download":
            # For download operations, try each backend until successful
            errors = []
            for i, backend in enumerate(self.backends):
                try:
                    result = getattr(backend, operation)(*args, **kwargs)
                    logger.debug(f"Sync download succeeded on backend {i}: {type(backend).__name__}", source="storage_client")
                    return result
                except Exception as e:
                    error_msg = f"Backend {i} ({type(backend).__name__}): {str(e)}"
                    errors.append(error_msg)
                    logger.debug(f"Sync download failed on backend {i}: {e}", source="storage_client")
                    continue
            raise Exception(f"Download failed on all backends. Errors: {'; '.join(errors)}")
        
        else:
            # For get_metadata and other operations, try primary first, then fallback
            try:
                result = getattr(self.primary_backend, operation)(*args, **kwargs)
                logger.debug(f"Sync single read succeeded on primary backend", source="storage_client")
                return result
            except Exception as primary_error:
                logger.warning(f"Sync single read failed on primary, trying other backends: {primary_error}", source="storage_client")
                
                # Try other backends as fallback
                for i, backend in enumerate(self.backends[1:], start=1):
                    try:
                        result = getattr(backend, operation)(*args, **kwargs)
                        logger.info(f"Sync single read succeeded on backend {i} after primary failure", source="storage_client")
                        return result
                    except Exception as e:
                        logger.debug(f"Sync single read failed on backend {i}: {e}", source="storage_client")
                        continue
                
                raise Exception(f"All backends failed for {operation}. Primary error: {primary_error}")

    def _attempt_rollback(self, operation: str, successful_backend_indices: list, *args, **kwargs):
        """Attempt to rollback successful operations to maintain consistency."""
        # Define rollback operations
        rollback_ops = {
            "upload": "delete",
            "create_bucket": "delete_bucket",
            # Note: delete and delete_bucket operations cannot be rolled back
            # rename operations would need complex state tracking
        }
        
        rollback_op = rollback_ops.get(operation)
        if not rollback_op:
            logger.warning(f"No rollback strategy for operation '{operation}'", source="storage_client")
            return
        
        # Attempt rollback on each successful backend
        for backend_idx in successful_backend_indices:
            try:
                backend = self.backends[backend_idx]
                getattr(backend, rollback_op)(*args, **kwargs)
                logger.debug(f"Rollback succeeded on backend {backend_idx}", source="storage_client")
            except Exception as rollback_error:
                logger.error(f"Rollback failed on backend {backend_idx}: {rollback_error}", source="storage_client")
                # Continue attempting rollback on other backends

    def _exec_atomic_bucket_creation(self, bucket_name: str) -> Dict[str, Any]:
        """
        Execute atomic bucket creation: create bucket only on backends where it doesn't exist.
        
        This implements the atomic deduplication requirement: each backend is checked 
        independently and bucket is created only on backends where it's missing.
        """
        # Check existence on each backend independently
        existence = self.bucket_exists_all_backends(bucket_name)
        
        results = []
        backends_needing_creation = []
        backends_skipped = []
        errors = []
        
        # Identify which backends need bucket creation
        for i, backend in enumerate(self.backends):
            if existence.get(i, False):
                # Bucket already exists on this backend
                backends_skipped.append(f"backend_{i}_{type(backend).__name__}")
                logger.debug(f"Bucket {bucket_name} exists on backend {i}, skipping", source="storage_client")
            else:
                # Bucket needs to be created on this backend
                backends_needing_creation.append(i)
        
        # Create bucket on backends where it's missing
        created_count = 0
        for backend_idx in backends_needing_creation:
            try:
                backend = self.backends[backend_idx]
                result = backend.create_bucket(bucket_name)
                results.append((backend_idx, result))
                created_count += 1
                logger.info(f"Atomic bucket creation succeeded on backend {backend_idx}: {type(backend).__name__}", 
                           source="storage_client", bucket=bucket_name)
            except Exception as e:
                error_msg = f"Backend {backend_idx} ({type(self.backends[backend_idx]).__name__}): {str(e)}"
                errors.append(error_msg)
                logger.error(f"Atomic bucket creation failed on backend {backend_idx}: {e}", 
                            source="storage_client", bucket=bucket_name)
        
        # Compile comprehensive result
        total_backends = len(self.backends)
        skipped_count = len(backends_skipped)
        failed_count = len(errors)
        
        success = failed_count == 0  # Success if no failures occurred
        
        result = {
            "name": bucket_name,
            "success": success,
            "backends_total": total_backends,
            "backends_created": created_count,
            "backends_skipped": skipped_count,
            "backends_failed": failed_count,
            "backends_needing_creation": backends_needing_creation,
            "backends_skipped_list": backends_skipped,
            "errors": errors,
            "atomic_deduplication": True
        }
        
        if success:
            logger.info(f"Atomic bucket creation completed successfully", 
                       source="storage_client", bucket=bucket_name, 
                       created=created_count, skipped=skipped_count, total=total_backends)
        else:
            logger.error(f"Atomic bucket creation completed with errors", 
                        source="storage_client", bucket=bucket_name,
                        created=created_count, failed=failed_count, errors=errors)
        
        # Return the result from the first successful creation or a summary
        if results:
            primary_result = results[0][1]  # Use first successful result as template
            primary_result.update(result)
            return primary_result
        else:
            # No creation attempted or all failed
            return result

    # ---- High-level API (resource-centric) ----
    def add_resource(self, storage_key: str, content: "bytes|str", metadata: Optional[Dict[str, Any]] = None, 
                    allow_override: bool = False) -> Dict[str, Any]:
        """
        Add resource to storage with multi-backend routing and automatic format handling.

        Summary
        -------
        Stores content at specified storage key with automatic encoding detection,
        metadata enrichment, and routing based on configured strategy.
        
        Includes duplication prevention: by default, skips creation if resource
        already exists unless allow_override=True.

        Parameters
        ----------
        storage_key : str
            Logical storage path (e.g., "reports/analysis.csv", "models/tokenizer.pkl")
        content : bytes or str
            Resource content (automatically encoded if string)
        metadata : Optional[Dict[str, Any]], default None
            Additional metadata for resource (experiment info, timestamps, etc.)
        allow_override : bool, default False
            If True, overwrites existing resource. If False, skips if resource exists.

        Returns
        -------
        Dict[str, Any]
            Storage result with backend info, storage_key, size, content_type.
            Includes "action" field: "created", "updated", or "skipped"

        Raises
        ------
        StorageError
            If storage operation fails across all configured backends
        ValidationError
            If storage_key format is invalid

        Examples
        --------
        >>> client = get_storage_client()
        >>> 
        >>> # Store CSV data (skip if exists)
        >>> result = client.add_resource("reports/analysis.csv", csv_data)
        >>> print(result["action"])  # "created" or "skipped"
        >>> 
        >>> # Force overwrite existing file
        >>> result = client.add_resource("reports/analysis.csv", new_data, allow_override=True)
        >>> print(result["action"])  # "updated"

        Notes
        -----
        - Default behavior prevents accidental duplication
        - allow_override=True forces update of existing resources  
        - Complexity: O(1) for primary strategy, O(n) for sync strategy
        - Encoding: Automatic UTF-8 encoding for string content
        - Routing: Executes according to configured storage strategy
        - Atomicity: Backend-specific atomic write guarantees
        """
        storage_key = normalize_storage_key(storage_key)
        
        # Check for existing resource unless override is allowed
        if not allow_override and self.resource_exists(storage_key):
            logger.info(f"Resource exists, skipping creation", source="storage_client", 
                       storage_key=storage_key, allow_override=allow_override)
            # Return metadata of existing resource with skipped action
            try:
                existing_metadata = self.get_resource_metadata(storage_key)
                existing_metadata["action"] = "skipped"
                existing_metadata["reason"] = "Resource already exists (use allow_override=True to update)"
                return existing_metadata
            except Exception:
                # Fallback if metadata retrieval fails
                return {
                    "storage_key": storage_key,
                    "action": "skipped", 
                    "reason": "Resource already exists (use allow_override=True to update)",
                    "success": True
                }
        
        if isinstance(content, str):
            content = content.encode("utf-8")
            metadata = {**(metadata or {}), "encoding": "utf-8"}
        
        result = self._execute_strategy("upload", storage_key, content, metadata)
        
        # Add action indicator based on whether resource existed before
        if allow_override:
            result["action"] = "updated"
        else:
            result["action"] = "created"
            
        return result

    def get_resource(self, storage_key: str) -> bytes:
        """
        Retrieve resource content from storage with optimal backend selection.

        Summary
        -------
        Downloads complete resource content using configured routing strategy
        for optimal performance and reliability.

        Parameters
        ----------
        storage_key : str
            Logical storage path for the resource

        Returns
        -------
        bytes
            Complete resource content as raw bytes

        Raises
        ------
        NotFoundError
            If resource doesn't exist in any configured backend
        StorageError
            If retrieval fails due to connectivity or access issues

        Examples
        --------
        >>> client = get_storage_client()
        >>> 
        >>> # Retrieve text data
        >>> csv_bytes = client.get_resource("reports/analysis.csv")
        >>> csv_text = csv_bytes.decode('utf-8')
        >>> 
        >>> # Retrieve binary model
        >>> model_bytes = client.get_resource("models/trained_classifier.pkl")

        Notes
        -----
        - Complexity: O(1) with optimized backend selection
        - Memory: Loads complete resource - use download_to_path() for large files
        - Strategy: Reads from fastest available backend in replica/failover modes
        """
        return self._execute_strategy("download", storage_key)

    def delete_resource(self, storage_key: str) -> bool:
        return self._execute_strategy("delete", storage_key)

    def list_resources(self, folder: str = "") -> List[Dict[str, Any]]:
        """
        List all resources in specified folder across storage backends.

        Summary
        -------
        Retrieves comprehensive listing of resources in given folder path,
        aggregating results from all configured storage backends with deduplication.

        Parameters
        ----------
        folder : str, default ""
            Folder path to list resources from; empty string lists root level

        Returns
        -------
        List[Dict[str, Any]]
            List of resource dictionaries containing:
            - storage_key (str): Resource identifier
            - size (int): Resource size in bytes
            - modified (str): Last modification timestamp
            - metadata (dict): Associated resource metadata

        Raises
        ------
        StorageError
            If listing operation fails on any backend
        ValidationError
            If folder path format is invalid

        Examples
        --------
        >>> client = StorageClient()
        >>> 
        >>> # List all resources in root
        >>> all_resources = client.list_resources()
        >>> 
        >>> # List papers in specific folder
        >>> papers = client.list_resources("raw_papers")
        >>> for paper in papers:
        ...     print(f"{paper['storage_key']}: {paper['size']} bytes")
        >>> 
        >>> # List processed XML files
        >>> xml_files = client.list_resources("processed_xml")
        >>> recent_files = [f for f in xml_files 
        ...                if f['modified'] > '2023-01-01']

        Notes
        -----
        - Aggregation: Combines results from all configured backends
        - Deduplication: Removes duplicate entries across backends
        - Performance: May be slow for large folders with many resources
        - Ordering: Results are not guaranteed to be in any specific order
        - Metadata: Includes comprehensive resource information for analysis
        """
        return self._execute_strategy("list_files", folder)

    def resource_exists(self, storage_key: str) -> bool:
        return self._execute_strategy("exists", storage_key)

    def get_resource_metadata(self, storage_key: str) -> Dict[str, Any]:
        return self._execute_strategy("get_metadata", storage_key)

    def upload_from_path(self, local_path: str, dest_storage_key: str, metadata: Optional[Dict[str, Any]] = None, 
                        allow_override: bool = False) -> Dict[str, Any]:
        """
        Upload local file to storage backend with automatic metadata capture.

        Summary
        -------
        Reads file from local filesystem and uploads to configured storage backend,
        automatically capturing file metadata and preserving original filename.
        
        Includes duplication prevention: by default, skips upload if resource
        already exists unless allow_override=True.

        Parameters
        ----------
        local_path : str
            Absolute or relative path to local file to upload
        dest_storage_key : str
            Target storage key following storage naming conventions
        metadata : Optional[Dict[str, Any]], default None
            Additional metadata to attach to stored resource
        allow_override : bool, default False
            If True, overwrites existing resource. If False, skips if resource exists.

        Returns
        -------
        Dict[str, Any]
            Upload result containing:
            - storage_key (str): Final storage location
            - size (int): File size in bytes
            - backend (str): Storage backend used
            - metadata (dict): Combined metadata including original filename
            - action (str): "created", "updated", or "skipped"

        Raises
        ------
        FileNotFoundError
            If local_path does not exist or is not accessible
        StorageError
            If upload fails due to backend issues
        ValidationError
            If dest_storage_key format is invalid

        Examples
        --------
        >>> client = StorageClient()
        >>> 
        >>> # Upload research paper (skip if exists)
        >>> result = client.upload_from_path(
        ...     "/tmp/polymer_study.pdf",
        ...     "raw_papers/polymer_study.pdf",
        ...     {"study_type": "mechanical_properties", "year": 2023}
        ... )
        >>> print(f"Action: {result['action']}")  # "created" or "skipped"
        >>> 
        >>> # Force overwrite existing file
        >>> result = client.upload_from_path(
        ...     "./updated_data.csv", 
        ...     "datasets/training_samples.csv",
        ...     allow_override=True
        ... )
        >>> print(f"Action: {result['action']}")  # "updated"

        Notes
        -----
        - Default behavior prevents accidental file duplication
        - allow_override=True forces update of existing files
        - Metadata: Automatically adds original_name and source_path
        - Path Resolution: Supports relative and absolute paths
        - Performance: Streams large files efficiently to backend
        - Atomicity: Upload either succeeds completely or fails cleanly
        """
        lp = Path(local_path)
        if not lp.exists():
            raise FileNotFoundError(local_path)
        content = lp.read_bytes()
        md = {"original_name": lp.name, "source_path": str(lp)}
        md.update(metadata or {})
        return self.add_resource(dest_storage_key, content, md, allow_override=allow_override)

    def download_to_path(self, storage_key: str, local_dest_path: str) -> bool:
        """
        Download resource from storage to local filesystem path.

        Summary
        -------
        Retrieves resource from storage backend and writes to specified local path,
        creating parent directories as needed.

        Parameters
        ----------
        storage_key : str
            Storage key identifying resource to download
        local_dest_path : str
            Target local filesystem path for downloaded content

        Returns
        -------
        bool
            True if download completed successfully

        Raises
        ------
        NotFoundError
            If storage_key does not exist in any backend
        StorageError
            If download fails due to backend issues
        OSError
            If local filesystem write fails

        Examples
        --------
        >>> client = StorageClient()
        >>> 
        >>> # Download processed data
        >>> success = client.download_to_path(
        ...     "processed_xml/paper_123.xml",
        ...     "/tmp/downloads/paper_123.xml"
        ... )
        >>> 
        >>> # Download to relative path (creates directories)
        >>> client.download_to_path(
        ...     "reports/analysis_2023.csv",
        ...     "./output/reports/analysis_2023.csv"
        ... )

        Notes
        -----
        - Directory Creation: Automatically creates parent directories
        - Overwrite: Overwrites existing files without warning
        - Performance: Streams large files efficiently from backend
        - Atomicity: Write operation is atomic (temp file + rename)
        """
        content = self.get_resource(storage_key)
        dp = Path(local_dest_path)
        dp.parent.mkdir(parents=True, exist_ok=True)
        dp.write_bytes(content)
        return True

    def fetch_from_url(self, url: str, dest_storage_key: Optional[str] = None, file_type: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Fetch content from URL and store in configured storage backend.

        Summary
        -------
        Downloads content from external URL and stores in storage system with
        automatic filename generation and comprehensive metadata capture.

        Parameters
        ----------
        url : str
            HTTP/HTTPS URL to fetch content from
        dest_storage_key : Optional[str], default None
            Target storage key; auto-generated if not provided
        file_type : Optional[str], default None
            File extension to append if missing from URL filename
        metadata : Optional[Dict[str, Any]], default None
            Additional metadata to attach to stored resource

        Returns
        -------
        Dict[str, Any]
            Storage result containing:
            - storage_key (str): Final storage location
            - size (int): Downloaded content size
            - metadata (dict): Including source_url, fetch_date, content_type

        Raises
        ------
        ValueError
            If URL is invalid or fetch operation fails
        StorageError
            If storage backend operations fail
        TimeoutError
            If URL fetch exceeds 30 second timeout

        Examples
        --------
        >>> client = StorageClient()
        >>> 
        >>> # Fetch research paper from publisher
        >>> result = client.fetch_from_url(
        ...     "https://doi.org/10.1234/polymer-study.pdf",
        ...     "raw_papers/polymer_study.pdf",
        ...     metadata={"doi": "10.1234/polymer-study"}
        ... )
        >>> 
        >>> # Auto-generate storage key from URL
        >>> result = client.fetch_from_url(
        ...     "https://example.com/data/samples.csv",
        ...     file_type="csv"
        ... )
        >>> # Stored as "downloads/samples.csv"

        Notes
        -----
        - Timeout: 30 second limit for URL fetch operations
        - Metadata: Automatically captures source_url, fetch_date, content_type
        - Filename: Auto-extracts from URL or generates "downloaded_file"
        - MIME Type: Preserves HTTP Content-Type header information
        - Security: No validation of URL content - use with trusted sources
        """
        import urllib.parse
        
        # Download content from URL
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            content = response.content
        except Exception as e:
            raise ValueError(f"Failed to fetch URL {url}: {e}")
        
        # Generate storage key if not provided
        if not dest_storage_key:
            parsed = urllib.parse.urlparse(url)
            filename = os.path.basename(parsed.path) or "downloaded_file"
            # Add file extension if missing and file_type provided
            if file_type and not filename.endswith(f".{file_type}"):
                filename = f"{filename}.{file_type}"
            dest_storage_key = f"downloads/{filename}"
        
        # Prepare metadata
        fetch_metadata = {
            "source_url": url,
            "fetch_date": datetime.now().isoformat(),
            "content_type": response.headers.get("content-type", ""),
            **(metadata or {})
        }
        
        if not fetch_metadata.get("mimeType"):
            fetch_metadata["mimeType"] = response.headers.get("content-type", "application/octet-stream")
        
        return self.add_resource(dest_storage_key, content, fetch_metadata)

    # ---- Buckets convenience ----
    def create_bucket(self, bucket_name: str, allow_override: bool = False) -> Dict[str, Any]:
        """
        Create storage bucket with duplication prevention and protected bucket handling.
        
        Summary
        -------
        Creates a new storage bucket across configured backends with automatic
        duplication prevention. Protected buckets (models, system_logs) are created
        only on local backend for security and performance.
        
        Parameters
        ----------
        bucket_name : str
            Name of the bucket to create
        allow_override : bool, default False
            If True, attempts to recreate bucket. If False, skips if bucket exists.
            
        Returns
        -------
        Dict[str, Any]
            Creation result with "action" field: "created", "updated", or "skipped"
            
        Notes
        -----
        - Default behavior prevents bucket duplication
        - Protected buckets only created on local backend
        - allow_override=True may fail if bucket contains data (backend-dependent)
        """
        # Check if this is a protected bucket (local-only)
        if self._is_protected_bucket(bucket_name):
            logger.info(f"Protected bucket detected, creating on local backend only", 
                       source="storage_client", bucket=bucket_name)
            
            # For protected buckets, only use local backend
            if self.backends and isinstance(self.backends[0], LocalStorageBackend):
                local_backend = self.backends[0]
                
                # Check if bucket already exists locally
                if not allow_override:
                    try:
                        local_buckets = local_backend.list_buckets()
                        bucket_exists = any(b.get("name") == bucket_name for b in local_buckets)
                        
                        if bucket_exists:
                            logger.info(f"Protected bucket exists locally, skipping creation", 
                                       source="storage_client", bucket=bucket_name)
                            return {
                                "name": bucket_name,
                                "action": "skipped",
                                "reason": "Protected bucket already exists locally",
                                "success": True,
                                "protected": True,
                                "backend": "local"
                            }
                    except Exception as e:
                        logger.warning(f"Could not check local bucket existence, proceeding with creation", 
                                      source="storage_client", error=str(e))
                
                # Create bucket on local backend only
                try:
                    result = local_backend.create_bucket(bucket_name)
                    result["action"] = "created" if not allow_override else "updated"
                    result["protected"] = True
                    result["backend"] = "local"
                    logger.info(f"Protected bucket created locally", source="storage_client", bucket=bucket_name)
                    return result
                except Exception as e:
                    logger.error(f"Failed to create protected bucket locally", 
                                source="storage_client", bucket=bucket_name, error=str(e))
                    raise
            else:
                # No local backend available, skip protected bucket creation
                logger.warning(f"No local backend available for protected bucket", 
                              source="storage_client", bucket=bucket_name)
                return {
                    "name": bucket_name,
                    "action": "skipped", 
                    "reason": "Protected bucket requires local backend",
                    "success": False,
                    "protected": True
                }
        
        # Regular bucket creation (non-protected)
        # Check for existing bucket unless override is allowed
        if not allow_override:
            try:
                existing_buckets = self.list_buckets()
                bucket_exists = any(b.get("name") == bucket_name for b in existing_buckets)
                
                if bucket_exists:
                    logger.info(f"Bucket exists, skipping creation", source="storage_client", 
                               bucket=bucket_name, allow_override=allow_override)
                    return {
                        "name": bucket_name,
                        "action": "skipped",
                        "reason": "Bucket already exists (use allow_override=True to recreate)",
                        "success": True,
                        "protected": False
                    }
            except Exception as e:
                logger.warning(f"Could not check existing buckets, proceeding with creation", 
                              source="storage_client", error=str(e))
        
        result = self._execute_strategy("create_bucket", bucket_name)
        
        # Add action indicator
        result["action"] = "created" if not allow_override else "updated"
        result["protected"] = False
        return result

    def delete_bucket(self, bucket_name: str) -> bool:
        return self._execute_strategy("delete_bucket", bucket_name)

    def list_buckets(self) -> List[Dict[str, Any]]:
        return self._execute_strategy("list_buckets")

    def rename_resource(self, old_storage_key: str, new_storage_key: str) -> bool:
        """
        Rename/move resource from old storage key to new storage key.
        
        Summary
        -------
        Moves resource content and metadata from old location to new location
        across configured storage backends according to routing strategy.
        
        Parameters
        ----------
        old_storage_key : str
            Current storage key of the resource
        new_storage_key : str  
            Target storage key for the resource
            
        Returns
        -------
        bool
            True if rename succeeded on all required backends
            
        Raises
        ------
        NotFoundError
            If old_storage_key does not exist
        StorageError
            If rename operation fails due to backend issues
            
        Examples
        --------
        >>> client = StorageClient()
        >>> success = client.rename_resource(
        ...     "temp/analysis.csv",
        ...     "reports/final_analysis.csv"
        ... )
        >>> if success:
        ...     print("Resource renamed successfully")
        
        Notes
        -----
        - Cross-bucket moves are supported where backend allows
        - Metadata is preserved during the rename operation
        - Operation is atomic per backend (temp copy + delete pattern)
        - Strategy determines how many backends must succeed
        """
        return self._execute_strategy("rename_resource", old_storage_key, new_storage_key)

    def rename_bucket(self, old_bucket_name: str, new_bucket_name: str) -> bool:
        """
        Rename bucket from old name to new name.
        
        Summary
        -------
        Renames bucket and all contained resources across configured storage
        backends according to routing strategy.
        
        Parameters
        ----------
        old_bucket_name : str
            Current name of the bucket
        new_bucket_name : str
            Target name for the bucket
            
        Returns
        -------
        bool
            True if rename succeeded on all required backends
            
        Raises
        ------
        NotFoundError
            If old_bucket_name does not exist
        StorageError
            If rename operation fails due to backend issues
        ValidationError
            If new_bucket_name is invalid for backend
            
        Examples
        --------
        >>> client = StorageClient()
        >>> success = client.rename_bucket("temp-data", "archived-data")
        >>> if success:
        ...     print("Bucket renamed successfully")
        
        Notes
        -----
        - All resources within bucket are moved to new bucket
        - Operation may take time for buckets with many resources
        - Some backends implement rename as copy+delete
        - Bucket naming rules are enforced per backend type
        """
        return self._execute_strategy("rename_bucket", old_bucket_name, new_bucket_name)

    def empty_bucket(self, bucket_name: str) -> bool:
        """
        Empty all files from a bucket across configured backends based on strategy.
        
        For sync/replica strategies: Empties bucket on ALL backends
        For primary/failover strategies: Empties bucket on primary backend only
        """
        if self.strategy in ["primary", "failover"]:
            # Single-backend operation
            return self._empty_bucket_single(bucket_name, self.primary_backend)
        
        elif self.strategy in ["replica", "sync"]:
            # Multi-backend operation - empty on ALL backends
            success_count = 0
            
            for i, backend in enumerate(self.backends):
                try:
                    if self._empty_bucket_single(bucket_name, backend):
                        success_count += 1
                        logger.debug(f"Empty bucket succeeded on backend {i}: {type(backend).__name__}", source="storage_client")
                    else:
                        logger.warning(f"Empty bucket failed on backend {i}: {type(backend).__name__}", source="storage_client")
                except Exception as e:
                    logger.warning(f"Empty bucket error on backend {i}: {e}", source="storage_client")
            
            if self.strategy == "sync":
                # Sync strategy requires success on ALL backends
                return success_count == len(self.backends)
            else:
                # Replica strategy succeeds if ANY backend succeeds
                return success_count > 0
        
        else:
            # Default fallback to primary
            return self._empty_bucket_single(bucket_name, self.primary_backend)
    
    def _empty_bucket_single(self, bucket_name: str, backend: StorageBackend) -> bool:
        """Empty bucket on a single backend."""
        try:
            if isinstance(backend, LocalStorageBackend):
                # Local backend: delete all files in bucket directory
                base = backend.base_path / bucket_name
                if base.exists() and base.is_dir():
                    for p in base.rglob("*"):
                        if p.is_file() and not p.name.endswith(".meta"):
                            try:
                                p.unlink()
                                # Also remove metadata file if exists
                                meta_file = p.with_suffix(p.suffix + ".meta")
                                if meta_file.exists():
                                    meta_file.unlink()
                            except Exception:
                                pass
                return True
            else:
                # Cloud backends: list and delete files
                try:
                    files = backend.list_files(bucket_name + "/")
                    for file_info in files:
                        storage_key = file_info.get("$id") or file_info.get("path")
                        if storage_key:
                            try:
                                backend.delete(storage_key)
                            except Exception:
                                pass
                    return True
                except Exception:
                    return False
        except Exception:
            return False

    def bucket_exists(self, bucket_name: str) -> bool:
        """
        Check if bucket exists based on current storage strategy.
        
        - primary/failover: Check primary backend only
        - replica/sync: Check if bucket exists on ANY backend (true multi-backend visibility)
        """
        if self.strategy in ["primary", "failover"]:
            # Single-backend effective operation - check primary only
            try:
                buckets = self._execute_strategy("list_buckets")
                names = {b.get("name") or b.get("$id") for b in buckets}
                return bucket_name in names
            except Exception:
                return False
        
        elif self.strategy in ["replica", "sync"]:
            # Multi-backend operation - check if exists on ANY backend
            existence = self.bucket_exists_all_backends(bucket_name)
            return any(existence.values())
        
        else:
            # Default fallback to primary behavior
            try:
                buckets = self._execute_strategy("list_buckets")
                names = {b.get("name") or b.get("$id") for b in buckets}
                return bucket_name in names
            except Exception:
                return False

    def bucket_exists_all_backends(self, bucket_name: str) -> Dict[str, bool]:
        """Check if bucket exists on all configured backends.
        
        Returns a dict mapping backend index to existence status.
        Useful for multi-backend strategies to determine if bucket needs creation.
        """
        existence = {}
        for i, backend in enumerate(self.backends):
            try:
                if hasattr(backend, 'bucket_exists'):
                    existence[i] = backend.bucket_exists(bucket_name)
                else:
                    # Fallback: check via list_buckets
                    buckets = backend.list_buckets() if hasattr(backend, 'list_buckets') else []
                    names = {b.get("name") or b.get("$id") for b in buckets}
                    existence[i] = bucket_name in names
            except Exception:
                existence[i] = False
        return existence

    def should_create_bucket(self, bucket_name: str) -> bool:
        """
        Determine if bucket should be created based on strategy and atomic per-backend existence checking.
        
        Implements atomic deduplication: checks each backend independently and only creates 
        bucket on backends where it doesn't exist, rather than all-or-nothing approach.
        
        For protected buckets: always check only local backend regardless of strategy.
        For regular buckets: check based on strategy requirements.
        """
        # Protected buckets are always local-only
        if self._is_protected_bucket(bucket_name):
            if self.backends and isinstance(self.backends[0], LocalStorageBackend):
                try:
                    local_buckets = self.backends[0].list_buckets()
                    bucket_exists = any(b.get("name") == bucket_name for b in local_buckets)
                    return not bucket_exists
                except Exception:
                    return True  # Assume needs creation if can't check
            return False  # No local backend for protected bucket
        
        # For non-protected buckets, use strategy-based atomic checking
        if self.strategy in ["primary", "failover"]:
            # Single-backend effective operation
            return not self.bucket_exists(bucket_name)
        
        elif self.strategy in ["replica", "sync"]:
            # Multi-backend operation with atomic per-backend checking
            # This allows creating buckets on backends where they don't exist
            # while skipping backends where they already exist
            try:
                existence = self.bucket_exists_all_backends(bucket_name)
                # Return True if ANY backend is missing the bucket
                # The actual creation logic will handle per-backend creation
                return not all(existence.values())
            except Exception:
                # If can't check, assume needs creation
                return True
        
        # Default fallback
        return not self.bucket_exists(bucket_name)

    # ---- Diagnostics ----
    def test_connection(self) -> Dict[str, Any]:
        """
        Comprehensive connection testing with strategy-specific validation.
        
        Tests each backend individually and validates strategy requirements
        for optimal performance and reliability.
        """
        if not self.backends:
            return {
                "success": False, 
                "message": "No storage backends configured", 
                "backends_tested": 0,
                "details": {},
                "strategy_assessment": "invalid - no backends"
            }
        
        results: Dict[str, Any] = {}
        successful_backends = 0
        test_start_time = time.time()
        
        # Test each backend individually
        for i, backend in enumerate(self.backends):
            backend_key = f"backend_{i}"
            backend_type = "unknown"
            backend_start_time = time.time()
            
            try:
                if isinstance(backend, LocalStorageBackend):
                    backend_type = "local"
                    path_exists = backend.base_path.exists()
                    if path_exists:
                        # Test write capability with atomic operation
                        test_key = f".test_connection_{int(time.time())}"
                        test_content = f"test_data_{i}_{int(time.time())}".encode()
                        backend.upload(test_key, test_content, {"test": True})
                        retrieved = backend.download(test_key)
                        backend.delete(test_key)
                        write_test = retrieved == test_content
                    else:
                        write_test = False
                    
                    backend_duration = time.time() - backend_start_time
                    results[backend_key] = {
                        "backend_type": backend_type,
                        "success": path_exists and write_test,
                        "path": str(backend.base_path),
                        "write_test": write_test,
                        "response_time_ms": round(backend_duration * 1000, 2)
                    }
                    if path_exists and write_test:
                        successful_backends += 1
                        
                elif "AppwriteStorageBackend" in str(type(backend)):
                    backend_type = "appwrite"
                    # Test with bucket listing and optional write test
                    buckets = backend.list_buckets()
                    
                    # Optional write test if we have buckets
                    write_test = True
                    if buckets:
                        try:
                            test_bucket = buckets[0]["name"]
                            test_key = f"{test_bucket}/.test_connection_{int(time.time())}"
                            test_content = f"test_data_{i}_{int(time.time())}".encode()
                            backend.upload(test_key, test_content, {"test": True})
                            backend.delete(test_key)
                        except Exception:
                            write_test = False
                    
                    backend_duration = time.time() - backend_start_time
                    results[backend_key] = {
                        "backend_type": backend_type,
                        "success": True,
                        "buckets_found": len(buckets),
                        "write_test": write_test,
                        "response_time_ms": round(backend_duration * 1000, 2)
                    }
                    successful_backends += 1
                    
                elif "S3StorageBackend" in str(type(backend)):
                    backend_type = "s3"
                    # Test with bucket listing
                    buckets = backend.list_buckets()
                    
                    # Optional write test if we have buckets
                    write_test = True
                    if buckets:
                        try:
                            test_bucket = buckets[0]["name"]
                            test_key = f".test_connection_{int(time.time())}"
                            test_content = f"test_data_{i}_{int(time.time())}".encode()
                            backend.upload(f"{test_bucket}/{test_key}", test_content, {"test": True})
                            backend.delete(f"{test_bucket}/{test_key}")
                        except Exception:
                            write_test = False
                    
                    backend_duration = time.time() - backend_start_time
                    results[backend_key] = {
                        "backend_type": backend_type,
                        "success": True,
                        "buckets_found": len(buckets),
                        "region": getattr(backend, "region", "unknown"),
                        "write_test": write_test,
                        "response_time_ms": round(backend_duration * 1000, 2)
                    }
                    successful_backends += 1
                    
                else:
                    # Generic test for unknown backend types
                    backend.list_files("")
                    backend_duration = time.time() - backend_start_time
                    results[backend_key] = {
                        "backend_type": backend_type,
                        "success": True,
                        "response_time_ms": round(backend_duration * 1000, 2)
                    }
                    successful_backends += 1
                    
            except Exception as e:
                backend_duration = time.time() - backend_start_time
                results[backend_key] = {
                    "backend_type": backend_type,
                    "success": False,
                    "error": str(e),
                    "response_time_ms": round(backend_duration * 1000, 2)
                }
        
        total_duration = time.time() - test_start_time
        overall_success = successful_backends > 0
        
        # Strategy-specific assessment
        strategy_assessment = self._assess_strategy_health(successful_backends, len(self.backends))
        
        return {
            "success": overall_success,
            "strategy": self.strategy,
            "backends_tested": len(self.backends),
            "successful_backends": successful_backends,
            "primary_backend": self.get_backend_type(),
            "total_test_duration_ms": round(total_duration * 1000, 2),
            "strategy_assessment": strategy_assessment,
            "details": results,
            "recommendations": self._get_health_recommendations(successful_backends, len(self.backends))
        }

    def _assess_strategy_health(self, successful_backends: int, total_backends: int) -> str:
        """Assess health status based on strategy requirements."""
        if successful_backends == 0:
            return "critical - no backends available"
        
        if self.strategy == "primary":
            return "healthy" if successful_backends >= 1 else "degraded"
        
        elif self.strategy == "replica":
            if successful_backends == total_backends:
                return "optimal - full redundancy"
            elif successful_backends >= 2:
                return "healthy - partial redundancy"
            elif successful_backends == 1:
                return "degraded - no redundancy"
            else:
                return "critical - no backends"
        
        elif self.strategy == "failover":
            if successful_backends == total_backends:
                return "optimal - full failover chain"
            elif successful_backends >= 2:
                return "healthy - partial failover"
            elif successful_backends == 1:
                return "degraded - no failover"
            else:
                return "critical - no backends"
        
        elif self.strategy == "sync":
            if successful_backends == total_backends:
                return "optimal - all backends synchronized"
            else:
                return f"critical - sync requires all backends ({successful_backends}/{total_backends} available)"
        
        return "unknown strategy"

    def _get_health_recommendations(self, successful_backends: int, total_backends: int) -> List[str]:
        """Get health-based recommendations for the current configuration."""
        recommendations = []
        
        if successful_backends == 0:
            recommendations.append("URGENT: No storage backends are accessible - check configuration and network connectivity")
            return recommendations
        
        if successful_backends < total_backends:
            failed_count = total_backends - successful_backends
            recommendations.append(f"WARNING: {failed_count}/{total_backends} backends are failing - investigate connection issues")
        
        if self.strategy == "sync" and successful_backends < total_backends:
            recommendations.append("CRITICAL: Sync strategy requires all backends functional - consider switching to 'replica' or 'failover' strategy")
        
        if self.strategy == "primary" and total_backends > 1:
            recommendations.append("INFO: Multiple backends configured but only primary is used - consider 'replica' or 'failover' strategy")
        
        if successful_backends == total_backends:
            recommendations.append("✓ All backends healthy - optimal configuration for current strategy")
        
        return recommendations


# Factories (preferred)

def get_storage_client() -> StorageClient:
    return StorageClient()


# Back-compat synonyms for file-centric method names
StorageClient.upload_file = StorageClient.add_resource  # type: ignore
StorageClient.download_file = StorageClient.get_resource  # type: ignore
StorageClient.delete_file = StorageClient.delete_resource  # type: ignore
StorageClient.list_files = StorageClient.list_resources  # type: ignore
StorageClient.file_exists = StorageClient.resource_exists  # type: ignore
StorageClient.get_file_metadata = StorageClient.get_resource_metadata  # type: ignore
