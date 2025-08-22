"""
Polymer NLP Extractor Utilities Package.

Purpose
-------
Centralized utility modules providing core functionality for path resolution,
logging, response formatting, and service utilities across the Polymer NLP
Extractor application. This package enforces consistent patterns for file
handling, error reporting, and API responses.

Key abstractions
----------------
- paths: Authoritative path resolution between storage keys and filesystem locations
- logging: Independent logging system with PostgreSQL integration and deduplication
- responses: Standardized JSON response envelopes for FastAPI endpoints
- service_utils: Common service patterns and utilities (if present)

Examples
--------
>>> from polymer_extractor.utils.paths import get_storage_path, path_resolver
>>> from polymer_extractor.utils.logging import get_logger
>>> from polymer_extractor.utils.responses import ok, error
>>> 
>>> # Path operations
>>> storage_key = get_storage_path('reports', 'analysis.csv')
>>> local_path = path_resolver.to_local_path(storage_key)
>>> 
>>> # Logging
>>> logger = get_logger()
>>> logger.info("Operation completed", source="example_service")
>>> 
>>> # API responses
>>> return ok(data={"result": "success"}, message="Operation completed")

Notes
-----
- All path operations should use paths.py to ensure portability
- Use logging.py for all application logging needs
- API endpoints should use responses.py for consistent formatting
- Avoid circular imports between utility modules
"""

# Main exports for convenience
from .paths import get_storage_path, path_resolver
from .logging import get_logger
from .responses import ok, error, partial, healthy, failure

__all__ = [
    "get_storage_path",
    "path_resolver", 
    "get_logger",
    "ok",
    "error", 
    "partial",
    "healthy",
    "failure"
]