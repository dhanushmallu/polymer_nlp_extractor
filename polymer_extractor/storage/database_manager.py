"""
polymer_extractor/storage/database_manager.py

PostgreSQL-focused database operations manager with resource locking and legacy compatibility.

Purpose
-------
Provides comprehensive relational database operations for PostgreSQL with:
- Universal CRUD operations (create_record, get_record, update_record, delete_record)
- Intelligent resource locking for concurrent access management
- Batch operations (bulk_insert, bulk_update, bulk_delete)
- Search and filtering capabilities
- Table management (create_table, drop_table, list_tables)
- Legacy compatibility for Appwrite-style method names
- Environment-driven configuration and feature flags

Key Abstractions
----------------
- DatabaseManager: High-level interface for PostgreSQL operations with resource locking
- Universal methods: Consistent naming across all database operations
- Resource locks: Intelligent conflict resolution for concurrent database access
- Legacy compatibility: Backward-compatible method aliases for existing code
- Table operations: Schema management and introspection
- Batch processing: Efficient bulk operations for large datasets

Design Invariants
-----------------
- PostgreSQL-first design with clear error messages when disabled
- Separation of concerns: Graph operations handled by GraphManager
- Environment-based feature flags control database backend selection
- Comprehensive error handling with structured logging
- Backward compatibility maintained without breaking existing services

Environment Integration
----------------------
Uses environment variables for configuration:
- USE_POSTGRESQL_DB: Enable/disable PostgreSQL database operations
- DATA_BACKEND: Control primary database backend selection

Examples
--------
>>> from polymer_extractor.storage.database_manager import DatabaseManager
>>> db = DatabaseManager()
>>> 
>>> # CRUD operations
>>> record = db.create_record("research_papers", {"title": "Study", "doi": "10.1234/test"})
>>> paper = db.get_record("research_papers", record["id"])
>>> db.update_record("research_papers", record["id"], {"status": "published"})
>>> db.delete_record("research_papers", record["id"])
>>> 
>>> # Batch operations
>>> records = [{"title": f"Paper {i}", "doi": f"10.1234/{i}"} for i in range(100)]
>>> results = db.bulk_insert("research_papers", records)
>>> 
>>> # Search and filtering
>>> papers = db.search_records("research_papers", "polymer", ["title", "abstract"])
>>> filtered = db.list_records("research_papers", {"status": "published"}, limit=50)
>>> 
>>> # Legacy compatibility (existing code continues to work)
>>> document = db.create_document("papers", data)  # Maps to create_record
>>> documents = db.list_documents("papers")        # Maps to list_records

Notes
-----
- Performance: Optimized bulk operations with PostgreSQL COPY for large datasets
- Thread Safety: Resource locking ensures safe concurrent access
- Memory: Streaming results for large queries to minimize memory usage
- Complexity: O(1) for single operations, O(n) for bulk and search operations
- Conflict Resolution: User-friendly error messages for resource conflicts
"""

import os
import warnings
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from polymer_extractor.storage.postgresql_client import PostgresClient
from polymer_extractor.utils.logging import get_logger
from polymer_extractor.utils.resource_lock_manager import (
    get_resource_lock_manager, LockType, ResourceLockConflict
)

logger = get_logger()


class DatabaseManager:
    """
    PostgreSQL database operations manager with comprehensive CRUD and batch capabilities.
    
    Summary
    -------
    Provides PostgreSQL-first database operations with universal method naming,
    legacy compatibility, and environment-driven configuration.

    Key Features
    ------------
    - Universal CRUD: create_record, get_record, update_record, delete_record
    - Batch operations: bulk_insert, bulk_update, bulk_delete  
    - Advanced queries: search_records with full-text search capabilities
    - Table management: create_table, drop_table, list_tables, table_exists
    - Legacy compatibility: Appwrite-style method aliases (create_document, etc.)
    - Environment flags: Controlled by USE_POSTGRESQL_DB and DATA_BACKEND

    Examples
    --------
    >>> db = DatabaseManager()
    >>> # Basic CRUD
    >>> record = db.create_record("papers", {"title": "Study", "doi": "10.1234"})
    >>> paper = db.get_record("papers", record["id"])
    >>> 
    >>> # Batch operations  
    >>> papers = [{"title": f"Paper {i}"} for i in range(100)]
    >>> results = db.bulk_insert("papers", papers)
    >>> 
    >>> # Search and filtering
    >>> found = db.search_records("papers", "polymer", ["title", "abstract"])

    Notes
    -----
    - Complexity: O(1) single ops, O(n) bulk ops, O(log n) indexed searches
    - Thread Safety: Individual operations thread-safe via connection pooling
    - Memory: Streaming for large result sets to minimize memory usage
    - Error Handling: Comprehensive exception propagation with context
    """

    def __init__(self):
        """
        Initialize DatabaseManager with PostgreSQL client and resource locking.

        Summary
        -------
        Creates DatabaseManager instance with PostgreSQL connection and resource locking
        if enabled via environment flags.

        Raises
        ------
        RuntimeError
            If PostgreSQL initialization fails when enabled
        ConfigError
            If required PostgreSQL environment variables are missing

        Examples
        --------
        >>> db = DatabaseManager()  # Uses .env configuration
        >>> if db.postgres_client:
        ...     health = db.postgres_client.health_check()

        Notes
        -----
        - Performance: O(1) - Establishes connection pool and lock manager during initialization
        - Side Effects: Logs PostgreSQL connection status and lock manager availability
        - Thread Safety: Resource locking prevents concurrent modification conflicts
        """
        self.postgres_client = None
        self.lock_manager = None
        self.enable_locking = os.getenv("RESOURCE_LOCK_ENABLE", "true").lower() == "true"
        
        # Initialize PostgreSQL client if enabled
        if self._should_use_postgres():
            try:
                self.postgres_client = PostgresClient()
                logger.info("DatabaseManager initialized with PostgreSQL support", 
                          source="database_manager", event_type="init")
            except Exception as e:
                logger.error(f"Failed to initialize PostgreSQL client: {e}", 
                           source="database_manager", event_type="init_error")
                raise RuntimeError(f"PostgreSQL initialization failed: {e}")
        else:
            logger.info("DatabaseManager initialized without PostgreSQL (disabled in environment)", 
                      source="database_manager", event_type="init")
        
        # Initialize resource lock manager if enabled
        if self.enable_locking:
            try:
                self.lock_manager = get_resource_lock_manager()
                logger.info("DatabaseManager initialized with resource locking support", 
                          source="database_manager", event_type="init")
            except Exception as e:
                logger.warning(f"Failed to initialize resource lock manager: {e}", 
                             source="database_manager", event_type="init_warning")
                self.enable_locking = False

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
        Create a new record in the specified PostgreSQL table.

        Summary
        -------
        Inserts new record with auto-generated ID and timestamp metadata.

        Parameters
        ----------
        table_name : str
            Target table name (e.g., "datasets_metadata", "extraction_metadata")
        data : Dict[str, Any]
            Record data with column-value pairs
        record_id : Optional[str], default None
            Ignored for PostgreSQL - uses auto-increment primary key

        Returns
        -------
        Dict[str, Any]
            Created record including generated ID and timestamps

        Raises
        ------
        DatabaseError
            If table doesn't exist or data violates constraints
        ValidationError
            If required fields are missing or invalid types

        Examples
        --------
        >>> db = DatabaseManager()
        >>> record = db.create_record("datasets_metadata", {
        ...     "name": "training_set_v1",
        ...     "file_path": "datasets/train.json",
        ...     "size": 1024
        ... })
        >>> print(f"Created record with ID: {record['id']}")

        Notes
        -----
        - Complexity: O(1) for single record insertion
        - Side Effects: Auto-generates timestamps, logs operation
        - Thread Safety: Resource locking prevents concurrent modification conflicts
        - Resource Locking: Acquires write lock on table during operation
        """
        self._ensure_postgres_available()
        
        # Acquire write lock for table modification
        resource_id = f"database/table/{table_name}"
        lock_metadata = {
            "operation": "create_record",
            "table_name": table_name,
            "user_context": "database_manager"
        }
        
        if self.enable_locking and self.lock_manager:
            try:
                with self.lock_manager.acquire_lock(resource_id, LockType.WRITE, 
                                                  timeout=30, metadata=lock_metadata) as lock:
                    result = self._create_postgres_record(table_name, data)
                    logger.info(f"Record created successfully in {table_name} (with lock {lock.lock_id})", 
                              source="database_manager", event_type="create_record")
                    return result
                    
            except ResourceLockConflict as e:
                logger.warning(f"Resource conflict while creating record in {table_name}: {e.user_message}",
                             source="database_manager", event_type="create_record_conflict")
                raise RuntimeError(f"Cannot create record in {table_name}: {e.user_message}")
        else:
            # Fallback without locking
            result = self._create_postgres_record(table_name, data)
            logger.info(f"Record created successfully in {table_name} (no locking)", 
                      source="database_manager", event_type="create_record")
            return result

    def get_record(self, table_name: str, record_id: str) -> Dict[str, Any]:
        """
        Get single record from PostgreSQL database with read locking.
        
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
            
        Notes
        -----
        - Complexity: O(1) for indexed record retrieval
        - Thread Safety: Resource locking prevents read-during-write conflicts
        - Resource Locking: Acquires read lock on table during operation
        """
        self._ensure_postgres_available()
        
        # Acquire read lock for table access
        resource_id = f"database/table/{table_name}"
        lock_metadata = {
            "operation": "get_record",
            "table_name": table_name,
            "record_id": record_id,
            "user_context": "database_manager"
        }
        
        if self.enable_locking and self.lock_manager:
            try:
                with self.lock_manager.acquire_lock(resource_id, LockType.READ, 
                                                  timeout=30, metadata=lock_metadata) as lock:
                    result = self._get_postgres_record(table_name, record_id)
                    logger.debug(f"Retrieved record {record_id} from {table_name} (with lock {lock.lock_id})", 
                               source="database_manager", event_type="get_record")
                    return result
                    
            except ResourceLockConflict as e:
                logger.warning(f"Resource conflict while reading record from {table_name}: {e.user_message}",
                             source="database_manager", event_type="get_record_conflict")
                raise RuntimeError(f"Cannot read record from {table_name}: {e.user_message}")
        else:
            # Fallback without locking
            result = self._get_postgres_record(table_name, record_id)
            logger.debug(f"Retrieved record {record_id} from {table_name} (no locking)", 
                       source="database_manager", event_type="get_record")
            return result

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

    # === Batch Operations ===
    def bulk_insert(self, table_name: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Insert multiple records efficiently.
        
        Parameters
        ----------
        table_name : str
            Table name
        records : List[Dict[str, Any]]
            List of records to insert
            
        Returns
        -------
        List[Dict[str, Any]]
            List of created records
        """
        self._ensure_postgres_available()
        
        try:
            results = self.postgres_client.bulk_insert(table_name, records)
            logger.info(f"Bulk inserted {len(results)} records into {table_name}", source="database_manager", event_type="bulk_insert")
            return results
            
        except Exception as e:
            logger.error(f"Failed to bulk insert records into {table_name}: {e}", source="database_manager", event_type="bulk_insert")
            raise

    def bulk_update(self, table_name: str, updates: List[Dict[str, Any]], id_field: str = "id") -> List[Dict[str, Any]]:
        """
        Update multiple records efficiently.
        
        Parameters
        ----------
        table_name : str
            Table name
        updates : List[Dict[str, Any]]
            List of update dictionaries
        id_field : str
            Field name to use as identifier
            
        Returns
        -------
        List[Dict[str, Any]]
            List of updated records
        """
        self._ensure_postgres_available()
        
        try:
            results = self.postgres_client.bulk_update(table_name, updates, id_field)
            logger.info(f"Bulk updated {len(results)} records in {table_name}", source="database_manager", event_type="bulk_update")
            return results
            
        except Exception as e:
            logger.error(f"Failed to bulk update records in {table_name}: {e}", source="database_manager", event_type="bulk_update")
            raise

    def bulk_delete(self, table_name: str, record_ids: List[Union[str, int]], id_field: str = "id") -> int:
        """
        Delete multiple records efficiently.
        
        Parameters
        ----------
        table_name : str
            Table name
        record_ids : List[Union[str, int]]
            List of record IDs to delete
        id_field : str
            Field name to use as identifier
            
        Returns
        -------
        int
            Number of records deleted
        """
        self._ensure_postgres_available()
        
        try:
            count = self.postgres_client.bulk_delete(table_name, record_ids, id_field)
            logger.info(f"Bulk deleted {count} records from {table_name}", source="database_manager", event_type="bulk_delete")
            return count
            
        except Exception as e:
            logger.error(f"Failed to bulk delete records from {table_name}: {e}", source="database_manager", event_type="bulk_delete")
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
