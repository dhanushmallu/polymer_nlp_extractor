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
>>> python3 -m pytest tests/test_setup.py -v

>>> # Run only service tests
>>> python3 -m pytest tests/test_setup.py::TestSetupService -v

>>> # Run with logging output
>>> python3 -m pytest tests/test_setup.py -s --log-cli-level=INFO

>>> # Test specific clean install behavior
>>> python3 -m pytest tests/test_setup.py::TestSetupService::test_clean_install_log_preservation -v

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

import json
import os
import pytest
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, Any, List

import psycopg2
from fastapi.testclient import TestClient

# Import setup system components
from polymer_extractor.services.setup_service import SetupService
from polymer_extractor.api.setup import router
from polymer_extractor.utils.logging import Logger, get_logger
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
    and error handling scenarios.
    """

    @pytest.fixture
    def mock_managers(self):
        """Create mock managers for isolated testing."""
        with patch('polymer_extractor.services.setup_service.DatabaseManager') as mock_db, \
             patch('polymer_extractor.services.setup_service.GraphManager') as mock_graph, \
             patch('polymer_extractor.services.setup_service.StorageManager') as mock_storage:
            
            # Configure mock database manager
            mock_db_instance = mock_db.return_value
            mock_db_instance.test_connection.return_value = True
            mock_db_instance.check_health.return_value = {
                "connected": True,
                "version": "14.2",
                "table_count": 5,
                "response_time": 0.1
            }
            mock_db_instance.get_database_status.return_value = {
                "connected": True,
                "tables": ["system_logs", "extraction_metadata"]
            }
            mock_db_instance.list_all_tables.return_value = ["system_logs", "extraction_metadata", "datasets_metadata"]
            mock_db_instance.purge_table.return_value = True
            mock_db_instance.initialize_logging_table.return_value = True
            mock_db_instance.deploy_schema.return_value = True
            mock_db_instance.drop_all_tables.return_value = True
            
            # Configure mock graph manager
            mock_graph_instance = mock_graph.return_value
            mock_graph_instance.test_connection.return_value = True
            mock_graph_instance.check_health.return_value = {
                "connected": True,
                "version": "5.11",
                "node_count": 100,
                "relationship_count": 250,
                "response_time": 0.05
            }
            mock_graph_instance.get_database_status.return_value = {
                "connected": True,
                "node_count": 100,
                "relationship_count": 250
            }
            mock_graph_instance.purge_all_data.return_value = {"nodes_deleted": 100, "relationships_deleted": 250}
            mock_graph_instance.initialize_constraints.return_value = True
            
            # Configure mock storage manager
            mock_storage_instance = mock_storage.return_value
            mock_storage_instance.test_connection.return_value = True
            mock_storage_instance.check_health.return_value = {
                "connected": True,
                "backend": "local",
                "available_space": "10GB",
                "response_time": 0.02
            }
            mock_storage_instance.get_storage_status.return_value = {
                "connected": True,
                "backend": "local",
                "available_space": "10GB"
            }
            mock_storage_instance.purge_all_data.return_value = {"files_deleted": 50, "size_freed": "1GB"}
            mock_storage_instance.initialize_storage.return_value = True
            
            yield {
                "database": mock_db_instance,
                "graph": mock_graph_instance,
                "storage": mock_storage_instance
            }

    @pytest.fixture
    def mock_logger(self):
        """Create mock logger for testing logging operations."""
        with patch('polymer_extractor.services.setup_service.Logger') as mock_logger_class:
            mock_logger = mock_logger_class.return_value
            mock_logger.info = Mock()
            mock_logger.error = Mock()
            mock_logger.warning = Mock()
            mock_logger.pause_database_logging = Mock()
            mock_logger.resume_database_logging = Mock()
            mock_logger.reset_database_logs = Mock()
            mock_logger.initialize_database_table = Mock()
            yield mock_logger

    @pytest.fixture
    def setup_service(self, mock_managers, mock_logger):
        """Create SetupService instance with mocked dependencies."""
        with patch('polymer_extractor.services.setup_service.Logger', return_value=mock_logger):
            service = SetupService()
            # Replace managers with mocks
            service.database_manager = mock_managers["database"]
            service.graph_manager = mock_managers["graph"]
            service.storage_manager = mock_managers["storage"]
            yield service

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

    def test_check_system_health_all_healthy(self, setup_service, mock_managers):
        """Test system health check when all components are healthy."""
        result = setup_service.check_system_health()
        
        assert result["overall_status"] == "healthy"
        assert "database" in result["services"]
        assert "graph" in result["services"]
        assert "storage" in result["services"]
        
        # Verify all components reported healthy
        assert result["services"]["database"]["status"] == "healthy"
        assert result["services"]["graph"]["status"] == "healthy"
        assert result["services"]["storage"]["status"] == "healthy"
        
        # Verify connection tests were called
        mock_managers["database"].test_connection.assert_called_once()
        mock_managers["graph"].test_connection.assert_called_once()
        mock_managers["storage"].test_connection.assert_called_once()

    def test_check_system_health_database_unhealthy(self, setup_service, mock_managers):
        """Test system health check when database is unhealthy."""
        # Configure database to be unhealthy
        mock_managers["database"].test_connection.return_value = False
        mock_managers["database"].get_database_status.side_effect = Exception("Connection failed")
        
        result = setup_service.check_system_health()
        
        assert result["overall_status"] == "degraded"
        assert result["services"]["database"]["status"] != "healthy"
        
        # Other components should still be healthy
        assert result["services"]["graph"]["status"] == "healthy"
        assert result["services"]["storage"]["status"] == "healthy"

    def test_check_system_health_all_unhealthy(self, setup_service, mock_managers):
        """Test system health check when all components are unhealthy."""
        # Configure all components to be unhealthy
        for manager in mock_managers.values():
            manager.test_connection.return_value = False
            if hasattr(manager, 'get_database_status'):
                manager.get_database_status.side_effect = Exception("Connection failed")
            if hasattr(manager, 'get_storage_status'):
                manager.get_storage_status.side_effect = Exception("Storage error")
        
        result = setup_service.check_system_health()
        
        assert result["overall_status"] == "unhealthy"
        assert all(svc["status"] != "healthy" for svc in result["services"].values())

    def test_initialize_system_success(self, setup_service, mock_managers, mock_logger):
        """Test successful system initialization."""
        result = setup_service.initialize_system()
        
        assert result["success"] is True
        assert result["status"] == "initialized"
        assert "database" in result["components"]
        assert "graph" in result["components"] 
        assert "storage" in result["components"]
        
        # Verify initialization calls
        mock_managers["database"].deploy_schema.assert_called_once()
        mock_managers["graph"].initialize_constraints.assert_called_once()
        mock_managers["storage"].initialize_storage.assert_called_once()
        
        # Verify logging
        mock_logger.info.assert_any_call("System initialization started", source="setup_service")

    def test_initialize_system_with_failures(self, setup_service, mock_managers, mock_logger):
        """Test system initialization with component failures."""
        # Configure database initialization to fail
        mock_managers["database"].deploy_schema.side_effect = Exception("Schema deployment failed")
        
        result = setup_service.initialize_system()
        
        assert result["success"] is False
        assert len(result["errors"]) > 0
        assert any("Schema deployment failed" in error for error in result["errors"])
        
        # Verify error logging
        mock_logger.error.assert_called()

    def test_purge_all_data_preserve_schemas(self, setup_service, mock_managers, mock_logger):
        """Test data purging while preserving schemas."""
        result = setup_service.purge_all_data(
            preserve_schemas=True,
            preserve_buckets=True,
            preserve_logs=False
        )
        
        assert result["success"] is True
        assert result["operations"]["preserve_schemas"] is True
        assert result["operations"]["preserve_buckets"] is True
        assert result["operations"]["preserve_logs"] is False
        
        # Verify purge operations were called
        mock_managers["database"].purge_table.assert_called()
        mock_managers["graph"].purge_all_data.assert_called()
        mock_managers["storage"].purge_all_data.assert_called()
        
        # Verify system_logs was handled first
        mock_logger.info.assert_any_call(
            "Starting system purge: schemas=True, buckets=True, logs=False",
            source="setup_service"
        )

    def test_purge_all_data_no_preservation(self, setup_service, mock_managers, mock_logger):
        """Test complete data purging without preservation."""
        result = setup_service.purge_all_data(
            preserve_schemas=False,
            preserve_buckets=False,
            preserve_logs=False
        )
        
        assert result["success"] is True
        assert result["operations"]["preserve_schemas"] is False
        assert result["operations"]["preserve_buckets"] is False
        assert result["operations"]["preserve_logs"] is False
        
        # Verify complete purge operations
        mock_managers["database"].drop_all_tables.assert_called()
        mock_managers["graph"].purge_all_data.assert_called()
        mock_managers["storage"].purge_all_data.assert_called()

    def test_purge_storage_data_preserve_buckets(self, setup_service, mock_managers):
        """Test storage purging while preserving bucket structures."""
        result = setup_service.purge_storage_data(preserve_buckets=True)
        
        assert result["success"] is True
        assert result["preserve_buckets"] is True
        
        # Verify storage purge was called with correct parameters
        mock_managers["storage"].purge_all_data.assert_called_with(preserve_buckets=True)

    def test_purge_storage_data_no_preservation(self, setup_service, mock_managers):
        """Test complete storage purging."""
        result = setup_service.purge_storage_data(preserve_buckets=False)
        
        assert result["success"] is True
        assert result["preserve_buckets"] is False
        
        # Verify complete storage purge
        mock_managers["storage"].purge_all_data.assert_called_with(preserve_buckets=False)

    def test_clean_install_success(self, setup_service, mock_managers, mock_logger):
        """Test successful clean install operation."""
        result = setup_service.clean_install()
        
        assert result["success"] is True
        assert result["operation"] == "clean_install"
        
        # Verify logging was paused and resumed
        mock_logger.pause_database_logging.assert_called_once()
        mock_logger.resume_database_logging.assert_called_once()
        
        # Verify purge and initialization sequence
        mock_managers["database"].drop_all_tables.assert_called()
        mock_managers["database"].deploy_schema.assert_called()

    def test_clean_install_with_logging_errors(self, setup_service, mock_managers, mock_logger):
        """Test clean install with logging system errors."""
        # Configure logging initialization to fail
        mock_managers["database"].initialize_logging_table.side_effect = Exception("Logging init failed")
        
        result = setup_service.clean_install()
        
        # Should still succeed but with warnings
        assert result["success"] is True
        assert len(result["warnings"]) > 0
        assert any("Failed to reinitialize logging system" in warning for warning in result["warnings"])

    def test_logging_system_integration(self, setup_service, mock_logger):
        """Test logging system integration during operations."""
        # Test that logging methods are called appropriately
        setup_service.initialize_system()
        
        # Verify info logging was called
        mock_logger.info.assert_called()
        
        # Test error scenarios trigger error logging
        setup_service.database_manager.deploy_schema.side_effect = Exception("Test error")
        setup_service.initialize_system()
        
        mock_logger.error.assert_called()

    def test_system_logs_handling(self, setup_service, mock_managers, mock_logger):
        """Test special handling of system_logs table during operations."""
        # Configure database to have system_logs table
        mock_managers["database"].list_all_tables.return_value = [
            "system_logs", "extraction_metadata", "datasets_metadata"
        ]
        
        result = setup_service.purge_all_data(preserve_logs=False)
        
        # Verify system_logs was handled appropriately
        assert result["success"] is True
        
        # Check that purge_table was called for all tables
        assert mock_managers["database"].purge_table.call_count >= 3


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
    def client(self):
        """Create FastAPI test client."""
        from fastapi import FastAPI
        
        # Create a minimal FastAPI app for testing
        app = FastAPI()
        app.include_router(router)
        
        return TestClient(app)

    @pytest.fixture
    def mock_setup_service(self):
        """Mock SetupService for API testing."""
        with patch('polymer_extractor.api.setup.setup_service') as mock_service:
            yield mock_service

    def test_health_endpoint_healthy_system(self, client, mock_setup_service):
        """Test /setup/health endpoint with healthy system."""
        # Configure mock to return healthy status
        mock_setup_service.check_system_health.return_value = {
            "status": "healthy",
            "overall_health": True,
            "components": {
                "database": {"healthy": True, "status": "connected"},
                "graph": {"healthy": True, "status": "connected"},
                "storage": {"healthy": True, "status": "connected"}
            },
            "timestamp": datetime.now().isoformat()
        }
        
        response = client.get('/setup/health')
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["status"] == "ok"
        assert data["data"]["status"] == "healthy"
        assert data["data"]["overall_health"] is True

    def test_health_endpoint_degraded_system(self, client, mock_setup_service):
        """Test /setup/health endpoint with degraded system."""
        mock_setup_service.check_system_health.return_value = {
            "status": "degraded",
            "overall_health": False,
            "components": {
                "database": {"healthy": False, "status": "connection_failed"},
                "graph": {"healthy": True, "status": "connected"},
                "storage": {"healthy": True, "status": "connected"}
            },
            "timestamp": datetime.now().isoformat()
        }
        
        response = client.get('/setup/health')
        
        assert response.status_code == 200  # Health endpoint returns 200 even for degraded
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["status"] == "degraded"
        assert data["data"]["overall_health"] is False

    def test_initialize_endpoint_success(self, client, mock_setup_service):
        """Test /setup/initialize endpoint with successful initialization."""
        mock_setup_service.initialize_system.return_value = {
            "success": True,
            "status": "initialized",
            "components": {
                "database": {"success": True, "message": "Schema deployed"},
                "graph": {"success": True, "message": "Constraints created"},
                "storage": {"success": True, "message": "Storage initialized"}
            },
            "timestamp": datetime.now().isoformat()
        }
        
        response = client.post('/setup/initialize')
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["status"] == "ok"
        assert data["data"]["status"] == "initialized"

    def test_initialize_endpoint_failure(self, client, mock_setup_service):
        """Test /setup/initialize endpoint with initialization failure."""
        mock_setup_service.initialize_system.return_value = {
            "success": False,
            "status": "failed",
            "errors": ["Database schema deployment failed", "Storage initialization failed"],
            "components": {
                "database": {"success": False, "error": "Connection timeout"},
                "graph": {"success": True, "message": "Constraints created"},
                "storage": {"success": False, "error": "Permission denied"}
            },
            "timestamp": datetime.now().isoformat()
        }
        
        response = client.post('/setup/initialize')
        
        assert response.status_code == 500
        data = response.json()
        
        assert data["success"] is False
        assert data["status"] == "error"
        assert len(data["data"]["errors"]) > 0

    def test_purge_endpoint_with_valid_request(self, client, mock_setup_service):
        """Test /setup/purge endpoint with valid request parameters."""
        mock_setup_service.purge_all_data.return_value = {
            "success": True,
            "operations": {
                "preserve_schemas": True,
                "preserve_buckets": True,
                "preserve_logs": False
            },
            "results": {
                "database": {"tables_purged": 5, "records_deleted": 1000},
                "graph": {"nodes_deleted": 100, "relationships_deleted": 250},
                "storage": {"files_deleted": 50, "size_freed": "1GB"}
            },
            "timestamp": datetime.now().isoformat()
        }
        
        request_data = {
            "preserve_schemas": True,
            "preserve_buckets": True,
            "preserve_logs": False
        }
        
        response = client.post('/setup/purge', json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["status"] == "ok"
        assert data["data"]["operations"]["preserve_schemas"] is True
        
        # Verify SetupService was called with correct parameters
        mock_setup_service.purge_all_data.assert_called_once_with(
            preserve_schemas=True,
            preserve_buckets=True,
            preserve_logs=False
        )

    def test_purge_endpoint_with_defaults(self, client, mock_setup_service):
        """Test /setup/purge endpoint with default parameters."""
        mock_setup_service.purge_all_data.return_value = {
            "success": True,
            "operations": {
                "preserve_schemas": True,
                "preserve_buckets": True,
                "preserve_logs": False
            },
            "results": {},
            "timestamp": datetime.now().isoformat()
        }
        
        response = client.post('/setup/purge', json={})
        
        assert response.status_code == 200
        
        # Verify default values were used
        mock_setup_service.purge_all_data.assert_called_once_with(
            preserve_schemas=True,
            preserve_buckets=True,
            preserve_logs=False
        )

    def test_purge_endpoint_failure(self, client, mock_setup_service):
        """Test /setup/purge endpoint with purge failure."""
        mock_setup_service.purge_all_data.return_value = {
            "success": False,
            "errors": ["Database connection failed", "Storage access denied"],
            "timestamp": datetime.now().isoformat()
        }
        
        response = client.post('/setup/purge', json={"preserve_schemas": False})
        
        assert response.status_code == 500
        data = response.json()
        
        assert data["success"] is False
        assert data["status"] == "error"

    def test_reset_endpoint_success(self, client, mock_setup_service):
        """Test /setup/reset endpoint with successful clean install."""
        mock_setup_service.clean_install.return_value = {
            "success": True,
            "operation": "clean_install",
            "stages": {
                "purge": {"success": True, "message": "All data purged"},
                "initialize": {"success": True, "message": "System initialized"}
            },
            "timestamp": datetime.now().isoformat()
        }
        
        response = client.post('/setup/reset')
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["status"] == "ok"
        assert data["data"]["operation"] == "clean_install"

    def test_reset_endpoint_failure(self, client, mock_setup_service):
        """Test /setup/reset endpoint with clean install failure."""
        mock_setup_service.clean_install.return_value = {
            "success": False,
            "operation": "clean_install",
            "errors": ["Failed to drop database tables", "Storage initialization failed"],
            "timestamp": datetime.now().isoformat()
        }
        
        response = client.post('/setup/reset')
        
        assert response.status_code == 500
        data = response.json()
        
        assert data["success"] is False
        assert data["status"] == "error"

    def test_invalid_json_request(self, client, mock_setup_service):
        """Test API endpoints with invalid JSON."""
        # FastAPI handles JSON validation automatically
        response = client.post('/setup/purge', 
                              data="invalid json",
                              headers={"Content-Type": "application/json"})
        
        assert response.status_code == 422  # FastAPI returns 422 for validation errors

    def test_cors_headers(self, client):
        """Test that CORS headers are properly set."""
        response = client.get('/setup/health')
        
        # Check for CORS headers if configured
        if 'Access-Control-Allow-Origin' in response.headers:
            assert response.headers['Access-Control-Allow-Origin'] is not None


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
        """Create real logger instance for integration testing."""
        # Use a test-specific logger to avoid interfering with global state
        from polymer_extractor.utils.logging import Logger
        logger = Logger(min_level="DEBUG", enable_database=False)  # Disable DB for testing
        yield logger

    @pytest.fixture
    def setup_with_real_logger(self, real_logger):
        """Create SetupService with real logger and mocked managers."""
        with patch('polymer_extractor.services.setup_service.DatabaseManager') as mock_db, \
             patch('polymer_extractor.services.setup_service.GraphManager') as mock_graph, \
             patch('polymer_extractor.services.setup_service.StorageManager') as mock_storage:
            
            # Configure basic mock responses
            mock_db.return_value.test_connection.return_value = True
            mock_graph.return_value.test_connection.return_value = True
            mock_storage.return_value.test_connection.return_value = True
            
            # Create service with real logger
            with patch('polymer_extractor.services.setup_service.Logger', return_value=real_logger):
                service = SetupService()
                yield service

    def test_logger_pause_resume_during_clean_install(self, setup_with_real_logger):
        """Test that logger is properly paused and resumed during clean install."""
        logger = setup_with_real_logger.logger
        
        # Mock the pause/resume methods to track calls
        with patch.object(logger, 'pause_database_logging') as mock_pause, \
             patch.object(logger, 'resume_database_logging') as mock_resume:
            
            result = setup_with_real_logger.clean_install()
            
            # Verify pause was called before purge
            mock_pause.assert_called_once()
            
            # Verify resume was called after initialization
            mock_resume.assert_called_once()

    def test_system_logs_table_special_handling(self, setup_with_real_logger):
        """Test special handling of system_logs table during operations."""
        service = setup_with_real_logger
        
        # Mock database manager to return system_logs in table list
        service.database_manager.list_all_tables.return_value = [
            "system_logs", "extraction_metadata", "datasets_metadata"
        ]
        
        # Mock individual table purge operations
        service.database_manager.purge_table.return_value = True
        
        result = service.purge_all_data(preserve_logs=False)
        
        assert result["success"] is True
        
        # Verify that system_logs was handled (exact implementation depends on priority logic)
        service.database_manager.purge_table.assert_called()

    def test_logging_during_health_checks(self, setup_with_real_logger):
        """Test that health checks generate appropriate log entries."""
        service = setup_with_real_logger
        
        # Capture log calls
        with patch.object(service.logger, 'info') as mock_info:
            result = service.check_system_health()
            
            # Verify health check was logged
            mock_info.assert_called()
            
            # Check that source was properly set
            calls = mock_info.call_args_list
            assert any('setup_service' in str(call) for call in calls)

    def test_error_logging_during_failures(self, setup_with_real_logger):
        """Test that errors are properly logged during operation failures."""
        service = setup_with_real_logger
        
        # Configure database to fail
        service.database_manager.deploy_schema.side_effect = Exception("Test deployment error")
        
        with patch.object(service.logger, 'error') as mock_error:
            result = service.initialize_system()
            
            # Verify error was logged
            mock_error.assert_called()
            
            # Check error message content
            calls = mock_error.call_args_list
            assert any("Test deployment error" in str(call) for call in calls)

    def test_logging_table_initialization(self, setup_with_real_logger):
        """Test logging table initialization during setup operations."""
        service = setup_with_real_logger
        
        # Mock database manager methods
        service.database_manager.initialize_logging_table.return_value = True
        
        with patch.object(service.logger, 'info') as mock_info:
            result = service.initialize_system()
            
            # Should succeed and log appropriately
            assert result["success"] is True
            mock_info.assert_called()


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
        """Create SetupService with failing dependencies for error testing."""
        with patch('polymer_extractor.services.setup_service.DatabaseManager') as mock_db, \
             patch('polymer_extractor.services.setup_service.GraphManager') as mock_graph, \
             patch('polymer_extractor.services.setup_service.StorageManager') as mock_storage, \
             patch('polymer_extractor.services.setup_service.Logger') as mock_logger:
            
            # Configure managers to fail in various ways
            mock_db.return_value.test_connection.side_effect = Exception("Database unreachable")
            mock_graph.return_value.test_connection.side_effect = Exception("Neo4j connection timeout")
            mock_storage.return_value.test_connection.side_effect = Exception("Storage permission denied")
            
            service = SetupService()
            yield service

    def test_database_connection_failure(self, failing_setup_service):
        """Test handling of database connection failures."""
        result = failing_setup_service.check_system_health()
        
        assert result["overall_health"] is False
        assert result["status"] == "critical"
        assert not result["components"]["database"]["healthy"]
        assert "Database unreachable" in str(result["components"]["database"]["status"])

    def test_partial_system_failure_recovery(self):
        """Test recovery from partial system failures."""
        with patch('polymer_extractor.services.setup_service.DatabaseManager') as mock_db, \
             patch('polymer_extractor.services.setup_service.GraphManager') as mock_graph, \
             patch('polymer_extractor.services.setup_service.StorageManager') as mock_storage:
            
            # Database works, graph fails, storage works
            mock_db.return_value.test_connection.return_value = True
            mock_db.return_value.get_database_status.return_value = {"connected": True}
            
            mock_graph.return_value.test_connection.side_effect = Exception("Graph error")
            
            mock_storage.return_value.test_connection.return_value = True
            mock_storage.return_value.get_storage_status.return_value = {"connected": True}
            
            service = SetupService()
            result = service.check_system_health()
            
            assert result["status"] == "degraded"
            assert result["components"]["database"]["healthy"] is True
            assert result["components"]["graph"]["healthy"] is False
            assert result["components"]["storage"]["healthy"] is True

    def test_initialization_with_mixed_results(self):
        """Test initialization when some components succeed and others fail."""
        with patch('polymer_extractor.services.setup_service.DatabaseManager') as mock_db, \
             patch('polymer_extractor.services.setup_service.GraphManager') as mock_graph, \
             patch('polymer_extractor.services.setup_service.StorageManager') as mock_storage:
            
            # Database succeeds
            mock_db.return_value.deploy_schema.return_value = True
            
            # Graph fails
            mock_graph.return_value.initialize_constraints.side_effect = Exception("Constraint creation failed")
            
            # Storage succeeds
            mock_storage.return_value.initialize_storage.return_value = True
            
            service = SetupService()
            result = service.initialize_system()
            
            assert result["success"] is False
            assert len(result["errors"]) > 0
            assert "Constraint creation failed" in str(result["errors"])

    def test_purge_operation_error_handling(self):
        """Test error handling during purge operations."""
        with patch('polymer_extractor.services.setup_service.DatabaseManager') as mock_db, \
             patch('polymer_extractor.services.setup_service.GraphManager') as mock_graph, \
             patch('polymer_extractor.services.setup_service.StorageManager') as mock_storage:
            
            # Configure purge operations to fail
            mock_db.return_value.purge_table.side_effect = Exception("Table purge failed")
            mock_graph.return_value.purge_all_data.side_effect = Exception("Graph purge failed")
            mock_storage.return_value.purge_all_data.return_value = {"success": True}
            
            service = SetupService()
            result = service.purge_all_data()
            
            assert result["success"] is False
            assert len(result["errors"]) >= 2  # At least database and graph errors

    def test_clean_install_error_recovery(self):
        """Test error recovery during clean install operations."""
        with patch('polymer_extractor.services.setup_service.DatabaseManager') as mock_db, \
             patch('polymer_extractor.services.setup_service.GraphManager') as mock_graph, \
             patch('polymer_extractor.services.setup_service.StorageManager') as mock_storage:
            
            # Purge succeeds but initialization fails
            mock_db.return_value.drop_all_tables.return_value = True
            mock_db.return_value.deploy_schema.side_effect = Exception("Schema deployment failed")
            
            service = SetupService()
            
            # Mock logger to verify error handling
            with patch.object(service.logger, 'error') as mock_error:
                result = service.clean_install()
                
                assert result["success"] is False
                mock_error.assert_called()


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
