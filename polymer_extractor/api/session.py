"""
polymer_extractor/api/session.py

Session Management API for Polymer NLP Extractor

Purpose
-------
FastAPI router providing session management endpoints for multi-user workflows.
Handles user session creation, management, monitoring, and cleanup operations
with proper UUID handling and resource allocation.

Core Endpoints
--------------
POST /session/create -> Create new user session with resource allocation
GET /session/{session_id} -> Get session details and status
GET /session/user/{user_id} -> List sessions for a user
DELETE /session/{session_id} -> Terminate session and cleanup resources
GET /session/{session_id}/health -> Get session health and resource usage

User Management
---------------
POST /session/user/create -> Create new user account
GET /session/user/{user_id}/info -> Get user information and quotas
GET /session/users -> List all users (admin only)

Examples
--------
# Create a user session
curl -X POST http://localhost:8000/api/session/create \
  -H "Content-Type: application/json" \
  -d '{"user_id": "researcher_123", "session_name": "polymer_analysis_batch_1"}'

# Get session status  
curl -X GET http://localhost:8000/api/session/{session_id}

Notes
-----
- All session operations require valid user_id and proper authentication
- Sessions automatically expire based on configured timeout
- Resource allocation is managed automatically based on requirements
- UUID format is enforced for all session and user identifiers
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, validator

from polymer_extractor.storage.session_manager import SessionManager, get_session_manager, SessionError
from polymer_extractor.repositories.session_repository import SessionRepository
from polymer_extractor.utils.logging import get_logger

logger = get_logger()
router = APIRouter(prefix="/session", tags=["session"])

# =============================================================================
# REQUEST MODELS
# =============================================================================

class CreateUserRequest(BaseModel):
    """Request model for creating a new user."""
    user_id: str = Field(..., description="Unique external user identifier")
    username: str = Field(..., description="Human-readable username")
    email: Optional[str] = Field(None, description="User email address")
    display_name: Optional[str] = Field(None, description="Display name for UI")
    organization: Optional[str] = Field(None, description="User's organization")
    user_role: str = Field("researcher", description="User role (admin, researcher, guest)")
    storage_quota_gb: float = Field(10.0, description="Storage quota in GB")
    max_concurrent_sessions: int = Field(3, description="Maximum concurrent sessions")

class CreateSessionRequest(BaseModel):
    """Request model for creating a new session."""
    user_id: str = Field(..., description="User identifier for session owner")
    session_name: str = Field(..., description="Descriptive name for the session")
    resource_requirements: Optional[Dict[str, Any]] = Field(
        None, description="Resource allocation requirements"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional session metadata"
    )
    expires_in_minutes: int = Field(60, description="Session expiration time in minutes")

class SessionResponse(BaseModel):
    """Response model for session information."""
    session_id: str
    user_id: str
    session_name: str
    status: str
    storage_prefix: Optional[str]
    created_at: str
    expires_at: Optional[str]
    last_activity: str

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_session_manager_instance() -> SessionManager:
    """Get session manager instance with error handling."""
    try:
        return get_session_manager()
    except Exception as e:
        logger.error("Failed to get session manager", source="session_api", error=str(e))
        raise HTTPException(status_code=500, detail="Session management not available")

def get_session_repository_instance() -> SessionRepository:
    """Get session repository instance with error handling."""
    try:
        return SessionRepository()
    except Exception as e:
        logger.error("Failed to get session repository", source="session_api", error=str(e))
        raise HTTPException(status_code=500, detail="Session repository not available")

# =============================================================================
# USER MANAGEMENT ENDPOINTS
# =============================================================================

@router.post("/user/create")
async def create_user(request: CreateUserRequest) -> Dict[str, Any]:
    """
    Create a new user account for session management.
    
    This endpoint creates a new user with specified quotas and permissions.
    Required before creating sessions for the user.
    
    Parameters
    ----------
    request : CreateUserRequest
        User creation configuration
        
    Returns
    -------
    Dict[str, Any]
        Created user information
    """
    start_time = time.time()
    
    logger.info(
        "Session API: Create user request",
        source="session_api",
        event_type="user_creation_start",
        extra={"user_id": request.user_id, "username": request.username}
    )
    
    try:
        session_repository = get_session_repository_instance()
        
        user = session_repository.create_user(
            user_id=request.user_id,
            username=request.username,
            email=request.email,
            display_name=request.display_name,
            organization=request.organization,
            user_role=request.user_role,
            storage_quota_gb=request.storage_quota_gb,
            max_concurrent_sessions=request.max_concurrent_sessions
        )
        
        duration = time.time() - start_time
        
        logger.info(
            "Session API: User created successfully",
            source="session_api",
            event_type="user_creation_complete",
            extra={
                "user_id": request.user_id,
                "duration_seconds": round(duration, 2)
            }
        )
        
        return {
            "success": True,
            "status": "ok",
            "data": user,
            "operation_metadata": {
                "duration_seconds": round(duration, 2),
                "timestamp": datetime.utcnow().isoformat(),
                "endpoint": "/session/user/create"
            }
        }
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Create user failed: {str(e)}"
        
        logger.error(
            error_msg,
            source="session_api",
            event_type="user_creation_failed",
            extra={
                "user_id": request.user_id,
                "duration_seconds": round(duration, 2),
                "exception": str(e)
            }
        )
        
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/user/{user_id}/info")
async def get_user_info(user_id: str) -> Dict[str, Any]:
    """
    Get user information including quotas and session statistics.
    
    Parameters
    ----------
    user_id : str
        User identifier
        
    Returns
    -------
    Dict[str, Any]
        User information and statistics
    """
    try:
        session_repository = get_session_repository_instance()
        
        # Get user basic info
        user_sessions = session_repository.list_user_sessions(user_id)
        
        # Get user metrics
        active_sessions = len([s for s in user_sessions if s.get("status") in ["active", "processing", "idle"]])
        
        return {
            "success": True,
            "status": "ok", 
            "data": {
                "user_id": user_id,
                "active_sessions": active_sessions,
                "total_sessions": len(user_sessions),
                "recent_sessions": user_sessions[:5]  # Last 5 sessions
            }
        }
        
    except Exception as e:
        logger.error(f"Get user info failed", source="session_api", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Get user info failed: {str(e)}")

# =============================================================================
# SESSION MANAGEMENT ENDPOINTS
# =============================================================================

@router.post("/create")
async def create_session(request: CreateSessionRequest) -> Dict[str, Any]:
    """
    Create a new user session with resource allocation.
    
    This endpoint creates a session with proper UUID format and resource management.
    Returns session UUID that can be used with other APIs.
    
    Parameters
    ----------
    request : CreateSessionRequest
        Session creation configuration
        
    Returns
    -------
    Dict[str, Any]
        Created session information with UUID
    """
    start_time = time.time()
    
    logger.info(
        "Session API: Create session request",
        source="session_api", 
        event_type="session_creation_start",
        extra={
            "user_id": request.user_id,
            "session_name": request.session_name
        }
    )
    
    try:
        session_manager = get_session_manager_instance()
        
        # Create session using session manager
        session = session_manager.create_session(
            user_id=request.user_id,
            session_name=request.session_name,
            metadata=request.metadata
        )
        
        duration = time.time() - start_time
        
        response_data = {
            "session_id": str(session.id),
            "user_id": session.user_id,
            "session_name": session.session_name,
            "status": session.status.value,
            "storage_prefix": session.storage_prefix,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat() if session.expires_at else None,
            "last_activity": session.last_activity.isoformat()
        }
        
        logger.info(
            "Session API: Session created successfully",
            source="session_api",
            event_type="session_creation_complete", 
            extra={
                "session_id": str(session.id),
                "user_id": request.user_id,
                "duration_seconds": round(duration, 2)
            }
        )
        
        return {
            "success": True,
            "status": "ok",
            "data": response_data,
            "operation_metadata": {
                "duration_seconds": round(duration, 2),
                "timestamp": datetime.utcnow().isoformat(),
                "endpoint": "/session/create"
            }
        }
        
    except SessionError as e:
        duration = time.time() - start_time
        logger.error(
            f"Session creation failed: {str(e)}",
            source="session_api",
            event_type="session_creation_failed",
            extra={
                "user_id": request.user_id,
                "duration_seconds": round(duration, 2),
                "session_error": str(e)
            }
        )
        raise HTTPException(status_code=400, detail=f"Session creation failed: {str(e)}")
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Create session failed: {str(e)}"
        
        logger.error(
            error_msg,
            source="session_api",
            event_type="session_creation_error",
            extra={
                "user_id": request.user_id,
                "duration_seconds": round(duration, 2),
                "exception": str(e)
            }
        )
        
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/{session_id}")
async def get_session(session_id: str) -> Dict[str, Any]:
    """
    Get session details and current status.
    
    Parameters
    ----------
    session_id : str
        Session UUID to retrieve
        
    Returns
    -------
    Dict[str, Any]
        Session information and status
    """
    try:
        session_manager = get_session_manager_instance()
        
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        response_data = {
            "session_id": str(session.id),
            "user_id": session.user_id,
            "session_name": session.session_name,
            "status": session.status.value,
            "storage_prefix": session.storage_prefix,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat() if session.expires_at else None,
            "last_activity": session.last_activity.isoformat(),
            "resource_requirements": session.resource_requirements.__dict__ if session.resource_requirements else None,
            "allocated_resources": session.allocated_resources
        }
        
        return {
            "success": True,
            "status": "ok",
            "data": response_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get session failed", source="session_api", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Get session failed: {str(e)}")

@router.get("/user/{user_id}")
async def list_user_sessions(user_id: str, status_filter: Optional[str] = Query(None)) -> Dict[str, Any]:
    """
    List sessions for a specific user.
    
    Parameters
    ----------
    user_id : str
        User identifier
    status_filter : str, optional
        Filter sessions by status (active, processing, completed, etc.)
        
    Returns
    -------
    Dict[str, Any]
        List of user sessions
    """
    try:
        session_manager = get_session_manager_instance()
        
        sessions = session_manager.list_user_sessions(user_id)
        
        # Apply status filter if provided
        if status_filter:
            sessions = [s for s in sessions if s.status.value == status_filter]
        
        response_data = []
        for session in sessions:
            response_data.append({
                "session_id": str(session.id),
                "user_id": session.user_id,
                "session_name": session.session_name,
                "status": session.status.value,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat()
            })
        
        return {
            "success": True,
            "status": "ok", 
            "data": {
                "user_id": user_id,
                "sessions": response_data,
                "total_count": len(response_data),
                "status_filter": status_filter
            }
        }
        
    except Exception as e:
        logger.error(f"List user sessions failed", source="session_api", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"List user sessions failed: {str(e)}")

@router.delete("/{session_id}")
async def terminate_session(session_id: str, save_results: bool = Query(True)) -> Dict[str, Any]:
    """
    Terminate session and cleanup resources.
    
    Parameters
    ----------
    session_id : str
        Session UUID to terminate
    save_results : bool, default True
        Whether to save session results before termination
        
    Returns
    -------
    Dict[str, Any]
        Termination result
    """
    start_time = time.time()
    
    try:
        session_manager = get_session_manager_instance()
        
        success = session_manager.terminate_session(session_id, save_results=save_results)
        
        duration = time.time() - start_time
        
        if success:
            logger.info(
                "Session terminated successfully",
                source="session_api",
                event_type="session_termination_complete",
                extra={
                    "session_id": session_id,
                    "save_results": save_results,
                    "duration_seconds": round(duration, 2)
                }
            )
            
            return {
                "success": True,
                "status": "ok",
                "data": {
                    "session_id": session_id,
                    "terminated": True,
                    "results_saved": save_results
                },
                "operation_metadata": {
                    "duration_seconds": round(duration, 2),
                    "timestamp": datetime.utcnow().isoformat(),
                    "endpoint": f"/session/{session_id}"
                }
            }
        else:
            raise HTTPException(status_code=404, detail="Session not found or already terminated")
            
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"Session termination failed",
            source="session_api",
            event_type="session_termination_failed",
            extra={
                "session_id": session_id,
                "duration_seconds": round(duration, 2),
                "exception": str(e)
            }
        )
        raise HTTPException(status_code=500, detail=f"Session termination failed: {str(e)}")

@router.get("/{session_id}/health")
async def get_session_health(session_id: str) -> Dict[str, Any]:
    """
    Get session health status and resource usage.
    
    Parameters
    ----------
    session_id : str
        Session UUID to check
        
    Returns
    -------
    Dict[str, Any]
        Session health information
    """
    try:
        session_manager = get_session_manager_instance()
        
        health = session_manager.get_session_health(session_id)
        
        return {
            "success": True,
            "status": "ok",
            "data": health
        }
        
    except Exception as e:
        logger.error(f"Get session health failed", source="session_api", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Get session health failed: {str(e)}")

# =============================================================================
# SYSTEM MONITORING ENDPOINTS
# =============================================================================

@router.get("/system/status")
async def get_system_status() -> Dict[str, Any]:
    """
    Get overall session management system status.
    
    Returns
    -------
    Dict[str, Any]
        System status and statistics
    """
    try:
        session_manager = get_session_manager_instance()
        
        # Get system resource utilization
        resource_utilization = session_manager.get_resource_utilization()
        
        return {
            "success": True,
            "status": "ok",
            "data": {
                "session_management_available": True,
                "resource_utilization": resource_utilization,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Get system status failed", source="session_api", error=str(e))
        raise HTTPException(status_code=500, detail=f"Get system status failed: {str(e)}")