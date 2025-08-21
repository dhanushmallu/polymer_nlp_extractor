"""
polymer_extractor/storage/storage_manager.py

High-level StorageManager for unified multi-backend storage operations.

Purpose
-------
Provides user-friendly, logged storage operations wrapping StorageClient with:
- Comprehensive resource management (add, get, delete, list, exists, metadata)
- Convenience operations (upload from path, download to path, URL fetching)
- Multi-backend support (local, Appwrite, S3) with routing strategies
- Integration with path resolution system for consistent file handling
- Structured logging for all storage operations

Key Abstractions
----------------
- StorageManager: High-level interface with logging and error handling
- Resource operations: Logical storage keys mapped to backend-specific implementations
- Path integration: Seamless conversion between local paths and storage keys
- URL fetching: Direct web resource ingestion into storage backends

Design Invariants
-----------------
- Storage keys are logical paths (e.g., "reports/eval.csv") independent of backend
- All operations are logged with structured metadata for debugging
- Path resolution uses polymer_extractor.utils.paths for consistency
- Backward compatibility maintained via method aliases

Environment Integration
----------------------
Uses environment variables for backend configuration:
- STORAGE_BACKEND: Primary backend (local|appwrite|s3)
- STORAGE_BACKENDS_ACTIVE: Active backends for routing
- STORAGE_STRATEGY: Routing strategy (primary|replica|failover|sync)

Examples
--------
>>> from polymer_extractor.storage.storage_manager import StorageManager
>>> storage = StorageManager()
>>> # Add resource with metadata
>>> result = storage.add_resource("reports/analysis.csv", csv_data, {"type": "analysis"})
>>> 
>>> # Upload from local path
>>> storage.upload_from_path("/tmp/data.json", "datasets/processed.json")
>>> 
>>> # Fetch from URL
>>> storage.fetch_from_url("https://example.com/paper.pdf", "papers/paper1.pdf")
>>> 
>>> # Resource management
>>> if storage.resource_exists("models/tokenizer.json"):
...     metadata = storage.get_resource_metadata("models/tokenizer.json")

Notes
-----
- Performance: O(1) operations with backend-specific optimizations
- Thread Safety: Individual operations are thread-safe; use locking for multi-operation sequences
- Error Handling: All operations raise structured exceptions from storage.exceptions
- Memory: Streaming operations for large files to minimize memory footprint
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Union

from polymer_extractor.utils.logging import get_logger
from polymer_extractor.utils.paths import path_resolver
try:
    from polymer_extractor.storage.storage_client import get_storage_client, StorageClient  # type: ignore
except Exception:  # pragma: no cover - fallback for local tooling
    from .storage_client import get_storage_client, StorageClient  # type: ignore

logger = get_logger()


class StorageManager:
    """
    High-level storage operations with comprehensive logging and error handling.

    Summary
    -------
    Provides user-friendly interface for multi-backend storage operations with
    structured logging, path resolution, and URL fetching capabilities.

    Methods Overview
    ----------------
    Standard resource operations:
    - add_resource(storage_key, content[, metadata]) -> dict
    - get_resource(storage_key) -> bytes  
    - delete_resource(storage_key) -> bool
    - list_resources(folder="") -> list[dict]
    - resource_exists(storage_key) -> bool
    - get_resource_metadata(storage_key) -> dict

    Convenience operations:
    - upload_from_path(source_path, dest_storage_key[, metadata]) -> dict
    - download_to_path(storage_key, dest_local_path) -> bool
    - fetch_from_url(url[, dest_storage_key, file_type, metadata]) -> dict

    Backend management:
    - create_bucket(bucket_name) -> dict
    - delete_bucket(bucket_name) -> bool  
    - list_buckets() -> list[dict]
    - bucket_exists(bucket_name) -> bool
    - test_connection() -> dict
    - get_backend_type() -> str
    - get_storage_info() -> dict
    - get_backend_param_spec() -> dict
    - get_api_overview() -> dict

    Examples
    --------
    >>> storage = StorageManager()
    >>> # Basic resource operations
    >>> storage.add_resource("data/sample.json", json_content)
    >>> content = storage.get_resource("data/sample.json")
    >>> storage.delete_resource("data/sample.json")
    >>> 
    >>> # Path-based operations
    >>> storage.upload_from_path("/local/file.csv", "datasets/upload.csv")
    >>> storage.download_to_path("datasets/upload.csv", "/local/download.csv")
    >>> 
    >>> # URL fetching
    >>> result = storage.fetch_from_url("https://example.com/data.pdf", "papers/fetched.pdf")

    Notes
    -----
    - Complexity: O(1) for single operations, O(n) for list operations
    - Side Effects: All operations logged with structured metadata
    - Thread Safety: Individual operations thread-safe, use external locking for sequences
    - Memory Usage: Streaming operations for large files
    """

    def __init__(self) -> None:
        """
        Initialize StorageManager with environment-configured backend.

        Summary
        -------
        Creates StorageManager instance using environment variables for backend configuration.

        Raises
        ------
        ConfigError
            If required environment variables are missing or invalid

        Examples
        --------
        >>> storage = StorageManager()  # Uses .env configuration
        >>> info = storage.get_storage_info()
        >>> print(f"Using {info['primary_backend']} backend")

        Notes
        -----
        - Performance: O(1) - Lightweight initialization
        - Side Effects: Logs initialization with backend information
        """
        self.client: StorageClient = get_storage_client()
        info = self.client.get_storage_info()
        logger.info(
            f"StorageManager initialized with {info['primary_backend']} backend ({info['strategy']} strategy)",
            source="storage_manager",
            event_type="startup",
        )

    # resource methods
    def add_resource(self, storage_key: str, content: Union[bytes, str], metadata: Optional[Dict[str, Any]] = None, 
                    allow_override: bool = False) -> Dict[str, Any]:
        """
        Add content to storage with optional metadata and duplication prevention.

        Summary
        -------
        Stores content at the specified storage key with structured logging and error handling.
        By default, skips creation if resource already exists unless allow_override=True.

        Parameters
        ----------
        storage_key : str
            Logical storage path (e.g., "reports/analysis.csv")
        content : Union[bytes, str]
            Content to store (binary or text)
        metadata : Optional[Dict[str, Any]], default None
            Additional metadata to associate with the resource
        allow_override : bool, default False
            If True, overwrites existing resource. If False, skips if resource exists.

        Returns
        -------
        Dict[str, Any]
            Storage operation result with backend-specific information.
            Includes "action" field: "created", "updated", or "skipped"

        Raises
        ------
        StorageError
            If the storage operation fails
        ConfigError
            If backend configuration is invalid

        Examples
        --------
        >>> storage = StorageManager()
        >>> # Skip if exists
        >>> result = storage.add_resource("data/sample.json", json_content, {"type": "processed"})
        >>> print(f"Action: {result['action']}")  # "created" or "skipped"
        >>> 
        >>> # Force overwrite
        >>> result = storage.add_resource("data/sample.json", new_content, allow_override=True)
        >>> print(f"Action: {result['action']}")  # "updated"

        Notes
        -----
        - Default behavior prevents accidental resource duplication
        - allow_override=True forces update of existing resources
        - Performance: O(1) - Direct storage operation
        - Side Effects: Logs operation with timing and metadata
        - Memory: Content held in memory during operation
        """
        try:
            return self.client.add_resource(storage_key, content, metadata, allow_override)
        except Exception as e:
            logger.error(f"Failed to add resource {storage_key}", error=e, source="storage_manager")
            raise

    def upload_from_path(self, source_path: str, dest_storage_key: str, metadata: Optional[Dict[str, Any]] = None, 
                        allow_override: bool = False) -> Dict[str, Any]:
        """
        Upload a local file to storage with path-based operations and duplication prevention.

        Summary
        -------
        Transfers file from local filesystem to configured storage backend with metadata.
        By default, skips upload if resource already exists unless allow_override=True.

        Parameters
        ----------
        source_path : str
            Absolute path to local file to upload
        dest_storage_key : str
            Storage key destination (e.g., "reports/analysis.pdf")
        metadata : Optional[Dict[str, Any]], default None
            Custom metadata to associate with the resource
        allow_override : bool, default False
            If True, overwrites existing resource. If False, skips if resource exists.

        Returns
        -------
        Dict[str, Any]
            Upload result with storage_key, size, content_type, and backend-specific info.
            Includes "action" field: "created", "updated", or "skipped"

        Raises
        ------
        FileNotFoundError
            If source_path does not exist
        StorageError
            If upload operation fails due to backend issues

        Examples
        --------
        >>> manager = get_storage_manager()
        >>> # Skip if exists
        >>> result = manager.upload_from_path(
        ...     "/tmp/data.csv", 
        ...     "datasets/experiment_1.csv",
        ...     metadata={"experiment": "polymer_analysis"}
        ... )
        >>> print(f"Action: {result['action']}")  # "created" or "skipped"
        >>> 
        >>> # Force overwrite
        >>> result = manager.upload_from_path(
        ...     "/tmp/updated_data.csv", 
        ...     "datasets/experiment_1.csv",
        ...     allow_override=True
        ... )
        >>> print(f"Action: {result['action']}")  # "updated"

        Notes
        -----
        - Default behavior prevents accidental file duplication
        - allow_override=True forces update of existing files
        - Complexity: O(n) where n is file size
        - Side Effects: Creates storage resource, logs operation
        """
        try:
            return self.client.upload_from_path(source_path, dest_storage_key, metadata, allow_override)
        except Exception as e:
            logger.error(f"Failed to upload from path {source_path} -> {dest_storage_key}", error=e, source="storage_manager")
            raise

    def get_resource(self, storage_key: str) -> bytes:
        """
        Retrieve resource content from storage as bytes.

        Summary
        -------
        Downloads complete resource content into memory for processing.

        Parameters
        ----------
        storage_key : str
            Storage identifier for the resource (e.g., "extracted_xml/paper1.xml")

        Returns
        -------
        bytes
            Complete resource content as raw bytes

        Raises
        ------
        NotFoundError
            If storage_key does not exist in storage
        StorageError
            If download operation fails

        Examples
        --------
        >>> manager = get_storage_manager()
        >>> data = manager.get_resource("datasets/training.json")
        >>> text_content = data.decode('utf-8')

        Notes
        -----
        - Complexity: O(n) where n is resource size
        - Memory: Loads entire resource into memory - use download_to_path for large files
        - Performance: Consider streaming for files > 100MB
        """
        try:
            return self.client.get_resource(storage_key)
        except Exception as e:
            logger.error(f"Failed to get resource {storage_key}", error=e, source="storage_manager")
            raise

    def download_to_path(self, storage_key: str, dest_path: str) -> bool:
        """
        Download storage resource directly to local filesystem path.

        Summary
        -------
        Streams resource from storage to local file without loading into memory.

        Parameters
        ----------
        storage_key : str
            Storage identifier for the resource
        dest_path : str
            Absolute path where file will be written

        Returns
        -------
        bool
            True if download succeeded, False otherwise

        Raises
        ------
        NotFoundError
            If storage_key does not exist
        PermissionError
            If dest_path cannot be written to

        Examples
        --------
        >>> manager = get_storage_manager()
        >>> success = manager.download_to_path(
        ...     "models/tokenizer.pkl", 
        ...     "/tmp/downloaded_tokenizer.pkl"
        ... )
        >>> if success:
        ...     print("Download completed successfully")

        Notes
        -----
        - Complexity: O(n) where n is file size
        - Memory: Streaming operation - O(1) memory usage
        - Performance: Preferred for large files to avoid memory constraints
        """
        try:
            return self.client.download_to_path(storage_key, dest_path)
        except Exception as e:
            logger.error(f"Failed to download {storage_key} -> {dest_path}", error=e, source="storage_manager")
            raise

    def delete_resource(self, storage_key: str) -> bool:
        try:
            ok = self.client.delete_resource(storage_key)
            if ok:
                logger.info(f"Deleted {storage_key}", source="storage_manager")
            else:
                logger.warning(f"Not found for deletion: {storage_key}", source="storage_manager")
            return ok
        except Exception as e:
            logger.error(f"Failed to delete {storage_key}", error=e, source="storage_manager")
            raise

    def list_resources(self, folder: str = "") -> List[Dict[str, Any]]:
        try:
            return self.client.list_resources(folder)
        except Exception as e:
            logger.error(f"Failed to list resources in {folder}", error=e, source="storage_manager")
            raise

    def resource_exists(self, storage_key: str) -> bool:
        try:
            return self.client.resource_exists(storage_key)
        except Exception as e:
            logger.error(f"Failed to check exists {storage_key}", error=e, source="storage_manager")
            return False

    def get_resource_metadata(self, storage_key: str) -> Dict[str, Any]:
        try:
            return self.client.get_resource_metadata(storage_key)
        except Exception as e:
            logger.error(f"Failed to get metadata {storage_key}", error=e, source="storage_manager")
            raise

    # URL fetch
    def fetch_from_url(self, url: str, dest_storage_key: Optional[str] = None, file_type: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            return self.client.fetch_from_url(url, dest_storage_key, file_type, metadata)
        except Exception as e:
            logger.error(f"Failed to fetch url {url}", error=e, source="storage_manager")
            raise

    # Diagnostics
    def get_backend_type(self) -> str:
        return self.client.get_backend_type()

    def get_storage_info(self) -> Dict[str, Any]:
        return self.client.get_storage_info()

    def get_backend_param_spec(self) -> Dict[str, Dict[str, Any]]:
        return self.client.get_backend_param_spec()

    def get_api_overview(self) -> Dict[str, Any]:
        return {
            "methods": [
                "add_resource(storage_key, content[, metadata])",
                "get_resource(storage_key) -> bytes",
                "delete_resource(storage_key) -> bool",
                "rename_resource(old_storage_key, new_storage_key) -> bool",
                "list_resources(folder='') -> list[dict]",
                "resource_exists(storage_key) -> bool",
                "get_resource_metadata(storage_key) -> dict",
                "upload_from_path(local_path, dest_storage_key[, metadata])",
                "download_to_path(storage_key, local_dest_path) -> bool",
                "fetch_from_url(url[, dest_storage_key, file_type, metadata]) -> dict",
                "create_bucket(bucket_name) -> dict",
                "delete_bucket(bucket_name) -> bool",
                "rename_bucket(old_bucket_name, new_bucket_name) -> bool",
                "list_buckets() -> list[dict]",
                "bucket_exists(bucket_name) -> bool",
                "test_connection() -> dict",
            ],
            "strategies": ["primary", "replica", "failover", "sync"],
        }

    def test_connection(self) -> Dict[str, Any]:
        """
        Comprehensive storage system health check with strategy validation.
        
        Performs backend connectivity testing, strategy assessment, and 
        provides actionable recommendations for optimal configuration.
        """
        try:
            start_time = time.time()
            res = self.client.test_connection()
            test_duration = time.time() - start_time
            
            ok = res.get("success", False)
            strategy = res.get("strategy", "unknown")
            successful_backends = res.get("successful_backends", 0)
            total_backends = res.get("backends_tested", 0)
            
            # Enhanced logging with strategy context
            if ok:
                logger.info(
                    f"Storage connection test PASSED - {successful_backends}/{total_backends} backends healthy",
                    source="storage_manager",
                    event_type="health_check",
                    extra={
                        "strategy": strategy,
                        "test_duration_ms": round(test_duration * 1000, 2),
                        "assessment": res.get("strategy_assessment", "unknown")
                    }
                )
            else:
                logger.error(
                    f"Storage connection test FAILED - {successful_backends}/{total_backends} backends healthy",
                    source="storage_manager",
                    event_type="health_check",
                    extra={
                        "strategy": strategy,
                        "test_duration_ms": round(test_duration * 1000, 2),
                        "assessment": res.get("strategy_assessment", "unknown")
                    }
                )
            
            # Log recommendations
            recommendations = res.get("recommendations", [])
            for rec in recommendations:
                if rec.startswith("URGENT") or rec.startswith("CRITICAL"):
                    logger.error(f"Health recommendation: {rec}", source="storage_manager")
                elif rec.startswith("WARNING"):
                    logger.warning(f"Health recommendation: {rec}", source="storage_manager")
                else:
                    logger.info(f"Health recommendation: {rec}", source="storage_manager")
            
            return res
            
        except Exception as e:
            logger.error("Storage connection test failed with exception", error=e, source="storage_manager")
            return {
                "success": False, 
                "error": str(e),
                "strategy": "unknown",
                "backends_tested": 0,
                "successful_backends": 0,
                "recommendations": ["URGENT: Connection test failed - check storage configuration"]
            }

    def get_strategy_performance_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive performance and reliability report for current strategy.
        
        Provides insights into strategy effectiveness, backend utilization,
        and recommendations for optimization.
        """
        start_time = time.time()
        
        try:
            # Get current configuration
            storage_info = self.get_storage_info()
            connection_test = self.test_connection()
            
            strategy = storage_info.get("strategy", "unknown")
            backend_count = storage_info.get("backend_count", 0)
            successful_backends = connection_test.get("successful_backends", 0)
            
            # Strategy-specific performance analysis
            performance_analysis = {
                "strategy": strategy,
                "configuration_assessment": self._assess_strategy_configuration(storage_info),
                "reliability_score": self._calculate_reliability_score(successful_backends, backend_count, strategy),
                "performance_characteristics": self._get_performance_characteristics(strategy, backend_count),
                "optimization_opportunities": self._identify_optimization_opportunities(storage_info, connection_test),
                "recommended_actions": self._get_strategy_recommendations(storage_info, connection_test)
            }
            
            report_duration = time.time() - start_time
            
            return {
                "success": True,
                "timestamp": time.time(),
                "report_generation_time_ms": round(report_duration * 1000, 2),
                "storage_info": storage_info,
                "health_check": connection_test,
                "performance_analysis": performance_analysis
            }
            
        except Exception as e:
            logger.error("Failed to generate strategy performance report", error=e, source="storage_manager")
            return {
                "success": False,
                "error": str(e),
                "timestamp": time.time()
            }

    def _assess_strategy_configuration(self, storage_info: Dict[str, Any]) -> str:
        """Assess if strategy is optimally configured for current setup."""
        strategy = storage_info.get("strategy", "unknown")
        backend_count = storage_info.get("backend_count", 0)
        backend_types = set(storage_info.get("backends", []))
        
        if strategy == "primary":
            if backend_count == 1:
                return "optimal - single backend for primary strategy"
            else:
                return "suboptimal - multiple backends configured but only primary used"
        
        elif strategy == "replica":
            if backend_count >= 2 and len(backend_types) > 1:
                return "optimal - multiple backends with diverse types for redundancy"
            elif backend_count >= 2:
                return "good - multiple backends for redundancy"
            else:
                return "suboptimal - replica strategy needs multiple backends"
        
        elif strategy == "failover":
            if backend_count >= 3:
                return "optimal - robust failover chain"
            elif backend_count == 2:
                return "good - basic failover capability"
            else:
                return "suboptimal - failover strategy needs multiple backends"
        
        elif strategy == "sync":
            if backend_count == 2 and len(backend_types) > 1:
                return "optimal - dual backend sync with diverse types"
            elif backend_count > 3:
                return "concerning - high backend count may impact performance"
            elif backend_count >= 2:
                return "good - multi-backend synchronization"
            else:
                return "suboptimal - sync strategy needs multiple backends"
        
        return "unknown strategy configuration"

    def _calculate_reliability_score(self, successful_backends: int, total_backends: int, strategy: str) -> Dict[str, Any]:
        """Calculate reliability score based on strategy and backend health."""
        if total_backends == 0:
            return {"score": 0, "grade": "F", "description": "No backends configured"}
        
        health_ratio = successful_backends / total_backends
        
        if strategy == "primary":
            score = 100 if successful_backends >= 1 else 0
            grade = "A" if score >= 90 else "F"
        
        elif strategy == "replica":
            if successful_backends >= 2:
                score = min(100, 70 + (health_ratio * 30))
                grade = "A" if score >= 90 else "B" if score >= 80 else "C"
            else:
                score = 40 if successful_backends == 1 else 0
                grade = "D" if score > 0 else "F"
        
        elif strategy == "failover":
            score = min(100, 50 + (health_ratio * 50))
            if score >= 90:
                grade = "A"
            elif score >= 80:
                grade = "B"
            elif score >= 60:
                grade = "C"
            elif score >= 40:
                grade = "D"
            else:
                grade = "F"
        
        elif strategy == "sync":
            score = 100 if health_ratio == 1.0 else 25 if successful_backends > 0 else 0
            grade = "A" if score == 100 else "D" if score > 0 else "F"
        
        else:
            score = min(100, health_ratio * 100)
            grade = "C"
        
        return {
            "score": round(score, 1),
            "grade": grade,
            "description": f"{successful_backends}/{total_backends} backends healthy"
        }

    def _get_performance_characteristics(self, strategy: str, backend_count: int) -> Dict[str, str]:
        """Get expected performance characteristics for the strategy."""
        if strategy == "primary":
            return {
                "read_latency": "lowest",
                "write_latency": "lowest",
                "consistency": "immediate",
                "availability": "single point of failure",
                "scalability": "limited to single backend"
            }
        
        elif strategy == "replica":
            return {
                "read_latency": "low (distributed)",
                "write_latency": "medium (parallel writes)",
                "consistency": "eventual",
                "availability": "high (automatic failover)",
                "scalability": "excellent for reads"
            }
        
        elif strategy == "failover":
            return {
                "read_latency": "low (single backend)",
                "write_latency": "low (single backend)",
                "consistency": "immediate",
                "availability": "very high (sequential fallback)",
                "scalability": "good (automatic switching)"
            }
        
        elif strategy == "sync":
            return {
                "read_latency": "low (primary only)",
                "write_latency": f"high (requires all {backend_count} backends)",
                "consistency": "immediate",
                "availability": "lowest (requires all backends)",
                "scalability": "limited by slowest backend"
            }
        
        return {"unknown": "strategy not recognized"}

    def _identify_optimization_opportunities(self, storage_info: Dict[str, Any], connection_test: Dict[str, Any]) -> List[str]:
        """Identify specific optimization opportunities."""
        opportunities = []
        
        strategy = storage_info.get("strategy", "unknown")
        backend_count = storage_info.get("backend_count", 0)
        successful_backends = connection_test.get("successful_backends", 0)
        backend_details = connection_test.get("details", {})
        
        # Check response times
        response_times = []
        for backend_key, details in backend_details.items():
            if details.get("success") and "response_time_ms" in details:
                response_times.append(details["response_time_ms"])
        
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            
            if max_response_time > 5000:  # 5 seconds
                opportunities.append(f"Slow backend detected ({max_response_time:.0f}ms) - investigate network or backend performance")
            
            if strategy == "sync" and avg_response_time > 1000:  # 1 second
                opportunities.append("High average latency with sync strategy - consider replica strategy for better performance")
        
        # Strategy-specific opportunities
        if strategy == "primary" and backend_count > 1:
            opportunities.append("Multiple backends available but unused - consider replica or failover strategy for redundancy")
        
        if strategy == "sync" and backend_count > 3:
            opportunities.append("High backend count with sync strategy - consider reducing backends or switching to replica strategy")
        
        if successful_backends < backend_count:
            opportunities.append(f"Unhealthy backends detected ({backend_count - successful_backends} failing) - investigate and repair for optimal performance")
        
        return opportunities

    def _get_strategy_recommendations(self, storage_info: Dict[str, Any], connection_test: Dict[str, Any]) -> List[str]:
        """Get specific recommendations for strategy optimization."""
        recommendations = []
        
        strategy = storage_info.get("strategy", "unknown")
        backend_count = storage_info.get("backend_count", 0)
        successful_backends = connection_test.get("successful_backends", 0)
        
        if successful_backends < backend_count:
            recommendations.append("Priority 1: Fix failing backends to restore full redundancy")
        
        if strategy == "sync" and backend_count > 2:
            recommendations.append("Consider: Switch to 'replica' strategy for better write performance with similar redundancy")
        
        if strategy == "primary" and backend_count > 1:
            recommendations.append("Consider: Switch to 'replica' or 'failover' strategy to utilize additional backends")
        
        if backend_count == 1 and strategy != "primary":
            recommendations.append("Consider: Add more backends or switch to 'primary' strategy for current single-backend setup")
        
        if successful_backends == backend_count and backend_count >= 2:
            recommendations.append("Optimal: Current configuration is healthy and well-suited for the selected strategy")
        
        return recommendations

    # Bucket helpers
    def create_bucket(self, bucket_name: str, allow_override: bool = False) -> Dict[str, Any]:
        """
        Create storage bucket with duplication prevention.
        
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
        """
        return self.client.create_bucket(bucket_name, allow_override)

    def delete_bucket(self, bucket_name: str) -> bool:
        return self.client.delete_bucket(bucket_name)

    def list_buckets(self) -> List[Dict[str, Any]]:
        return self.client.list_buckets()

    def rename_resource(self, old_storage_key: str, new_storage_key: str) -> bool:
        """
        Rename/move resource from old storage key to new storage key.
        
        Summary
        -------
        High-level resource renaming with comprehensive logging and error handling.
        
        Parameters
        ----------
        old_storage_key : str
            Current storage key of the resource
        new_storage_key : str
            Target storage key for the resource
            
        Returns
        -------
        bool
            True if rename succeeded
            
        Examples
        --------
        >>> manager = StorageManager()
        >>> success = manager.rename_resource(
        ...     "temp/analysis.csv", 
        ...     "reports/final_analysis.csv"
        ... )
        """
        try:
            success = self.client.rename_resource(old_storage_key, new_storage_key)
            if success:
                logger.info(f"Renamed resource {old_storage_key} -> {new_storage_key}", source="storage_manager")
            else:
                logger.warning(f"Failed to rename resource {old_storage_key} -> {new_storage_key}", source="storage_manager")
            return success
        except Exception as e:
            logger.error(f"Exception renaming resource {old_storage_key} -> {new_storage_key}", error=e, source="storage_manager")
            raise

    def rename_bucket(self, old_bucket_name: str, new_bucket_name: str) -> bool:
        """
        Rename bucket from old name to new name.
        
        Summary
        -------
        High-level bucket renaming with comprehensive logging and error handling.
        
        Parameters
        ----------
        old_bucket_name : str
            Current name of the bucket  
        new_bucket_name : str
            Target name for the bucket
            
        Returns
        -------
        bool
            True if rename succeeded
            
        Examples
        --------
        >>> manager = StorageManager()
        >>> success = manager.rename_bucket("temp-data", "archived-data")
        """
        try:
            success = self.client.rename_bucket(old_bucket_name, new_bucket_name)
            if success:
                logger.info(f"Renamed bucket {old_bucket_name} -> {new_bucket_name}", source="storage_manager")
            else:
                logger.warning(f"Failed to rename bucket {old_bucket_name} -> {new_bucket_name}", source="storage_manager")
            return success
        except Exception as e:
            logger.error(f"Exception renaming bucket {old_bucket_name} -> {new_bucket_name}", error=e, source="storage_manager")
            raise

    def list_all_buckets(self) -> Dict[str, Any]:
        """
        List all buckets with comprehensive metadata and classification.
        
        Returns detailed bucket information including standard vs non-standard
        classification and backend-specific metadata.
        
        Returns
        -------
        Dict[str, Any]
            Comprehensive bucket listing with metadata and classification
            
        Examples
        --------
        >>> storage = StorageManager()
        >>> result = storage.list_all_buckets()
        >>> print(f"Total buckets: {result['total_buckets']}")
        >>> for bucket in result['standard_buckets']:
        ...     print(f"Standard: {bucket['name']} -> {bucket['logical_name']}")
        """
        from polymer_extractor.utils.paths import STORAGE_PATHS
        
        result = {
            "success": True,
            "timestamp": time.time(),
            "total_buckets": 0,
            "standard_buckets": [],
            "non_standard_buckets": [],
            "bucket_mapping": {},
            "backend_info": {}
        }
        
        try:
            # Get all buckets from storage backend
            all_buckets = self.list_buckets()
            result["total_buckets"] = len(all_buckets)
            
            # Create mapping of logical names to backend bucket names
            logical_to_backend = {}
            backend_to_logical = {}
            for logical_name in STORAGE_PATHS.keys():
                backend_name = self._normalize_bucket_name(logical_name)
                logical_to_backend[logical_name] = backend_name
                backend_to_logical[backend_name] = logical_name
                result["bucket_mapping"][logical_name] = backend_name
            
            # Classify buckets
            for bucket in all_buckets:
                bucket_name = bucket.get("name", bucket.get("$id", "unknown"))
                
                if bucket_name in backend_to_logical:
                    # This is a standard bucket
                    logical_name = backend_to_logical[bucket_name]
                    storage_path = STORAGE_PATHS[logical_name]
                    
                    standard_bucket = {
                        "name": bucket_name,
                        "logical_name": logical_name,
                        "storage_path": storage_path,
                        "is_standard": True,
                        **bucket  # Include all original bucket metadata
                    }
                    result["standard_buckets"].append(standard_bucket)
                else:
                    # This is a non-standard bucket
                    non_standard_bucket = {
                        "name": bucket_name,
                        "is_standard": False,
                        **bucket  # Include all original bucket metadata
                    }
                    result["non_standard_buckets"].append(non_standard_bucket)
            
            # Add backend information
            try:
                storage_info = self.get_storage_info()
                result["backend_info"] = storage_info
            except Exception as e:
                result["backend_info"] = {"error": f"Could not get backend info: {e}"}
            
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            self.logger.error(f"Bucket listing failed: {str(e)}", 
                            source="storage_manager", event_type="bucket_listing")
        
        return result

    def bucket_exists(self, bucket_name: str) -> bool:
        try:
            return self.client.bucket_exists(bucket_name)
        except Exception:
            return False

    # Standardized bucket management methods
    def create_standard_buckets(self) -> Dict[str, Any]:
        """
        Create all standard storage buckets based on STORAGE_PATHS configuration.
        
        Creates buckets for all logical storage types defined in paths.py,
        using backend-safe naming conventions for compatibility across storage systems.
        
        Returns
        -------
        Dict[str, Any]
            Results including created buckets, skipped buckets, and any errors
            
        Examples
        --------
        >>> storage = StorageManager()
        >>> result = storage.create_standard_buckets()
        >>> print(f"Created {len(result['created'])} buckets")
        """
        from polymer_extractor.utils.paths import STORAGE_PATHS
        
        result = {
            "success": True,
            "timestamp": time.time(),
            "buckets_created": [],
            "buckets_skipped": [],
            "buckets_failed": [],
            "errors": []
        }
        
        total_duration_start = time.time()
        
        # Debug logging for STORAGE_PATHS
        logger.info(f"Creating standard buckets from STORAGE_PATHS: {list(STORAGE_PATHS.keys())}",
                   source="storage_manager", event_type="bucket_creation")
        
        for logical_name, storage_path in STORAGE_PATHS.items():
            try:
                # Normalize bucket name for backend compatibility
                bucket_name = self._normalize_bucket_name(logical_name)
                
                logger.debug(f"Processing bucket: {logical_name} -> {bucket_name}",
                            source="storage_manager", event_type="bucket_creation")
                
                # Check if bucket should be created based on strategy and multi-backend existence
                should_create = self.client.should_create_bucket(bucket_name)
                
                if not should_create:
                    result["buckets_skipped"].append({
                        "logical_name": logical_name,
                        "backend_name": bucket_name,
                        "reason": "exists_on_all_required_backends"
                    })
                    logger.debug(f"Bucket {bucket_name} exists on all required backends, skipping",
                                source="storage_manager", event_type="bucket_creation")
                    continue
                
                # Create the bucket
                logger.debug(f"Creating bucket: {bucket_name}",
                            source="storage_manager", event_type="bucket_creation")
                create_result = self.create_bucket(bucket_name)
                
                logger.debug(f"Bucket creation result for {bucket_name}: {create_result}",
                            source="storage_manager", event_type="bucket_creation")
                
                # Check if creation was successful - handle different return formats
                success = create_result.get("success", True) if isinstance(create_result, dict) else True
                
                if success and not create_result.get("error"):
                    result["buckets_created"].append({
                        "logical_name": logical_name,
                        "backend_name": bucket_name,
                        "storage_path": storage_path,
                        "backend": self.get_backend_type(),
                        "duration": create_result.get("duration", 0) if isinstance(create_result, dict) else 0
                    })
                    logger.info(f"Successfully created bucket: {bucket_name} for {logical_name}",
                               source="storage_manager", event_type="bucket_creation")
                else:
                    error_msg = create_result.get("error", "Unknown creation error") if isinstance(create_result, dict) else "Unknown error format"
                    result["buckets_failed"].append({
                        "logical_name": logical_name,
                        "backend_name": bucket_name,
                        "error": error_msg
                    })
                    result["errors"].append(f"Failed to create {bucket_name}: {error_msg}")
                    logger.error(f"Failed to create bucket {bucket_name}: {error_msg}",
                                source="storage_manager", event_type="bucket_creation")
                    
            except Exception as e:
                error_msg = f"Exception creating bucket for {logical_name}: {str(e)}"
                result["buckets_failed"].append({
                    "logical_name": logical_name,
                    "backend_name": bucket_name if 'bucket_name' in locals() else "unknown",
                    "error": error_msg
                })
                result["errors"].append(error_msg)
                logger.error(error_msg, source="storage_manager", event_type="bucket_creation")
        
        # Set overall success based on whether any failures occurred
        result["success"] = len(result["buckets_failed"]) == 0
        result["total_duration"] = time.time() - total_duration_start
        
        return result

    def validate_bucket_structure(self) -> Dict[str, Any]:
        """
        Validate that all required buckets exist according to STORAGE_PATHS.
        
        Returns
        -------
        Dict[str, Any]
            Validation results with missing buckets and recommendations
            
        Examples
        --------
        >>> storage = StorageManager()
        >>> result = storage.validate_bucket_structure()
        >>> if not result['valid']: print("Missing buckets!")
        """
        from polymer_extractor.utils.paths import STORAGE_PATHS
        
        result = {
            "success": True,
            "timestamp": time.time(),
            "valid": True,
            "total_required": len(STORAGE_PATHS),
            "total_found": 0,
            "missing_buckets": [],
            "extra_buckets": [],
            "standard_buckets_found": 0,
            "recommendations": []
        }
        
        try:
            # Get all existing buckets
            existing_buckets = self.list_buckets()
            existing_bucket_names = [bucket.get("name", bucket.get("$id", "unknown")) for bucket in existing_buckets]
            
            # Check for required buckets
            required_bucket_names = set()
            for logical_name in STORAGE_PATHS.keys():
                bucket_name = self._normalize_bucket_name(logical_name)
                required_bucket_names.add(bucket_name)
                
                if bucket_name in existing_bucket_names:
                    result["standard_buckets_found"] += 1
                else:
                    result["missing_buckets"].append({
                        "logical_name": logical_name,
                        "backend_name": bucket_name
                    })
            
            result["total_found"] = len(existing_bucket_names)
            
            # Check for extra buckets
            for bucket_name in existing_bucket_names:
                if bucket_name not in required_bucket_names:
                    result["extra_buckets"].append(bucket_name)
            
            # Determine if structure is valid
            result["valid"] = len(result["missing_buckets"]) == 0
            
            # Generate recommendations
            if result["missing_buckets"]:
                result["recommendations"].append(f"Missing {len(result['missing_buckets'])} required buckets - run create_standard_buckets()")
            
            if result["extra_buckets"]:
                extra_limited = result["extra_buckets"][:3]  # Show first 3
                extra_text = ", ".join(extra_limited)
                if len(result["extra_buckets"]) > 3:
                    extra_text += f", and {len(result['extra_buckets']) - 3} more"
                result["recommendations"].append(f"Consider removing non-standard buckets: {extra_text}")
            
            if result["valid"]:
                result["recommendations"].append("Bucket structure is valid and complete")
            
        except Exception as e:
            result["success"] = False
            result["valid"] = False
            result["error"] = str(e)
            self.logger.error(f"Bucket validation failed: {str(e)}", 
                            source="storage_manager", event_type="bucket_validation")
        
        return result

    def recreate_all_buckets(self) -> Dict[str, Any]:
        """
        Recreate all standard buckets (delete existing and create fresh).
        
        Warning: This will remove all existing buckets and their contents!
        Only use during clean installs or when explicitly requested.
        
        Returns
        -------
        Dict[str, Any]
            Results of deletion and recreation operations
            
        Examples
        --------
        >>> storage = StorageManager()
        >>> result = storage.recreate_all_buckets()  # DANGEROUS!
        >>> print(f"Recreated {len(result['created'])} buckets")
        """
        result = {
            "success": False,
            "timestamp": time.time(),
            "deleted": [],
            "created": [],
            "errors": []
        }
        
        try:
            # First, delete all existing buckets
            existing_buckets = self.list_buckets()
            for bucket in existing_buckets:
                bucket_name = bucket.get("name", bucket.get("$id", "unknown"))
                try:
                    if self.delete_bucket(bucket_name):
                        result["deleted"].append(bucket_name)
                        self.logger.info(f"Deleted bucket: {bucket_name}",
                                       source="storage_manager", event_type="bucket_recreation")
                    else:
                        result["errors"].append(f"Failed to delete bucket: {bucket_name}")
                except Exception as e:
                    result["errors"].append(f"Exception deleting {bucket_name}: {str(e)}")
            
            # Then create all standard buckets
            creation_result = self.create_standard_buckets()
            result["created"] = creation_result.get("buckets_created", [])
            result["errors"].extend(creation_result.get("errors", []))
            
            result["success"] = len(result["errors"]) == 0
            
        except Exception as e:
            result["errors"].append(f"Recreation failed: {str(e)}")
            result["success"] = False
            self.logger.error(f"Bucket recreation failed: {str(e)}", 
                            source="storage_manager", event_type="bucket_recreation")
        
        return result

    def _normalize_bucket_name(self, logical_name: str) -> str:
        """
        Normalize logical storage name to backend-safe bucket name.
        
        Converts underscore-separated logical names to hyphen-separated
        bucket names for compatibility across storage backends.
        
        Parameters
        ----------
        logical_name : str
            Logical storage name from STORAGE_PATHS (e.g., "raw_inputs")
            
        Returns
        -------
        str
            Backend-safe bucket name (e.g., "raw_inputs" -> "raw-inputs")
        """
        return logical_name.replace("_", "-")

    # Strategy-aware operations
    def get_current_strategy(self) -> str:
        """Get the current storage strategy."""
        return self.client.strategy
    
    def get_backend_count(self) -> int:
        """Get the number of configured storage backends."""
        return len(self.client.backends)
    
    def is_multi_backend_mode(self) -> bool:
        """Check if current strategy affects multiple backends."""
        return self.client.strategy in ["replica", "sync", "failover"] and len(self.client.backends) > 1
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """
        Get comprehensive information about current strategy and backend configuration.
        
        Returns
        -------
        Dict[str, Any]
            Strategy information including:
            - strategy: Current routing strategy
            - backend_count: Number of configured backends
            - backend_types: List of backend types
            - affects_all_backends: Whether operations affect all backends
            - read_behavior: How read operations are handled
            - write_behavior: How write operations are handled
        """
        strategy = self.client.strategy
        backend_count = len(self.client.backends)
        backend_types = [type(b).__name__.replace("StorageBackend", "").lower() for b in self.client.backends]
        
        if strategy == "primary":
            read_behavior = "Primary backend only"
            write_behavior = "Primary backend only"
            affects_all = False
        elif strategy == "replica":
            read_behavior = "Aggregates from all backends for lists, primary-first for single values"
            write_behavior = "Writes to all backends (best effort)"
            affects_all = True
        elif strategy == "failover":
            read_behavior = "Aggregates from all backends for lists, failover order for single values"
            write_behavior = "Failover order (first successful)"
            affects_all = True
        elif strategy == "sync":
            read_behavior = "Aggregates from all backends for lists, checks all for existence"
            write_behavior = "Writes to ALL backends (must succeed on all)"
            affects_all = True
        else:
            read_behavior = "Unknown strategy"
            write_behavior = "Unknown strategy"
            affects_all = False
        
        return {
            "strategy": strategy,
            "backend_count": backend_count,
            "backend_types": backend_types,
            "affects_all_backends": affects_all,
            "read_behavior": read_behavior,
            "write_behavior": write_behavior,
            "multi_backend_mode": self.is_multi_backend_mode()
        }

    # Back-compat (file-centric names)
    upload_file = add_resource
    download_file = get_resource
    delete_file = delete_resource
    list_files = list_resources
    file_exists = resource_exists
    get_file_metadata = get_resource_metadata


# Factory

def get_storage_manager() -> StorageManager:
    return StorageManager()
