# 07. Database Layer Architecture

## Overview

The Polymer NLP Extractor employs a sophisticated PostgreSQL-based database architecture designed specifically for polymer science data extraction workflows. This layer provides comprehensive data persistence, multi-user session management, and high-performance operations optimized for ensemble learning scenarios.

## Architecture Components

The database layer consists of three main architectural components:

### 1. **PostgreSQL Client** (`postgresql_client.py`)
- **Purpose**: Low-level PostgreSQL interface with enterprise-grade connection management
- **Features**: Connection pooling, transaction management, bulk operations, health monitoring
- **Use Case**: Direct database operations with optimal performance and reliability

### 2. **Database Manager** (`database_manager.py`) 
- **Purpose**: High-level database operations with resource locking and legacy compatibility
- **Features**: Universal CRUD operations, batch processing, resource conflict resolution
- **Use Case**: Service layer integration with intelligent concurrency management

### 3. **Database Schema** (`db/sql/`)
- **Purpose**: Production-ready PostgreSQL schema optimized for polymer science workflows
- **Features**: Multi-backend storage support, ensemble learning metadata, session management
- **Use Case**: Complete data model supporting research paper processing and entity extraction

## Database Schema Deep Dive

### Core Schema Structure (`001_core.sql`)

The core schema is organized into logical sections designed for polymer science research workflows:

#### **1. Research Papers Metadata**

```sql
CREATE TABLE research_papers (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(255) UNIQUE NOT NULL,
    title TEXT,
    authors TEXT,
    abstract TEXT,
    doi VARCHAR(255),
    -- Multi-backend storage support
    storage_key TEXT NOT NULL,
    local_path VARCHAR(500),
    appwrite_file_id VARCHAR(255),
    s3_key VARCHAR(500),
    storage_backends TEXT[] NOT NULL,
    primary_backend VARCHAR(20) NOT NULL,
    -- Processing metadata
    processing_status VARCHAR(20) DEFAULT 'pending',
    extraction_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Key Features:**
- **Multi-Backend Storage**: Supports simultaneous local, Appwrite, and S3 storage with flexible routing
- **Processing Status Tracking**: Complete lifecycle management from upload to extraction completion
- **Flexible Metadata**: JSONB fields for extensible research paper attributes
- **Performance Indexes**: Optimized for common query patterns (DOI lookup, status filtering, storage routing)

**Usage Example:**
```python
from polymer_extractor.storage.database_manager import DatabaseManager

db = DatabaseManager()

# Create research paper record with multi-backend storage
paper_data = {
    "file_name": "polymer_study_2023.pdf",
    "title": "Advanced Polymer Characterization",
    "doi": "10.1234/polymer.2023.001",
    "storage_key": "papers/polymer_study_2023.pdf",
    "storage_backends": ["local", "s3"],
    "primary_backend": "local"
}

paper = db.create_record("research_papers", paper_data)
print(f"Created paper with ID: {paper['id']}")
```

#### **2. Sentences and Text Processing**

```sql
CREATE TABLE sentences (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER REFERENCES research_papers(id) ON DELETE CASCADE,
    sentence_number INTEGER NOT NULL,
    text_content TEXT NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    token_count INTEGER,
    section_type VARCHAR(100),
    section_header TEXT
);
```

**Design Rationale:**
- **Granular Text Storage**: Each sentence stored individually for precise entity location tracking
- **Section Context**: Maintains document structure (introduction, methods, results, conclusion)
- **Character Position Tracking**: Enables exact entity location within original document
- **Token Count**: Pre-computed for efficient model input preparation

#### **3. Unified Entity Storage**

```sql
CREATE TABLE entities (
    id SERIAL PRIMARY KEY,
    sentence_id INTEGER REFERENCES sentences(id) ON DELETE CASCADE,
    session_id UUID REFERENCES extraction_sessions(id) ON DELETE CASCADE,
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('POLYMER', 'PROPERTY', 'VALUE', 'UNIT', 'SYMBOL')),
    text_content TEXT NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    confidence_score DECIMAL(6,4) NOT NULL,
    model_source VARCHAR(100) NOT NULL,
    model_weight DECIMAL(4,2),
    data_type VARCHAR(20) DEFAULT 'extracted' CHECK (data_type IN ('training', 'testing', 'extracted'))
);
```

**Architectural Decisions:**
- **Unified Storage**: All entity types stored in single table with discriminator column for query efficiency
- **Session Tracking**: Links entities to specific extraction runs for result versioning
- **Model Attribution**: Tracks which model extracted each entity for ensemble analysis
- **Confidence Scoring**: Decimal precision for accurate ensemble weight calculations
- **Data Type Separation**: Distinguishes training/testing data from live extraction results

**Performance Indexes:**
```sql
-- Optimized for common polymer science queries
CREATE INDEX idx_entities_type_confidence ON entities(entity_type, confidence_score DESC);
CREATE INDEX idx_entities_session_type ON entities(session_id, entity_type);
CREATE INDEX idx_entities_text_gin ON entities USING GIN(to_tsvector('english', text_content));
CREATE INDEX idx_entities_text_trigram ON entities USING GIN(text_content gin_trgm_ops);
```

#### **4. Ensemble Learning Support**

```sql
CREATE TABLE model_configurations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    model_id VARCHAR(255) NOT NULL,
    version VARCHAR(50) DEFAULT 'v1.0',
    base_weight DECIMAL(4,2) DEFAULT 1.00,
    reliability_score DECIMAL(3,2) DEFAULT 0.50,
    specialization_domains TEXT[],
    training_details JSONB,
    storage_key VARCHAR(500),
    primary_backend VARCHAR(20),
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE model_entity_expertise (
    id SERIAL PRIMARY KEY,
    model_config_id INTEGER REFERENCES model_configurations(id),
    entity_type VARCHAR(20) NOT NULL,
    expertise_weight DECIMAL(4,2) DEFAULT 1.00,
    confidence_threshold DECIMAL(3,2) DEFAULT 0.50
);
```

**Ensemble Strategy Implementation:**
- **Model Registry**: Central registry of available models with version tracking
- **Dynamic Weighting**: Per-entity-type expertise weights for specialized ensemble strategies
- **Reliability Scoring**: Model performance tracking for automated weight adjustment
- **Specialization Domains**: Array-based tagging for domain-specific model selection

**Usage Example:**
```python
# Configure ensemble model weights
model_data = {
    "name": "scibert-polymer-v2",
    "model_id": "allenai/scibert_scivocab_uncased",
    "version": "v2.0",
    "base_weight": 1.20,
    "reliability_score": 0.92,
    "specialization_domains": ["polymer_science", "materials"]
}

model = db.create_record("model_configurations", model_data)

# Set entity-specific expertise
expertise_data = {
    "model_config_id": model["id"],
    "entity_type": "POLYMER",
    "expertise_weight": 1.35,
    "confidence_threshold": 0.65
}

db.create_record("model_entity_expertise", expertise_data)
```

#### **5. Semantic Relationships**

```sql
CREATE TABLE value_unit_pairs (
    id SERIAL PRIMARY KEY,
    value_entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    unit_entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    numerical_value DECIMAL(15,6),
    unit_canonical TEXT,
    relationship_confidence DECIMAL(6,4) NOT NULL,
    distance_tokens INTEGER
);

CREATE TABLE property_measurements (
    id SERIAL PRIMARY KEY,
    property_entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    value_entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    unit_entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    measurement_type VARCHAR(50),
    measurement_confidence DECIMAL(6,4) NOT NULL
);
```

**Semantic Modeling Approach:**
- **Structured Relationships**: Dedicated tables for common polymer science relationships
- **Value-Unit Pairing**: Automatic detection and validation of measurement pairs
- **Property Measurements**: Complete semantic triples (property → value → unit)
- **Distance Tracking**: Token distance for relationship validation
- **Confidence Propagation**: Relationship confidence derived from entity confidences

#### **6. Knowledge Graph Integration**

```sql
CREATE TABLE kg_relationship_cache (
    id SERIAL PRIMARY KEY,
    entity1_canonical TEXT NOT NULL,
    entity2_canonical TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    confidence_score DECIMAL(5,3) NOT NULL,
    confidence_boost DECIMAL(3,2) DEFAULT 0.00,
    validation_rules JSONB,
    cache_hits INTEGER DEFAULT 0
);
```

**Knowledge Graph Strategy:**
- **Caching Layer**: High-performance cache for Neo4j relationship lookups
- **Canonical Forms**: Normalized entity representations for consistent matching
- **Validation Rules**: JSONB storage for complex validation logic
- **Performance Tracking**: Cache hit metrics for optimization analysis

### Multi-User Extension (`002_multi_user.sql`)

The multi-user extension adds production-ready session management and resource allocation:

#### **1. User Management**

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    user_role VARCHAR(50) DEFAULT 'researcher',
    storage_quota_gb DECIMAL(10,2) DEFAULT 10.0,
    max_concurrent_sessions INTEGER DEFAULT 3,
    is_active BOOLEAN DEFAULT true
);
```

#### **2. Session Management**

```sql
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL REFERENCES users(user_id),
    session_name VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    storage_prefix VARCHAR(500),
    resource_requirements JSONB,
    allocated_resources JSONB,
    expires_at TIMESTAMP
);
```

**Session Lifecycle Management:**
- **UUID-Based Sessions**: Globally unique session identifiers
- **Resource Allocation**: JSON-based resource requirement specification
- **Storage Isolation**: User-specific storage namespace prefixes
- **Automatic Expiration**: Configurable session timeout with cleanup procedures

**Usage Example:**
```python
# Create user session with resource requirements
session_data = {
    "user_id": "researcher_001",
    "session_name": "polymer_extraction_batch_1",
    "resource_requirements": {
        "memory_gb": 8.0,
        "cpu_cores": 4,
        "max_papers": 100
    },
    "storage_prefix": "users/researcher_001/sessions/"
}

session = db.create_record("user_sessions", session_data)
```

#### **3. Resource Tracking**

```sql
CREATE TABLE resource_allocations (
    id SERIAL PRIMARY KEY,
    user_session_id UUID NOT NULL REFERENCES user_sessions(id),
    resource_type VARCHAR(50) NOT NULL,
    resource_name VARCHAR(100),
    allocated_amount DECIMAL(10,4),
    peak_usage DECIMAL(10,4),
    status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE user_storage_usage (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL REFERENCES users(user_id),
    storage_key VARCHAR(500) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    storage_backend VARCHAR(50)
);
```

**Resource Management Features:**
- **Fine-Grained Tracking**: Individual resource allocation records
- **Usage Monitoring**: Peak usage tracking for capacity planning
- **Storage Quotas**: Per-user storage limits with automatic enforcement
- **Multi-Backend Awareness**: Storage tracking across all backend types

### Session Integration (`003_session_integration.sql`)

Provides triggers and functions for automatic session management:

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE OR REPLACE FUNCTION can_user_create_session(p_user_id VARCHAR(255))
RETURNS BOOLEAN AS $$
-- Implementation checks user and global session limits
$$;
```

## Database Manager Architecture

### Universal CRUD Operations

The `DatabaseManager` class provides a consistent interface for all database operations:

```python
class DatabaseManager:
    def __init__(self):
        """Initialize with PostgreSQL client and resource locking."""
        
    # Universal CRUD operations
    def create_record(self, table_name: str, data: Dict[str, Any]) -> Dict[str, Any]
    def get_record(self, table_name: str, record_id: str) -> Dict[str, Any]
    def list_records(self, table_name: str, filters: Optional[Dict] = None) -> List[Dict]
    def update_record(self, table_name: str, record_id: str, data: Dict) -> Dict[str, Any]
    def delete_record(self, table_name: str, record_id: str) -> None
    
    # Batch operations
    def bulk_insert(self, table_name: str, records: List[Dict]) -> List[Dict]
    def bulk_update(self, table_name: str, updates: List[Dict]) -> List[Dict]
    def bulk_delete(self, table_name: str, record_ids: List[str]) -> int
    
    # Advanced operations
    def search_records(self, table_name: str, search_term: str, fields: List[str]) -> List[Dict]
    def count_records(self, table_name: str, filters: Optional[Dict] = None) -> int
```

### Resource Locking Strategy

The database manager implements intelligent resource locking to prevent concurrent modification conflicts:

```python
# Example: Create record with automatic locking
def create_record(self, table_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    resource_id = f"database/table/{table_name}"
    lock_metadata = {
        "operation": "create_record",
        "table_name": table_name,
        "user_context": "database_manager"
    }
    
    if self.enable_locking and self.lock_manager:
        try:
            with self.lock_manager.acquire_lock(
                resource_id, LockType.WRITE, metadata=lock_metadata, timeout=30
            ):
                return self._create_postgres_record(table_name, data)
        except ResourceLockConflict as e:
            raise DatabaseError(f"Resource conflict: {e}")
    else:
        return self._create_postgres_record(table_name, data)
```

**Lock Types and Strategies:**
- **Read Locks**: Multiple concurrent reads allowed
- **Write Locks**: Exclusive access for modifications
- **Table-Level Locking**: Granular locking per database table
- **Timeout Handling**: Configurable timeout with graceful failure

### Legacy Compatibility Layer

The database manager maintains backward compatibility with existing Appwrite-style method names:

```python
# Legacy compatibility methods
def create_document(self, collection_id: str, data: Dict) -> Dict:
    """Legacy: Maps to create_record for backward compatibility."""
    return self.create_record(collection_id, data)

def list_documents(self, collection_id: str, queries: Optional[List] = None) -> List[Dict]:
    """Legacy: Maps to list_records with query conversion."""
    filters = self._convert_queries_to_filters(queries)
    return self.list_records(collection_id, filters)
```

This ensures existing services continue to work without modification while new development uses the improved universal methods.

## PostgreSQL Client Architecture

### Connection Pool Management

The `PostgresClient` class provides enterprise-grade connection management:

```python
class PostgresClient:
    def __init__(self, dsn: Optional[str] = None, min_conn: int = 1, max_conn: int = 10):
        """Initialize with connection pooling."""
        self.dsn = dsn or os.getenv("POSTGRES_DSN") or self._build_dsn_from_parts()
        self.pool = SimpleConnectionPool(min_conn, max_conn, self.dsn)
        
    def health_check(self) -> Dict[str, Any]:
        """Comprehensive database health monitoring."""
        
    def run(self, sql: str, params: Optional[Tuple] = None, 
           fetch: Literal["none", "one", "all"] = "none") -> Union[None, Dict, List[Dict]]:
        """Safe parameterized query execution."""
```

### Transaction Management

Provides ACID-compliant transaction support with automatic rollback:

```python
@contextmanager
def transaction(self):
    """ACID-compliant transaction context manager."""
    conn = self._get_conn()
    try:
        yield TransactionContext(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        self._put_conn(conn)
```

### Bulk Operations

Optimized bulk operations for large dataset processing:

```python
def bulk_insert(self, table_name: str, records: List[Dict]) -> List[Dict]:
    """High-performance bulk insert using PostgreSQL COPY."""
    with self.transaction() as tx:
        # Use COPY FROM for maximum performance
        tx.copy_from(records, table_name)
        return tx.execute(f"SELECT * FROM {table_name} WHERE id IN (...)")
```

## Environment Configuration

### Database Connection Setup

The database layer uses environment-driven configuration for maximum flexibility:

```bash
# Primary configuration (recommended)
POSTGRES_DSN=postgresql://polymer_user:secure_password@localhost:5432/polymer_extractor

# Alternative discrete configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=polymer_extractor
POSTGRES_USER=polymer_user
POSTGRES_PASSWORD=secure_password

# Connection pool settings
POSTGRES_MIN_CONN=2
POSTGRES_MAX_CONN=20
POSTGRES_CONNECT_TIMEOUT=10

# Feature flags
USE_POSTGRESQL_DB=true
DATA_BACKEND=postgres
RESOURCE_LOCK_ENABLE=true
```

### Schema Deployment

Deploy the complete schema using the provided SQL files:

```bash
# Activate virtual environment
source .venv/bin/activate

# Deploy core schema
python3 -c "
from polymer_extractor.storage.postgresql_client import PostgresClient
db = PostgresClient()
result = db.deploy_schema('db/sql/001_core.sql')
print(f'Core schema: {result[\"status\"]}')
"

# Deploy multi-user extension
python3 -c "
from polymer_extractor.storage.postgresql_client import PostgresClient
db = PostgresClient()
result = db.deploy_schema('db/sql/002_multi_user.sql')
print(f'Multi-user schema: {result[\"status\"]}')
"

# Deploy session integration
python3 -c "
from polymer_extractor.storage.postgresql_client import PostgresClient
db = PostgresClient()
result = db.deploy_schema('db/sql/003_session_integration.sql')
print(f'Session integration: {result[\"status\"]}')
"
```

## Common Usage Patterns

### 1. Research Paper Processing

```python
from polymer_extractor.storage.database_manager import DatabaseManager

db = DatabaseManager()

# Upload and register research paper
paper_data = {
    "file_name": "polymer_analysis_2023.pdf",
    "title": "Advanced Polymer Characterization Techniques",
    "authors": "Smith, J.; Johnson, A.; Chen, L.",
    "doi": "10.1234/polymer.2023.045",
    "storage_key": "papers/polymer_analysis_2023.pdf",
    "storage_backends": ["local", "s3"],
    "primary_backend": "local",
    "processing_status": "pending"
}

paper = db.create_record("research_papers", paper_data)

# Create extraction session
session_data = {
    "session_name": f"extraction_{paper['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    "paper_id": paper["id"],
    "model_ids": [1, 2, 3],  # IDs from model_configurations
    "ensemble_strategy": "weighted_voting",
    "confidence_threshold": 0.60
}

session = db.create_record("extraction_sessions", session_data)
```

### 2. Entity Extraction and Storage

```python
# Store extracted entities from ensemble models
entities_data = [
    {
        "sentence_id": 123,
        "session_id": session["id"],
        "entity_type": "POLYMER",
        "text_content": "polyethylene",
        "char_start": 45,
        "char_end": 57,
        "confidence_score": 0.92,
        "model_source": "scibert-v2",
        "model_weight": 1.20
    },
    {
        "sentence_id": 123,
        "session_id": session["id"],
        "entity_type": "PROPERTY",
        "text_content": "tensile strength",
        "char_start": 78,
        "char_end": 94,
        "confidence_score": 0.87,
        "model_source": "bert-base",
        "model_weight": 1.00
    }
]

# Bulk insert for performance
entities = db.bulk_insert("entities", entities_data)

# Create semantic relationships
relationship_data = {
    "entity1_id": entities[0]["id"],  # polymer
    "entity2_id": entities[1]["id"],  # property
    "relationship_type": "has_property",
    "relationship_confidence": 0.89,
    "sentence_id": 123,
    "session_id": session["id"]
}

db.create_record("entity_relationships", relationship_data)
```

### 3. Multi-User Session Management

```python
# Create user
user_data = {
    "user_id": "researcher_001",
    "username": "john.smith",
    "email": "john.smith@university.edu",
    "display_name": "Dr. John Smith",
    "organization": "University Research Lab",
    "user_role": "researcher",
    "storage_quota_gb": 25.0
}

user = db.create_record("users", user_data)

# Create user session with resource allocation
session_data = {
    "user_id": "researcher_001",
    "session_name": "polymer_batch_processing_2023",
    "resource_requirements": {
        "memory_gb": 16.0,
        "cpu_cores": 8,
        "max_concurrent_extractions": 5
    },
    "storage_prefix": "users/researcher_001/sessions/2023_batch/"
}

user_session = db.create_record("user_sessions", session_data)
```

### 4. Performance Monitoring and Analytics

```python
# Query extraction performance by model
performance_query = """
SELECT 
    mc.name as model_name,
    e.entity_type,
    COUNT(*) as total_extractions,
    AVG(e.confidence_score) as avg_confidence,
    COUNT(CASE WHEN e.confidence_score > 0.8 THEN 1 END) as high_confidence_count
FROM entities e
JOIN extraction_sessions es ON e.session_id = es.id
JOIN model_configurations mc ON mc.id = ANY(es.model_ids)
WHERE e.created_at >= %s
GROUP BY mc.name, e.entity_type
ORDER BY avg_confidence DESC
"""

results = db.postgres_client.run(
    performance_query, 
    (datetime.now() - timedelta(days=30),),
    fetch="all"
)

# Generate performance report
for result in results:
    print(f"Model: {result['model_name']}")
    print(f"Entity Type: {result['entity_type']}")
    print(f"Avg Confidence: {result['avg_confidence']:.3f}")
    print(f"High Confidence: {result['high_confidence_count']}/{result['total_extractions']}")
    print("---")
```

### 5. Storage Usage Analytics

```python
# Check user storage utilization
storage_summary = db.postgres_client.run("""
SELECT 
    u.user_id,
    u.username,
    u.storage_quota_gb,
    COALESCE(SUM(sus.file_size_bytes), 0) / (1024.0^3) as used_gb,
    u.storage_quota_gb - COALESCE(SUM(sus.file_size_bytes), 0) / (1024.0^3) as remaining_gb
FROM users u
LEFT JOIN user_storage_usage sus ON u.user_id = sus.user_id
GROUP BY u.user_id, u.username, u.storage_quota_gb
ORDER BY used_gb DESC
""", fetch="all")

for user in storage_summary:
    utilization = (user['used_gb'] / user['storage_quota_gb']) * 100
    print(f"{user['username']}: {user['used_gb']:.2f}GB / {user['storage_quota_gb']}GB ({utilization:.1f}%)")
```

## Performance Optimization Guidelines

### 1. Index Strategy

The schema includes comprehensive indexes optimized for polymer science queries:

```sql
-- Entity lookup optimization
CREATE INDEX idx_entities_type_confidence ON entities(entity_type, confidence_score DESC);
CREATE INDEX idx_entities_session_type ON entities(session_id, entity_type);

-- Full-text search optimization
CREATE INDEX idx_entities_text_gin ON entities USING GIN(to_tsvector('english', text_content));
CREATE INDEX idx_entities_text_trigram ON entities USING GIN(text_content gin_trgm_ops);

-- Multi-backend storage optimization
CREATE INDEX idx_papers_storage_backends ON research_papers USING GIN(storage_backends);
CREATE INDEX idx_papers_primary_backend ON research_papers(primary_backend);
```

### 2. Query Optimization

**Recommended Query Patterns:**

```python
# Use parameterized queries for safety and performance
papers = db.postgres_client.run(
    "SELECT * FROM research_papers WHERE processing_status = %s AND created_at >= %s",
    ("completed", datetime.now() - timedelta(days=7)),
    fetch="all"
)

# Use appropriate fetch modes
single_paper = db.postgres_client.run(
    "SELECT * FROM research_papers WHERE id = %s",
    (paper_id,),
    fetch="one"  # More efficient for single results
)

# Use bulk operations for large datasets
entities = db.bulk_insert("entities", large_entity_list)
```

### 3. Connection Pool Sizing

Configure connection pools based on workload characteristics:

```bash
# For development (low concurrency)
POSTGRES_MIN_CONN=2
POSTGRES_MAX_CONN=8

# For production (high concurrency)
POSTGRES_MIN_CONN=5
POSTGRES_MAX_CONN=25

# For batch processing (high throughput)
POSTGRES_MIN_CONN=10
POSTGRES_MAX_CONN=50
```

## Error Handling and Troubleshooting

### Common Error Scenarios

**1. Connection Pool Exhaustion:**
```python
try:
    result = db.create_record("entities", data)
except Exception as e:
    if "connection pool exhausted" in str(e):
        # Implement retry logic or increase pool size
        logger.warning("Connection pool exhausted, retrying...")
```

**2. Resource Lock Conflicts:**
```python
from polymer_extractor.utils.resource_lock_manager import ResourceLockConflict

try:
    result = db.create_record("research_papers", data)
except ResourceLockConflict as e:
    logger.warning(f"Resource conflict detected: {e}")
    # Implement exponential backoff retry
```

**3. Schema Validation Errors:**
```python
try:
    entity = db.create_record("entities", entity_data)
except Exception as e:
    if "CHECK constraint" in str(e):
        logger.error(f"Invalid entity type: {entity_data.get('entity_type')}")
```

### Health Check Implementation

```python
def check_database_health():
    """Comprehensive database health check."""
    db = DatabaseManager()
    
    # Check connection
    health = db.postgres_client.health_check()
    if not health["ok"]:
        return {"status": "unhealthy", "error": health["error"]}
    
    # Check table existence
    tables = db.list_tables()
    required_tables = ["research_papers", "entities", "extraction_sessions"]
    missing_tables = [t for t in required_tables if t not in tables]
    
    if missing_tables:
        return {"status": "unhealthy", "error": f"Missing tables: {missing_tables}"}
    
    # Check recent activity
    recent_papers = db.count_records("research_papers", {
        "created_at": {"$gte": datetime.now() - timedelta(hours=24)}
    })
    
    return {
        "status": "healthy",
        "details": {
            "server_version": health["details"]["server_version"],
            "total_papers": db.count_records("research_papers"),
            "recent_papers_24h": recent_papers,
            "active_sessions": db.count_records("extraction_sessions", {"status": "running"})
        }
    }
```

## Migration and Maintenance

### Schema Migrations

When updating the schema, follow this migration pattern:

```python
def migrate_schema_v2_to_v3():
    """Example schema migration."""
    db = PostgresClient()
    
    with db.transaction() as tx:
        # Add new columns
        tx.execute("ALTER TABLE entities ADD COLUMN entity_confidence_v2 DECIMAL(8,6)")
        
        # Migrate existing data
        tx.execute("""
            UPDATE entities 
            SET entity_confidence_v2 = confidence_score * 1.0 
            WHERE entity_confidence_v2 IS NULL
        """)
        
        # Update constraints
        tx.execute("ALTER TABLE entities ALTER COLUMN entity_confidence_v2 SET NOT NULL")
```

### Cleanup Procedures

```python
def cleanup_expired_sessions():
    """Clean up expired user sessions and related data."""
    db = DatabaseManager()
    
    # Use the built-in cleanup function
    cleanup_count = db.postgres_client.run(
        "SELECT cleanup_expired_sessions()",
        fetch="one"
    )
    
    logger.info(f"Cleaned up {cleanup_count} expired sessions")
```

## Integration with Storage Layer

The database layer integrates seamlessly with the storage architecture (see [Document 6: Storage Architecture](6_storage_architecture.md)):

```python
from polymer_extractor.storage.database_manager import DatabaseManager
from polymer_extractor.storage.storage_manager import StorageManager

# Coordinated database and storage operations
db = DatabaseManager()
storage = StorageManager()

# Upload file and create database record
storage_key = "papers/new_research.pdf"
file_path = "/tmp/uploaded_file.pdf"

# Store file
storage_result = storage.add_resource(storage_key, file_path)

# Create database record with storage references
paper_data = {
    "file_name": "new_research.pdf",
    "storage_key": storage_key,
    "storage_backends": storage_result["backends"],
    "primary_backend": storage_result["primary_backend"],
    "file_size": storage_result["file_size"]
}

paper = db.create_record("research_papers", paper_data)
```

This tight integration ensures consistency between file storage and database metadata, supporting the project's multi-backend storage strategy while maintaining data integrity.

---

## Summary

The database layer provides a robust, scalable foundation for the Polymer NLP Extractor with:

- **Production-Ready Schema**: Optimized for polymer science workflows with comprehensive indexing
- **Multi-User Support**: Complete session management and resource allocation
- **Ensemble Learning**: Native support for multi-model extraction and confidence tracking
- **Multi-Backend Storage**: Seamless integration with local, Appwrite, and S3 storage
- **Performance Optimization**: Connection pooling, bulk operations, and intelligent caching
- **Operational Excellence**: Health monitoring, error handling, and maintenance procedures

The layered architecture (PostgreSQL Client → Database Manager → Application Services) provides flexibility for different use cases while maintaining consistency and performance across the entire system.
