# polymer_extractor/api/setup.py

from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from polymer_extractor.services.setup_service import SetupService
from polymer_extractor.storage.bucket_manager import BucketManager
from polymer_extractor.utils.logging import Logger

router = APIRouter()
logger = Logger()
setup = SetupService()
bucket_manager = BucketManager()

# === Pydantic Models for Request/Response ===
class ResetOptions(BaseModel):
    """Options for database reset operations"""
    postgres: bool = True
    neo4j: bool = True
    appwrite: bool = True
    preserve_logs: bool = True

class CleanInstallRequest(BaseModel):
    """Request model for clean installation"""
    databases: Optional[List[str]] = None
    preserve_logs: bool = False

class ServiceAction(BaseModel):
    """Request model for service actions"""
    services: Optional[List[str]] = None  # ["postgres", "neo4j"] or None for all

# === Enhanced Setup Endpoints (Phase E Implementation) ===

@router.post("/setup/initialize")
async def initialize_system():
    """
    Initialize complete database system based on .env.example configuration.
    
    This endpoint orchestrates the initialization of all enabled databases:
    - PostgreSQL: Schema deployment and table verification
    - Neo4j: Constraints deployment and graph readiness
    - Appwrite: Collection setup with PostgreSQL compatibility
    
    Environment routing based on USE_POSTGRESQL_DB, USE_NEO4J_DB, USE_APPWRITE_DB flags.
    
    Returns
    -------
    Dict[str, Any]
        Comprehensive initialization results with per-database status
    """
    try:
        logger.info("Starting system initialization via API", source="setup_api", event_type="initialize_start")
        
        result = setup.initialize_system()
        
        if result.get("success", False):
            logger.info("System initialization completed successfully", 
                       source="setup_api", event_type="initialize_success",
                       context={"execution_time": result.get("execution_time_seconds", 0)})
            return {
                "status": "success",
                "message": "Database system initialized successfully",
                "details": result
            }
        else:
            logger.warning("System initialization completed with issues",
                          source="setup_api", event_type="initialize_partial",
                          context={"errors": result.get("errors", [])})
            return {
                "status": "partial_success", 
                "message": "System initialization completed with some issues",
                "details": result
            }
            
    except Exception as e:
        logger.error(f"System initialization failed: {e}", source="setup_api", event_type="initialize_error")
        # Return structured error response instead of raising HTTPException
        return {
            "status": "error",
            "message": f"Failed to initialize system: {str(e)}",
            "details": {
                "success": False,
                "operation": "initialize_system",
                "timestamp": datetime.now().isoformat() + "Z",
                "error": str(e),
                "exception_type": type(e).__name__,
                "execution_time_seconds": 0
            }
        }

@router.post("/setup/reset")
async def reset_databases(options: Optional[ResetOptions] = None):
    """
    Reset databases with granular options.
    
    Performs controlled database reset with configurable scope:
    - postgres: Reset PostgreSQL database (drop/recreate tables)
    - neo4j: Reset Neo4j database (delete all nodes/relationships)
    - appwrite: Reset Appwrite collections (delete/recreate collections)
    - preserve_logs: Preserve logging tables/collections during reset
    
    Reset operations ignore .env flags - always reset if database exists.
    
    Parameters
    ----------
    options : ResetOptions, optional
        Reset configuration options
        
    Returns
    -------
    Dict[str, Any]
        Results of reset operations per database
    """
    try:
        if options is None:
            options = ResetOptions()
            
        logger.info("Starting database reset via API", source="setup_api", event_type="reset_start",
                   context={"options": options.dict()})
        
        reset_options = {
            "postgres": options.postgres,
            "neo4j": options.neo4j,
            "appwrite": options.appwrite,
            "preserve_logs": options.preserve_logs
        }
        
        result = setup.reset_all_databases(reset_options)
        
        success_count = result.get("summary", {}).get("reset_databases", 0)
        total_count = result.get("summary", {}).get("total_databases", 0)
        
        if success_count == total_count and total_count > 0:
            logger.info(f"Database reset completed successfully: {success_count}/{total_count}",
                       source="setup_api", event_type="reset_success")
            return {
                "status": "success",
                "message": f"Successfully reset {success_count} databases",
                "details": result
            }
        elif success_count > 0:
            logger.warning(f"Database reset partially successful: {success_count}/{total_count}",
                          source="setup_api", event_type="reset_partial")
            return {
                "status": "partial_success",
                "message": f"Reset {success_count} of {total_count} databases",
                "details": result
            }
        else:
            logger.error("Database reset failed for all databases", source="setup_api", event_type="reset_failed")
            return {
                "status": "failure",
                "message": "Failed to reset any databases",
                "details": result
            }
            
    except Exception as e:
        logger.error(f"Database reset operation failed: {e}", source="setup_api", event_type="reset_error")
        # Return structured error response instead of raising HTTPException
        return {
            "status": "error",
            "message": f"Failed to reset databases: {str(e)}",
            "details": {
                "success": False,
                "operation": "reset_all_databases",
                "timestamp": datetime.now().isoformat() + "Z",
                "error": str(e),
                "exception_type": type(e).__name__,
                "execution_time_seconds": 0
            }
        }

@router.post("/setup/clean-install")
async def clean_install(request: Optional[CleanInstallRequest] = None):
    """
    Perform clean installation of specified databases.
    
    Complete clean installation process:
    1. Stop all services (graceful shutdown)
    2. Reset databases (complete wipe including schema)
    3. Reinitialize based on .env.example flags
    4. Health verification and startup validation
    
    Parameters
    ----------
    request : CleanInstallRequest, optional
        Clean install configuration
        
    Returns
    -------
    Dict[str, Any]
        Results of clean installation process
    """
    try:
        if request is None:
            request = CleanInstallRequest()
            
        databases = request.databases or ["postgres", "neo4j", "appwrite"]
        
        logger.info("Starting clean installation via API", source="setup_api", event_type="clean_install_start",
                   context={"databases": databases, "preserve_logs": request.preserve_logs})
        
        result = setup.clean_install(preserve_logs=request.preserve_logs)
        
        if result.get("success", False):
            logger.info("Clean installation completed successfully", 
                       source="setup_api", event_type="clean_install_success",
                       context={"execution_time": result.get("execution_time_seconds", 0)})
            return {
                "status": "success",
                "message": "Clean installation completed successfully",
                "details": result
            }
        else:
            logger.error("Clean installation failed", source="setup_api", event_type="clean_install_failed",
                        context={"error": result.get("error"), "phases": result.get("phases", {})})
            return {
                "status": "failure", 
                "message": "Clean installation failed",
                "details": result
            }
            
    except Exception as e:
        logger.error(f"Clean installation operation failed: {e}", source="setup_api", event_type="clean_install_error")
        # Return structured error response instead of raising HTTPException
        return {
            "status": "error",
            "message": f"Failed to perform clean installation: {str(e)}",
            "details": {
                "success": False,
                "operation": "clean_install",
                "timestamp": datetime.now().isoformat() + "Z",
                "error": str(e),
                "exception_type": type(e).__name__,
                "execution_time_seconds": 0
            }
        }

@router.get("/setup/health")
async def health_check_all():
    """
    Health check all configured databases per .env.example flags.
    
    Comprehensive health assessment:
    - PostgreSQL: Service status, connection health, table verification
    - Neo4j: Service status, connection health, constraint verification  
    - Appwrite: Connection health, collection verification
    - Managers: Database manager and graph manager availability
    
    Returns
    -------
    Dict[str, Any]
        Comprehensive health status of all database systems
    """
    try:
        logger.info("Starting health check via API", source="setup_api", event_type="health_check_start")
        
        result = setup.health_check_all()
        
        overall_health = result.get("overall_health", "unknown")
        healthy_count = result.get("summary", {}).get("healthy_databases", 0)
        total_count = result.get("summary", {}).get("total_databases", 0)
        
        if overall_health == "healthy":
            logger.info(f"Health check passed: {healthy_count}/{total_count} databases healthy",
                       source="setup_api", event_type="health_check_success")
            return {
                "status": "healthy",
                "message": f"All {healthy_count} configured databases are healthy",
                "details": result
            }
        elif overall_health == "partial":
            logger.warning(f"Health check partial: {healthy_count}/{total_count} databases healthy",
                          source="setup_api", event_type="health_check_partial")
            return {
                "status": "partial",
                "message": f"{healthy_count} of {total_count} databases are healthy",
                "details": result
            }
        else:
            logger.error(f"Health check failed: {healthy_count}/{total_count} databases healthy",
                        source="setup_api", event_type="health_check_failed")
            return {
                "status": "unhealthy",
                "message": f"Only {healthy_count} of {total_count} databases are healthy",
                "details": result
            }
            
    except Exception as e:
        logger.error(f"Health check operation failed: {e}", source="setup_api", event_type="health_check_error")
        # Return structured error response instead of raising HTTPException
        return {
            "status": "error",
            "message": f"Failed to perform health check: {str(e)}",
            "details": {
                "success": False,
                "operation": "health_check_all",
                "timestamp": datetime.now().isoformat() + "Z",
                "error": str(e),
                "exception_type": type(e).__name__,
                "execution_time_seconds": 0
            }
        }

@router.post("/setup/services/start")
async def start_all_services(action: Optional[ServiceAction] = None):
    """
    Start all database services based on enabled flags.
    
    Service startup based on environment configuration:
    - PostgreSQL: Start via system service manager (systemctl/brew)
    - Neo4j: Start via system service manager or Docker container
    - Appwrite: Cloud-based service (no local startup required)
    
    Parameters
    ----------
    action : ServiceAction, optional
        Service action configuration
        
    Returns
    -------
    Dict[str, Any]
        Results of starting all configured database services
    """
    try:
        if action is None:
            action = ServiceAction()
            
        logger.info("Starting database services via API", source="setup_api", event_type="services_start",
                   context={"requested_services": action.services})
        
        result = setup.start_all_services()
        
        started_count = result.get("summary", {}).get("started_services", 0)
        total_count = result.get("summary", {}).get("total_services", 0)
        
        if started_count > 0:
            logger.info(f"Service startup completed: {started_count}/{total_count} services started",
                       source="setup_api", event_type="services_start_success")
            return {
                "status": "success",
                "message": f"Started {started_count} of {total_count} services",
                "details": result
            }
        else:
            logger.warning("No services were started", source="setup_api", event_type="services_start_none")
            return {
                "status": "no_action",
                "message": "No services required starting or none are configured",
                "details": result
            }
            
    except Exception as e:
        logger.error(f"Service startup operation failed: {e}", source="setup_api", event_type="services_start_error")
        raise HTTPException(status_code=500, detail=f"Failed to start services: {str(e)}")

@router.post("/setup/services/stop")
async def stop_all_services(action: Optional[ServiceAction] = None):
    """
    Stop all database services.
    
    Graceful shutdown of all configured database services:
    - PostgreSQL: Stop via system service manager
    - Neo4j: Stop via system service manager or Docker container
    - Appwrite: Cloud-based service (no local shutdown required)
    
    Parameters
    ----------
    action : ServiceAction, optional
        Service action configuration
        
    Returns
    -------
    Dict[str, Any]
        Results of stopping all database services
    """
    try:
        if action is None:
            action = ServiceAction()
            
        logger.info("Stopping database services via API", source="setup_api", event_type="services_stop",
                   context={"requested_services": action.services})
        
        result = setup.stop_all_services()
        
        stopped_count = result.get("summary", {}).get("stopped_services", 0)
        total_count = result.get("summary", {}).get("total_services", 0)
        
        if stopped_count > 0 or total_count == 0:
            logger.info(f"Service shutdown completed: {stopped_count}/{total_count} services stopped",
                       source="setup_api", event_type="services_stop_success")
            return {
                "status": "success",
                "message": f"Stopped {stopped_count} services" if stopped_count > 0 else "No services were running",
                "details": result
            }
        else:
            logger.error("Failed to stop any services", source="setup_api", event_type="services_stop_failed")
            raise HTTPException(status_code=500, detail="Failed to stop any services")
            
    except Exception as e:
        logger.error(f"Service shutdown operation failed: {e}", source="setup_api", event_type="services_stop_error")
        raise HTTPException(status_code=500, detail=f"Failed to stop services: {str(e)}")

@router.post("/setup/services/restart")
async def restart_all_services(action: Optional[ServiceAction] = None):
    """
    Restart all database services.
    
    Graceful restart of all configured database services:
    1. Stop all services (with 2-second grace period)
    2. Start all services based on environment configuration
    3. Verify successful restart and health status
    
    Parameters
    ----------
    action : ServiceAction, optional
        Service action configuration
        
    Returns
    -------
    Dict[str, Any]
        Results of restarting all database services
    """
    try:
        if action is None:
            action = ServiceAction()
            
        logger.info("Restarting database services via API", source="setup_api", event_type="services_restart",
                   context={"requested_services": action.services})
        
        result = setup.restart_all_services()
        
        restarted_count = result.get("summary", {}).get("restarted_services", 0)
        total_count = result.get("summary", {}).get("total_services", 0)
        
        if restarted_count > 0:
            logger.info(f"Service restart completed: {restarted_count}/{total_count} services restarted",
                       source="setup_api", event_type="services_restart_success")
            return {
                "status": "success",
                "message": f"Restarted {restarted_count} of {total_count} services",
                "details": result
            }
        else:
            logger.warning("No services were restarted", source="setup_api", event_type="services_restart_none")
            return {
                "status": "no_action", 
                "message": "No services required restarting or none are configured",
                "details": result
            }
            
    except Exception as e:
        logger.error(f"Service restart operation failed: {e}", source="setup_api", event_type="services_restart_error")
        raise HTTPException(status_code=500, detail=f"Failed to restart services: {str(e)}")

# === Legacy Compatibility Endpoints ===

@router.get("/setup/analyze")
def analyze_system():
    """
    Legacy compatibility: Analyze current Appwrite resources.
    
    Returns
    -------
    dict
        Summary of existing collections and buckets
    """
    try:
        collections = setup.list_collections()
        buckets = bucket_manager.list_buckets()
        logger.info("System analysis performed successfully", source="setup_api",
                    event_type="analyze_system")
        return {
            "collections": [col.get('$id', str(col)) for col in collections],
            "buckets": [bkt.get('$id', str(bkt)) for bkt in buckets]
        }
    except Exception as e:
        logger.error(f"Failed to analyze system: {e}", source="setup_api", event_type="analyze_error")
        raise HTTPException(status_code=500, detail="Failed to analyze system")

@router.post("/setup/init")
def initialize_resources():
    """
    Legacy compatibility: Initialize resources with intelligent setup.
    
    Maps to the new /setup/initialize endpoint for backward compatibility.
    
    Returns
    -------
    dict
        Initialization results
    """
    try:
        result = setup.initialize_system()
        
        logger.info("Resources initialized via legacy endpoint", source="setup_api", 
                   event_type="init_resources_legacy")
        
        return {
            "status": "success", 
            "message": "All project resources initialized successfully",
            "setup_details": result
        }
    except Exception as e:
        logger.error(f"Failed to initialize resources via legacy endpoint: {e}", 
                    source="setup_api", event_type="init_error_legacy")
        raise HTTPException(status_code=500, detail="Failed to initialize resources")

# === Database-Specific Endpoints ===

@router.post("/setup/databases/postgres")
async def setup_postgres():
    """
    Setup PostgreSQL database specifically.
    
    Dedicated PostgreSQL setup including:
    - Service status check and startup if needed
    - Schema deployment from db/sql/001_core.sql
    - Table verification against model_updates/database_migration.md requirements
    
    Returns
    -------
    Dict[str, Any]
        PostgreSQL setup results
    """
    try:
        logger.info("Starting PostgreSQL setup via API", source="setup_api", event_type="postgres_setup_start")
        
        result = setup.setup_postgres()
        
        if result.get("success", False):
            logger.info("PostgreSQL setup completed successfully", source="setup_api", event_type="postgres_setup_success")
            return {
                "status": "success",
                "message": "PostgreSQL database setup completed successfully",
                "details": result
            }
        else:
            logger.error("PostgreSQL setup failed", source="setup_api", event_type="postgres_setup_failed")
            raise HTTPException(status_code=500, detail="PostgreSQL setup failed")
            
    except Exception as e:
        logger.error(f"PostgreSQL setup operation failed: {e}", source="setup_api", event_type="postgres_setup_error")
        raise HTTPException(status_code=500, detail=f"Failed to setup PostgreSQL: {str(e)}")

# === Legacy Compatibility Endpoints ===

@router.get("/setup/analyze")
def analyze_system():
    """
    Legacy compatibility: Analyze current Appwrite resources.
    
    Returns
    -------
    dict
        Summary of existing collections and buckets
    """
    try:
        collections = setup.list_collections()
        buckets = bucket_manager.list_buckets()
        logger.info("System analysis performed successfully", source="setup_api", event_type="analyze_system")
        return {
            "collections": [col.get('$id', str(col)) for col in collections],
            "buckets": [bkt.get('$id', str(bkt)) for bkt in buckets]
        }
    except Exception as e:
        logger.error(f"Failed to analyze system: {e}", source="setup_api", event_type="analyze_error")
        raise HTTPException(status_code=500, detail="Failed to analyze system")

@router.post("/setup/init")
def initialize_resources():
    """
    Legacy compatibility: Initialize resources with intelligent setup.
    
    Maps to the new /setup/initialize endpoint for backward compatibility.
    
    Returns
    -------
    dict
        Initialization results
    """
    try:
        result = setup.initialize_system()
        
        logger.info("Resources initialized via legacy endpoint", source="setup_api", event_type="init_resources_legacy")
        
        return {
            "status": "success", 
            "message": "All project resources initialized successfully",
            "setup_details": result
        }
    except Exception as e:
        logger.error(f"Failed to initialize resources via legacy endpoint: {e}", 
                    source="setup_api", event_type="init_error_legacy")
        raise HTTPException(status_code=500, detail="Failed to initialize resources")
