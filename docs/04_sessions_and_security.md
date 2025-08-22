# 04. Sessions and Multi-User Security

## Overview

This section provides comprehensive guidance for implementing production-ready multi-user sessions and security for the Polymer NLP Extractor. The current implementation provides a **foundational session management system** that serves as the first step toward full production deployment. **This is not a complete authentication system** but rather the session and user management infrastructure that integrates with your chosen authentication provider.

## Current Implementation Status

### What's Implemented (Session Foundation)

The project includes a complete **session management framework** that handles:
- **User Session Creation and Lifecycle**: Full session orchestration with resource allocation
- **Multi-User Data Isolation**: User-specific storage prefixes and database filtering
- **Resource Management**: Quota tracking, concurrent session limits, and cleanup
- **Performance Monitoring**: Comprehensive session analytics and health monitoring
- **Production-Ready Architecture**: Scalable design supporting 50+ concurrent sessions

### What Requires Extension (Authentication Layer)

The current system creates users **without passwords or authentication**. This is intentional - the session management is designed to integrate with your chosen authentication system:

```python
# Current user creation (NO PASSWORD)
user = session_repo.create_user(
    user_id="researcher_123",         # External user ID from your auth system
    username="alice_researcher",      # Display username
    email="alice@university.edu",     # Contact information
    storage_quota_gb=50.0,            # Resource allocation
    max_concurrent_sessions=5         # Concurrency limits
)
```

## Authentication Integration Strategies

### Strategy 1: Separate Authentication Database

**Recommended for custom authentication requirements**

Create a dedicated authentication database alongside the session management:

```sql
-- Example auth schema (create as separate database)
-- File: db/sql/004_authentication.sql

CREATE DATABASE polymer_auth;

CREATE TABLE auth_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    salt VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE
);

CREATE TABLE auth_sessions (
    session_token VARCHAR(255) PRIMARY KEY,
    user_id UUID REFERENCES auth_users(id) ON DELETE CASCADE,
    expires_at TIMESTAMP NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Integration Flow**:
```python
# 1. User authenticates via your auth system
auth_user = authenticate_user(email, password)  # Your auth logic

# 2. Create session management user using auth user ID
session_user = session_repo.create_user(
    user_id=str(auth_user.id),           # Link to auth system
    username=auth_user.username,
    email=auth_user.email,
    storage_quota_gb=get_user_quota(auth_user),
    max_concurrent_sessions=get_session_limit(auth_user)
)

# 3. Create extraction session
session = session_manager.create_session(
    user_id=str(auth_user.id),           # Same ID as auth system
    session_name="polymer_analysis_project",
    resource_requirements=ResourceRequirements(models=["bert_polymer"])
)
```

### Strategy 2: External Authentication Service (Appwrite)

**Recommended for rapid deployment with managed authentication**

Integrate with Appwrite's or any other authentication handling service. In this documentation, we will focus on Appwrite:

```python
# Environment configuration for Appwrite auth
APPWRITE_AUTH_ENDPOINT=https://cloud.appwrite.io/v1 # Replace with your actual endpoint here
APPWRITE_AUTH_PROJECT_ID=your_project_id
APPWRITE_AUTH_API_KEY=your_auth_api_key

# Integration example
from appwrite.client import Client
from appwrite.services.account import Account

def authenticate_with_appwrite(email: str, password: str):
    client = Client()
    client.set_endpoint(APPWRITE_AUTH_ENDPOINT)
    client.set_project(APPWRITE_AUTH_PROJECT_ID)
    
    account = Account(client)
    session = account.create_email_session(email, password)
    
    # Get user info from Appwrite
    appwrite_user = account.get()
    
    # Create/update session management user
    session_user = session_repo.create_user(
        user_id=appwrite_user['$id'],          # Appwrite user ID
        username=appwrite_user.get('name', email),
        email=appwrite_user.get('email'),
        storage_quota_gb=calculate_quota(appwrite_user),
        max_concurrent_sessions=get_user_limits(appwrite_user)
    )
    
    return session_user, session['$id']        # Return session token
```

### Strategy 3: Extended Users Table

**For simple password-based authentication**

Extend the existing users table to include authentication fields:

```sql
-- Add authentication columns to existing users table
-- File: db/sql/003_user_authentication.sql

ALTER TABLE users ADD COLUMN password_hash VARCHAR(255);
ALTER TABLE users ADD COLUMN salt VARCHAR(255);
ALTER TABLE users ADD COLUMN last_login TIMESTAMP;
ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN account_locked_until TIMESTAMP;
ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN two_factor_enabled BOOLEAN DEFAULT FALSE;

-- Add authentication functions
CREATE OR REPLACE FUNCTION verify_password(
    p_email VARCHAR(255),
    p_password VARCHAR(255)
) RETURNS TABLE(user_id VARCHAR(255), is_valid BOOLEAN) AS $$
BEGIN
    -- Implementation for password verification
    -- (Add your password hashing logic here)
END;
$$ LANGUAGE plpgsql;
```

**Extended Repository Methods**:
```python
# Add to session_repository.py
class SessionRepository:
    def create_user_with_password(
        self, 
        user_id: str, 
        username: str, 
        email: str,
        password: str,  # Raw password (will be hashed)
        **kwargs
    ) -> Dict[str, Any]:
        """Create user with password authentication."""
        password_hash, salt = self._hash_password(password)
        
        # Create user with authentication fields
        user_data = {
            **kwargs,
            'password_hash': password_hash,
            'salt': salt,
            'email_verified': False
        }
        
        return self.create_user(user_id, username, email, **user_data)
    
    def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with email and password."""
        # Implementation for password verification
        pass
```

## Complete Session Management Architecture

### Core Components Overview

The session management system (as implemented in `session_manager.py`, `session_repository.py`, and `session.py`) provides a complete foundation:

#### 1. Session Manager (`session_manager.py`)

**Primary orchestration layer** providing high-level session operations:

```python
from polymer_extractor.storage.session_manager import get_session_manager, ResourceRequirements

session_mgr = get_session_manager()

# Create session with resource requirements
session = session_mgr.create_session(
    user_id="researcher_alice",                    # From your auth system
    session_name="polymer_thermal_conductivity",
    resource_requirements=ResourceRequirements(
        models=["bert_polymer", "roberta_ensemble"],
        memory_gb=6.0,
        cpu_cores=2,
        priority=3,
        max_duration_hours=12
    ),
    metadata={"project": "thermal_study", "department": "materials_science"}
)
```

**Key Features**:
- **Resource Allocation**: Automatic memory, CPU, and model allocation
- **Session Lifecycle**: Creation, monitoring, expiration, cleanup
- **Configurable Strategies**: Shared, isolated, or hybrid resource sharing
- **Performance Monitoring**: Real-time metrics and health checking

#### 2. Session Repository (`session_repository.py`)

**Data access layer** for users, sessions, and resource management:

```python
from polymer_extractor.repositories.session_repository import get_session_repository

session_repo = get_session_repository()

# User management
user = session_repo.create_user(
    user_id="auth_user_123",               # ID from your authentication system
    username="alice_researcher",
    email="alice@university.edu",
    display_name="Dr. Alice Smith",
    organization="Materials Science Dept",
    user_role="researcher",                # admin, researcher, guest
    storage_quota_gb=50.0,
    max_concurrent_sessions=5
)

# Resource tracking
allocation = session_repo.allocate_resource(
    user_session_id=session.id,
    resource_type="memory",
    resource_name="bert_polymer_model",
    allocated_amount=4.5
)

# Analytics and monitoring
user_analytics = session_repo.get_user_analytics("auth_user_123")
system_capacity = session_repo.get_system_capacity()
```

**Key Features**:
- **User CRUD Operations**: Complete user lifecycle management
- **Resource Quota Management**: Storage quotas with usage tracking
- **Session Analytics**: Performance metrics and capacity planning
- **Activity Logging**: Complete audit trail for security

#### 3. Session API (`session.py`)

**FastAPI endpoints** for external session management:

```python
# API Usage Examples

# Create user (integrate with your auth system)
POST /api/session/user/create
{
    "user_id": "auth_system_user_456",      # From your authentication
    "username": "bob_researcher",
    "email": "bob@university.edu",
    "storage_quota_gb": 25.0,
    "max_concurrent_sessions": 3
}

# Create session
POST /api/session/create
{
    "user_id": "auth_system_user_456",
    "session_name": "polymer_strength_analysis",
    "resource_requirements": {
        "models": ["bert_polymer"],
        "memory_gb": 4.0,
        "priority": 2
    },
    "expires_in_minutes": 180
}

# Monitor session
GET /api/session/{session_id}/health
# Returns: status, resource usage, time to expiry, metrics
```

## Production Multi-User Configuration

### Environment Setup

**Core Session Configuration**:
```bash
# === SESSION MANAGEMENT ===
MAX_CONCURRENT_SESSIONS=50              # Global session limit
SESSION_TIMEOUT_MINUTES=180             # Auto-timeout for idle sessions
RESOURCE_SHARING_STRATEGY=hybrid        # shared|isolated|hybrid
USER_STORAGE_ISOLATION=true             # Enable user storage prefixes
SESSION_CLEANUP_INTERVAL=15             # Cleanup check interval (minutes)

# === USER QUOTAS ===
DEFAULT_STORAGE_QUOTA_GB=25.0          # Default storage per user
MAX_CONCURRENT_SESSIONS_PER_USER=5     # Sessions per user default
DEFAULT_USER_ROLE=researcher            # Default role for new users

# === AUTHENTICATION INTEGRATION ===
AUTH_PROVIDER=appwrite                  # appwrite|custom|oauth
AUTH_REQUIRED=true                      # Require authentication for sessions
SESSION_TOKEN_EXPIRY_HOURS=24          # Auth session token expiry
```

**Multi-Backend Storage for Production**:
```bash
# === PRODUCTION STORAGE ===
STORAGE_BACKENDS_ACTIVE=local,s3        # Multiple backends for redundancy
STORAGE_STRATEGY=failover               # failover|sync|replica
USER_STORAGE_ISOLATION=true            # User-specific storage prefixes

# User storage structure: users/{user_id}/sessions/{session_id}/
```

### Database Schema Integration

The multi-user system extends the existing schema with comprehensive session management:

**Core Tables** (from `db/sql/002_multi_user.sql`):
```sql
-- Users table (no passwords - integrates with external auth)
CREATE TABLE users (
    user_id VARCHAR(255) PRIMARY KEY,      -- From external auth system
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255),
    display_name VARCHAR(255),
    organization VARCHAR(255),
    user_role VARCHAR(50) DEFAULT 'researcher',
    storage_quota_gb DECIMAL(10,2) DEFAULT 10.0,
    max_concurrent_sessions INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- User sessions with resource allocation
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) REFERENCES users(user_id),
    session_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'creating',
    storage_prefix VARCHAR(500),            -- User-specific storage path
    resource_requirements JSONB,
    allocated_resources JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

-- Resource allocation tracking
CREATE TABLE resource_allocations (
    id SERIAL PRIMARY KEY,
    user_session_id UUID REFERENCES user_sessions(id),
    resource_type VARCHAR(100),
    resource_name VARCHAR(255),
    allocated_amount DECIMAL(10,2),
    allocated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deallocated_at TIMESTAMP
);
```

## Security Implementation

### User Data Isolation

**Storage Isolation** (handled automatically by `storage_manager.py`):
```python
# When USER_STORAGE_ISOLATION=true, all storage operations use user prefixes
# users/researcher_alice/sessions/a1b2c3d4-e5f6-7890-abcd-ef1234567890/

# Storage operations automatically include user context
storage.add_resource("reports/analysis.csv", data)
# Actual storage key: users/researcher_alice/sessions/{session_id}/reports/analysis.csv
```

**Database Isolation** (enforced in `session_repository.py`):
```python
# All database queries automatically filter by user_id
def list_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
    """All sessions filtered by user ownership."""
    query = """
        SELECT * FROM user_sessions 
        WHERE user_id = %s 
        ORDER BY created_at DESC
    """
    # User can only see their own sessions
```

### Resource Quotas and Limits

**Quota Enforcement** (implemented in `session_repository.py`):
```python
def check_user_quota(self, user_id: str) -> Dict[str, Any]:
    """Comprehensive quota checking with enforcement."""
    quota_info = self.db.execute_query("""
        SELECT 
            u.storage_quota_gb,
            u.max_concurrent_sessions,
            COALESCE(storage_usage.total_usage_gb, 0) as storage_used_gb,
            active_sessions.session_count as active_sessions
        FROM users u
        LEFT JOIN get_user_storage_usage(u.user_id) storage_usage ON true
        LEFT JOIN get_user_active_sessions(u.user_id) active_sessions ON true
        WHERE u.user_id = %s
    """, [user_id])
    
    # Automatic enforcement in session creation
    if quota_info['storage_used_gb'] >= quota_info['storage_quota_gb']:
        raise QuotaExceededError("Storage quota exceeded")
```

### Session Security

**Session Token Management**:
```python
# UUID-based session identification prevents session hijacking
session_id = uuid4()  # Cryptographically secure session ID

# Session expiration with automatic cleanup
expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)

# Activity tracking for security monitoring
session_repo.log_user_access(
    user_id=user_id,
    action="session_created",
    resource_accessed=f"session/{session_id}",
    ip_address=request.client.host,
    user_agent=request.headers.get("user-agent")
)
```

## Production Deployment Workflow

### 1. Database Setup

```bash
# Apply core schema (if not already applied)
source .venv/bin/activate
psql -d polymer_extractor -f db/sql/001_core.sql

# Apply multi-user extensions
psql -d polymer_extractor -f db/sql/002_multi_user.sql

# Optional: Add authentication schema (if using Strategy 3)
psql -d polymer_extractor -f db/sql/003_user_authentication.sql
```

### 2. Configure Authentication Integration

**Option A: Appwrite Integration**:
```python
# Add to your main application
from polymer_extractor.auth.appwrite_integration import AppwriteAuthManager

auth_manager = AppwriteAuthManager()

@app.middleware("http")
async def authenticate_requests(request: Request, call_next):
    """Authenticate API requests and create session users."""
    auth_token = request.headers.get("Authorization", "").replace("Bearer ", "")
    
    if auth_token:
        appwrite_user = auth_manager.verify_token(auth_token)
        if appwrite_user:
            # Ensure user exists in session management
            session_repo.create_or_update_user(
                user_id=appwrite_user['$id'],
                username=appwrite_user.get('name'),
                email=appwrite_user.get('email')
            )
            
            # Add user context to request
            request.state.user_id = appwrite_user['$id']
    
    return await call_next(request)
```

**Option B: Custom Authentication**:
```python
# Add authentication middleware to your FastAPI app
@app.middleware("http")
async def custom_auth_middleware(request: Request, call_next):
    """Custom authentication integration."""
    auth_token = request.headers.get("Authorization", "").replace("Bearer ", "")
    
    if auth_token:
        # Your custom authentication logic
        user = your_auth_system.verify_token(auth_token)
        if user:
            # Ensure user exists in session management
            session_repo.create_or_update_user(
                user_id=user.id,
                username=user.username,
                email=user.email,
                storage_quota_gb=user.get_quota(),
                max_concurrent_sessions=user.get_session_limit()
            )
            
            request.state.user_id = user.id
    
    return await call_next(request)
```

### 3. Session-Aware API Integration

**Update existing API endpoints** to use session context:

```python
# Example: Update extraction endpoints to use sessions
@router.post("/extract")
async def extract_entities(
    request: ExtractionRequest,
    user_id: str = Depends(get_current_user_id)  # From auth middleware
) -> Dict[str, Any]:
    """Session-aware entity extraction."""
    
    # Create or get user session
    session = session_manager.create_session(
        user_id=user_id,
        session_name=f"extraction_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        resource_requirements=ResourceRequirements(
            models=request.models,
            memory_gb=estimate_memory_requirements(request.papers),
            priority=request.priority
        )
    )
    
    try:
        # Run extraction with session context
        results = session_manager.run_extraction(
            session_id=session.id,
            paper_ids=request.paper_ids,
            ensemble_strategy=request.ensemble_strategy,
            config=request.config
        )
        
        return {
            "session_id": str(session.id),
            "extraction_results": results,
            "storage_location": session.storage_prefix
        }
        
    finally:
        # Optional: Keep session for user to access results
        # Or terminate immediately: session_manager.terminate_session(session.id)
        pass
```

### 4. Monitoring and Maintenance

**System Health Monitoring**:
```python
# Regular monitoring script
def monitor_session_system():
    session_repo = get_session_repository()
    
    # Check system capacity
    capacity = session_repo.get_system_capacity()
    if capacity['capacity_utilization'] > 0.85:
        alert("High system utilization", capacity)
    
    # Check user quotas
    users = session_repo.get_all_users()
    for user in users:
        analytics = session_repo.get_user_analytics(user['user_id'])
        quota_utilization = analytics['storage_quota']['quota_utilization']
        
        if quota_utilization > 0.9:
            alert(f"User {user['username']} approaching quota limit", analytics)
    
    # Cleanup expired sessions
    cleaned = session_repo.cleanup_expired_sessions()
    if cleaned > 0:
        logger.info(f"Cleaned up {cleaned} expired sessions")
```

## Integration Testing

**Complete Multi-User Workflow Test**:
```python
async def test_complete_multiuser_workflow():
    """Test complete multi-user session workflow."""
    
    # 1. Create users (simulating external auth)
    alice = session_repo.create_user(
        user_id="alice_auth_123",
        username="alice_researcher",
        email="alice@university.edu",
        storage_quota_gb=25.0
    )
    
    bob = session_repo.create_user(
        user_id="bob_auth_456", 
        username="bob_researcher",
        email="bob@university.edu",
        storage_quota_gb=15.0
    )
    
    # 2. Create concurrent sessions
    alice_session = session_manager.create_session(
        user_id="alice_auth_123",
        session_name="alice_thermal_conductivity",
        resource_requirements=ResourceRequirements(models=["bert_polymer"])
    )
    
    bob_session = session_manager.create_session(
        user_id="bob_auth_456",
        session_name="bob_mechanical_properties", 
        resource_requirements=ResourceRequirements(models=["roberta_ensemble"])
    )
    
    # 3. Run concurrent extractions with isolation
    alice_results = session_manager.run_extraction(
        session_id=alice_session.id,
        paper_ids=["paper1", "paper2"],
        ensemble_strategy="weighted_voting"
    )
    
    bob_results = session_manager.run_extraction(
        session_id=bob_session.id,
        paper_ids=["paper3", "paper4"],
        ensemble_strategy="consensus"
    )
    
    # 4. Verify isolation
    alice_files = storage.list_resources(alice_session.storage_prefix)
    bob_files = storage.list_resources(bob_session.storage_prefix)
    
    # Alice and Bob should not see each other's results
    assert len(set(alice_files) & set(bob_files)) == 0
    
    # 5. Cleanup
    session_manager.terminate_session(alice_session.id)
    session_manager.terminate_session(bob_session.id)
```

## Summary

The Polymer NLP Extractor provides a **complete session management foundation** ready for production deployment. The system includes:

✅ **Complete Session Infrastructure**: User management, resource allocation, lifecycle management
✅ **Production-Ready Architecture**: Scalable to 50+ concurrent sessions with monitoring
✅ **Flexible Authentication Integration**: Works with any authentication provider
✅ **Comprehensive Security**: User isolation, quotas, audit trails, resource limits
✅ **Rich API Layer**: RESTful endpoints for all session operations

**Next Steps for Production**:
1. Choose authentication strategy (Appwrite, custom, or extended users table)
2. Implement authentication middleware in your FastAPI application
3. Update existing API endpoints to use session context
4. Configure monitoring and alerting for system health
5. Test multi-user workflows thoroughly before deployment

The session management system is **production-ready** - only the authentication layer requires implementation based on your specific security requirements.
