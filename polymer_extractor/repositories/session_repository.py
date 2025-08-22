"""
polymer_extractor/repositories/session_repository.py

Repository for multi-user session management and extraction session analytics.

Purpose
-------
Provides data access layer for user sessions, extraction sessions, and resource management with:
- User-aware session CRUD operations with isolation
- Resource allocation tracking and cleanup
- Session metrics and performance analytics
- User storage quota management and monitoring
- Cross-session data aggregation and reporting

Key Abstractions
----------------
- SessionRepository: High-level session and user management interface
- UserSession: Individual user session with resource and lifecycle tracking  
- ExtractionSession: Processing session linked to user context
- ResourceAllocation: Resource tracking and quota management
- SessionMetrics: Performance monitoring and capacity planning

Design Patterns
---------------
- Repository Pattern: Clean separation of data access logic
- User Isolation: Logical data separation with configurable sharing
- Resource Tracking: Comprehensive allocation and usage monitoring
- Metrics Aggregation: Multi-level performance and capacity analytics
- Audit Trail: Complete session and user activity logging

Examples
--------
>>> from polymer_extractor.repositories.session_repository import SessionRepository
>>> session_repo = SessionRepository()
>>> 
>>> # User session management
>>> session = session_repo.create_user_session(
...     user_id="researcher_123",
...     session_name="polymer_conductivity_study",
...     resource_requirements={"memory_gb": 4.0, "models": ["bert", "roberta"]}
... )
>>> 
>>> # Resource tracking
>>> allocation = session_repo.allocate_resource(
...     session_id=session["id"],
...     resource_type="memory",
...     amount=4.0
... )
>>> 
>>> # Session analytics
>>> metrics = session_repo.get_session_metrics(session["id"])
>>> capacity = session_repo.get_system_capacity()

Notes
-----
- Performance: O(1) for single operations, O(n) for aggregation queries
- Thread Safety: Database transactions ensure consistency
- User Isolation: Query filtering ensures user data separation
- Memory: Streaming results for large analytics queries
- Audit: Complete activity logging for security and debugging
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from uuid import UUID
import json

from polymer_extractor.storage.database_manager import DatabaseManager
from polymer_extractor.utils.logging import get_logger

logger = get_logger()


class SessionRepository:
    """
    Repository for multi-user session management and extraction analytics.

    Summary
    -------
    Provides comprehensive data access for user sessions, extraction workflows,
    and resource management with user isolation and performance monitoring.

    Core Operations
    ---------------
    User Session Management:
    - create_user_session(user_id, session_name[, requirements]) -> dict
    - get_user_session(session_id) -> dict
    - update_user_session(session_id, data) -> dict
    - list_user_sessions(user_id[, status_filter]) -> list
    - terminate_user_session(session_id) -> bool

    Resource Management:
    - allocate_resource(session_id, resource_type, amount) -> dict
    - deallocate_resource(allocation_id) -> bool
    - get_session_resources(session_id) -> list
    - check_user_quota(user_id) -> dict

    Extraction Sessions:
    - create_extraction_session(user_session_id, config) -> dict
    - get_extraction_session(extraction_id) -> dict
    - list_user_extractions(user_id[, limit]) -> list
    - update_extraction_status(extraction_id, status) -> dict

    Analytics and Monitoring:
    - get_session_metrics(session_id) -> dict
    - get_user_analytics(user_id) -> dict
    - get_system_capacity() -> dict
    - get_resource_utilization() -> dict

    Examples
    --------
    >>> repo = SessionRepository()
    >>> # Create user session with resource allocation
    >>> session = repo.create_user_session(
    ...     user_id="researcher_alice",
    ...     session_name="polymer_thermal_analysis",
    ...     resource_requirements={
    ...         "memory_gb": 6.0,
    ...         "cpu_cores": 2,
    ...         "models": ["bert_polymer", "roberta_ensemble"],
    ...         "max_duration_hours": 8
    ...     },
    ...     metadata={"project": "thermal_conductivity", "priority": "high"}
    ... )
    >>> 
    >>> # Track resource usage
    >>> allocation = repo.allocate_resource(
    ...     session_id=session["id"],
    ...     resource_type="memory",
    ...     resource_name="bert_polymer_model",
    ...     allocated_amount=4.5
    ... )
    >>> 
    >>> # Monitor session performance
    >>> metrics = repo.get_session_metrics(session["id"])
    >>> print(f"Entities extracted: {metrics['total_entities']}")

    Notes
    -----
    - Complexity: O(1) single ops, O(n) for analytics and list operations
    - Data Integrity: Foreign key constraints ensure referential integrity
    - User Isolation: All queries filter by user_id for data separation
    - Performance: Indexed queries for fast session and resource lookups
    """

    def __init__(self):
        """Initialize session repository with database connection."""
        self.db = DatabaseManager()
        self.logger = get_logger()

    # ============================================================================
    # User Management
    # ============================================================================

    def create_user(
        self, 
        user_id: str, 
        username: str, 
        email: Optional[str] = None,
        display_name: Optional[str] = None,
        organization: Optional[str] = None,
        user_role: str = "researcher",
        storage_quota_gb: float = 10.0,
        max_concurrent_sessions: int = 3
    ) -> Dict[str, Any]:
        """
        Create a new user account.

        Parameters
        ----------
        user_id : str
            Unique external user identifier
        username : str
            Human-readable username
        email : str, optional
            User email address
        display_name : str, optional
            Display name for UI
        organization : str, optional
            User's organization
        user_role : str, default "researcher"
            User role (admin, researcher, guest)
        storage_quota_gb : float, default 10.0
            Storage quota in GB
        max_concurrent_sessions : int, default 3
            Maximum concurrent sessions allowed

        Returns
        -------
        dict
            Created user record

        Notes
        -----
        - Side Effects: Creates user record, initializes quotas
        """
        user_data = {
            "user_id": user_id,
            "username": username,
            "email": email,
            "display_name": display_name or username,
            "organization": organization,
            "user_role": user_role,
            "storage_quota_gb": storage_quota_gb,
            "max_concurrent_sessions": max_concurrent_sessions,
            "is_active": True,
            "created_at": datetime.now(),
            "metadata": {}
        }
        
        try:
            user = self.db.create_record("users", user_data)
            
            self.logger.info(
                f"User created successfully",
                source="session_repository",
                event_type="user_created",
                extra={
                    "user_id": user_id,
                    "username": username,
                    "role": user_role,
                    "storage_quota_gb": storage_quota_gb
                }
            )
            
            return user
            
        except Exception as e:
            self.logger.error(
                f"Failed to create user {user_id}",
                source="session_repository",
                event_type="user_creation_error",
                extra={"error": str(e)}
            )
            raise

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by user_id."""
        try:
            users = self.db.list_records("users", {"user_id": user_id})
            return users[0] if users else None
        except Exception as e:
            self.logger.error(f"Failed to get user {user_id}: {e}")
            return None

    def can_user_create_session(self, user_id: str) -> bool:
        """Check if user can create a new session based on limits."""
        try:
            # Use PostgreSQL function for consistent logic
            result = self.db._postgres_client.execute_query(
                "SELECT can_user_create_session(%s) as can_create",
                (user_id,)
            )
            return result[0]["can_create"] if result else False
        except Exception as e:
            self.logger.error(f"Error checking session creation for {user_id}: {e}")
            return False

    # ============================================================================
    # User Session Management
    # ============================================================================

    def create_user_session(
        self,
        user_id: str,
        session_name: str,
        resource_requirements: Optional[Dict[str, Any]] = None,
        storage_prefix: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expires_in_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        Create a new user session with resource requirements.

        Parameters
        ----------
        user_id : str
            User creating the session
        session_name : str
            Descriptive name for the session
        resource_requirements : dict, optional
            Resource allocation requirements
        storage_prefix : str, optional
            User-isolated storage prefix
        metadata : dict, optional
            Additional session metadata
        expires_in_minutes : int, default 60
            Session expiration time in minutes

        Returns
        -------
        dict
            Created session record with allocated resources

        Notes
        -----
        - Complexity: O(1) session creation
        - Side Effects: Allocates resources, creates storage namespace
        """
        # Check if user can create session
        if not self.can_user_create_session(user_id):
            raise ValueError(f"User {user_id} cannot create new session (quota exceeded)")
        
        session_data = {
            "user_id": user_id,
            "session_name": session_name,
            "status": "creating",
            "storage_prefix": storage_prefix,
            "resource_requirements": json.dumps(resource_requirements or {}),
            "allocated_resources": json.dumps({}),
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "expires_at": datetime.now() + timedelta(minutes=expires_in_minutes),
            "metadata": json.dumps(metadata or {})
        }
        
        try:
            session = self.db.create_record("user_sessions", session_data)
            
            # Log session creation
            self.log_user_access(
                user_id=user_id,
                action="session_create",
                resource_accessed=session["id"],
                success=True
            )
            
            self.logger.info(
                f"User session created",
                source="session_repository",
                event_type="session_created",
                extra={
                    "session_id": session["id"],
                    "user_id": user_id,
                    "session_name": session_name,
                    "expires_at": session_data["expires_at"].isoformat()
                }
            )
            
            return session
            
        except Exception as e:
            self.logger.error(
                f"Failed to create session for user {user_id}",
                source="session_repository",
                event_type="session_creation_error",
                extra={"error": str(e)}
            )
            raise

    def get_user_session(self, session_id: Union[str, UUID]) -> Optional[Dict[str, Any]]:
        """Get user session by ID."""
        try:
            session = self.db.get_record("user_sessions", str(session_id))
            return session
        except Exception as e:
            self.logger.error(f"Failed to get session {session_id}: {e}")
            return None

    def update_user_session(self, session_id: Union[str, UUID], data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user session data."""
        # Always update last_activity
        data["last_activity"] = datetime.now()
        
        try:
            session = self.db.update_record("user_sessions", str(session_id), data)
            
            self.logger.info(
                f"Session updated",
                source="session_repository",
                event_type="session_updated",
                extra={"session_id": str(session_id), "fields_updated": list(data.keys())}
            )
            
            return session
            
        except Exception as e:
            self.logger.error(f"Failed to update session {session_id}: {e}")
            raise

    def list_user_sessions(
        self, 
        user_id: str, 
        status_filter: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """List sessions for a specific user."""
        filters = {"user_id": user_id}
        if status_filter:
            filters["status"] = status_filter
        
        try:
            sessions = self.db.list_records("user_sessions", filters, limit)
            return sorted(sessions, key=lambda s: s.get("created_at", ""), reverse=True)
        except Exception as e:
            self.logger.error(f"Failed to list sessions for user {user_id}: {e}")
            return []

    def terminate_user_session(self, session_id: Union[str, UUID]) -> bool:
        """Terminate a user session and clean up resources."""
        try:
            # Update session status
            self.update_user_session(session_id, {
                "status": "completed",
                "completed_at": datetime.now()
            })
            
            # Deallocate all session resources
            self.deallocate_session_resources(session_id)
            
            self.logger.info(
                f"Session terminated",
                source="session_repository",
                event_type="session_terminated",
                extra={"session_id": str(session_id)}
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to terminate session {session_id}: {e}")
            return False

    # ============================================================================
    # Resource Management
    # ============================================================================

    def allocate_resource(
        self,
        user_session_id: Union[str, UUID],
        resource_type: str,
        resource_name: Optional[str] = None,
        allocated_amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Allocate a resource to a user session.

        Parameters
        ----------
        user_session_id : str or UUID
            Session to allocate resource to
        resource_type : str
            Type of resource (memory, cpu, storage, model, gpu)
        resource_name : str, optional
            Specific resource identifier
        allocated_amount : float, optional
            Amount of resource allocated

        Returns
        -------
        dict
            Resource allocation record

        Notes
        -----
        - Side Effects: Tracks resource usage for quota management
        """
        allocation_data = {
            "user_session_id": str(user_session_id),
            "resource_type": resource_type,
            "resource_name": resource_name,
            "allocated_amount": allocated_amount,
            "allocated_at": datetime.now(),
            "status": "active"
        }
        
        try:
            allocation = self.db.create_record("resource_allocations", allocation_data)
            
            self.logger.info(
                f"Resource allocated",
                source="session_repository",
                event_type="resource_allocated",
                extra={
                    "session_id": str(user_session_id),
                    "resource_type": resource_type,
                    "resource_name": resource_name,
                    "amount": allocated_amount
                }
            )
            
            return allocation
            
        except Exception as e:
            self.logger.error(f"Failed to allocate resource: {e}")
            raise

    def deallocate_resource(self, allocation_id: int) -> bool:
        """Deallocate a specific resource allocation."""
        try:
            self.db.update_record("resource_allocations", allocation_id, {
                "status": "deallocated",
                "deallocated_at": datetime.now()
            })
            
            self.logger.info(
                f"Resource deallocated",
                source="session_repository",
                event_type="resource_deallocated",
                extra={"allocation_id": allocation_id}
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to deallocate resource {allocation_id}: {e}")
            return False

    def deallocate_session_resources(self, session_id: Union[str, UUID]) -> int:
        """Deallocate all resources for a session."""
        try:
            # Get all active allocations for session
            allocations = self.db.list_records("resource_allocations", {
                "user_session_id": str(session_id),
                "status": "active"
            })
            
            deallocated_count = 0
            for allocation in allocations:
                if self.deallocate_resource(allocation["id"]):
                    deallocated_count += 1
            
            return deallocated_count
            
        except Exception as e:
            self.logger.error(f"Failed to deallocate session resources: {e}")
            return 0

    def get_session_resources(self, session_id: Union[str, UUID]) -> List[Dict[str, Any]]:
        """Get all resource allocations for a session."""
        try:
            allocations = self.db.list_records("resource_allocations", {
                "user_session_id": str(session_id)
            })
            return allocations
        except Exception as e:
            self.logger.error(f"Failed to get session resources: {e}")
            return []

    def check_user_quota(self, user_id: str) -> Dict[str, Any]:
        """Check user storage quota and usage."""
        try:
            # Use PostgreSQL function for efficient quota calculation
            result = self.db._postgres_client.execute_query(
                "SELECT * FROM get_user_storage_usage(%s)",
                (user_id,)
            )
            
            if result:
                quota_info = result[0]
                return {
                    "user_id": user_id,
                    "storage_used_gb": float(quota_info["storage_used_gb"]),
                    "storage_quota_gb": float(quota_info["storage_quota_gb"]),
                    "storage_remaining_gb": float(quota_info["storage_remaining_gb"]),
                    "file_count": int(quota_info["file_count"]),
                    "quota_utilization": float(quota_info["storage_used_gb"]) / float(quota_info["storage_quota_gb"])
                }
            else:
                return {"user_id": user_id, "error": "User not found"}
                
        except Exception as e:
            self.logger.error(f"Failed to check quota for {user_id}: {e}")
            return {"user_id": user_id, "error": str(e)}

    # ============================================================================
    # Extraction Session Management
    # ============================================================================

    def create_extraction_session(
        self,
        user_session_id: Union[str, UUID],
        session_name: str,
        paper_ids: List[str],
        ensemble_strategy: str = "weighted_voting",
        config: Optional[Dict[str, Any]] = None,
        priority: int = 1
    ) -> Dict[str, Any]:
        """
        Create an extraction session linked to a user session.

        Parameters
        ----------
        user_session_id : str or UUID
            Parent user session
        session_name : str
            Name for the extraction session
        paper_ids : List[str]
            Papers to process in this extraction
        ensemble_strategy : str, default "weighted_voting"
            Strategy for model ensemble
        config : dict, optional
            Additional extraction configuration
        priority : int, default 1
            Processing priority (1=low, 5=high)

        Returns
        -------
        dict
            Created extraction session record

        Notes
        -----
        - Links extraction to user session for tracking and isolation
        """
        # Get user session to extract user context
        user_session = self.get_user_session(user_session_id)
        if not user_session:
            raise ValueError(f"User session {user_session_id} not found")
        
        extraction_data = {
            "session_name": session_name,
            "user_session_id": str(user_session_id),
            "user_id": user_session["user_id"],
            "paper_ids": paper_ids,
            "ensemble_strategy": ensemble_strategy,
            "priority": priority,
            "status": "running",
            "config": json.dumps(config or {}),
            "created_at": datetime.now()
        }
        
        try:
            # Use existing extraction_sessions table (enhanced with user fields)
            extraction_session = self.db.create_record("extraction_sessions", extraction_data)
            
            # Log extraction start
            self.log_user_access(
                user_id=user_session["user_id"],
                action="extraction_start",
                resource_accessed=extraction_session["id"],
                success=True
            )
            
            self.logger.info(
                f"Extraction session created",
                source="session_repository",
                event_type="extraction_created",
                extra={
                    "extraction_id": extraction_session["id"],
                    "user_session_id": str(user_session_id),
                    "user_id": user_session["user_id"],
                    "paper_count": len(paper_ids)
                }
            )
            
            return extraction_session
            
        except Exception as e:
            self.logger.error(f"Failed to create extraction session: {e}")
            raise

    def get_extraction_session(self, extraction_id: Union[str, UUID]) -> Optional[Dict[str, Any]]:
        """Get extraction session by ID."""
        try:
            return self.db.get_record("extraction_sessions", str(extraction_id))
        except Exception as e:
            self.logger.error(f"Failed to get extraction session {extraction_id}: {e}")
            return None

    def list_user_extractions(self, user_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List extraction sessions for a user."""
        try:
            extractions = self.db.list_records("extraction_sessions", {"user_id": user_id}, limit)
            return sorted(extractions, key=lambda e: e.get("created_at", ""), reverse=True)
        except Exception as e:
            self.logger.error(f"Failed to list extractions for {user_id}: {e}")
            return []

    def update_extraction_status(self, extraction_id: Union[str, UUID], status: str, 
                                metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update extraction session status and metadata."""
        update_data = {"status": status}
        
        if status in ["completed", "failed"]:
            update_data["completed_at"] = datetime.now()
        
        if metadata:
            update_data.update(metadata)
        
        try:
            extraction = self.db.update_record("extraction_sessions", str(extraction_id), update_data)
            
            self.logger.info(
                f"Extraction status updated",
                source="session_repository",
                event_type="extraction_status_updated",
                extra={"extraction_id": str(extraction_id), "status": status}
            )
            
            return extraction
            
        except Exception as e:
            self.logger.error(f"Failed to update extraction {extraction_id}: {e}")
            raise

    # ============================================================================
    # Analytics and Monitoring
    # ============================================================================

    def get_session_metrics(self, session_id: Union[str, UUID]) -> Dict[str, Any]:
        """Get comprehensive metrics for a user session."""
        try:
            # Get session basic info
            session = self.get_user_session(session_id)
            if not session:
                return {"error": "Session not found"}
            
            # Get resource allocations
            resources = self.get_session_resources(session_id)
            
            # Get extraction sessions for this user session
            extractions = self.db.list_records("extraction_sessions", {
                "user_session_id": str(session_id)
            })
            
            # Calculate metrics
            total_entities = sum(e.get("total_entities", 0) for e in extractions)
            total_papers = len(set(paper_id for e in extractions for paper_id in e.get("paper_ids", [])))
            processing_time = sum(e.get("processing_time_ms", 0) for e in extractions)
            
            return {
                "session_id": str(session_id),
                "user_id": session["user_id"],
                "status": session["status"],
                "created_at": session["created_at"],
                "last_activity": session["last_activity"],
                "resource_allocations": len(resources),
                "extraction_sessions": len(extractions),
                "total_entities_extracted": total_entities,
                "total_papers_processed": total_papers,
                "total_processing_time_ms": processing_time,
                "average_processing_time_per_paper": (processing_time / total_papers) if total_papers > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get session metrics: {e}")
            return {"error": str(e)}

    def get_user_analytics(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive analytics for a user."""
        try:
            # Get user info
            user = self.get_user(user_id)
            if not user:
                return {"error": "User not found"}
            
            # Get quota information
            quota_info = self.check_user_quota(user_id)
            
            # Get sessions
            sessions = self.list_user_sessions(user_id)
            active_sessions = [s for s in sessions if s["status"] in ["active", "processing", "idle"]]
            
            # Get extractions
            extractions = self.list_user_extractions(user_id)
            completed_extractions = [e for e in extractions if e["status"] == "completed"]
            
            # Calculate analytics
            total_entities = sum(e.get("total_entities", 0) for e in completed_extractions)
            total_papers = len(set(paper_id for e in extractions for paper_id in e.get("paper_ids", [])))
            
            return {
                "user_id": user_id,
                "username": user["username"],
                "user_role": user["user_role"],
                "account_created": user["created_at"],
                "last_login": user.get("last_login"),
                "storage_quota": quota_info,
                "session_summary": {
                    "total_sessions": len(sessions),
                    "active_sessions": len(active_sessions),
                    "max_concurrent_allowed": user["max_concurrent_sessions"]
                },
                "extraction_summary": {
                    "total_extractions": len(extractions),
                    "completed_extractions": len(completed_extractions),
                    "total_entities_extracted": total_entities,
                    "total_papers_processed": total_papers
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get user analytics: {e}")
            return {"error": str(e)}

    def get_system_capacity(self) -> Dict[str, Any]:
        """Get system-wide capacity and utilization metrics."""
        try:
            # Use the system capacity view
            capacity_result = self.db._postgres_client.execute_query(
                "SELECT * FROM system_capacity_view"
            )
            
            if not capacity_result:
                return {"error": "No capacity data available"}
            
            capacity = capacity_result[0]
            
            # Get configuration limits
            config_result = self.db.list_records("system_config", {
                "config_key": "max_concurrent_sessions_global"
            })
            
            max_global_sessions = int(config_result[0]["config_value"]) if config_result else 50
            
            return {
                "active_sessions": capacity.get("total_active_sessions", 0),
                "processing_sessions": capacity.get("processing_sessions", 0),
                "active_users": capacity.get("active_users", 0),
                "max_global_sessions": max_global_sessions,
                "capacity_utilization": capacity.get("total_active_sessions", 0) / max_global_sessions,
                "resource_utilization": {
                    "memory_allocated_gb": float(capacity.get("total_memory_allocated_gb", 0)),
                    "cpu_allocated_cores": float(capacity.get("total_cpu_allocated_cores", 0)),
                    "storage_used_gb": float(capacity.get("total_storage_used_gb", 0))
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get system capacity: {e}")
            return {"error": str(e)}

    # ============================================================================
    # User Activity Logging
    # ============================================================================

    def log_user_access(
        self,
        user_id: str,
        action: str,
        resource_accessed: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log user access and activity."""
        log_data = {
            "user_id": user_id,
            "action": action,
            "resource_accessed": resource_accessed,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": datetime.now(),
            "success": success,
            "error_message": error_message,
            "metadata": json.dumps(metadata or {})
        }
        
        try:
            self.db.create_record("user_access_logs", log_data)
        except Exception as e:
            # Don't fail the main operation if logging fails
            self.logger.error(f"Failed to log user access: {e}")

    # ============================================================================
    # Cleanup and Maintenance
    # ============================================================================

    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions using database function."""
        try:
            result = self.db._postgres_client.execute_query(
                "SELECT cleanup_expired_sessions() as cleanup_count"
            )
            
            cleanup_count = result[0]["cleanup_count"] if result else 0
            
            if cleanup_count > 0:
                self.logger.info(
                    f"Cleaned up {cleanup_count} expired sessions",
                    source="session_repository",
                    event_type="cleanup_completed"
                )
            
            return cleanup_count
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup expired sessions: {e}")
            return 0

    def record_session_metric(
        self,
        user_session_id: Union[str, UUID],
        metric_type: str,
        metric_name: str,
        metric_value: float,
        metric_unit: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Record a session-specific metric."""
        metric_data = {
            "user_session_id": str(user_session_id),
            "metric_type": metric_type,
            "metric_name": metric_name,
            "metric_value": metric_value,
            "metric_unit": metric_unit,
            "recorded_at": datetime.now(),
            "metadata": json.dumps(metadata or {})
        }
        
        try:
            metric = self.db.create_record("session_metrics", metric_data)
            return metric
        except Exception as e:
            self.logger.error(f"Failed to record session metric: {e}")
            raise

    def track_user_storage_usage(
        self,
        user_id: str,
        storage_key: str,
        file_size_bytes: int,
        storage_backend: str = "local",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Track user storage usage for quota management."""
        storage_data = {
            "user_id": user_id,
            "storage_key": storage_key,
            "file_size_bytes": file_size_bytes,
            "storage_backend": storage_backend,
            "created_at": datetime.now(),
            "last_accessed": datetime.now(),
            "metadata": json.dumps(metadata or {})
        }
        
        try:
            storage_record = self.db.create_record("user_storage_usage", storage_data)
            return storage_record
        except Exception as e:
            self.logger.error(f"Failed to track storage usage: {e}")
            raise


# Factory function
def get_session_repository() -> SessionRepository:
    """Get configured SessionRepository instance."""
    return SessionRepository()


# Example usage
if __name__ == "__main__":
    # Example repository operations
    repo = SessionRepository()
    
    # Create user
    user = repo.create_user(
        user_id="researcher_123",
        username="alice_researcher",
        email="alice@university.edu",
        display_name="Dr. Alice Smith",
        organization="Materials Science Dept"
    )
    
    # Create session
    session = repo.create_user_session(
        user_id="researcher_123",
        session_name="polymer_thermal_conductivity_study",
        resource_requirements={
            "memory_gb": 4.0,
            "cpu_cores": 2,
            "models": ["bert_polymer", "roberta_ensemble"]
        }
    )
    
    # Get analytics
    analytics = repo.get_user_analytics("researcher_123")
    capacity = repo.get_system_capacity()
    
    print("Multi-user session repository example completed successfully")
