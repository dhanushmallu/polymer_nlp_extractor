"""
polymer_extractor/services/setup_service.py

Setup Service for Polymer NLP Extractor - Complete System Orchestration.

Purpose
-------
Production-ready system orchestration service providing comprehensive lifecycle management
for PostgreSQL, Neo4j, multi-backend storage, and multi-user session management with safe 
initialization, health monitoring, and data management operations aligned with server.sh commands.

Core Operations (Aligned with server.sh)
----------------------------------------
System Lifecycle:
- initialize() -> Safe initialization of missing/corrupted components
- reset() -> Reset components with data removal but preserve structure
- clean() -> Clean shutdown with data preservation
- wipe_data() -> Remove all data while preserving schemas/structure

Health & Monitoring:
- check_health() -> Comprehensive system health validation
- get_status() -> Current system status and configuration
- check_storage_health() -> Multi-backend storage validation
- get_session_management_status() -> Session management status and statistics

Component Management:
- initialize_database() -> PostgreSQL setup and recovery
- initialize_session_management() -> Multi-user session tables and constraints
- initialize_graph() -> Neo4j setup and recovery  
- initialize_storage() -> Multi-backend storage setup
- create_buckets() -> Create standardized storage buckets
- validate_buckets() -> Validate bucket structure

Bucket Management:
- create_standard_buckets() -> Create all standard buckets
- validate_bucket_structure() -> Validate required buckets exist
- list_all_buckets() -> List buckets across all backends

Session Management Integration:
- Initializes multi-user session tables during database setup
- Handles session management component dependencies
- Provides session management health monitoring
- Ensures proper component ordering to avoid circular dependencies

Examples
--------
>>> from polymer_extractor.services.setup_service import SetupService
>>> setup = SetupService()
>>> 
>>> # Initialize missing/corrupted components (includes session management)
>>> result = setup.initialize()
>>> print(f"Success: {result['success']}, Components: {list(result['components'].keys())}")
>>> 
>>> # Check session management status
>>> session_status = setup.get_session_management_status()
>>> print(f"Session management enabled: {session_status['enabled']}")
>>> 
>>> # Reset system data (preserves structure)
>>> reset_result = setup.reset(components=['database', 'storage'])
>>> 
>>> # Health monitoring (includes session management)
>>> health = setup.check_health()
>>> print(f"Overall: {health['overall_status']}, Services: {health['services']}")
>>> 
>>> # Wipe all data but keep schemas
>>> wipe_result = setup.wipe_data(preserve_structure=True)

Notes
-----
- Method names aligned with server.sh command structure
- Consistent parameter patterns across all methods
- Production-safe defaults with comprehensive validation
- Environment-driven configuration with graceful degradation
- Session management components integrated with proper dependency ordering
- Avoids circular dependencies between database and session management
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from polymer_extractor.storage.postgresql_client import PostgresClient
from polymer_extractor.storage.neo4j_client import Neo4jClient
from polymer_extractor.storage.storage_client import get_storage_client
from polymer_extractor.storage.storage_manager import get_storage_manager
from polymer_extractor.utils.logging import get_logger
from polymer_extractor.utils.paths import (
    PROJECT_ROOT, WORKSPACE_DIR, PUBLIC_DIR, MODELS_DIR,
    RAW_INPUT_DIR, EXTRACTED_XML_DIR, PROCESSED_XML_DIR, SAMPLES_DIR,
    REPORTS_DIR, SYSTEM_LOGS_DIR, DATASETS_DIR, EXPORTS_DIR
)

logger = get_logger()

# Import models sync service for Phase 2 GitHub sync functionality
try:
    from polymer_extractor.services.models_sync_service import ModelsSyncService
    MODELS_SYNC_AVAILABLE = True
except ImportError:
    # Graceful degradation if models sync service not available
    ModelsSyncService = None
    MODELS_SYNC_AVAILABLE = False

# Import session management components for multi-user support
try:
    from polymer_extractor.storage.session_manager import SessionManager
    from polymer_extractor.repositories.session_repository import SessionRepository
    from polymer_extractor.config.production_config import ProductionConfig
    SESSION_MANAGEMENT_AVAILABLE = True
except ImportError:
    # Graceful degradation if session management not available
    SessionManager = None
    SessionRepository = None
    ProductionConfig = None
    SESSION_MANAGEMENT_AVAILABLE = False


class SetupService:
    """
    Complete system orchestration service aligned with server.sh commands.

    Summary
    -------
    Provides production-ready system management operations with method names
    and behaviors that directly correspond to server.sh commands for consistency.
    Includes comprehensive multi-user session management integration.

    Core Methods (server.sh alignment)
    ----------------------------------
    initialize() -> Safe initialization of missing/corrupted components
    reset(components) -> Reset specified components (remove data, keep structure)
    wipe_data() -> Remove all data while preserving schemas/buckets
    check_health() -> Comprehensive system health validation  
    get_status() -> Current system status and configuration

    Component Operations
    -------------------
    initialize_database() -> PostgreSQL setup and recovery
    initialize_session_management() -> Multi-user session tables and constraints
    initialize_graph() -> Neo4j setup and recovery
    initialize_storage() -> Multi-backend storage setup and bucket creation

    Session Management
    ------------------
    get_session_management_status() -> Session management status and statistics
    Session components: SessionManager, SessionRepository, ProductionConfig
    Dependency handling: Proper ordering to avoid circular dependencies

    Configuration
    -------------
    Environment-driven via USE_POSTGRESQL_DB, USE_NEO4J_DB, STORAGE_BACKEND, etc.
    Session management requires PostgreSQL and auto-detects component availability.

    Examples
    --------
    >>> setup = SetupService()
    >>> result = setup.initialize()  # Safe initialization with session management
    >>> reset_result = setup.reset(['database', 'storage'])  # Reset specific components
    >>> health = setup.check_health()  # System health check including sessions
    >>> session_status = setup.get_session_management_status()  # Session-specific status
    """

    def __init__(self):
        """
        Initialize SetupService with environment-driven configuration.
        
        Summary
        -------
        Configures the service based on environment variables for PostgreSQL,
        Neo4j, and storage backends. Creates client instances only when enabled.
        
        Environment Variables
        --------------------
        USE_POSTGRESQL_DB : str
            Enable PostgreSQL operations (true/false)
        USE_NEO4J_DB : str  
            Enable Neo4j operations (true/false)
        STORAGE_BACKEND : str
            Primary storage backend (local/appwrite/s3)
        
        Attributes
        ----------
        postgres_enabled : bool
            Whether PostgreSQL operations are enabled
        neo4j_enabled : bool
            Whether Neo4j operations are enabled
        postgres_client : PostgresClient or None
            PostgreSQL client instance if enabled
        neo4j_client : Neo4jClient or None
            Neo4j client instance if enabled
        storage_client : StorageClient
            Storage client for multi-backend operations
            
        Notes
        -----
        - Clients are initialized lazily to avoid connection issues during import
        - Graceful degradation when services are disabled
        - All initialization errors are logged but don't prevent service creation
        """
        logger.info("Initializing SetupService", source="setup_service")
        
        # Environment configuration
        self.postgres_enabled = self._should_use_postgres()
        self.neo4j_enabled = self._should_use_neo4j()
        self.storage_backend = os.getenv("STORAGE_BACKEND", "local")
        
        # Initialize clients
        self.postgres_client = None
        self.neo4j_client = None
        self.storage_client = None
        self.storage_manager = None
        self.session_repository = None
        self.session_manager = None
        
        try:
            self.storage_client = get_storage_client()
            self.storage_manager = get_storage_manager()
            logger.info("Storage client initialized", source="setup_service", 
                       backend=self.storage_backend)
        except Exception as e:
            logger.error("Failed to initialize storage client", source="setup_service",
                        error=str(e))
        
        if self.postgres_enabled:
            try:
                self.postgres_client = PostgresClient()
                logger.info("PostgreSQL client initialized", source="setup_service")
            except Exception as e:
                logger.error("Failed to initialize PostgreSQL client", source="setup_service",
                           error=str(e))
        
        if self.neo4j_enabled:
            try:
                self.neo4j_client = Neo4jClient()
                logger.info("Neo4j client initialized", source="setup_service")
            except Exception as e:
                logger.error("Failed to initialize Neo4j client", source="setup_service",
                           error=str(e))

        # Initialize session management components if available and PostgreSQL is enabled
        # Note: Session management requires PostgreSQL for user/session tracking
        if SESSION_MANAGEMENT_AVAILABLE and self.postgres_enabled:
            try:
                # Initialize session repository first (data layer)
                self.session_repository = SessionRepository()
                logger.info("Session repository initialized", source="setup_service")
                
                # Initialize session manager (orchestration layer) 
                self.session_manager = SessionManager()
                logger.info("Session manager initialized", source="setup_service")
            except Exception as e:
                logger.warning("Failed to initialize session management components", 
                             source="setup_service", error=str(e))
        elif SESSION_MANAGEMENT_AVAILABLE and not self.postgres_enabled:
            logger.info("Session management disabled: requires PostgreSQL", source="setup_service")
        else:
            logger.info("Session management not available", source="setup_service")

    def _should_use_postgres(self) -> bool:
        """Check if PostgreSQL should be used based on environment."""
        return os.getenv("USE_POSTGRESQL_DB", "false").lower() == "true"
    
    def _should_use_neo4j(self) -> bool:
        """Check if Neo4j should be used based on environment."""
        return os.getenv("USE_NEO4J_DB", "false").lower() == "true"
    
    def _get_protected_buckets(self) -> List[str]:
        """
        Get list of bucket names that should be protected from reset/wipe operations.
        
        Summary
        -------
        Returns buckets containing valuable assets that should not be accidentally
        deleted during reset or wipe operations. These buckets can still be
        initialized if they don't exist.
        
        Returns
        -------
        List[str]
            List of protected bucket names
            
        Notes
        -----
        - models: Contains trained models and tokenizers (valuable assets)
        - system_logs: Contains log files and historical data (important for debugging)
        - Protected buckets are excluded from reset/wipe but can be initialized
        - Protected buckets are independent and don't sync with other storage backends
        """
        return ["models", "system_logs"]
    
    def _cleanup_system_logs_files(self, preserve_recent_hours: int = 1) -> Dict[str, Any]:
        """
        Clean up system_logs directory by truncating file contents, not deleting files.
        
        Summary
        -------
        Handles system_logs directory during reset operations by clearing file contents
        older than specified hours while preserving recent entries and file structure.
        This respects the requirement to never delete log files themselves.
        
        Parameters
        ----------
        preserve_recent_hours : int, optional
            Hours of recent log entries to preserve (default: 1)
        
        Returns
        -------
        Dict[str, Any]
            Cleanup results with files processed and entries preserved
        
        Notes
        -----
        - Never deletes log files themselves, only truncates old content
        - Preserves recent log entries based on timestamp
        - Safe for production use during reset operations
        """
        result = {
            "success": True,
            "files_processed": 0,
            "entries_preserved": 0,
            "details": ""
        }
        
        try:
            logs_path = Path(SYSTEM_LOGS_DIR)
            if not logs_path.exists():
                result["details"] = "System logs directory does not exist"
                return result
            
            # For file-based logs, we'd need to implement log rotation
            # Since we're using database logging primarily, this is handled by database reset
            # But we can clean up any file-based logs in the directory
            
            log_files = list(logs_path.glob("*.log"))
            if not log_files:
                result["details"] = "No log files found in system_logs directory"
                return result
            
            # For now, just report what would be cleaned
            # In a full implementation, you'd parse timestamps and truncate files
            result["files_processed"] = len(log_files)
            result["details"] = f"Found {len(log_files)} log files (file content cleanup not implemented for file-based logs)"
            
            logger.info("System logs cleanup completed", source="setup_service",
                       files_found=len(log_files), preserve_hours=preserve_recent_hours)
            
        except Exception as e:
            result["success"] = False
            result["details"] = f"System logs cleanup failed: {str(e)}"
            logger.error("System logs cleanup failed", source="setup_service", error=str(e))
        
        return result
    
    def _create_standard_buckets_with_override(self) -> Dict[str, Any]:
        """
        Create standard buckets with override enabled for reset/setup operations.
        
        Summary
        -------
        Creates standard storage buckets with allow_override=True, intended for
        reset operations where we want to ensure buckets are properly recreated
        even if they exist.
        
        Returns
        -------
        Dict[str, Any]
            Creation results with same structure as create_standard_buckets()
            
        Notes
        -----
        - Uses allow_override=True for all bucket creation operations
        - Intended for reset/destructive operations
        - Normal setup should use create_standard_buckets() instead
        """
        logger.info("Creating standard buckets with override enabled", source="setup_service")
        
        result = {
            "success": True,
            "buckets_created": [],
            "buckets_existed": [],
            "details": ""
        }
        
        if not self.storage_manager:
            result["success"] = False
            result["details"] = "Storage manager not available"
            return result
        
        # Standard bucket names (same as create_standard_buckets)
        standard_buckets = [
            "raw_inputs_dir",
            "extracted_xml_dir", 
            "processed_xml_dir",
            "samples_dir",
            "models",
            "full_reports_dir",
            "system_logs",
            "datasets_dir",
            "exports_dir"
        ]
        
        for bucket_name in standard_buckets:
            try:
                # Create bucket with override enabled (for reset operations)
                bucket_result = self.storage_manager.create_bucket(bucket_name, allow_override=True)
                action = bucket_result.get("action", "created")
                
                if action == "created":
                    result["buckets_created"].append(bucket_name)
                    logger.info(f"Bucket created with override", source="setup_service", bucket=bucket_name)
                elif action == "skipped":
                    result["buckets_existed"].append(bucket_name)
                    logger.info(f"Bucket already existed", source="setup_service", bucket=bucket_name)
                else:  # updated
                    result["buckets_created"].append(bucket_name)
                    logger.info(f"Bucket recreated with override", source="setup_service", bucket=bucket_name)
                    
            except Exception as e:
                result["details"] += f"Error creating bucket {bucket_name}: {str(e)}; "
                logger.error(f"Bucket creation with override failed", source="setup_service",
                           bucket=bucket_name, error=str(e))
                result["success"] = False
        
        # Update details
        total_created = len(result["buckets_created"])
        total_existed = len(result["buckets_existed"])
        
        if self.storage_manager:
            strategy_info = self.storage_manager.get_strategy_info()
            result["details"] += f"Bucket setup completed with override: {total_created} created, {total_existed} existed (total: {total_created + total_existed}). "
            result["details"] += f"Operations affected all {strategy_info['backend_count']} backends ({', '.join(strategy_info['backend_types'])}); "
        
        logger.info("Standard buckets creation with override completed", source="setup_service",
                   created=total_created, existed=total_existed, success=result["success"])
        
        return result
    
    def _get_storage_impact_summary(self) -> Dict[str, Any]:
        """Get summary of how operations will impact storage backends."""
        impact = {
            "manager_available": False,
            "strategy": "unknown",
            "backend_count": 0,
            "backend_types": [],
            "affects_all_backends": False,
            "summary": "Storage manager not available"
        }
        
        if self.storage_manager:
            try:
                strategy_info = self.storage_manager.get_strategy_info()
                impact.update({
                    "manager_available": True,
                    "strategy": strategy_info['strategy'],
                    "backend_count": strategy_info['backend_count'],
                    "backend_types": strategy_info['backend_types'],
                    "affects_all_backends": strategy_info['affects_all_backends'],
                    "summary": f"Strategy '{strategy_info['strategy']}' with {strategy_info['backend_count']} backends ({', '.join(strategy_info['backend_types'])})"
                })
                
                if strategy_info['affects_all_backends']:
                    impact["summary"] += " - operations affect ALL backends"
                else:
                    impact["summary"] += " - operations affect primary backend only"
                    
            except Exception as e:
                impact["summary"] = f"Error getting storage info: {str(e)}"
                
        return impact

    def get_environment_info(self) -> Dict[str, Any]:
        """
        Get comprehensive environment configuration information.
        
        Summary
        -------
        Returns detailed information about the current environment configuration
        including enabled services, storage backends, and key paths.
        
        Returns
        -------
        Dict[str, Any]
            Environment configuration details with structure:
            {
                "postgres_enabled": bool,
                "neo4j_enabled": bool, 
                "storage_backend": str,
                "workspace_dir": str,
                "public_dir": str,
                "models_dir": str,
                "storage_backends_active": List[str]
            }
            
        Examples
        --------
        >>> setup = SetupService()
        >>> env_info = setup.get_environment_info()
        >>> print(f"PostgreSQL: {env_info['postgres_enabled']}")
        >>> print(f"Storage: {env_info['storage_backend']}")
        
        Notes
        -----
        - Always returns current environment state
        - Safe to call even if services are not initialized
        - Useful for debugging configuration issues
        """
        logger.debug("Getting environment information", source="setup_service")
        
        return {
            "postgres_enabled": self.postgres_enabled,
            "neo4j_enabled": self.neo4j_enabled,
            "storage_backend": self.storage_backend,
            "storage_backends_active": os.getenv("STORAGE_BACKENDS_ACTIVE", "local").split(","),
            "workspace_dir": WORKSPACE_DIR,
            "public_dir": PUBLIC_DIR,
            "models_dir": MODELS_DIR,
            "project_root": PROJECT_ROOT,
            "timestamp": datetime.utcnow().isoformat()
        }

    def initialize(self, clean_install: bool = False, preserve_logs: bool = True, admin_user: Optional[str] = None, force_model_sync: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Safe initialization of missing or corrupted system components.
        
        Summary
        -------
        Performs comprehensive system initialization by checking each component
        and initializing only those that are missing or corrupted. Safe to run
        multiple times without affecting existing data.
        
        Parameters
        ----------
        clean_install : bool, optional
            If True, recreate all components even if they exist (default: False)
        preserve_logs : bool, optional
            If True, preserve existing logs during initialization (default: True)
        admin_user : Optional[str], optional
            Admin user context for initialization (default: None)
        force_model_sync : bool, optional
            Force model synchronization during initialization (default: False)
        **kwargs
            Additional parameters for forward compatibility
            
        Returns
        -------
        Dict[str, Any]
            Initialization results with structure:
            {
                "success": bool,
                "components": {
                    "database": {"initialized": bool, "details": str},
                    "graph": {"initialized": bool, "details": str},
                    "storage": {"initialized": bool, "details": str}
                },
                "warnings": List[str],
                "duration_seconds": float
            }
            
        Examples
        --------
        >>> setup = SetupService()
        >>> result = setup.initialize()
        >>> if result["success"]:
        ...     print("System initialized successfully")
        ... else:
        ...     print(f"Issues: {result['warnings']}")
        
        Notes
        -----
        - Safe to run multiple times - only initializes missing components
        - Creates directory structure if missing
        - Validates existing components before initializing
        - Comprehensive error handling with detailed feedback
        """
        start_time = datetime.utcnow()
        logger.info("Starting system initialization", source="setup_service",
                   clean_install=clean_install, preserve_logs=preserve_logs, 
                   admin_user=admin_user, force_model_sync=force_model_sync)
        
        # Get storage impact summary for better visibility
        storage_impact = self._get_storage_impact_summary()
        logger.info("Storage configuration for initialization", source="setup_service",
                   storage_impact=storage_impact["summary"])
        
        result = {
            "success": True,
            "components": {},
            "warnings": [],
            "duration_seconds": 0.0,
            "storage_impact": storage_impact
        }
        
        try:
            # Initialize storage first (directories and buckets)
            storage_result = self.initialize_storage(clean_install=clean_install)
            result["components"]["storage"] = storage_result
            if not storage_result.get("success", False):
                result["warnings"].append("Storage initialization had issues")
            
            # Initialize database if enabled
            if self.postgres_enabled:
                db_result = self.initialize_database(clean_install=clean_install, 
                                                   preserve_logs=preserve_logs)
                result["components"]["database"] = db_result
                if not db_result.get("success", False):
                    result["warnings"].append("Database initialization had issues")
                
                # Initialize session management if available and database succeeded
                if SESSION_MANAGEMENT_AVAILABLE and db_result.get("success", False):
                    session_result = self.initialize_session_management(clean_install=clean_install,
                                                                       preserve_logs=preserve_logs)
                    result["components"]["session_management"] = session_result
                    if not session_result.get("success", False):
                        result["warnings"].append("Session management initialization had issues")
                elif SESSION_MANAGEMENT_AVAILABLE:
                    result["components"]["session_management"] = {
                        "initialized": False,
                        "details": "Session management skipped due to database initialization failure",
                        "success": False
                    }
                    result["warnings"].append("Session management skipped: database not ready")
                else:
                    result["components"]["session_management"] = {
                        "initialized": False,
                        "details": "Session management components not available",
                        "success": True  # Not a failure if not available
                    }
            else:
                result["components"]["database"] = {
                    "initialized": False,
                    "details": "PostgreSQL disabled in environment"
                }
                result["components"]["session_management"] = {
                    "initialized": False,
                    "details": "Session management requires PostgreSQL"
                }
            
            # Initialize graph database if enabled
            if self.neo4j_enabled:
                graph_result = self.initialize_graph(clean_install=clean_install)
                result["components"]["graph"] = graph_result
                if not graph_result.get("success", False):
                    result["warnings"].append("Graph database initialization had issues")
            else:
                result["components"]["graph"] = {
                    "initialized": False,
                    "details": "Neo4j disabled in environment"
                }
            
            # Initialize models sync if requested and available (Phase 2 enhancement)
            if force_model_sync and MODELS_SYNC_AVAILABLE:
                try:
                    models_sync_service = ModelsSyncService(logger=logger)
                    models_result = models_sync_service.sync_models_from_github(force_redownload=clean_install)
                    result["components"]["models_sync"] = {
                        "initialized": models_result["success"],
                        "details": f"Models synced: {models_result['models_synced']}, Tokenizers synced: {models_result['tokenizers_synced']}",
                        "success": models_result["success"],
                        "models_synced": models_result["models_synced"],
                        "tokenizers_synced": models_result["tokenizers_synced"],
                        "version_validated": models_result["version_validated"]
                    }
                    if not models_result["success"]:
                        result["warnings"].append("Models sync had issues")
                        result["warnings"].extend(models_result.get("errors", []))
                except Exception as e:
                    logger.error("Models sync failed during initialization", source="setup_service", error=str(e))
                    result["components"]["models_sync"] = {
                        "initialized": False,
                        "details": f"Models sync error: {str(e)}",
                        "success": False
                    }
                    result["warnings"].append(f"Models sync failed: {str(e)}")
            elif force_model_sync and not MODELS_SYNC_AVAILABLE:
                result["components"]["models_sync"] = {
                    "initialized": False,
                    "details": "Models sync service not available",
                    "success": False
                }
                result["warnings"].append("Models sync requested but service not available")
            else:
                result["components"]["models_sync"] = {
                    "initialized": False,
                    "details": "Models sync not requested",
                    "success": True  # Not a failure if not requested
                }
            
            # Check if any critical component failed
            critical_failures = [
                comp for comp_name, comp in result["components"].items()
                if not comp.get("success", False) and comp.get("initialized", False)
            ]
            
            if critical_failures:
                result["success"] = False
                result["warnings"].append(f"Critical components failed: {len(critical_failures)}")
            
        except Exception as e:
            logger.error("System initialization failed", source="setup_service", error=str(e))
            result["success"] = False
            result["warnings"].append(f"Initialization error: {str(e)}")
        
        # Calculate duration
        end_time = datetime.utcnow()
        result["duration_seconds"] = (end_time - start_time).total_seconds()
        
        logger.info("System initialization completed", source="setup_service",
                   success=result["success"], warnings_count=len(result["warnings"]),
                   duration=result["duration_seconds"])
        
        return result

    def initialize_database(self, clean_install: bool = False, preserve_logs: bool = True) -> Dict[str, Any]:
        """
        Initialize PostgreSQL database with essential tables and indexes.
        
        Summary
        -------
        Sets up PostgreSQL database infrastructure including core tables for
        metadata storage, paper management, and system operations. Creates
        indexes for performance and constraints for data integrity.
        
        Parameters
        ----------
        clean_install : bool, optional
            If True, drop and recreate all tables (default: False)
        preserve_logs : bool, optional
            If True, preserve existing logs during reset (default: True)
            
        Returns
        -------
        Dict[str, Any]
            Database initialization results with structure:
            {
                "success": bool,
                "initialized": bool,
                "tables_created": List[str],
                "indexes_created": List[str],
                "details": str,
                "health_check": Dict[str, Any]
            }
            
        Raises
        ------
        Exception
            If PostgreSQL is disabled or client initialization failed
            
        Examples
        --------
        >>> setup = SetupService()
        >>> result = setup.initialize_database()
        >>> print(f"Tables: {result['tables_created']}")
        >>> print(f"Health: {result['health_check']['status']}")
        
        Notes
        -----
        - Creates essential tables: datasets_metadata, extraction_metadata, models_metadata
        - system_logs table creation/management is handled by logging.py to avoid conflicts
        - Never drops system_logs table during clean_install to prevent database locks
        - Adds performance indexes for common query patterns
        - Validates database connection before proceeding
        - Safe to run multiple times - uses CREATE IF NOT EXISTS
        """
        logger.info("Initializing PostgreSQL database", source="setup_service",
                   clean_install=clean_install)
        
        if not self.postgres_enabled:
            raise Exception("PostgreSQL is disabled in environment (USE_POSTGRESQL_DB=false)")
        
        if not self.postgres_client:
            raise Exception("PostgreSQL client not initialized")
        
        result = {
            "success": False,
            "initialized": False,
            "tables_created": [],
            "indexes_created": [],
            "details": "",
            "health_check": {}
        }
        
        try:
            # Check database health first
            health = self.postgres_client.health_check()
            result["health_check"] = health
            
            if not health.get("ok", False):
                result["details"] = f"Database health check failed: {health.get('error', 'Unknown')}"
                return result
            
            # Core metadata tables
            # NOTE: system_logs table creation delegated to logging.py to avoid conflicts
            core_tables = [
                ("datasets_metadata", """
                    CREATE TABLE IF NOT EXISTS datasets_metadata (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) NOT NULL UNIQUE,
                        description TEXT,
                        file_path VARCHAR(500),
                        format VARCHAR(50),
                        size_bytes BIGINT,
                        record_count INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata JSONB,
                        tags TEXT[]
                    )
                """),
                ("extraction_metadata", """
                    CREATE TABLE IF NOT EXISTS extraction_metadata (
                        id SERIAL PRIMARY KEY,
                        source_file VARCHAR(500) NOT NULL,
                        extraction_type VARCHAR(100),
                        status VARCHAR(50) DEFAULT 'pending',
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        error_message TEXT,
                        extracted_entities INTEGER DEFAULT 0,
                        output_file VARCHAR(500),
                        processing_time_seconds REAL,
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """),
                ("models_metadata", """
                    CREATE TABLE IF NOT EXISTS models_metadata (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) NOT NULL UNIQUE,
                        model_type VARCHAR(100),
                        version VARCHAR(50),
                        file_path VARCHAR(500),
                        size_bytes BIGINT,
                        accuracy REAL,
                        f1_score REAL,
                        precision_score REAL,
                        recall_score REAL,
                        training_data_path VARCHAR(500),
                        hyperparameters JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata JSONB
                    )
                """)
            ]
            
            # Ensure system_logs table exists (delegated to logging.py)
            try:
                # Use the logging system to ensure its table exists
                logger.initialize_database_table()
                logger.info("Ensured system_logs table exists via logging.py", source="setup_service")
            except Exception as e:
                logger.warning("Could not initialize system_logs via logging.py", source="setup_service", error=str(e))
            
            # Create tables
            for table_name, create_sql in core_tables:
                try:
                    if clean_install:
                        # Drop table if clean install, but NEVER drop system_logs (handled by logging.py)
                        if table_name != "system_logs":
                            self.postgres_client.run(f"DROP TABLE IF EXISTS {table_name} CASCADE")
                            logger.info(f"Dropped table for clean install", source="setup_service",
                                       table=table_name)
                        else:
                            logger.info(f"Skipping system_logs table drop - managed by logging.py", 
                                       source="setup_service", table=table_name)
                    
                    self.postgres_client.run(create_sql)
                    result["tables_created"].append(table_name)
                    logger.info(f"Created table", source="setup_service", table=table_name)
                    
                except Exception as e:
                    logger.error(f"Failed to create table {table_name}", source="setup_service",
                               error=str(e))
                    result["details"] += f"Table {table_name} error: {str(e)}; "
            
            # Create indexes for performance (excluding system_logs - managed by logging.py)
            indexes = [
                ("idx_datasets_name", "CREATE INDEX IF NOT EXISTS idx_datasets_name ON datasets_metadata(name)"),
                ("idx_extraction_source", "CREATE INDEX IF NOT EXISTS idx_extraction_source ON extraction_metadata(source_file)"),
                ("idx_extraction_status", "CREATE INDEX IF NOT EXISTS idx_extraction_status ON extraction_metadata(status)"),
                ("idx_models_name", "CREATE INDEX IF NOT EXISTS idx_models_name ON models_metadata(name)"),
                ("idx_models_type", "CREATE INDEX IF NOT EXISTS idx_models_type ON models_metadata(model_type)")
            ]
            
            for index_name, create_sql in indexes:
                try:
                    self.postgres_client.run(create_sql)
                    result["indexes_created"].append(index_name)
                    logger.debug(f"Created index", source="setup_service", index=index_name)
                except Exception as e:
                    logger.warning(f"Failed to create index {index_name}", source="setup_service",
                                 error=str(e))
            
            result["success"] = True
            result["initialized"] = True
            result["details"] = f"Database initialized with {len(result['tables_created'])} tables and {len(result['indexes_created'])} indexes"
            
        except Exception as e:
            logger.error("Database initialization failed", source="setup_service", error=str(e))
            result["details"] = f"Database initialization error: {str(e)}"
        
        return result

    def initialize_session_management(self, clean_install: bool = False, preserve_logs: bool = True) -> Dict[str, Any]:
        """
        Initialize multi-user session management tables and constraints.
        
        Summary
        -------
        Sets up PostgreSQL tables for multi-user session management including
        user accounts, sessions, resource allocation, and analytics. Creates
        the foundation for production multi-user polymer extraction workflows.
        
        Parameters
        ----------
        clean_install : bool, optional
            If True, drop and recreate session tables (default: False)
        preserve_logs : bool, optional
            If True, preserve existing session logs during reset (default: True)
            
        Returns
        -------
        Dict[str, Any]
            Session management initialization results with structure:
            {
                "success": bool,
                "initialized": bool,
                "tables_created": List[str],
                "indexes_created": List[str], 
                "details": str,
                "session_management_available": bool
            }
            
        Raises
        ------
        Exception
            If PostgreSQL is disabled or session management not available
            
        Examples
        --------
        >>> setup = SetupService()
        >>> result = setup.initialize_session_management()
        >>> print(f"Session tables: {result['tables_created']}")
        >>> print(f"Session management: {result['session_management_available']}")
        
        Notes
        -----
        - Creates multi-user tables: users, user_sessions, resource_allocations, storage_allocations
        - Requires PostgreSQL to be enabled and available
        - Safe to run multiple times - uses CREATE IF NOT EXISTS
        - Avoids circular dependencies by only creating tables, not initializing managers
        - Session managers are initialized separately in __init__ after tables exist
        """
        logger.info("Initializing session management tables", source="setup_service",
                   clean_install=clean_install)
        
        if not self.postgres_enabled:
            raise Exception("Session management requires PostgreSQL (USE_POSTGRESQL_DB=true)")
        
        if not SESSION_MANAGEMENT_AVAILABLE:
            raise Exception("Session management components not available")
        
        if not self.postgres_client:
            raise Exception("PostgreSQL client not initialized")
        
        result = {
            "success": False,
            "initialized": False,
            "tables_created": [],
            "indexes_created": [],
            "details": "",
            "session_management_available": SESSION_MANAGEMENT_AVAILABLE
        }
        
        try:
            # Check database health first
            health = self.postgres_client.health_check()
            
            if not health.get("ok", False):
                result["details"] = f"Database health check failed: {health.get('error', 'Unknown')}"
                return result
            
            # Read the multi-user schema from the SQL file to ensure consistency
            sql_file_path = os.path.join(PROJECT_ROOT, "db", "sql", "002_multi_user.sql")
            
            if not os.path.exists(sql_file_path):
                result["details"] = f"Multi-user schema file not found: {sql_file_path}"
                return result
            
            # Execute the multi-user schema script
            try:
                with open(sql_file_path, 'r') as f:
                    sql_content = f.read()
                
                # Split into individual statements (basic splitting on semicolons)
                sql_statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
                
                # Track what we're creating
                session_tables = []
                session_indexes = []
                deferred_indexes = []  # For indexes on columns that need to be added first
                
                for statement in sql_statements:
                    statement_upper = statement.upper()
                    
                    if clean_install and statement_upper.startswith('DROP TABLE'):
                        # Execute DROP statements during clean install
                        try:
                            self.postgres_client.run(statement)
                            logger.info("Dropped table during clean install", source="setup_service")
                        except Exception as e:
                            # Non-fatal if table doesn't exist
                            logger.debug("Table drop failed (may not exist)", source="setup_service", error=str(e))
                    
                    # Handle statements that contain multiple CREATE TABLE commands
                    if 'CREATE TABLE' in statement_upper:
                        # Split by CREATE TABLE to extract individual table definitions
                        table_parts = statement.split('CREATE TABLE')
                        
                        for i, part in enumerate(table_parts):
                            if i == 0:  # Skip the first part (comments/headers)
                                continue
                                
                            # Reconstruct the CREATE TABLE statement
                            table_statement = 'CREATE TABLE' + part
                            
                            # Extract table name for tracking
                            table_name = "unknown_table"
                            try:
                                # Find the table name (first word after CREATE TABLE)
                                lines = table_statement.split('\n')
                                first_line = lines[0].strip()
                                table_name = first_line.replace('CREATE TABLE', '').strip().split(' ')[0].split('(')[0].strip()
                                session_tables.append(table_name)
                            except:
                                pass
                            
                            try:
                                self.postgres_client.run(table_statement)
                                logger.info(f"Created session table", source="setup_service", table=table_name)
                            except Exception as e:
                                logger.error(f"Failed to create session table", source="setup_service", 
                                           table=table_name, error=str(e))
                                result["details"] += f"Table {table_name} error: {str(e)}; "
                    
                    elif statement_upper.startswith('CREATE INDEX') or statement_upper.startswith('CREATE UNIQUE INDEX'):
                        # Extract index name for tracking
                        index_name = "unknown_index"  # Default value for error handling
                        
                        # Special handling for indexes on columns that might not exist yet
                        if ('uploaded_by' in statement or 'created_by' in statement):
                            # Check if these indexes depend on columns that need to be added first
                            # Skip these for now and process them after ALTER TABLE statements
                            logger.debug(f"Deferring index creation for user-aware columns", 
                                       source="setup_service", statement=statement[:100])
                            deferred_indexes.append(statement)
                            continue
                        
                        # Handle various CREATE INDEX patterns
                        if 'CREATE INDEX IF NOT EXISTS' in statement_upper:
                            index_match = statement_upper.split('CREATE INDEX IF NOT EXISTS ')
                            if len(index_match) > 1:
                                index_name = index_match[1].split(' ')[0].strip()
                        elif 'CREATE UNIQUE INDEX' in statement_upper:
                            index_match = statement_upper.split('CREATE UNIQUE INDEX ')
                            if len(index_match) > 1:
                                index_name = index_match[1].split(' ')[0].strip()
                        else:
                            index_match = statement_upper.split('CREATE INDEX ')
                            if len(index_match) > 1:
                                index_name = index_match[1].split(' ')[0].strip()
                        
                        session_indexes.append(index_name)
                        
                        try:
                            self.postgres_client.run(statement)
                            logger.debug(f"Created session index", source="setup_service", index=index_name)
                        except Exception as e:
                            logger.warning(f"Failed to create session index", source="setup_service",
                                         index=index_name, error=str(e))
                    
                    elif statement_upper.startswith('ALTER TABLE'):
                        # Execute ALTER TABLE statements
                        try:
                            self.postgres_client.run(statement)
                            logger.debug("Executed ALTER TABLE statement", source="setup_service")
                        except Exception as e:
                            logger.warning("Failed to execute ALTER TABLE", source="setup_service", error=str(e))
                    
                    elif statement_upper.startswith('CREATE FUNCTION') or statement_upper.startswith('CREATE OR REPLACE FUNCTION'):
                        # Execute function creation
                        try:
                            self.postgres_client.run(statement)
                            logger.info("Created session management function", source="setup_service")
                        except Exception as e:
                            logger.warning("Failed to create session function", source="setup_service", error=str(e))
                    
                    elif statement_upper.startswith('CREATE VIEW') or statement_upper.startswith('CREATE OR REPLACE VIEW'):
                        # Execute view creation
                        try:
                            self.postgres_client.run(statement)
                            logger.debug("Created session management view", source="setup_service")
                        except Exception as e:
                            logger.warning("Failed to create session view", source="setup_service", error=str(e))
                    
                    elif statement_upper.startswith('CREATE TRIGGER'):
                        # Execute trigger creation
                        try:
                            self.postgres_client.run(statement)
                            logger.debug("Created session management trigger", source="setup_service")
                        except Exception as e:
                            logger.warning("Failed to create session trigger", source="setup_service", error=str(e))
                    
                    elif statement_upper.startswith('INSERT INTO'):
                        # Execute data inserts
                        try:
                            self.postgres_client.run(statement)
                            logger.debug("Executed session management data insert", source="setup_service")
                        except Exception as e:
                            logger.warning("Failed to execute data insert", source="setup_service", error=str(e))
                
                # Process deferred indexes after all schema changes are complete
                logger.info(f"Processing {len(deferred_indexes)} deferred indexes", source="setup_service")
                for deferred_statement in deferred_indexes:
                    try:
                        # Extract index name for tracking
                        statement_upper = deferred_statement.upper()
                        index_name = "unknown_deferred_index"
                        
                        if 'CREATE INDEX IF NOT EXISTS' in statement_upper:
                            index_match = statement_upper.split('CREATE INDEX IF NOT EXISTS ')
                            if len(index_match) > 1:
                                index_name = index_match[1].split(' ')[0].strip()
                        elif 'CREATE UNIQUE INDEX' in statement_upper:
                            index_match = statement_upper.split('CREATE UNIQUE INDEX ')
                            if len(index_match) > 1:
                                index_name = index_match[1].split(' ')[0].strip()
                        else:
                            index_match = statement_upper.split('CREATE INDEX ')
                            if len(index_match) > 1:
                                index_name = index_match[1].split(' ')[0].strip()
                        
                        self.postgres_client.run(deferred_statement)
                        session_indexes.append(index_name)
                        logger.debug(f"Created deferred session index", source="setup_service", index=index_name)
                    except Exception as e:
                        logger.error(f"Failed to create deferred session index", source="setup_service",
                                   index=index_name, error=str(e))
                
                result["tables_created"] = session_tables
                result["indexes_created"] = session_indexes
                result["success"] = True
                result["initialized"] = True
                result["details"] = f"Session management initialized with {len(session_tables)} tables and {len(session_indexes)} indexes"
                
            except Exception as e:
                logger.error("Failed to execute multi-user schema", source="setup_service", error=str(e))
                result["details"] = f"Schema execution error: {str(e)}"
        
        except Exception as e:
            logger.error("Session management initialization failed", source="setup_service", error=str(e))
            result["details"] = f"Session management initialization error: {str(e)}"
        
        return result

    def initialize_graph(self, clean_install: bool = False) -> Dict[str, Any]:
        """
        Initialize Neo4j graph database with constraints and indexes.
        
        Summary
        -------
        Sets up Neo4j graph database infrastructure including constraints for
        data integrity and indexes for query performance. Creates the foundation
        for polymer science knowledge graph operations.
        
        Parameters
        ----------
        clean_install : bool, optional
            If True, drop existing constraints and recreate (default: False)
            
        Returns
        -------
        Dict[str, Any]
            Graph initialization results with structure:
            {
                "success": bool,
                "initialized": bool,
                "constraints_created": List[str],
                "indexes_created": List[str],
                "details": str,
                "health_check": Dict[str, Any]
            }
            
        Raises
        ------
        Exception
            If Neo4j is disabled or client initialization failed
            
        Examples
        --------
        >>> setup = SetupService()
        >>> result = setup.initialize_graph()
        >>> print(f"Constraints: {result['constraints_created']}")
        >>> print(f"Health: {result['health_check']['status']}")
        
        Notes
        -----
        - Creates uniqueness constraints for Paper.doi, Polymer.name
        - Adds performance indexes for common graph traversal patterns
        - Validates graph database connection before proceeding
        - Safe to run multiple times - uses IF NOT EXISTS where possible
        """
        logger.info("Initializing Neo4j graph database", source="setup_service",
                   clean_install=clean_install)
        
        if not self.neo4j_enabled:
            raise Exception("Neo4j is disabled in environment (USE_NEO4J_DB=false)")
        
        if not self.neo4j_client:
            raise Exception("Neo4j client not initialized")
        
        result = {
            "success": False,
            "initialized": False,
            "constraints_created": [],
            "indexes_created": [],
            "details": "",
            "health_check": {}
        }
        
        try:
            # Check graph database health
            health = self.neo4j_client.health_check()
            result["health_check"] = health
            
            if not health.get("ok", False):
                result["details"] = f"Graph database health check failed: {health.get('error', 'Unknown')}"
                return result
            
            # Create constraints for data integrity
            constraints = [
                ("Paper_doi", "CREATE CONSTRAINT paper_doi_unique IF NOT EXISTS FOR (p:Paper) REQUIRE p.doi IS UNIQUE"),
                ("Polymer_name", "CREATE CONSTRAINT polymer_name_unique IF NOT EXISTS FOR (p:Polymer) REQUIRE p.name IS UNIQUE"),
                ("Author_orcid", "CREATE CONSTRAINT author_orcid_unique IF NOT EXISTS FOR (a:Author) REQUIRE a.orcid IS UNIQUE"),
                ("Property_name", "CREATE CONSTRAINT property_name_unique IF NOT EXISTS FOR (p:Property) REQUIRE p.name IS UNIQUE")
            ]
            
            if clean_install:
                # Drop existing constraints for clean install
                try:
                    existing_constraints = self.neo4j_client.run(
                        "SHOW CONSTRAINTS YIELD name", fetch="all"
                    )
                    for constraint in existing_constraints:
                        constraint_name = constraint.get("name", "")
                        if any(c[0].lower() in constraint_name.lower() for c in constraints):
                            self.neo4j_client.run(f"DROP CONSTRAINT {constraint_name} IF EXISTS")
                            logger.info(f"Dropped constraint for clean install", 
                                       source="setup_service", constraint=constraint_name)
                except Exception as e:
                    logger.warning("Failed to drop existing constraints", source="setup_service",
                                 error=str(e))
            
            # Create constraints
            for constraint_name, create_sql in constraints:
                try:
                    self.neo4j_client.run(create_sql)
                    result["constraints_created"].append(constraint_name)
                    logger.info(f"Created constraint", source="setup_service", 
                               constraint=constraint_name)
                except Exception as e:
                    logger.warning(f"Failed to create constraint {constraint_name}", 
                                 source="setup_service", error=str(e))
                    result["details"] += f"Constraint {constraint_name} error: {str(e)}; "
            
            # Create indexes for performance
            indexes = [
                ("paper_title", "CREATE INDEX paper_title_index IF NOT EXISTS FOR (p:Paper) ON (p.title)"),
                ("polymer_type", "CREATE INDEX polymer_type_index IF NOT EXISTS FOR (p:Polymer) ON (p.type)"),
                ("author_name", "CREATE INDEX author_name_index IF NOT EXISTS FOR (a:Author) ON (a.name)"),
                ("property_value", "CREATE INDEX property_value_index IF NOT EXISTS FOR (p:Property) ON (p.value)")
            ]
            
            for index_name, create_sql in indexes:
                try:
                    self.neo4j_client.run(create_sql)
                    result["indexes_created"].append(index_name)
                    logger.debug(f"Created index", source="setup_service", index=index_name)
                except Exception as e:
                    logger.warning(f"Failed to create index {index_name}", source="setup_service",
                                 error=str(e))
            
            result["success"] = True
            result["initialized"] = True
            result["details"] = f"Graph database initialized with {len(result['constraints_created'])} constraints and {len(result['indexes_created'])} indexes"
            
        except Exception as e:
            logger.error("Graph database initialization failed", source="setup_service", error=str(e))
            result["details"] = f"Graph database initialization error: {str(e)}"
        
        return result

    def initialize_storage(self, clean_install: bool = False) -> Dict[str, Any]:
        """
        Initialize storage backend with directory structure and buckets.
        
        Summary
        -------
        Creates the complete directory structure for the polymer extractor and
        initializes storage buckets across all configured backends. Ensures
        all required directories exist for data processing pipelines.
        
        Parameters
        ----------
        clean_install : bool, optional
            If True, recreate directory structure (default: False)
            
        Returns
        -------
        Dict[str, Any]
            Storage initialization results with structure:
            {
                "success": bool,
                "directories_created": List[str],
                "buckets_created": List[str],
                "details": str,
                "storage_health": Dict[str, Any]
            }
            
        Examples
        --------
        >>> setup = SetupService()
        >>> result = setup.initialize_storage()
        >>> print(f"Directories: {result['directories_created']}")
        >>> print(f"Buckets: {result['buckets_created']}")
        
        Notes
        -----
        - Creates workspace directory structure under PUBLIC_DIR
        - Initializes storage buckets for all active backends
        - Validates storage client connectivity
        - Safe to run multiple times - only creates missing directories
        """
        logger.info("Initializing storage infrastructure", source="setup_service",
                   clean_install=clean_install)
        
        result = {
            "success": False,
            "directories_created": [],
            "buckets_created": [],
            "details": "",
            "storage_health": {}
        }
        
        try:
            # Check storage health if client available
            if self.storage_client:
                try:
                    # Basic connectivity test - fix parameter issue
                    test_result = self.storage_client.list_resources("")
                    result["storage_health"] = {"status": "healthy", "backend": self.storage_backend}
                except Exception as e:
                    result["storage_health"] = {"status": "unhealthy", "error": str(e)}
            
            # Create directory structure (respecting protected folders)
            required_directories = [
                WORKSPACE_DIR,
                PUBLIC_DIR,
                RAW_INPUT_DIR,
                EXTRACTED_XML_DIR,
                PROCESSED_XML_DIR,
                SAMPLES_DIR,
                MODELS_DIR,  # Protected - only create if missing
                REPORTS_DIR,
                SYSTEM_LOGS_DIR,  # Protected - only create if missing
                DATASETS_DIR,
                EXPORTS_DIR,
                os.path.join(DATASETS_DIR, "training"),
                os.path.join(DATASETS_DIR, "testing")
            ]
            
            # Define protected directories that should never be deleted during clean_install
            protected_directories = {MODELS_DIR, SYSTEM_LOGS_DIR}
            
            for directory in required_directories:
                try:
                    dir_path = Path(directory)
                    
                    # For clean install, respect protected directories
                    if clean_install and dir_path.exists() and directory in protected_directories:
                        # Protected directories: only ensure they exist, never delete content
                        logger.info(f"Protected directory preserved during clean install", 
                                   source="setup_service", directory=directory)
                        continue
                    elif clean_install and dir_path.exists() and directory not in protected_directories:
                        # Non-protected directories: could be cleaned but directories are not removed for safety
                        # This preserves the original safe behavior
                        logger.debug(f"Non-protected directory preserved during clean install", 
                                    source="setup_service", directory=directory)
                    
                    if not dir_path.exists():
                        dir_path.mkdir(parents=True, exist_ok=True)
                        result["directories_created"].append(str(directory))
                        logger.debug(f"Created directory", source="setup_service", 
                                   directory=directory)
                    
                except Exception as e:
                    logger.error(f"Failed to create directory {directory}", 
                               source="setup_service", error=str(e))
                    result["details"] += f"Directory {directory} error: {str(e)}; "
            
            # Create storage buckets if storage client available
            if self.storage_manager:
                # For clean install, delete and recreate non-protected buckets only
                if clean_install:
                    try:
                        # Get strategy info to understand multi-backend impact
                        strategy_info = self.storage_manager.get_strategy_info()
                        logger.info("Clean install: recreating non-protected buckets across all backends", 
                                   source="setup_service",
                                   strategy=strategy_info['strategy'],
                                   backend_count=strategy_info['backend_count'])
                        
                        # Define protected buckets that should never be deleted
                        protected_buckets = self._get_protected_buckets()  # ["models", "system_logs"]
                        
                        # Delete existing non-protected buckets first
                        existing_buckets = self.storage_manager.list_buckets()
                        deleted_count = 0
                        protected_count = 0
                        
                        for bucket in existing_buckets:
                            bucket_name = bucket.get("name") or bucket.get("$id")
                            if bucket_name:
                                if bucket_name in protected_buckets:
                                    # Skip protected buckets
                                    protected_count += 1
                                    logger.info(f"Protected bucket preserved during clean install", 
                                               source="setup_service", bucket=bucket_name)
                                else:
                                    # Delete non-protected buckets
                                    try:
                                        self.storage_manager.delete_bucket(bucket_name)
                                        deleted_count += 1
                                        logger.debug(f"Deleted non-protected bucket", source="setup_service", bucket=bucket_name)
                                    except Exception as e:
                                        logger.warning(f"Failed to delete bucket {bucket_name}: {e}", source="setup_service")
                        
                        if deleted_count > 0:
                            result["details"] += f"Deleted {deleted_count} non-protected buckets for clean install ({protected_count} protected buckets preserved); "
                            logger.info(f"Clean install: deleted {deleted_count} non-protected buckets, preserved {protected_count} protected buckets", 
                                       source="setup_service")
                    
                    except Exception as e:
                        result["details"] += f"Clean install bucket deletion error: {str(e)}; "
                        logger.warning("Clean install bucket deletion failed", source="setup_service", error=str(e))
                
                # Create standard buckets
                bucket_result = self.create_standard_buckets()
                result["buckets_created"] = bucket_result.get("buckets_created", [])
                
                # Include existing buckets in the report for transparency
                buckets_existed = bucket_result.get("buckets_existed", [])
                if buckets_existed:
                    result["details"] += f"Found {len(buckets_existed)} existing buckets; "
                
                if not bucket_result.get("success", False):
                    result["details"] += f"Bucket creation issues: {bucket_result.get('details', '')}; "
                else:
                    # Log multi-backend impact
                    strategy_info = self.storage_manager.get_strategy_info()
                    if strategy_info['affects_all_backends']:
                        result["details"] += f"Buckets created on all {strategy_info['backend_count']} backends; "
                    else:
                        result["details"] += f"Buckets created on primary backend only; "
            else:
                result["details"] += "Storage manager not available for bucket creation; "
            
            # Check overall success
            if len(result["directories_created"]) > 0 or len(result["buckets_created"]) > 0:
                result["success"] = True
                result["details"] = f"Storage initialized: {len(result['directories_created'])} directories, {len(result['buckets_created'])} buckets"
            elif result["details"] == "":
                result["success"] = True
                result["details"] = "Storage already initialized"
            
        except Exception as e:
            logger.error("Storage initialization failed", source="setup_service", error=str(e))
            result["details"] = f"Storage initialization error: {str(e)}"
        
        return result

    def create_standard_buckets(self) -> Dict[str, Any]:
        """
        Create standardized storage buckets across all backends.
        
        Summary
        -------
        Creates the standard set of storage buckets required for polymer
        extractor operations. Handles multi-backend scenarios and provides
        detailed feedback on bucket creation status.
        
        Returns
        -------
        Dict[str, Any]
            Bucket creation results with structure:
            {
                "success": bool,
                "buckets_created": List[str],
                "buckets_existed": List[str],
                "details": str
            }
            
        Examples
        --------
        >>> setup = SetupService()
        >>> result = setup.create_standard_buckets()
        >>> print(f"Created: {result['buckets_created']}")
        >>> print(f"Existed: {result['buckets_existed']}")
        
        Notes
        -----
        - Creates buckets: raw_inputs, extracted_xml, processed_xml, samples, 
          models, reports, system_logs, datasets, exports
        - Safe to run multiple times - tracks which buckets already exist
        - Works across all configured storage backends
        """
        logger.info("Creating standard storage buckets", source="setup_service")
        
        result = {
            "success": True,
            "buckets_created": [],
            "buckets_existed": [],
            "details": ""
        }
        
        if not self.storage_manager:
            result["success"] = False
            result["details"] = "Storage manager not available"
            return result
        
        # Standard bucket names (normalized for all backends)
        standard_buckets = [
            "raw_inputs_dir",
            "extracted_xml_dir", 
            "processed_xml_dir",
            "samples_dir",
            "models",
            "full_reports_dir",
            "system_logs",
            "datasets_dir",
            "exports_dir"
        ]
        
        for bucket_name in standard_buckets:
            try:
                # Check if bucket exists using storage manager (strategy-aware)
                try:
                    if self.storage_manager.bucket_exists(bucket_name):
                        result["buckets_existed"].append(bucket_name)
                        logger.debug(f"Bucket already exists", source="setup_service", 
                                   bucket=bucket_name)
                    else:
                        # Create bucket using storage manager (affects backends per strategy)
                        bucket_result = self.storage_manager.create_bucket(bucket_name)
                        if bucket_result.get("success", False) or bucket_result.get("$id"):
                            result["buckets_created"].append(bucket_name)
                            logger.info(f"Bucket created successfully", source="setup_service",
                                       bucket=bucket_name)
                        else:
                            result["details"] += f"Failed to create bucket {bucket_name}; "
                            logger.warning(f"Bucket creation failed", source="setup_service",
                                         bucket=bucket_name, result=bucket_result)
                
                except Exception as e:
                    result["details"] += f"Error handling bucket {bucket_name}: {str(e)}; "
                    logger.error(f"Bucket operation failed", source="setup_service",
                               bucket=bucket_name, error=str(e))
                    result["success"] = False
                    
            except Exception as e:
                result["details"] += f"Critical error with bucket {bucket_name}: {str(e)}; "
                logger.error(f"Critical bucket error", source="setup_service",
                           bucket=bucket_name, error=str(e))
                result["success"] = False
        
        # Add multi-backend information to result
        if self.storage_manager:
            try:
                strategy_info = self.storage_manager.get_strategy_info()
                total_created = len(result["buckets_created"])
                total_existed = len(result["buckets_existed"])
                
                if strategy_info['affects_all_backends']:
                    result["details"] += f"Operations affected all {strategy_info['backend_count']} backends ({', '.join(strategy_info['backend_types'])}); "
                    logger.info(f"Bucket operations completed across all backends", 
                               source="setup_service",
                               created=total_created, existed=total_existed,
                               backends=strategy_info['backend_count'])
                else:
                    result["details"] += f"Operations affected primary backend only (strategy: {strategy_info['strategy']}); "
                    logger.info(f"Bucket operations completed on primary backend", 
                               source="setup_service",
                               created=total_created, existed=total_existed,
                               strategy=strategy_info['strategy'])
                    
            except Exception as e:
                result["details"] += f"Failed to get strategy info: {str(e)}; "
        
        # Final success assessment
        if result["success"] and (len(result["buckets_created"]) > 0 or len(result["buckets_existed"]) > 0):
            total_buckets = len(result["buckets_created"]) + len(result["buckets_existed"])
            result["details"] = f"Bucket setup completed: {len(result['buckets_created'])} created, {len(result['buckets_existed'])} existed (total: {total_buckets}). {result['details']}"
        elif result["success"]:
            result["details"] = "No buckets needed creation. " + result["details"]
        
        return result

    def check_health(self) -> Dict[str, Any]:
        """
        Comprehensive system health check across all components.
        
        Summary
        -------
        Performs detailed health validation of PostgreSQL, Neo4j, and storage
        backends. Returns comprehensive status information for monitoring
        and diagnostic purposes.
        
        Returns
        -------
        Dict[str, Any]
            Health check results with structure:
            {
                "overall_status": str,  # "healthy", "degraded", "unhealthy"
                "services": {
                    "postgres": {"status": str, "details": Dict},
                    "neo4j": {"status": str, "details": Dict},
                    "storage": {"status": str, "details": Dict}
                },
                "warnings": List[str],
                "timestamp": str
            }
            
        Examples
        --------
        >>> setup = SetupService()
        >>> health = setup.check_health()
        >>> print(f"Overall: {health['overall_status']}")
        >>> for service, status in health['services'].items():
        ...     print(f"{service}: {status['status']}")
        
        Notes
        -----
        - Always returns a result even if services are disabled
        - Provides detailed diagnostic information for troubleshooting
        - Safe to call frequently for monitoring purposes
        - Non-blocking - won't hang on unresponsive services
        """
        logger.info("Performing comprehensive health check", source="setup_service")
        
        result = {
            "overall_status": "healthy",
            "services": {},
            "warnings": [],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Check PostgreSQL
        if self.postgres_enabled and self.postgres_client:
            try:
                pg_health = self.postgres_client.health_check()
                result["services"]["postgres"] = {
                    "status": "healthy" if pg_health.get("ok", False) else "unhealthy",
                    "details": pg_health
                }
                if not pg_health.get("ok", False):
                    result["warnings"].append("PostgreSQL is unhealthy")
            except Exception as e:
                result["services"]["postgres"] = {
                    "status": "error",
                    "details": {"error": str(e)}
                }
                result["warnings"].append(f"PostgreSQL health check failed: {str(e)}")
        else:
            result["services"]["postgres"] = {
                "status": "disabled",
                "details": {"reason": "PostgreSQL disabled or client not initialized"}
            }
        
        # Check Neo4j
        if self.neo4j_enabled and self.neo4j_client:
            try:
                neo4j_health = self.neo4j_client.health_check()
                result["services"]["neo4j"] = {
                    "status": "healthy" if neo4j_health.get("ok", False) else "unhealthy",
                    "details": neo4j_health
                }
                if not neo4j_health.get("ok", False):
                    result["warnings"].append("Neo4j is unhealthy")
            except Exception as e:
                result["services"]["neo4j"] = {
                    "status": "error", 
                    "details": {"error": str(e)}
                }
                result["warnings"].append(f"Neo4j health check failed: {str(e)}")
        else:
            result["services"]["neo4j"] = {
                "status": "disabled",
                "details": {"reason": "Neo4j disabled or client not initialized"}
            }
        
        # Check Storage
        if self.storage_client:
            try:
                # Simple connectivity test - just list root folder (fix parameter issue)
                resources = self.storage_client.list_resources("")
                result["services"]["storage"] = {
                    "status": "healthy",
                    "details": {
                        "backend": self.storage_backend,
                        "connectivity": "ok"
                    }
                }
            except Exception as e:
                result["services"]["storage"] = {
                    "status": "unhealthy",
                    "details": {
                        "backend": self.storage_backend,
                        "error": str(e)
                    }
                }
                result["warnings"].append(f"Storage backend unhealthy: {str(e)}")
        else:
            result["services"]["storage"] = {
                "status": "error",
                "details": {"reason": "Storage client not initialized"}
            }
            result["warnings"].append("Storage client not available")
        
        # Check Session Management
        if SESSION_MANAGEMENT_AVAILABLE and self.postgres_enabled and self.session_repository:
            try:
                # Simple session management health check - verify table existence
                session_health = self.session_repository.health_check() if hasattr(self.session_repository, 'health_check') else {"status": "ok"}
                result["services"]["session_management"] = {
                    "status": "healthy" if session_health.get("status") == "ok" else "unhealthy",
                    "details": {
                        "components_available": SESSION_MANAGEMENT_AVAILABLE,
                        "postgres_enabled": self.postgres_enabled,
                        "repository_initialized": self.session_repository is not None,
                        "manager_initialized": self.session_manager is not None,
                        "health_details": session_health
                    }
                }
                if session_health.get("status") != "ok":
                    result["warnings"].append("Session management is unhealthy")
            except Exception as e:
                result["services"]["session_management"] = {
                    "status": "error",
                    "details": {
                        "error": str(e),
                        "components_available": SESSION_MANAGEMENT_AVAILABLE,
                        "postgres_enabled": self.postgres_enabled
                    }
                }
                result["warnings"].append(f"Session management health check failed: {str(e)}")
        elif SESSION_MANAGEMENT_AVAILABLE and not self.postgres_enabled:
            result["services"]["session_management"] = {
                "status": "disabled",
                "details": {"reason": "Session management requires PostgreSQL"}
            }
        else:
            result["services"]["session_management"] = {
                "status": "disabled", 
                "details": {"reason": "Session management components not available"}
            }
        
        # Determine overall status
        service_statuses = [svc["status"] for svc in result["services"].values()]
        if any(status == "error" for status in service_statuses):
            result["overall_status"] = "unhealthy"
        elif any(status == "unhealthy" for status in service_statuses):
            result["overall_status"] = "degraded"
        elif len(result["warnings"]) > 0:
            result["overall_status"] = "degraded"
        
        logger.info("Health check completed", source="setup_service",
                   overall_status=result["overall_status"], 
                   warnings_count=len(result["warnings"]))
        
        return result

    def get_status(self) -> Dict[str, Any]:
        """
        Get current system status and configuration.
        
        Summary
        -------
        Returns comprehensive information about the current system state
        including configuration, component status, and operational metrics.
        Combines environment info with health status for complete overview.
        
        Returns
        -------
        Dict[str, Any]
            System status with structure:
            {
                "environment": Dict[str, Any],
                "health": Dict[str, Any],
                "configuration": {
                    "postgres_enabled": bool,
                    "neo4j_enabled": bool,
                    "storage_backend": str
                },
                "timestamp": str
            }
            
        Examples
        --------
        >>> setup = SetupService()
        >>> status = setup.get_status()
        >>> print(f"PostgreSQL: {status['configuration']['postgres_enabled']}")
        >>> print(f"Health: {status['health']['overall_status']}")
        
        Notes
        -----
        - Combines environment and health information
        - Useful for administrative dashboards and monitoring
        - Safe to call frequently for status updates
        """
        logger.debug("Getting system status", source="setup_service")
        
        return {
            "environment": self.get_environment_info(),
            "health": self.check_health(),
            "configuration": {
                "postgres_enabled": self.postgres_enabled,
                "neo4j_enabled": self.neo4j_enabled,
                "storage_backend": self.storage_backend,
                "storage_backends_active": os.getenv("STORAGE_BACKENDS_ACTIVE", "local").split(","),
                "session_management_available": SESSION_MANAGEMENT_AVAILABLE,
                "session_management_enabled": SESSION_MANAGEMENT_AVAILABLE and self.postgres_enabled
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    def reset(self, components: Optional[List[str]] = None, preserve_structure: bool = True) -> Dict[str, Any]:
        """
        Reset specified components by removing data while preserving structure.
        
        Summary
        -------
        Safely resets system components by clearing data while maintaining
        database schemas, graph constraints, and directory structures.
        Provides granular control over which components to reset.
        
        Parameters
        ----------
        components : List[str], optional
            Components to reset: ['database', 'graph', 'storage'] (default: all enabled)
        preserve_structure : bool, optional
            If True, keep schemas/constraints/directories (default: True)
            
        Returns
        -------
        Dict[str, Any]
            Reset results with structure:
            {
                "success": bool,
                "components_reset": List[str],
                "details": Dict[str, str],
                "warnings": List[str]
            }
            
        Examples
        --------
        >>> setup = SetupService()
        >>> result = setup.reset(['database', 'storage'])
        >>> print(f"Reset: {result['components_reset']}")
        
        Notes
        -----
        - Safe operation - preserves schemas and structure by default
        - Never resets system_logs table structure (managed by logging.py)
        - For system_logs: only clears old data, preserves recent entries
        - Protected buckets (models) are excluded from reset operations
        - Protected buckets contain valuable assets and are preserved
        - Granular control over which components to reset
        - Logs all reset operations for audit trail
        """
        logger.info("Starting component reset", source="setup_service",
                   components=components, preserve_structure=preserve_structure)
        
        if components is None:
            components = []
            if self.postgres_enabled:
                components.append("database")
            if self.neo4j_enabled:
                components.append("graph")
            components.append("storage")
        
        result = {
            "success": True,
            "components_reset": [],
            "details": {},
            "warnings": []
        }
        
        # Reset session management first (due to foreign key dependencies)
        if "database" in components and SESSION_MANAGEMENT_AVAILABLE and self.postgres_enabled and self.postgres_client:
            try:
                # Clear session management data first to avoid foreign key conflicts
                session_tables = ["resource_allocations", "storage_allocations", "user_sessions", "users"]
                reset_session_count = 0
                
                for table in session_tables:
                    try:
                        # Check if table exists before trying to truncate
                        check_result = self.postgres_client.run(
                            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)",
                            (table,)
                        )
                        
                        if check_result and len(check_result) > 0 and check_result[0][0]:
                            self.postgres_client.run(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
                            reset_session_count += 1
                            logger.info(f"Reset session table data", source="setup_service", table=table)
                    except Exception as e:
                        # Non-fatal if table doesn't exist
                        logger.debug(f"Session table reset skipped (may not exist)", source="setup_service",
                                   table=table, error=str(e))
                
                if reset_session_count > 0:
                    result["components_reset"].append("session_management")
                    result["details"]["session_management"] = f"Reset {reset_session_count} session tables"
                    logger.info("Reset session management data", source="setup_service", 
                               tables_reset=reset_session_count)
                
            except Exception as e:
                result["warnings"].append(f"Session management reset failed: {str(e)}")
                logger.warning("Session management reset failed", source="setup_service", error=str(e))
        
        # Reset database
        if "database" in components and self.postgres_enabled and self.postgres_client:
            try:
                # Clear table data but preserve structure
                # NEVER reset system_logs table structure - only clear data if needed
                # system_logs table is managed by logging.py
                tables = ["datasets_metadata", "extraction_metadata", "models_metadata"]
                for table in tables:
                    try:
                        self.postgres_client.run(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
                        logger.info(f"Reset table data", source="setup_service", table=table)
                    except Exception as e:
                        result["warnings"].append(f"Failed to reset table {table}: {str(e)}")
                
                # For system_logs, only clear records if explicitly requested (not structure)
                if preserve_structure:
                    try:
                        # Only clear data, not structure - system_logs is managed by logging.py
                        self.postgres_client.run("DELETE FROM system_logs WHERE created_at < NOW() - INTERVAL '1 hour'")
                        logger.info("Cleared old system_logs data (preserving recent entries)", source="setup_service")
                    except Exception as e:
                        result["warnings"].append(f"Failed to clear old system_logs data: {str(e)}")
                
                result["components_reset"].append("database")
                result["details"]["database"] = f"Reset {len(tables)} tables (system_logs data partially cleared)"
                
            except Exception as e:
                result["warnings"].append(f"Database reset failed: {str(e)}")
                result["success"] = False
        
        # Reset graph
        if "graph" in components and self.neo4j_enabled and self.neo4j_client:
            try:
                # Clear all nodes and relationships but preserve constraints
                self.neo4j_client.run("MATCH (n) DETACH DELETE n")
                result["components_reset"].append("graph")
                result["details"]["graph"] = "Cleared all nodes and relationships"
                logger.info("Reset graph database", source="setup_service")
                
            except Exception as e:
                result["warnings"].append(f"Graph reset failed: {str(e)}")
                result["success"] = False
        
        # Reset storage (clear ALL buckets and files across ALL backends)
        if "storage" in components:
            try:
                reset_details = []
                
                if self.storage_manager:
                    # Get current storage strategy info to understand multi-backend setup
                    strategy_info = self.storage_manager.get_strategy_info()
                    logger.info("Resetting storage across all backends", source="setup_service",
                               strategy=strategy_info['strategy'], 
                               backend_count=strategy_info['backend_count'],
                               affects_all=strategy_info['affects_all_backends'])
                    
                    # For setup operations, we need to reset ALL backends regardless of strategy
                    # This overrides normal strategy constraints during setup
                    
                    # 1. Get all buckets from all backends (aggregated view)
                    try:
                        all_buckets = self.storage_manager.list_buckets()
                        bucket_names = list(set([bucket.get("name") or bucket.get("$id") for bucket in all_buckets if bucket.get("name") or bucket.get("$id")]))
                        
                        # Exclude models bucket from reset operations (preserve valuable models)
                        protected_buckets = self._get_protected_buckets()
                        resetable_buckets = [name for name in bucket_names if name not in protected_buckets]
                        excluded_buckets = [name for name in bucket_names if name in protected_buckets]
                        
                        logger.info(f"Found {len(bucket_names)} buckets total: {len(resetable_buckets)} to reset, {len(excluded_buckets)} protected", 
                                   source="setup_service", 
                                   resetable=resetable_buckets, 
                                   protected=excluded_buckets)
                        
                        # 2. Delete only non-protected buckets (this will affect all backends based on strategy)
                        deleted_buckets = []
                        for bucket_name in resetable_buckets:
                            try:
                                success = self.storage_manager.delete_bucket(bucket_name)
                                if success:
                                    deleted_buckets.append(bucket_name)
                                    logger.info(f"Deleted bucket from all backends", source="setup_service", bucket=bucket_name)
                                else:
                                    result["warnings"].append(f"Failed to delete bucket: {bucket_name}")
                            except Exception as e:
                                result["warnings"].append(f"Error deleting bucket {bucket_name}: {str(e)}")
                        
                        if excluded_buckets:
                            reset_details.append(f"Deleted {len(deleted_buckets)} buckets across all backends (protected: {', '.join(excluded_buckets)})")
                        else:
                            reset_details.append(f"Deleted {len(deleted_buckets)} buckets across all backends")
                        
                        # Special handling for system_logs: clean file contents but preserve files
                        if "system_logs" in excluded_buckets:
                            logs_cleanup = self._cleanup_system_logs_files(preserve_recent_hours=1)
                            if logs_cleanup["success"]:
                                reset_details.append(f"System logs: {logs_cleanup['details']}")
                            else:
                                result["warnings"].append(f"System logs cleanup issue: {logs_cleanup['details']}")
                        
                        # 3. Recreate standard buckets if preserve_structure is True
                        if preserve_structure:
                            bucket_creation_result = self._create_standard_buckets_with_override()
                            if bucket_creation_result.get("success", False):
                                created_buckets = bucket_creation_result.get("buckets_created", [])
                                reset_details.append(f"Recreated {len(created_buckets)} standard buckets")
                                logger.info("Recreated standard buckets after reset", source="setup_service", 
                                           created=len(created_buckets))
                            else:
                                result["warnings"].append("Failed to recreate standard buckets after reset")
                        
                    except Exception as e:
                        result["warnings"].append(f"Storage bucket reset failed: {str(e)}")
                    
                    # 4. Log multi-backend impact
                    if strategy_info['affects_all_backends']:
                        reset_details.append(f"Reset affected all {strategy_info['backend_count']} backends ({', '.join(strategy_info['backend_types'])})")
                    else:
                        reset_details.append(f"Reset affected primary backend only (strategy: {strategy_info['strategy']})")
                
                else:
                    reset_details.append("Storage manager not available - basic directory cleanup performed")
                    # Fallback: basic directory cleanup for local storage only
                    try:
                        from polymer_extractor.utils.paths import PUBLIC_DIR
                        public_path = Path(PUBLIC_DIR)
                        if public_path.exists():
                            # Don't actually delete directories during reset - too dangerous
                            # Just mark for cleanup or leave as-is
                            reset_details.append("Local storage directories preserved")
                    except Exception as e:
                        result["warnings"].append(f"Local directory handling failed: {str(e)}")
                
                result["components_reset"].append("storage")
                result["details"]["storage"] = "; ".join(reset_details)
                logger.info("Storage reset completed", source="setup_service", details=reset_details)
                
            except Exception as e:
                result["warnings"].append(f"Storage reset failed: {str(e)}")
                result["success"] = False
        
        logger.info("Component reset completed", source="setup_service",
                   success=result["success"], components_reset=result["components_reset"])
        
        return result

    def wipe_data(self, preserve_structure: bool = True, confirm_wipe: bool = False) -> Dict[str, Any]:
        """
        Remove all data while preserving schemas and structure.
        
        Summary
        -------
        Performs comprehensive data removal across all components while
        optionally preserving database schemas, graph constraints, and
        directory structures. Requires explicit confirmation for safety.
        
        For storage operations, this affects ALL configured backends regardless
        of the normal strategy constraints, ensuring complete data removal
        across the distributed storage system.
        
        Parameters
        ----------
        preserve_structure : bool, optional
            If True, keep schemas/constraints/directories (default: True)
        confirm_wipe : bool, optional
            Explicit confirmation required for data wipe (default: False)
            
        Returns
        -------
        Dict[str, Any]
            Wipe results with structure:
            {
                "success": bool,
                "data_wiped": bool,
                "components_affected": List[str],
                "details": str,
                "warnings": List[str],
                "backend_impact": Dict[str, Any]
            }
            
        Raises
        ------
        ValueError
            If confirm_wipe is False (safety mechanism)
            
        Examples
        --------
        >>> setup = SetupService()
        >>> result = setup.wipe_data(confirm_wipe=True)
        >>> print(f"Wiped: {result['data_wiped']}")
        >>> print(f"Backends affected: {result['backend_impact']}")
        
        Notes
        -----
        - Requires explicit confirmation for safety
        - Preserves structure by default
        - Protected buckets (models) are excluded from wipe operations
        - Affects ALL configured storage backends during setup
        - Comprehensive logging for audit trail
        - Use with extreme caution in production
        """
        if not confirm_wipe:
            raise ValueError("Data wipe requires explicit confirmation (confirm_wipe=True)")
        
        logger.warning("Starting COMPLETE data wipe operation", source="setup_service",
                      preserve_structure=preserve_structure, confirm_wipe=confirm_wipe)
        
        # Get storage strategy info before wiping for impact assessment
        backend_impact = {"strategy": "unknown", "backends_affected": 0, "backend_types": []}
        if self.storage_manager:
            try:
                strategy_info = self.storage_manager.get_strategy_info()
                backend_impact = {
                    "strategy": strategy_info['strategy'],
                    "backends_affected": strategy_info['backend_count'],
                    "backend_types": strategy_info['backend_types'],
                    "affects_all_backends": strategy_info['affects_all_backends']
                }
                logger.warning("Data wipe will affect storage backends", source="setup_service",
                              strategy=strategy_info['strategy'],
                              backend_count=strategy_info['backend_count'],
                              backend_types=strategy_info['backend_types'])
            except Exception as e:
                logger.warning("Could not assess backend impact before wipe", source="setup_service", error=str(e))
        
        # Use enhanced reset functionality with all components
        reset_result = self.reset(
            components=["database", "graph", "storage"],
            preserve_structure=preserve_structure
        )
        
        # Enhance result with wipe-specific information
        wipe_result = {
            "success": reset_result.get("success", False),
            "data_wiped": reset_result.get("success", False),
            "components_affected": reset_result.get("components_reset", []),
            "details": f"Complete data wipe performed: {'; '.join([f'{k}: {v}' for k, v in reset_result.get('details', {}).items()])}",
            "warnings": reset_result.get("warnings", []),
            "backend_impact": backend_impact
        }
        
        if wipe_result["success"]:
            logger.warning("Data wipe completed successfully", source="setup_service",
                          components=wipe_result["components_affected"],
                          backend_impact=backend_impact)
        else:
            logger.error("Data wipe completed with errors", source="setup_service",
                        warnings=wipe_result["warnings"],
                        backend_impact=backend_impact)
        
        return wipe_result

    def sync_models_from_github(self, force_redownload: bool = False) -> Dict[str, Any]:
        """
        Synchronize models and tokenizers from GitHub repositories.
        
        Summary
        -------
        Phase 2 enhancement for GitHub-based models synchronization. Downloads 
        latest models and tokenizers from configured GitHub repositories, validates
        version compatibility, and updates local models directory atomically.
        
        Parameters
        ----------
        force_redownload : bool, optional
            Force redownload even if models exist (default: False)
            
        Returns
        -------
        Dict[str, Any]
            Sync results with structure:
            {
                "success": bool,
                "service_available": bool,
                "models_synced": int,
                "tokenizers_synced": int,
                "version_validated": bool,
                "errors": List[str],
                "duration_seconds": float
            }
            
        Examples
        --------
        >>> setup = SetupService()
        >>> result = setup.sync_models_from_github(force_redownload=True)
        >>> if result["success"]:
        ...     print(f"Synced {result['models_synced']} models")
        ... else:
        ...     print(f"Errors: {result['errors']}")
        
        Notes
        -----
        - Atomic operation: either fully succeeds or rolls back
        - Requires GITHUB_TOKEN, TOKENIZERS_REMOTE_URL, FINETUNED_REMOTE_URL
        - Integrates with protected bucket logic for models storage
        - Part of Phase 2 setup enhancements for models folder GitHub sync
        """
        logger.info("Starting GitHub models sync via setup service", source="setup_service", 
                   force_redownload=force_redownload)
        
        result = {
            "success": False,
            "service_available": MODELS_SYNC_AVAILABLE,
            "models_synced": 0,
            "tokenizers_synced": 0,
            "version_validated": False,
            "errors": [],
            "duration_seconds": 0.0
        }
        
        if not MODELS_SYNC_AVAILABLE:
            error_msg = "Models sync service not available - ModelsSyncService import failed"
            result["errors"].append(error_msg)
            logger.error(error_msg, source="setup_service")
            return result
        
        try:
            start_time = datetime.utcnow()
            
            # Initialize models sync service
            models_sync_service = ModelsSyncService(logger=logger)
            
            # Perform GitHub sync
            sync_result = models_sync_service.sync_models_from_github(force_redownload=force_redownload)
            
            # Map results
            result["success"] = sync_result["success"]
            result["models_synced"] = sync_result["models_synced"]
            result["tokenizers_synced"] = sync_result["tokenizers_synced"]
            result["version_validated"] = sync_result["version_validated"]
            result["errors"] = sync_result.get("errors", [])
            
            end_time = datetime.utcnow()
            result["duration_seconds"] = (end_time - start_time).total_seconds()
            
            if result["success"]:
                logger.info("GitHub models sync completed successfully via setup service", 
                           source="setup_service", 
                           models_synced=result["models_synced"],
                           tokenizers_synced=result["tokenizers_synced"])
            else:
                logger.error("GitHub models sync failed via setup service", 
                           source="setup_service", errors=result["errors"])
                           
        except Exception as e:
            error_msg = f"Unexpected error during models sync: {str(e)}"
            result["errors"].append(error_msg)
            logger.error(error_msg, source="setup_service", error=str(e))
        
        return result

    def get_session_management_status(self) -> Dict[str, Any]:
        """
        Get detailed session management configuration and status.
        
        Summary
        -------
        Returns comprehensive information about multi-user session management
        including availability, configuration, health status, and current
        session statistics for monitoring and administrative purposes.
        
        Returns
        -------
        Dict[str, Any]
            Session management status with structure:
            {
                "available": bool,
                "enabled": bool,
                "components": {
                    "session_repository": bool,
                    "session_manager": bool,
                    "production_config": bool
                },
                "configuration": Dict[str, Any],
                "statistics": Dict[str, Any],
                "health": Dict[str, Any]
            }
            
        Examples
        --------
        >>> setup = SetupService()
        >>> status = setup.get_session_management_status()
        >>> print(f"Available: {status['available']}")
        >>> print(f"Active sessions: {status['statistics']['active_sessions']}")
        
        Notes
        -----
        - Safe to call even if session management is not available
        - Provides detailed component-level status information
        - Includes current session statistics when available
        - Useful for administrative dashboards and capacity planning
        """
        logger.debug("Getting session management status", source="setup_service")
        
        result = {
            "available": SESSION_MANAGEMENT_AVAILABLE,
            "enabled": SESSION_MANAGEMENT_AVAILABLE and self.postgres_enabled,
            "components": {
                "session_repository": self.session_repository is not None,
                "session_manager": self.session_manager is not None,
                "production_config": ProductionConfig is not None
            },
            "configuration": {},
            "statistics": {},
            "health": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if not SESSION_MANAGEMENT_AVAILABLE:
            result["details"] = "Session management components not available"
            return result
        
        if not self.postgres_enabled:
            result["details"] = "Session management requires PostgreSQL"
            return result
        
        # Get configuration if ProductionConfig is available
        if ProductionConfig:
            try:
                # Get development configuration as reference (safe default)
                dev_config = ProductionConfig.get_environment_config("development")
                result["configuration"] = {
                    "max_concurrent_sessions": dev_config.get("MAX_CONCURRENT_SESSIONS", "unknown"),
                    "session_timeout_minutes": dev_config.get("SESSION_TIMEOUT_MINUTES", "unknown"),
                    "resource_sharing_strategy": dev_config.get("RESOURCE_SHARING_STRATEGY", "unknown"),
                    "user_storage_isolation": dev_config.get("USER_STORAGE_ISOLATION", "unknown"),
                    "current_environment": os.getenv("DEPLOYMENT_ENVIRONMENT", "development")
                }
            except Exception as e:
                result["configuration"] = {"error": f"Configuration access failed: {str(e)}"}
        
        # Get session statistics if session_repository is available
        if self.session_repository:
            try:
                # Get basic session statistics - use safe methods
                active_sessions_result = self.session_repository.count_active_sessions()
                user_count_result = self.session_repository.count_total_users()
                
                result["statistics"] = {
                    "active_sessions": active_sessions_result,
                    "total_users": user_count_result,
                    "last_updated": datetime.utcnow().isoformat()
                }
            except Exception as e:
                result["statistics"] = {"error": f"Statistics access failed: {str(e)}"}
        
        # Get health status if session_repository is available
        if self.session_repository:
            try:
                health_check = self.session_repository.health_check() if hasattr(self.session_repository, 'health_check') else {"status": "unknown"}
                result["health"] = health_check
            except Exception as e:
                result["health"] = {"status": "error", "error": str(e)}
        
        return result

    def validate_models_versions(self) -> Dict[str, Any]:
        """
        Validate version compatibility between existing models and tokenizers.
        
        Summary
        -------
        Phase 2 enhancement for models version validation. Checks all models and 
        tokenizers in the models directory for version compatibility and structural
        completeness. Provides detailed analysis of each model-tokenizer pair.
        
        Returns
        -------
        Dict[str, Any]
            Validation results with structure:
            {
                "valid": bool,
                "service_available": bool,
                "models_checked": int,
                "compatible_pairs": int,
                "incompatible_pairs": int,
                "missing_components": List[str],
                "validation_details": List[Dict[str, Any]],
                "recommended_actions": List[str]
            }
            
        Examples
        --------
        >>> setup = SetupService()
        >>> result = setup.validate_models_versions()
        >>> if result["valid"]:
        ...     print("All models validated successfully")
        ... else:
        ...     print(f"Issues found: {result['recommended_actions']}")
        
        Notes
        -----
        - Checks for required model files (config.json, pytorch_model.bin)
        - Validates tokenizer files (tokenizer_config.json, vocab.txt)
        - Verifies version metadata consistency
        - Part of Phase 2 setup enhancements for models folder version validation
        """
        logger.info("Starting models version validation via setup service", source="setup_service")
        
        result = {
            "valid": False,
            "service_available": MODELS_SYNC_AVAILABLE,
            "models_checked": 0,
            "compatible_pairs": 0,
            "incompatible_pairs": 0,
            "missing_components": [],
            "validation_details": [],
            "recommended_actions": []
        }
        
        if not MODELS_SYNC_AVAILABLE:
            error_msg = "Models sync service not available - ModelsSyncService import failed"
            result["recommended_actions"].append(error_msg)
            logger.error(error_msg, source="setup_service")
            return result
        
        try:
            # Initialize models sync service
            models_sync_service = ModelsSyncService(logger=logger)
            
            # Perform validation
            validation_result = models_sync_service.validate_models_versions()
            
            # Map results
            result.update(validation_result)
            result["service_available"] = True
            
            if result["valid"]:
                logger.info("Models version validation completed successfully via setup service", 
                           source="setup_service", models_checked=result["models_checked"])
            else:
                logger.warning("Models version validation found issues via setup service", 
                             source="setup_service", 
                             incompatible_pairs=result["incompatible_pairs"],
                             missing_components=result["missing_components"])
                             
        except Exception as e:
            error_msg = f"Unexpected error during models validation: {str(e)}"
            result["recommended_actions"].append(error_msg)
            logger.error(error_msg, source="setup_service", error=str(e))
        
        return result


# Factory function for easy access
def get_setup_service() -> SetupService:
    """
    Get SetupService instance.
    
    Summary
    -------
    Factory function that returns a SetupService instance with proper
    configuration and initialization.
    
    Returns
    -------
    SetupService
        Configured setup service instance
        
    Examples
    --------
    >>> setup = get_setup_service()
    >>> health = setup.check_health()
    """
    return SetupService()


if __name__ == "__main__":
    # Example usage and testing
    setup = SetupService()
    print("SetupService initialized")
    
    # Get environment info
    env_info = setup.get_environment_info()
    print(f"Environment: PostgreSQL={env_info['postgres_enabled']}, Neo4j={env_info['neo4j_enabled']}")
    
    # Check health
    health = setup.check_health()
    print(f"Health: {health['overall_status']}")
    
    # Initialize system
    if env_info['postgres_enabled'] or env_info['neo4j_enabled']:
        init_result = setup.initialize()
        print(f"Initialization: {init_result['success']}")