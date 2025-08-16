"""
Database Manager for Polymer NLP Extractor.

Purpose
-------
Relational database operations layer for PostgreSQL with backward compatibility support.
Graph operations (Neo4j) are handled separately by GraphManager in graph_manager.py

The manager provides universal method names for PostgreSQL operations and maintains
backward compatibility for legacy code that expects Appwrite-style method signatures.

Environment Variables
---------------------
Required for database operations:
- USE_POSTGRESQL_DB=true/false - Enable/disable PostgreSQL database operations
- DATA_BACKEND=postgres - Should be set to postgres for this simplified version

Design Principles
-----------------
1. PostgreSQL-first design with clear error messages when disabled
2. Universal method names (create_record, get_record, etc.) for consistency
3. Comprehensive error handling and logging
4. Backward compatibility via deprecated method mapping
5. Integration with model_config.py entity types and validation patterns
6. SEPARATION: Graph operations handled by GraphManager, not this class

Examples
--------
>>> from polymer_extractor.storage.database_manager import DatabaseManager
>>> db = DatabaseManager()
>>> result = db.create_record("research_papers", {"title": "Polymer Study", "doi": "10.1234/test"})
>>> # Uses PostgreSQL backend

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

from polymer_extractor.storage.postgresql_client import PostgresClient
from polymer_extractor.utils.logging import Logger

logger = Logger()


class DatabaseManager:
    """
    PostgreSQL database operations manager with backward compatibility support.
    
    Provides PostgreSQL-based CRUD operations with universal method names.
    Maintains backward compatibility for legacy code expecting Appwrite-style methods.
    
    Note: Graph database operations (Neo4j) are handled by GraphManager in graph_manager.py
    """

    def __init__(self):
        """Initialize PostgreSQL client based on environment configuration."""
        # NOTE: Cannot use Logger here due to circular dependency (Logger -> DatabaseManager -> Logger)
        # Use simple print statements for initialization logging
        
        # Initialize PostgreSQL client
        self.postgres_client = None
        
        # Initialize PostgreSQL if enabled
        if self._should_use_postgres():
            try:
                self.postgres_client = PostgresClient()
                print("[DATABASE_MANAGER] PostgreSQL database client initialized")
            except Exception as e:
                print(f"[DATABASE_MANAGER] Failed to initialize PostgreSQL client: {e}")
                
        # Validate PostgreSQL is available
        if not self.postgres_client:
            print("[DATABASE_MANAGER] PostgreSQL not available - check environment configuration and server status")

    def _should_use_postgres(self) -> bool:
        """Check if PostgreSQL should be used based on .env flags."""
        return (os.getenv("USE_POSTGRESQL_DB", "true").lower() == "true" or
                os.getenv("DATA_BACKEND", "postgres") == "postgres")
    
    def _ensure_postgres_available(self) -> None:
        """Ensure PostgreSQL client is available, raise error if not."""
        if not self.postgres_client:
            raise RuntimeError(
                "PostgreSQL database not available. Please check:\n"
                "1. Environment variable USE_POSTGRESQL_DB=true\n"
                "2. PostgreSQL server is running\n"
                "3. Database connection configuration is correct"
            )

    # === Universal CRUD Operations ===
    def create_record(self, table_name: str, data: Dict[str, Any], record_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create record in PostgreSQL database.
        
        Parameters
        ----------
        table_name : str
            Table name
        data : dict
            Record data to create
        record_id : str, optional
            Specific record ID (ignored for PostgreSQL as it uses auto-increment)
            
        Returns
        -------
        dict
            Created record details
        """
        self._ensure_postgres_available()
        
        try:
            result = self._create_postgres_record(table_name, data)
            logger.info(f"Record created successfully in {table_name}", source="database_manager", event_type="create_record")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create record in {table_name}: {e}", source="database_manager", event_type="create_record")
            raise

    def get_record(self, table_name: str, record_id: str) -> Dict[str, Any]:
        """
        Get single record from PostgreSQL database.
        
        Parameters
        ----------
        table_name : str
            Table name
        record_id : str
            Record ID to retrieve
            
        Returns
        -------
        dict
            Record data from PostgreSQL
        """
        self._ensure_postgres_available()
        
        try:
            result = self._get_postgres_record(table_name, record_id)
            logger.debug(f"Retrieved record {record_id} from {table_name}", source="database_manager", event_type="get_record")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get record {record_id} from {table_name}: {e}", source="database_manager", event_type="get_record")
            raise

    def list_records(self, table_name: str, filters: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        List multiple records from PostgreSQL database.
        
        Parameters
        ----------
        table_name : str
            Table name
        filters : dict, optional
            Filter conditions
        limit : int, optional
            Maximum number of records to return
            
        Returns
        -------
        list
            List of records from PostgreSQL
        """
        self._ensure_postgres_available()
        
        try:
            result = self._list_postgres_records(table_name, filters, limit)
            logger.debug(f"Listed {len(result)} records from {table_name}", source="database_manager", event_type="list_records")
            return result
            
        except Exception as e:
            logger.error(f"Failed to list records from {table_name}: {e}", source="database_manager", event_type="list_records")
            raise

    def update_record(self, table_name: str, record_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update record in PostgreSQL database.
        
        Parameters
        ----------
        table_name : str
            Table name
        record_id : str
            Record ID to update
        data : dict
            Updated data
            
        Returns
        -------
        dict
            Updated record details
        """
        self._ensure_postgres_available()
        
        try:
            result = self._update_postgres_record(table_name, record_id, data)
            logger.info(f"Record {record_id} updated in {table_name}", source="database_manager", event_type="update_record")
            return result
            
        except Exception as e:
            logger.error(f"Failed to update record {record_id} in {table_name}: {e}", source="database_manager", event_type="update_record")
            raise

    def delete_record(self, table_name: str, record_id: str) -> None:
        """
        Delete record from PostgreSQL database.
        
        Parameters
        ----------
        table_name : str
            Table name
        record_id : str
            Record ID to delete
        """
        self._ensure_postgres_available()
        
        try:
            self._delete_postgres_record(table_name, record_id)
            logger.info(f"Record {record_id} deleted from {table_name}", source="database_manager", event_type="delete_record")
            
        except Exception as e:
            logger.error(f"Failed to delete record {record_id} from {table_name}: {e}", source="database_manager", event_type="delete_record")
            raise

    def upsert_record(self, table_name: str, data: Dict[str, Any], unique_key: str) -> Dict[str, Any]:
        """
        Upsert (insert or update) record in PostgreSQL database.
        
        Parameters
        ----------
        table_name : str
            Table name
        data : dict
            Record data
        unique_key : str
            Field name to use for uniqueness check
            
        Returns
        -------
        dict
            Upserted record details
        """
        self._ensure_postgres_available()
        
        try:
            # Try to find existing record by unique key
            filters = {unique_key: data.get(unique_key)}
            existing_records = self.list_records(table_name, filters, limit=1)
            
            if existing_records:
                # Update existing record
                record_id = existing_records[0].get("id")
                return self.update_record(table_name, record_id, data)
            else:
                # Create new record
                return self.create_record(table_name, data)
                
        except Exception as e:
            logger.error(f"Failed to upsert record in {table_name}: {e}", source="database_manager", event_type="upsert_record")
            raise
    
    def count_records(self, table_name: str, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count records in PostgreSQL database.
        
        Parameters
        ----------
        table_name : str
            Table name
        filters : dict, optional
            Filter conditions
            
        Returns
        -------
        int
            Number of records matching filters
        """
        self._ensure_postgres_available()
        
        try:
            count = self._count_postgres_records(table_name, filters)
            logger.debug(f"Counted {count} records in {table_name}", source="database_manager", event_type="count_records")
            return count
            
        except Exception as e:
            logger.error(f"Failed to count records in {table_name}: {e}", source="database_manager", event_type="count_records")
            raise
    
    def search_records(self, table_name: str, search_term: str, fields: List[str]) -> List[Dict[str, Any]]:
        """
        Search records in PostgreSQL database using text search.
        
        Parameters
        ----------
        table_name : str
            Table name
        search_term : str
            Text to search for
        fields : list
            List of field names to search in
            
        Returns
        -------
        list
            Records matching search criteria
        """
        self._ensure_postgres_available()
        
        try:
            results = self._search_postgres_records(table_name, search_term, fields)
            logger.debug(f"Found {len(results)} records matching search in {table_name}", source="database_manager", event_type="search_records")
            return results
            
        except Exception as e:
            logger.error(f"Failed to search records in {table_name}: {e}", source="database_manager", event_type="search_records")
            raise

    # === Collection/Table Management ===
    def create_table(self, table_name: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create table in PostgreSQL database - references db/sql/001_core.sql for schema.
        
        Parameters
        ----------
        table_name : str
            Name of table to create
        schema : dict
            Table schema definition
            
        Returns
        -------
        dict
            Created table information
        """
        self._ensure_postgres_available()
        
        try:
            result = self._create_postgres_table(table_name, schema)
            logger.info(f"Table {table_name} created successfully", source="database_manager", event_type="create_table")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create table {table_name}: {e}", source="database_manager", event_type="create_table")
            raise
    
    def drop_table(self, table_name: str) -> None:
        """
        Drop table from PostgreSQL database.
        
        Parameters
        ----------
        table_name : str
            Name of table to delete
        """
        self._ensure_postgres_available()
        
        try:
            self._drop_postgres_table(table_name)
            logger.info(f"Table {table_name} dropped successfully", source="database_manager", event_type="drop_table")
            
        except Exception as e:
            logger.error(f"Failed to drop table {table_name}: {e}", source="database_manager", event_type="drop_table")
            raise

    def list_tables(self) -> List[str]:
        """
        List all tables in PostgreSQL database.
        
        Returns
        -------
        list
            List of table names
        """
        self._ensure_postgres_available()
        
        try:
            result = self._list_postgres_tables()
            logger.debug(f"Listed {len(result)} tables", source="database_manager", event_type="list_tables")
            return result
            
        except Exception as e:
            logger.error(f"Failed to list tables: {e}", source="database_manager", event_type="list_tables")
            raise
    
    def table_exists(self, table_name: str) -> bool:
        """
        Check if table exists in PostgreSQL database.
        
        Parameters
        ----------
        table_name : str
            Table name to check
            
        Returns
        -------
        bool
            True if table exists, False otherwise
        """
        self._ensure_postgres_available()
        
        try:
            tables = self.list_tables()
            exists = table_name in tables
            logger.debug(f"Table {table_name} exists: {exists}", source="database_manager", event_type="table_exists")
            return exists
            
        except Exception as e:
            logger.error(f"Failed to check table existence {table_name}: {e}", source="database_manager", event_type="table_exists")
            raise

    # === PostgreSQL Helper Methods ===
    def _create_postgres_record(self, table_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create record in PostgreSQL using postgres_client."""
        return self.postgres_client.create_record(table_name, data)
    
    def _get_postgres_record(self, table_name: str, record_id: str) -> Dict[str, Any]:
        """Get record from PostgreSQL using postgres_client."""
        return self.postgres_client.get_record(table_name, record_id)
    
    def _list_postgres_records(self, table_name: str, filters: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List records from PostgreSQL using postgres_client."""
        return self.postgres_client.list_records(table_name, filters, limit)
    
    def _update_postgres_record(self, table_name: str, record_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update record in PostgreSQL using postgres_client."""
        return self.postgres_client.update_record(table_name, record_id, data)
    
    def _delete_postgres_record(self, table_name: str, record_id: str) -> None:
        """Delete record from PostgreSQL using postgres_client."""
        self.postgres_client.delete_record(table_name, record_id)
    
    def _count_postgres_records(self, table_name: str, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records in PostgreSQL using postgres_client."""
        return self.postgres_client.count_records(table_name, filters)
    
    def _search_postgres_records(self, table_name: str, search_term: str, fields: List[str]) -> List[Dict[str, Any]]:
        """Search records in PostgreSQL using postgres_client."""
        return self.postgres_client.search_records(table_name, search_term, fields)
    
    def _create_postgres_table(self, table_name: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Create table in PostgreSQL using postgres_client."""
        return self.postgres_client.create_table(table_name, schema)
    
    def _drop_postgres_table(self, table_name: str) -> None:
        """Drop table from PostgreSQL using postgres_client."""
        self.postgres_client.drop_table(table_name)
    
    def _list_postgres_tables(self) -> List[str]:
        """List tables in PostgreSQL using postgres_client."""
        return self.postgres_client.list_tables()

    # === Compatibility Layer (for existing services) ===
    # These methods maintain backward compatibility while routing to new universal methods
    
    def create_document(self, collection_id: str, data: Dict[str, Any], document_id: Optional[str] = None) -> Dict[str, Any]:
        """Legacy compatibility: create_document -> create_record."""
        warnings.warn(
            "create_document is deprecated. Use create_record instead.", 
            DeprecationWarning, 
            stacklevel=2
        )
        return self.create_record(collection_id, data, document_id)
    
    def get_document(self, collection_id: str, document_id: str) -> Dict[str, Any]:
        """Legacy compatibility: get_document -> get_record."""
        warnings.warn(
            "get_document is deprecated. Use get_record instead.", 
            DeprecationWarning, 
            stacklevel=2
        )
        return self.get_record(collection_id, document_id)
    
    def list_documents(self, collection_id: str, queries: Optional[List] = None) -> List[Dict[str, Any]]:
        """Legacy compatibility: list_documents -> list_records."""
        warnings.warn(
            "list_documents is deprecated. Use list_records instead.", 
            DeprecationWarning, 
            stacklevel=2
        )
        # Convert queries to filters if needed
        filters = self._convert_queries_to_filters(queries) if queries else None
        return self.list_records(collection_id, filters)
    
    def update_document(self, collection_id: str, document_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy compatibility: update_document -> update_record."""
        warnings.warn(
            "update_document is deprecated. Use update_record instead.", 
            DeprecationWarning, 
            stacklevel=2
        )
        return self.update_record(collection_id, document_id, data)
    
    def delete_document(self, collection_id: str, document_id: str) -> None:
        """Legacy compatibility: delete_document -> delete_record."""
        warnings.warn(
            "delete_document is deprecated. Use delete_record instead.", 
            DeprecationWarning, 
            stacklevel=2
        )
        self.delete_record(collection_id, document_id)

    # === Legacy Collection Operations ===
    def create_collection(self, collection_id: str, name: str, document_security: bool = False) -> Dict[str, Any]:
        """Legacy compatibility: create_collection -> create_table."""
        warnings.warn(
            "create_collection is deprecated. Use create_table instead.", 
            DeprecationWarning, 
            stacklevel=2
        )
        schema = {"name": name, "document_security": document_security}
        return self.create_table(collection_id, schema)
    
    def delete_collection(self, collection_id: str) -> None:
        """Legacy compatibility: delete_collection -> drop_table."""
        warnings.warn(
            "delete_collection is deprecated. Use drop_table instead.", 
            DeprecationWarning, 
            stacklevel=2
        )
        self.drop_table(collection_id)
    
    def get_collection(self, collection_id: str) -> Dict[str, Any]:
        """Legacy compatibility: get_collection (returns basic table info)."""
        warnings.warn(
            "get_collection is deprecated. Use table_exists instead.", 
            DeprecationWarning, 
            stacklevel=2
        )
        if self.table_exists(collection_id):
            return {"$id": collection_id, "name": collection_id, "enabled": True}
        else:
            raise RuntimeError(f"Table '{collection_id}' not found")
    
    def list_collections(self) -> List[Dict[str, Any]]:
        """Legacy compatibility: list_collections -> list_tables."""
        warnings.warn(
            "list_collections is deprecated. Use list_tables instead.", 
            DeprecationWarning, 
            stacklevel=2
        )
        tables = self.list_tables()
        return [{"$id": table, "name": table, "enabled": True} for table in tables]

    # === Legacy Attribute Operations (Appwrite-specific) ===
    def create_attribute(self, collection_id: str, attr_type: str, key: str, **kwargs) -> Dict[str, Any]:
        """Legacy compatibility: Appwrite-style attribute creation (not implemented for PostgreSQL)."""
        warnings.warn(
            "create_attribute is deprecated and not implemented for PostgreSQL. Use SQL ALTER TABLE instead.", 
            DeprecationWarning, 
            stacklevel=2
        )
        # Return mock success for backward compatibility
        return {"key": key, "type": attr_type, "status": "available"}
    
    def delete_attribute(self, collection_id: str, key: str) -> None:
        """Legacy compatibility: Appwrite-style attribute deletion (not implemented for PostgreSQL)."""
        warnings.warn(
            "delete_attribute is deprecated and not implemented for PostgreSQL. Use SQL ALTER TABLE instead.", 
            DeprecationWarning, 
            stacklevel=2
        )
        # Silent success for backward compatibility
        pass

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
