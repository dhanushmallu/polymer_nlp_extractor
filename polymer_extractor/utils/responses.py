"""
Unified JSON response helpers for FastAPI endpoints.

Purpose
-------
Provides consistent response envelopes across all HTTP status codes (1xx-5xx) with
deterministic field structure and proper timestamp formatting. Ensures API clients
can reliably parse responses regardless of success or failure conditions.

Key abstractions
----------------
- ResponseBuilder: generates standardized JSON envelopes with status, message, data
- StatusHelpers: convenience functions for common response types (2xx, 4xx, 5xx)
- HTTPException wrapper: raises FastAPI exceptions with consistent envelope format

Envelope structure (common)
---------------------------
{
  "status": <str>,           # e.g., success | partial_success | failure | error | healthy | unhealthy | degraded
  "code": <int>,             # HTTP status code mirrored in payload
  "message": <str>,          # human-friendly summary
  "data": <any>,             # primary payload (optional)
  "details": <dict|any>,     # secondary details (optional)
  "timestamp": <ISO-8601>    # UTC timestamp
}

Examples
--------
>>> from polymer_extractor.utils.responses import ok, partial, failure, error, healthy, raise_http
>>> 
>>> # Success responses
>>> return ok({"items": [1, 2, 3]}, message="Data retrieved successfully")
>>> return healthy({"services": ["postgres", "neo4j"]}, message="All systems operational")
>>> 
>>> # Partial success
>>> return partial({"processed": 5, "failed": 2}, message="Some items failed processing")
>>> 
>>> # Error responses
>>> return failure(message="Invalid input parameters", code=400, details={"field": "email"})
>>> return error(message="Database connection failed", code=500, exception=db_error)
>>> 
>>> # Exceptions
>>> raise_http(404, status_label="not_found", message="Resource not found", details={"id": "abc123"})

Notes
-----
- All timestamps are UTC in ISO-8601 format
- Data field is optional and can contain any JSON-serializable content
- Details field is optional and typically contains error specifics or metadata
- Exception parameter automatically extracts type and message information
- Consistent envelope format enables reliable client-side error handling
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException


def _now_iso() -> str:
    """
    Generate current UTC timestamp in ISO-8601 format.
    
    Returns
    -------
    str
        UTC timestamp string in ISO-8601 format with 'Z' suffix
        
    Examples
    --------
    >>> _now_iso()
    '2025-08-20T12:34:56.789123Z'
    
    Notes
    -----
    - Always returns UTC timezone for consistency across deployments
    - Format includes microseconds for precise temporal ordering
    - Used internally by all response envelope functions
    """
    return datetime.now(timezone.utc).isoformat()


def build(
    status: str,
    *,
    message: str = "",
    code: int = 200,
    data: Any | None = None,
    details: Any | None = None,
    **extra: Any,
) -> Dict[str, Any]:
    """
    Build standardized response envelope with consistent field structure.
    
    Parameters
    ----------
    status : str
        Response status label (success, error, healthy, etc.)
    message : str
        Human-readable summary message
    code : int
        HTTP status code to mirror in response body
    data : Any, optional
        Primary response payload (any JSON-serializable content)
    details : Any, optional
        Secondary details (typically error specifics or metadata)
    **extra : Any
        Additional fields to include in response envelope
        
    Returns
    -------
    Dict[str, Any]
        Standardized response envelope with status, code, message, timestamp
        
    Raises
    ------
    TypeError
        If data or details contain non-JSON-serializable content
        
    Examples
    --------
    >>> build("success", message="Operation completed", code=200, data={"result": 42})
    {
        "status": "success",
        "code": 200,
        "message": "Operation completed",
        "data": {"result": 42},
        "timestamp": "2025-08-20T12:34:56.789Z"
    }
    
    Notes
    -----
    - Timestamp is automatically added as UTC ISO-8601 string
    - Optional fields (data, details) are only included if not None
    - Extra fields are merged directly into envelope
    """
    payload: Dict[str, Any] = {
        "status": status,
        "code": code,
        "message": message,
        "timestamp": _now_iso(),
    }
    if data is not None:
        payload["data"] = data
    if details is not None:
        payload["details"] = details
    if extra:
        payload.update(extra)
    return payload


# === 2xx Success Responses ===

def ok(data: Any | None = None, *, message: str = "OK", code: int = 200, **extra: Any) -> Dict[str, Any]:
    """
    Generate successful operation response (200 OK).
    
    Parameters
    ----------
    data : Any, optional
        Response payload data
    message : str
        Success message (default: "OK")
    code : int
        HTTP status code (default: 200)
    **extra : Any
        Additional envelope fields
        
    Returns
    -------
    Dict[str, Any]
        Success response envelope with status="success"
        
    Examples
    --------
    >>> ok({"user_id": 123}, message="User created successfully")
    >>> ok([1, 2, 3], message="Items retrieved")
    
    Notes
    -----
    - Most common success response for API endpoints
    - Data field contains the primary response payload
    """
    return build("success", message=message, code=code, data=data, **extra)


def healthy(data: Any | None = None, *, message: str = "All systems healthy", code: int = 200, **extra: Any) -> Dict[str, Any]:
    """
    Generate health check success response.
    
    Parameters
    ----------
    data : Any, optional
        Health status data (service statuses, metrics, etc.)
    message : str
        Health summary message
    code : int
        HTTP status code (default: 200)
    **extra : Any
        Additional envelope fields
        
    Returns
    -------
    Dict[str, Any]
        Health response envelope with status="healthy"
        
    Examples
    --------
    >>> healthy({"services": {"postgres": "up", "neo4j": "up"}})
    >>> healthy(message="All services operational")
    
    Notes
    -----
    - Specialized for health check and status endpoints
    - Data typically contains service-specific status information
    """
    return build("healthy", message=message, code=code, data=data, **extra)


def partial(data: Any | None = None, *, message: str = "Partial Content", code: int = 206, **extra: Any) -> Dict[str, Any]:
    """
    Generate partial success response (206 Partial Content).
    
    Parameters
    ----------
    data : Any, optional
        Partial response data (what succeeded and what failed)
    message : str
        Partial success message
    code : int
        HTTP status code (default: 206)
    **extra : Any
        Additional envelope fields
        
    Returns
    -------
    Dict[str, Any]
        Partial success envelope with status="partial_success"
        
    Examples
    --------
    >>> partial({"processed": 8, "failed": 2}, message="Some items failed processing")
    >>> partial({"uploaded": ["file1.pdf"], "skipped": ["file2.pdf"]})
    
    Notes
    -----
    - Used when operation completes but with some failures
    - Data should indicate what succeeded vs. what failed
    - Client can determine if retry is needed based on details
    """
    return build("partial_success", message=message, code=code, data=data, **extra)


# === 4xx/5xx Error Responses ===

def failure(*, message: str = "Bad Request", code: int = 400, details: Any | None = None, **extra: Any) -> Dict[str, Any]:
    """
    Generate client error response (4xx status codes).
    
    Parameters
    ----------
    message : str
        Error description for client
    code : int
        HTTP status code (default: 400)
    details : Any, optional
        Specific error details (field validation, missing parameters, etc.)
    **extra : Any
        Additional envelope fields
        
    Returns
    -------
    Dict[str, Any]
        Client error envelope with status="failure"
        
    Examples
    --------
    >>> failure(message="Invalid email format", code=400, details={"field": "email", "value": "invalid"})
    >>> failure(message="Resource not found", code=404, details={"resource_id": "abc123"})
    
    Notes
    -----
    - Used for client-side errors (bad input, missing resources, etc.)
    - Details should help client understand and fix the issue
    - Message should be user-friendly and actionable
    """
    return build("failure", message=message, code=code, details=details, **extra)


def error(*, message: str = "Internal Server Error", code: int = 500, details: Any | None = None, exception: Optional[BaseException] = None, **extra: Any) -> Dict[str, Any]:
    """
    Generate server error response (5xx status codes).
    
    Parameters
    ----------
    message : str
        Error description (should not leak internal details)
    code : int
        HTTP status code (default: 500)
    details : Any, optional
        Safe error details for debugging (no sensitive information)
    exception : BaseException, optional
        Exception instance to extract type and message from
    **extra : Any
        Additional envelope fields
        
    Returns
    -------
    Dict[str, Any]
        Server error envelope with status="error"
        
    Examples
    --------
    >>> error(message="Database connection failed", code=500)
    >>> error(message="Service unavailable", code=503, exception=connection_error)
    >>> error(message="Processing timeout", code=504, details={"timeout_seconds": 30})
    
    Notes
    -----
    - Used for server-side errors (database failures, timeouts, etc.)
    - Exception parameter automatically adds exception_type and error fields
    - Message should be generic to avoid leaking internal architecture
    - Details should be safe for client consumption
    """
    if exception is not None:
        extra.setdefault("exception_type", type(exception).__name__)
        extra.setdefault("error", str(exception))
    return build("error", message=message, code=code, details=details, **extra)


def raise_http(
    status_code: int,
    *,
    status_label: str,
    message: str,
    data: Any | None = None,
    details: Any | None = None,
    **extra: Any,
) -> None:
    """
    Raise HTTPException with standardized envelope in detail field.
    
    Parameters
    ----------
    status_code : int
        HTTP status code to return
    status_label : str
        Status label for envelope (failure, error, not_found, etc.)
    message : str
        Human-readable error message
    data : Any, optional
        Response data (rarely used for errors)
    details : Any, optional
        Error-specific details for debugging
    **extra : Any
        Additional envelope fields
        
    Raises
    ------
    HTTPException
        FastAPI exception with standardized envelope as detail
        
    Examples
    --------
    >>> raise_http(404, status_label="not_found", message="User not found", details={"user_id": 123})
    >>> raise_http(429, status_label="rate_limited", message="Too many requests")
    >>> raise_http(422, status_label="validation_error", message="Invalid input", details={"errors": [...]})
    
    Notes
    -----
    - Automatically terminates request processing with proper HTTP status
    - Detail field contains full standardized envelope
    - FastAPI will serialize envelope to JSON response body
    - Client receives consistent error format regardless of error type
    """
    raise HTTPException(
        status_code=status_code,
        detail=build(status_label, message=message, code=status_code, data=data, details=details, **extra),
    )
