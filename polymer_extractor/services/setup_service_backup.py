# polymer_extractor/services/setup_service.py

"""
Enhanced Setup Service for Polymer NLP Extractor.

Purpose
-------
Database orchestration and lifecycle management service that coordinates operations across
all supported database backends: PostgreSQL, Neo4j, and Appwrite.

Features
--------
- Environment-driven database initialization based on .env.example flags
- Comprehensive lifecycle management (start/stop/restart/reset)
- Multi-backend health checking and status reporting
- Granular database reset operations with log preservation options
- Clean installation workflows
- Verbose response patterns for enhanced debugging
- Integration with Phase B enhanced clients and Phase C universal managers

Environment Variables
---------------------
Based on .env.example configuration (lines 12-19):
- USE_APPWRITE=true/false - Enable/disable Appwrite operations
- USE_APPWRITE_DB=true/false - Enable/disable Appwrite database operations  
- USE_POSTGRESQL_DB=true/false - Enable/disable PostgreSQL database operations
- USE_NEO4J_DB=true/false - Enable/disable Neo4j database operations
- DATA_BACKEND=postgres|appwrite - Primary backend for structured data
- GRAPH_BACKEND=neo4j|disabled - Enable/disable graph operations

Design Principles
-----------------
1. Environment-first configuration respecting user preferences
2. Verbose response patterns for comprehensive debugging
3. Non-blocking error handling with detailed error context
4. Separation of concerns: orchestration vs. direct database operations
5. Integration with model_config.py patterns and validation
6. Backward compatibility with existing service interfaces

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
from polymer_extractor.storage.bucket_manager import BucketManager
from polymer_extractor.utils.logging import Logger


logger = Logger()


class SetupService:
    """
    Enhanced database orchestration and lifecycle management service.
    
    Coordinates operations across PostgreSQL, Neo4j, and Appwrite backends with
    comprehensive error handling and verbose response patterns for debugging.
    """

    def __init__(self):
        """Initialize setup service with environment-based configuration."""
        self.logger = Logger()
        
        # Initialize clients based on environment flags
        self.postgres_client = None
        self.neo4j_client = None
        self.database_manager = None
        self.graph_manager = None
        self.bucket_manager = None
        
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
        
        # Initialize universal managers
        try:
            self.database_manager = DatabaseManager()
            self.logger.info("Database manager initialized", source="setup_service", event_type="initialization")
        except Exception as e:
            self.logger.warning(f"Failed to initialize database manager: {e}", source="setup_service", event_type="initialization")
        
        try:
            self.graph_manager = GraphManager()
            self.logger.info("Graph manager initialized", source="setup_service", event_type="initialization")
        except Exception as e:
            self.logger.warning(f"Failed to initialize graph manager: {e}", source="setup_service", event_type="initialization")
        
        # Initialize bucket manager if Appwrite is enabled
        if self._should_use_appwrite():
            try:
                self.bucket_manager = BucketManager()
                self.logger.info("Bucket manager initialized", source="setup_service", event_type="initialization")
            except Exception as e:
                self.logger.warning(f"Failed to initialize bucket manager: {e}", source="setup_service", event_type="initialization")
    
    def _should_use_postgres(self) -> bool:
        """Check if PostgreSQL should be used based on .env flags."""
        return (os.getenv("USE_POSTGRESQL_DB", "true").lower() == "true" or
                os.getenv("DATA_BACKEND", "appwrite") == "postgres")
        
    def _should_use_neo4j(self) -> bool:
        """Check if Neo4j should be used based on .env flags."""
        return (os.getenv("USE_NEO4J_DB", "true").lower() == "true" and
                os.getenv("GRAPH_BACKEND", "neo4j") == "neo4j")
        
    def _should_use_appwrite(self) -> bool:
        """Check if Appwrite should be used based on .env flags."""
        return (os.getenv("USE_APPWRITE", "true").lower() == "true" and
                os.getenv("USE_APPWRITE_DB", "true").lower() == "true")
    
    # === System Initialization ===
    def initialize_system(self) -> Dict[str, Any]:
        """
        Complete system initialization based on .env.example flags.
        
        Returns detailed results following grobid_service.py and token_packing_service.py patterns.
        
        Returns
        -------
        Dict[str, Any]
            Comprehensive initialization results with per-database status
        """
        start_time = time.time()
        self.logger.info("Starting complete system initialization", source="setup_service", event_type="system_initialization")
        
        result = {
            "success": False,
            "operation": "initialize_system",
            "timestamp": datetime.now().isoformat() + "Z",
            "environment_config": {
                "use_postgres": self._should_use_postgres(),
                "use_neo4j": self._should_use_neo4j(),
                "use_appwrite": self._should_use_appwrite(),
                "data_backend": os.getenv("DATA_BACKEND", "appwrite"),
                "graph_backend": os.getenv("GRAPH_BACKEND", "neo4j")
            },
            "databases": {},
            "managers_initialized": {
                "database_manager": self.database_manager is not None,
                "graph_manager": self.graph_manager is not None
            },
            "errors": [],
            "execution_time_seconds": 0,
            "total_operations": 0,
            "successful_operations": 0
        }
        
        total_operations = 0
        successful_operations = 0
        
        # Initialize PostgreSQL if enabled
        if self._should_use_postgres():
            total_operations += 1
            postgres_result = self.setup_postgres()
            result["databases"]["postgres"] = postgres_result
            
            if postgres_result.get("success", False):
                successful_operations += 1
                self.logger.info("PostgreSQL initialization successful", source="setup_service", event_type="system_initialization")
            else:
                result["errors"].append({
                    "database": "postgres",
                    "error": postgres_result.get("error", "Unknown error"),
                    "context": postgres_result.get("details", {})
                })
                self.logger.error("PostgreSQL initialization failed", source="setup_service", event_type="system_initialization")
        
        # Initialize Neo4j if enabled
        if self._should_use_neo4j():
            total_operations += 1
            neo4j_result = self.setup_neo4j()
            result["databases"]["neo4j"] = neo4j_result
            
            if neo4j_result.get("success", False):
                successful_operations += 1
                self.logger.info("Neo4j initialization successful", source="setup_service", event_type="system_initialization")
            else:
                result["errors"].append({
                    "database": "neo4j", 
                    "error": neo4j_result.get("error", "Unknown error"),
                    "context": neo4j_result.get("details", {})
                })
                self.logger.error("Neo4j initialization failed", source="setup_service", event_type="system_initialization")
        
        # Initialize Appwrite if enabled
        if self._should_use_appwrite():
            total_operations += 2  # Collections + Buckets
            
            # Setup Appwrite collections
            appwrite_result = self.setup_appwrite_collections()
            result["databases"]["appwrite"] = appwrite_result
            
            if appwrite_result.get("success", False):
                successful_operations += 1
                self.logger.info("Appwrite collections initialization successful", source="setup_service", event_type="system_initialization")
                
                # Setup Appwrite buckets
                bucket_result = self.setup_appwrite_buckets()
                result["databases"]["appwrite_buckets"] = bucket_result
                
                if bucket_result.get("success", False):
                    successful_operations += 1
                    self.logger.info("Appwrite buckets initialization successful", source="setup_service", event_type="system_initialization")
                else:
                    result["errors"].append({
                        "database": "appwrite_buckets",
                        "error": bucket_result.get("error", "Unknown error"),
                        "context": bucket_result.get("details", {})
                    })
                    self.logger.error("Appwrite buckets initialization failed", source="setup_service", event_type="system_initialization")
            else:
                result["errors"].append({
                    "database": "appwrite",
                    "error": appwrite_result.get("error", "Unknown error"),
                    "context": appwrite_result.get("details", {})
                })
                self.logger.error("Appwrite collections initialization failed", source="setup_service", event_type="system_initialization")
        
        # Calculate final results
        result["total_operations"] = total_operations
        result["successful_operations"] = successful_operations
        result["execution_time_seconds"] = round(time.time() - start_time, 2)
        result["success"] = (successful_operations > 0 and len(result["errors"]) == 0)
        
        if result["success"]:
            self.logger.info(f"System initialization completed successfully ({successful_operations}/{total_operations} databases)", 
                           source="setup_service", event_type="system_initialization")
        else:
            self.logger.warning(f"System initialization completed with issues ({successful_operations}/{total_operations} databases successful)", 
                              source="setup_service", event_type="system_initialization")
        
        return result
    
    # === Individual Database Setup ===
    def setup_postgres(self) -> Dict[str, Any]:
        """
        Complete PostgreSQL setup - references db/sql/001_core.sql.
        
        Returns
        -------
        Dict[str, Any]
            Detailed PostgreSQL setup results
        """
        start_time = time.time()
        self.logger.info("Starting PostgreSQL setup", source="setup_service", event_type="postgres_setup")
        
        result = {
            "success": False,
            "database": "postgresql",
            "operation": "setup_postgres",
            "timestamp": datetime.now().isoformat() + "Z",
            "service_status": None,
            "schema_deployment": None,
            "health_check": None,
            "tables_verified": None,
            "error": None,
            "details": {},
            "execution_time_seconds": 0
        }
        
        try:
            # Ensure PostgreSQL client is initialized
            if not self.postgres_client:
                try:
                    self.postgres_client = PostgresClient()
                    self.logger.info("PostgreSQL client initialized during setup", source="setup_service", event_type="postgres_setup")
                except Exception as e:
                    result["error"] = f"Failed to initialize PostgreSQL client: {str(e)}"
                    result["details"]["initialization_failed"] = True
                    return result
            
            # Step 1: Health check
            self.logger.info("Performing PostgreSQL health check", source="setup_service", event_type="postgres_setup")
            health_result = self.postgres_client.health_check()
            result["health_check"] = health_result
            
            if not health_result.get("ok", False):
                result["error"] = f"PostgreSQL health check failed: {health_result.get('error', 'Unknown error')}"
                result["details"]["health_check_failed"] = True
                return result
            
            # Step 2: Deploy schema
            schema_path = self._get_sql_schema_path()
            if schema_path and schema_path.exists():
                self.logger.info(f"Deploying PostgreSQL schema from {schema_path}", source="setup_service", event_type="postgres_setup")
                schema_result = self.postgres_client.deploy_schema(str(schema_path))
                result["schema_deployment"] = schema_result
                
                if not schema_result.get("success", False):
                    result["error"] = f"Schema deployment failed: {schema_result.get('errors', [])}"
                    result["details"]["schema_deployment_failed"] = True
                    return result
            else:
                self.logger.warning(f"PostgreSQL schema file not found at expected path: {schema_path}", source="setup_service", event_type="postgres_setup")
                result["details"]["schema_file_missing"] = True
            
            # Step 3: Verify tables were created
            try:
                tables_query = """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name;
                """
                tables_result = self.postgres_client.run(tables_query, fetch="all")
                result["tables_verified"] = [row["table_name"] for row in tables_result] if tables_result else []
                
                if len(result["tables_verified"]) > 0:
                    self.logger.info(f"Verified {len(result['tables_verified'])} PostgreSQL tables created", source="setup_service", event_type="postgres_setup")
                else:
                    self.logger.warning("No PostgreSQL tables found after schema deployment", source="setup_service", event_type="postgres_setup")
                    
            except Exception as e:
                self.logger.warning(f"Failed to verify PostgreSQL tables: {e}", source="setup_service", event_type="postgres_setup")
                result["details"]["table_verification_failed"] = str(e)
            
            result["success"] = True
            self.logger.info("PostgreSQL setup completed successfully", source="setup_service", event_type="postgres_setup")
            
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"PostgreSQL setup failed: {e}", source="setup_service", error=e, event_type="postgres_setup")
        
        finally:
            result["execution_time_seconds"] = round(time.time() - start_time, 2)
        
        return result
    
    def setup_neo4j(self) -> Dict[str, Any]:
        """
        Complete Neo4j setup - references kg/cypher/001_constraints.cypher.
        
        Returns
        -------
        Dict[str, Any]
            Detailed Neo4j setup results
        """
        start_time = time.time()
        self.logger.info("Starting Neo4j setup", source="setup_service", event_type="neo4j_setup")
        
        result = {
            "success": False,
            "database": "neo4j",
            "operation": "setup_neo4j",
            "timestamp": datetime.now().isoformat() + "Z",
            "service_status": None,
            "constraints_deployment": None,
            "health_check": None,
            "graph_ready": False,
            "error": None,
            "details": {},
            "execution_time_seconds": 0
        }
        
        try:
            # Ensure Neo4j client is initialized
            if not self.neo4j_client:
                try:
                    self.neo4j_client = Neo4jClient()
                    self.logger.info("Neo4j client initialized during setup", source="setup_service", event_type="neo4j_setup")
                except Exception as e:
                    result["error"] = f"Failed to initialize Neo4j client: {str(e)}"
                    result["details"]["initialization_failed"] = True
                    return result
            
            # Step 1: Health check
            self.logger.info("Performing Neo4j health check", source="setup_service", event_type="neo4j_setup")
            health_result = self.neo4j_client.health_check()
            result["health_check"] = health_result
            
            if not health_result.get("ok", False):
                result["error"] = f"Neo4j health check failed: {health_result.get('error', 'Unknown error')}"
                result["details"]["health_check_failed"] = True
                return result
            
            # Step 2: Deploy constraints
            constraints_path = self._get_cypher_constraints_path()
            if constraints_path and constraints_path.exists():
                self.logger.info(f"Deploying Neo4j constraints from {constraints_path}", source="setup_service", event_type="neo4j_setup")
                constraints_result = self.neo4j_client.deploy_constraints(str(constraints_path))
                result["constraints_deployment"] = constraints_result
                
                if not constraints_result.get("success", False):
                    result["error"] = f"Constraints deployment failed: {constraints_result.get('error', 'Unknown error')}"
                    result["details"]["constraints_deployment_failed"] = True
                    return result
            else:
                self.logger.warning(f"Neo4j constraints file not found at expected path: {constraints_path}", source="setup_service", event_type="neo4j_setup")
                result["details"]["constraints_file_missing"] = True
            
            # Step 3: Verify graph is ready with a simple query
            try:
                test_result = self.neo4j_client.run("RETURN 1 as test", fetch="one")
                if test_result and test_result.get("test") == 1:
                    result["graph_ready"] = True
                    self.logger.info("Neo4j graph connectivity verified", source="setup_service", event_type="neo4j_setup")
                else:
                    self.logger.warning("Neo4j graph test query returned unexpected result", source="setup_service", event_type="neo4j_setup")
                    
            except Exception as e:
                self.logger.warning(f"Failed to verify Neo4j graph connectivity: {e}", source="setup_service", event_type="neo4j_setup")
                result["details"]["graph_verification_failed"] = str(e)
            
            result["success"] = True
            self.logger.info("Neo4j setup completed successfully", source="setup_service", event_type="neo4j_setup")
            
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"Neo4j setup failed: {e}", source="setup_service", error=e, event_type="neo4j_setup")
        
        finally:
            result["execution_time_seconds"] = round(time.time() - start_time, 2)
        
        return result
    
    def setup_appwrite_collections(self) -> Dict[str, Any]:
        """
        Setup Appwrite collections that mirror PostgreSQL schema per model_updates/database_migration.md.
        
        Returns
        -------
        Dict[str, Any]
            Detailed Appwrite collections setup results
        """
        start_time = time.time()
        self.logger.info("Starting Appwrite collections setup", source="setup_service", event_type="appwrite_setup")
        
        result = {
            "success": False,
            "database": "appwrite",
            "operation": "setup_appwrite_collections", 
            "timestamp": datetime.now().isoformat() + "Z",
            "collections_created": {},
            "collections_skipped": {},
            "health_check": None,
            "error": None,
            "details": {},
            "execution_time_seconds": 0
        }
        
        try:
            if not self.database_manager:
                result["error"] = "Database manager not initialized"
                result["details"]["initialization_failed"] = True
                return result
            
            # PostgreSQL-compatible collection definitions with Appwrite constraints
            # Appwrite limitations: string/bool/int/float types only, 512 char max (64 for complex attributes)
            collections = [
                {
                    "id": "research_papers",
                    "name": "Research Papers", 
                    "document_security": False,
                    "attributes": [
                        {"type": "string", "key": "title", "size": 512, "required": False},
                        {"type": "string", "key": "doi", "size": 255, "required": False},
                        {"type": "string", "key": "journal", "size": 255, "required": False},
                        {"type": "string", "key": "authors", "size": 512, "required": False},  # Reduced from 1000
                        {"type": "string", "key": "published_on", "size": 64, "required": False},  # datetime -> string ISO format
                        {"type": "string", "key": "file_url", "size": 512, "required": False},
                        {"type": "string", "key": "pdf_url", "size": 512, "required": False}
                    ]
                },
                {
                    "id": "sentences", 
                    "name": "Extracted Sentences",
                    "document_security": False,
                    "attributes": [
                        {"type": "string", "key": "paper_id", "size": 255, "required": True},
                        {"type": "string", "key": "text", "size": 512, "required": True},  # Reduced from 2000
                        {"type": "integer", "key": "sentence_number", "required": True},
                        {"type": "integer", "key": "char_start", "required": False},
                        {"type": "integer", "key": "char_end", "required": False}
                    ]
                },
                {
                    "id": "entities",
                    "name": "Extracted Entities", 
                    "document_security": False,
                    "attributes": [
                        {"type": "string", "key": "sentence_id", "size": 255, "required": True},
                        {"type": "string", "key": "entity_type", "size": 50, "required": True},
                        {"type": "string", "key": "entity_text", "size": 512, "required": True},  # Increased from 500 to standard 512
                        {"type": "integer", "key": "start_pos", "required": True},
                        {"type": "integer", "key": "end_pos", "required": True},
                        {"type": "float", "key": "confidence", "required": False},
                        {"type": "string", "key": "model_name", "size": 100, "required": False}
                    ]
                },
                {
                    "id": "extraction_sessions",
                    "name": "Extraction Sessions",
                    "document_security": False,
                    "attributes": [
                        {"type": "string", "key": "session_name", "size": 255, "required": True},
                        {"type": "string", "key": "paper_id", "size": 255, "required": True},
                        {"type": "string", "key": "model_config", "size": 512, "required": False},  # Reduced from 2000
                        {"type": "string", "key": "started_at", "size": 64, "required": False},  # datetime -> string ISO format
                        {"type": "string", "key": "completed_at", "size": 64, "required": False},  # datetime -> string ISO format
                        {"type": "string", "key": "status", "size": 50, "required": False}
                    ]
                }
            ]
            
            successful_collections = 0
            total_collections = len(collections)
            
            for collection in collections:
                collection_id = collection["id"]
                collection_name = collection["name"]
                
                try:
                    # Create collection
                    collection_result = self.database_manager.create_collection(
                        collection_id=collection_id,
                        name=collection_name,
                        document_security=collection.get("document_security", False)
                    )
                    
                    # Create attributes
                    attributes_created = 0
                    attributes_failed = []
                    
                    for attr in collection.get("attributes", []):
                        try:
                            attr_result = self.database_manager.create_attribute(
                                collection_id=collection_id,
                                attr_type=attr["type"],
                                key=attr["key"],
                                **{k: v for k, v in attr.items() if k not in ["type", "key"]}
                            )
                            attributes_created += 1
                        except Exception as attr_error:
                            attributes_failed.append({
                                "attribute": attr["key"],
                                "error": str(attr_error)
                            })
                    
                    result["collections_created"][collection_id] = {
                        "collection_result": collection_result,
                        "attributes_created": attributes_created,
                        "attributes_failed": attributes_failed,
                        "total_attributes": len(collection.get("attributes", [])),
                        "success": len(attributes_failed) == 0
                    }
                    
                    if len(attributes_failed) == 0:
                        successful_collections += 1
                        self.logger.info(f"Collection {collection_id} created successfully with {attributes_created} attributes", 
                                       source="setup_service", event_type="appwrite_setup")
                    else:
                        self.logger.warning(f"Collection {collection_id} created but {len(attributes_failed)} attributes failed", 
                                          source="setup_service", event_type="appwrite_setup")
                
                except Exception as e:
                    result["collections_skipped"][collection_id] = {
                        "error": str(e),
                        "exception_type": type(e).__name__
                    }
                    self.logger.error(f"Failed to create collection {collection_id}: {e}", 
                                    source="setup_service", event_type="appwrite_setup")
            
            # Verify collections exist
            try:
                existing_collections = self.database_manager.list_collections()
                result["details"]["existing_collections"] = [col.get("$id", col.get("id")) for col in existing_collections]
                result["details"]["collections_verified"] = len(result["details"]["existing_collections"])
            except Exception as e:
                result["details"]["verification_error"] = str(e)
                result["details"]["collections_verified"] = 0
            
            # Final results
            result["details"]["total_collections"] = total_collections
            result["details"]["successful_collections"] = successful_collections
            result["details"]["failed_collections"] = len(result["collections_skipped"])
            
            result["success"] = (successful_collections > 0)
            result["execution_time_seconds"] = round(time.time() - start_time, 2)
            
            if result["success"]:
                self.logger.info(f"Appwrite collections setup completed ({successful_collections}/{total_collections} collections)", 
                               source="setup_service", event_type="appwrite_setup")
            else:
                self.logger.warning(f"Appwrite collections setup completed with issues ({successful_collections}/{total_collections} collections)", 
                                  source="setup_service", event_type="appwrite_setup")
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            result["details"]["exception_type"] = type(e).__name__
            result["execution_time_seconds"] = round(time.time() - start_time, 2)
            self.logger.error(f"Appwrite collections setup failed: {e}", source="setup_service", event_type="appwrite_setup")
            return result
        """
        Set up Appwrite collections that match PostgreSQL schema.
        
        Returns
        -------
        Dict[str, Any]
            Results from Appwrite collection setup
        """
        self.logger.log("INFO", "Setting up Appwrite collections", "setup_service")
        
        # PostgreSQL-compatible collection definitions
        collections = [
            {
                "id": "research_papers",
                "name": "Research Papers",
                "attributes": [
                    {"type": "string", "key": "title", "size": 1000, "required": True},
                    {"type": "string", "key": "doi", "size": 255, "required": False},
                    {"type": "string", "key": "pdf_url", "size": 1000, "required": False},
                    {"type": "string", "key": "source", "size": 255, "required": False},
                    {"type": "datetime", "key": "uploaded_at", "required": True},
                    {"type": "string", "key": "status", "size": 50, "required": True}
                ]
            },
            {
                "id": "extraction_sessions", 
                "name": "Extraction Sessions",
                "attributes": [
                    {"type": "string", "key": "paper_id", "size": 50, "required": True},
                    {"type": "string", "key": "model_version", "size": 100, "required": True},
                    {"type": "datetime", "key": "started_at", "required": True},
                    {"type": "datetime", "key": "completed_at", "required": False},
                    {"type": "string", "key": "status", "size": 50, "required": True},
                    {"type": "string", "key": "metadata", "size": 10000, "required": False}
                ]
            },
            {
                "id": "model_configurations",
                "name": "Model Configurations", 
                "attributes": [
                    {"type": "string", "key": "name", "size": 255, "required": True},
                    {"type": "string", "key": "version", "size": 100, "required": True},
                    {"type": "string", "key": "model_type", "size": 100, "required": True},
                    {"type": "string", "key": "config_json", "size": 10000, "required": False},
                    {"type": "boolean", "key": "is_active", "required": True},
                    {"type": "datetime", "key": "created_at", "required": True}
                ]
            },
            {
                "id": "datasets",
                "name": "Datasets",
                "attributes": [
                    {"type": "string", "key": "name", "size": 255, "required": True},
                    {"type": "string", "key": "description", "size": 2000, "required": False},
                    {"type": "string", "key": "source_type", "size": 100, "required": True},
                    {"type": "string", "key": "file_path", "size": 1000, "required": False},
                    {"type": "integer", "key": "record_count", "required": False},
                    {"type": "datetime", "key": "created_at", "required": True}
                ]
            }
        ]
        
        results = {}
        for collection in collections:
            try:
                # Use database_manager to create collections
                collection_result = self.database_manager.create_table(
                    table_name=collection["id"],
                    schema=collection
                )
                results[collection["id"]] = collection_result
                self.logger.info(f"Set up collection: {collection['id']}", source="setup_service", event_type="collection_setup")
            except Exception as e:
                results[collection["id"]] = {"error": str(e)}
                self.logger.error(f"Failed to set up collection {collection['id']}: {e}", source="setup_service", event_type="collection_setup")
        
        return results

    def setup_appwrite_buckets(self) -> Dict[str, Any]:
        """
        Setup Appwrite storage buckets required by services.
        
        Creates all necessary buckets used by:
        - grobid_service: raw_documents_bucket, processed_xml_bucket
        - evaluation_service: datasets_bucket, model_results_bucket
        - tei_processing_service: processed_xml_bucket
        - groundtruth_service: datasets_bucket
        
        Returns
        -------
        Dict[str, Any]
            Detailed bucket setup results
        """
        start_time = time.time()
        self.logger.info("Starting Appwrite buckets setup", source="setup_service", event_type="bucket_setup")
        
        result = {
            "success": False,
            "operation": "setup_appwrite_buckets",
            "timestamp": datetime.now().isoformat() + "Z",
            "buckets_created": {},
            "buckets_skipped": {},
            "error": None,
            "details": {},
            "execution_time_seconds": 0
        }
        
        try:
            if not self.bucket_manager:
                result["error"] = "Bucket manager not initialized"
                result["details"]["initialization_failed"] = True
                return result
            
            # Required buckets for services
            buckets = [
                {
                    "id": "raw_documents_bucket",
                    "name": "Raw Documents",
                    "description": "PDF and raw document uploads for GROBID processing"
                },
                {
                    "id": "processed_xml_bucket", 
                    "name": "Processed XML",
                    "description": "TEI XML files from GROBID and processed documents"
                },
                {
                    "id": "datasets_bucket",
                    "name": "Datasets",
                    "description": "Training and evaluation datasets"
                },
                {
                    "id": "model_results_bucket",
                    "name": "Model Results", 
                    "description": "Model evaluation results and outputs"
                }
            ]
            
            successful_buckets = 0
            total_buckets = len(buckets)
            
            for bucket in buckets:
                try:
                    # Try to create bucket (will skip if exists)
                    bucket_result = self.bucket_manager.create_bucket(
                        bucket_id=bucket["id"],
                        name=bucket["name"],
                        file_security=False  # Public file access for development
                    )
                    
                    if bucket_result.get("status") == "exists":
                        result["buckets_skipped"][bucket["id"]] = {
                            "name": bucket["name"],
                            "description": bucket["description"],
                            "status": "already_exists"
                        }
                        self.logger.info(f"Bucket '{bucket['id']}' already exists", source="setup_service", event_type="bucket_setup")
                    else:
                        result["buckets_created"][bucket["id"]] = {
                            "name": bucket["name"],
                            "description": bucket["description"],
                            "bucket_result": bucket_result
                        }
                        self.logger.info(f"Created bucket '{bucket['id']}'", source="setup_service", event_type="bucket_setup")
                    
                    successful_buckets += 1
                    
                except Exception as e:
                    result["details"][f"bucket_{bucket['id']}_error"] = str(e)
                    self.logger.error(f"Failed to create bucket '{bucket['id']}': {e}", source="setup_service", event_type="bucket_setup")
            
            result["success"] = successful_buckets == total_buckets
            result["details"]["buckets_processed"] = successful_buckets
            result["details"]["total_buckets"] = total_buckets
            result["execution_time_seconds"] = round(time.time() - start_time, 2)
            
            if result["success"]:
                self.logger.info(f"Successfully set up {successful_buckets}/{total_buckets} buckets", source="setup_service", event_type="bucket_setup")
            else:
                self.logger.warning(f"Bucket setup partially successful: {successful_buckets}/{total_buckets}", source="setup_service", event_type="bucket_setup")
        
        except Exception as e:
            result["error"] = str(e)
            result["details"]["exception_type"] = type(e).__name__
            result["execution_time_seconds"] = round(time.time() - start_time, 2)
            self.logger.error(f"Bucket setup failed: {e}", source="setup_service", event_type="bucket_setup")
        
        return result

    def check_system_health(self) -> Dict[str, Any]:
        """
        Check health of all database systems.
        
        Returns
        -------
        Dict[str, Any]
            Health status of all database systems
        """
        # Use the comprehensive health check method instead
        return self.health_check_all()

    def detect_environment(self) -> Dict[str, Any]:
        """
        Detect current database environment configuration.
        
        Returns
        -------
        Dict[str, Any]
            Environment detection results
        """
        result = {
            "success": True,
            "operation": "detect_environment",
            "timestamp": datetime.now().isoformat() + "Z",
            "environment_config": {
                "use_postgres": self._should_use_postgres(),
                "use_neo4j": self._should_use_neo4j(),
                "use_appwrite": self._should_use_appwrite(),
                "data_backend": os.getenv("DATA_BACKEND", "appwrite"),
                "graph_backend": os.getenv("GRAPH_BACKEND", "neo4j")
            },
            "clients_initialized": {
                "postgres_client": self.postgres_client is not None,
                "neo4j_client": self.neo4j_client is not None,
                "database_manager": self.database_manager is not None,
                "graph_manager": self.graph_manager is not None,
                "bucket_manager": self.bucket_manager is not None
            }
        }
        return result

    def setup_native_databases(self) -> Dict[str, Any]:
        """
        Set up native database installations.
        
        Returns
        -------
        Dict[str, Any]
            Results from native database setup
        """
        # This method is deprecated in favor of individual setup methods
        result = {
            "success": False,
            "operation": "setup_native_databases",
            "timestamp": datetime.now().isoformat() + "Z",
            "error": "Method deprecated. Use setup_postgres(), setup_neo4j(), and setup_appwrite_collections() instead.",
            "recommendations": [
                "Use initialize_system() for complete setup",
                "Use individual setup methods for specific databases"
            ]
        }
        return result

    def setup_docker_databases(self) -> Dict[str, Any]:
        """
        Set up Docker-based database containers.
        
        Returns
        -------
        Dict[str, Any]
            Results from Docker database setup
        """
        # This method is deprecated in favor of individual setup methods
        result = {
            "success": False,
            "operation": "setup_docker_databases", 
            "timestamp": datetime.now().isoformat() + "Z",
            "error": "Method deprecated. Use setup_postgres(), setup_neo4j(), and setup_appwrite_collections() instead.",
            "recommendations": [
                "Use initialize_system() for complete setup",
                "Use individual setup methods for specific databases"
            ]
        }
        return result

    # === Health Check and Status Operations ===
    def health_check_all(self) -> Dict[str, Any]:
        """
        Health check all configured databases per .env.example flags.
        
        Returns
        -------
        Dict[str, Any]
            Comprehensive health status of all database systems
        """
        start_time = time.time()
        self.logger.info("Starting comprehensive health check", source="setup_service", event_type="health_check")
        
        result = {
            "success": False,
            "operation": "health_check_all",
            "timestamp": datetime.now().isoformat() + "Z",
            "overall_health": "unknown",
            "databases": {},
            "managers": {},
            "environment_config": {
                "use_postgres": self._should_use_postgres(),
                "use_neo4j": self._should_use_neo4j(),
                "use_appwrite": self._should_use_appwrite()
            },
            "summary": {
                "total_databases": 0,
                "healthy_databases": 0,
                "unhealthy_databases": 0,
                "managers_available": 0,
                "total_managers": 2
            },
            "execution_time_seconds": 0
        }
        
        try:
            healthy_count = 0
            total_count = 0
            
            # Check PostgreSQL
            if self._should_use_postgres():
                total_count += 1
                if self.postgres_client:
                    try:
                        postgres_health = self.postgres_client.service_status()
                        result["databases"]["postgres"] = postgres_health
                        if postgres_health.get("status") == "healthy":
                            healthy_count += 1
                    except Exception as e:
                        result["databases"]["postgres"] = {
                            "status": "error",
                            "error": str(e),
                            "service": "postgresql"
                        }
                else:
                    result["databases"]["postgres"] = {
                        "status": "unavailable",
                        "error": "Client not initialized",
                        "service": "postgresql"
                    }
            
            # Check Neo4j
            if self._should_use_neo4j():
                total_count += 1
                if self.neo4j_client:
                    try:
                        neo4j_health = self.neo4j_client.service_status()
                        result["databases"]["neo4j"] = neo4j_health
                        if neo4j_health.get("status") == "healthy":
                            healthy_count += 1
                    except Exception as e:
                        result["databases"]["neo4j"] = {
                            "status": "error",
                            "error": str(e),
                            "service": "neo4j"
                        }
                else:
                    result["databases"]["neo4j"] = {
                        "status": "unavailable",
                        "error": "Client not initialized",
                        "service": "neo4j"
                    }
            
            # Check Appwrite via database manager
            if self._should_use_appwrite():
                total_count += 1
                if self.database_manager:
                    try:
                        # Test Appwrite connectivity via database manager
                        collections = self.database_manager.list_collections()
                        result["databases"]["appwrite"] = {
                            "status": "healthy",
                            "service": "appwrite",
                            "collections_count": len(collections),
                            "timestamp": time.time()
                        }
                        healthy_count += 1
                    except Exception as e:
                        result["databases"]["appwrite"] = {
                            "status": "error",
                            "error": str(e),
                            "service": "appwrite"
                        }
                else:
                    result["databases"]["appwrite"] = {
                        "status": "unavailable",
                        "error": "Database manager not initialized",
                        "service": "appwrite"
                    }
            
            # Check managers
            managers_available = 0
            if self.database_manager:
                result["managers"]["database_manager"] = {"status": "available", "scope": "relational/document"}
                managers_available += 1
            else:
                result["managers"]["database_manager"] = {"status": "unavailable", "error": "Not initialized"}
            
            if self.graph_manager:
                result["managers"]["graph_manager"] = {"status": "available", "scope": "graph"}
                managers_available += 1
            else:
                result["managers"]["graph_manager"] = {"status": "unavailable", "error": "Not initialized"}
            
            # Calculate summary
            result["summary"]["total_databases"] = total_count
            result["summary"]["healthy_databases"] = healthy_count
            result["summary"]["unhealthy_databases"] = total_count - healthy_count
            result["summary"]["managers_available"] = managers_available
            
            # Determine overall health
            if healthy_count == total_count and total_count > 0:
                result["overall_health"] = "healthy"
                result["success"] = True
            elif healthy_count > 0:
                result["overall_health"] = "partial"
                result["success"] = True
            else:
                result["overall_health"] = "unhealthy"
                result["success"] = False
            
            result["execution_time_seconds"] = round(time.time() - start_time, 2)
            
            self.logger.info(f"Health check completed: {healthy_count}/{total_count} databases healthy, {managers_available}/2 managers available", 
                           source="setup_service", event_type="health_check")
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            result["execution_time_seconds"] = round(time.time() - start_time, 2)
            self.logger.error(f"Health check failed: {e}", source="setup_service", event_type="health_check")
            return result
    
    # === Service Lifecycle Operations ===
    def start_all_services(self) -> Dict[str, Any]:
        """
        Start all database services based on enabled flags.
        
        Returns
        -------
        Dict[str, Any]
            Results of starting all configured database services
        """
        start_time = time.time()
        self.logger.info("Starting all database services", source="setup_service", event_type="start_services")
        
        result = {
            "success": False,
            "operation": "start_all_services",
            "timestamp": datetime.now().isoformat() + "Z",
            "services": {},
            "summary": {
                "total_services": 0,
                "started_services": 0,
                "failed_services": 0
            },
            "execution_time_seconds": 0
        }
        
        started_count = 0
        total_count = 0
        
        try:
            # Start PostgreSQL
            if self._should_use_postgres() and self.postgres_client:
                total_count += 1
                try:
                    start_result = self.postgres_client.start_service()
                    result["services"]["postgres"] = start_result
                    if start_result.get("status") in ["started", "healthy"]:
                        started_count += 1
                except Exception as e:
                    result["services"]["postgres"] = {"status": "error", "error": str(e)}
            
            # Start Neo4j
            if self._should_use_neo4j() and self.neo4j_client:
                total_count += 1
                try:
                    start_result = self.neo4j_client.start_service()
                    result["services"]["neo4j"] = start_result
                    if start_result.get("status") in ["started", "healthy"]:
                        started_count += 1
                except Exception as e:
                    result["services"]["neo4j"] = {"status": "error", "error": str(e)}
            
            # Note: Appwrite is cloud-based, no local service to start
            if self._should_use_appwrite():
                result["services"]["appwrite"] = {
                    "status": "cloud_service",
                    "message": "Appwrite is cloud-based, no local service to start"
                }
            
            result["summary"]["total_services"] = total_count
            result["summary"]["started_services"] = started_count
            result["summary"]["failed_services"] = total_count - started_count
            result["success"] = started_count > 0
            result["execution_time_seconds"] = round(time.time() - start_time, 2)
            
            self.logger.info(f"Service startup completed: {started_count}/{total_count} services started", 
                           source="setup_service", event_type="start_services")
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            result["execution_time_seconds"] = round(time.time() - start_time, 2)
            self.logger.error(f"Failed to start services: {e}", source="setup_service", event_type="start_services")
            return result
    
    def stop_all_services(self) -> Dict[str, Any]:
        """
        Stop all database services.
        
        Returns
        -------
        Dict[str, Any]
            Results of stopping all database services
        """
        start_time = time.time()
        self.logger.info("Stopping all database services", source="setup_service", event_type="stop_services")
        
        result = {
            "success": False,
            "operation": "stop_all_services",
            "timestamp": datetime.now().isoformat() + "Z",
            "services": {},
            "summary": {
                "total_services": 0,
                "stopped_services": 0,
                "failed_services": 0
            },
            "execution_time_seconds": 0
        }
        
        stopped_count = 0
        total_count = 0
        
        try:
            # Stop PostgreSQL
            if self.postgres_client:
                total_count += 1
                try:
                    stop_result = self.postgres_client.stop_service()
                    result["services"]["postgres"] = stop_result
                    if stop_result.get("status") == "stopped":
                        stopped_count += 1
                except Exception as e:
                    result["services"]["postgres"] = {"status": "error", "error": str(e)}
            
            # Stop Neo4j
            if self.neo4j_client:
                total_count += 1
                try:
                    stop_result = self.neo4j_client.stop_service()
                    result["services"]["neo4j"] = stop_result
                    if stop_result.get("status") == "stopped":
                        stopped_count += 1
                except Exception as e:
                    result["services"]["neo4j"] = {"status": "error", "error": str(e)}
            
            result["summary"]["total_services"] = total_count
            result["summary"]["stopped_services"] = stopped_count
            result["summary"]["failed_services"] = total_count - stopped_count
            result["success"] = stopped_count > 0 or total_count == 0
            result["execution_time_seconds"] = round(time.time() - start_time, 2)
            
            self.logger.info(f"Service shutdown completed: {stopped_count}/{total_count} services stopped", 
                           source="setup_service", event_type="stop_services")
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            result["execution_time_seconds"] = round(time.time() - start_time, 2)
            self.logger.error(f"Failed to stop services: {e}", source="setup_service", event_type="stop_services")
            return result
    
    def restart_all_services(self) -> Dict[str, Any]:
        """
        Restart all database services.
        
        Returns
        -------
        Dict[str, Any]
            Results of restarting all database services
        """
        start_time = time.time()
        self.logger.info("Restarting all database services", source="setup_service", event_type="restart_services")
        
        result = {
            "success": False,
            "operation": "restart_all_services",
            "timestamp": datetime.now().isoformat() + "Z",
            "stop_results": {},
            "start_results": {},
            "summary": {
                "total_services": 0,
                "restarted_services": 0,
                "failed_services": 0
            },
            "execution_time_seconds": 0
        }
        
        try:
            # Stop all services first
            stop_result = self.stop_all_services()
            result["stop_results"] = stop_result
            
            # Wait a moment for services to fully stop
            time.sleep(2)
            
            # Start all services
            start_result = self.start_all_services()
            result["start_results"] = start_result
            
            # Calculate summary
            total_services = max(
                stop_result.get("summary", {}).get("total_services", 0),
                start_result.get("summary", {}).get("total_services", 0)
            )
            restarted_services = start_result.get("summary", {}).get("started_services", 0)
            
            result["summary"]["total_services"] = total_services
            result["summary"]["restarted_services"] = restarted_services
            result["summary"]["failed_services"] = total_services - restarted_services
            result["success"] = restarted_services > 0
            result["execution_time_seconds"] = round(time.time() - start_time, 2)
            
            self.logger.info(f"Service restart completed: {restarted_services}/{total_services} services restarted", 
                           source="setup_service", event_type="restart_services")
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            result["execution_time_seconds"] = round(time.time() - start_time, 2)
            self.logger.error(f"Failed to restart services: {e}", source="setup_service", event_type="restart_services")
            return result
    
    # === Reset and Clean Operations ===
    def reset_all_databases(self, preserve_logs: bool = True) -> Dict[str, Any]:
        """
        Reset all database tables and schemas to clean state.
        
        NOTE: This does NOT delete databases themselves, only tables and data.
        The databases and users must be manually managed as per the README.
        
        Parameters
        ----------
        preserve_logs : bool
            Whether to preserve log tables during reset
            
        Returns
        -------
        Dict[str, Any]
            Results of resetting all database schemas and tables
        """
        start_time = time.time()
        self.logger.info("Starting database reset operation", source="setup_service", event_type="reset_databases")
        
        result = {
            "success": False,
            "operation": "reset_all_databases",
            "timestamp": datetime.now().isoformat() + "Z",
            "preserve_logs": preserve_logs,
            "databases": {},
            "summary": {
                "total_databases": 0,
                "reset_databases": 0,
                "failed_resets": 0
            },
            "execution_time_seconds": 0
        }
        
        reset_count = 0
        total_count = 0
        
        try:
            # Reset PostgreSQL tables
            if self._should_use_postgres() and self.postgres_client:
                total_count += 1
                try:
                    postgres_reset = self.postgres_client.reset_database(preserve_logs=preserve_logs)
                    result["databases"]["postgres"] = postgres_reset
                    if postgres_reset.get("success"):
                        reset_count += 1
                        self.logger.info("PostgreSQL tables reset successfully", source="setup_service", event_type="reset_databases")
                    else:
                        self.logger.error(f"PostgreSQL reset failed: {postgres_reset.get('error')}", source="setup_service", event_type="reset_databases")
                except Exception as e:
                    result["databases"]["postgres"] = {"success": False, "error": str(e)}
                    self.logger.error(f"PostgreSQL reset exception: {e}", source="setup_service", event_type="reset_databases")
            
            # Reset Neo4j nodes and relationships
            if self._should_use_neo4j() and self.neo4j_client:
                total_count += 1
                try:
                    neo4j_reset = self.neo4j_client.reset_database(confirm=True)
                    result["databases"]["neo4j"] = neo4j_reset
                    if neo4j_reset.get("success"):
                        reset_count += 1
                        self.logger.info("Neo4j data reset successfully", source="setup_service", event_type="reset_databases")
                    else:
                        self.logger.error(f"Neo4j reset failed: {neo4j_reset.get('error')}", source="setup_service", event_type="reset_databases")
                except Exception as e:
                    result["databases"]["neo4j"] = {"success": False, "error": str(e)}
                    self.logger.error(f"Neo4j reset exception: {e}", source="setup_service", event_type="reset_databases")
            
            result["summary"]["total_databases"] = total_count
            result["summary"]["reset_databases"] = reset_count
            result["summary"]["failed_resets"] = total_count - reset_count
            result["success"] = reset_count > 0
            
            if result["success"]:
                self.logger.info(f"Database reset completed successfully. Reset {reset_count}/{total_count} databases", source="setup_service", event_type="reset_databases")
            else:
                self.logger.warning("Database reset completed with no successful resets", source="setup_service", event_type="reset_databases")
                
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"Database reset failed with exception: {e}", source="setup_service", event_type="reset_databases")
        finally:
            result["execution_time_seconds"] = time.time() - start_time
            
        return result
    
    def clean_install(self, preserve_logs: bool = True) -> Dict[str, Any]:
        """
        Perform clean installation by resetting tables and reinitializing schemas.
        
        NOTE: This does NOT delete databases themselves, only tables and data.
        The databases and users must be manually managed as per the README.
        
        Parameters
        ----------
        preserve_logs : bool
            Whether to preserve log tables during reset
            
        Returns
        -------
        Dict[str, Any]
            Results of clean installation process
        """
        start_time = time.time()
        self.logger.info("Starting clean installation", source="setup_service", event_type="clean_install")
        
        result = {
            "success": False,
            "operation": "clean_install",
            "timestamp": datetime.now().isoformat() + "Z",
            "preserve_logs": preserve_logs,
            "phases": {},
            "execution_time_seconds": 0
        }
        
        try:
            # Phase 1: Stop all services
            self.logger.info("Phase 1: Stopping all services", source="setup_service", event_type="clean_install")
            stop_result = self.stop_all_services()
            result["phases"]["stop_services"] = stop_result
            
            # Phase 2: Reset all databases
            self.logger.info("Phase 2: Resetting all databases", source="setup_service", event_type="clean_install")
            reset_result = self.reset_all_databases(preserve_logs=preserve_logs)
            result["phases"]["reset_databases"] = reset_result
            
            # Phase 3: Initialize system
            self.logger.info("Phase 3: Initializing system", source="setup_service", event_type="clean_install")
            init_result = self.initialize_system()
            result["phases"]["initialize_system"] = init_result
            
            # Phase 4: Health check
            self.logger.info("Phase 4: Final health check", source="setup_service", event_type="clean_install")
            health_result = self.health_check_all()
            result["phases"]["health_check"] = health_result
            
            # Determine overall success
            result["success"] = (
                init_result.get("success", False) and 
                health_result.get("overall_health") in ["healthy", "partial"]
            )
            result["execution_time_seconds"] = round(time.time() - start_time, 2)
            
            self.logger.info(f"Clean installation completed: {result['success']}", 
                           source="setup_service", event_type="clean_install")
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            result["execution_time_seconds"] = round(time.time() - start_time, 2)
            self.logger.error(f"Clean installation failed: {e}", source="setup_service", event_type="clean_install")
            return result
    
    # === Helper Methods ===
    def _get_sql_schema_path(self) -> Optional[Path]:
        """Get path to db/sql/001_core.sql"""
        try:
            return Path(__file__).parent.parent.parent / "db" / "sql" / "001_core.sql"
        except Exception:
            return None
        
    def _get_cypher_constraints_path(self) -> Optional[Path]:
        """Get path to kg/cypher/001_constraints.cypher"""
        try:
            return Path(__file__).parent.parent.parent / "kg" / "cypher" / "001_constraints.cypher"
        except Exception:
            return None
    
    def _should_use_postgres(self) -> bool:
        """Check if PostgreSQL should be used based on environment variables."""
        return (
            os.getenv("USE_POSTGRESQL_DB", "false").lower() == "true" or
            os.getenv("DATA_BACKEND", "").lower() == "postgresql"
        )
    
    def _should_use_neo4j(self) -> bool:
        """Check if Neo4j should be used based on environment variables."""
        return (
            os.getenv("USE_NEO4J_DB", "false").lower() == "true" or
            os.getenv("GRAPH_BACKEND", "").lower() == "neo4j"
        )
    
    def _should_use_appwrite(self) -> bool:
        """Check if Appwrite should be used based on environment variables."""
        return (
            os.getenv("USE_APPWRITE_DB", "false").lower() == "true" or
            os.getenv("DATA_BACKEND", "").lower() == "appwrite"
        )
    
    # === Legacy Compatibility Layer ===
    def list_collections(self) -> List[Dict[str, Any]]:
        """Legacy compatibility: List all Appwrite collections."""
        if self.database_manager:
            return self.database_manager.list_collections()
        return []
    
    def create_record(self, collection_id: str, data: Dict[str, Any], document_id: Optional[str] = None) -> Dict[str, Any]:
        """Legacy compatibility: Create a document in an Appwrite collection."""
        if self.database_manager:
            return self.database_manager.create_record(collection_id, data, document_id)
        raise RuntimeError("Database manager not available")
    
    def get_record(self, collection_id: str, document_id: str) -> Dict[str, Any]:
        """Legacy compatibility: Get a document from an Appwrite collection.""" 
        if self.database_manager:
            return self.database_manager.get_record(collection_id, document_id)
        raise RuntimeError("Database manager not available")
    
    def list_records(self, collection_id: str, queries: Optional[List] = None) -> List[Dict[str, Any]]:
        """Legacy compatibility: List documents from an Appwrite collection."""
        if self.database_manager:
            return self.database_manager.list_records(collection_id, queries)
        return []
    
    def update_record(self, collection_id: str, document_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy compatibility: Update a document in an Appwrite collection."""
        if self.database_manager:
            return self.database_manager.update_record(collection_id, document_id, data)
        raise RuntimeError("Database manager not available")
        
    def delete_collection(self, collection_id: str) -> None:
        """Legacy compatibility: Delete an Appwrite collection."""
        if self.database_manager:
            return self.database_manager.delete_collection(collection_id)
        raise RuntimeError("Database manager not available")
