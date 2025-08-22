# Multi-User Production Architecture Guide

## Overview

This document outlines the production-ready multi-user, multi-session architecture for the Polymer NLP Extractor. The design balances efficiency with user isolation while avoiding over-engineering.

## Architecture Components

### 1. Session Management Layer
- **SessionManager**: High-level session orchestration with user awareness
- **UserSession**: Individual user sessions with isolated resources
- **SessionRepository**: Data access layer for session and user management

### 2. Storage Isolation Strategy
- **User Prefixes**: Storage keys prefixed with `users/{user_id}/sessions/{session_id}/`
- **Configurable Isolation**: Environment-controlled via `USER_STORAGE_ISOLATION`
- **Shared Resources**: Models and system data remain shared for efficiency

### 3. Database Architecture
- **User Management**: Basic user accounts with quotas and permissions
- **Session Tracking**: User sessions with resource allocation and lifecycle
- **Enhanced Extraction Sessions**: Linked to user context for tracking

### 4. Resource Management
- **Resource Sharing Strategies**: `shared`, `isolated`, `hybrid` modes
- **Quota Management**: Storage quotas with usage tracking
- **Concurrent Session Limits**: Per-user and global session limits

## Key Design Principles

### Efficient Resource Sharing
```python
# Resource sharing strategies
SHARED = "shared"      # Resources shared across all sessions (most efficient)
ISOLATED = "isolated"  # Each session gets dedicated resources (most secure)
HYBRID = "hybrid"      # Mix of shared and isolated (balanced approach)
```

### User Isolation Without Over-Engineering
- **Logical Separation**: Database queries filter by user_id
- **Storage Namespacing**: Optional user-specific storage prefixes
- **Shared Infrastructure**: Models, system services remain shared
- **Configurable Isolation**: Can be disabled for simpler deployments

### Session Lifecycle Management
```python
# Session states optimize resource utilization
SessionStatus.CREATING -> ACTIVE -> PROCESSING -> IDLE -> COMPLETED
                                  ↘ FAILED ↗
                                  ↘ EXPIRED ↗
```

## Configuration

### Environment Variables
```bash
# Session Management
MAX_CONCURRENT_SESSIONS=10              # Global session limit
SESSION_TIMEOUT_MINUTES=60              # Auto-timeout for idle sessions
RESOURCE_SHARING_STRATEGY=hybrid        # shared|isolated|hybrid
USER_STORAGE_ISOLATION=true             # Enable user storage prefixes
SESSION_CLEANUP_INTERVAL=15             # Cleanup check interval

# User Quotas (can be per-user in database)
DEFAULT_STORAGE_QUOTA_GB=10.0          # Storage quota per user
MAX_CONCURRENT_SESSIONS_PER_USER=3     # Sessions per user
```

### Database Schema
The architecture extends existing schema with:
- `users` table for basic user management
- `user_sessions` table for session tracking
- `resource_allocations` table for resource management
- Enhanced `extraction_sessions` with user context

## Implementation Example

### 1. Multi-User Session Creation
```python
from polymer_extractor.storage.session_manager import get_session_manager
from polymer_extractor.storage.session_manager import ResourceRequirements

session_mgr = get_session_manager()

# Create sessions for multiple users
alice_session = session_mgr.create_session(
    user_id="researcher_alice",
    session_name="polymer_conductivity_study",
    resource_requirements=ResourceRequirements(
        models=["bert_polymer", "roberta_ensemble"],
        memory_gb=4.0,
        priority=3
    )
)

bob_session = session_mgr.create_session(
    user_id="researcher_bob",
    session_name="polymer_strength_analysis",
    resource_requirements=ResourceRequirements(
        models=["bert_polymer"],
        memory_gb=2.0,
        priority=2
    )
)
```

### 2. Session-Aware Extraction
```python
# Run extractions with user isolation
alice_results = session_mgr.run_extraction(
    session_id=alice_session.id,
    paper_ids=["paper1", "paper2"],
    ensemble_strategy="weighted_voting"
)

# Results are stored with user-specific storage prefix
# alice: users/researcher_alice/sessions/a1b2c3d4/results/
# bob:   users/researcher_bob/sessions/e5f6g7h8/results/
```

### 3. Resource Monitoring
```python
# Monitor system capacity
capacity = session_mgr.get_system_capacity()
print(f"System utilization: {capacity['capacity_utilization']:.1%}")
print(f"Active sessions: {capacity['active_sessions']}/{capacity['max_concurrent_sessions']}")

# Monitor user-specific metrics
alice_health = session_mgr.get_session_health(alice_session.id)
print(f"Alice's session: {alice_health['status']}")
print(f"Time to expiry: {alice_health['time_to_expiry_minutes']} minutes")
```

### 4. Storage with User Isolation
```python
from polymer_extractor.storage.storage_manager import get_storage_manager

storage = get_storage_manager()

# Storage automatically uses session prefix if USER_STORAGE_ISOLATION=true
# For alice's session: users/researcher_alice/sessions/a1b2c3d4/reports/analysis.csv
storage.add_resource("reports/analysis.csv", csv_data, metadata={"user_session": alice_session.id})
```

## Production Deployment

### 1. Database Setup
```bash
# Apply core schema
psql -d polymer_extractor -f db/sql/001_core.sql

# Apply multi-user extensions
psql -d polymer_extractor -f db/sql/002_multi_user.sql
```

### 2. Environment Configuration
```bash
# Production settings
ENVIRONMENT=production
MAX_CONCURRENT_SESSIONS=50
SESSION_TIMEOUT_MINUTES=180
RESOURCE_SHARING_STRATEGY=hybrid
USER_STORAGE_ISOLATION=true

# Storage backends for scalability
STORAGE_BACKENDS_ACTIVE=local,s3
STORAGE_STRATEGY=failover
```

### 3. User Management Integration
```python
from polymer_extractor.repositories.session_repository import get_session_repository

repo = get_session_repository()

# Create users (integrate with your auth system)
user = repo.create_user(
    user_id="external_user_123",  # From your auth system
    username="alice_researcher",
    email="alice@university.edu",
    display_name="Dr. Alice Smith",
    storage_quota_gb=50.0,
    max_concurrent_sessions=5
)
```

## Monitoring and Analytics

### Session Health Monitoring
```python
# System-wide monitoring
capacity = session_mgr.get_system_capacity()
if capacity['capacity_utilization'] > 0.8:
    alert("High system utilization")

# User-specific monitoring
user_analytics = repo.get_user_analytics("researcher_alice")
if user_analytics['storage_quota']['quota_utilization'] > 0.9:
    alert("User approaching storage quota")
```

### Performance Metrics
The architecture tracks:
- **Session Metrics**: Processing time, entities extracted, confidence scores
- **Resource Utilization**: Memory, CPU, storage usage per session
- **User Analytics**: Total extractions, papers processed, quota usage
- **System Capacity**: Global utilization, concurrent sessions, resource allocation

## Scaling Considerations

### Horizontal Scaling
- **Database**: PostgreSQL with read replicas for analytics
- **Storage**: Multi-backend with S3 for scalability
- **Session Management**: Stateless design allows multiple API instances

### Vertical Scaling
- **Resource Pools**: Smart allocation based on session requirements
- **Model Sharing**: Shared model instances reduce memory overhead
- **Caching**: Knowledge graph caching for faster relationship queries

## Security and Isolation

### Data Isolation
- **Query Filtering**: All database queries filter by user_id
- **Storage Prefixes**: Optional user-specific storage namespaces
- **Session Tokens**: UUID-based session identification

### Resource Limits
- **Per-User Quotas**: Storage and session limits prevent abuse
- **Global Limits**: System-wide limits prevent overload
- **Priority Scheduling**: High-priority users get preference

### Audit Trail
- **User Access Logs**: Complete activity logging
- **Session Metrics**: Performance and usage tracking
- **Resource Allocation**: Detailed resource usage history

## Migration from Single-User

### Backward Compatibility
The architecture maintains backward compatibility:
- Existing extraction sessions continue to work
- Storage keys without user prefixes remain accessible
- API endpoints accept both session-aware and legacy requests

### Gradual Migration
1. **Deploy Schema**: Add multi-user tables alongside existing schema
2. **Enable Features**: Gradually enable user isolation and session management
3. **Migrate Data**: Optional migration of existing data to user-specific namespaces

## Example Production Workflow

```python
# 1. User creates session
session = session_mgr.create_session(
    user_id="researcher_alice",
    session_name="thermal_conductivity_batch_nov_2025",
    resource_requirements=ResourceRequirements(
        models=["bert_polymer", "roberta_ensemble"],
        memory_gb=6.0,
        max_duration_hours=12
    )
)

# 2. Run extraction with automatic resource allocation
results = session_mgr.run_extraction(
    session_id=session.id,
    paper_ids=["10.1234/polymer1", "10.1234/polymer2", "10.1234/polymer3"],
    ensemble_strategy="weighted_voting"
)

# 3. Monitor progress
health = session_mgr.get_session_health(session.id)
print(f"Status: {health['status']}")
print(f"Entities extracted: {health['metrics']['total_entities_extracted']}")

# 4. Access results with user isolation
extracted_data = storage.get_resource(f"{session.storage_prefix}/extraction_results.json")

# 5. Clean up when done
session_mgr.terminate_session(session.id, save_results=True)
```

This architecture provides production-ready multi-user support while maintaining simplicity and efficiency. The configurable isolation allows deployment flexibility from simple single-tenant to complex multi-tenant scenarios.
