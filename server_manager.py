# polymer_extractor/services/server_manager.py

"""
Server Manager for Polymer NLP Extractor.

Purpose
-------
Manages the lifecycle of external services (PostgreSQL, Neo4j, Grobid) to ensure:
- Proper startup sequence
- Safe shutdown to prevent data corruption
- Health monitoring and status reporting
- Graceful cleanup on application exit

This manager handles the three critical external services:
1. PostgreSQL - Database server
2. Neo4j - Graph database server  
3. Grobid - Document processing service

The manager ensures these services are running when needed and properly
stopped during application shutdown to prevent any data corruption.
"""

import asyncio
import atexit
import json
import os
import signal
import subprocess
import sys
import time
import psutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from dotenv import load_dotenv

from polymer_extractor.utils.logging import get_logger

# Load environment variables
load_dotenv()


class ServerManager:
    """
    Manages external service lifecycle for safe database operations.
    
    Responsibilities:
    - Start/stop PostgreSQL, Neo4j, and Grobid services
    - Monitor service health and availability
    - Ensure graceful shutdown to prevent corruption
    - Provide status reporting for debugging
    """
    
    def __init__(self):
        self.logger = get_logger()
        
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
                "docker_compose_service": "postgres"
            },
            "neo4j": {
                "status": "unknown", 
                "pid": None, 
                "port": neo4j_port,
                "http_port": neo4j_http_port,
                "name": "Neo4j", 
                "docker_compose_service": "neo4j"
            },
            "grobid": {
                "status": "unknown", 
                "pid": None, 
                "port": grobid_port,
                "name": "GROBID",
                "docker_compose_service": "grobid"
            }
        }
        
        # Track process IDs for cleanup
        self._tracked_pids = set()
        
        # Register cleanup handlers
        atexit.register(self._cleanup_on_exit)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info(f"ServerManager initialized with ports: PostgreSQL:{postgres_port}, Neo4j:{neo4j_port}, GROBID:{grobid_port}", 
                        source="server_manager", event_type="initialization")
        self.logger.info(f"Configuration: startup_timeout={self.startup_timeout}s, shutdown_timeout={self.shutdown_timeout}s, auto_restart={self.auto_restart}",
                        source="server_manager", event_type="initialization")
    
    def _signal_handler(self, signum, frame):
        """Handle interrupt signals with graceful cleanup."""
        self.logger.warning(f"Received signal {signum}, initiating graceful shutdown...", 
                           source="server_manager", event_type="signal_handler")
        print("\n🛑 CLEANING UP (stopping servers), please wait - DO NOT INTERRUPT!")
        self.stop_all_services()
        sys.exit(0)
    
    def _cleanup_on_exit(self):
        """Cleanup function called on normal exit."""
        print("🛑 CLEANING UP (stopping servers), please wait - DO NOT INTERRUPT!")
        self.stop_all_services()
    
    def check_service_running(self, service_name: str) -> bool:
        """
        Check if a service is currently running.
        
        Parameters
        ----------
        service_name : str
            Name of service ('postgresql', 'neo4j', 'grobid')
            
        Returns
        -------
        bool
            True if service is running and responsive
        """
        if service_name not in self.services:
            return False
            
        service_info = self.services[service_name]
        port = service_info["port"]
        
        try:
            # Check if port is listening
            result = subprocess.run(
                ["netstat", "-tuln"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            
            if result.returncode == 0:
                listening = f":{port}" in result.stdout
                self.services[service_name]["status"] = "running" if listening else "stopped"
                return listening
            else:
                self.services[service_name]["status"] = "unknown"
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to check {service_name} status: {e}", 
                            source="server_manager", event_type="health_check")
            self.services[service_name]["status"] = "error"
            return False
    
    def start_postgresql(self) -> Dict[str, Any]:
        """
        Start PostgreSQL service if not running.
        
        Returns
        -------
        Dict[str, Any]
            Status of PostgreSQL startup attempt
        """
        result = {
            "service": "postgresql",
            "success": False,
            "message": "",
            "timestamp": datetime.now().isoformat() + "Z"
        }
        
        try:
            if self.check_service_running("postgresql"):
                result["success"] = True
                result["message"] = "PostgreSQL already running"
                return result
            
            self.logger.info("Starting PostgreSQL service...", 
                           source="server_manager", event_type="start_service")
            
            # Try common PostgreSQL startup commands
            start_commands = [
                ["sudo", "systemctl", "start", "postgresql"],
                ["brew", "services", "start", "postgresql"],  # macOS
                ["pg_ctl", "start", "-D", "/usr/local/var/postgres"]  # Direct start
            ]
            
            for cmd in start_commands:
                try:
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if proc.returncode == 0:
                        # Wait for service to be ready
                        for _ in range(10):
                            if self.check_service_running("postgresql"):
                                result["success"] = True
                                result["message"] = f"PostgreSQL started successfully with: {' '.join(cmd)}"
                                self.logger.info(result["message"], 
                                               source="server_manager", event_type="start_service")
                                return result
                            time.sleep(1)
                        break
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue
            
            result["message"] = "Failed to start PostgreSQL with any known method"
            
        except Exception as e:
            result["message"] = f"PostgreSQL startup error: {e}"
            self.logger.error(result["message"], source="server_manager", event_type="start_service")
        
        return result
    
    def start_neo4j(self) -> Dict[str, Any]:
        """
        Start Neo4j service if not running.
        
        Returns
        -------
        Dict[str, Any]
            Status of Neo4j startup attempt
        """
        result = {
            "service": "neo4j",
            "success": False,
            "message": "",
            "timestamp": datetime.now().isoformat() + "Z"
        }
        
        try:
            if self.check_service_running("neo4j"):
                result["success"] = True
                result["message"] = "Neo4j already running"
                return result
            
            self.logger.info("Starting Neo4j service...", 
                           source="server_manager", event_type="start_service")
            
            # Try common Neo4j startup commands
            start_commands = [
                ["sudo", "systemctl", "start", "neo4j"],
                ["brew", "services", "start", "neo4j"],  # macOS
                ["neo4j", "start"],  # Direct start
                ["/usr/share/neo4j/bin/neo4j", "start"]  # Ubuntu path
            ]
            
            for cmd in start_commands:
                try:
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if proc.returncode == 0:
                        # Wait for service to be ready
                        for _ in range(15):  # Neo4j takes longer to start
                            if self.check_service_running("neo4j"):
                                result["success"] = True
                                result["message"] = f"Neo4j started successfully with: {' '.join(cmd)}"
                                self.logger.info(result["message"], 
                                               source="server_manager", event_type="start_service")
                                return result
                            time.sleep(2)
                        break
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue
            
            result["message"] = "Failed to start Neo4j with any known method"
            
        except Exception as e:
            result["message"] = f"Neo4j startup error: {e}"
            self.logger.error(result["message"], source="server_manager", event_type="start_service")
        
        return result
    
    def start_grobid(self) -> Dict[str, Any]:
        """
        Start Grobid service if not running.
        
        Returns
        -------
        Dict[str, Any]
            Status of Grobid startup attempt
        """
        result = {
            "service": "grobid",
            "success": False,
            "message": "",
            "timestamp": datetime.now().isoformat() + "Z"
        }
        
        try:
            if self.check_service_running("grobid"):
                result["success"] = True
                result["message"] = "Grobid already running"
                return result
            
            self.logger.info("Starting Grobid service...", 
                           source="server_manager", event_type="start_service")
            
            # Look for Grobid installation, starting with environment variable
            grobid_paths = []
            
            # Check if GROBID_PATH is set in environment
            env_grobid_path = os.getenv("GROBID_PATH")
            if env_grobid_path:
                grobid_paths.append(env_grobid_path)
            
            # Add default search paths
            grobid_paths.extend([
                "./workspace/grobid-0.8.2",
                "/opt/grobid",
                os.path.expanduser("~/grobid"),
                os.path.expanduser("~/grobid-0.8.2")
            ])
            
            grobid_path = None
            for path in grobid_paths:
                if os.path.exists(os.path.join(path, "gradlew")):
                    grobid_path = path
                    self.logger.info(f"Found Grobid installation at: {path}", 
                                   source="server_manager", event_type="start_service")
                    break
            
            if not grobid_path:
                result["message"] = f"Grobid installation not found. Searched paths: {grobid_paths}. Set GROBID_PATH environment variable to specify custom location."
                return result
            
            # Start Grobid
            try:
                cmd = ["./gradlew", "run"]
                proc = subprocess.Popen(
                    cmd,
                    cwd=grobid_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )
                
                self.services["grobid"]["pid"] = proc.pid
                
                # Wait for service to be ready
                for _ in range(30):  # Grobid takes time to start
                    if self.check_service_running("grobid"):
                        result["success"] = True
                        result["message"] = f"Grobid started successfully (PID: {proc.pid})"
                        self.logger.info(result["message"], 
                                       source="server_manager", event_type="start_service")
                        return result
                    time.sleep(2)
                
                result["message"] = "Grobid process started but not responding on port 8070"
                
            except Exception as e:
                result["message"] = f"Failed to start Grobid: {e}"
            
        except Exception as e:
            result["message"] = f"Grobid startup error: {e}"
            self.logger.error(result["message"], source="server_manager", event_type="start_service")
        
        return result
    
    def stop_service(self, service_name: str) -> Dict[str, Any]:
        """
        Stop a specific service.
        
        Parameters
        ----------
        service_name : str
            Name of service to stop
            
        Returns
        -------
        Dict[str, Any]
            Status of stop operation
        """
        result = {
            "service": service_name,
            "success": False,
            "message": "",
            "timestamp": datetime.now().isoformat() + "Z"
        }
        
        try:
            if service_name == "postgresql":
                stop_commands = [
                    ["sudo", "systemctl", "stop", "postgresql"],
                    ["brew", "services", "stop", "postgresql"],
                    ["pg_ctl", "stop", "-D", "/usr/local/var/postgres"]
                ]
            elif service_name == "neo4j":
                stop_commands = [
                    ["sudo", "systemctl", "stop", "neo4j"],
                    ["brew", "services", "stop", "neo4j"],
                    ["neo4j", "stop"],
                    ["/usr/share/neo4j/bin/neo4j", "stop"]
                ]
            elif service_name == "grobid":
                # Handle Grobid specially since it might be a process we started
                service_info = self.services.get("grobid", {})
                pid = service_info.get("pid")
                if pid:
                    try:
                        os.kill(pid, signal.SIGTERM)
                        time.sleep(2)
                        os.kill(pid, signal.SIGKILL)  # Force kill if still running
                        result["success"] = True
                        result["message"] = f"Grobid process {pid} stopped"
                        return result
                    except ProcessLookupError:
                        result["success"] = True
                        result["message"] = "Grobid process was already stopped"
                        return result
                
                stop_commands = [
                    ["pkill", "-f", "grobid"],
                    ["killall", "java"]  # Last resort
                ]
            else:
                result["message"] = f"Unknown service: {service_name}"
                return result
            
            for cmd in stop_commands:
                try:
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    if proc.returncode == 0:
                        result["success"] = True
                        result["message"] = f"{service_name} stopped successfully"
                        self.services[service_name]["status"] = "stopped"
                        return result
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue
            
            result["message"] = f"Failed to stop {service_name} with any known method"
            
        except Exception as e:
            result["message"] = f"Error stopping {service_name}: {e}"
            self.logger.error(result["message"], source="server_manager", event_type="stop_service")
        
        return result
    
    def stop_all_services(self) -> Dict[str, Any]:
        """
        Stop all managed services in safe order.
        
        Returns
        -------
        Dict[str, Any]
            Summary of stop operations
        """
        result = {
            "operation": "stop_all_services",
            "services": {},
            "timestamp": datetime.now().isoformat() + "Z"
        }
        
        # Stop in reverse dependency order: Grobid, Neo4j, PostgreSQL
        services_order = ["grobid", "neo4j", "postgresql"]
        
        for service_name in services_order:
            print(f"🛑 Stopping {service_name}...")
            stop_result = self.stop_service(service_name)
            result["services"][service_name] = stop_result
            
            if stop_result["success"]:
                print(f"✅ {service_name} stopped safely")
            else:
                print(f"⚠️  {service_name} stop issue: {stop_result['message']}")
        
        self.logger.info("All services stop attempt completed", 
                        source="server_manager", event_type="stop_all")
        print("✅ Cleanup completed")
        
        return result
    
    def start_all_services(self) -> Dict[str, Any]:
        """
        Start all required services in correct order.
        
        Returns
        -------
        Dict[str, Any]
            Summary of startup operations
        """
        result = {
            "operation": "start_all_services",
            "services": {},
            "timestamp": datetime.now().isoformat() + "Z"
        }
        
        # Start in dependency order: PostgreSQL, Neo4j, Grobid
        services_order = ["postgresql", "neo4j", "grobid"]
        
        for service_name in services_order:
            if service_name == "postgresql":
                start_result = self.start_postgresql()
            elif service_name == "neo4j":
                start_result = self.start_neo4j()
            elif service_name == "grobid":
                start_result = self.start_grobid()
            
            result["services"][service_name] = start_result
            
            if not start_result["success"]:
                self.logger.error(f"Failed to start {service_name}: {start_result['message']}", 
                                source="server_manager", event_type="start_all")
        
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of all services.
        
        Returns
        -------
        Dict[str, Any]
            Current status of all managed services
        """
        # Refresh status for all services
        for service_name in self.services.keys():
            self.check_service_running(service_name)
        
        return {
            "operation": "get_status",
            "services": self.services.copy(),
            "timestamp": datetime.now().isoformat() + "Z"
        }

    # === ENHANCED PORT MANAGEMENT AND CLEANUP ===
    
    def free_all_ports(self) -> Dict[str, Any]:
        """
        Free all ports used by managed services.
        
        Returns
        -------
        Dict[str, Any]
            Summary of port cleanup operations
        """
        result = {
            "operation": "free_all_ports",
            "ports_freed": [],
            "errors": [],
            "timestamp": datetime.now().isoformat() + "Z"
        }
        
        for service_name, service_info in self.services.items():
            try:
                port = service_info["port"]
                if self._free_port(port):
                    result["ports_freed"].append({"service": service_name, "port": port})
                    self.logger.info(f"Freed port {port} for {service_name}", 
                                   source="server_manager", event_type="free_port")
                
                # Also free HTTP port for Neo4j
                if service_name == "neo4j" and "http_port" in service_info:
                    http_port = service_info["http_port"]
                    if self._free_port(http_port):
                        result["ports_freed"].append({"service": f"{service_name}_http", "port": http_port})
                        
            except Exception as e:
                error_msg = f"Failed to free port for {service_name}: {str(e)}"
                result["errors"].append(error_msg)
                self.logger.error(error_msg, source="server_manager", event_type="free_port")
        
        return result
    
    def _free_port(self, port: int) -> bool:
        """
        Free a specific port by killing processes using it.
        
        Parameters
        ----------
        port : int
            Port number to free
            
        Returns
        -------
        bool
            True if port was freed successfully
        """
        try:
            # Find processes using the port
            for proc in psutil.process_iter(['pid', 'name', 'connections']):
                try:
                    for conn in proc.info['connections'] or []:
                        if conn.laddr.port == port:
                            proc.terminate()
                            self.logger.info(f"Terminated process {proc.info['pid']} ({proc.info['name']}) using port {port}",
                                           source="server_manager", event_type="free_port")
                            # Wait for graceful termination
                            try:
                                proc.wait(timeout=5)
                            except psutil.TimeoutExpired:
                                proc.kill()
                                self.logger.warning(f"Force killed process {proc.info['pid']} on port {port}",
                                                  source="server_manager", event_type="free_port")
                            return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return True
        except Exception as e:
            self.logger.error(f"Error freeing port {port}: {str(e)}", 
                            source="server_manager", event_type="free_port")
            return False
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get comprehensive status of all services with health checks.
        
        Returns
        -------
        Dict[str, Dict[str, Any]]
            Detailed status for each service
        """
        status = {}
        for service_name in self.services.keys():
            is_running = self.check_service_running(service_name)
            service_info = self.services[service_name].copy()
            service_info["is_running"] = is_running
            service_info["health_check_time"] = datetime.now().isoformat() + "Z"
            
            # Add port information
            if is_running:
                service_info["port_status"] = "listening"
            else:
                service_info["port_status"] = "not_listening"
            
            status[service_name] = service_info
        
        return status
    
    def emergency_cleanup(self) -> Dict[str, Any]:
        """
        Emergency cleanup method for force-stopping all services.
        
        Returns
        -------
        Dict[str, Any]
            Summary of emergency cleanup operations
        """
        result = {
            "operation": "emergency_cleanup",
            "actions": [],
            "timestamp": datetime.now().isoformat() + "Z"
        }
        
        self.logger.warning("Initiating emergency cleanup", 
                          source="server_manager", event_type="emergency_cleanup")
        
        # Stop all services
        stop_result = self.stop_all_services()
        result["actions"].append({"action": "stop_services", "result": stop_result})
        
        # Free all ports
        port_result = self.free_all_ports()
        result["actions"].append({"action": "free_ports", "result": port_result})
        
        # Kill tracked PIDs
        killed_pids = []
        for pid in self._tracked_pids.copy():
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except psutil.TimeoutExpired:
                    proc.kill()
                killed_pids.append(pid)
                self._tracked_pids.discard(pid)
            except psutil.NoSuchProcess:
                self._tracked_pids.discard(pid)
            except Exception as e:
                self.logger.error(f"Failed to kill PID {pid}: {str(e)}", 
                                source="server_manager", event_type="emergency_cleanup")
        
        if killed_pids:
            result["actions"].append({"action": "kill_tracked_pids", "pids": killed_pids})
        
        return result
    
    def restart_service(self, service_name: str) -> Dict[str, Any]:
        """
        Restart a specific service.
        
        Parameters
        ----------
        service_name : str
            Name of service to restart
            
        Returns
        -------
        Dict[str, Any]
            Result of restart operation
        """
        result = {
            "operation": "restart_service",
            "service": service_name,
            "timestamp": datetime.now().isoformat() + "Z"
        }
        
        # Stop the service
        stop_result = self.stop_service(service_name)
        result["stop_result"] = stop_result
        
        if stop_result["success"]:
            # Wait a moment for cleanup
            time.sleep(2)
            
            # Start the service
            if service_name == "postgresql":
                start_result = self.start_postgresql()
            elif service_name == "neo4j":
                start_result = self.start_neo4j()
            elif service_name == "grobid":
                start_result = self.start_grobid()
            else:
                start_result = {"success": False, "message": f"Unknown service: {service_name}"}
            
            result["start_result"] = start_result
            result["success"] = start_result["success"]
        else:
            result["success"] = False
            result["message"] = f"Failed to stop {service_name} for restart"
        
        return result
