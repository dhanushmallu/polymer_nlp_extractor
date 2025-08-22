#!/usr/bin/env python3
"""
Comprehensive Database Layer Test Suite for Polymer NLP Extractor.

Purpose
-------
Comprehensive testing of PostgreSQL database operations to ensure reliability,
completeness, and correctness of the database layer components:
- PostgresClient: Low-level database connectivity and operations
- DatabaseManager: High-level CRUD operations with backward compatibility
- Schema deployment and table management
- Transaction handling and error scenarios
- Bulk operations and search functionality

Test Coverage
-------------
1. Connection and health checks
2. Schema deployment from SQL files
3. CRUD operations (Create, Read, Update, Delete)
4. Bulk operations (insert, update, delete)
5. Transaction management
6. Error handling and edge cases
7. Search and filtering capabilities
8. Backward compatibility layer
9. Performance and stress testing
10. Data integrity validation

Environment Setup
-----------------
Tests assume:
- PostgreSQL server is running and accessible
- Environment variables are configured (.env loaded)
- Database exists and user has proper permissions
- No conflicting data in test tables

Examples
--------
>>> # Run all tests
>>> python3 -m pytest tests/test_database.py -v

>>> # Run specific test class
>>> python3 -m pytest tests/test_database.py::TestPostgresClient -v

>>> # Run with coverage
>>> python3 -m pytest tests/test_database.py --cov=polymer_extractor.storage

Notes
-----
- Tests create and clean up their own test tables
- Uses transaction rollback where possible to avoid data pollution
- Includes stress tests for concurrent operations
- Tests both success and failure scenarios
- Validates data integrity and consistency
"""

import os
import pytest
import uuid
import time
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
from datetime import datetime

# Import test subjects
from polymer_extractor.storage.postgresql_client import PostgresClient, Row, Rows
from polymer_extractor.storage.database_manager import DatabaseManager


class TestSetup:
    """Setup and teardown utilities for database tests."""
    
    @staticmethod
    def get_test_table_name(prefix: str = "test") -> str:
        """Generate unique test table name."""
        return f"{prefix}_{uuid.uuid4().hex[:8]}"
    
    @staticmethod
    def create_test_table_sql(table_name: str, with_indexes: bool = True) -> str:
        """Generate CREATE TABLE SQL for testing."""
        base_sql = f"""
        CREATE TABLE {table_name} (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            value_numeric DECIMAL(10,2),
            value_int INTEGER,
            is_active BOOLEAN DEFAULT true,
            tags TEXT[],
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        if with_indexes:
            base_sql += f"""
            ;
            CREATE INDEX idx_{table_name}_title ON {table_name}(title);
            CREATE INDEX idx_{table_name}_active ON {table_name}(is_active);
            CREATE INDEX idx_{table_name}_created ON {table_name}(created_at);
            CREATE INDEX idx_{table_name}_metadata_gin ON {table_name} USING GIN(metadata);
            """
        
        return base_sql
    
    @staticmethod
    def sample_test_data() -> List[Dict[str, Any]]:
        """Generate sample test data."""
        return [
            {
                "title": "Test Record 1",
                "description": "First test record for validation",
                "value_numeric": 123.45,
                "value_int": 100,
                "is_active": True,
                "tags": ["test", "validation", "first"],
                "metadata": {"category": "test", "priority": 1}
            },
            {
                "title": "Test Record 2", 
                "description": "Second test record with different values",
                "value_numeric": 678.90,
                "value_int": 200,
                "is_active": False,
                "tags": ["test", "validation", "second"],
                "metadata": {"category": "test", "priority": 2}
            },
            {
                "title": "Search Test Record",
                "description": "Record specifically for search testing with keywords",
                "value_numeric": 999.99,
                "value_int": 300,
                "is_active": True,
                "tags": ["search", "keywords", "testing"],
                "metadata": {"category": "search", "priority": 3, "keywords": ["polymer", "material"]}
            }
        ]


class TestPostgresClient:
    """Test PostgresClient core functionality."""
    
    def setup_method(self):
        """Setup for each test method."""
        self.client = PostgresClient()
        self.test_table = TestSetup.get_test_table_name("postgres_client")
        
    def teardown_method(self):
        """Cleanup after each test method."""
        try:
            self.client.run(f"DROP TABLE IF EXISTS {self.test_table} CASCADE")
        except:
            pass
        self.client.close()
    
    def test_initialization_and_connection(self):
        """Test PostgresClient initialization and basic connection."""
        # Test initialization
        assert self.client is not None
        assert self.client.dsn is not None
        assert self.client.pool is not None
        assert self.client.min_conn >= 1
        assert self.client.max_conn >= self.client.min_conn
        
        # Test basic connection
        health = self.client.health_check()
        assert health["ok"] is True
        assert "server_version" in health["details"]
        assert "pool" in health["details"]
    
    def test_database_existence_check(self):
        """Test database existence validation."""
        db_check = self.client.check_database_exists()
        
        assert db_check["exists"] is True
        assert db_check["accessible"] is True
        assert db_check["database_name"] is not None
        assert db_check["error"] is None
        assert "timestamp" in db_check
    
    def test_basic_query_execution(self):
        """Test basic SQL query execution."""
        # Test simple SELECT
        result = self.client.run("SELECT 1 as test_value", fetch="one")
        assert result is not None
        assert result["test_value"] == 1
        
        # Test SELECT with parameters
        result = self.client.run("SELECT %s as param_value", ["test_param"], fetch="one")
        assert result["param_value"] == "test_param"
        
        # Test SELECT returning multiple rows
        results = self.client.run("SELECT generate_series(1, 3) as num", fetch="all")
        assert len(results) == 3
        assert results[0]["num"] == 1
        assert results[2]["num"] == 3
    
    def test_table_creation_and_management(self):
        """Test table creation and basic schema operations."""
        # Create test table
        create_sql = TestSetup.create_test_table_sql(self.test_table)
        self.client.run(create_sql)
        
        # Verify table exists
        tables = self.client.list_tables()
        assert self.test_table in tables
        
        # Test table structure
        result = self.client.run(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = %s 
            ORDER BY ordinal_position
        """, [self.test_table], fetch="all")
        
        assert len(result) >= 9  # Should have at least 9 columns
        column_names = [row["column_name"] for row in result]
        expected_columns = ["id", "title", "description", "value_numeric", "is_active"]
        for col in expected_columns:
            assert col in column_names
    
    def test_crud_operations(self):
        """Test Create, Read, Update, Delete operations."""
        # Setup test table
        create_sql = TestSetup.create_test_table_sql(self.test_table, with_indexes=False)
        self.client.run(create_sql)
        
        test_data = TestSetup.sample_test_data()[0]
        
        # Test CREATE
        created = self.client.create_record(self.test_table, test_data)
        assert created is not None
        assert "id" in created
        assert created["title"] == test_data["title"]
        record_id = created["id"]
        
        # Test READ
        retrieved = self.client.get_record(self.test_table, record_id)
        assert retrieved is not None
        assert retrieved["id"] == record_id
        assert retrieved["title"] == test_data["title"]
        assert float(retrieved["value_numeric"]) == test_data["value_numeric"]  # Handle Decimal conversion
        
        # Test UPDATE
        update_data = {"title": "Updated Title", "value_int": 999}
        updated = self.client.update_record(self.test_table, record_id, update_data)
        assert updated is not None
        assert updated["title"] == "Updated Title"
        assert updated["value_int"] == 999
        assert updated["description"] == test_data["description"]  # Unchanged
        
        # Test DELETE
        self.client.delete_record(self.test_table, record_id)
        deleted = self.client.get_record(self.test_table, record_id)
        assert deleted is None
    
    def test_list_and_filtering(self):
        """Test record listing with various filters."""
        # Setup test table and data
        create_sql = TestSetup.create_test_table_sql(self.test_table, with_indexes=False)
        self.client.run(create_sql)
        
        test_records = TestSetup.sample_test_data()
        for record in test_records:
            self.client.create_record(self.test_table, record)
        
        # Test list all
        all_records = self.client.list_records(self.test_table)
        assert len(all_records) == 3
        
        # Test filter by boolean
        active_records = self.client.list_records(self.test_table, filters={"is_active": True})
        assert len(active_records) == 2
        
        # Test filter by string
        first_record = self.client.list_records(self.test_table, filters={"title": "Test Record 1"})
        assert len(first_record) == 1
        assert first_record[0]["title"] == "Test Record 1"
        
        # Test limit
        limited = self.client.list_records(self.test_table, limit=2)
        assert len(limited) == 2
        
        # Test ordering
        ordered = self.client.list_records(self.test_table, order_by="value_int DESC")
        assert len(ordered) == 3
        assert ordered[0]["value_int"] == 300  # Highest value first
    
    def test_bulk_operations(self):
        """Test bulk insert, update, and delete operations."""
        # Setup test table
        create_sql = TestSetup.create_test_table_sql(self.test_table, with_indexes=False)
        self.client.run(create_sql)
        
        test_records = TestSetup.sample_test_data()
        
        # Test bulk insert
        inserted = self.client.bulk_insert(self.test_table, test_records)
        assert len(inserted) == 3
        assert all("id" in record for record in inserted)
        record_ids = [record["id"] for record in inserted]
        
        # Test bulk update
        updates = [
            {"id": record_ids[0], "title": "Bulk Updated 1"},
            {"id": record_ids[1], "title": "Bulk Updated 2"}
        ]
        updated = self.client.bulk_update(self.test_table, updates)
        assert len(updated) == 2
        assert updated[0]["title"] == "Bulk Updated 1"
        
        # Test bulk delete
        deleted_count = self.client.bulk_delete(self.test_table, record_ids[:2])
        assert deleted_count == 2
        
        # Verify only one record remains
        remaining = self.client.list_records(self.test_table)
        assert len(remaining) == 1
    
    def test_transaction_management(self):
        """Test transaction context manager."""
        # Setup test table
        create_sql = TestSetup.create_test_table_sql(self.test_table, with_indexes=False)
        self.client.run(create_sql)
        
        test_data = TestSetup.sample_test_data()[0]
        
        # Test successful transaction
        with self.client.transaction() as cur:
            cur.execute(f"""
                INSERT INTO {self.test_table} (title, description, value_int) 
                VALUES (%s, %s, %s) RETURNING id
            """, (test_data["title"], test_data["description"], test_data["value_int"]))
            result = cur.fetchone()
            record_id = result["id"]
            
            cur.execute(f"UPDATE {self.test_table} SET title = %s WHERE id = %s", 
                       ("Transaction Updated", record_id))
        
        # Verify transaction was committed
        record = self.client.get_record(self.test_table, record_id)
        assert record["title"] == "Transaction Updated"
        
        # Test transaction rollback on error
        try:
            with self.client.transaction() as cur:
                cur.execute(f"""
                    INSERT INTO {self.test_table} (title, description) 
                    VALUES (%s, %s) RETURNING id
                """, ("Rollback Test", "This should be rolled back"))
                
                # Force an error
                cur.execute("SELECT 1/0")  # Division by zero error
        except:
            pass  # Expected to fail
        
        # Verify rollback - should still be only 1 record
        all_records = self.client.list_records(self.test_table)
        assert len(all_records) == 1
    
    def test_search_functionality(self):
        """Test full-text and fuzzy search capabilities."""
        # Setup test table
        create_sql = TestSetup.create_test_table_sql(self.test_table, with_indexes=True)
        self.client.run(create_sql)
        
        # Insert test data
        test_records = TestSetup.sample_test_data()
        for record in test_records:
            self.client.create_record(self.test_table, record)
        
        # Test search in specific fields
        search_results = self.client.search_records(self.test_table, "Search", ["title", "description"])
        assert len(search_results) >= 1
        
        # Test search with keyword
        keyword_results = self.client.search_records(self.test_table, "validation", ["description"])
        assert len(keyword_results) >= 1  # Only one record has "validation" in description
        
        # Test fuzzy search
        fuzzy_results = self.client.search_records(self.test_table, "Serch", ["title"])  # Misspelled
        # Should still find results due to similarity
    
    def test_pagination(self):
        """Test pagination functionality."""
        # Setup test table with more data
        create_sql = TestSetup.create_test_table_sql(self.test_table, with_indexes=False)
        self.client.run(create_sql)
        
        # Insert 10 test records
        for i in range(10):
            self.client.create_record(self.test_table, {
                "title": f"Pagination Test {i}",
                "description": f"Test record {i} for pagination",
                "value_int": i
            })
        
        # Test pagination with run method
        page_0 = self.client.run(f"SELECT * FROM {self.test_table} ORDER BY id", 
                                fetch="all", page=0, page_size=3)
        assert len(page_0) == 3
        
        page_1 = self.client.run(f"SELECT * FROM {self.test_table} ORDER BY id", 
                                fetch="all", page=1, page_size=3)
        assert len(page_1) == 3
        
        # Verify different records
        assert page_0[0]["id"] != page_1[0]["id"]
    
    def test_count_functionality(self):
        """Test record counting with filters."""
        # Setup test table and data
        create_sql = TestSetup.create_test_table_sql(self.test_table, with_indexes=False)
        self.client.run(create_sql)
        
        test_records = TestSetup.sample_test_data()
        for record in test_records:
            self.client.create_record(self.test_table, record)
        
        # Test total count
        total_count = self.client.count_records(self.test_table)
        assert total_count == 3
        
        # Test filtered count
        active_count = self.client.count_records(self.test_table, filters={"is_active": True})
        assert active_count == 2
        
        inactive_count = self.client.count_records(self.test_table, filters={"is_active": False})
        assert inactive_count == 1
    
    def test_error_handling(self):
        """Test error handling for various failure scenarios."""
        # Test non-existent table
        with pytest.raises(Exception):
            self.client.get_record("non_existent_table", "1")
        
        # Test invalid SQL
        with pytest.raises(Exception):
            self.client.run("INVALID SQL STATEMENT")
        
        # Test invalid parameters
        with pytest.raises(Exception):
            self.client.run("SELECT * FROM %s", ["'; DROP TABLE users; --"])
        
        # Test empty data for create
        create_sql = TestSetup.create_test_table_sql(self.test_table, with_indexes=False)
        self.client.run(create_sql)
        
        with pytest.raises(ValueError):
            self.client.create_record(self.test_table, {})
        
        # Test update non-existent record
        with pytest.raises(ValueError):
            self.client.update_record(self.test_table, 999999, {"title": "Non-existent"})
    
    def test_schema_management(self):
        """Test schema deployment and management operations."""
        # Create temporary schema file
        schema_content = TestSetup.create_test_table_sql(self.test_table, with_indexes=True)
        schema_file = Path(f"/tmp/test_schema_{uuid.uuid4().hex[:8]}.sql")
        schema_file.write_text(schema_content)
        
        try:
            # Test schema deployment
            result = self.client.deploy_schema(str(schema_file))
            assert result["success"] is True
            
            # Verify table was created
            tables = self.client.list_tables()
            assert self.test_table in tables
            
        finally:
            schema_file.unlink(missing_ok=True)
        
        # Test table creation with if not exists
        another_table = TestSetup.get_test_table_name("schema_test")
        table_sql = f"CREATE TABLE {another_table} (id SERIAL PRIMARY KEY, name TEXT)"
        
        created_first = self.client.create_table_if_not_exists(another_table, table_sql)
        assert created_first is True
        
        created_second = self.client.create_table_if_not_exists(another_table, table_sql)
        assert created_second is False  # Already exists
        
        # Cleanup
        self.client.run(f"DROP TABLE IF EXISTS {another_table}")


class TestDatabaseManager:
    """Test DatabaseManager high-level functionality and compatibility."""
    
    def setup_method(self):
        """Setup for each test method."""
        self.db_manager = DatabaseManager()
        self.test_table = TestSetup.get_test_table_name("db_manager")
        
        # Create test table
        if self.db_manager.postgres_client:
            create_sql = TestSetup.create_test_table_sql(self.test_table, with_indexes=False)
            self.db_manager.postgres_client.run(create_sql)
    
    def teardown_method(self):
        """Cleanup after each test method."""
        if self.db_manager.postgres_client:
            try:
                self.db_manager.postgres_client.run(f"DROP TABLE IF EXISTS {self.test_table} CASCADE")
            except:
                pass
    
    def test_initialization(self):
        """Test DatabaseManager initialization."""
        assert self.db_manager is not None
        
        # Should have PostgreSQL client when enabled
        if os.getenv("USE_POSTGRESQL_DB", "true").lower() == "true":
            assert self.db_manager.postgres_client is not None
    
    def test_universal_crud_operations(self):
        """Test universal CRUD methods."""
        if not self.db_manager.postgres_client:
            pytest.skip("PostgreSQL not available")
        
        test_data = TestSetup.sample_test_data()[0]
        
        # Test create_record
        created = self.db_manager.create_record(self.test_table, test_data)
        assert created is not None
        assert "id" in created
        record_id = str(created["id"])
        
        # Test get_record
        retrieved = self.db_manager.get_record(self.test_table, record_id)
        assert retrieved is not None
        assert retrieved["title"] == test_data["title"]
        
        # Test list_records
        all_records = self.db_manager.list_records(self.test_table)
        assert len(all_records) >= 1
        
        # Test update_record
        update_data = {"title": "Updated via DatabaseManager"}
        updated = self.db_manager.update_record(self.test_table, record_id, update_data)
        assert updated["title"] == "Updated via DatabaseManager"
        
        # Test delete_record
        self.db_manager.delete_record(self.test_table, record_id)
        deleted = self.db_manager.get_record(self.test_table, record_id)
        assert deleted is None
    
    def test_bulk_operations_through_manager(self):
        """Test bulk operations through DatabaseManager."""
        if not self.db_manager.postgres_client:
            pytest.skip("PostgreSQL not available")
        
        test_records = TestSetup.sample_test_data()
        
        # Test bulk_insert
        inserted = self.db_manager.bulk_insert(self.test_table, test_records)
        assert len(inserted) == 3
        record_ids = [str(record["id"]) for record in inserted]
        
        # Test bulk_update
        updates = [
            {"id": record_ids[0], "title": "Bulk Updated 1"},
            {"id": record_ids[1], "title": "Bulk Updated 2"}
        ]
        updated = self.db_manager.bulk_update(self.test_table, updates)
        assert len(updated) == 2
        
        # Test bulk_delete
        deleted_count = self.db_manager.bulk_delete(self.test_table, record_ids[:2])
        assert deleted_count == 2
    
    def test_search_and_count(self):
        """Test search and count operations through DatabaseManager."""
        if not self.db_manager.postgres_client:
            pytest.skip("PostgreSQL not available")
        
        # Insert test data
        test_records = TestSetup.sample_test_data()
        for record in test_records:
            self.db_manager.create_record(self.test_table, record)
        
        # Test search_records
        search_results = self.db_manager.search_records(self.test_table, "validation", ["description"])
        assert len(search_results) >= 1
        
        # Test count_records
        total_count = self.db_manager.count_records(self.test_table)
        assert total_count == 3
        
        active_count = self.db_manager.count_records(self.test_table, filters={"is_active": True})
        assert active_count == 2
    
    def test_backward_compatibility_layer(self):
        """Test backward compatibility with Appwrite-style methods."""
        if not self.db_manager.postgres_client:
            pytest.skip("PostgreSQL not available")
        
        test_data = TestSetup.sample_test_data()[0]
        
        # Test create_document (should map to create_record)
        created = self.db_manager.create_document(self.test_table, test_data)
        assert created is not None
        document_id = str(created["id"])
        
        # Test get_document (should map to get_record)
        retrieved = self.db_manager.get_document(self.test_table, document_id)
        assert retrieved is not None
        assert retrieved["title"] == test_data["title"]
        
        # Test list_documents (should map to list_records)
        all_documents = self.db_manager.list_documents(self.test_table)
        assert len(all_documents) >= 1
        
        # Test update_document (should map to update_record)
        update_data = {"title": "Updated via compatibility layer"}
        updated = self.db_manager.update_document(self.test_table, document_id, update_data)
        assert updated["title"] == "Updated via compatibility layer"
        
        # Test delete_document (should map to delete_record)
        self.db_manager.delete_document(self.test_table, document_id)
        deleted = self.db_manager.get_document(self.test_table, document_id)
        assert deleted is None
    
    def test_table_management(self):
        """Test table/collection management operations."""
        if not self.db_manager.postgres_client:
            pytest.skip("PostgreSQL not available")
        
        # Test list_tables
        tables = self.db_manager.list_tables()
        assert isinstance(tables, list)
        assert self.test_table in tables
        
        # Test table_exists
        assert self.db_manager.table_exists(self.test_table) is True
        assert self.db_manager.table_exists("non_existent_table") is False
        
        # Test create_table with schema
        new_table = TestSetup.get_test_table_name("schema_test")
        schema = {
            "columns": {
                "name": {"type": "VARCHAR(255)", "nullable": False},
                "email": {"type": "VARCHAR(255)"},
                "age": {"type": "INTEGER", "default": "0"}
            },
            "primary_key": "id",
            "indexes": {
                "idx_name": {"columns": ["name"], "type": "btree"}
            }
        }
        
        result = self.db_manager.create_table(new_table, schema)
        assert result["status"] == "created"
        assert self.db_manager.table_exists(new_table) is True
        
        # Test drop_table
        self.db_manager.drop_table(new_table)
        assert self.db_manager.table_exists(new_table) is False
    
    def test_error_handling_and_edge_cases(self):
        """Test error handling for edge cases."""
        if not self.db_manager.postgres_client:
            pytest.skip("PostgreSQL not available")
        
        # Test operations on non-existent table
        with pytest.raises(Exception):
            self.db_manager.get_record("non_existent_table", "1")
        
        # Test invalid record ID
        with pytest.raises(Exception):
            self.db_manager.get_record(self.test_table, "invalid_id")
        
        # Test empty data
        with pytest.raises(ValueError):
            self.db_manager.create_record(self.test_table, {})
    
    def test_upsert_functionality(self):
        """Test upsert (insert or update) operations."""
        if not self.db_manager.postgres_client:
            pytest.skip("PostgreSQL not available")
        
        test_data = {
            "title": "Upsert Test",
            "description": "Testing upsert functionality",
            "value_int": 100
        }
        
        # First upsert should insert
        result1 = self.db_manager.upsert_record(self.test_table, test_data, "title")
        assert result1 is not None
        record_id = result1["id"]
        
        # Second upsert with same title should update
        test_data["description"] = "Updated description"
        test_data["value_int"] = 200
        
        result2 = self.db_manager.upsert_record(self.test_table, test_data, "title")
        assert result2["id"] == record_id  # Same record
        assert result2["description"] == "Updated description"
        assert result2["value_int"] == 200


class TestSchemaDeployment:
    """Test schema deployment and database initialization."""
    
    def setup_method(self):
        """Setup for schema tests."""
        self.client = PostgresClient()
        
    def teardown_method(self):
        """Cleanup after schema tests."""
        self.client.close()
    
    def test_core_schema_deployment(self):
        """Test deployment of the core database schema."""
        # Use the single corrected schema file
        schema_file = Path(__file__).parent.parent / "db" / "sql" / "001_core.sql"
        
        if schema_file.exists():
            # Use the corrected schema file
            result = self.client.deploy_schema(str(schema_file))
            assert result["success"] is True
            
            # Verify key tables were created
            tables = self.client.list_tables()
            expected_tables = [
                'research_papers', 'entities', 'extraction_sessions', 'datasets',
                'model_configurations', 'sentences', 'system_logs'
            ]
            
            for table in expected_tables:
                assert table in tables, f"Table {table} was not created"
                
        else:
            pytest.skip("Core schema file not found")
    
    def test_table_structure_validation(self):
        """Validate structure of core tables."""
        # Test entities table structure
        entities_columns = self.client.run("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'entities'
            ORDER BY ordinal_position
        """, fetch="all")
        
        if entities_columns:  # Only test if table exists
            column_names = [col["column_name"] for col in entities_columns]
            expected_columns = ["id", "session_id", "sentence_id", "entity_type", "text_content"]
            
            for col in expected_columns:
                assert col in column_names, f"Expected column '{col}' not found in entities table"


class TestPerformanceAndStress:
    """Performance and stress testing for database operations."""
    
    def setup_method(self):
        """Setup for performance tests."""
        self.client = PostgresClient()
        self.test_table = TestSetup.get_test_table_name("perf_test")
        
        # Create test table optimized for performance testing
        create_sql = f"""
        CREATE TABLE {self.test_table} (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255),
            description TEXT,
            value_int INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX idx_{self.test_table}_title ON {self.test_table}(title);
        CREATE INDEX idx_{self.test_table}_value ON {self.test_table}(value_int);
        """
        self.client.run(create_sql)
    
    def teardown_method(self):
        """Cleanup after performance tests."""
        try:
            self.client.run(f"DROP TABLE IF EXISTS {self.test_table} CASCADE")
        except:
            pass
        self.client.close()
    
    def test_bulk_insert_performance(self):
        """Test bulk insert performance with large datasets."""
        # Generate 1000 test records
        large_dataset = []
        for i in range(1000):
            large_dataset.append({
                "title": f"Performance Test Record {i}",
                "description": f"Large dataset test record number {i}",
                "value_int": i
            })
        
        # Time the bulk insert
        start_time = time.time()
        inserted = self.client.bulk_insert(self.test_table, large_dataset)
        end_time = time.time()
        
        # Verify results
        assert len(inserted) == 1000
        insert_time = end_time - start_time
        
        # Should complete within reasonable time (adjust threshold as needed)
        assert insert_time < 30.0, f"Bulk insert took {insert_time:.2f}s, expected < 30s"
        
        # Verify data integrity
        count = self.client.count_records(self.test_table)
        assert count == 1000
    
    def test_concurrent_operations(self):
        """Test concurrent database operations."""
        def concurrent_insert(thread_id: int, results: list):
            """Insert records concurrently."""
            try:
                local_client = PostgresClient()
                for i in range(10):
                    data = {
                        "title": f"Concurrent Test {thread_id}-{i}",
                        "description": f"Thread {thread_id} record {i}",
                        "value_int": thread_id * 10 + i
                    }
                    result = local_client.create_record(self.test_table, data)
                    results.append(result)
                local_client.close()
            except Exception as e:
                results.append({"error": str(e)})
        
        # Run 5 concurrent threads
        threads = []
        results = []
        
        for i in range(5):
            thread = threading.Thread(target=concurrent_insert, args=(i, results))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        successful_inserts = [r for r in results if "error" not in r]
        assert len(successful_inserts) == 50  # 5 threads * 10 inserts each
        
        # Verify database consistency
        total_count = self.client.count_records(self.test_table)
        assert total_count == 50
    
    def test_large_query_performance(self):
        """Test performance of queries on large datasets."""
        # Insert test data
        test_records = []
        for i in range(500):
            test_records.append({
                "title": f"Query Test {i}",
                "description": f"Performance query test record {i}",
                "value_int": i % 100  # Create some repeated values
            })
        
        self.client.bulk_insert(self.test_table, test_records)
        
        # Test filtered query performance
        start_time = time.time()
        filtered_results = self.client.list_records(
            self.test_table, 
            filters={"value_int": 50},
            limit=100
        )
        end_time = time.time()
        
        query_time = end_time - start_time
        assert query_time < 5.0, f"Filtered query took {query_time:.2f}s, expected < 5s"
        assert len(filtered_results) > 0


class TestDataIntegrity:
    """Test data integrity and consistency."""
    
    def setup_method(self):
        """Setup for integrity tests."""
        self.client = PostgresClient()
        self.test_table = TestSetup.get_test_table_name("integrity_test")
        
        # Create test table with constraints
        create_sql = f"""
        CREATE TABLE {self.test_table} (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE,
            age INTEGER CHECK (age >= 0 AND age <= 150),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.client.run(create_sql)
    
    def teardown_method(self):
        """Cleanup after integrity tests."""
        try:
            self.client.run(f"DROP TABLE IF EXISTS {self.test_table} CASCADE")
        except:
            pass
        self.client.close()
    
    def test_constraint_validation(self):
        """Test database constraints are enforced."""
        # Test NOT NULL constraint
        with pytest.raises(Exception):
            self.client.create_record(self.test_table, {"email": "test@example.com"})
        
        # Test valid record
        valid_record = {
            "title": "Valid Record",
            "email": "valid@example.com",
            "age": 25
        }
        created = self.client.create_record(self.test_table, valid_record)
        assert created is not None
        
        # Test UNIQUE constraint
        with pytest.raises(Exception):
            self.client.create_record(self.test_table, {
                "title": "Duplicate Email",
                "email": "valid@example.com",  # Same email
                "age": 30
            })
        
        # Test CHECK constraint
        with pytest.raises(Exception):
            self.client.create_record(self.test_table, {
                "title": "Invalid Age",
                "email": "invalid@example.com",
                "age": -5  # Invalid age
            })
    
    def test_transaction_atomicity(self):
        """Test transaction atomicity - all or nothing."""
        valid_data = {
            "title": "Transaction Test",
            "email": "transaction@example.com",
            "age": 30
        }
        
        # Test successful transaction
        with self.client.transaction() as cur:
            cur.execute(f"""
                INSERT INTO {self.test_table} (title, email, age) 
                VALUES (%s, %s, %s) RETURNING id
            """, (valid_data["title"], valid_data["email"], valid_data["age"]))
            
            result = cur.fetchone()
            record_id = result["id"]
            
            cur.execute(f"UPDATE {self.test_table} SET age = %s WHERE id = %s", (31, record_id))
        
        # Verify transaction was committed
        record = self.client.get_record(self.test_table, record_id)
        assert record["age"] == 31
        
        # Test failed transaction (should rollback)
        try:
            with self.client.transaction() as cur:
                cur.execute(f"""
                    INSERT INTO {self.test_table} (title, email, age) 
                    VALUES (%s, %s, %s)
                """, ("Rollback Test", "rollback@example.com", 25))
                
                # This should fail due to constraint violation
                cur.execute(f"""
                    INSERT INTO {self.test_table} (title, email, age) 
                    VALUES (%s, %s, %s)
                """, ("Constraint Violation", "transaction@example.com", 25))  # Duplicate email
        except:
            pass  # Expected to fail
        
        # Verify rollback - should still be only 1 record
        count = self.client.count_records(self.test_table)
        assert count == 1


# Run the tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
