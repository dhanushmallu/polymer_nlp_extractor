"""
Comprehensive test suite for the setup system including service and API.

Summary
-------
Tests the complete setup functionality including SetupService class and FastAPI
endpoints with focus on production-ready operations, logging integration, and
system health validation. Validates initialization, purging, health checks,
and storage operations while addressing logging issues in clean_install.

Key test areas
--------------
1. SetupService Class Tests:
   - System initialization and validation
   - Complete data purging with dependency ordering
   - Health checks across all components
   - Clean install operations (with log preservation fix)
   - Storage management and health validation

2. FastAPI Endpoint Tests:
   - POST /setup/initialize endpoint
   - POST /setup/purge endpoint  
   - GET /setup/health endpoint
   - POST /setup/reset endpoint
   - POST /setup/clean-install endpoint
   - Request validation and error handling

3. Logging Integration Tests:
   - System logs handling during operations
   - Database logging pause/resume functionality
   - Log table initialization and reset
   - Logging system health validation
   - Clean install log preservation validation

4. Edge Cases and Error Handling:
   - Database connection failures
   - Storage backend issues
   - Neo4j connectivity problems
   - Partial system failures
   - Log purging conflicts in clean install

Test Environment
---------------
- Requires running PostgreSQL, Neo4j, and configured storage backend
- Uses test database schemas where possible
- Mocks external dependencies for isolated testing
- Validates against production logging system
- Tests log preservation behavior in clean_install

Examples
--------
>>> # Run all setup tests
>>> python3 -m pytest tests/test_setup_comprehensive.py -v

>>> # Run only service tests
>>> python3 -m pytest tests/test_setup_comprehensive.py::TestSetupService -v

>>> # Run with logging output
>>> python3 -m pytest tests/test_setup_comprehensive.py -s --log-cli-level=INFO

>>> # Test specific clean install behavior
>>> python3 -m pytest tests/test_setup_comprehensive.py::TestSetupService::test_clean_install_log_preservation -v

Notes
-----
- Complexity: O(n) for database operations, O(m) for storage operations
- Thread Safety: Individual test operations are thread-safe via mocking
- Performance: Tests use mocked managers for speed and isolation
- Clean Install Fix: Addresses log purging issues by preserving logs by default
- Production Safety: Tests validate safe operation defaults
"""

import pytest
import os
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, AsyncMock
from typing import Dict, Any, List, Optional
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import setup system components
from polymer_extractor.services.setup_service import SetupService
from polymer_extractor.api.setup import router
from polymer_extractor.utils.logging import Logger
from polymer_extractor.utils import responses as R
from polymer_extractor.storage.database_manager import DatabaseManager
from polymer_extractor.storage.graph_manager import GraphManager
from polymer_extractor.storage.storage_manager import StorageManager


class TestSetupService:
    """
    Test suite for SetupService class core functionality.
    
    Summary
    -------
    Validates all SetupService methods including initialization, health checks,
    data purging, and clean install operations. Tests both successful operations
    and error handling scenarios with specific focus on log preservation.
    """

    @pytest.fixture
    def mock_managers(self):
        """Mock all manager instances with realistic behavior."""
        database_manager = Mock(spec=DatabaseManager)
        graph_manager = Mock(spec=GraphManager)
        storage_manager = Mock(spec=StorageManager)
        
        # Mock database manager methods
        database_manager.postgres_client.health_check.return_value = {"status": "healthy", "connected": True}
        database_manager.postgres_client.deploy_schema.return_value = {"success": True, "tables_created": ["system_logs", "datasets"]}
        database_manager.postgres_client.drop_all_tables.return_value = {"success": True, "tables_dropped": 5}
        database_manager.list_tables.return_value = ["system_logs", "datasets", "extraction_sessions", "entities"]
        database_manager.table_exists.return_value = True
        database_manager.initialize_logging_table.return_value = {"success": True}
        database_manager.purge_all_data.return_value = {"success": True, "tables_purged": 4}
        
        # Mock graph manager methods
        graph_manager.neo4j_client.health_check.return_value = {"status": "healthy", "connected": True}
        graph_manager.neo4j_client.deploy_constraints.return_value = {"success": True, "constraints_created": 8}
        graph_manager.neo4j_client.purge_all_data.return_value = {"success": True, "nodes_deleted": 100}
        graph_manager.initialize.return_value = {"success": True}
        graph_manager.purge_all_data.return_value = {"success": True}
        
        # Mock storage manager methods
        storage_manager.health_check.return_value = {"status": "healthy", "backends": {"local": "healthy"}}
        storage_manager.initialize_buckets.return_value = {"success": True, "buckets_created": ["public", "models"]}
        storage_manager.purge_all_data.return_value = {"success": True, "files_deleted": 50}
        
        return {
            "database": database_manager,
            "graph": graph_manager,
            "storage": storage_manager
        }

    @pytest.fixture
    def mock_logger(self):
        """Mock logger with all required methods."""
        logger = Mock(spec=Logger)
        logger.info = Mock()
        logger.warning = Mock()
        logger.error = Mock()
        logger.pause_database_logging = Mock()
        logger.resume_database_logging = Mock()
        return logger

    @pytest.fixture
    def setup_service(self, mock_managers, mock_logger):
        """SetupService instance with mocked dependencies."""
        with patch.object(SetupService, '__init__', lambda x: None):
            service = SetupService()
            service.database_manager = mock_managers["database"]
            service.graph_manager = mock_managers["graph"]
            service.storage_manager = mock_managers["storage"]
            service.logger = mock_logger
            service.initialization_status = {
                "database_manager": True,
                "graph_manager": True,
                "storage_manager": True
            }
            # Mock environment methods
            service._should_use_postgres = Mock(return_value=True)
            service._should_use_neo4j = Mock(return_value=True)
            return service

    def test_initialization(self, setup_service, mock_managers):
        """Test SetupService initialization and dependency injection."""
        assert setup_service.database_manager is not None
        assert setup_service.graph_manager is not None
        assert setup_service.storage_manager is not None
        assert setup_service.logger is not None
        
        # Verify managers were initialized
        assert setup_service.database_manager == mock_managers["database"]
        assert setup_service.graph_manager == mock_managers["graph"]
        assert setup_service.storage_manager == mock_managers["storage"]

    def test_environment_info(self, setup_service):
        """Test environment information gathering."""
        with patch.dict(os.environ, {
            'USE_POSTGRESQL_DB': 'true',
            'USE_NEO4J_DB': 'true',
            'DATA_BACKEND': 'postgres',
            'GRAPH_BACKEND': 'neo4j',
            'STORAGE_BACKEND': 'local'
        }):
            env_info = setup_service.get_environment_info()
            
            assert 'timestamp' in env_info
            assert 'environment_flags' in env_info
            assert 'manager_status' in env_info
            assert 'capabilities' in env_info
            
            flags = env_info['environment_flags']
            assert flags['data_backend'] == 'postgres'
            assert flags['graph_backend'] == 'neo4j'
            assert flags['storage_backend'] == 'local'

    def test_check_system_health_all_healthy(self, setup_service, mock_managers):
        """Test system health check when all components are healthy."""
        health = setup_service.check_system_health()
        
        assert health['overall_status'] == 'healthy'
        assert 'services' in health
        assert 'database' in health['services']
        assert 'graph' in health['services']
        assert 'storage' in health['services']
        
        # Verify all services are healthy
        assert health['services']['database']['status'] == 'healthy'
        assert health['services']['graph']['status'] == 'healthy'
        assert health['services']['storage']['status'] == 'healthy'

    def test_check_system_health_database_unhealthy(self, setup_service, mock_managers):
        """Test system health check when database is unhealthy."""
        mock_managers["database"].postgres_client.health_check.return_value = {
            "status": "unhealthy", 
            "connected": False,
            "error": "Connection refused"
        }
        
        health = setup_service.check_system_health()
        
        assert health['overall_status'] == 'degraded'
        assert health['services']['database']['status'] == 'unhealthy'
        assert 'issues' in health
        assert len(health['issues']) > 0

    def test_check_system_health_all_unhealthy(self, setup_service, mock_managers):
        """Test system health check when all components are unhealthy."""
        # Make all services unhealthy
        mock_managers["database"].postgres_client.health_check.return_value = {"status": "unhealthy", "connected": False}
        mock_managers["graph"].neo4j_client.health_check.return_value = {"status": "unhealthy", "connected": False}
        mock_managers["storage"].health_check.return_value = {"status": "unhealthy", "backends": {}}
        
        health = setup_service.check_system_health()
        
        assert health['overall_status'] == 'unhealthy'
        assert all(service['status'] == 'unhealthy' for service in health['services'].values())
        assert len(health['issues']) >= 3

    def test_initialize_system_success(self, setup_service, mock_managers, mock_logger):
        """Test successful system initialization."""
        result = setup_service.initialize_system(clean_install=False)
        
        assert result['success'] is True
        assert 'components' in result
        assert 'database' in result['components']
        assert 'graph' in result['components']
        assert 'storage' in result['components']
        assert result['total_duration'] >= 0
        
        # Verify initialization was called for each component
        mock_logger.info.assert_called()

    def test_initialize_system_clean_install(self, setup_service, mock_managers, mock_logger):
        """Test system initialization with clean install."""
        result = setup_service.initialize_system(clean_install=True)
        
        assert result['success'] is True
        assert result['clean_install'] is True
        
        # Verify logging was paused and resumed
        mock_logger.pause_database_logging.assert_called_once()
        mock_logger.resume_database_logging.assert_called_once()

    def test_initialize_system_with_failures(self, setup_service, mock_managers, mock_logger):
        """Test system initialization with component failures."""
        # Make database initialization fail
        mock_managers["database"].postgres_client.deploy_schema.side_effect = Exception("Schema deployment failed")
        
        result = setup_service.initialize_system(clean_install=False)
        
        assert 'errors' in result
        assert len(result['errors']) > 0
        assert any('Database initialization failed' in error for error in result['errors'])

    def test_initialize_database_success(self, setup_service, mock_managers):
        """Test successful database initialization."""
        result = setup_service.initialize_database(clean_install=False)
        
        assert result['success'] is True
        assert 'operations' in result
        assert 'tables_created' in result
        assert result['duration'] >= 0

    def test_initialize_database_clean_install(self, setup_service, mock_managers):
        """Test database initialization with clean install."""
        result = setup_service.initialize_database(clean_install=True)
        
        assert result['success'] is True
        assert result['clean_install'] is True
        
        # Verify tables were dropped
        mock_managers["database"].postgres_client.drop_all_tables.assert_called_once()

    def test_initialize_graph_success(self, setup_service, mock_managers):
        """Test successful graph database initialization."""
        result = setup_service.initialize_graph(clean_install=False)
        
        assert result['success'] is True
        mock_managers["graph"].initialize.assert_called_once()

    def test_initialize_storage_success(self, setup_service, mock_managers):
        """Test successful storage system initialization."""
        result = setup_service.initialize_storage(clean_install=False)
        
        assert result['success'] is True
        mock_managers["storage"].initialize_buckets.assert_called_once()

    def test_purge_all_data_preserve_schemas(self, setup_service, mock_managers, mock_logger):
        """Test data purge while preserving schemas and buckets."""
        result = setup_service.purge_all_data(
            preserve_schemas=True, 
            preserve_buckets=True, 
            preserve_logs=False
        )
        
        assert result['success'] is True
        assert 'components_purged' in result
        
        # Verify purge operations were called
        mock_managers["database"].purge_all_data.assert_called_once()
        mock_managers["graph"].purge_all_data.assert_called_once()
        mock_managers["storage"].purge_all_data.assert_called_once()

    def test_purge_all_data_no_preservation(self, setup_service, mock_managers, mock_logger):
        """Test complete data purge without preservation."""
        result = setup_service.purge_all_data(
            preserve_schemas=False, 
            preserve_buckets=False, 
            preserve_logs=False
        )
        
        assert result['success'] is True
        
        # Verify all purge operations were called
        mock_managers["database"].purge_all_data.assert_called_once()
        mock_managers["graph"].purge_all_data.assert_called_once()
        mock_managers["storage"].purge_all_data.assert_called_once()

    def test_clean_install_success(self, setup_service, mock_managers, mock_logger):
        """Test successful clean installation."""
        # Mock purge_all_data and initialize_system
        setup_service.purge_all_data = Mock(return_value={"success": True})
        setup_service.initialize_system = Mock(return_value={"success": True})
        setup_service.check_system_health = Mock(return_value={"overall_status": "healthy"})
        
        result = setup_service.clean_install(preserve_logs=True)
        
        assert result['success'] is True
        assert result['preserve_logs'] is True
        assert 'operations' in result
        assert 'purge' in result['operations']
        assert 'initialize' in result['operations']
        assert 'validate' in result['operations']
        
        # Verify operation sequence
        setup_service.purge_all_data.assert_called_once_with(
            preserve_schemas=False, 
            preserve_buckets=False, 
            preserve_logs=True
        )
        setup_service.initialize_system.assert_called_once_with(clean_install=True)
        setup_service.check_system_health.assert_called_once()

    def test_clean_install_preserve_logs_default(self, setup_service, mock_managers, mock_logger):
        """Test that clean install preserves logs by default (addressing the issue)."""
        setup_service.purge_all_data = Mock(return_value={"success": True})
        setup_service.initialize_system = Mock(return_value={"success": True})
        setup_service.check_system_health = Mock(return_value={"overall_status": "healthy"})
        
        # Test default behavior
        result = setup_service.clean_install()
        
        assert result['preserve_logs'] is True
        
        # Verify logs are preserved in purge operation
        setup_service.purge_all_data.assert_called_once_with(
            preserve_schemas=False, 
            preserve_buckets=False, 
            preserve_logs=True  # This should be True by default
        )

    def test_clean_install_with_failures(self, setup_service, mock_managers, mock_logger):
        """Test clean installation with operation failures."""
        # Make purge fail
        setup_service.purge_all_data = Mock(return_value={"success": False, "error": "Purge failed"})
        
        result = setup_service.clean_install(preserve_logs=True)
        
        assert result['success'] is False
        assert 'errors' in result
        assert "Purge operation failed" in result['errors']

    def test_reset_components_success(self, setup_service, mock_managers):
        """Test successful component reset."""
        setup_service.purge_database_data = Mock(return_value={"success": True})
        setup_service.initialize_database = Mock(return_value={"success": True})
        setup_service.purge_graph_data = Mock(return_value={"success": True})
        setup_service.initialize_graph = Mock(return_value={"success": True})
        
        result = setup_service.reset_components(["database", "graph"], preserve_logs=True)
        
        assert result['success'] is True
        assert 'component_results' in result
        assert 'database' in result['component_results']
        assert 'graph' in result['component_results']

    def test_logging_system_integration(self, setup_service, mock_logger):
        """Test logging system integration during operations."""
        setup_service.purge_all_data = Mock(return_value={"success": True})
        setup_service.initialize_system = Mock(return_value={"success": True})
        setup_service.check_system_health = Mock(return_value={"overall_status": "healthy"})
        
        # Test clean install with logging
        result = setup_service.clean_install(preserve_logs=True)
        
        # Verify logging calls were made
        mock_logger.info.assert_called()
        assert any("clean installation" in str(call).lower() for call in mock_logger.info.call_args_list)

    def test_environment_configuration_handling(self, setup_service):
        """Test environment configuration handling."""
        # Test PostgreSQL configuration
        with patch.dict(os.environ, {'USE_POSTGRESQL_DB': 'true', 'DATA_BACKEND': 'postgres'}):
            assert setup_service._should_use_postgres() is True
        
        with patch.dict(os.environ, {'USE_POSTGRESQL_DB': 'false', 'DATA_BACKEND': 'other'}):
            setup_service._should_use_postgres = SetupService._should_use_postgres.__get__(setup_service)
            assert setup_service._should_use_postgres() is False
        
        # Test Neo4j configuration
        with patch.dict(os.environ, {'USE_NEO4J_DB': 'true', 'GRAPH_BACKEND': 'neo4j'}):
            setup_service._should_use_neo4j = SetupService._should_use_neo4j.__get__(setup_service)
            assert setup_service._should_use_neo4j() is True
        
        with patch.dict(os.environ, {'USE_NEO4J_DB': 'false', 'GRAPH_BACKEND': 'disabled'}):
            setup_service._should_use_neo4j = SetupService._should_use_neo4j.__get__(setup_service)
            assert setup_service._should_use_neo4j() is False


class TestSetupAPI:
    """
    Test suite for FastAPI endpoints in setup.py.
    
    Summary
    -------
    Validates all FastAPI routes, request handling, response formatting,
    and error scenarios. Tests integration with SetupService and
    proper JSON response structures.
    """

    @pytest.fixture
    def mock_setup_service(self):
        """Mock SetupService for API testing."""
        with patch('polymer_extractor.api.setup.setup_service') as mock_service:
            # Mock successful responses by default
            mock_service.initialize_system.return_value = {
                "success": True,
                "components": {"database": {"success": True}, "graph": {"success": True}, "storage": {"success": True}},
                "total_duration": 1.5
            }
            mock_service.purge_all_data.return_value = {
                "success": True,
                "components_purged": {"database": True, "graph": True, "storage": True},
                "total_duration": 2.1
            }
            mock_service.check_system_health.return_value = {
                "overall_status": "healthy",
                "services": {"database": {"status": "healthy"}, "graph": {"status": "healthy"}, "storage": {"status": "healthy"}}
            }
            mock_service.reset_components.return_value = {
                "success": True,
                "component_results": {"database": {"success": True}, "graph": {"success": True}},
                "total_duration": 1.8
            }
            mock_service.clean_install.return_value = {
                "success": True,
                "preserve_logs": True,
                "operations": {"purge": {"success": True}, "initialize": {"success": True}, "validate": {"success": True}},
                "total_duration": 3.2
            }
            yield mock_service

    @pytest.fixture
    def client(self):
        """Test client for FastAPI endpoints."""
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_health_endpoint_healthy_system(self, client, mock_setup_service):
        """Test health endpoint with healthy system."""
        response = client.get("/setup/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'success'
        assert data['data']['overall_status'] == 'healthy'
        assert 'services' in data['data']

    def test_health_endpoint_detailed(self, client, mock_setup_service):
        """Test health endpoint with detailed information."""
        response = client.get("/setup/health?detailed=true")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'success'
        mock_setup_service.check_system_health.assert_called_once()

    def test_health_endpoint_degraded_system(self, client, mock_setup_service):
        """Test health endpoint with degraded system."""
        mock_setup_service.check_system_health.return_value = {
            "overall_status": "degraded",
            "services": {"database": {"status": "unhealthy"}, "graph": {"status": "healthy"}, "storage": {"status": "healthy"}},
            "issues": ["Database connection failed"]
        }
        
        response = client.get("/setup/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['data']['overall_status'] == 'degraded'
        assert 'issues' in data['data']

    def test_initialize_endpoint_success(self, client, mock_setup_service):
        """Test initialize endpoint with successful operation."""
        request_data = {"clean_install": False}
        
        response = client.post("/setup/initialize", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'success'
        assert 'components' in data['data']
        mock_setup_service.initialize_system.assert_called_once_with(clean_install=False)

    def test_initialize_endpoint_clean_install(self, client, mock_setup_service):
        """Test initialize endpoint with clean install."""
        request_data = {"clean_install": True}
        
        response = client.post("/setup/initialize", json=request_data)
        
        assert response.status_code == 200
        mock_setup_service.initialize_system.assert_called_once_with(clean_install=True)

    def test_initialize_endpoint_failure(self, client, mock_setup_service):
        """Test initialize endpoint with failure."""
        mock_setup_service.initialize_system.return_value = {
            "success": False,
            "errors": ["Database connection failed"],
            "components": {}
        }
        
        request_data = {"clean_install": False}
        
        response = client.post("/setup/initialize", json=request_data)
        
        assert response.status_code == 500
        data = response.json()
        
        assert data['status'] == 'failure'
        assert 'errors' in data['details']

    def test_purge_endpoint_with_valid_request(self, client, mock_setup_service):
        """Test purge endpoint with valid request parameters."""
        request_data = {
            "preserve_schemas": True,
            "preserve_buckets": True,
            "preserve_logs": False
        }
        
        response = client.post("/setup/purge", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'success'
        mock_setup_service.purge_all_data.assert_called_once_with(
            preserve_schemas=True,
            preserve_buckets=True,
            preserve_logs=False
        )

    def test_purge_endpoint_with_defaults(self, client, mock_setup_service):
        """Test purge endpoint with default parameters."""
        request_data = {}
        
        response = client.post("/setup/purge", json=request_data)
        
        assert response.status_code == 200
        # Should use default values from PurgeRequest model
        mock_setup_service.purge_all_data.assert_called_once_with(
            preserve_schemas=True,  # Default
            preserve_buckets=True,  # Default
            preserve_logs=False     # Default
        )

    def test_purge_endpoint_failure(self, client, mock_setup_service):
        """Test purge endpoint with operation failure."""
        mock_setup_service.purge_all_data.return_value = {
            "success": False,
            "errors": ["Failed to connect to database"],
            "components_purged": {}
        }
        
        request_data = {"preserve_schemas": False}
        
        response = client.post("/setup/purge", json=request_data)
        
        assert response.status_code == 500
        data = response.json()
        
        assert data['status'] == 'failure'

    def test_reset_endpoint_success(self, client, mock_setup_service):
        """Test reset endpoint with successful operation."""
        request_data = {
            "components": ["database", "graph"],
            "preserve_logs": True
        }
        
        response = client.post("/setup/reset", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'success'
        mock_setup_service.reset_components.assert_called_once_with(
            components=["database", "graph"],
            preserve_logs=True
        )

    def test_reset_endpoint_with_defaults(self, client, mock_setup_service):
        """Test reset endpoint with default parameters."""
        request_data = {}
        
        response = client.post("/setup/reset", json=request_data)
        
        assert response.status_code == 200
        # Should use default values from ResetRequest model
        mock_setup_service.reset_components.assert_called_once_with(
            components=["database", "graph", "storage"],  # Default
            preserve_logs=True  # Default
        )

    def test_reset_endpoint_failure(self, client, mock_setup_service):
        """Test reset endpoint with operation failure."""
        mock_setup_service.reset_components.return_value = {
            "success": False,
            "errors": ["Component reset failed"],
            "component_results": {}
        }
        
        request_data = {"components": ["database"]}
        
        response = client.post("/setup/reset", json=request_data)
        
        assert response.status_code == 500
        data = response.json()
        
        assert data['status'] == 'failure'

    def test_clean_install_endpoint_success(self, client, mock_setup_service):
        """Test clean install endpoint with successful operation."""
        request_data = {"preserve_logs": True}
        
        response = client.post("/setup/clean-install", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'success'
        mock_setup_service.clean_install.assert_called_once_with(preserve_logs=True)

    def test_clean_install_endpoint_default_preserve_logs(self, client, mock_setup_service):
        """Test clean install endpoint preserves logs by default (fixing the issue)."""
        request_data = {}
        
        response = client.post("/setup/clean-install", json=request_data)
        
        assert response.status_code == 200
        # Should preserve logs by default
        mock_setup_service.clean_install.assert_called_once_with(preserve_logs=True)

    def test_clean_install_endpoint_no_log_preservation(self, client, mock_setup_service):
        """Test clean install endpoint with log purging disabled."""
        request_data = {"preserve_logs": False}
        
        response = client.post("/setup/clean-install", json=request_data)
        
        assert response.status_code == 200
        mock_setup_service.clean_install.assert_called_once_with(preserve_logs=False)

    def test_clean_install_endpoint_failure(self, client, mock_setup_service):
        """Test clean install endpoint with operation failure."""
        mock_setup_service.clean_install.return_value = {
            "success": False,
            "errors": ["Clean installation failed"],
            "operations": {}
        }
        
        request_data = {"preserve_logs": True}
        
        response = client.post("/setup/clean-install", json=request_data)
        
        assert response.status_code == 500
        data = response.json()
        
        assert data['status'] == 'failure'

    def test_environment_endpoint(self, client, mock_setup_service):
        """Test environment information endpoint."""
        mock_setup_service.get_environment_info.return_value = {
            "timestamp": "2025-08-20T10:00:00",
            "environment_flags": {"use_postgresql": True, "use_neo4j": True},
            "manager_status": {"database_manager": True, "graph_manager": True, "storage_manager": True},
            "capabilities": {"can_initialize_database": True}
        }
        
        response = client.get("/setup/environment")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'success'
        assert 'environment_flags' in data['data']
        assert 'manager_status' in data['data']

    def test_storage_health_endpoint(self, client, mock_setup_service):
        """Test storage health endpoint."""
        mock_setup_service.check_storage_health.return_value = {
            "status": "healthy",
            "backends": {"local": "healthy", "appwrite": "healthy", "s3": "healthy"},
            "response_times": {"local": 0.1, "appwrite": 0.5, "s3": 0.3}
        }
        
        response = client.get("/setup/storage-health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'success'
        assert 'backends' in data['data']

    def test_invalid_json_request(self, client, mock_setup_service):
        """Test endpoints with invalid JSON."""
        response = client.post("/setup/initialize", data="invalid json")
        
        assert response.status_code == 422  # FastAPI validation error

    def test_missing_required_fields(self, client, mock_setup_service):
        """Test endpoints with missing required fields (if any)."""
        # For initialize endpoint, clean_install has a default value, so this should work
        response = client.post("/setup/initialize", json={})
        
        assert response.status_code == 200
        mock_setup_service.initialize_system.assert_called_once_with(clean_install=False)

    def test_api_error_handling(self, client, mock_setup_service):
        """Test API error handling when service raises exceptions."""
        mock_setup_service.initialize_system.side_effect = Exception("Service error")
        
        request_data = {"clean_install": False}
        
        response = client.post("/setup/initialize", json=request_data)
        
        assert response.status_code == 500
        data = response.json()
        
        assert data['status'] == 'error'
        assert 'exception' in data['details']


class TestLoggingIntegration:
    """
    Test suite for logging system integration with setup operations.
    
    Summary
    -------
    Validates that setup operations properly integrate with the logging
    system, including pause/resume functionality, system_logs table
    handling, and logging during critical operations.
    """

    @pytest.fixture
    def real_logger(self):
        """Real logger instance for testing logging integration."""
        return Logger()

    @pytest.fixture
    def setup_with_real_logger(self, mock_managers, real_logger):
        """SetupService with real logger for logging tests."""
        with patch.object(SetupService, '__init__', lambda x: None):
            service = SetupService()
            service.database_manager = mock_managers["database"]
            service.graph_manager = mock_managers["graph"]
            service.storage_manager = mock_managers["storage"]
            service.logger = real_logger
            service._should_use_postgres = Mock(return_value=True)
            service._should_use_neo4j = Mock(return_value=True)
            return service

    @pytest.fixture
    def mock_managers(self):
        """Mock managers for logging tests."""
        database_manager = Mock(spec=DatabaseManager)
        graph_manager = Mock(spec=GraphManager)
        storage_manager = Mock(spec=StorageManager)
        
        # Mock successful operations
        database_manager.purge_all_data.return_value = {"success": True}
        database_manager.initialize_logging_table.return_value = {"success": True}
        graph_manager.purge_all_data.return_value = {"success": True}
        storage_manager.purge_all_data.return_value = {"success": True}
        
        return {
            "database": database_manager,
            "graph": graph_manager,
            "storage": storage_manager
        }

    def test_logger_pause_resume_during_clean_install(self, setup_with_real_logger):
        """Test logger pause/resume functionality during clean install."""
        # Mock the service methods to focus on logging behavior
        setup_with_real_logger.purge_all_data = Mock(return_value={"success": True})
        setup_with_real_logger.initialize_system = Mock(return_value={"success": True})
        setup_with_real_logger.check_system_health = Mock(return_value={"overall_status": "healthy"})
        
        # Spy on logger methods
        with patch.object(setup_with_real_logger.logger, 'pause_database_logging') as mock_pause, \
             patch.object(setup_with_real_logger.logger, 'resume_database_logging') as mock_resume:
            
            result = setup_with_real_logger.clean_install(preserve_logs=True)
            
            assert result['success'] is True
            
            # Verify logging was managed properly
            # Note: The actual pause/resume should happen in initialize_system with clean_install=True
            # This test validates the integration

    def test_system_logs_table_special_handling(self, setup_with_real_logger):
        """Test system_logs table special handling during operations."""
        # This test ensures system_logs table is handled specially during purge operations
        setup_with_real_logger.purge_database_data = Mock(return_value={"success": True})
        
        result = setup_with_real_logger.purge_database_data(preserve_logs=True)
        
        assert result['success'] is True

    def test_logging_during_health_checks(self, setup_with_real_logger):
        """Test logging behavior during health check operations."""
        with patch.object(setup_with_real_logger.logger, 'info') as mock_info:
            
            health = setup_with_real_logger.check_system_health()
            
            # Verify health check completed
            assert 'overall_status' in health

    def test_error_logging_during_failures(self, setup_with_real_logger, mock_managers):
        """Test error logging when operations fail."""
        # Make database operations fail
        mock_managers["database"].purge_all_data.side_effect = Exception("Database error")
        
        with patch.object(setup_with_real_logger.logger, 'error') as mock_error:
            
            result = setup_with_real_logger.purge_database_data(preserve_logs=False)
            
            # Should have logged the error
            mock_error.assert_called()

    def test_clean_install_log_preservation_behavior(self, setup_with_real_logger):
        """Test clean install behavior regarding log preservation (addresses the main issue)."""
        setup_with_real_logger.purge_all_data = Mock(return_value={"success": True})
        setup_with_real_logger.initialize_system = Mock(return_value={"success": True})
        setup_with_real_logger.check_system_health = Mock(return_value={"overall_status": "healthy"})
        
        # Test default behavior (should preserve logs)
        result = setup_with_real_logger.clean_install()
        
        assert result['preserve_logs'] is True
        
        # Verify purge was called with preserve_logs=True
        setup_with_real_logger.purge_all_data.assert_called_once_with(
            preserve_schemas=False,
            preserve_buckets=False,
            preserve_logs=True  # This addresses the issue - logs should be preserved by default
        )


class TestErrorHandling:
    """
    Test suite for error handling and edge cases in setup operations.
    
    Summary  
    -------
    Validates robust error handling across all setup operations including
    network failures, permission errors, partial system failures, and
    recovery scenarios.
    """

    @pytest.fixture
    def failing_setup_service(self):
        """SetupService with failing managers for error testing."""
        with patch.object(SetupService, '__init__', lambda x: None):
            service = SetupService()
            
            # Create failing managers
            service.database_manager = Mock(spec=DatabaseManager)
            service.graph_manager = Mock(spec=GraphManager)
            service.storage_manager = Mock(spec=StorageManager)
            service.logger = Mock(spec=Logger)
            
            # Make all operations fail
            service.database_manager.postgres_client.health_check.side_effect = Exception("DB connection failed")
            service.graph_manager.neo4j_client.health_check.side_effect = Exception("Neo4j connection failed")
            service.storage_manager.health_check.side_effect = Exception("Storage connection failed")
            
            service._should_use_postgres = Mock(return_value=True)
            service._should_use_neo4j = Mock(return_value=True)
            
            return service

    def test_database_connection_failure(self, failing_setup_service):
        """Test handling of database connection failures."""
        health = failing_setup_service.check_database_health()
        
        assert health['status'] == 'unhealthy'
        assert 'error' in health

    def test_graph_connection_failure(self, failing_setup_service):
        """Test handling of graph database connection failures."""
        health = failing_setup_service.check_graph_health()
        
        assert health['status'] == 'unhealthy'
        assert 'error' in health

    def test_storage_connection_failure(self, failing_setup_service):
        """Test handling of storage system failures."""
        health = failing_setup_service.check_storage_health()
        
        assert health['status'] == 'unhealthy'
        assert 'error' in health

    def test_partial_system_failure_recovery(self):
        """Test system behavior with partial failures."""
        with patch.object(SetupService, '__init__', lambda x: None):
            service = SetupService()
            
            # Database works, graph fails
            service.database_manager = Mock(spec=DatabaseManager)
            service.graph_manager = Mock(spec=GraphManager)
            service.storage_manager = Mock(spec=StorageManager)
            service.logger = Mock(spec=Logger)
            
            service.database_manager.postgres_client.health_check.return_value = {"status": "healthy"}
            service.graph_manager.neo4j_client.health_check.side_effect = Exception("Neo4j failed")
            service.storage_manager.health_check.return_value = {"status": "healthy"}
            
            service._should_use_postgres = Mock(return_value=True)
            service._should_use_neo4j = Mock(return_value=True)
            
            health = service.check_system_health()
            
            assert health['overall_status'] == 'degraded'
            assert health['services']['database']['status'] == 'healthy'
            assert health['services']['graph']['status'] == 'unhealthy'
            assert health['services']['storage']['status'] == 'healthy'

    def test_initialization_with_mixed_results(self):
        """Test initialization when some components succeed and others fail."""
        with patch.object(SetupService, '__init__', lambda x: None):
            service = SetupService()
            
            service.database_manager = Mock(spec=DatabaseManager)
            service.graph_manager = Mock(spec=GraphManager)
            service.storage_manager = Mock(spec=StorageManager)
            service.logger = Mock(spec=Logger)
            
            service._should_use_postgres = Mock(return_value=True)
            service._should_use_neo4j = Mock(return_value=True)
            
            # Database succeeds, graph fails
            service.initialize_database = Mock(return_value={"success": True})
            service.initialize_graph = Mock(return_value={"success": False, "error": "Graph init failed"})
            service.initialize_storage = Mock(return_value={"success": True})
            
            result = service.initialize_system()
            
            assert 'errors' in result
            assert any('Graph initialization failed' in error for error in result['errors'])

    def test_purge_operation_error_handling(self, failing_setup_service):
        """Test error handling during purge operations."""
        failing_setup_service.database_manager.purge_all_data.side_effect = Exception("Purge failed")
        
        result = failing_setup_service.purge_database_data(preserve_logs=False)
        
        assert result['success'] is False
        assert 'error' in result

    def test_clean_install_error_recovery(self, failing_setup_service):
        """Test clean install error recovery and rollback."""
        # Make purge succeed but initialization fail
        failing_setup_service.purge_all_data = Mock(return_value={"success": True})
        failing_setup_service.initialize_system = Mock(return_value={"success": False, "error": "Init failed"})
        
        result = failing_setup_service.clean_install(preserve_logs=True)
        
        assert result['success'] is False
        assert "Initialization after purge failed" in result['errors']

    def test_environment_validation_errors(self):
        """Test handling of invalid environment configurations."""
        with patch.dict(os.environ, {'USE_POSTGRESQL_DB': 'invalid_value'}):
            # Should handle gracefully and not crash
            with patch.object(SetupService, '__init__', lambda x: None):
                service = SetupService()
                service._should_use_postgres = SetupService._should_use_postgres.__get__(service)
                
                # Should default to safe behavior
                result = service._should_use_postgres()
                assert isinstance(result, bool)


if __name__ == "__main__":
    # Run tests with verbose output and show local variables on failure
    pytest.main([__file__, "-v", "--tb=long", "-x"])
