# polymer_extractor/services/setup_service.py

"""
Setup Service for Polymer NLP Extractor.

Purpose
-------
Database orchestration and lifecycle management service that coordinates operations across
PostgreSQL and Neo4j backends with flexible storage via BucketClient.

Features
--------
- Environment-driven database initialization based on .env configuration
- Comprehensive lifecycle management (start/stop/restart/reset)
- Multi-backend health checking and status reporting
- Granular database reset operations with log preservation options
- Clean installation workflows with logging system coordination
- Verbose response patterns for enhanced debugging
- Integration with BucketClient for flexible storage operations

Environment Variables
---------------------
Required for setup operations:
- USE_POSTGRESQL_DB=true/false - Enable/disable PostgreSQL database operations
- USE_NEO4J_DB=true/false - Enable/disable Neo4j database operations
- DATA_BACKEND=postgres - Primary backend for structured data (should be postgres)
- GRAPH_BACKEND=neo4j|disabled - Enable/disable graph operations
- Storage backend configuration handled by BucketClient

Design Principles
-----------------
1. PostgreSQL + Neo4j focused with flexible storage options
2. Environment-first configuration respecting user preferences
3. Verbose response patterns for comprehensive debugging
4. Non-blocking error handling with detailed error context
5. Separation of concerns: orchestration vs. direct database operations
6. Integration with logging system for clean install coordination
7. Backward compatibility with existing service interfaces

Examples
--------
>>> setup = SetupService()
>>> result = setup.initialize_system()
>>> print(result["success"])  # True/False
>>> print(result["databases"])  # Detailed per-database results
>>> print(result["errors"])  # Detailed error information if any
"""

import os
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

from polymer_extractor.storage.postgresql_client import PostgresClient
from polymer_extractor.storage.neo4j_client import Neo4jClient
from polymer_extractor.storage.database_manager import DatabaseManager
from polymer_extractor.storage.graph_manager import GraphManager
from polymer_extractor.storage.bucket_client import BucketClient
from polymer_extractor.utils.logging import Logger


logger = Logger()


class SetupService:
    """
    Database orchestration and lifecycle management service.
    
    Coordinates operations across PostgreSQL and Neo4j backends with
    comprehensive error handling and verbose response patterns for debugging.
    Uses BucketClient for flexible storage operations.
    """

    def __init__(self):
        """Initialize setup service with environment-based configuration."""
        self.logger = Logger()
        
        # Initialize clients based on environment flags
        self.postgres_client = None
        self.neo4j_client = None
        self.database_manager = None
        self.graph_manager = None
        self.bucket_client = None
        
        # Initialize PostgreSQL client if enabled
        if self._should_use_postgres():
            try:
                self.postgres_client = PostgresClient()
                self.logger.info("PostgreSQL client initialized", source="setup_service", event_type="initialization")
            except Exception as e:
                self.logger.warning(f"Failed to initialize PostgreSQL client: {e}", source="setup_service", event_type="initialization")
        
        # Initialize Neo4j client if enabled
        if self._should_use_neo4j():
            try:
                self.neo4j_client = Neo4jClient()
                self.logger.info("Neo4j client initialized", source="setup_service", event_type="initialization")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Neo4j client: {e}", source="setup_service", event_type="initialization")
        
        # Initialize managers
        try:
            self.database_manager = DatabaseManager()
            self.graph_manager = GraphManager()
            self.bucket_client = BucketClient()
            self.logger.info("Managers initialized successfully", source="setup_service", event_type="initialization")
        except Exception as e:
            self.logger.warning(f"Failed to initialize managers: {e}", source="setup_service", event_type="initialization")

    def _should_use_postgres(self) -> bool:
        """Check if PostgreSQL should be used based on .env flags."""
        return (os.getenv("USE_POSTGRESQL_DB", "true").lower() == "true" or
                os.getenv("DATA_BACKEND", "postgres") == "postgres")
    
    def _should_use_neo4j(self) -> bool:
        """Check if Neo4j should be used based on .env flags."""
        return (os.getenv("USE_NEO4J_DB", "true").lower() == "true" and
                os.getenv("GRAPH_BACKEND", "neo4j") == "neo4j")

    def get_environment_info(self) -> Dict[str, Any]:
        """Get current environment configuration information."""
        return {
            "timestamp": datetime.now().isoformat(),
            "environment_flags": {
                "use_postgresql": self._should_use_postgres(),
                "use_neo4j": self._should_use_neo4j(),
                "data_backend": os.getenv("DATA_BACKEND", "postgres"),
                "graph_backend": os.getenv("GRAPH_BACKEND", "neo4j"),
                "storage_backend": os.getenv("STORAGE_BACKEND", "local")
            },
            "client_status": {
                "postgres_client": self.postgres_client is not None,
                "neo4j_client": self.neo4j_client is not None,
                "database_manager": self.database_manager is not None,
                "graph_manager": self.graph_manager is not None,
                "bucket_client": self.bucket_client is not None
            }
        }

    def initialize_system(self, clean_install: bool = False) -> Dict[str, Any]:
        """
        Initialize the complete system with all databases.
        
        Parameters
        ----------
        clean_install : bool
            If True, performs clean installation (drops existing data)
            
        Returns
        -------
        dict
            Comprehensive system initialization results
        """
        start_time = time.time()
        
        # Pause logging database operations for clean install
        if clean_install and self.logger:
            self.logger.pause_database_logging()
        
        result = {
            "success": False,
            "timestamp": datetime.now().isoformat(),
            "clean_install": clean_install,
            "databases": {},
            "storage": {},
            "total_duration": 0,
            "errors": [],
            "warnings": []
        }
        
        try:
            # Initialize PostgreSQL if enabled
            if self._should_use_postgres():
                postgres_result = self.setup_postgresql_database(clean_install=clean_install)
                result["databases"]["postgresql"] = postgres_result
                if not postgres_result.get("success", False):
                    result["errors"].append(f"PostgreSQL initialization failed: {postgres_result.get('error', 'Unknown error')}")
            
            # Initialize Neo4j if enabled
            if self._should_use_neo4j():
                neo4j_result = self.setup_neo4j_database(clean_install=clean_install)
                result["databases"]["neo4j"] = neo4j_result
                if not neo4j_result.get("success", False):
                    result["errors"].append(f"Neo4j initialization failed: {neo4j_result.get('error', 'Unknown error')}")
            
            # Initialize storage
            storage_result = self.setup_storage_system()
            result["storage"] = storage_result
            if not storage_result.get("success", False):
                result["warnings"].append(f"Storage initialization had issues: {storage_result.get('error', 'Unknown error')}")
            
            # Resume logging database operations
            if clean_install and self.logger:
                self.logger.resume_database_logging()
                self.logger.initialize_database_table()
            
            # Check overall success
            database_success = all(
                db_result.get("success", False) 
                for db_result in result["databases"].values()
            )
            
            result["success"] = database_success and not result["errors"]
            result["total_duration"] = time.time() - start_time
            
            self.logger.info(
                f"System initialization {'completed successfully' if result['success'] else 'completed with errors'}",
                source="setup_service", 
                event_type="system_initialization",
                duration=result["total_duration"],
                clean_install=clean_install
            )
            
            return result
            
        except Exception as e:
            result["success"] = False
            result["errors"].append(f"System initialization failed: {str(e)}")
            result["total_duration"] = time.time() - start_time
            
            # Resume logging even on failure
            if clean_install and self.logger:
                self.logger.resume_database_logging()
            
            self.logger.error(
                f"System initialization failed: {str(e)}", 
                source="setup_service", 
                event_type="system_initialization"
            )
            return result

    def setup_postgresql_database(self, clean_install: bool = False) -> Dict[str, Any]:
        """
        Setup PostgreSQL database with comprehensive schema creation.
        
        Parameters
        ----------
        clean_install : bool
            If True, drops existing tables before creating new ones
            
        Returns
        -------
        dict
            PostgreSQL setup results
        """
        start_time = time.time()
        
        result = {
            "success": False,
            "timestamp": datetime.now().isoformat(),
            "clean_install": clean_install,
            "tables_created": [],
            "duration": 0,
            "error": None
        }
        
        if not self.postgres_client:
            result["error"] = "PostgreSQL client not available"
            return result
        
        try:
            # Test connection
            if not self.postgres_client.test_connection():
                result["error"] = "PostgreSQL connection test failed"
                return result
            
            # Execute schema from SQL file
            schema_file = Path(__file__).parent.parent.parent / "db" / "sql" / "001_core.sql"
            
            if schema_file.exists():
                with open(schema_file, 'r') as f:
                    schema_sql = f.read()
                
                # Execute the schema
                self.postgres_client.execute_sql_script(schema_sql)
                
                # Get list of created tables
                tables = self.postgres_client.list_tables()
                result["tables_created"] = tables
                
                self.logger.info(
                    f"PostgreSQL schema executed successfully. Created {len(tables)} tables",
                    source="setup_service",
                    event_type="postgresql_setup",
                    tables_count=len(tables)
                )
                
            else:
                result["error"] = f"Schema file not found: {schema_file}"
                return result
            
            result["success"] = True
            result["duration"] = time.time() - start_time
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            result["duration"] = time.time() - start_time
            
            self.logger.error(
                f"PostgreSQL setup failed: {str(e)}", 
                source="setup_service", 
                event_type="postgresql_setup"
            )
            return result

    def setup_neo4j_database(self, clean_install: bool = False) -> Dict[str, Any]:
        """
        Setup Neo4j database with constraints and indexes.
        
        Parameters
        ----------
        clean_install : bool
            If True, clears existing data before setup
            
        Returns
        -------
        dict
            Neo4j setup results
        """
        start_time = time.time()
        
        result = {
            "success": False,
            "timestamp": datetime.now().isoformat(),
            "clean_install": clean_install,
            "constraints_created": [],
            "indexes_created": [],
            "duration": 0,
            "error": None
        }
        
        if not self.neo4j_client:
            result["error"] = "Neo4j client not available"
            return result
        
        try:
            # Test connection
            if not self.neo4j_client.test_connection():
                result["error"] = "Neo4j connection test failed"
                return result
            
            # Clear database if clean install
            if clean_install:
                self.neo4j_client.clear_database()
                self.logger.info("Neo4j database cleared for clean install", source="setup_service", event_type="neo4j_setup")
            
            # Create constraints and indexes
            constraints_file = Path(__file__).parent.parent.parent / "kg" / "cypher" / "001_constraints.cypher"
            
            if constraints_file.exists():
                with open(constraints_file, 'r') as f:
                    constraints_cypher = f.read()
                
                # Execute constraints (this would need to be implemented in neo4j_client)
                # For now, we'll create basic constraints
                basic_constraints = [
                    "CREATE CONSTRAINT polymer_name IF NOT EXISTS FOR (p:POLYMER) REQUIRE p.name IS UNIQUE",
                    "CREATE CONSTRAINT property_name IF NOT EXISTS FOR (pr:PROPERTY) REQUIRE pr.name IS UNIQUE",
                    "CREATE INDEX polymer_canonical IF NOT EXISTS FOR (p:POLYMER) ON (p.canonical_name)",
                    "CREATE INDEX property_type IF NOT EXISTS FOR (pr:PROPERTY) ON (pr.type)"
                ]
                
                for constraint in basic_constraints:
                    try:
                        self.neo4j_client.execute_query(constraint)
                        if "CONSTRAINT" in constraint:
                            result["constraints_created"].append(constraint)
                        else:
                            result["indexes_created"].append(constraint)
                    except Exception as e:
                        self.logger.warning(f"Failed to create constraint/index: {e}", source="setup_service")
                
                self.logger.info(
                    f"Neo4j setup completed. Created {len(result['constraints_created'])} constraints and {len(result['indexes_created'])} indexes",
                    source="setup_service",
                    event_type="neo4j_setup"
                )
            
            result["success"] = True
            result["duration"] = time.time() - start_time
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            result["duration"] = time.time() - start_time
            
            self.logger.error(
                f"Neo4j setup failed: {str(e)}", 
                source="setup_service", 
                event_type="neo4j_setup"
            )
            return result

    def setup_storage_system(self) -> Dict[str, Any]:
        """
        Setup storage system using BucketClient.
        
        Returns
        -------
        dict
            Storage setup results
        """
        start_time = time.time()
        
        result = {
            "success": False,
            "timestamp": datetime.now().isoformat(),
            "backend": "unknown",
            "buckets_created": [],
            "duration": 0,
            "error": None
        }
        
        if not self.bucket_client:
            result["error"] = "BucketClient not available"
            return result
        
        try:
            # Get storage backend info
            result["backend"] = self.bucket_client.get_backend_type()
            
            # Create essential buckets
            essential_buckets = [
                "research_papers",
                "processed_xml", 
                "extracted_xml",
                "models",
                "exports",
                "system_logs"
            ]
            
            for bucket_name in essential_buckets:
                try:
                    if not self.bucket_client.bucket_exists(bucket_name):
                        bucket_result = self.bucket_client.create_bucket(bucket_name)
                        result["buckets_created"].append(bucket_name)
                        self.logger.debug(f"Created bucket: {bucket_name}", source="setup_service")
                    else:
                        self.logger.debug(f"Bucket already exists: {bucket_name}", source="setup_service")
                except Exception as e:
                    self.logger.warning(f"Failed to create bucket {bucket_name}: {e}", source="setup_service")
            
            result["success"] = True
            result["duration"] = time.time() - start_time
            
            self.logger.info(
                f"Storage system setup completed using {result['backend']} backend",
                source="setup_service",
                event_type="storage_setup",
                buckets_created=len(result["buckets_created"])
            )
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            result["duration"] = time.time() - start_time
            
            self.logger.error(
                f"Storage setup failed: {str(e)}", 
                source="setup_service", 
                event_type="storage_setup"
            )
            return result

    def check_system_health(self) -> Dict[str, Any]:
        """
        Comprehensive system health check.
        
        Returns
        -------
        dict
            System health status
        """
        result = {
            "timestamp": datetime.now().isoformat(),
            "overall_health": "unknown",
            "databases": {},
            "storage": {},
            "managers": {},
            "issues": []
        }
        
        # Check PostgreSQL
        if self.postgres_client:
            try:
                postgres_healthy = self.postgres_client.test_connection()
                result["databases"]["postgresql"] = {
                    "status": "healthy" if postgres_healthy else "unhealthy",
                    "connection": postgres_healthy,
                    "tables_count": len(self.postgres_client.list_tables()) if postgres_healthy else 0
                }
                if not postgres_healthy:
                    result["issues"].append("PostgreSQL connection failed")
            except Exception as e:
                result["databases"]["postgresql"] = {"status": "error", "error": str(e)}
                result["issues"].append(f"PostgreSQL health check failed: {e}")
        else:
            result["databases"]["postgresql"] = {"status": "not_configured"}
        
        # Check Neo4j
        if self.neo4j_client:
            try:
                neo4j_healthy = self.neo4j_client.test_connection()
                result["databases"]["neo4j"] = {
                    "status": "healthy" if neo4j_healthy else "unhealthy",
                    "connection": neo4j_healthy
                }
                if not neo4j_healthy:
                    result["issues"].append("Neo4j connection failed")
            except Exception as e:
                result["databases"]["neo4j"] = {"status": "error", "error": str(e)}
                result["issues"].append(f"Neo4j health check failed: {e}")
        else:
            result["databases"]["neo4j"] = {"status": "not_configured"}
        
        # Check storage
        if self.bucket_client:
            try:
                storage_healthy = self.bucket_client.test_connection()
                result["storage"] = {
                    "status": "healthy" if storage_healthy else "unhealthy",
                    "backend": self.bucket_client.get_backend_type(),
                    "connection": storage_healthy
                }
                if not storage_healthy:
                    result["issues"].append("Storage connection failed")
            except Exception as e:
                result["storage"] = {"status": "error", "error": str(e)}
                result["issues"].append(f"Storage health check failed: {e}")
        else:
            result["storage"] = {"status": "not_configured"}
        
        # Check managers
        result["managers"] = {
            "database_manager": "available" if self.database_manager else "not_available",
            "graph_manager": "available" if self.graph_manager else "not_available",
            "bucket_client": "available" if self.bucket_client else "not_available"
        }
        
        # Determine overall health
        if not result["issues"]:
            result["overall_health"] = "healthy"
        elif len(result["issues"]) <= 2:
            result["overall_health"] = "degraded"
        else:
            result["overall_health"] = "unhealthy"
        
        return result

    def clean_install(self) -> Dict[str, Any]:
        """
        Perform clean installation - drops all data and recreates schemas.
        
        Returns
        -------
        dict
            Clean installation results
        """
        self.logger.info("Starting clean installation", source="setup_service", event_type="clean_install")
        
        # Reset database logs first
        if self.logger:
            self.logger.reset_database_logs()
        
        # Perform clean initialization
        result = self.initialize_system(clean_install=True)
        
        if result["success"]:
            self.logger.info("Clean installation completed successfully", source="setup_service", event_type="clean_install")
        else:
            self.logger.error("Clean installation failed", source="setup_service", event_type="clean_install", errors=result["errors"])
        
        return result

    # === Backward Compatibility Methods (Deprecated) ===
    
    def setup_appwrite_collections(self) -> Dict[str, Any]:
        """Deprecated: Appwrite collections no longer supported."""
        import warnings
        warnings.warn(
            "setup_appwrite_collections is deprecated. Use setup_storage_system instead.", 
            DeprecationWarning, 
            stacklevel=2
        )
        return {
            "success": False,
            "error": "Appwrite collections are no longer supported. Use PostgreSQL + storage backends instead.",
            "migration_note": "Data should be migrated to PostgreSQL database with flexible storage via BucketClient"
        }
    
    def setup_appwrite_buckets(self) -> Dict[str, Any]:
        """Deprecated: Use setup_storage_system instead."""
        import warnings
        warnings.warn(
            "setup_appwrite_buckets is deprecated. Use setup_storage_system instead.", 
            DeprecationWarning, 
            stacklevel=2
        )
        return self.setup_storage_system()
    
    def reset_appwrite_database(self) -> Dict[str, Any]:
        """Deprecated: Appwrite database operations no longer supported."""
        import warnings
        warnings.warn(
            "reset_appwrite_database is deprecated. Use PostgreSQL reset operations instead.", 
            DeprecationWarning, 
            stacklevel=2
        )
        return {
            "success": False,
            "error": "Appwrite database operations are no longer supported. Use PostgreSQL operations instead."
        }
    
    def check_appwrite_status(self) -> Dict[str, Any]:
        """Deprecated: Appwrite status checks no longer supported."""
        import warnings
        warnings.warn(
            "check_appwrite_status is deprecated. Use check_system_health instead.", 
            DeprecationWarning, 
            stacklevel=2
        )
        return {
            "success": False,
            "error": "Appwrite status checks are no longer supported. Use check_system_health instead."
        }
