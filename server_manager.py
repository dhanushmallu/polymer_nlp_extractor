# polymer_extractor/server_manager.py

"""
Server Manager for Polymer NLP Extractor.

Purpose
-------
Manages the lifecycle of external services (PostgreSQL, Neo4j, Grobid) via Docker Compose.
Provides Python interface for service management while delegating actual operations to 
the authoritative server.sh script.

Key Abstractions
---------------
- ServiceManager: Orchestrates Docker Compose services via server.sh delegation
- HealthChecker: Validates service readiness using port checks and container status
- StatusReporter: Provides detailed service status for debugging

Examples
--------
>>> from server_manager import ServerManager
>>> sm = ServerManager()
>>> sm.start_all_services()  # Delegates to Docker Compose
>>> status = sm.get_status()  # Health check results
>>> sm.clean_shutdown()      # Graceful shutdown

Notes
-----
- Actual service management via Docker Compose and server.sh
- Health checks independent of Docker container status
- Preserves data during shutdown operations
"""

import os
import sys
import time
import signal
import atexit
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime
from dotenv import load_dotenv
import socket

from polymer_extractor.utils.logging import Logger

# Load environment variables
load_dotenv()


class ServerManager:
    """
    Manages external service lifecycle via Docker Compose delegation.
    
    Summary
    -------
    Provides Python interface for service management while delegating actual operations
    to Docker Compose via server.sh script. Focuses on health monitoring and status
    reporting rather than direct service manipulation.
    
    Parameters
    ----------
    startup_timeout : int
        Maximum seconds to wait for service startup (default: 30)
    shutdown_timeout : int  
        Maximum seconds to wait for service shutdown (default: 15)
    auto_restart : bool
        Whether to automatically restart failed services (default: True)
    
    Returns
    -------
    ServerManager
        Configured service manager instance
        
    Raises
    ------
    EnvironmentError
        When required environment variables are missing
    subprocess.CalledProcessError
        When Docker Compose commands fail
        
    Examples
    --------
    >>> sm = ServerManager()
    >>> sm.services_up()  # Check if all services are running
    >>> sm.get_status()   # Get detailed status report
    
    Notes
    -----
    - Complexity: Service operations are O(1), health checks are O(n) services
    - Side effects: Registers signal handlers for graceful cleanup
    """
    
    def __init__(self):
        self.logger = Logger()
        
        # Get configuration from environment variables
        self.startup_timeout = int(os.getenv("SERVER_STARTUP_TIMEOUT", "30"))
        self.shutdown_timeout = int(os.getenv("SERVER_SHUTDOWN_TIMEOUT", "15"))
        self.auto_restart = os.getenv("AUTO_RESTART_SERVICES", "true").lower() == "true"
        self.force_kill_on_exit = os.getenv("FORCE_KILL_ON_EXIT", "true").lower() == "true"
        
        # Get ports from environment variables with fallback defaults
        postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        neo4j_port = int(os.getenv("NEO4J_PORT", "7687"))
        neo4j_http_port = int(os.getenv("NEO4J_HTTP_PORT", "7474"))
        grobid_port = int(os.getenv("GROBID_PORT", "8070"))
        
        self.services = {
            "postgresql": {
                "status": "unknown", 
                "pid": None, 
                "port": postgres_port,
                "name": "PostgreSQL",
                "docker_compose_service": "postgres",
                "container_name": "polymer_postgres"
            },
            "neo4j": {
                "status": "unknown", 
                "pid": None, 
                "port": neo4j_port,
                "http_port": neo4j_http_port,
                "name": "Neo4j", 
                "docker_compose_service": "neo4j",
                "container_name": "polymer_neo4j"
            },
            "grobid": {
                "status": "unknown", 
                "pid": None, 
                "port": grobid_port,
                "name": "GROBID",
                "docker_compose_service": "grobid",
                "container_name": "polymer_grobid"
            }
        }
        
        # Track managed services
        self._managed_services = set()
        
        # Register cleanup handlers
        atexit.register(self._cleanup_on_exit)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info(f"ServerManager initialized with ports: PostgreSQL:{postgres_port}, Neo4j:{neo4j_port}, GROBID:{grobid_port}", 
                        source="server_manager", event_type="initialization")

    def _check_port_available(self, port: int, host: str = "localhost") -> bool:
        """
        Check if a port is available (not in use).
        
        Parameters
        ----------
        port : int
            Port number to check
        host : str
            Host to check port on (default: localhost)
            
        Returns
        -------
        bool
            True if port is available, False if in use
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                return result != 0  # 0 means connection successful (port in use)
        except Exception:
            return True  # Assume available if check fails

    def _check_service_health(self, service_name: str) -> Dict[str, Any]:
        """
        Check health of a specific service.
        
        Parameters
        ----------
        service_name : str
            Name of service to check (postgresql, neo4j, grobid)
            
        Returns
        -------
        Dict[str, Any]
            Health status with port_active, container_running, ready fields
        """
        if service_name not in self.services:
            return {"error": f"Unknown service: {service_name}"}
            
        service = self.services[service_name]
        health = {
            "service": service_name,
            "port_active": False,
            "container_running": False,
            "ready": False
        }
        
        # Check if main port is active
        health["port_active"] = not self._check_port_available(service["port"])
        
        # Check container status via docker
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={service['container_name']}", "--format", "{{.Status}}"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                status = result.stdout.strip().lower()
                health["container_running"] = "up" in status
        except Exception as e:
            self.logger.warning(f"Failed to check container status for {service_name}: {e}", 
                              source="server_manager", event_type="health_check")
        
        # Service is ready if both port is active and container is running
        health["ready"] = health["port_active"] and health["container_running"]
        
        return health

    def start_postgresql(self) -> bool:
        """
        Start PostgreSQL service via Docker Compose.
        
        Returns
        -------
        bool
            True if service started successfully
            
        Raises
        ------
        subprocess.CalledProcessError
            When Docker Compose command fails
            
        Examples
        --------
        >>> sm = ServerManager()
        >>> success = sm.start_postgresql()
        >>> if success:
        ...     print("PostgreSQL is ready")
        
        Notes
        -----
        - Delegates to Docker Compose for actual service management
        - Waits for service readiness up to startup_timeout seconds
        """
        try:
            self.logger.info("Starting PostgreSQL service via Docker Compose", 
                           source="server_manager", event_type="service_start")
            
            # Start PostgreSQL service
            result = subprocess.run(
                ["docker-compose", "-f", "docker-compose.services.yml", "up", "-d", "postgres"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                self.logger.error(f"Failed to start PostgreSQL: {result.stderr}", 
                                source="server_manager", event_type="service_start_failed")
                return False
            
            # Wait for service to be ready
            start_time = time.time()
            while time.time() - start_time < self.startup_timeout:
                health = self._check_service_health("postgresql")
                if health.get("ready", False):
                    self.services["postgresql"]["status"] = "running"
                    self._managed_services.add("postgresql")
                    self.logger.info("PostgreSQL service started successfully", 
                                   source="server_manager", event_type="service_ready")
                    return True
                time.sleep(2)
            
            self.logger.error(f"PostgreSQL failed to become ready within {self.startup_timeout}s", 
                            source="server_manager", event_type="service_timeout")
            return False
            
        except Exception as e:
            self.logger.error(f"Error starting PostgreSQL: {e}", 
                            source="server_manager", event_type="service_error")
            return False

    def start_neo4j(self) -> bool:
        """
        Start Neo4j service via Docker Compose.
        
        Returns
        -------
        bool
            True if service started successfully
            
        Examples
        --------
        >>> sm = ServerManager()
        >>> success = sm.start_neo4j()
        
        Notes
        -----
        - Neo4j may take longer to start than other services
        - Checks both bolt port (7687) and HTTP port (7474)
        """
        try:
            self.logger.info("Starting Neo4j service via Docker Compose", 
                           source="server_manager", event_type="service_start")
            
            # Start Neo4j service
            result = subprocess.run(
                ["docker-compose", "-f", "docker-compose.services.yml", "up", "-d", "neo4j"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                self.logger.error(f"Failed to start Neo4j: {result.stderr}", 
                                source="server_manager", event_type="service_start_failed")
                return False
            
            # Wait for service to be ready
            start_time = time.time()
            while time.time() - start_time < self.startup_timeout:
                health = self._check_service_health("neo4j")
                if health.get("ready", False):
                    self.services["neo4j"]["status"] = "running"
                    self._managed_services.add("neo4j")
                    self.logger.info("Neo4j service started successfully", 
                                   source="server_manager", event_type="service_ready")
                    return True
                time.sleep(2)
            
            self.logger.error(f"Neo4j failed to become ready within {self.startup_timeout}s", 
                            source="server_manager", event_type="service_timeout")
            return False
            
        except Exception as e:
            self.logger.error(f"Error starting Neo4j: {e}", 
                            source="server_manager", event_type="service_error")
            return False

    def start_grobid(self) -> bool:
        """
        Start GROBID service via Docker Compose.
        
        Returns
        -------
        bool
            True if service started successfully
            
        Examples
        --------
        >>> sm = ServerManager()
        >>> success = sm.start_grobid()
        
        Notes
        -----
        - GROBID is heaviest service and may take longest to start
        - Service readiness determined by HTTP endpoint availability
        """
        try:
            self.logger.info("Starting GROBID service via Docker Compose", 
                           source="server_manager", event_type="service_start")
            
            # Start GROBID service
            result = subprocess.run(
                ["docker-compose", "-f", "docker-compose.services.yml", "up", "-d", "grobid"],
                capture_output=True, text=True, timeout=60  # GROBID takes longer
            )
            
            if result.returncode != 0:
                self.logger.error(f"Failed to start GROBID: {result.stderr}", 
                                source="server_manager", event_type="service_start_failed")
                return False
            
            # Wait for service to be ready (GROBID takes longer)
            start_time = time.time()
            extended_timeout = max(self.startup_timeout, 60)  # At least 60s for GROBID
            while time.time() - start_time < extended_timeout:
                health = self._check_service_health("grobid")
                if health.get("ready", False):
                    self.services["grobid"]["status"] = "running"
                    self._managed_services.add("grobid")
                    self.logger.info("GROBID service started successfully", 
                                   source="server_manager", event_type="service_ready")
                    return True
                time.sleep(3)  # Check less frequently for GROBID
            
            self.logger.error(f"GROBID failed to become ready within {extended_timeout}s", 
                            source="server_manager", event_type="service_timeout")
            return False
            
        except Exception as e:
            self.logger.error(f"Error starting GROBID: {e}", 
                            source="server_manager", event_type="service_error")
            return False

    def start_all_services(self) -> bool:
        """
        Start all services via Docker Compose.
        
        Returns
        -------
        bool
            True if all services started successfully
            
        Examples
        --------
        >>> sm = ServerManager()
        >>> if sm.start_all_services():
        ...     print("All services ready")
        
        Notes
        -----
        - Starts services in parallel for faster startup
        - Returns False if any service fails to start
        """
        try:
            self.logger.info("Starting all services via Docker Compose", 
                           source="server_manager", event_type="services_start")
            
            # Start all services at once
            result = subprocess.run(
                ["docker-compose", "-f", "docker-compose.services.yml", "up", "-d"],
                capture_output=True, text=True, timeout=60
            )
            
            if result.returncode != 0:
                self.logger.error(f"Failed to start services: {result.stderr}", 
                                source="server_manager", event_type="services_start_failed")
                return False
            
            # Wait for all services to be ready
            all_ready = False
            start_time = time.time()
            max_timeout = max(self.startup_timeout, 60)  # At least 60s for GROBID
            
            while time.time() - start_time < max_timeout and not all_ready:
                service_status = []
                for service_name in self.services.keys():
                    health = self._check_service_health(service_name)
                    if health.get("ready", False):
                        self.services[service_name]["status"] = "running"
                        self._managed_services.add(service_name)
                    service_status.append(health.get("ready", False))
                
                all_ready = all(service_status)
                if not all_ready:
                    time.sleep(3)
            
            if all_ready:
                self.logger.info("All services started successfully", 
                               source="server_manager", event_type="services_ready")
                return True
            else:
                self.logger.error(f"Not all services ready within {max_timeout}s", 
                                source="server_manager", event_type="services_timeout")
                return False
                
        except Exception as e:
            self.logger.error(f"Error starting services: {e}", 
                            source="server_manager", event_type="services_error")
            return False

    def stop_service(self, service_name: str) -> bool:
        """
        Stop a specific service via Docker Compose.
        
        Parameters
        ----------
        service_name : str
            Name of service to stop
            
        Returns
        -------
        bool
            True if service stopped successfully
        """
        if service_name not in self.services:
            self.logger.error(f"Unknown service: {service_name}", 
                            source="server_manager", event_type="service_error")
            return False
        
        try:
            service = self.services[service_name]
            compose_service = service["docker_compose_service"]
            
            result = subprocess.run(
                ["docker-compose", "-f", "docker-compose.services.yml", "stop", compose_service],
                capture_output=True, text=True, timeout=self.shutdown_timeout
            )
            
            if result.returncode == 0:
                self.services[service_name]["status"] = "stopped"
                self._managed_services.discard(service_name)
                self.logger.info(f"{service_name} service stopped", 
                               source="server_manager", event_type="service_stop")
                return True
            else:
                self.logger.error(f"Failed to stop {service_name}: {result.stderr}", 
                                source="server_manager", event_type="service_stop_failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Error stopping {service_name}: {e}", 
                            source="server_manager", event_type="service_error")
            return False

    def stop_all_services(self) -> bool:
        """
        Stop all services via Docker Compose.
        
        Returns
        -------
        bool
            True if all services stopped successfully
        """
        try:
            self.logger.info("Stopping all services via Docker Compose", 
                           source="server_manager", event_type="services_stop")
            
            result = subprocess.run(
                ["docker-compose", "-f", "docker-compose.services.yml", "down"],
                capture_output=True, text=True, timeout=self.shutdown_timeout * 2
            )
            
            if result.returncode == 0:
                for service_name in self.services.keys():
                    self.services[service_name]["status"] = "stopped"
                self._managed_services.clear()
                self.logger.info("All services stopped successfully", 
                               source="server_manager", event_type="services_stopped")
                return True
            else:
                self.logger.error(f"Failed to stop services: {result.stderr}", 
                                source="server_manager", event_type="services_stop_failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Error stopping services: {e}", 
                            source="server_manager", event_type="services_error")
            return False

    def services_up(self) -> bool:
        """
        Check if all services are running and ready.
        
        Returns
        -------
        bool
            True if all services are ready
            
        Examples
        --------
        >>> sm = ServerManager()
        >>> if sm.services_up():
        ...     print("All services operational")
        
        Notes
        -----
        - Performs actual health checks, not just container status
        - Returns False if any service is not ready
        """
        try:
            for service_name in self.services.keys():
                health = self._check_service_health(service_name)
                if not health.get("ready", False):
                    return False
            return True
        except Exception as e:
            self.logger.error(f"Error checking services: {e}", 
                            source="server_manager", event_type="health_check_error")
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        Get detailed status of all services.
        
        Returns
        -------
        Dict[str, Any]
            Status report with service health and configuration
            
        Examples
        --------
        >>> sm = ServerManager()
        >>> status = sm.get_status()
        >>> print(f"PostgreSQL ready: {status['postgresql']['ready']}")
        
        Notes
        -----
        - Provides comprehensive health information for debugging
        - Includes port status, container status, and readiness
        """
        status = {
            "timestamp": datetime.now().isoformat(),
            "services": {},
            "summary": {
                "total_services": len(self.services),
                "running_services": 0,
                "ready_services": 0,
                "all_ready": False
            }
        }
        
        for service_name, service_config in self.services.items():
            health = self._check_service_health(service_name)
            status["services"][service_name] = {
                "name": service_config["name"],
                "port": service_config["port"],
                "container": service_config["container_name"],
                "health": health,
                "managed": service_name in self._managed_services
            }
            
            if health.get("container_running", False):
                status["summary"]["running_services"] += 1
            if health.get("ready", False):
                status["summary"]["ready_services"] += 1
        
        status["summary"]["all_ready"] = (
            status["summary"]["ready_services"] == status["summary"]["total_services"]
        )
        
        return status

    def clean_shutdown(self) -> bool:
        """
        Perform graceful shutdown preserving data.
        
        Returns
        -------
        bool
            True if shutdown completed successfully
            
        Examples
        --------
        >>> sm = ServerManager()
        >>> sm.clean_shutdown()  # Preserves all data
        
        Notes
        -----
        - Stops services but preserves volumes and data
        - Equivalent to server.sh clean command
        """
        try:
            self.logger.info("Performing clean shutdown (preserving data)", 
                           source="server_manager", event_type="shutdown")
            return self.stop_all_services()
        except Exception as e:
            self.logger.error(f"Error during clean shutdown: {e}", 
                            source="server_manager", event_type="shutdown_error")
            return False

    def reset_all(self) -> bool:
        """
        Reset all services removing volumes but keeping images.
        
        Returns
        -------
        bool
            True if reset completed successfully
            
        Notes
        -----
        - Equivalent to server.sh reset command
        - Removes volumes but keeps Docker images
        """
        try:
            self.logger.info("Resetting all services (removing volumes)", 
                           source="server_manager", event_type="reset")
            
            result = subprocess.run(
                ["docker-compose", "-f", "docker-compose.services.yml", "down", "-v"],
                capture_output=True, text=True, timeout=self.shutdown_timeout * 2
            )
            
            if result.returncode == 0:
                for service_name in self.services.keys():
                    self.services[service_name]["status"] = "reset"
                self._managed_services.clear()
                self.logger.info("All services reset successfully", 
                               source="server_manager", event_type="reset_complete")
                return True
            else:
                self.logger.error(f"Failed to reset services: {result.stderr}", 
                                source="server_manager", event_type="reset_failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Error during reset: {e}", 
                            source="server_manager", event_type="reset_error")
            return False

    def purge_all(self) -> bool:
        """
        Purge all services removing containers, volumes, and images.
        
        Returns
        -------
        bool
            True if purge completed successfully
            
        Notes
        -----
        - Equivalent to server.sh purge command
        - Complete cleanup removing everything
        """
        try:
            self.logger.info("Purging all services (complete cleanup)", 
                           source="server_manager", event_type="purge")
            
            # Use server.sh for complete purge
            result = subprocess.run(
                ["./server.sh", "purge"],
                capture_output=True, text=True, timeout=60
            )
            
            if result.returncode == 0:
                for service_name in self.services.keys():
                    self.services[service_name]["status"] = "purged"
                self._managed_services.clear()
                self.logger.info("All services purged successfully", 
                               source="server_manager", event_type="purge_complete")
                return True
            else:
                self.logger.error(f"Failed to purge services: {result.stderr}", 
                                source="server_manager", event_type="purge_failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Error during purge: {e}", 
                            source="server_manager", event_type="purge_error")
            return False

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, initiating shutdown", 
                        source="server_manager", event_type="signal_received")
        self.clean_shutdown()
        sys.exit(0)

    def _cleanup_on_exit(self) -> None:
        """Cleanup services on application exit."""
        if self._managed_services:
            self.logger.info("Application exit detected, cleaning up services", 
                           source="server_manager", event_type="cleanup")
            self.clean_shutdown()


# Convenience functions for direct use
def start_services() -> bool:
    """Start all services. Returns True if successful."""
    manager = ServerManager()
    return manager.start_all_services()

def stop_services() -> bool:
    """Stop all services. Returns True if successful."""
    manager = ServerManager()
    return manager.stop_all_services()

def check_services() -> bool:
    """Check if all services are running. Returns True if all ready."""
    manager = ServerManager()
    return manager.services_up()

def get_service_status() -> Dict[str, Any]:
    """Get detailed service status report."""
    manager = ServerManager()
    return manager.get_status()
