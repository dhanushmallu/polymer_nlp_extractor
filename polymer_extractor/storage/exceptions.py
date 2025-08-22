"""
polymer_extractor/storage/exceptions.py

Storage-specific exception classes for the Polymer NLP Extractor.

Purpose
-------
Provides lightweight, backend-agnostic exception hierarchy for storage operations.
These exceptions abstract away backend-specific error types to provide a consistent
error handling interface across local, Appwrite, and S3 storage backends.

Key Abstractions
----------------
- StorageError: Base exception for all storage-related failures
- ConfigError: Configuration validation and environment setup issues
- NotFoundError: Resource (file/bucket) not found in storage
- BackendOperationError: Backend-specific operation failures

Design Invariants
-----------------
- No backend-specific types leak through these exceptions
- Clear error categorization for appropriate error handling
- Minimal hierarchy to avoid over-engineering

Examples
--------
>>> from polymer_extractor.storage.exceptions import NotFoundError, ConfigError
>>> try:
...     storage.get_resource("nonexistent.txt")
... except NotFoundError as e:
...     logger.warning(f"Resource not found: {e}")
>>> 
>>> try:
...     storage_client = StorageClient()
... except ConfigError as e:
...     logger.error(f"Storage misconfiguration: {e}")

Notes
-----
- Performance: O(1) - Exception classes have no computational overhead
- Thread Safety: Exception instances are immutable and thread-safe
- Error Context: Use exception chaining (raise ... from e) to preserve backend details when needed
"""

from __future__ import annotations


class StorageError(Exception):
    """
    Base class for storage-related errors.
    
    Summary
    -------
    Root exception for all storage operation failures across backends.
    
    Parameters
    ----------
    message : str
        Human-readable error description
    
    Examples
    --------
    >>> raise StorageError("Failed to connect to storage backend")
    
    Notes
    -----
    - Use specific subclasses when possible for better error handling
    - Safe to catch broadly for storage-related error recovery
    """


class ConfigError(StorageError):
    """
    Misconfiguration or missing/invalid environment settings.
    
    Summary
    -------
    Raised when storage backend configuration is invalid or incomplete.
    
    Parameters
    ----------
    message : str
        Description of the configuration issue
        
    Examples
    --------
    >>> if not os.getenv("S3_ACCESS_KEY_ID"):
    ...     raise ConfigError("S3_ACCESS_KEY_ID environment variable required")
    
    Notes
    -----
    - Typically raised during client initialization
    - Indicates setup/deployment issue, not runtime failure
    """


class NotFoundError(StorageError):
    """
    Requested resource (file/bucket) was not found in storage.
    
    Summary
    -------
    Raised when attempting to access a non-existent storage resource.
    
    Parameters
    ----------
    message : str
        Description of what resource was not found
        
    Examples
    --------
    >>> try:
    ...     content = storage.get_resource("missing-file.txt")
    ... except NotFoundError:
    ...     logger.info("File not found, using default content")
    
    Notes
    -----
    - Distinguishes "not found" from other storage failures
    - Safe to catch for optional resource handling
    """


class BackendOperationError(StorageError):
    """
    A concrete backend failed to perform an operation.
    
    Summary
    -------
    Raised when a storage backend encounters an operational failure.
    
    Parameters
    ----------
    message : str
        Description of the backend operation that failed
        
    Examples
    --------
    >>> try:
    ...     storage.upload_file(large_file)
    ... except BackendOperationError as e:
    ...     logger.error(f"Upload failed: {e}")
    ...     # Retry with different backend or smaller chunks
    
    Notes
    -----
    - May indicate transient issues (network, permissions, quota)
    - Consider retry logic or backend failover when catching
    """
