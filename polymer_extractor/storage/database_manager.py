"""
Universal Database Manager for Polymer NLP Extractor.

Purpose
-------
Universal abstraction layer that routes database operations across relational and document backends:
- Appwrite (cloud-native document database)
- PostgreSQL (relational database)

Note: Graph operations (Neo4j) are handled separately by GraphManager in graph_manager.py

The manager routes operations to active backends based on environment configuration
and provides universal method names that work consistently across relational/document database types.

Environment Variables
---------------------
Required for routing decisions (reference: .env.example lines 12-19):
- USE_APPWRITE=true/false - Enable/disable Appwrite operations
- USE_APPWRITE_DB=true/false - Enable/disable Appwrite database operations  
- USE_POSTGRESQL_DB=true/false - Enable/disable PostgreSQL database operations
- DATA_BACKEND=postgres|appwrite - Primary backend for structured data

Design Principles
-----------------
1. Universal method names (create_record, get_record, etc.) work across relational/document backends
2. Environment-driven routing respects user preferences and availability
3. Comprehensive error handling with fallback logic
4. Backward compatibility via legacy method mapping
5. Integration with model_config.py entity types and validation patterns
6. SEPARATION: Graph operations handled by GraphManager, not this class

Examples
--------
>>> from polymer_extractor.storage.database_manager import DatabaseManager
>>> db = DatabaseManager()
>>> result = db.create_record("research_papers", {"title": "Polymer Study", "doi": "10.1234/test"})
>>> # Routes to active backends based on .env configuration

>>> # For graph operations, use GraphManager:
>>> from polymer_extractor.storage.graph_manager import GraphManager
>>> graph = GraphManager()
>>> graph.create_polymer_entity("PDMS", {"molecular_weight": 10000})

Legacy Compatibility
--------------------
Existing code continues to work:
>>> db.create_record("collection", data)  # Maps to create_record()
>>> db.list_records("collection")         # Maps to list_records()
"""

import os
import warnings
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from appwrite.exception import AppwriteException
from appwrite.id import ID

from polymer_extractor.storage.appwrite_client import get_database_service, get_database_id
from polymer_extractor.storage.postgresql_client import PostgresClient
from polymer_extractor.utils.logging import Logger

logger = Logger()


class DatabaseManager:
    """
    Universal relational/document database operations router supporting Appwrite and PostgreSQL.
    
    Routes operations to active backends based on environment configuration (.env.example).
    Provides universal method names that work consistently across relational and document database types.
    
    Note: Graph database operations (Neo4j) are handled by GraphManager in graph_manager.py
    """

    def __init__(self):
        """Initialize database clients based on environment configuration."""
        # NOTE: Cannot use Logger here due to circular dependency (Logger -> DatabaseManager -> Logger)
        # Use simple print statements for initialization logging
        
        # Initialize clients based on .env flags
        self.appwrite_db = None
        self.appwrite_database_id = None
        self.postgres_client = None
        
        # Initialize Appwrite if enabled
        if self._should_use_appwrite():
            try:
                self.appwrite_db, self.appwrite_database_id = get_database_service(), get_database_id()
                print("[DATABASE_MANAGER] Appwrite database client initialized")
            except Exception as e:
                print(f"[DATABASE_MANAGER] Failed to initialize Appwrite client: {e}")
        
        # Initialize PostgreSQL if enabled
        if self._should_use_postgres():
            try:
                self.postgres_client = PostgresClient()
                print("[DATABASE_MANAGER] PostgreSQL database client initialized")
            except Exception as e:
                print(f"[DATABASE_MANAGER] Failed to initialize PostgreSQL client: {e}")
                
        # Validate at least one backend is available
        if not self.appwrite_db and not self.postgres_client:
            print("[DATABASE_MANAGER] No database backends available - check environment configuration")
    
    def _should_use_appwrite(self) -> bool:
        """Check if Appwrite should be used based on .env flags."""
        return (os.getenv("USE_APPWRITE", "true").lower() == "true" and 
                os.getenv("USE_APPWRITE_DB", "true").lower() == "true")
    
    def _should_use_postgres(self) -> bool:
        """Check if PostgreSQL should be used based on .env flags."""
        return (os.getenv("USE_POSTGRESQL_DB", "true").lower() == "true" or
                os.getenv("DATA_BACKEND", "appwrite") == "postgres")
    
    def _get_primary_backend(self) -> str:
        """Get the primary backend for read operations based on DATA_BACKEND preference."""
        return os.getenv("DATA_BACKEND", "appwrite")
    
    def _convert_queries_to_filters(self, queries: Optional[List]) -> Optional[Dict[str, Any]]:
        """Convert Appwrite-style queries to universal filter format."""
        if not queries:
            return None
        
        filters = {}
        for query in queries:
            # Basic query parsing - can be enhanced based on actual query format
            if isinstance(query, dict):
                filters.update(query)
            # Add more query parsing logic as needed
        return filters
    
    # === Universal CRUD Operations ===
    def create_record(self, table_name: str, data: Dict[str, Any], record_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Universal create - routes to active backends based on .env configuration.
        
        Parameters
        ----------
        table_name : str
            Table/collection name
        data : dict
            Record data to create
        record_id : str, optional
            Specific record ID (if supported by backend)
            
        Returns
        -------
        dict
            Created record details with backend routing information
        """
        results = {"backends": {}, "primary": None}
        
        try:
            # Route to Appwrite if enabled
            if self.appwrite_db and self._should_use_appwrite():
                try:
                    appwrite_result = self._create_appwrite_document(table_name, data, record_id)
                    results["backends"]["appwrite"] = appwrite_result
                    self.logger.debug(f"Created record in Appwrite: {table_name}", source="database_manager", event_type="create_record")
                except Exception as e:
                    results["backends"]["appwrite"] = {"error": str(e)}
                    self.logger.warning(f"Appwrite create failed: {e}", source="database_manager", event_type="create_record")
            
            # Route to PostgreSQL if enabled
            if self.postgres_client and self._should_use_postgres():
                try:
                    postgres_result = self._create_postgres_record(table_name, data)
                    results["backends"]["postgres"] = postgres_result
                    self.logger.debug(f"Created record in PostgreSQL: {table_name}", source="database_manager", event_type="create_record")
                except Exception as e:
                    results["backends"]["postgres"] = {"error": str(e)}
                    self.logger.warning(f"PostgreSQL create failed: {e}", source="database_manager", event_type="create_record")
            
            # Set primary result based on DATA_BACKEND preference
            primary_backend = self._get_primary_backend()
            if primary_backend in results["backends"] and "error" not in results["backends"][primary_backend]:
                results["primary"] = results["backends"][primary_backend]
            else:
                # Fallback to first successful backend
                for backend, result in results["backends"].items():
                    if "error" not in result:
                        results["primary"] = result
                        break
            
            if not results["primary"]:
                raise Exception("All backends failed to create record")
                
            self.logger.info(f"Record created successfully in {table_name}", source="database_manager", event_type="create_record")
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to create record in {table_name}: {e}", source="database_manager", event_type="create_record")
            raise
    
    def get_record(self, table_name: str, record_id: str) -> Dict[str, Any]:
        """
        Universal read single record - routes based on DATA_BACKEND preference.
        
        Parameters
        ----------
        table_name : str
            Table/collection name
        record_id : str
            Record ID to retrieve
            
        Returns
        -------
        dict
            Record data from primary backend
        """
        primary_backend = self._get_primary_backend()
        
        try:
            # Try primary backend first
            if primary_backend == "postgres" and self.postgres_client:
                return self._get_postgres_record(table_name, record_id)
            elif primary_backend == "appwrite" and self.appwrite_db:
                return self._get_appwrite_document(table_name, record_id)
            
            # Fallback logic
            if self.postgres_client and primary_backend != "postgres":
                return self._get_postgres_record(table_name, record_id)
            elif self.appwrite_db and primary_backend != "appwrite":
                return self._get_appwrite_document(table_name, record_id)
            
            raise Exception("No available backends for record retrieval")
            
        except Exception as e:
            self.logger.error(f"Failed to get record {record_id} from {table_name}: {e}", source="database_manager", event_type="get_record")
            raise
    
    def list_records(self, table_name: str, filters: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Universal read multiple records - integrates with model_config.py entity types.
        
        Parameters
        ----------
        table_name : str
            Table/collection name
        filters : dict, optional
            Filter conditions
        limit : int, optional
            Maximum number of records to return
            
        Returns
        -------
        list
            List of records from primary backend
        """
        primary_backend = self._get_primary_backend()
        
        try:
            # Try primary backend first
            if primary_backend == "postgres" and self.postgres_client:
                return self._list_postgres_records(table_name, filters, limit)
            elif primary_backend == "appwrite" and self.appwrite_db:
                return self._list_appwrite_documents(table_name, filters, limit)
            
            # Fallback logic
            if self.postgres_client and primary_backend != "postgres":
                return self._list_postgres_records(table_name, filters, limit)
            elif self.appwrite_db and primary_backend != "appwrite":
                return self._list_appwrite_documents(table_name, filters, limit)
            
            raise Exception("No available backends for record listing")
            
        except Exception as e:
            self.logger.error(f"Failed to list records from {table_name}: {e}", source="database_manager", event_type="list_records")
            raise
    
    def update_record(self, table_name: str, record_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Universal update - routes to active backends.
        
        Parameters
        ----------
        table_name : str
            Table/collection name
        record_id : str
            Record ID to update
        data : dict
            Updated data
            
        Returns
        -------
        dict
            Updated record details with backend routing information
        """
        results = {"backends": {}, "primary": None}
        
        try:
            # Route to Appwrite if enabled
            if self.appwrite_db and self._should_use_appwrite():
                try:
                    appwrite_result = self._update_appwrite_document(table_name, record_id, data)
                    results["backends"]["appwrite"] = appwrite_result
                except Exception as e:
                    results["backends"]["appwrite"] = {"error": str(e)}
                    self.logger.warning(f"Appwrite update failed: {e}", source="database_manager", event_type="update_record")
            
            # Route to PostgreSQL if enabled
            if self.postgres_client and self._should_use_postgres():
                try:
                    postgres_result = self._update_postgres_record(table_name, record_id, data)
                    results["backends"]["postgres"] = postgres_result
                except Exception as e:
                    results["backends"]["postgres"] = {"error": str(e)}
                    self.logger.warning(f"PostgreSQL update failed: {e}", source="database_manager", event_type="update_record")
            
            # Set primary result
            primary_backend = self._get_primary_backend()
            if primary_backend in results["backends"] and "error" not in results["backends"][primary_backend]:
                results["primary"] = results["backends"][primary_backend]
            else:
                for backend, result in results["backends"].items():
                    if "error" not in result:
                        results["primary"] = result
                        break
            
            if not results["primary"]:
                raise Exception("All backends failed to update record")
                
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to update record {record_id} in {table_name}: {e}", source="database_manager", event_type="update_record")
            raise
    
    def delete_record(self, table_name: str, record_id: str) -> None:
        """
        Universal delete - routes to active backends.
        
        Parameters
        ----------
        table_name : str
            Table/collection name
        record_id : str
            Record ID to delete
        """
        try:
            errors = []
            
            # Delete from Appwrite if enabled
            if self.appwrite_db and self._should_use_appwrite():
                try:
                    self._delete_appwrite_document(table_name, record_id)
                except Exception as e:
                    errors.append(f"Appwrite: {e}")
                    self.logger.warning(f"Appwrite delete failed: {e}", source="database_manager", event_type="delete_record")
            
            # Delete from PostgreSQL if enabled
            if self.postgres_client and self._should_use_postgres():
                try:
                    self._delete_postgres_record(table_name, record_id)
                except Exception as e:
                    errors.append(f"PostgreSQL: {e}")
                    self.logger.warning(f"PostgreSQL delete failed: {e}", source="database_manager", event_type="delete_record")
            
            if errors and len(errors) == (int(self._should_use_appwrite()) + int(self._should_use_postgres())):
                raise Exception(f"All backends failed: {'; '.join(errors)}")
                
            self.logger.info(f"Record {record_id} deleted from {table_name}", source="database_manager", event_type="delete_record")
            
        except Exception as e:
            self.logger.error(f"Failed to delete record {record_id} from {table_name}: {e}", source="database_manager", event_type="delete_record")
            raise
    
    def upsert_record(self, table_name: str, data: Dict[str, Any], unique_key: str) -> Dict[str, Any]:
        """
        Universal upsert (insert or update based on unique key).
        
        Parameters
        ----------
        table_name : str
            Table/collection name
        data : dict
            Record data
        unique_key : str
            Field name to use for uniqueness check
            
        Returns
        -------
        dict
            Upserted record details
        """
        try:
            # Try to find existing record by unique key
            filters = {unique_key: data.get(unique_key)}
            existing_records = self.list_records(table_name, filters, limit=1)
            
            if existing_records:
                # Update existing record
                record_id = existing_records[0].get("$id") or existing_records[0].get("id")
                return self.update_record(table_name, record_id, data)
            else:
                # Create new record
                return self.create_record(table_name, data)
                
        except Exception as e:
            self.logger.error(f"Failed to upsert record in {table_name}: {e}", source="database_manager", event_type="upsert_record")
            raise
    
    def count_records(self, table_name: str, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Universal count records.
        
        Parameters
        ----------
        table_name : str
            Table/collection name
        filters : dict, optional
            Filter conditions
            
        Returns
        -------
        int
            Number of records matching filters
        """
        try:
            # Use primary backend for count
            primary_backend = self._get_primary_backend()
            
            if primary_backend == "postgres" and self.postgres_client:
                return self._count_postgres_records(table_name, filters)
            elif primary_backend == "appwrite" and self.appwrite_db:
                return self._count_appwrite_documents(table_name, filters)
            
            # Fallback to listing and counting (less efficient but universal)
            records = self.list_records(table_name, filters)
            return len(records)
            
        except Exception as e:
            self.logger.error(f"Failed to count records in {table_name}: {e}", source="database_manager", event_type="count_records")
            raise
    
    def search_records(self, table_name: str, search_term: str, fields: List[str]) -> List[Dict[str, Any]]:
        """
        Universal text search across specified fields.
        
        Parameters
        ----------
        table_name : str
            Table/collection name
        search_term : str
            Text to search for
        fields : list
            List of field names to search in
            
        Returns
        -------
        list
            Records matching search criteria
        """
        try:
            primary_backend = self._get_primary_backend()
            
            if primary_backend == "postgres" and self.postgres_client:
                return self._search_postgres_records(table_name, search_term, fields)
            elif primary_backend == "appwrite" and self.appwrite_db:
                return self._search_appwrite_documents(table_name, search_term, fields)
            
            # Fallback to basic filtering
            filters = {}
            # Basic implementation - can be enhanced per backend capabilities
            return self.list_records(table_name, filters)
            
        except Exception as e:
            self.logger.error(f"Failed to search records in {table_name}: {e}", source="database_manager", event_type="search_records")
            raise
    
    # === Collection/Table Management ===
    def create_table(self, table_name: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Universal table/collection creation - references db/sql/001_core.sql for PostgreSQL schema.
        
        Parameters
        ----------
        table_name : str
            Name of table/collection to create
        schema : dict
            Schema definition (format varies by backend)
            
        Returns
        -------
        dict
            Creation results from active backends
        """
        results = {"backends": {}}
        
        try:
            # Create in Appwrite if enabled
            if self.appwrite_db and self._should_use_appwrite():
                try:
                    appwrite_result = self._create_appwrite_collection(table_name, schema)
                    results["backends"]["appwrite"] = appwrite_result
                except Exception as e:
                    results["backends"]["appwrite"] = {"error": str(e)}
            
            # Create in PostgreSQL if enabled
            if self.postgres_client and self._should_use_postgres():
                try:
                    postgres_result = self._create_postgres_table(table_name, schema)
                    results["backends"]["postgres"] = postgres_result
                except Exception as e:
                    results["backends"]["postgres"] = {"error": str(e)}
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to create table {table_name}: {e}", source="database_manager", event_type="create_table")
            raise
    
    def drop_table(self, table_name: str) -> None:
        """
        Universal table/collection deletion.
        
        Parameters
        ----------
        table_name : str
            Name of table/collection to delete
        """
        try:
            # Drop from Appwrite if enabled
            if self.appwrite_db and self._should_use_appwrite():
                try:
                    self._drop_appwrite_collection(table_name)
                except Exception as e:
                    self.logger.warning(f"Appwrite drop failed: {e}", source="database_manager", event_type="drop_table")
            
            # Drop from PostgreSQL if enabled
            if self.postgres_client and self._should_use_postgres():
                try:
                    self._drop_postgres_table(table_name)
                except Exception as e:
                    self.logger.warning(f"PostgreSQL drop failed: {e}", source="database_manager", event_type="drop_table")
            
        except Exception as e:
            self.logger.error(f"Failed to drop table {table_name}: {e}", source="database_manager", event_type="drop_table")
            raise
    
    def list_tables(self) -> List[str]:
        """
        Universal list all tables/collections.
        
        Returns
        -------
        list
            List of table/collection names from primary backend
        """
        try:
            primary_backend = self._get_primary_backend()
            
            if primary_backend == "postgres" and self.postgres_client:
                return self._list_postgres_tables()
            elif primary_backend == "appwrite" and self.appwrite_db:
                return self._list_appwrite_collections()
            
            # Fallback
            if self.postgres_client:
                return self._list_postgres_tables()
            elif self.appwrite_db:
                return self._list_appwrite_collections()
            
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to list tables: {e}", source="database_manager", event_type="list_tables")
            raise
    
    def table_exists(self, table_name: str) -> bool:
        """
        Universal check if table/collection exists.
        
        Parameters
        ----------
        table_name : str
            Table/collection name to check
            
        Returns
        -------
        bool
            True if table exists in primary backend
        """
        try:
            tables = self.list_tables()
            return table_name in tables
        except Exception as e:
            self.logger.error(f"Failed to check table existence {table_name}: {e}", source="database_manager", event_type="table_exists")
            return False
    
    # === Backend-Specific Helper Methods ===
    
    # --- Appwrite Helper Methods ---
    def _create_appwrite_document(self, collection_id: str, data: Dict[str, Any], document_id: Optional[str] = None) -> Dict[str, Any]:
        """Create document in Appwrite."""
        return self.appwrite_db.create_record(
            database_id=self.appwrite_database_id,
            collection_id=collection_id,
            document_id=document_id or ID.unique(),
            data=data
        )
    
    def _get_appwrite_document(self, collection_id: str, document_id: str) -> Dict[str, Any]:
        """Get document from Appwrite."""
        return self.appwrite_db.get_record(
            database_id=self.appwrite_database_id,
            collection_id=collection_id,
            document_id=document_id
        )
    
    def _list_appwrite_documents(self, collection_id: str, filters: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List documents from Appwrite."""
        queries = []
        if limit:
            queries.append(f"limit({limit})")
        # Convert filters to Appwrite queries if needed
        
        response = self.appwrite_db.list_records(
            database_id=self.appwrite_database_id,
            collection_id=collection_id,
            queries=queries
        )
        return response.get("documents", [])
    
    def _update_appwrite_document(self, collection_id: str, document_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update document in Appwrite."""
        return self.appwrite_db.update_record(
            database_id=self.appwrite_database_id,
            collection_id=collection_id,
            document_id=document_id,
            data=data
        )
    
    def _delete_appwrite_document(self, collection_id: str, document_id: str) -> None:
        """Delete document from Appwrite."""
        self.appwrite_db.delete_record(
            database_id=self.appwrite_database_id,
            collection_id=collection_id,
            document_id=document_id
        )
    
    def _count_appwrite_documents(self, collection_id: str, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count documents in Appwrite."""
        # Appwrite may require listing to count - optimize as needed
        documents = self._list_appwrite_documents(collection_id, filters)
        return len(documents)
    
    def _search_appwrite_documents(self, collection_id: str, search_term: str, fields: List[str]) -> List[Dict[str, Any]]:
        """Search documents in Appwrite."""
        # Implement Appwrite-specific search queries
        # This is a basic implementation - enhance based on Appwrite search capabilities
        return self._list_appwrite_documents(collection_id)
    
    def _create_appwrite_collection(self, collection_id: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Create collection in Appwrite."""
        return self.appwrite_db.create_collection(
            database_id=self.appwrite_database_id,
            collection_id=collection_id,
            name=schema.get("name", collection_id),
            document_security=schema.get("document_security", False)
        )
    
    def _drop_appwrite_collection(self, collection_id: str) -> None:
        """Drop collection from Appwrite."""
        self.appwrite_db.delete_collection(
            database_id=self.appwrite_database_id,
            collection_id=collection_id
        )
    
    def _list_appwrite_collections(self) -> List[str]:
        """List collections in Appwrite."""
        response = self.appwrite_db.list_collections(database_id=self.appwrite_database_id)
        return [col.get("$id", col.get("id")) for col in response.get("collections", [])]
    
    # --- PostgreSQL Helper Methods ---
    def _create_postgres_record(self, table_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create record in PostgreSQL."""
        # Build INSERT query
        columns = list(data.keys())
        placeholders = ["%s" for _ in range(len(columns))]
        values = list(data.values())
        
        query = f"""
            INSERT INTO {table_name} ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
            RETURNING *
        """
        
        result = self.postgres_client.run(query, values, fetch="one")
        return dict(result) if result else {}
    
    def _get_postgres_record(self, table_name: str, record_id: str) -> Dict[str, Any]:
        """Get record from PostgreSQL."""
        query = f"SELECT * FROM {table_name} WHERE id = %s"
        result = self.postgres_client.run(query, [record_id], fetch="one")
        return dict(result) if result else {}
    
    def _list_postgres_records(self, table_name: str, filters: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List records from PostgreSQL."""
        query = f"SELECT * FROM {table_name}"
        params = []
        
        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(f"{key} = %s")
                params.append(value)
            query += f" WHERE {' AND '.join(conditions)}"
        
        if limit:
            query += f" LIMIT {limit}"
        
        results = self.postgres_client.run(query, params, fetch="all")
        return [dict(row) for row in results] if results else []
    
    def _update_postgres_record(self, table_name: str, record_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update record in PostgreSQL."""
        set_clauses = []
        values = []
        
        for key, value in data.items():
            set_clauses.append(f"{key} = %s")
            values.append(value)
        
        values.append(record_id)  # Add record_id as last parameter
        
        query = f"""
            UPDATE {table_name} 
            SET {', '.join(set_clauses)}
            WHERE id = %s
            RETURNING *
        """
        
        result = self.postgres_client.run(query, values, fetch="one")
        return dict(result) if result else {}
    
    def _delete_postgres_record(self, table_name: str, record_id: str) -> None:
        """Delete record from PostgreSQL."""
        query = f"DELETE FROM {table_name} WHERE id = %s"
        self.postgres_client.run(query, [record_id], fetch="none")
    
    def _count_postgres_records(self, table_name: str, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records in PostgreSQL."""
        query = f"SELECT COUNT(*) as count FROM {table_name}"
        params = []
        
        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(f"{key} = %s")
                params.append(value)
            query += f" WHERE {' AND '.join(conditions)}"
        
        result = self.postgres_client.run(query, params, fetch="one")
        return result["count"] if result else 0
    
    def _search_postgres_records(self, table_name: str, search_term: str, fields: List[str]) -> List[Dict[str, Any]]:
        """Search records in PostgreSQL using full-text search."""
        # Build search conditions for each field
        conditions = []
        params = []
        
        for field in fields:
            conditions.append(f"{field} ILIKE %s")
            params.append(f"%{search_term}%")
        
        query = f"SELECT * FROM {table_name} WHERE {' OR '.join(conditions)}"
        results = self.postgres_client.run(query, params, fetch="all")
        return [dict(row) for row in results] if results else []
    
    def _create_postgres_table(self, table_name: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Create table in PostgreSQL."""
        # This would need schema translation from universal format to PostgreSQL DDL
        # For now, assume schema contains raw SQL
        if "sql" in schema:
            self.postgres_client.run(schema["sql"], fetch="none")
            return {"table": table_name, "status": "created"}
        else:
            raise ValueError("PostgreSQL table creation requires 'sql' key in schema")
    
    def _drop_postgres_table(self, table_name: str) -> None:
        """Drop table from PostgreSQL."""
        query = f"DROP TABLE IF EXISTS {table_name}"
        self.postgres_client.run(query, fetch="none")
    
    def _list_postgres_tables(self) -> List[str]:
        """List tables in PostgreSQL."""
        query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """
        results = self.postgres_client.run(query, fetch="all")
        return [row["table_name"] for row in results] if results else []
    
    # === Compatibility Layer (for existing services) ===
    # These methods maintain backward compatibility while routing to new universal methods
    
    def create_document(self, collection_id: str, data: Dict[str, Any], document_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Legacy compatibility: maps to create_record.
        
        Used by: ensemble_inference_service.py, evaluation_service.py, grobid_service.py
        
        .. deprecated:: 1.0.0
            Use create_record() instead for universal database operations.
        """
        warnings.warn(
            "create_document() is deprecated. Use create_record() for universal database operations.",
            DeprecationWarning,
            stacklevel=2
        )
        self.logger.debug(f"Legacy create_document called - routing to create_record", source="database_manager", event_type="legacy_compatibility")
        result = self.create_record(collection_id, data, document_id)
        # Return primary result for backward compatibility
        return result.get("primary", result)
    
    def get_document(self, collection_id: str, document_id: str) -> Dict[str, Any]:
        """
        Legacy compatibility: maps to get_record.
        
        Used by: evaluation_service.py, groundtruth_service.py
        
        .. deprecated:: 1.0.0
            Use get_record() instead for universal database operations.
        """
        warnings.warn(
            "get_document() is deprecated. Use get_record() for universal database operations.",
            DeprecationWarning,
            stacklevel=2
        )
        self.logger.debug(f"Legacy get_document called - routing to get_record", source="database_manager", event_type="legacy_compatibility")
        return self.get_record(collection_id, document_id)
    
    def list_documents(self, collection_id: str, queries: Optional[List] = None) -> List[Dict[str, Any]]:
        """
        Legacy compatibility: maps to list_records.
        
        Used by: grobid_service.py, enhanced_merging_service.py, tei_processing_service.py
        
        .. deprecated:: 1.0.0
            Use list_records() instead for universal database operations.
        """
        warnings.warn(
            "list_documents() is deprecated. Use list_records() for universal database operations.",
            DeprecationWarning,
            stacklevel=2
        )
        self.logger.debug(f"Legacy list_documents called - routing to list_records", source="database_manager", event_type="legacy_compatibility")
        filters = self._convert_queries_to_filters(queries) if queries else None
        return self.list_records(collection_id, filters)
    
    def update_document(self, collection_id: str, document_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Legacy compatibility: maps to update_record.
        
        Used by: ensemble_inference_service.py, evaluation_service.py
        
        .. deprecated:: 1.0.0
            Use update_record() instead for universal database operations.
        """
        warnings.warn(
            "update_document() is deprecated. Use update_record() for universal database operations.",
            DeprecationWarning,
            stacklevel=2
        )
        self.logger.debug(f"Legacy update_document called - routing to update_record", source="database_manager", event_type="legacy_compatibility")
        result = self.update_record(collection_id, document_id, data)
        # Return primary result for backward compatibility
        return result.get("primary", result)
    
    def delete_document(self, collection_id: str, document_id: str) -> None:
        """
        Legacy compatibility: maps to delete_record.
        
        Used by: groundtruth_service.py, tei_processing_service.py
        
        .. deprecated:: 1.0.0
            Use delete_record() instead for universal database operations.
        """
        warnings.warn(
            "delete_document() is deprecated. Use delete_record() for universal database operations.",
            DeprecationWarning,
            stacklevel=2
        )
        self.logger.debug(f"Legacy delete_document called - routing to delete_record", source="database_manager", event_type="legacy_compatibility")
        return self.delete_record(collection_id, document_id)
    
    # === Legacy Collection Operations ===
    def create_collection(self, collection_id: str, name: str, document_security: bool = False) -> Dict[str, Any]:
        """
        Legacy compatibility: maps to create_table.
        
        Used by: setup services and database initialization
        """
        self.logger.debug(f"Legacy create_collection called - routing to create_table", source="database_manager", event_type="legacy_compatibility")
        schema = {
            "name": name,
            "document_security": document_security
        }
        result = self.create_table(collection_id, schema)
        
        # Return Appwrite-style result for compatibility
        if "appwrite" in result.get("backends", {}):
            return result["backends"]["appwrite"]
        elif "postgres" in result.get("backends", {}):
            return {"$id": collection_id, "name": name, "status": "created"}
        else:
            return {"$id": collection_id, "status": "exists"}
    
    def delete_collection(self, collection_id: str) -> None:
        """
        Legacy compatibility: maps to drop_table.
        
        Used by: database reset operations
        """
        self.logger.debug(f"Legacy delete_collection called - routing to drop_table", source="database_manager", event_type="legacy_compatibility")
        return self.drop_table(collection_id)
    
    def get_collection(self, collection_id: str) -> Dict[str, Any]:
        """
        Legacy compatibility: check if collection/table exists.
        
        Used by: collection management in services
        """
        self.logger.debug(f"Legacy get_collection called - checking table existence", source="database_manager", event_type="legacy_compatibility")
        
        if self.table_exists(collection_id):
            return {"$id": collection_id, "name": collection_id, "status": "exists"}
        else:
            # Raise AppwriteException for compatibility with existing error handling
            raise AppwriteException(message=f"Collection '{collection_id}' not found", code=404)
    
    def list_collections(self) -> List[Dict[str, Any]]:
        """
        Legacy compatibility: maps to list_tables.
        
        Used by: collection discovery and management
        """
        self.logger.debug(f"Legacy list_collections called - routing to list_tables", source="database_manager", event_type="legacy_compatibility")
        tables = self.list_tables()
        
        # Return Appwrite-style collection format for compatibility
        return [{"$id": table, "name": table} for table in tables]
    
    # === Legacy Attribute Operations (Appwrite-specific) ===
    def create_attribute(self, collection_id: str, attr_type: str, key: str, **kwargs) -> Dict[str, Any]:
        """
        Legacy compatibility: Appwrite-specific attribute creation.
        
        Note: This is Appwrite-specific and may not translate to other backends.
        Used by: schema management in setup services
        """
        self.logger.debug(f"Legacy create_attribute called for {collection_id}.{key}", source="database_manager", event_type="legacy_compatibility")
        
        if self.appwrite_db and self._should_use_appwrite():
            try:
                # Route to Appwrite-specific attribute creation
                if attr_type == "string":
                    return self.appwrite_db.create_string_attribute(
                        database_id=self.appwrite_database_id,
                        collection_id=collection_id,
                        key=key,
                        size=kwargs.get("size", 255),
                        required=kwargs.get("required", False),
                        default=kwargs.get("default"),
                        array=kwargs.get("array", False)
                    )
                elif attr_type == "integer":
                    return self.appwrite_db.create_integer_attribute(
                        database_id=self.appwrite_database_id,
                        collection_id=collection_id,
                        key=key,
                        required=kwargs.get("required", False),
                        min=kwargs.get("min"),
                        max=kwargs.get("max"),
                        default=kwargs.get("default"),
                        array=kwargs.get("array", False)
                    )
                elif attr_type == "float":
                    return self.appwrite_db.create_float_attribute(
                        database_id=self.appwrite_database_id,
                        collection_id=collection_id,
                        key=key,
                        required=kwargs.get("required", False),
                        min=kwargs.get("min"),
                        max=kwargs.get("max"),
                        default=kwargs.get("default"),
                        array=kwargs.get("array", False)
                    )
                elif attr_type == "boolean":
                    return self.appwrite_db.create_boolean_attribute(
                        database_id=self.appwrite_database_id,
                        collection_id=collection_id,
                        key=key,
                        required=kwargs.get("required", False),
                        default=kwargs.get("default"),
                        array=kwargs.get("array", False)
                    )
                elif attr_type == "datetime":
                    return self.appwrite_db.create_datetime_attribute(
                        database_id=self.appwrite_database_id,
                        collection_id=collection_id,
                        key=key,
                        required=kwargs.get("required", False),
                        default=kwargs.get("default"),
                        array=kwargs.get("array", False)
                    )
                else:
                    raise ValueError(f"Unsupported attribute type: {attr_type}")
                    
            except Exception as e:
                self.logger.error(f"Failed to create attribute {key} in {collection_id}: {e}", source="database_manager", event_type="create_attribute")
                raise
        else:
            # For non-Appwrite backends, this operation may not be applicable
            self.logger.warning(f"create_attribute called but Appwrite not available - this operation is Appwrite-specific", source="database_manager", event_type="legacy_compatibility")
            return {"key": key, "type": attr_type, "status": "skipped", "reason": "Appwrite not available"}
    
    def delete_attribute(self, collection_id: str, key: str) -> None:
        """
        Legacy compatibility: Appwrite-specific attribute deletion.
        
        Used by: schema management and cleanup operations
        """
        self.logger.debug(f"Legacy delete_attribute called for {collection_id}.{key}", source="database_manager", event_type="legacy_compatibility")
        
        if self.appwrite_db and self._should_use_appwrite():
            try:
                self.appwrite_db.delete_attribute(
                    database_id=self.appwrite_database_id,
                    collection_id=collection_id,
                    key=key
                )
            except Exception as e:
                self.logger.error(f"Failed to delete attribute {key} from {collection_id}: {e}", source="database_manager", event_type="delete_attribute")
                raise
        else:
            self.logger.warning(f"delete_attribute called but Appwrite not available - this operation is Appwrite-specific", source="database_manager", event_type="legacy_compatibility")

    # === COLLECTION OPERATIONS ===
    def create_collection(self, collection_id: str, name: str, document_security: bool = False) -> dict:
        """
        Create a new collection.

        Parameters
        ----------
        collection_id : str
            Unique collection identifier.
        name : str
            Human-readable collection name.
        document_security : bool, optional
            Enable document-level permissions. Defaults to False.

        Returns
        -------
        dict
            Created collection details.
        """
        try:
            # Check existence
            self.get_collection(collection_id)
            logger.debug(f"Collection '{collection_id}' already exists. Skipping creation.",
                         source="database_manager", event_type="create_collection")
            return {"$id": collection_id, "status": "exists"}
        except AppwriteException as e:
            if e.code == 404:
                # Create only if not found
                result = self.appwrite_db.create_collection(
                    database_id=self.appwrite_database_id,
                    collection_id=collection_id,
                    name=name,
                    document_security=document_security
                )
                logger.info(f"Created collection '{collection_id}'",
                            source="database_manager", event_type="create_collection")
                return result
            else:
                logger.error(f"Failed to create collection '{collection_id}'",
                             source="database_manager", error=e, event_type="create_collection")
                raise

    def delete_collection(self, collection_id: str) -> None:
        """
        Delete a collection by its ID.

        Parameters
        ----------
        collection_id : str
            Unique collection identifier.
        """
        try:
            self.appwrite_db.delete_collection(self.appwrite_database_id, collection_id)
            logger.warning(f"Deleted collection '{collection_id}'", source="database_manager",
                           event_type="delete_collection")
        except AppwriteException as e:
            logger.error(f"Failed to delete collection '{collection_id}'", source="database_manager", error=e,
                         event_type="delete_collection")
            raise

    def get_collection(self, collection_id: str) -> dict:
        """
        Fetch details of a collection.

        Parameters
        ----------
        collection_id : str
            Unique collection identifier.

        Returns
        -------
        dict
            Collection details.
        """
        try:
            result = self.appwrite_db.get_collection(self.appwrite_database_id, collection_id)
            logger.debug(f"Fetched collection '{collection_id}'", source="database_manager",
                         event_type="get_collection")
            return result
        except AppwriteException as e:
            logger.error(f"Failed to fetch collection '{collection_id}'", source="database_manager", error=e,
                         event_type="get_collection")
            raise

    def list_collections(self) -> list:
        """
        List all collections in the database.

        Returns
        -------
        list
            List of collections.
        """
        try:
            response = self.appwrite_db.list_collections(self.appwrite_database_id)
            logger.debug("Listed all collections", source="database_manager", event_type="list_collections")
            return response['collections']
        except AppwriteException as e:
            logger.error("Failed to list collections", source="database_manager", error=e,
                         event_type="list_collections")
            raise

    # === ATTRIBUTE OPERATIONS ===
    def create_attribute(self, collection_id: str, attr_type: str, key: str, **kwargs) -> dict:
        """
        Create an attribute of any supported type in a collection.

        Parameters
        ----------
        collection_id : str
            Target collection ID.
        attr_type : str
            Attribute type ('string', 'integer', 'float', 'boolean', 'datetime', 'enum', 'ip', 'email', 'url', 'relationship').
        key : str
            Attribute key (name).
        kwargs : dict
            Additional parameters required for the attribute type.

        Returns
        -------
        dict
            Created attribute details.

        Raises
        ------
        ValueError
            If the attribute type is not supported.
        AppwriteException
            If API call fails.
        """
        try:
            # Check if attribute exists
            collection = self.get_collection(collection_id)
            if any(attr['key'] == key for attr in collection['attributes']):
                logger.debug(f"Attribute '{key}' already exists in '{collection_id}'. Skipping creation.",
                             source="database_manager", event_type="create_attribute")
                return {"key": key, "status": "exists"}

            # Create attribute if not found
            method = getattr(self.appwrite_db, f"create_{attr_type}_attribute", None)
            if not method:
                raise ValueError(f"Unsupported attribute type: {attr_type}")

            result = method(
                database_id=self.appwrite_database_id,
                collection_id=collection_id,
                key=key,
                **kwargs
            )
            logger.info(f"Created {attr_type} attribute '{key}' in '{collection_id}'",
                        source="database_manager", event_type="create_attribute")
            return result
        except AppwriteException as e:
            logger.error(f"Failed to create {attr_type} attribute '{key}' in '{collection_id}'",
                         source="database_manager", error=e, event_type="create_attribute")
            raise

    def delete_attribute(self, collection_id: str, key: str) -> None:
        """
        Delete an attribute from a collection.

        Parameters
        ----------
        collection_id : str
            Target collection ID.
        key : str
            Attribute key (name).
        """
        try:
            self.appwrite_db.delete_attribute(self.appwrite_database_id, collection_id, key)
            logger.warning(f"Deleted attribute '{key}' from '{collection_id}'", source="database_manager",
                           event_type="delete_attribute")
        except AppwriteException as e:
            logger.error(f"Failed to delete attribute '{key}' from '{collection_id}'", source="database_manager",
                         error=e, event_type="delete_attribute")
            raise

