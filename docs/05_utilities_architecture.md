# 05. Utilities - Decoupled Architecture Foundation

## Overview

The `polymer_extractor/utils/` directory demonstrates the **decoupled architecture philosophy** that makes the Polymer NLP Extractor robust, maintainable, and production-ready. Each utility module provides a **single source of truth** for its domain, enabling clean separation of concerns while ensuring consistent behavior across all services.

This section explores the four core utilities that form the foundation of the project's architecture:

1. **`paths.py`** - Universal storage and path resolution
2. **`logging.py`** - Thread-safe system-wide logging with database integration
3. **`resource_lock_manager.py`** - Intelligent resource locking and conflict resolution
4. **`responses.py`** - Standardized API response envelopes

## Architecture Principles

### Decoupled Design Benefits

- **Single Source of Truth**: Each utility owns its domain completely
- **Zero Circular Dependencies**: Utilities are designed to be independent
- **Consistent Interfaces**: Standardized patterns across all components
- **Production Hardened**: Built for concurrent, multi-user environments
- **Easily Testable**: Utilities can be tested in isolation

### Integration Strategy

```python
# Each service imports only what it needs
from polymer_extractor.utils.paths import get_storage_path, path_resolver
from polymer_extractor.utils.logging import get_logger
from polymer_extractor.utils.responses import ok, error, raise_http
from polymer_extractor.utils.resource_lock_manager import acquire_resource_lock

# Services remain focused on business logic
class MyService:
    def __init__(self):
        self.logger = get_logger()
    
    def process_data(self, input_path: str) -> Dict[str, Any]:
        # Path resolution
        local_path = path_resolver.to_local_path(input_path, "processed_xml")
        
        # Resource locking
        with acquire_resource_lock(f"file:{local_path}", "write") as lock:
            # Logging
            self.logger.info("Processing started", source="my_service", file=local_path)
            
            # Business logic here...
            
            # Standardized response
            return ok({"processed_file": local_path}, message="Processing completed")
```

## 1. Path Resolution (`paths.py`) - Universal Storage Authority

### Overview

`paths.py` serves as the **authoritative source** for all path resolution, storage routing, and file location logic. It eliminates hardcoded paths and provides a unified interface for handling local storage, remote backends, and complex path transformations.

### Key Features

#### Universal Path Resolution

The `PathResolver` class handles **any path format** and converts it to the target format intelligently:

```python
from polymer_extractor.utils.paths import path_resolver, get_storage_path

# Input normalization - all these are equivalent:
path_resolver.to_local_path("extracted_xml/paper1.xml")
path_resolver.to_local_path("/extracted_xml/paper1.xml")  # Leading slash ignored
path_resolver.to_local_path("workspace/public/extracted_xml_dir/paper1.xml")

# All resolve to: /home/user/workspace/polymer_nlp_extractor/workspace/public/extracted_xml_dir/paper1.xml
```

#### Storage Strategy Support

Supports multiple storage backends with consistent routing:

```python
# Local storage
storage_key = get_storage_path("reports", "evaluation_metrics.csv")
# Returns: "full_reports_dir/evaluation_metrics.csv"

# Remote storage (S3, Appwrite) - same interface
local_path = path_resolver.to_local_path(storage_key, "reports", for_write=True)
# Ensures: workspace/public/full_reports_dir/evaluation_metrics.csv exists for writing
```

#### Read vs Write Path Resolution

**Critical feature**: Different resolution logic for reads vs writes:

```python
# READ RESOLUTION (searches in order: public -> workspace)
read_path = path_resolver.to_local_path("models/bert_polymer.bin", for_write=False)
# Searches:
# 1. workspace/public/models/bert_polymer.bin
# 2. workspace/models/bert_polymer.bin (legacy location)
# 3. workspace/bert_polymer.bin
# Returns first found

# WRITE RESOLUTION (ensures write location under public)
write_path = path_resolver.to_local_path("models/new_model.bin", for_write=True)
# Always returns: workspace/public/models/new_model.bin
# Creates directory structure if needed
```

#### URL Handling and Downloads

Automatically handles HTTP/HTTPS URLs with intelligent caching:

```python
# URL inputs are automatically downloaded
pdf_url = "https://arxiv.org/pdf/2023.12345.pdf"
local_path = path_resolver.to_local_path(pdf_url, "raw_inputs")
# Downloads to: workspace/public/raw_inputs_dir/2023.12345.pdf
# Subsequent calls return cached local path

# URL detection is automatic
path_type = path_resolver.detect_path_type("https://example.com/file.pdf")
# Returns: "url"
```

#### File Type Intelligence

Supports logical file types with automatic directory mapping:

```python
# Logical file types map to directory structure
STORAGE_PATHS = {
    "raw_inputs": "raw_inputs_dir",          # Original PDFs
    "extracted_xml": "extracted_xml_dir",    # Raw XML from GROBID  
    "processed_xml": "processed_xml_dir",    # Cleaned TEI XML
    "samples": "samples_dir",                # Tokenization samples
    "models": "models",                      # Model files
    "reports": "full_reports_dir",           # Analysis reports
    "exports": "exports_dir",                # Export files
    "system_logs": "system_logs",            # System logs
    "datasets": "datasets_dir"               # Datasets
}

# Usage examples
get_local_path("reports", "thermal_analysis.csv")
# Returns: workspace/public/full_reports_dir/thermal_analysis.csv

get_storage_path("models", "ensemble_v2.1.bin") 
# Returns: models/ensemble_v2.1.bin (for BucketClient)
```

### ServicePathHandler Integration

Provides consistent service response helpers:

```python
from polymer_extractor.utils.paths import service_path_handler

# Service input resolution
input_path, file_type = service_path_handler.resolve_service_input("reports/eval.csv")
# Returns: ("/full/path/to/workspace/public/full_reports_dir/eval.csv", "reports")

# Service output directory creation
output_path = service_path_handler.ensure_service_output_dir("exports/polymer_data.json")
# Creates directory and returns: "/full/path/workspace/public/exports_dir/polymer_data.json"

# Standardized service response
return service_path_handler.format_service_response(
    success=True,
    local_path=output_path,
    file_type="exports",
    message="Export completed successfully",
    record_count=1500
)
# Returns standardized response with storage info
```

### Complete Path Resolution Examples

```python
# Complex real-world examples

# 1. Multi-format input handling
inputs = [
    "raw_inputs/paper1.pdf",                    # Relative path
    "/home/user/papers/paper2.pdf",             # Absolute path  
    "https://arxiv.org/pdf/2023.12345.pdf",     # Remote URL
    "workspace/public/raw_inputs_dir/paper3.pdf" # Project-relative
]

for input_path in inputs:
    # All normalize to consistent local paths
    local_path = path_resolver.to_local_path(input_path, "raw_inputs")
    storage_key = path_resolver.to_storage_path(input_path, "raw_inputs")
    print(f"Input: {input_path}")
    print(f"Local: {local_path}")
    print(f"Storage: {storage_key}\n")

# 2. Service integration example
def process_extraction_results(result_file: str) -> Dict[str, Any]:
    """Process extraction results with full path resolution."""
    
    # Input resolution (searches multiple locations)
    local_path = path_resolver.to_local_path(result_file, "reports", for_write=False)
    
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Result file not found: {result_file}")
    
    # Process the file...
    processed_data = process_file(local_path)
    
    # Output with guaranteed write location
    output_path = path_resolver.to_local_path("exports/processed_results.json", "exports", for_write=True)
    
    # Save processed data
    with open(output_path, 'w') as f:
        json.dump(processed_data, f)
    
    # Return standardized response
    return {
        "input_path": local_path,
        "output_path": output_path,
        "storage_key": get_storage_path("exports", "processed_results.json"),
        "record_count": len(processed_data)
    }
```

## 2. System Logging (`logging.py`) - Production-Grade Observability

### Overview

`logging.py` provides a **thread-safe, production-hardened logging system** with dual output (file + database), intelligent deduplication, and zero circular dependencies. It's designed to handle high-throughput scenarios while maintaining performance and reliability.

### Key Architecture Features

#### Database Independence

**Critical design**: Direct PostgreSQL connection to avoid circular imports:

```python
class DirectPostgreSQLLogger:
    """Direct database connection for logging to avoid circular dependencies."""
    
    def __init__(self):
        # Direct connection - NO dependency on DatabaseManager
        self.connection_string = (
            f"postgresql://{os.getenv('DATABASE_USER')}:"
            f"{os.getenv('DATABASE_PASSWORD')}@"
            f"{os.getenv('DATABASE_HOST')}:"
            f"{os.getenv('DATABASE_PORT')}/"
            f"{os.getenv('DATABASE_NAME')}"
        )
        
    def log_to_database(self, log_entry: LogEntry):
        """Direct database logging with connection pooling."""
        # Independent database operations
        # No risk of circular imports or database locks
```

#### Dual Logging Strategy

**Redundant persistence** ensures logs survive any single point of failure:

```python
from polymer_extractor.utils.logging import get_logger

logger = get_logger()

# Single log call writes to BOTH destinations
logger.info("Processing started", source="extraction_service", paper_count=25)

# File output: workspace/public/system_logs/general.log
# Database output: system_logs table with full structured data
# Memory buffer: Recent logs kept for fast API access
```

#### Intelligent Deduplication

Prevents log spam in high-frequency scenarios:

```python
# Log deduplication in action
for i in range(100):
    logger.warning("Database connection slow", source="db_service", latency_ms=250)

# Only logs first 5 occurrences within 60-second window
# Subsequent identical messages are suppressed
# Prevents log flooding from repetitive errors
```

### Structured Logging with Context

Every log entry is a structured `LogEntry` with rich metadata:

```python
@dataclass
class LogEntry:
    timestamp: str              # UTC ISO-8601 timestamp
    level: str                 # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message: str               # Primary log message
    source: str                # Component/service identifier
    event_type: str            # Event classification
    user_action: bool          # User-initiated vs system event
    category: str              # Log category for organization
    filename: str              # Source file name
    line_number: int           # Source line number
    function_name: str         # Source function name
    context: Dict[str, Any]    # Additional structured data

# Usage creates rich, searchable logs
logger.error(
    "Extraction failed for paper",
    source="ensemble_service",
    event_type="extraction_error", 
    user_action=True,
    category="model",
    paper_id="10.1234/polymer.2023.001",
    model_name="bert_polymer_v2",
    error_code="MODEL_TIMEOUT",
    processing_time_seconds=45.2,
    memory_usage_mb=2048
)
```

### Smart Truncation and Safety

Prevents oversized logs while preserving data structure:

```python
class SmartTruncator:
    """Intelligent content truncation for log context data."""
    
    def truncate_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Preserves structure while limiting size."""
        
        # Large strings truncated with indicators
        large_text = "x" * 1000
        truncated = truncator.truncate_context({"data": large_text})
        # Result: {"data": "xxx...xxx[truncated: 1000 -> 500 chars]"}
        
        # Large lists summarized intelligently  
        large_list = list(range(100))
        truncated = truncator.truncate_context({"items": large_list})
        # Result: {"items": [0, 1, 2, ..., 97, 98, 99, "...[90 items truncated]"]}
        
        # Nested dictionaries handled recursively
        nested_data = {"level1": {"level2": {"large_field": "x" * 800}}}
        # All levels truncated while preserving structure
```

### Production Logging Examples

```python
# 1. Service lifecycle logging
class ExtractionService:
    def __init__(self):
        self.logger = get_logger()
    
    def start_extraction(self, paper_ids: List[str], user_id: str) -> Dict[str, Any]:
        # Service start log
        self.logger.info(
            "Extraction service started",
            source="extraction_service",
            event_type="service_start",
            user_action=True,
            category="api",
            user_id=user_id,
            paper_count=len(paper_ids),
            request_timestamp=datetime.utcnow().isoformat()
        )
        
        try:
            results = self.process_papers(paper_ids)
            
            # Success log
            self.logger.info(
                "Extraction completed successfully", 
                source="extraction_service",
                event_type="extraction_complete",
                user_action=True,
                category="model",
                user_id=user_id,
                papers_processed=len(results),
                total_entities=sum(len(r["entities"]) for r in results),
                processing_time_seconds=42.5,
                average_confidence=0.87
            )
            
            return results
            
        except Exception as e:
            # Error log with full context
            self.logger.error(
                "Extraction failed with exception",
                source="extraction_service", 
                event_type="extraction_error",
                user_action=True,
                category="model",
                user_id=user_id,
                paper_count=len(paper_ids),
                exception_type=type(e).__name__,
                exception_message=str(e),
                stack_trace=traceback.format_exc()
            )
            raise

# 2. Performance monitoring
def log_performance_metrics():
    """Regular performance logging."""
    logger = get_logger()
    
    # System metrics
    logger.info(
        "System performance metrics",
        source="performance_monitor",
        event_type="metrics_collection", 
        category="performance",
        cpu_usage_percent=65.2,
        memory_usage_mb=4096,
        disk_usage_percent=78.5,
        active_connections=23,
        cache_hit_rate=0.91,
        average_response_time_ms=120.5
    )

# 3. User activity tracking
def log_user_activity(user_id: str, action: str, **context):
    """Track user actions for analytics and security."""
    logger = get_logger()
    
    logger.info(
        f"User action: {action}",
        source="user_activity_tracker",
        event_type="user_action",
        user_action=True,
        category="user",
        user_id=user_id,
        action=action,
        timestamp=datetime.utcnow().isoformat(),
        **context
    )

# Usage:
log_user_activity(
    user_id="researcher_123",
    action="upload_paper",
    filename="thermal_conductivity_study.pdf",
    file_size_mb=2.4,
    ip_address="192.168.1.100"
)
```

### Log Analysis and Monitoring

```python
# Query recent logs programmatically
logger = get_logger()

# Get recent errors for monitoring
recent_errors = logger.get_recent_logs(count=50, level="ERROR")
for log_entry in recent_errors:
    print(f"{log_entry['timestamp']}: {log_entry['message']}")

# Get performance statistics
stats = logger.get_log_stats()
print(f"Total logs today: {stats['logs_today']}")
print(f"Error rate: {stats['error_rate']:.2%}")
print(f"Most active sources: {stats['top_sources']}")

# Database queries for analytics (using DirectPostgreSQLLogger)
db_logger = DirectPostgreSQLLogger()
query_results = db_logger.query_logs(
    level="ERROR",
    source="extraction_service", 
    since_hours=24
)
```

## 3. Resource Lock Manager (`resource_lock_manager.py`) - Intelligent Concurrency Control

### Overview

`resource_lock_manager.py` provides **intelligent resource locking** with conflict resolution, preventing race conditions in multi-user environments. It standardizes database access patterns and ensures data consistency across concurrent operations.

### Core Locking Mechanisms

#### Multiple Lock Types

Support for different access patterns:

```python
from polymer_extractor.utils.resource_lock_manager import ResourceLockManager, LockType

lock_manager = ResourceLockManager()

# 1. READ locks (shared access)
with lock_manager.acquire_lock("database/papers", LockType.READ) as lock:
    # Multiple readers can access simultaneously
    papers = db.query("SELECT * FROM papers")

# 2. WRITE locks (exclusive for writes, blocks reads)
with lock_manager.acquire_lock("database/papers", LockType.WRITE) as lock:
    # Exclusive access for data modification
    db.update("UPDATE papers SET processed=true WHERE id=%s", paper_id)

# 3. EXCLUSIVE locks (completely exclusive)
with lock_manager.acquire_lock("graph/bulk_update", LockType.EXCLUSIVE) as lock:
    # No other access allowed during bulk operations
    graph.bulk_update_relationships(polymer_data)

# 4. SHARED locks (multiple shared access)
with lock_manager.acquire_lock("storage/reports", LockType.SHARED) as lock:
    # Multiple processes can share resource
    generate_report(report_data)
```

#### Intelligent Conflict Resolution

User-friendly error handling with retry recommendations:

```python
try:
    with lock_manager.acquire_lock("database/models", LockType.WRITE, timeout=30) as lock:
        # Attempt database update
        update_model_metadata(model_id, new_metadata)
        
except ResourceLockConflict as e:
    # Intelligent conflict information
    print(f"Resource busy: {e.user_message}")
    # "Database update in progress by user_456. Try again in 15 seconds."
    
    print(f"Conflicting locks: {len(e.conflicting_locks)}")
    print(f"Estimated retry time: {e.retry_after} seconds")
    
    # Automatic retry logic
    time.sleep(e.retry_after)
    # retry_operation()
```

#### Deadlock Prevention

Automatic detection and prevention of deadlock scenarios:

```python
# Example: Service A and Service B need same resources
def service_a_operation():
    with lock_manager.acquire_lock("database/papers", LockType.WRITE):
        with lock_manager.acquire_lock("database/models", LockType.READ):
            # Resource ordering prevents deadlocks
            pass

def service_b_operation(): 
    # Lock manager ensures consistent ordering
    with lock_manager.acquire_lock("database/papers", LockType.READ):
        with lock_manager.acquire_lock("database/models", LockType.WRITE):
            # No deadlock possible with intelligent ordering
            pass
```

### Database Standardization Examples

#### Coordinated Database Access

```python
# 1. Model Training Coordination
def train_model_safely(model_config: Dict[str, Any]) -> Dict[str, Any]:
    """Train model with resource coordination."""
    
    # Lock model directory for exclusive access
    resource_id = f"models/{model_config['model_name']}"
    
    with acquire_resource_lock(resource_id, LockType.EXCLUSIVE, timeout=300) as lock:
        logger.info("Model training started", source="model_trainer", 
                   model_name=model_config['model_name'])
        
        try:
            # Lock training data for read access
            data_resource = f"datasets/{model_config['dataset_name']}"
            with acquire_resource_lock(data_resource, LockType.READ) as data_lock:
                
                # Perform training with guaranteed exclusive access
                training_result = perform_training(model_config)
                
                # Save model with exclusive lock still held
                save_model(training_result, model_config['model_name'])
                
                logger.info("Model training completed", source="model_trainer",
                           model_name=model_config['model_name'],
                           accuracy=training_result['accuracy'])
                
                return training_result
                
        except Exception as e:
            logger.error("Model training failed", source="model_trainer",
                        model_name=model_config['model_name'], 
                        exception=e)
            raise

# 2. Database Migration Coordination  
def run_database_migration(migration_name: str) -> bool:
    """Run database migration with exclusive coordination."""
    
    migration_resource = f"database/migration/{migration_name}"
    
    try:
        # Attempt exclusive lock with short timeout
        with acquire_resource_lock(migration_resource, LockType.EXCLUSIVE, timeout=5) as lock:
            
            logger.info("Database migration started", source="migration_service",
                       migration=migration_name)
            
            # Check if migration already applied
            if is_migration_applied(migration_name):
                logger.info("Migration already applied", source="migration_service",
                           migration=migration_name)
                return True
            
            # Run migration with exclusive database access
            with acquire_resource_lock("database/schema", LockType.EXCLUSIVE, timeout=120) as db_lock:
                apply_migration(migration_name)
                record_migration_applied(migration_name)
                
                logger.info("Database migration completed", source="migration_service",
                           migration=migration_name)
                return True
                
    except ResourceLockConflict as e:
        # Another process is running migrations
        logger.warning("Migration already in progress", source="migration_service",
                      migration=migration_name, 
                      conflict_message=e.user_message)
        return False
```

#### Session Resource Coordination

```python
# 3. Multi-User Session Resource Management
def allocate_session_resources(session_id: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
    """Allocate resources for user session with coordination."""
    
    allocated_resources = {}
    
    try:
        # Lock session allocation table
        with acquire_resource_lock("database/session_allocations", LockType.WRITE) as alloc_lock:
            
            # Lock specific models requested
            for model_name in requirements.get('models', []):
                model_resource = f"models/{model_name}"
                
                try:
                    # Try to acquire shared model access
                    model_lock = lock_manager.try_acquire_lock(model_resource, LockType.SHARED)
                    if model_lock:
                        allocated_resources[f"model_{model_name}"] = model_lock
                        logger.info("Model allocated to session", source="session_manager",
                                   session_id=session_id, model=model_name)
                    else:
                        # Model unavailable - check conflicts
                        conflicts = lock_manager.get_resource_locks(model_resource)
                        logger.warning("Model unavailable", source="session_manager",
                                      session_id=session_id, model=model_name,
                                      conflicting_sessions=len(conflicts))
                        
                except ResourceLockConflict as e:
                    logger.error("Model allocation failed", source="session_manager",
                                session_id=session_id, model=model_name,
                                conflict_reason=e.user_message)
                    
                    # Release already allocated resources
                    for allocated_lock in allocated_resources.values():
                        lock_manager.release_lock(allocated_lock.lock_id)
                    
                    raise
            
            # Record allocation in database
            record_session_allocation(session_id, allocated_resources)
            
            return {
                "session_id": session_id,
                "allocated_models": list(requirements.get('models', [])),
                "allocation_count": len(allocated_resources),
                "status": "allocated"
            }
            
    except Exception as e:
        logger.error("Session resource allocation failed", source="session_manager",
                    session_id=session_id, exception=e)
        raise
```

### Lock Monitoring and Statistics

```python
# Real-time lock monitoring
def monitor_lock_system():
    """Monitor lock system health and performance."""
    lock_manager = get_resource_lock_manager()
    
    # Get system statistics
    stats = lock_manager.get_lock_statistics()
    
    logger.info("Lock system statistics", source="lock_monitor",
               category="performance",
               active_locks=stats["current_active_locks"],
               locks_acquired_today=stats["locks_acquired"],
               conflicts_resolved=stats["conflicts_resolved"],
               timeout_rate=stats["timeouts"] / max(stats["locks_acquired"], 1),
               average_lock_duration=stats.get("average_duration_seconds", 0))
    
    # Check for resource contention
    if stats["conflicts_resolved"] > 100:  # High contention threshold
        logger.warning("High resource contention detected", source="lock_monitor",
                      conflicts_in_period=stats["conflicts_resolved"],
                      recommendation="Consider scaling resources or optimizing access patterns")
    
    # Monitor specific resource usage
    high_contention_resources = []
    for resource_id in ["database/papers", "models/bert_polymer", "graph/relationships"]:
        resource_locks = lock_manager.get_resource_locks(resource_id)
        if len(resource_locks) > 5:  # High usage threshold
            high_contention_resources.append({
                "resource": resource_id,
                "active_locks": len(resource_locks),
                "lock_types": [lock.lock_type.value for lock in resource_locks]
            })
    
    if high_contention_resources:
        logger.warning("High resource contention", source="lock_monitor",
                      resources=high_contention_resources)
```

## 4. API Responses (`responses.py`) - Standardized Communication

### Overview

`responses.py` ensures **consistent API communication** across all endpoints with standardized envelopes, proper HTTP status codes, and structured error handling. It eliminates response format inconsistencies and provides a unified interface for all client interactions.

### Standardized Response Envelopes

Every API response follows the same structure for predictable client parsing:

```python
# Standard envelope structure
{
  "status": "success|partial_success|failure|error|healthy|unhealthy",
  "code": 200,                    # HTTP status code mirrored in payload
  "message": "Human-readable summary",
  "data": {...},                  # Primary payload (optional)
  "details": {...},               # Secondary details (optional)  
  "timestamp": "2025-08-22T14:30:45.123456Z"  # UTC ISO-8601
}
```

### Success Response Patterns

```python
from polymer_extractor.utils.responses import ok, healthy, partial

# 1. Standard success responses
def extract_entities(paper_ids: List[str]) -> Dict[str, Any]:
    """Extract entities with standardized success response."""
    
    extraction_results = perform_extraction(paper_ids)
    
    return ok(
        data={
            "extracted_entities": extraction_results,
            "paper_count": len(paper_ids),
            "total_entities": sum(len(r["entities"]) for r in extraction_results),
            "processing_time_seconds": 45.2
        },
        message=f"Successfully extracted entities from {len(paper_ids)} papers",
        code=200
    )
    
    # Response:
    # {
    #   "status": "success",
    #   "code": 200,
    #   "message": "Successfully extracted entities from 3 papers",
    #   "data": {
    #     "extracted_entities": [...],
    #     "paper_count": 3,
    #     "total_entities": 156,
    #     "processing_time_seconds": 45.2
    #   },
    #   "timestamp": "2025-08-22T14:30:45.123456Z"
    # }

# 2. Health check responses
def check_system_health() -> Dict[str, Any]:
    """System health with service status details."""
    
    service_status = {
        "database": check_database_connection(),
        "neo4j": check_graph_connection(),
        "grobid": check_grobid_service(),
        "storage": check_storage_backend()
    }
    
    all_healthy = all(status["healthy"] for status in service_status.values())
    
    if all_healthy:
        return healthy(
            data=service_status,
            message="All systems operational"
        )
    else:
        return healthy(
            data=service_status,
            message="Some services degraded", 
            code=200  # Still 200 but status indicates issues
        )

# 3. Partial success handling
def bulk_upload_papers(files: List[str]) -> Dict[str, Any]:
    """Handle bulk operations with partial success reporting."""
    
    results = {"successful": [], "failed": []}
    
    for file_path in files:
        try:
            processed_file = process_paper(file_path)
            results["successful"].append({
                "file": file_path,
                "entities_extracted": len(processed_file["entities"])
            })
        except Exception as e:
            results["failed"].append({
                "file": file_path,
                "error": str(e),
                "error_type": type(e).__name__
            })
    
    if results["failed"]:
        # Partial success response
        return partial(
            data=results,
            message=f"Processed {len(results['successful'])}/{len(files)} files successfully",
            code=206
        )
    else:
        # Complete success
        return ok(
            data=results,
            message=f"All {len(files)} files processed successfully"
        )
```

### Error Response Standardization

```python
from polymer_extractor.utils.responses import failure, error, raise_http

# 1. Client error responses (4xx)
def validate_extraction_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """Validate request with detailed error information."""
    
    validation_errors = []
    
    if not request.get("paper_ids"):
        validation_errors.append({
            "field": "paper_ids",
            "error": "Required field missing",
            "expected": "List of paper identifiers"
        })
    
    if "ensemble_strategy" in request:
        valid_strategies = ["weighted_voting", "consensus", "best_confidence"]
        if request["ensemble_strategy"] not in valid_strategies:
            validation_errors.append({
                "field": "ensemble_strategy", 
                "error": "Invalid strategy",
                "provided": request["ensemble_strategy"],
                "valid_options": valid_strategies
            })
    
    if validation_errors:
        return failure(
            message="Request validation failed",
            code=400,
            details={
                "validation_errors": validation_errors,
                "error_count": len(validation_errors),
                "help_url": "https://docs.polymer-extractor.com/api/validation"
            }
        )
    
    # Validation passed
    return {"valid": True}

# 2. Server error responses (5xx)
def handle_model_loading_error(model_name: str, exception: Exception) -> Dict[str, Any]:
    """Handle server errors with safe error details."""
    
    return error(
        message="Model loading failed - please try again later",
        code=500,
        details={
            "model_name": model_name,
            "error_category": "model_loading",
            "retry_recommended": True,
            "estimated_retry_delay_seconds": 30
        },
        exception=exception,  # Automatically adds exception_type and error fields
        operation_id=str(uuid4()),  # For tracking in support
        support_reference="Contact support with operation_id if issue persists"
    )
    
    # Response includes safe error details:
    # {
    #   "status": "error",
    #   "code": 500,
    #   "message": "Model loading failed - please try again later",
    #   "details": {
    #     "model_name": "bert_polymer_v2",
    #     "error_category": "model_loading",
    #     "retry_recommended": true,
    #     "estimated_retry_delay_seconds": 30
    #   },
    #   "exception_type": "FileNotFoundError",
    #   "error": "Model file not found at specified path",
    #   "operation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    #   "support_reference": "Contact support with operation_id if issue persists",
    #   "timestamp": "2025-08-22T14:30:45.123456Z"
    # }

# 3. HTTP exception raising
def get_paper_by_id(paper_id: str) -> Dict[str, Any]:
    """Retrieve paper with standardized error handling."""
    
    if not paper_id or len(paper_id) < 5:
        raise_http(
            status_code=400,
            status_label="invalid_parameter",
            message="Invalid paper ID format",
            details={
                "parameter": "paper_id",
                "provided": paper_id,
                "requirements": "Must be at least 5 characters long",
                "examples": ["10.1234/polymer.2023.001", "arxiv:2023.12345"]
            }
        )
    
    paper = database.get_paper(paper_id)
    if not paper:
        raise_http(
            status_code=404,
            status_label="not_found", 
            message="Paper not found",
            details={
                "paper_id": paper_id,
                "searched_in": ["papers", "extraction_sessions", "cached_results"],
                "suggestion": "Check paper ID spelling or try different search terms"
            }
        )
    
    return ok(data=paper, message="Paper retrieved successfully")
```

### Service Integration Examples

```python
# Complete service implementation with standardized responses

class EvaluationService:
    def __init__(self):
        self.logger = get_logger()
    
    def run_evaluation(self, model_name: str, test_dataset: str) -> Dict[str, Any]:
        """Run model evaluation with comprehensive response handling."""
        
        self.logger.info("Evaluation started", source="evaluation_service",
                        model_name=model_name, dataset=test_dataset)
        
        try:
            # Validate inputs
            validation_result = self._validate_evaluation_request(model_name, test_dataset)
            if not validation_result["valid"]:
                return validation_result  # Returns failure() response
            
            # Check resource availability
            if not self._check_resource_availability(model_name):
                return failure(
                    message="Model temporarily unavailable",
                    code=503,
                    details={
                        "model_name": model_name,
                        "reason": "Model is being updated",
                        "retry_after_seconds": 300,
                        "alternative_models": self._get_alternative_models(model_name)
                    }
                )
            
            # Perform evaluation
            evaluation_results = self._run_evaluation_internal(model_name, test_dataset)
            
            # Success response with comprehensive data
            return ok(
                data={
                    "model_name": model_name,
                    "test_dataset": test_dataset,
                    "metrics": evaluation_results["metrics"],
                    "confusion_matrix": evaluation_results["confusion_matrix"],
                    "sample_predictions": evaluation_results["samples"][:10],  # Limit for response size
                    "evaluation_metadata": {
                        "test_samples": evaluation_results["sample_count"],
                        "processing_time_seconds": evaluation_results["duration"],
                        "model_version": evaluation_results["model_version"],
                        "evaluation_timestamp": datetime.utcnow().isoformat()
                    }
                },
                message=f"Evaluation completed for {model_name} on {test_dataset}",
                code=200
            )
            
        except ResourceLockConflict as e:
            # Resource conflict - user-friendly response
            return failure(
                message="Evaluation resource busy",
                code=409,
                details={
                    "resource_conflict": e.user_message,
                    "retry_after_seconds": e.retry_after,
                    "conflicting_operations": len(e.conflicting_locks)
                }
            )
            
        except ValidationError as e:
            # Input validation error
            return failure(
                message="Invalid evaluation parameters",
                code=422,
                details={
                    "validation_errors": e.errors,
                    "parameter_help": "https://docs.polymer-extractor.com/evaluation-api"
                }
            )
            
        except Exception as e:
            # Unexpected server error
            self.logger.error("Evaluation failed", source="evaluation_service",
                            model_name=model_name, dataset=test_dataset,
                            exception=e)
            
            return error(
                message="Evaluation failed due to internal error",
                code=500,
                details={
                    "model_name": model_name,
                    "dataset": test_dataset,
                    "error_category": "internal_error",
                    "support_contact": "Include operation details when contacting support"
                },
                exception=e
            )
    
    def _validate_evaluation_request(self, model_name: str, test_dataset: str) -> Dict[str, Any]:
        """Validate evaluation request parameters."""
        
        errors = []
        
        # Validate model
        available_models = self._get_available_models()
        if model_name not in available_models:
            errors.append({
                "field": "model_name",
                "error": "Model not available",
                "provided": model_name,
                "available_models": available_models
            })
        
        # Validate dataset
        available_datasets = self._get_available_datasets()
        if test_dataset not in available_datasets:
            errors.append({
                "field": "test_dataset",
                "error": "Dataset not found",
                "provided": test_dataset,
                "available_datasets": available_datasets
            })
        
        if errors:
            return failure(
                message="Evaluation parameters validation failed",
                code=400,
                details={
                    "validation_errors": errors,
                    "help": "Use /api/models and /api/datasets endpoints to see available options"
                }
            )
        
        return {"valid": True}
```

## Integration Benefits and Production Impact

### Consistency Across Services

The utilities provide **unprecedented consistency** across the entire application:

```python
# Every service follows the same patterns
class AnyService:
    def __init__(self):
        self.logger = get_logger()                    # Standardized logging
        self.lock_manager = get_resource_lock_manager()  # Resource coordination
    
    def any_operation(self, input_path: str) -> Dict[str, Any]:
        # Standardized path resolution
        local_path = path_resolver.to_local_path(input_path, "reports")
        
        # Standardized resource locking
        with self.lock_manager.acquire_lock(f"file:{local_path}", "write") as lock:
            
            # Standardized logging
            self.logger.info("Operation started", source="any_service", file=local_path)
            
            try:
                # Business logic...
                result = process_file(local_path)
                
                # Standardized success response
                return ok(data=result, message="Operation completed successfully")
                
            except Exception as e:
                # Standardized error logging and response
                self.logger.error("Operation failed", source="any_service", 
                                exception=e, file=local_path)
                return error(message="Operation failed", exception=e)
```

### Production Reliability

The utilities ensure production-grade reliability:

- **Zero Circular Dependencies**: Utilities are completely independent
- **Thread-Safe Operations**: All utilities handle concurrent access safely
- **Fault Tolerance**: Graceful degradation when services are unavailable
- **Resource Management**: Automatic cleanup and leak prevention
- **Monitoring Integration**: Built-in observability and health checking

### Development Efficiency

Developers can focus on business logic while utilities handle infrastructure concerns:

```python
# Clean, business-focused service code
def extract_polymer_properties(paper_url: str) -> Dict[str, Any]:
    """Extract polymer properties - utilities handle everything else."""
    
    # Path handling - automatic URL download and resolution
    local_path = path_resolver.to_local_path(paper_url, "raw_inputs")
    
    # Resource coordination - automatic conflict resolution
    with acquire_resource_lock(f"extraction:{local_path}", "read") as lock:
        
        # Logging - structured, dual-output, deduplicated
        logger.info("Property extraction started", source="property_extractor", 
                   paper_url=paper_url)
        
        # Business logic (the only part developers need to focus on)
        properties = run_nlp_extraction(local_path)
        
        # Response - standardized, client-friendly
        return ok(
            data={"properties": properties, "source_file": local_path},
            message=f"Extracted {len(properties)} properties"
        )
```

This decoupled utilities architecture ensures the Polymer NLP Extractor remains maintainable, scalable, and production-ready while providing developers with powerful, consistent tools for building robust services.
