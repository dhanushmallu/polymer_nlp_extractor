# polymer_extractor/api/setup.py

"""
Setup API for Polymer NLP Extractor

Purpose
-------
FastAPI router providing direct access to SetupService methods for system orchestration.
All endpoints map directly to setup service operations without authentication requirements.

Core Endpoints
--------------
POST /setup/initialize -> Initialize missing/corrupted components
POST /setup/reset -> Reset components with data removal but preserve structure  
POST /setup/wipe-data -> Remove all data while preserving schemas/structure
GET /setup/health -> Comprehensive system health validation
GET /setup/status -> Current system status and configuration
GET /setup/environment -> Environment configuration information

Component Management
--------------------
POST /setup/database/initialize -> PostgreSQL setup and recovery
POST /setup/graph/initialize -> Neo4j setup and recovery
POST /setup/storage/initialize -> Multi-backend storage setup
POST /setup/storage/create-buckets -> Create standardized storage buckets

Examples
--------
# Health check
curl -X GET http://localhost:8000/api/setup/health

# Initialize system
curl -X POST http://localhost:8000/api/setup/initialize \
  -H "Content-Type: application/json" \
  -d '{"clean_install": false, "preserve_logs": true}'

# Reset specific components
curl -X POST http://localhost:8000/api/setup/reset \
  -H "Content-Type: application/json" \
  -d '{"components": ["database", "storage"], "preserve_structure": true}'

Notes
-----
- Direct mapping to SetupService methods without authentication
- All operations return detailed status and error information
- Safe defaults for all destructive operations
- Comprehensive logging for all operations
"""
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from polymer_extractor.services.setup_service import SetupService
from polymer_extractor.utils.logging import get_logger

logger = get_logger()
router = APIRouter(prefix="/setup", tags=["setup"])

# =============================================================================
# REQUEST MODELS
# =============================================================================

class InitializeRequest(BaseModel):
    """Request model for system initialization."""
    clean_install: bool = Field(False, description="If True, recreate all components even if they exist")
    preserve_logs: bool = Field(True, description="If True, preserve existing logs during initialization")

class ResetRequest(BaseModel):
    """Request model for system reset."""
    components: Optional[List[str]] = Field(None, description="Components to reset: ['database', 'graph', 'storage']")
    preserve_structure: bool = Field(True, description="If True, keep schemas/constraints/directories")

class WipeDataRequest(BaseModel):
    """Request model for data wiping."""
    preserve_structure: bool = Field(True, description="If True, keep schemas/constraints/directories")
    confirm_wipe: bool = Field(False, description="Explicit confirmation required for data wipe")

class InitializeDatabaseRequest(BaseModel):
    """Request model for database initialization."""
    clean_install: bool = Field(False, description="If True, drop and recreate all tables")
    preserve_logs: bool = Field(True, description="If True, preserve existing logs during reset")

class InitializeGraphRequest(BaseModel):
    """Request model for graph initialization."""
    clean_install: bool = Field(False, description="If True, drop existing constraints and recreate")

class InitializeStorageRequest(BaseModel):
    """Request model for storage initialization."""
    clean_install: bool = Field(False, description="If True, recreate storage structure")

# =============================================================================
# CORE LIFECYCLE ENDPOINTS
# =============================================================================

@router.post("/initialize")
async def initialize_system(request: InitializeRequest) -> Dict[str, Any]:
    """
    Safe initialization of missing or corrupted system components.
    
    This endpoint performs comprehensive system initialization by checking each component
    and initializing only those that are missing or corrupted. Safe to run multiple times.
    
    Parameters
    ----------
    request : InitializeRequest
        Initialization configuration
        
    Returns
    -------
    Dict[str, Any]
        Operation results with component status
    """
    start_time = time.time()
    
    logger.info(
        "Setup API: Initialize system request",
        source="setup_api",
        event_type="operation_start",
        extra={
            "clean_install": request.clean_install,
            "preserve_logs": request.preserve_logs
        }
    )
    
    try:
        setup_service = SetupService()
        result = setup_service.initialize(
            clean_install=request.clean_install,
            preserve_logs=request.preserve_logs
        )
        
        duration = time.time() - start_time
        
        if result.get("success", False):
            logger.info(
                "Setup API: Initialize system completed successfully",
                source="setup_api",
                event_type="operation_complete",
                extra={
                    "duration_seconds": round(duration, 2),
                    "components_processed": len(result.get("components", {}))
                }
            )
        else:
            logger.warning(
                "Setup API: Initialize system completed with warnings",
                source="setup_api",
                event_type="operation_warning",
                extra={
                    "duration_seconds": round(duration, 2),
                    "warnings_count": len(result.get("warnings", []))
                }
            )
        
        # Add operation metadata
        result["operation_metadata"] = {
            "duration_seconds": round(duration, 2),
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": "/setup/initialize"
        }
        
        return result
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Initialize system failed: {str(e)}"
        
        logger.error(
            error_msg,
            source="setup_api",
            event_type="operation_failed",
            extra={
                "duration_seconds": round(duration, 2),
                "exception": str(e)
            }
        )
        
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/reset")
async def reset_system(request: ResetRequest) -> Dict[str, Any]:
    """
    Reset specified components by removing data while preserving structure.
    
    This operation safely resets system components by clearing data while maintaining
    database schemas, graph constraints, and directory structures.
    
    Parameters
    ----------
    request : ResetRequest
        Reset configuration
        
    Returns
    -------
    Dict[str, Any]
        Operation results with component status
    """
    start_time = time.time()
    
    logger.info(
        "Setup API: Reset system request",
        source="setup_api",
        event_type="operation_start",
        extra={
            "components": request.components,
            "preserve_structure": request.preserve_structure
        }
    )
    
    try:
        setup_service = SetupService()
        result = setup_service.reset(
            components=request.components,
            preserve_structure=request.preserve_structure
        )
        
        duration = time.time() - start_time
        
        if result.get("success", False):
            logger.info(
                "Setup API: Reset system completed successfully",
                source="setup_api",
                event_type="operation_complete",
                extra={
                    "duration_seconds": round(duration, 2),
                    "components_reset": result.get("components_reset", [])
                }
            )
        else:
            logger.error(
                "Setup API: Reset system completed with errors",
                source="setup_api",
                event_type="operation_error",
                extra={
                    "duration_seconds": round(duration, 2),
                    "warnings_count": len(result.get("warnings", []))
                }
            )
        
        # Add operation metadata
        result["operation_metadata"] = {
            "duration_seconds": round(duration, 2),
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": "/setup/reset"
        }
        
        return result
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Reset system failed: {str(e)}"
        
        logger.error(
            error_msg,
            source="setup_api",
            event_type="operation_failed",
            extra={
                "duration_seconds": round(duration, 2),
                "exception": str(e)
            }
        )
        
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/wipe-data")
async def wipe_data(request: WipeDataRequest) -> Dict[str, Any]:
    """
    Remove all data while preserving schemas and structure.
    
    WARNING: This operation removes all data across all components. 
    Requires explicit confirmation for safety.
    
    Parameters
    ----------
    request : WipeDataRequest
        Wipe configuration with confirmation
        
    Returns
    -------
    Dict[str, Any]
        Operation results with affected components
    """
    if not request.confirm_wipe:
        raise HTTPException(
            status_code=400,
            detail="Data wipe operation requires explicit confirmation via confirm_wipe=true"
        )
    
    start_time = time.time()
    
    logger.warning(
        "Setup API: Wipe data request - DATA WILL BE DELETED",
        source="setup_api",
        event_type="operation_start",
        extra={
            "preserve_structure": request.preserve_structure
        }
    )
    
    try:
        setup_service = SetupService()
        result = setup_service.wipe_data(
            preserve_structure=request.preserve_structure,
            confirm_wipe=request.confirm_wipe
        )
        
        duration = time.time() - start_time
        
        if result.get("success", False):
            logger.warning(
                "Setup API: Wipe data completed successfully - DATA DELETED",
                source="setup_api",
                event_type="operation_complete",
                extra={
                    "duration_seconds": round(duration, 2),
                    "components_affected": result.get("components_affected", [])
                }
            )
        else:
            logger.error(
                "Setup API: Wipe data completed with errors",
                source="setup_api",
                event_type="operation_error",
                extra={
                    "duration_seconds": round(duration, 2),
                    "warnings_count": len(result.get("warnings", []))
                }
            )
        
        # Add operation metadata
        result["operation_metadata"] = {
            "duration_seconds": round(duration, 2),
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": "/setup/wipe-data"
        }
        
        return result
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Wipe data failed: {str(e)}"
        
        logger.error(
            error_msg,
            source="setup_api",
            event_type="operation_failed",
            extra={
                "duration_seconds": round(duration, 2),
                "exception": str(e)
            }
        )
        
        raise HTTPException(status_code=500, detail=error_msg)

# =============================================================================
# MONITORING ENDPOINTS (PUBLIC)
# =============================================================================

@router.get("/health")
async def get_system_health() -> Dict[str, Any]:
    """
    Comprehensive system health check.
    
    This endpoint provides detailed health information for all system components
    including PostgreSQL, Neo4j, storage backends, and overall system status.
    
    Returns
    -------
    Dict[str, Any]
        Comprehensive health status
    """
    try:
        setup_service = SetupService()
        result = setup_service.check_health()
        
        logger.debug(
            "Setup API: Health check completed",
            source="setup_api",
            event_type="health_check",
            extra={
                "overall_status": result.get("overall_status", "unknown"),
                "services_healthy": len([s for s in result.get("services", {}).values() if s.get("status") == "healthy"])
            }
        )
        
        return result
        
    except Exception as e:
        error_msg = f"Health check failed: {str(e)}"
        
        logger.error(
            error_msg,
            source="setup_api",
            event_type="health_check_failed",
            extra={"exception": str(e)}
        )
        
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/status")
async def get_system_status() -> Dict[str, Any]:
    """
    Get comprehensive system status and configuration information.
    
    This endpoint provides detailed status including environment configuration,
    health information, and component details.
    
    Returns
    -------
    Dict[str, Any]
        Comprehensive system status
    """
    try:
        setup_service = SetupService()
        result = setup_service.get_status()
        
        logger.debug(
            "Setup API: Status check completed",
            source="setup_api",
            event_type="status_check"
        )
        
        return result
        
    except Exception as e:
        error_msg = f"Status check failed: {str(e)}"
        
        logger.error(
            error_msg,
            source="setup_api",
            event_type="status_check_failed",
            extra={"exception": str(e)}
        )
        
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/environment")
async def get_environment_info() -> Dict[str, Any]:
    """
    Get environment configuration information.
    
    This endpoint provides detailed information about the current environment
    configuration including enabled services, storage backends, and key paths.
    
    Returns
    -------
    Dict[str, Any]
        Environment configuration details
    """
    try:
        setup_service = SetupService()
        result = setup_service.get_environment_info()
        
        logger.debug(
            "Setup API: Environment info retrieved",
            source="setup_api",
            event_type="environment_info"
        )
        
        return result
        
    except Exception as e:
        error_msg = f"Environment info failed: {str(e)}"
        
        logger.error(
            error_msg,
            source="setup_api",
            event_type="environment_info_failed",
            extra={"exception": str(e)}
        )
        
        raise HTTPException(status_code=500, detail=error_msg)

# =============================================================================
# COMPONENT MANAGEMENT ENDPOINTS
# =============================================================================

@router.post("/database/initialize")
async def initialize_database(request: InitializeDatabaseRequest) -> Dict[str, Any]:
    """
    Initialize PostgreSQL database with essential tables and indexes.
    
    This endpoint sets up PostgreSQL database infrastructure including core tables
    for metadata storage, paper management, and system operations.
    
    Parameters
    ----------
    request : InitializeDatabaseRequest
        Database initialization configuration
        
    Returns
    -------
    Dict[str, Any]
        Database initialization results
    """
    start_time = time.time()
    
    logger.info(
        "Setup API: Initialize database request",
        source="setup_api",
        event_type="operation_start",
        extra={
            "clean_install": request.clean_install,
            "preserve_logs": request.preserve_logs
        }
    )
    
    try:
        setup_service = SetupService()
        result = setup_service.initialize_database(
            clean_install=request.clean_install,
            preserve_logs=request.preserve_logs
        )
        
        duration = time.time() - start_time
        
        # Add operation metadata
        result["operation_metadata"] = {
            "duration_seconds": round(duration, 2),
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": "/setup/database/initialize"
        }
        
        logger.info(
            "Setup API: Initialize database completed",
            source="setup_api",
            event_type="operation_complete",
            extra={
                "duration_seconds": round(duration, 2),
                "success": result.get("success", False)
            }
        )
        
        return result
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Initialize database failed: {str(e)}"
        
        logger.error(
            error_msg,
            source="setup_api",
            event_type="operation_failed",
            extra={
                "duration_seconds": round(duration, 2),
                "exception": str(e)
            }
        )
        
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/graph/initialize")
async def initialize_graph(request: InitializeGraphRequest) -> Dict[str, Any]:
    """
    Initialize Neo4j graph database with constraints and indexes.
    
    This endpoint sets up Neo4j graph database infrastructure including constraints
    for data integrity and indexes for query performance.
    
    Parameters
    ----------
    request : InitializeGraphRequest
        Graph initialization configuration
        
    Returns
    -------
    Dict[str, Any]
        Graph initialization results
    """
    start_time = time.time()
    
    logger.info(
        "Setup API: Initialize graph request",
        source="setup_api",
        event_type="operation_start",
        extra={
            "clean_install": request.clean_install
        }
    )
    
    try:
        setup_service = SetupService()
        result = setup_service.initialize_graph(
            clean_install=request.clean_install
        )
        
        duration = time.time() - start_time
        
        # Add operation metadata
        result["operation_metadata"] = {
            "duration_seconds": round(duration, 2),
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": "/setup/graph/initialize"
        }
        
        logger.info(
            "Setup API: Initialize graph completed",
            source="setup_api",
            event_type="operation_complete",
            extra={
                "duration_seconds": round(duration, 2),
                "success": result.get("success", False)
            }
        )
        
        return result
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Initialize graph failed: {str(e)}"
        
        logger.error(
            error_msg,
            source="setup_api",
            event_type="operation_failed",
            extra={
                "duration_seconds": round(duration, 2),
                "exception": str(e)
            }
        )
        
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/storage/initialize")
async def initialize_storage(request: InitializeStorageRequest) -> Dict[str, Any]:
    """
    Initialize multi-backend storage with standardized bucket structure.
    
    This endpoint sets up storage infrastructure across all configured backends
    and creates the standardized bucket structure for the application.
    
    Parameters
    ----------
    request : InitializeStorageRequest
        Storage initialization configuration
        
    Returns
    -------
    Dict[str, Any]
        Storage initialization results
    """
    start_time = time.time()
    
    logger.info(
        "Setup API: Initialize storage request",
        source="setup_api",
        event_type="operation_start",
        extra={
            "clean_install": request.clean_install
        }
    )
    
    try:
        setup_service = SetupService()
        result = setup_service.initialize_storage(
            clean_install=request.clean_install
        )
        
        duration = time.time() - start_time
        
        # Add operation metadata
        result["operation_metadata"] = {
            "duration_seconds": round(duration, 2),
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": "/setup/storage/initialize"
        }
        
        logger.info(
            "Setup API: Initialize storage completed",
            source="setup_api",
            event_type="operation_complete",
            extra={
                "duration_seconds": round(duration, 2),
                "success": result.get("success", False)
            }
        )
        
        return result
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Initialize storage failed: {str(e)}"
        
        logger.error(
            error_msg,
            source="setup_api",
            event_type="operation_failed",
            extra={
                "duration_seconds": round(duration, 2),
                "exception": str(e)
            }
        )
        
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/storage/create-buckets")
async def create_standard_buckets() -> Dict[str, Any]:
    """
    Create standardized storage buckets across all backends.
    
    This endpoint creates all required storage buckets using the standardized
    naming conventions and structure for the application.
    
    Returns
    -------
    Dict[str, Any]
        Bucket creation results
    """
    start_time = time.time()
    
    logger.info(
        "Setup API: Create standard buckets request",
        source="setup_api",
        event_type="operation_start"
    )
    
    try:
        setup_service = SetupService()
        result = setup_service.create_standard_buckets()
        
        duration = time.time() - start_time
        
        # Add operation metadata
        result["operation_metadata"] = {
            "duration_seconds": round(duration, 2),
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": "/setup/storage/create-buckets"
        }
        
        logger.info(
            "Setup API: Create standard buckets completed",
            source="setup_api",
            event_type="operation_complete",
            extra={
                "duration_seconds": round(duration, 2),
                "success": result.get("success", False)
            }
        )
        
        return result
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Create standard buckets failed: {str(e)}"
        
        logger.error(
            error_msg,
            source="setup_api",
            event_type="operation_failed",
            extra={
                "duration_seconds": round(duration, 2),
                "exception": str(e)
            }
        )
        
        raise HTTPException(status_code=500, detail=error_msg)
