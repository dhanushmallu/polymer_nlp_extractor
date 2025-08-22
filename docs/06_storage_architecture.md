# 06. Storage Architecture - Multi-Backend Strategy

## Overview

The Polymer NLP Extractor implements a **sophisticated multi-backend storage architecture** that provides flexibility, redundancy, and scalability for polymer science data workflows. The storage system is built around two core components: `storage_manager.py` (high-level operations) and `storage_client.py` (backend orchestration), which together deliver enterprise-grade storage capabilities with seamless backend switching and intelligent routing strategies.

## Storage Philosophy and Design Principles

### Multi-Backend Approach Rationale

The project adopts a **multi-backend storage strategy** for several critical reasons:

1. **Research Environment Flexibility**: Polymer science research occurs across diverse environments - from local university labs to cloud-based consortiums
2. **Data Sovereignty**: Different institutions have varying requirements for data locality and sovereignty
3. **Cost Optimization**: Ability to leverage cost-effective storage solutions (local) alongside enterprise cloud services
4. **Disaster Recovery**: Built-in redundancy across multiple storage providers prevents data loss
5. **Migration Safety**: Zero-downtime migration between storage providers as requirements evolve
6. **Performance Optimization**: Intelligent routing based on data access patterns and geographic proximity

### Architectural Benefits

```python
# Single interface, multiple backends - complete transparency to services
from polymer_extractor.storage.storage_manager import get_storage_manager

storage = get_storage_manager()

# Same API works with any backend configuration
storage.add_resource("datasets/polymer_properties.csv", csv_data)
storage.get_resource("models/bert_polymer_v2.bin")
storage.fetch_from_url("https://api.polymer.org/data.json", "external/polymer_database.json")

# Backend complexity is completely abstracted
# Could be running on: local filesystem, AWS S3, Appwrite Cloud, or all three simultaneously
```

## Core Storage Components

### 1. StorageManager (`storage_manager.py`) - High-Level Operations

The `StorageManager` serves as the **primary interface** for all storage operations, providing comprehensive resource management with logging, error handling, and path resolution integration.

#### Resource Management Operations

**Standard Resource Operations:**

```python
from polymer_extractor.storage.storage_manager import get_storage_manager

storage = get_storage_manager()

# === CORE RESOURCE OPERATIONS ===

# 1. Add resources with metadata
result = storage.add_resource(
    storage_key="datasets/thermal_conductivity_study.csv",
    content=csv_data,  # bytes or string
    metadata={
        "experiment_id": "TC_2025_001", 
        "researcher": "Dr. Alice Chen",
        "polymer_type": "thermoplastic",
        "temperature_range": "20-200C",
        "data_points": 1500,
        "created_date": "2025-08-22"
    },
    allow_override=False  # Prevents accidental overwrites
)
# Returns: {"success": True, "storage_key": "...", "backend": "...", "size_bytes": 45234}

# 2. Retrieve resources
thermal_data = storage.get_resource("datasets/thermal_conductivity_study.csv")
# Returns: bytes content

# 3. Check resource existence
exists = storage.resource_exists("models/ensemble_thermal_v3.bin")
# Returns: True/False (checks ALL backends in multi-backend mode)

# 4. Get comprehensive metadata
metadata = storage.get_resource_metadata("datasets/thermal_conductivity_study.csv")
# Returns: {
#   "size_bytes": 45234,
#   "content_type": "text/csv",
#   "created_at": "2025-08-22T14:30:45Z",
#   "backend": "local",
#   "storage_key": "datasets/thermal_conductivity_study.csv",
#   "custom_metadata": {"experiment_id": "TC_2025_001", ...}
# }

# 5. List resources with filtering
polymer_datasets = storage.list_resources(folder="datasets")
# Returns: [
#   {
#     "storage_key": "datasets/thermal_conductivity_study.csv",
#     "size_bytes": 45234,
#     "content_type": "text/csv", 
#     "last_modified": "2025-08-22T14:30:45Z",
#     "backend": "local"
#   },
#   {...}
# ]

# 6. Delete resources
deleted = storage.delete_resource("datasets/old_experiment.csv")
# Returns: True if successful (deletes from ALL backends in multi-backend mode)
```

#### File-Based Operations

**Path-Integrated Operations:**

```python
# === FILE SYSTEM INTEGRATION ===

# 1. Upload from local filesystem
upload_result = storage.upload_from_path(
    source_path="/tmp/processed_polymer_data.json",
    dest_storage_key="datasets/processed/polymer_data_batch_5.json",
    metadata={
        "processing_pipeline": "ensemble_v2.1",
        "source_papers": 150,
        "confidence_threshold": 0.85
    }
)
# Automatically detects file type, calculates size, preserves timestamps

# 2. Download to local filesystem  
download_success = storage.download_to_path(
    storage_key="models/bert_polymer_optimized.bin",
    dest_path="/tmp/models/bert_polymer_optimized.bin"
)
# Creates directory structure, preserves metadata, verifies integrity

# 3. Fetch from external URLs
fetch_result = storage.fetch_from_url(
    url="https://materialsproject.org/api/polymers/dataset_v2025.json",
    dest_storage_key="external_data/materials_project_polymers.json",
    file_type="datasets",  # For path resolution optimization
    metadata={
        "source": "Materials Project API",
        "api_version": "v2025", 
        "fetch_date": "2025-08-22",
        "license": "CC-BY-4.0"
    }
)
# Handles redirects, validates content, automatic retry on failures
```

#### Advanced Resource Operations

```python
# === ADVANCED OPERATIONS ===

# 1. Resource renaming/moving
rename_success = storage.rename_resource(
    old_storage_key="datasets/experiment_temp.csv",
    new_storage_key="datasets/published/thermal_conductivity_nature_2025.csv"
)

# 2. Bucket management (for supported backends)
bucket_created = storage.create_bucket(
    bucket_name="polymer-research-archive",
    allow_override=False
)

# 3. Cross-backend resource validation
validation_report = storage.validate_bucket_structure()
# Returns: {
#   "local": {"datasets": "present", "models": "present", ...},
#   "s3": {"datasets": "present", "models": "missing"},  
#   "appwrite": {"datasets": "present", "models": "present"},
#   "inconsistencies": ["models bucket missing on s3"],
#   "recommendations": ["Run create_standard_buckets() to fix"]
# }

# 4. Comprehensive system diagnostics
system_info = storage.get_storage_info()
# Returns: {
#   "primary_backend": "local",
#   "active_backends": ["local", "s3", "appwrite"],
#   "strategy": "failover",
#   "total_resources": 1247,
#   "total_size_gb": 45.7,
#   "backend_health": {"local": "healthy", "s3": "healthy", "appwrite": "degraded"}
# }
```

### 2. StorageClient (`storage_client.py`) - Backend Orchestration

The `StorageClient` provides the **backend orchestration engine** that manages multiple storage providers with sophisticated routing strategies.

#### Multi-Backend Routing Strategies

**Strategy 1: Primary (Single Backend)**
```python
# Configuration: STORAGE_STRATEGY=primary
# Best for: Development, single-system deployments

# Behavior:
storage.add_resource("data.csv", content)      # → Writes to primary backend only
storage.get_resource("data.csv")               # → Reads from primary backend only
storage.list_resources()                       # → Lists from primary backend only

# Characteristics:
# ✅ Fastest performance (no cross-backend coordination)
# ✅ Simplest configuration and debugging
# ❌ No redundancy or backup protection
# ❌ Single point of failure
```

**Strategy 2: Replica (Multi-Backend with Read Optimization)**
```python
# Configuration: STORAGE_STRATEGY=replica
# Best for: Read-heavy workloads with backup needs

# Behavior:
storage.add_resource("data.csv", content)      # → Writes to ALL backends (best effort)
storage.get_resource("data.csv")               # → Primary first, fallback to others
storage.list_resources()                       # → Aggregates ALL backends, deduplicates
storage.resource_exists("data.csv")            # → Returns True if exists on ANY backend

# Example result aggregation:
# Local backend: ["file1.csv", "file2.json"]
# S3 backend: ["file1.csv", "file3.pdf"]  
# Appwrite: ["file2.json", "file4.xml"]
# Final result: ["file1.csv", "file2.json", "file3.pdf", "file4.xml"]

# Characteristics:
# ✅ Read optimization with intelligent fallback
# ✅ Backup redundancy for data protection
# ✅ Complete resource visibility across all backends
# ⚠️ Potential consistency delays between backends
# ⚠️ More complex error scenarios
```

**Strategy 3: Failover (High Availability)**
```python
# Configuration: STORAGE_STRATEGY=failover
# Best for: Critical systems requiring maximum uptime

# Behavior:
storage.add_resource("data.csv", content)      # → Try backends in order until success
storage.get_resource("data.csv")               # → Try backends in failover order
storage.list_resources()                       # → Aggregate from ALL available backends

# Backend priority example:
# Primary: local (fast access)
# Secondary: s3 (reliable cloud)  
# Tertiary: appwrite (backup cloud)

# Failover sequence for writes:
# 1. Try local → Success: Complete
# 2. Try local → Fail → Try S3 → Success: Complete (log warning)
# 3. Try local → Fail → Try S3 → Fail → Try Appwrite → Success: Complete (log error)

# Characteristics:
# ✅ Maximum uptime and availability
# ✅ Automatic recovery from backend failures
# ✅ Complete resource visibility
# ❌ No load balancing for writes
# ⚠️ Slower performance during backend failures
```

**Strategy 4: Sync (Maximum Reliability)**
```python
# Configuration: STORAGE_STRATEGY=sync
# Best for: Mission-critical data requiring absolute durability

# Behavior:
storage.add_resource("data.csv", content)      # → Must succeed on ALL backends
storage.get_resource("data.csv")               # → Try all backends until success
storage.list_resources()                       # → Aggregate ALL backends with deduplication
storage.delete_resource("data.csv")            # → Delete from ALL backends

# Write operation:
# 1. Validate all backends are available
# 2. Begin write to all backends simultaneously  
# 3. If ANY backend fails → Rollback all writes → Report failure
# 4. Only succeed if ALL backends confirm write success

# Characteristics:
# ✅ Maximum data durability guarantee
# ✅ Complete resource visibility across all backends
# ✅ Zero data loss risk
# ❌ Slower write performance (synchronous cross-backend)
# ❌ Write operations fail if ANY backend is unavailable
# 💡 Use for critical research data that cannot be lost
```

#### Backend Performance Monitoring

```python
# Comprehensive performance analysis
performance_report = storage.get_strategy_performance_report()

# Example output:
{
  "strategy": "failover",
  "active_backends": ["local", "s3", "appwrite"],
  "performance_metrics": {
    "average_write_latency_ms": 150,
    "average_read_latency_ms": 45,
    "success_rate": 0.987,
    "bandwidth_utilization": "moderate"
  },
  "reliability_assessment": {
    "data_durability_score": 0.95,
    "availability_score": 0.99,
    "consistency_score": 0.92
  },
  "recommendations": [
    "Consider switching to 'sync' strategy for critical datasets",
    "S3 backend showing occasional timeouts - investigate network",
    "Local backend at 85% capacity - consider cleanup or expansion"
  ],
  "optimization_opportunities": [
    "Enable S3 transfer acceleration for large files",
    "Implement local caching for frequently accessed models",
    "Configure Appwrite CDN for global read optimization"
  ]
}
```

## Supported Storage Backends

### 1. Local Filesystem Backend

**Best for**: Development, single-system deployments, high-speed local access

```python
# Configuration
STORAGE_BACKEND=local
STORAGE_PATH=/home/user/polymer_data
STORAGE_BACKENDS_ACTIVE=local

# Characteristics:
# ✅ Zero latency access for local operations
# ✅ No network dependencies
# ✅ Simple debugging and direct file access
# ✅ Cost-free storage
# ❌ No built-in redundancy
# ❌ Limited to single system
# ❌ No automatic backup or versioning

# File structure:
# /home/user/polymer_data/
# ├── datasets/
# │   ├── thermal_conductivity_study.csv
# │   └── mechanical_properties.json
# ├── models/
# │   ├── bert_polymer_v2.bin
# │   └── ensemble_tokenizer.json
# └── reports/
#     ├── evaluation_metrics.csv
#     └── analysis_summary.pdf
```

### 2. Amazon S3 Backend

**Best for**: Production deployments, large-scale data, enterprise requirements

```python
# Configuration
S3_ENABLED=true
S3_REGION=us-west-2
S3_ACCESS_KEY_ID=your_access_key
S3_SECRET_ACCESS_KEY=your_secret_key
S3_ENDPOINT_URL=https://s3.us-west-2.amazonaws.com  # Optional for S3-compatible services

# Advanced S3 features supported:
# - Bucket versioning for data protection
# - Lifecycle policies for cost optimization
# - Server-side encryption for data security
# - Transfer acceleration for global access
# - Cross-region replication for disaster recovery

# Example usage with S3-specific features:
storage.add_resource(
    "datasets/large_polymer_database.parquet",
    large_dataset_content,
    metadata={
        "storage_class": "STANDARD_IA",  # Infrequent Access for cost savings
        "encryption": "AES256",
        "backup_policy": "cross_region"
    }
)

# Characteristics:
# ✅ Virtually unlimited storage capacity
# ✅ Enterprise-grade durability (99.999999999%)
# ✅ Global accessibility and CDN integration
# ✅ Advanced security and compliance features
# ✅ Cost-effective storage classes
# ⚠️ Network latency for access
# ⚠️ Ongoing costs based on usage
# ⚠️ Requires AWS account and configuration
```

### 3. Appwrite Cloud Backend

**Best for**: Rapid deployment, managed infrastructure, developer-friendly workflows

```python
# Configuration
APPWRITE_ENABLED=true
APPWRITE_STORAGE_ENDPOINT=https://cloud.appwrite.io/v1
APPWRITE_STORAGE_PROJECT_ID=your_project_id
APPWRITE_STORAGE_API_KEY=your_api_key

# Appwrite-specific advantages:
# - Built-in user management integration
# - Real-time synchronization capabilities
# - Automatic CDN and global distribution
# - Generous free tier for development
# - Simple pricing model

# Example Appwrite integration:
storage.add_resource(
    "shared/community_polymer_dataset.json",
    community_data,
    metadata={
        "access_level": "public",
        "community_contribution": True,
        "license": "CC-BY-4.0",
        "contributors": ["researcher_alice", "researcher_bob"]
    }
)

# Characteristics:
# ✅ Managed infrastructure (no server maintenance)
# ✅ Built-in collaboration features
# ✅ Automatic scaling and CDN
# ✅ Developer-friendly API and dashboard
# ✅ Real-time features for collaborative research
# ⚠️ Platform dependency
# ⚠️ Less customizable than S3
# ⚠️ Smaller ecosystem compared to AWS
```

## Extending Storage Backends

### Adding Custom Storage Backends

The storage architecture is designed for easy extension. Here's how to add support for a **custom Ubuntu file hosting server**:

#### Step 1: Implement the StorageBackend Interface

```python
# File: polymer_extractor/storage/backends/ubuntu_server_backend.py

import requests
import os
from typing import Dict, Any, List, Optional
from polymer_extractor.storage.storage_client import StorageBackend

class UbuntuServerBackend(StorageBackend):
    """
    Storage backend for Ubuntu file hosting server.
    
    Supports RESTful file operations over HTTP/HTTPS with the following API:
    - POST /api/files/{path} - Upload file
    - GET /api/files/{path} - Download file  
    - DELETE /api/files/{path} - Delete file
    - GET /api/files/list?folder={folder} - List files
    - HEAD /api/files/{path} - Check existence
    - GET /api/files/{path}/metadata - Get file metadata
    """
    
    def __init__(self, base_url: str, api_key: str, verify_ssl: bool = True):
        """
        Initialize Ubuntu server backend.
        
        Parameters
        ----------
        base_url : str
            Base URL of the file server (e.g., "https://files.university.edu")
        api_key : str
            Authentication API key for the server
        verify_ssl : bool
            Whether to verify SSL certificates (default: True)
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "PolymerNLP-Extractor/1.0"
        })
    
    def upload(self, storage_key: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Upload file to Ubuntu server."""
        url = f"{self.base_url}/api/files/{storage_key}"
        
        files = {"file": (os.path.basename(storage_key), content)}
        data = {"metadata": json.dumps(metadata or {})}
        
        response = self.session.post(url, files=files, data=data, verify=self.verify_ssl)
        response.raise_for_status()
        
        result = response.json()
        return {
            "success": True,
            "storage_key": storage_key,
            "size_bytes": len(content),
            "server_response": result,
            "upload_time": result.get("upload_time"),
            "file_id": result.get("file_id")
        }
    
    def download(self, storage_key: str) -> bytes:
        """Download file from Ubuntu server."""
        url = f"{self.base_url}/api/files/{storage_key}"
        
        response = self.session.get(url, verify=self.verify_ssl)
        response.raise_for_status()
        
        return response.content
    
    def delete(self, storage_key: str) -> bool:
        """Delete file from Ubuntu server."""
        url = f"{self.base_url}/api/files/{storage_key}"
        
        response = self.session.delete(url, verify=self.verify_ssl)
        return response.status_code == 200
    
    def list_files(self, folder: str = "") -> List[Dict[str, Any]]:
        """List files in Ubuntu server directory."""
        url = f"{self.base_url}/api/files/list"
        params = {"folder": folder} if folder else {}
        
        response = self.session.get(url, params=params, verify=self.verify_ssl)
        response.raise_for_status()
        
        files_data = response.json()
        return [
            {
                "storage_key": file_info["path"],
                "size_bytes": file_info["size"],
                "content_type": file_info.get("content_type", "application/octet-stream"),
                "last_modified": file_info["modified_time"],
                "backend": "ubuntu_server"
            }
            for file_info in files_data.get("files", [])
        ]
    
    def exists(self, storage_key: str) -> bool:
        """Check if file exists on Ubuntu server."""
        url = f"{self.base_url}/api/files/{storage_key}"
        
        response = self.session.head(url, verify=self.verify_ssl)
        return response.status_code == 200
    
    def get_metadata(self, storage_key: str) -> Dict[str, Any]:
        """Get file metadata from Ubuntu server."""
        url = f"{self.base_url}/api/files/{storage_key}/metadata"
        
        response = self.session.get(url, verify=self.verify_ssl)
        response.raise_for_status()
        
        metadata = response.json()
        return {
            "size_bytes": metadata["size"],
            "content_type": metadata.get("content_type", "application/octet-stream"),
            "created_at": metadata["created_time"],
            "last_modified": metadata["modified_time"], 
            "backend": "ubuntu_server",
            "storage_key": storage_key,
            "server_metadata": metadata.get("custom_metadata", {}),
            "checksum": metadata.get("md5_hash"),
            "server_location": metadata.get("server_location")
        }
    
    # Bucket operations (if Ubuntu server supports directories)
    def create_bucket(self, bucket_name: str) -> Dict[str, Any]:
        """Create directory on Ubuntu server."""
        url = f"{self.base_url}/api/directories/{bucket_name}"
        
        response = self.session.post(url, verify=self.verify_ssl)
        response.raise_for_status()
        
        return {
            "bucket_name": bucket_name,
            "created": True,
            "backend": "ubuntu_server"
        }
    
    def delete_bucket(self, bucket_name: str) -> bool:
        """Delete directory from Ubuntu server."""
        url = f"{self.base_url}/api/directories/{bucket_name}"
        
        response = self.session.delete(url, verify=self.verify_ssl)
        return response.status_code == 200
    
    def list_buckets(self) -> List[Dict[str, Any]]:
        """List directories on Ubuntu server."""
        url = f"{self.base_url}/api/directories"
        
        response = self.session.get(url, verify=self.verify_ssl)
        response.raise_for_status()
        
        directories = response.json()
        return [
            {
                "name": dir_info["name"],
                "created_at": dir_info["created_time"],
                "file_count": dir_info.get("file_count", 0),
                "total_size_bytes": dir_info.get("total_size", 0)
            }
            for dir_info in directories.get("directories", [])
        ]
    
    def rename_resource(self, old_storage_key: str, new_storage_key: str) -> bool:
        """Rename/move file on Ubuntu server."""
        url = f"{self.base_url}/api/files/{old_storage_key}/move"
        data = {"new_path": new_storage_key}
        
        response = self.session.post(url, json=data, verify=self.verify_ssl)
        return response.status_code == 200
    
    def rename_bucket(self, old_bucket_name: str, new_bucket_name: str) -> bool:
        """Rename directory on Ubuntu server."""
        url = f"{self.base_url}/api/directories/{old_bucket_name}/rename"
        data = {"new_name": new_bucket_name}
        
        response = self.session.post(url, json=data, verify=self.verify_ssl)
        return response.status_code == 200
```

#### Step 2: Register the Backend

```python
# File: polymer_extractor/storage/storage_client.py

# Add Ubuntu server backend support
from polymer_extractor.storage.backends.ubuntu_server_backend import UbuntuServerBackend

class StorageClient:
    def __init__(self):
        # ... existing code ...
        
        # Add Ubuntu server backend initialization
        if "ubuntu_server" in self.active_backends:
            ubuntu_backend = self._create_ubuntu_server_backend()
            self.backends["ubuntu_server"] = ubuntu_backend
    
    def _create_ubuntu_server_backend(self) -> UbuntuServerBackend:
        """Create Ubuntu server backend from environment configuration."""
        base_url = os.getenv("UBUNTU_SERVER_BASE_URL")
        api_key = os.getenv("UBUNTU_SERVER_API_KEY")
        verify_ssl = os.getenv("UBUNTU_SERVER_VERIFY_SSL", "true").lower() == "true"
        
        if not base_url or not api_key:
            raise ConfigError("Ubuntu server backend requires UBUNTU_SERVER_BASE_URL and UBUNTU_SERVER_API_KEY")
        
        return UbuntuServerBackend(
            base_url=base_url,
            api_key=api_key,
            verify_ssl=verify_ssl
        )
```

#### Step 3: Environment Configuration

```bash
# Add to .env file for Ubuntu server backend
UBUNTU_SERVER_ENABLED=true
UBUNTU_SERVER_BASE_URL=https://files.polymer-research.university.edu
UBUNTU_SERVER_API_KEY=your_server_api_key
UBUNTU_SERVER_VERIFY_SSL=true

# Include in active backends
STORAGE_BACKENDS_ACTIVE=local,ubuntu_server,s3
STORAGE_STRATEGY=failover
```

#### Step 4: Usage Examples

```python
# Ubuntu server now fully integrated into storage system
from polymer_extractor.storage.storage_manager import get_storage_manager

storage = get_storage_manager()

# Upload to Ubuntu file server (automatically routed based on strategy)
upload_result = storage.upload_from_path(
    source_path="/local/polymer_research/experiment_results.csv",
    dest_storage_key="research_data/2025/thermal_conductivity/experiment_001.csv",
    metadata={
        "experiment_id": "TC_001", 
        "researcher": "Dr. Alice Chen",
        "institution": "University Polymer Lab",
        "equipment": "DSC Q2000",
        "temperature_range": "25-300C"
    }
)

# Download from Ubuntu server with automatic failover
experiment_data = storage.get_resource("research_data/2025/thermal_conductivity/experiment_001.csv")

# List all polymer research data across all backends (including Ubuntu server)
research_files = storage.list_resources("research_data/2025")

# Backend-specific information shows Ubuntu server integration
storage_info = storage.get_storage_info()
# {
#   "primary_backend": "local",
#   "active_backends": ["local", "ubuntu_server", "s3"],
#   "strategy": "failover",
#   "backend_health": {
#     "local": "healthy",
#     "ubuntu_server": "healthy", 
#     "s3": "healthy"
#   }
# }
```

### Advanced Ubuntu Server Features

```python
# Additional Ubuntu server integration features

class UbuntuServerBackend(StorageBackend):
    def get_server_status(self) -> Dict[str, Any]:
        """Get Ubuntu server health and capacity information."""
        url = f"{self.base_url}/api/status"
        
        response = self.session.get(url, verify=self.verify_ssl)
        response.raise_for_status()
        
        status = response.json()
        return {
            "server_health": status["health"],
            "disk_usage_percent": status["disk_usage"],
            "available_space_gb": status["available_space"] / (1024**3),
            "active_connections": status["active_connections"],
            "uptime_hours": status["uptime_seconds"] / 3600,
            "api_version": status["api_version"]
        }
    
    def create_shared_link(self, storage_key: str, expires_hours: int = 24) -> Dict[str, Any]:
        """Create shareable link for collaboration."""
        url = f"{self.base_url}/api/files/{storage_key}/share"
        data = {"expires_hours": expires_hours}
        
        response = self.session.post(url, json=data, verify=self.verify_ssl)
        response.raise_for_status()
        
        share_info = response.json()
        return {
            "share_url": share_info["share_url"],
            "expires_at": share_info["expires_at"],
            "access_count": share_info.get("access_count", 0),
            "share_id": share_info["share_id"]
        }
    
    def backup_to_local(self, storage_key: str, local_backup_path: str) -> bool:
        """Create local backup of server file."""
        content = self.download(storage_key)
        
        os.makedirs(os.path.dirname(local_backup_path), exist_ok=True)
        with open(local_backup_path, 'wb') as f:
            f.write(content)
        
        return True
    
    def sync_with_local(self, local_folder: str, server_folder: str) -> Dict[str, Any]:
        """Synchronize local folder with server folder."""
        # Implementation for bidirectional sync
        sync_results = {
            "uploaded": [],
            "downloaded": [],
            "conflicts": [],
            "errors": []
        }
        
        # Compare local and server file lists
        local_files = self._get_local_files(local_folder)
        server_files = {f["storage_key"]: f for f in self.list_files(server_folder)}
        
        # Sync logic implementation...
        
        return sync_results
```

## Ensemble Learning Integration

### Storage for Model Management

The storage system provides **specialized support for ensemble learning workflows** with comprehensive model lifecycle management:

```python
# === MODEL STORAGE AND VERSIONING ===

def store_ensemble_models(storage: StorageManager):
    """Store ensemble models with versioning and metadata."""
    
    # Store individual models with comprehensive metadata
    models = [
        ("models/ensemble/bert_polymer_v2.1.bin", bert_model_data, {
            "model_type": "transformer",
            "architecture": "BERT-base",
            "training_dataset": "polymer_abstracts_v2025",
            "performance_metrics": {
                "accuracy": 0.94,
                "f1_score": 0.91,
                "precision": 0.93,
                "recall": 0.89
            },
            "hyperparameters": {
                "learning_rate": 2e-5,
                "batch_size": 16,
                "epochs": 10,
                "warmup_steps": 500
            },
            "specialized_for": ["thermal_conductivity", "glass_transition"],
            "polymer_types": ["thermoplastics", "thermosets"]
        }),
        
        ("models/ensemble/roberta_ensemble_v1.3.bin", roberta_model_data, {
            "model_type": "transformer", 
            "architecture": "RoBERTa-base",
            "training_dataset": "polymer_papers_full_v2025",
            "performance_metrics": {
                "accuracy": 0.92,
                "f1_score": 0.90,
                "precision": 0.91,
                "recall": 0.89
            },
            "specialized_for": ["mechanical_properties", "chemical_structure"],
            "polymer_types": ["composites", "bio_polymers"]
        }),
        
        ("models/ensemble/distilbert_fast_v1.0.bin", distilbert_model_data, {
            "model_type": "transformer",
            "architecture": "DistilBERT", 
            "training_dataset": "polymer_abstracts_distilled",
            "performance_metrics": {
                "accuracy": 0.89,
                "f1_score": 0.87,
                "inference_speed_ms": 12,  # Fast inference
                "model_size_mb": 108
            },
            "specialized_for": ["real_time_classification"],
            "use_case": "quick_screening"
        })
    ]
    
    # Store models with atomic operations
    for storage_key, model_data, metadata in models:
        result = storage.add_resource(storage_key, model_data, metadata)
        print(f"Stored {storage_key}: {result['size_bytes']} bytes")

def store_ensemble_configuration(storage: StorageManager):
    """Store ensemble configuration and weights."""
    
    ensemble_config = {
        "ensemble_strategy": "weighted_voting",
        "model_weights": {
            "bert_polymer_v2.1": 0.4,      # Highest weight for best performer
            "roberta_ensemble_v1.3": 0.35,  # Strong general performance  
            "distilbert_fast_v1.0": 0.25    # Speed specialist
        },
        "confidence_thresholds": {
            "thermal_conductivity": 0.85,
            "mechanical_properties": 0.88,
            "chemical_structure": 0.82,
            "glass_transition": 0.90
        },
        "fallback_strategy": "best_confidence",
        "voting_mechanism": "weighted_probability",
        "created_date": "2025-08-22",
        "validation_dataset": "polymer_test_set_v2025"
    }
    
    storage.add_resource(
        "models/ensemble/ensemble_config_v2.1.json",
        json.dumps(ensemble_config, indent=2).encode(),
        metadata={
            "config_type": "ensemble_configuration",
            "version": "2.1",
            "models_count": 3,
            "strategy": "weighted_voting",
            "validation_accuracy": 0.945
        }
    )
```

### Training Data Management

```python
# === TRAINING DATA LIFECYCLE ===

def manage_training_datasets(storage: StorageManager):
    """Comprehensive training data management for ensemble models."""
    
    # Store processed training datasets
    training_datasets = [
        {
            "storage_key": "datasets/training/polymer_abstracts_processed_v2025.parquet",
            "content": processed_abstracts_data,
            "metadata": {
                "dataset_type": "training",
                "processing_pipeline": "polymer_nlp_v2.1",
                "source_papers": 15000,
                "entity_types": ["polymer_name", "property", "value", "condition"],
                "annotation_quality": 0.96,
                "inter_annotator_agreement": 0.92,
                "size_mb": 245.7,
                "format": "Apache Parquet",
                "columns": ["text", "entities", "labels", "confidence"]
            }
        },
        
        {
            "storage_key": "datasets/validation/polymer_validation_v2025.json",
            "content": validation_data,
            "metadata": {
                "dataset_type": "validation",
                "holdout_percentage": 15,
                "stratified_sampling": True,
                "polymer_categories": ["thermoplastic", "thermoset", "composite", "bio_polymer"],
                "property_coverage": {
                    "thermal": 0.85,
                    "mechanical": 0.90,
                    "electrical": 0.75,
                    "chemical": 0.88
                }
            }
        },
        
        {
            "storage_key": "datasets/test/polymer_benchmark_2025.json", 
            "content": test_data,
            "metadata": {
                "dataset_type": "test",
                "benchmark_version": "2025.1",
                "test_cases": 2000,
                "difficulty_distribution": {
                    "easy": 0.3,
                    "medium": 0.5, 
                    "hard": 0.2
                },
                "evaluation_metrics": ["accuracy", "f1", "precision", "recall", "confidence_calibration"]
            }
        }
    ]
    
    # Store datasets with comprehensive metadata
    for dataset in training_datasets:
        storage.add_resource(
            dataset["storage_key"],
            dataset["content"], 
            dataset["metadata"]
        )

def store_feature_extractors(storage: StorageManager):
    """Store feature extraction components for ensemble."""
    
    # Tokenizers for different models
    tokenizers = [
        ("models/tokenizers/bert_polymer_tokenizer.json", bert_tokenizer_data, {
            "tokenizer_type": "BertTokenizer",
            "vocab_size": 30522,
            "special_tokens": ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"],
            "polymer_specific_tokens": 1250,
            "max_sequence_length": 512
        }),
        
        ("models/tokenizers/roberta_ensemble_tokenizer.json", roberta_tokenizer_data, {
            "tokenizer_type": "RobertaTokenizer", 
            "vocab_size": 50265,
            "byte_level": True,
            "polymer_specific_tokens": 2100,
            "chemical_notation_support": True
        })
    ]
    
    for storage_key, tokenizer_data, metadata in tokenizers:
        storage.add_resource(storage_key, tokenizer_data, metadata)
    
    # Store preprocessing pipelines
    preprocessing_config = {
        "text_normalization": {
            "lowercase": False,  # Preserve chemical notation case
            "remove_punctuation": False,  # Chemical formulas need punctuation
            "expand_abbreviations": True,
            "standardize_units": True
        },
        "chemical_notation": {
            "parse_formulas": True,
            "standardize_naming": True,
            "resolve_synonyms": True
        },
        "entity_preprocessing": {
            "numerical_value_normalization": True,
            "unit_conversion": "SI_standard",
            "temperature_scale": "celsius_kelvin_both"
        }
    }
    
    storage.add_resource(
        "models/preprocessing/pipeline_config_v2.1.json",
        json.dumps(preprocessing_config, indent=2).encode(),
        metadata={
            "pipeline_version": "2.1",
            "compatible_models": ["bert_polymer", "roberta_ensemble", "distilbert_fast"],
            "preprocessing_steps": 12,
            "chemical_notation_parser": "RDKit_integrated"
        }
    )
```

### Results and Analytics Storage

```python
# === RESULTS MANAGEMENT ===

def store_extraction_results(storage: StorageManager, session_id: str):
    """Store comprehensive extraction results with analytics."""
    
    extraction_results = {
        "session_id": session_id,
        "extraction_timestamp": "2025-08-22T14:30:45Z",
        "ensemble_configuration": "weighted_voting_v2.1",
        "papers_processed": 50,
        "total_entities_extracted": 2847,
        "extraction_statistics": {
            "by_entity_type": {
                "polymer_name": 892,
                "thermal_property": 567,
                "mechanical_property": 634,
                "electrical_property": 289,
                "chemical_structure": 465
            },
            "by_confidence_range": {
                "high_confidence_0.9_1.0": 1820,
                "medium_confidence_0.7_0.9": 847,
                "low_confidence_0.5_0.7": 180
            },
            "model_contributions": {
                "bert_polymer_v2.1": 1435,      # 50.4% of extractions
                "roberta_ensemble_v1.3": 1128,  # 39.6% of extractions
                "distilbert_fast_v1.0": 284     # 10.0% of extractions
            }
        },
        "quality_metrics": {
            "average_confidence": 0.847,
            "agreement_rate": 0.923,  # Rate where multiple models agree
            "validation_accuracy": 0.915,
            "processing_time_seconds": 342.7
        },
        "detailed_results": [
            {
                "paper_id": "10.1234/polymer.2025.001",
                "title": "Thermal Conductivity of Novel Polyimide Composites",
                "entities": [
                    {
                        "text": "polyimide",
                        "label": "polymer_name",
                        "confidence": 0.96,
                        "start_char": 45,
                        "end_char": 54,
                        "contributing_models": ["bert_polymer", "roberta_ensemble"]
                    },
                    {
                        "text": "thermal conductivity: 0.25 W/m·K",
                        "label": "thermal_property",
                        "confidence": 0.89,
                        "start_char": 78,
                        "end_char": 111,
                        "normalized_value": {"value": 0.25, "unit": "W/m·K", "property": "thermal_conductivity"}
                    }
                ],
                "processing_metadata": {
                    "extraction_time_ms": 156,
                    "model_agreement": 0.92,
                    "entities_count": 23
                }
            }
            # ... more papers
        ]
    }
    
    # Store results with session context
    storage.add_resource(
        f"results/sessions/{session_id}/extraction_results.json",
        json.dumps(extraction_results, indent=2).encode(),
        metadata={
            "result_type": "ensemble_extraction",
            "session_id": session_id,
            "papers_count": 50,
            "entities_count": 2847,
            "ensemble_version": "2.1",
            "quality_score": 0.915
        }
    )
    
    # Store analytics summary
    analytics_summary = {
        "session_summary": {
            "total_extractions": 2847,
            "processing_efficiency": "5.73 entities/second",
            "model_performance_ranking": [
                {"model": "bert_polymer_v2.1", "accuracy": 0.94, "contribution": "50.4%"},
                {"model": "roberta_ensemble_v1.3", "accuracy": 0.92, "contribution": "39.6%"},
                {"model": "distilbert_fast_v1.0", "accuracy": 0.89, "contribution": "10.0%"}
            ]
        },
        "quality_assessment": {
            "high_confidence_extractions": 1820,
            "requires_manual_review": 180,
            "estimated_accuracy": 0.915,
            "recommended_confidence_threshold": 0.78
        },
        "recommendations": [
            "Increase BERT model weight to 0.45 for thermal property extraction",
            "Consider adding domain-specific post-processing for chemical structures",
            "Manual review recommended for 180 low-confidence extractions"
        ]
    }
    
    storage.add_resource(
        f"analytics/sessions/{session_id}/performance_summary.json",
        json.dumps(analytics_summary, indent=2).encode(),
        metadata={
            "analytics_type": "session_performance",
            "session_id": session_id,
            "generated_at": "2025-08-22T14:35:12Z",
            "ensemble_efficiency": 0.915
        }
    )

def export_results_for_publication(storage: StorageManager, session_id: str):
    """Export results in publication-ready formats."""
    
    # Get extraction results
    results_data = storage.get_resource(f"results/sessions/{session_id}/extraction_results.json")
    results = json.loads(results_data.decode())
    
    # Create CSV export for data analysis
    csv_data = []
    for paper in results["detailed_results"]:
        for entity in paper["entities"]:
            csv_data.append({
                "paper_id": paper["paper_id"],
                "paper_title": paper["title"],
                "entity_text": entity["text"],
                "entity_label": entity["label"],
                "confidence": entity["confidence"],
                "normalized_value": entity.get("normalized_value", {}),
                "contributing_models": ",".join(entity["contributing_models"])
            })
    
    # Convert to CSV
    csv_content = pandas.DataFrame(csv_data).to_csv(index=False)
    
    storage.add_resource(
        f"exports/sessions/{session_id}/extraction_data.csv",
        csv_content.encode(),
        metadata={
            "export_type": "csv_data",
            "session_id": session_id,
            "format": "CSV",
            "rows": len(csv_data),
            "suitable_for": ["statistical_analysis", "visualization", "publication"]
        }
    )
    
    # Create summary report
    report_content = f"""
# Polymer Property Extraction Report - Session {session_id}

## Overview
- **Papers Processed**: {results['papers_processed']}
- **Total Entities Extracted**: {results['total_entities_extracted']}
- **Average Confidence**: {results['quality_metrics']['average_confidence']:.3f}
- **Processing Time**: {results['quality_metrics']['processing_time_seconds']:.1f} seconds

## Model Performance
{chr(10).join([f"- **{model}**: {count} extractions" for model, count in results['extraction_statistics']['model_contributions'].items()])}

## Entity Distribution
{chr(10).join([f"- **{entity_type}**: {count} instances" for entity_type, count in results['extraction_statistics']['by_entity_type'].items()])}

## Quality Assessment
- **High Confidence (>0.9)**: {results['extraction_statistics']['by_confidence_range']['high_confidence_0.9_1.0']} entities
- **Medium Confidence (0.7-0.9)**: {results['extraction_statistics']['by_confidence_range']['medium_confidence_0.7_0.9']} entities
- **Requires Review (<0.7)**: {results['extraction_statistics']['by_confidence_range']['low_confidence_0.5_0.7']} entities

Generated by Polymer NLP Extractor v2.1 on {results['extraction_timestamp']}
"""
    
    storage.add_resource(
        f"exports/sessions/{session_id}/extraction_report.md",
        report_content.encode(),
        metadata={
            "export_type": "markdown_report",
            "session_id": session_id,
            "format": "Markdown",
            "suitable_for": ["documentation", "publication", "sharing"]
        }
    )
```

## Production Deployment Strategies

### Multi-Environment Configuration

```python
# === DEVELOPMENT ENVIRONMENT ===
# .env.development
STORAGE_BACKEND=local
STORAGE_PATH=./workspace/public
STORAGE_BACKENDS_ACTIVE=local
STORAGE_STRATEGY=primary

# === STAGING ENVIRONMENT ===
# .env.staging  
STORAGE_BACKEND=local
STORAGE_BACKENDS_ACTIVE=local,s3
STORAGE_STRATEGY=replica
S3_ENABLED=true
S3_REGION=us-west-2

# === PRODUCTION ENVIRONMENT ===
# .env.production
STORAGE_BACKEND=s3
STORAGE_BACKENDS_ACTIVE=local,s3,appwrite
STORAGE_STRATEGY=sync
S3_ENABLED=true
APPWRITE_ENABLED=true
UBUNTU_SERVER_ENABLED=true

# Production redundancy: All operations succeed on ALL backends
# Maximum data durability and availability
```

### Performance Optimization

```python
def optimize_storage_performance():
    """Storage performance optimization recommendations."""
    
    storage = get_storage_manager()
    performance_report = storage.get_strategy_performance_report()
    
    print("=== Storage Performance Analysis ===")
    print(f"Current Strategy: {performance_report['strategy']}")
    print(f"Active Backends: {performance_report['active_backends']}")
    print(f"Write Latency: {performance_report['performance_metrics']['average_write_latency_ms']}ms")
    print(f"Read Latency: {performance_report['performance_metrics']['average_read_latency_ms']}ms")
    print(f"Success Rate: {performance_report['performance_metrics']['success_rate']:.1%}")
    
    print("\n=== Optimization Recommendations ===")
    for recommendation in performance_report['recommendations']:
        print(f"• {recommendation}")
    
    print("\n=== Reliability Assessment ===")
    reliability = performance_report['reliability_assessment']
    print(f"Data Durability: {reliability['data_durability_score']:.1%}")
    print(f"Availability: {reliability['availability_score']:.1%}")
    print(f"Consistency: {reliability['consistency_score']:.1%}")
```

The storage architecture provides the foundation for reliable, scalable polymer science data management with enterprise-grade features and seamless extensibility for custom backend integration.
