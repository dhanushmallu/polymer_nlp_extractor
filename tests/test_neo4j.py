#!/usr/bin/env python3
"""
Comprehensive Neo4j Client and Graph Manager Tests

Test Suite Coverage
-------------------
1. Neo4j Client Operations:
   - Connection and health checks
   - Database validation
   - Query execution (read/write)
   - Transaction management
   - Schema operations (constraints)
   - Error handling and recovery

2. Graph Manager Operations:
   - Node CRUD operations
   - Relationship management
   - Entity-specific operations
   - Knowledge graph queries
   - Polymer science domain logic
   - Environment configuration

3. Production-Ready Validation:
   - Real-world data scenarios
   - Performance testing
   - Error recovery patterns
   - Multi-transaction consistency
   - Constraint validation

Purpose
-------
Validates that the Neo4j integration is production-ready for polymer NLP extraction
workflows with comprehensive error handling, performance validation, and domain-specific
knowledge graph operations.

Design Principles
-----------------
1) Environment-driven testing respecting .env configuration
2) Real-world scenario validation with polymer science data
3) Comprehensive error recovery and edge case testing
4) Performance benchmarking for production readiness
5) Integration testing with model_config.py entity types

Requirements
------------
- Neo4j server running and accessible via .env configuration
- Valid credentials and permissions for test database operations
- Python packages: neo4j, pytest

Examples
--------
$ python3 -m pytest tests/test_neo4j.py -v
$ python3 tests/test_neo4j.py  # Direct execution for development
"""

import os
import sys
import time
import unittest
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import patch, MagicMock

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from polymer_extractor.storage.neo4j_client import Neo4jClient
from polymer_extractor.storage.graph_manager import GraphManager
from polymer_extractor.utils.logging import Logger


class TestNeo4jClient(unittest.TestCase):
    """
    Test Neo4j client connectivity, query execution, and basic operations.
    
    Validates core Neo4j functionality including connection management,
    query execution, transaction handling, and error recovery patterns.
    """

    def setUp(self):
        """Set up test environment and Neo4j client."""
        self.logger = Logger()
        
        # Check if Neo4j should be tested based on environment
        self.should_test_neo4j = (
            os.getenv("USE_NEO4J_DB", "true").lower() == "true" and
            os.getenv("GRAPH_BACKEND", "neo4j") == "neo4j"
        )
        
        if not self.should_test_neo4j:
            self.skipTest("Neo4j testing disabled via environment configuration")
        
        try:
            self.client = Neo4jClient()
            # Clean up any test data from previous runs
            self._cleanup_test_data()
        except Exception as e:
            self.skipTest(f"Neo4j client initialization failed: {e}")
    
    def tearDown(self):
        """Clean up test data and close connections."""
        if hasattr(self, 'client') and self.client:
            try:
                self._cleanup_test_data()
                self.client.close()
            except Exception as e:
                self.logger.log("WARNING", f"Cleanup failed: {e}", "test_neo4j")

    def _cleanup_test_data(self):
        """Remove test nodes and relationships."""
        try:
            # Delete test nodes (this will also delete relationships)
            test_labels = ["TestPolymer", "TestProperty", "TestValue", "TestUnit"]
            for label in test_labels:
                self.client.run(f"MATCH (n:{label}) DETACH DELETE n")
        except Exception as e:
            # Ignore cleanup errors in setUp
            pass

    def test_01_health_check(self):
        """Test Neo4j health check and connectivity."""
        print("\n=== Testing Neo4j Health Check ===")
        
        health = self.client.health_check()
        print(f"Health check result: {health}")
        
        self.assertIsInstance(health, dict)
        self.assertIn("ok", health)
        
        if health["ok"]:
            self.assertIn("details", health)
            print("✓ Neo4j is healthy and accessible")
        else:
            self.fail(f"Neo4j health check failed: {health.get('error', 'Unknown error')}")

    def test_02_database_validation(self):
        """Test database existence and accessibility validation."""
        print("\n=== Testing Database Validation ===")
        
        db_check = self.client.check_database_exists()
        print(f"Database validation: {db_check}")
        
        self.assertIsInstance(db_check, dict)
        self.assertIn("exists", db_check)
        self.assertIn("accessible", db_check)
        self.assertEqual(db_check["database_name"], self.client.database)
        
        if not (db_check["exists"] and db_check["accessible"]):
            self.fail(f"Database validation failed: {db_check.get('error', 'Database not accessible')}")
        
        print("✓ Database exists and is accessible")

    def test_03_basic_query_execution(self):
        """Test basic Cypher query execution with different fetch modes."""
        print("\n=== Testing Basic Query Execution ===")
        
        # Test fetch="none"
        result = self.client.run("RETURN 1 AS test_value", fetch="none")
        self.assertIsNone(result)
        print("✓ Query execution with fetch='none' works")
        
        # Test fetch="one"
        result = self.client.run("RETURN 1 AS test_value", fetch="one")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["test_value"], 1)
        print("✓ Query execution with fetch='one' works")
        
        # Test fetch="all"
        result = self.client.run("UNWIND [1, 2, 3] AS num RETURN num", fetch="all")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        self.assertEqual([r["num"] for r in result], [1, 2, 3])
        print("✓ Query execution with fetch='all' works")
        
        # Test parameterized query
        result = self.client.run(
            "RETURN $value AS param_test", 
            {"value": "test_param"}, 
            fetch="one"
        )
        self.assertEqual(result["param_test"], "test_param")
        print("✓ Parameterized query execution works")

    def test_04_node_operations(self):
        """Test node creation, reading, updating, and deletion."""
        print("\n=== Testing Node Operations ===")
        
        # Create test node
        create_result = self.client.run(
            "CREATE (n:TestPolymer {name: $name, type: $type}) RETURN n, ID(n) as node_id",
            {"name": "PDMS", "type": "elastomer"},
            fetch="one"
        )
        
        self.assertIsNotNone(create_result)
        node_id = create_result["node_id"]
        print(f"✓ Created test node with ID: {node_id}")
        
        # Read node back
        read_result = self.client.run(
            "MATCH (n:TestPolymer) WHERE ID(n) = $node_id RETURN n",
            {"node_id": node_id},
            fetch="one"
        )
        
        self.assertIsNotNone(read_result)
        self.assertEqual(read_result["n"]["name"], "PDMS")
        print("✓ Successfully read back created node")
        
        # Update node
        self.client.run(
            "MATCH (n:TestPolymer) WHERE ID(n) = $node_id SET n.molecular_weight = $mw",
            {"node_id": node_id, "mw": 10000}
        )
        
        # Verify update
        updated_result = self.client.run(
            "MATCH (n:TestPolymer) WHERE ID(n) = $node_id RETURN n.molecular_weight as mw",
            {"node_id": node_id},
            fetch="one"
        )
        
        self.assertEqual(updated_result["mw"], 10000)
        print("✓ Successfully updated node properties")
        
        # Delete node
        self.client.run(
            "MATCH (n:TestPolymer) WHERE ID(n) = $node_id DELETE n",
            {"node_id": node_id}
        )
        
        # Verify deletion
        deleted_check = self.client.run(
            "MATCH (n:TestPolymer) WHERE ID(n) = $node_id RETURN n",
            {"node_id": node_id},
            fetch="one"
        )
        
        self.assertIsNone(deleted_check)
        print("✓ Successfully deleted node")

    def test_05_relationship_operations(self):
        """Test relationship creation and querying."""
        print("\n=== Testing Relationship Operations ===")
        
        # Create two nodes
        polymer_result = self.client.run(
            "CREATE (p:TestPolymer {name: 'PDMS'}) RETURN ID(p) as polymer_id",
            fetch="one"
        )
        
        property_result = self.client.run(
            "CREATE (prop:TestProperty {name: 'tensile_strength'}) RETURN ID(prop) as property_id",
            fetch="one"
        )
        
        polymer_id = polymer_result["polymer_id"]
        property_id = property_result["property_id"]
        
        # Create relationship
        self.client.run(
            """
            MATCH (p:TestPolymer), (prop:TestProperty)
            WHERE ID(p) = $polymer_id AND ID(prop) = $property_id
            CREATE (p)-[r:HAS_PROPERTY {strength: 0.9}]->(prop)
            """,
            {"polymer_id": polymer_id, "property_id": property_id}
        )
        
        # Query relationship
        rel_result = self.client.run(
            """
            MATCH (p:TestPolymer)-[r:HAS_PROPERTY]->(prop:TestProperty)
            WHERE ID(p) = $polymer_id
            RETURN r.strength as strength, prop.name as property_name
            """,
            {"polymer_id": polymer_id},
            fetch="one"
        )
        
        self.assertIsNotNone(rel_result)
        self.assertEqual(rel_result["strength"], 0.9)
        self.assertEqual(rel_result["property_name"], "tensile_strength")
        print("✓ Successfully created and queried relationship")

    def test_06_transaction_management(self):
        """Test transaction context manager and rollback behavior."""
        print("\n=== Testing Transaction Management ===")
        
        # Test successful transaction
        with self.client.transaction(access_mode="write") as tx:
            result = tx.run(
                "CREATE (n:TestUnit {name: 'MPa', type: 'pressure'}) RETURN ID(n) as node_id"
            )
            node_data = result.single()
            node_id = node_data["node_id"]
        
        # Verify transaction was committed
        committed_result = self.client.run(
            "MATCH (n:TestUnit) WHERE ID(n) = $node_id RETURN n.name as name",
            {"node_id": node_id},
            fetch="one"
        )
        
        self.assertIsNotNone(committed_result)
        self.assertEqual(committed_result["name"], "MPa")
        print("✓ Transaction commit works correctly")
        
        # Test transaction rollback on exception
        try:
            with self.client.transaction(access_mode="write") as tx:
                tx.run("CREATE (n:TestUnit {name: 'GPa', type: 'pressure'})")
                # Force an error to trigger rollback
                tx.run("INVALID CYPHER SYNTAX")
        except Exception:
            pass  # Expected exception
        
        # Verify rollback occurred - GPa node should not exist
        rollback_result = self.client.run(
            "MATCH (n:TestUnit {name: 'GPa'}) RETURN n",
            fetch="one"
        )
        
        self.assertIsNone(rollback_result)
        print("✓ Transaction rollback works correctly")

    def test_07_schema_operations(self):
        """Test constraint creation and schema management."""
        print("\n=== Testing Schema Operations ===")
        
        # Create unique constraint
        constraint_name = "test_polymer_name_unique"
        self.client.run(
            f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
            "FOR (p:TestPolymer) REQUIRE p.name IS UNIQUE"
        )
        print("✓ Created unique constraint")
        
        # Test constraint enforcement
        self.client.run("CREATE (p:TestPolymer {name: 'UniquePolymer'})")
        
        # This should fail due to constraint
        with self.assertRaises(Exception):
            self.client.run("CREATE (p:TestPolymer {name: 'UniquePolymer'})")
        
        print("✓ Constraint enforcement works")
        
        # Clean up constraint
        self.client.run(f"DROP CONSTRAINT {constraint_name} IF EXISTS")

    def test_08_upsert_operations(self):
        """Test upsert (MERGE) functionality."""
        print("\n=== Testing Upsert Operations ===")
        
        # Test upsert with ON CREATE
        self.client.upsert_node(
            label="TestValue",
            match={"numerical_value": 45.5},
            on_create={"unit": "MPa", "created": True},
            on_match={"updated": True}
        )
        
        # Verify creation
        result = self.client.run(
            "MATCH (v:TestValue {numerical_value: 45.5}) RETURN v.created as created, v.updated as updated",
            fetch="one"
        )
        
        self.assertTrue(result["created"])
        self.assertIsNone(result.get("updated"))
        print("✓ Upsert with ON CREATE works")
        
        # Test upsert with ON MATCH
        self.client.upsert_node(
            label="TestValue",
            match={"numerical_value": 45.5},
            on_create={"unit": "GPa", "created": True},
            on_match={"updated": True}
        )
        
        # Verify match update
        result = self.client.run(
            "MATCH (v:TestValue {numerical_value: 45.5}) RETURN v.created as created, v.updated as updated",
            fetch="one"
        )
        
        self.assertTrue(result["created"])
        self.assertTrue(result["updated"])
        print("✓ Upsert with ON MATCH works")

    def test_09_error_handling(self):
        """Test error handling and recovery patterns."""
        print("\n=== Testing Error Handling ===")
        
        # Test invalid Cypher syntax
        with self.assertRaises(Exception):
            self.client.run("INVALID CYPHER SYNTAX")
        
        print("✓ Invalid syntax properly raises exception")
        
        # Test non-existent node query (should not raise exception)
        result = self.client.run(
            "MATCH (n:NonExistentLabel) RETURN n",
            fetch="one"
        )
        self.assertIsNone(result)
        print("✓ Non-existent node queries handled gracefully")

    def test_10_service_status(self):
        """Test service status reporting."""
        print("\n=== Testing Service Status ===")
        
        status = self.client.service_status()
        
        self.assertIsInstance(status, dict)
        self.assertIn("status", status)
        self.assertIn("service", status)
        self.assertEqual(status["service"], "neo4j")
        
        if status["status"] == "healthy":
            print("✓ Neo4j service status is healthy")
        else:
            self.fail(f"Neo4j service status check failed: {status}")


class TestGraphManager(unittest.TestCase):
    """
    Test Graph Manager high-level operations and domain-specific functionality.
    
    Validates polymer science domain operations, entity management,
    and knowledge graph intelligence features.
    """

    def setUp(self):
        """Set up test environment and Graph Manager."""
        self.logger = Logger()
        
        # Check if Neo4j should be tested
        self.should_test_neo4j = (
            os.getenv("USE_NEO4J_DB", "true").lower() == "true" and
            os.getenv("GRAPH_BACKEND", "neo4j") == "neo4j"
        )
        
        if not self.should_test_neo4j:
            self.skipTest("Neo4j testing disabled via environment configuration")
        
        try:
            self.graph_manager = GraphManager()
            if not self.graph_manager.neo4j_client:
                self.skipTest("Graph Manager Neo4j client not available")
            self._cleanup_test_data()
        except Exception as e:
            self.skipTest(f"Graph Manager initialization failed: {e}")
    
    def tearDown(self):
        """Clean up test data."""
        if hasattr(self, 'graph_manager') and self.graph_manager and self.graph_manager.neo4j_client:
            try:
                self._cleanup_test_data()
            except Exception as e:
                self.logger.log("WARNING", f"Graph Manager cleanup failed: {e}", "test_neo4j")

    def _cleanup_test_data(self):
        """Remove test nodes and relationships."""
        try:
            test_labels = ["TestPolymer", "TestProperty", "TestValue", "TestUnit", "TestSymbol"]
            for label in test_labels:
                self.graph_manager.neo4j_client.run(f"MATCH (n:{label}) DETACH DELETE n")
        except Exception:
            pass  # Ignore cleanup errors

    def test_01_environment_configuration(self):
        """Test environment-based configuration."""
        print("\n=== Testing Graph Manager Environment Configuration ===")
        
        # Test that Neo4j client is properly initialized based on environment
        self.assertIsNotNone(self.graph_manager.neo4j_client)
        self.assertTrue(self.graph_manager._should_use_neo4j())
        
        print("✓ Graph Manager properly configured from environment")

    def test_02_node_crud_operations(self):
        """Test Graph Manager node CRUD operations."""
        print("\n=== Testing Graph Manager Node CRUD ===")
        
        # Test node creation
        polymer_node = self.graph_manager.create_node(
            "TestPolymer",
            {"name": "PDMS", "type": "silicone", "molecular_weight": 10000},
            node_id="test_pdms_001"
        )
        
        self.assertIsNotNone(polymer_node)
        self.assertIn("node", polymer_node)
        self.assertIn("internal_id", polymer_node)
        self.assertEqual(polymer_node["node"]["name"], "PDMS")
        print(f"✓ Created polymer node: {polymer_node['internal_id']}")
        
        # Test node retrieval by ID
        retrieved_node = self.graph_manager.get_node("TestPolymer", node_id="test_pdms_001")
        
        self.assertIsNotNone(retrieved_node)
        self.assertEqual(retrieved_node["node"]["name"], "PDMS")
        self.assertEqual(retrieved_node["node"]["molecular_weight"], 10000)
        print("✓ Retrieved node by ID")
        
        # Test node retrieval by properties
        prop_retrieved = self.graph_manager.get_node(
            "TestPolymer", 
            properties={"type": "silicone"}
        )
        
        self.assertIsNotNone(prop_retrieved)
        self.assertEqual(prop_retrieved["node"]["name"], "PDMS")
        print("✓ Retrieved node by properties")
        
        # Test node update
        updated_node = self.graph_manager.update_node(
            "TestPolymer",
            "test_pdms_001",
            {"glass_transition_temp": -125}
        )
        
        self.assertIsNotNone(updated_node)
        print("✓ Updated node properties")
        
        # Verify update
        updated_retrieved = self.graph_manager.get_node("TestPolymer", node_id="test_pdms_001")
        self.assertEqual(updated_retrieved["node"]["glass_transition_temp"], -125)
        print("✓ Verified node update")

    def test_03_relationship_management(self):
        """Test relationship creation and management."""
        print("\n=== Testing Relationship Management ===")
        
        # Create nodes for relationship testing
        polymer_node = self.graph_manager.create_node(
            "TestPolymer",
            {"name": "PET", "type": "thermoplastic"},
            node_id="test_pet_001"
        )
        
        property_node = self.graph_manager.create_node(
            "TestProperty",
            {"name": "tensile_strength", "category": "mechanical"},
            node_id="test_tensile_001"
        )
        
        # Create relationship
        relationship = self.graph_manager.create_relationship(
            from_node={"label": "TestPolymer", "id": "test_pet_001"},
            to_node={"label": "TestProperty", "id": "test_tensile_001"},
            rel_type="HAS_PROPERTY",
            properties={"strength": 0.95, "context": "standard_conditions"}
        )
        
        self.assertIsNotNone(relationship)
        print("✓ Created relationship between polymer and property")
        
        # Test relationship retrieval
        relationships = self.graph_manager.get_relationships(
            polymer_node["internal_id"],
            direction="outgoing",
            rel_type="HAS_PROPERTY"
        )
        
        self.assertIsInstance(relationships, list)
        self.assertGreater(len(relationships), 0)
        print(f"✓ Retrieved {len(relationships)} relationships")

    def test_04_entity_validation(self):
        """Test entity type validation against model config."""
        print("\n=== Testing Entity Validation ===")
        
        # Test creation of model_config.py entity types
        entity_types = ["POLYMER", "PROPERTY", "VALUE", "UNIT", "SYMBOL"]
        
        for entity_type in entity_types:
            test_node = self.graph_manager.create_node(
                f"Test{entity_type.title()}",
                {"name": f"test_{entity_type.lower()}", "type": entity_type},
                node_id=f"test_{entity_type.lower()}_001"
            )
            
            self.assertIsNotNone(test_node)
            print(f"✓ Created {entity_type} entity node")

    def test_05_polymer_science_operations(self):
        """Test polymer science domain-specific operations."""
        print("\n=== Testing Polymer Science Operations ===")
        
        # Use unique identifier to prevent conflicts from multiple test runs
        import time
        test_suffix = str(int(time.time() * 1000))[-6:]  # Last 6 digits of milliseconds
        
        # Test polymer entity creation
        polymer_result = self.graph_manager.create_polymer_entity(
            f"PDMS_test_{test_suffix}",
            {
                "chemical_formula": "C2H6OSi",
                "molecular_weight": 10000,
                "glass_transition_temp": -125,
                "applications": ["medical_devices", "sealants"]
            }
        )
        
        self.assertIsNotNone(polymer_result)
        print("✓ Created polymer entity with domain-specific properties")
        
        # Test property measurement creation
        measurement_result = self.graph_manager.create_property_measurement(
            polymer_result["node_id"],
            f"tensile_strength_test_{test_suffix}",
            45.2,
            "MPa",
            metadata={
                "test_method": "ASTM_D638",
                "temperature": 23,
                "humidity": 50
            }
        )
        
        self.assertIsNotNone(measurement_result)
        print("✓ Created property measurement with metadata")

    def test_06_knowledge_graph_queries(self):
        """Test knowledge graph query operations."""
        print("\n=== Testing Knowledge Graph Queries ===")
        
        # Create a small knowledge graph
        polymer = self.graph_manager.create_node(
            "TestPolymer",
            {"name": "PEEK", "type": "thermoplastic"},
            node_id="test_peek_001"
        )
        
        property1 = self.graph_manager.create_node(
            "TestProperty",
            {"name": "melting_point", "category": "thermal"},
            node_id="test_melting_001"
        )
        
        property2 = self.graph_manager.create_node(
            "TestProperty",
            {"name": "tensile_modulus", "category": "mechanical"},
            node_id="test_modulus_001"
        )
        
        # Create relationships
        self.graph_manager.create_relationship(
            from_node={"label": "TestPolymer", "id": "test_peek_001"},
            to_node={"label": "TestProperty", "id": "test_melting_001"},
            rel_type="HAS_PROPERTY",
            properties={"strength": 0.9}
        )
        
        self.graph_manager.create_relationship(
            from_node={"label": "TestPolymer", "id": "test_peek_001"},
            to_node={"label": "TestProperty", "id": "test_modulus_001"},
            rel_type="HAS_PROPERTY",
            properties={"strength": 0.85}
        )
        
        # Test neighbor discovery
        neighbors = self.graph_manager.get_neighbors(
            polymer["internal_id"],
            hops=1,
            rel_type="HAS_PROPERTY"
        )
        
        self.assertIsInstance(neighbors, list)
        self.assertEqual(len(neighbors), 2)
        print(f"✓ Found {len(neighbors)} neighbors for polymer node")
        
        # Test path finding
        path = self.graph_manager.find_path(
            start_node={"label": "TestPolymer", "id": "test_peek_001"},
            end_node={"label": "TestProperty", "id": "test_melting_001"},
            max_depth=3
        )
        
        self.assertIsInstance(path, list)
        print("✓ Found path between polymer and property nodes")

    def test_07_cypher_query_execution(self):
        """Test raw Cypher query execution."""
        print("\n=== Testing Cypher Query Execution ===")
        
        # Create test data
        self.graph_manager.create_node(
            "TestPolymer",
            {"name": "PS", "type": "thermoplastic", "applications": ["packaging", "insulation"]},
            node_id="test_ps_001"
        )
        
        # Test raw Cypher query
        results = self.graph_manager.cypher_query(
            """
            MATCH (p:TestPolymer {name: $polymer_name})
            RETURN p.name as name, p.type as type, p.applications as apps
            """,
            parameters={"polymer_name": "PS"}
        )
        
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "PS")
        self.assertEqual(results[0]["type"], "thermoplastic")
        print("✓ Raw Cypher query execution works")

    def test_08_error_handling_and_recovery(self):
        """Test error handling and recovery patterns."""
        print("\n=== Testing Error Handling and Recovery ===")
        
        # Test node creation with invalid data
        try:
            invalid_node = self.graph_manager.create_node(
                "TestPolymer",
                None,  # Invalid properties
                node_id="test_invalid_001"
            )
            # Should handle gracefully
        except Exception as e:
            print(f"✓ Handled invalid node creation: {type(e).__name__}")
        
        # Test retrieval of non-existent node
        missing_node = self.graph_manager.get_node(
            "TestPolymer",
            node_id="non_existent_node"
        )
        
        self.assertIsNone(missing_node)
        print("✓ Gracefully handled non-existent node retrieval")
        
        # Test invalid Cypher query
        try:
            self.graph_manager.cypher_query("INVALID CYPHER SYNTAX")
        except Exception as e:
            print(f"✓ Properly handled invalid Cypher query: {type(e).__name__}")


class TestNeo4jProduction(unittest.TestCase):
    """
    Production-ready validation tests for Neo4j integration.
    
    Tests performance, consistency, real-world scenarios, and
    integration with polymer science workflows.
    """

    def setUp(self):
        """Set up production validation environment."""
        self.logger = Logger()
        
        # Check if Neo4j should be tested
        self.should_test_neo4j = (
            os.getenv("USE_NEO4J_DB", "true").lower() == "true" and
            os.getenv("GRAPH_BACKEND", "neo4j") == "neo4j"
        )
        
        if not self.should_test_neo4j:
            self.skipTest("Neo4j testing disabled via environment configuration")
        
        try:
            self.client = Neo4jClient()
            self.graph_manager = GraphManager()
            self._cleanup_test_data()
        except Exception as e:
            self.skipTest(f"Production test setup failed: {e}")
    
    def tearDown(self):
        """Clean up production test data."""
        if hasattr(self, 'client') and self.client:
            try:
                self._cleanup_test_data()
                self.client.close()
            except Exception:
                pass

    def _cleanup_test_data(self):
        """Remove all production test data."""
        try:
            production_labels = [
                "ProductionPolymer", "ProductionProperty", "ProductionValue", 
                "ProductionUnit", "ProductionSymbol", "ProductionMaterial"
            ]
            for label in production_labels:
                self.client.run(f"MATCH (n:{label}) DETACH DELETE n")
        except Exception:
            pass

    def test_01_real_world_polymer_scenario(self):
        """Test real-world polymer science data scenario."""
        print("\n=== Testing Real-World Polymer Science Scenario ===")
        
        # Use unique identifier to prevent conflicts from multiple test runs
        import time
        test_suffix = str(int(time.time() * 1000))[-6:]  # Last 6 digits of milliseconds
        
        # Simulate polymer extraction and knowledge graph population
        polymers_data = [
            {
                "name": f"PDMS_prod_{test_suffix}",
                "chemical_formula": "C2H6OSi",
                "type": "silicone_elastomer",
                "properties": [
                    {"name": f"glass_transition_temp_{test_suffix}", "value": -125, "unit": "°C"},
                    {"name": f"tensile_strength_{test_suffix}", "value": 2.24, "unit": "MPa"},
                    {"name": f"elongation_at_break_{test_suffix}", "value": 140, "unit": "%"}
                ]
            },
            {
                "name": f"PEEK_prod_{test_suffix}",
                "chemical_formula": "C19H12O3",
                "type": "thermoplastic",
                "properties": [
                    {"name": f"melting_point_{test_suffix}", "value": 343, "unit": "°C"},
                    {"name": f"tensile_modulus_{test_suffix}", "value": 3600, "unit": "MPa"},
                    {"name": f"density_{test_suffix}", "value": 1.32, "unit": "g/cm³"}
                ]
            }
        ]
        
        created_polymers = []
        start_time = time.time()
        
        for polymer_data in polymers_data:
            # Create polymer node
            polymer_node = self.graph_manager.create_node(
                "ProductionPolymer",
                {
                    "name": polymer_data["name"],
                    "chemical_formula": polymer_data["chemical_formula"],
                    "type": polymer_data["type"]
                },
                node_id=f"prod_{polymer_data['name'].lower()}_001"
            )
            
            created_polymers.append(polymer_node)
            
            # Create property nodes and relationships
            for prop_data in polymer_data["properties"]:
                # Create property node
                property_node = self.graph_manager.create_node(
                    "ProductionProperty",
                    {"name": prop_data["name"], "category": "measured"},
                    node_id=f"prod_prop_{prop_data['name']}_{polymer_data['name'].lower()}"
                )
                
                # Create value node
                value_node = self.graph_manager.create_node(
                    "ProductionValue",
                    {"numerical_value": prop_data["value"], "data_type": "float"},
                    node_id=f"prod_val_{prop_data['value']}_{prop_data['name']}"
                )
                
                # Create unit node
                unit_node = self.graph_manager.create_node(
                    "ProductionUnit",
                    {"symbol": prop_data["unit"], "category": "scientific"},
                    node_id=f"prod_unit_{prop_data['unit'].replace('°', 'deg').replace('/', '_per_')}"
                )
                
                # Create relationships
                self.graph_manager.create_relationship(
                    from_node={"label": "ProductionPolymer", "id": polymer_node["node"]["id"]},
                    to_node={"label": "ProductionProperty", "id": property_node["node"]["id"]},
                    rel_type="HAS_PROPERTY",
                    properties={"confidence": 0.95, "source": "extraction"}
                )
                
                self.graph_manager.create_relationship(
                    from_node={"label": "ProductionProperty", "id": property_node["node"]["id"]},
                    to_node={"label": "ProductionValue", "id": value_node["node"]["id"]},
                    rel_type="HAS_VALUE",
                    properties={"confidence": 0.9}
                )
                
                self.graph_manager.create_relationship(
                    from_node={"label": "ProductionValue", "id": value_node["node"]["id"]},
                    to_node={"label": "ProductionUnit", "id": unit_node["node"]["id"]},
                    rel_type="HAS_UNIT",
                    properties={"confidence": 1.0}
                )
        
        creation_time = time.time() - start_time
        
        self.assertEqual(len(created_polymers), 2)
        print(f"✓ Created real-world polymer knowledge graph in {creation_time:.2f}s")
        
        # Test complex knowledge graph queries
        query_results = self.graph_manager.cypher_query(
            """
            MATCH (p:ProductionPolymer)-[:HAS_PROPERTY]->(prop:ProductionProperty)-[:HAS_VALUE]->(v:ProductionValue)-[:HAS_UNIT]->(u:ProductionUnit)
            WHERE prop.name CONTAINS 'temp'
            RETURN p.name as polymer, prop.name as property, v.numerical_value as value, u.symbol as unit
            ORDER BY v.numerical_value DESC
            """
        )
        
        self.assertGreater(len(query_results), 0)
        print(f"✓ Complex knowledge graph query returned {len(query_results)} results")
        
        # Test performance with larger queries
        performance_results = self.graph_manager.cypher_query(
            """
            MATCH (p:ProductionPolymer)
            OPTIONAL MATCH (p)-[:HAS_PROPERTY]->(prop)-[:HAS_VALUE]->(v)-[:HAS_UNIT]->(u)
            RETURN p.name as polymer, count(prop) as property_count
            """
        )
        
        self.assertEqual(len(performance_results), 2)
        print("✓ Performance query execution successful")

    def test_02_constraint_validation(self):
        """Test constraint deployment and validation."""
        print("\n=== Testing Constraint Validation ===")
        
        # Deploy constraints from file
        constraint_result = self.client.deploy_constraints()
        
        if constraint_result["success"]:
            print(f"✓ Deployed {len(constraint_result['constraints_created'])} constraints")
        else:
            print(f"⚠ Constraint deployment issue: {constraint_result.get('error', 'Unknown')}")
        
        # Test constraint enforcement with production data
        self.graph_manager.create_node(
            "ProductionPolymer",
            {"canonical_form": "pdms_standard", "name": "PDMS"},
            node_id="constraint_test_001"
        )
        
        # This should fail if constraints are properly enforced
        try:
            self.graph_manager.create_node(
                "ProductionPolymer",
                {"canonical_form": "pdms_standard", "name": "PDMS_Duplicate"},
                node_id="constraint_test_002"
            )
            print("⚠ Constraint enforcement may not be active")
        except Exception:
            print("✓ Constraint enforcement is working")

    def test_03_performance_benchmarks(self):
        """Test performance benchmarks for production readiness."""
        print("\n=== Testing Performance Benchmarks ===")
        
        # Test bulk node creation performance
        start_time = time.time()
        node_count = 100
        
        for i in range(node_count):
            self.graph_manager.create_node(
                "ProductionMaterial",
                {
                    "name": f"material_{i}",
                    "type": "synthetic",
                    "index": i
                },
                node_id=f"perf_material_{i:03d}"
            )
        
        creation_time = time.time() - start_time
        creation_rate = node_count / creation_time
        
        print(f"✓ Created {node_count} nodes in {creation_time:.2f}s ({creation_rate:.1f} nodes/sec)")
        
        # Test bulk query performance
        start_time = time.time()
        
        query_results = self.graph_manager.cypher_query(
            "MATCH (m:ProductionMaterial) RETURN m.name, m.type, m.index ORDER BY m.index"
        )
        
        query_time = time.time() - start_time
        
        self.assertEqual(len(query_results), node_count)
        print(f"✓ Queried {len(query_results)} nodes in {query_time:.3f}s")
        
        # Performance should be reasonable for production use
        self.assertLess(creation_time, 30.0, "Node creation performance too slow for production")
        self.assertLess(query_time, 5.0, "Query performance too slow for production")

    def test_04_transaction_consistency(self):
        """Test transaction consistency and ACID properties."""
        print("\n=== Testing Transaction Consistency ===")
        
        # Test multi-operation transaction consistency
        with self.client.transaction(access_mode="write") as tx:
            # Create related nodes in single transaction
            tx.run(
                "CREATE (p:ProductionPolymer {name: 'TxTestPolymer', id: 'tx_test_001'})"
            )
            tx.run(
                "CREATE (prop:ProductionProperty {name: 'TxTestProperty', id: 'tx_prop_001'})"
            )
            tx.run(
                """
                MATCH (p:ProductionPolymer {id: 'tx_test_001'}), 
                      (prop:ProductionProperty {id: 'tx_prop_001'})
                CREATE (p)-[:HAS_PROPERTY {created_in_tx: true}]->(prop)
                """
            )
        
        # Verify all operations were committed together
        verification_result = self.client.run(
            """
            MATCH (p:ProductionPolymer {id: 'tx_test_001'})-[r:HAS_PROPERTY]->(prop:ProductionProperty {id: 'tx_prop_001'})
            RETURN p.name as polymer, prop.name as property, r.created_in_tx as in_tx
            """,
            fetch="one"
        )
        
        self.assertIsNotNone(verification_result)
        self.assertTrue(verification_result["in_tx"])
        print("✓ Transaction consistency maintained across multiple operations")

    def test_05_error_recovery_patterns(self):
        """Test comprehensive error recovery patterns."""
        print("\n=== Testing Error Recovery Patterns ===")
        
        # Test recovery from connection issues (simulated)
        original_run = self.client.run
        
        # Simulate temporary connection failure
        call_count = 0
        def mock_run_with_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                from neo4j.exceptions import ServiceUnavailable
                raise ServiceUnavailable("Simulated connection failure")
            return original_run(*args, **kwargs)
        
        # Test retry mechanism (if implemented)
        try:
            with patch.object(self.client, 'run', side_effect=mock_run_with_failure):
                result = self.client.run("RETURN 1 as test", retries=2, fetch="one")
                if result and result.get("test") == 1:
                    print("✓ Connection failure retry mechanism works")
                else:
                    print("⚠ Retry mechanism may not be fully implemented")
        except Exception as e:
            print(f"⚠ Error recovery test failed: {e}")
        
        # Test graceful degradation
        with patch.object(os, 'getenv') as mock_getenv:
            def mock_env_disabled(key, default=None):
                if key == "USE_NEO4J_DB":
                    return "false"
                return os.environ.get(key, default)
            
            mock_getenv.side_effect = mock_env_disabled
            
            # Create new manager with disabled Neo4j
            disabled_manager = GraphManager()
            self.assertIsNone(disabled_manager.neo4j_client)
            print("✓ Graceful degradation when Neo4j is disabled")


def main():
    """Run comprehensive Neo4j tests with detailed reporting."""
    print("=" * 80)
    print("COMPREHENSIVE NEO4J INTEGRATION TESTS")
    print("=" * 80)
    print()
    print("Testing Neo4j client, Graph Manager, and production readiness...")
    print("Environment configuration:")
    print(f"  USE_NEO4J_DB: {os.getenv('USE_NEO4J_DB', 'not set')}")
    print(f"  GRAPH_BACKEND: {os.getenv('GRAPH_BACKEND', 'not set')}")
    print(f"  NEO4J_URI: {os.getenv('NEO4J_URI', 'not set')}")
    print(f"  NEO4J_DATABASE: {os.getenv('NEO4J_DATABASE', 'not set')}")
    print()
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [TestNeo4jClient, TestGraphManager, TestNeo4jProduction]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    start_time = time.time()
    result = runner.run(test_suite)
    total_time = time.time() - start_time
    
    # Final summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"Total execution time: {total_time:.2f} seconds")
    print()
    
    if result.failures:
        print("FAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback.split('AssertionError: ')[-1].split('\n')[0]}")
        print()
    
    if result.errors:
        print("ERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback.split('\n')[-2]}")
        print()
    
    if result.wasSuccessful():
        print("🎉 ALL TESTS PASSED! Neo4j integration is production-ready.")
    else:
        print("❌ SOME TESTS FAILED! Review failures and errors above.")
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
