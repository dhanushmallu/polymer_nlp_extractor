# 02. Project Structure

## Overview

This document provides a comprehensive overview of the Polymer NLP Extractor project structure, file organization, and the purpose of each module. The structure follows a modular architecture with clear separation of concerns between API endpoints, business logic, data persistence, and utilities.

## Root Directory Structure

```
polymer_nlp_extractor/
├── config.json                          # Application configuration settings
├── doc_changelog.md                     # Documentation change tracking
├── docker-compose.services.yml          # Docker services configuration for PostgreSQL, Neo4j, GROBID
├── Dockerfile                           # Container definition for production deployment
├── Procfile                             # Process definitions for deployment platforms
├── pyproject.toml                       # Python project metadata and build configuration
├── README.md                            # Main project documentation and setup guide
├── requirements.txt                     # Python package dependencies
├── server.sh                            # Enhanced server management script with service control
├── server_manager.py                    # Server orchestration and lifecycle management
├── db/                                  # Database schema and migration files
├── docs/                                # Project documentation
├── kg/                                  # Knowledge graph schema and initialization
├── notebooks/                           # Jupyter notebooks for development and analysis
├── polymer_extractor/                   # Core application package
├── postman/                             # API testing collections
├── tests/                               # Test suite
└── workspace/                           # Working directory for data processing
```

## Core Application Structure (`polymer_extractor/`)

### Main Application Files

```
polymer_extractor/
├── __init__.py                          # Package initialization and version info
├── main.py                              # FastAPI application entry point and routing setup
└── model_config.py                      # Central model configurations and ensemble settings
```

**Purpose**: Core application entry points and configuration management.

- **main.py**: Defines the FastAPI application, includes all API routers, manages application lifespan, and handles service connectivity checks
- **model_config.py**: Centralizes all model-related configurations, ensemble strategies, and processing thresholds

### API Layer (`api/`)

```
api/
├── __init__.py                          # API package initialization
├── documentation.py                     # Project documentation API endpoints
├── ensemble_inference.py               # Ensemble model inference endpoints
├── evaluation.py                        # Model evaluation and performance assessment APIs
├── grobid.py                            # PDF to XML conversion API using GROBID service
├── groundtruth.py                       # Ground truth data management endpoints
├── models_sync.py                       # Model synchronization and GitHub integration APIs
├── preprocessing.py                     # Data preprocessing and cleaning endpoints
├── session.py                           # User and session management endpoints
└── setup.py                            # System initialization and configuration APIs
```

**Purpose**: FastAPI endpoint definitions and request/response handling.

- **documentation.py**: Serves project documentation files with multiple output formats (Markdown, HTML, raw)
- **ensemble_inference.py**: Handles ensemble model predictions and entity extraction requests
- **evaluation.py**: Provides model performance evaluation and metrics calculation endpoints
- **grobid.py**: Manages PDF document processing and TEI XML conversion using GROBID service
- **groundtruth.py**: Handles ground truth dataset uploads, validation, and management
- **models_sync.py**: Manages model downloads from GitHub and version synchronization
- **preprocessing.py**: Provides text preprocessing, cleaning, and normalization endpoints
- **session.py**: Manages user accounts, session creation, and multi-user workflow coordination
- **setup.py**: Handles system initialization, health checks, and configuration management

### Configuration (`config/`)

```
config/
└── production_config.py                 # Production environment configuration profiles
```

**Purpose**: Environment-specific configuration management and validation.

### Business Logic Layer (`services/`)

```
services/
├── __init__.py                          # Services package initialization
├── bucket_manager.py                    # File bucket operations and storage coordination
├── enhanced_merging_service.py          # Advanced entity merging with TEI alignment
├── ensemble_inference_service.py        # Core ensemble inference engine with semantic boosting
├── evaluation_service.py                # Model evaluation and metrics calculation logic
├── grobid_service.py                    # GROBID integration for PDF processing
├── groundtruth_service.py               # Ground truth data processing and validation logic
├── models_sync_service.py               # GitHub-based model synchronization service
├── schema_definitions.py               # Database schema definitions and validation
├── setup_service.py                     # System initialization and configuration logic
├── tei_processing_service.py            # TEI XML processing and sentence extraction
├── token_packing_service.py             # Tokenization and sequence packing for model input
└── constants/                           # Domain-specific constants and lookup tables
```

**Purpose**: Core business logic, data processing, and domain-specific operations.

- **enhanced_merging_service.py**: Implements sophisticated entity merging algorithms with deduplication
- **ensemble_inference_service.py**: Orchestrates multiple ML models for robust entity extraction
- **evaluation_service.py**: Calculates performance metrics and provides model assessment tools
- **grobid_service.py**: Integrates with GROBID service for scientific PDF processing
- **groundtruth_service.py**: Processes and validates ground truth datasets for training/evaluation
- **models_sync_service.py**: Manages model downloads and version consistency from GitHub repositories
- **setup_service.py**: Handles system initialization, database setup, and health monitoring
- **tei_processing_service.py**: Processes TEI XML documents and extracts structured text
- **token_packing_service.py**: Prepares text data for model input with proper tokenization

#### Constants Package (`services/constants/`)

```
constants/
├── __init__.py                          # Constants package initialization
├── configuration_constants.py          # System configuration constants and content markers
├── greek_letters.py                    # Greek letter mappings for scientific notation
├── polymer_names.py                    # Comprehensive polymer name database
├── property_names.py                   # Material property names and terminology
├── property_table.py                   # Standard property-value-unit relationships
├── scientific_symbols.py               # Scientific symbols and mathematical notation
├── scientific_units.py                 # Comprehensive units database with SI conversions
├── templates.py                        # Sentence templates for data augmentation
├── training_constants.py               # Training-specific parameters and configurations
└── value_formats.py                    # Numerical value patterns and format recognition
```

**Purpose**: Centralized domain knowledge and scientific terminology lookup tables.

### Data Persistence Layer (`storage/`)

```
storage/
├── __init__.py                          # Storage package initialization
├── bucket_client.py                    # Universal storage client (local/Appwrite/S3)
├── bucket_manager.py                   # High-level file bucket operations
├── database_manager.py                 # Legacy database operations and compatibility layer
├── exceptions.py                       # Storage-specific exception definitions
├── graph_manager.py                    # Neo4j graph database operations
├── neo4j_client.py                     # Neo4j client for semantic relationships
├── postgresql_client.py                # PostgreSQL client for relational data
├── session_manager.py                  # User session management and resource allocation
├── storage_client.py                   # Storage abstraction layer
└── storage_manager.py                  # Storage backend coordination and routing
```

**Purpose**: Data persistence, database connectivity, and storage backend management.

- **bucket_client.py**: Provides unified interface for file storage across multiple backends
- **database_manager.py**: Maintains backward compatibility during database transition
- **graph_manager.py**: Manages Neo4j operations for semantic relationships and validation
- **neo4j_client.py**: Low-level Neo4j database connectivity and query execution
- **postgresql_client.py**: PostgreSQL connectivity with connection pooling and optimization
- **session_manager.py**: Handles multi-user sessions with resource isolation and lifecycle management
- **storage_manager.py**: Coordinates multiple storage backends with configurable routing strategies

### Repository Pattern (`repositories/`)

```
repositories/
├── __init__.py                          # Repositories package initialization
├── base_repository.py                  # Abstract base repository with common CRUD operations
├── entity_repository.py                # Entity data access and relationship management
├── knowledge_graph_repository.py       # Knowledge graph data access with caching
├── paper_repository.py                 # Research paper metadata storage and retrieval
├── session_repository.py               # Session tracking and analytics
└── validation_repository.py            # Validation results storage and effectiveness tracking
```

**Purpose**: Database abstraction layer implementing repository pattern for clean data access.

- **base_repository.py**: Defines common database operations and abstract interface
- **entity_repository.py**: Handles all entity-related database operations with semantic grouping
- **knowledge_graph_repository.py**: Caches frequently accessed graph relationships with LRU optimization
- **paper_repository.py**: Manages research paper metadata, search, and categorization
- **session_repository.py**: Tracks extraction sessions with performance analytics
- **validation_repository.py**: Stores validation results and provides effectiveness insights

### Knowledge Graph Intelligence (`knowledge_graph/`)

```
knowledge_graph/
├── __init__.py                          # Knowledge graph package initialization
├── kg_canonical_manager.py             # Entity standardization and canonical form management
├── kg_client.py                        # Neo4j integration hub with connection pooling
├── kg_error_pattern_detector.py        # Automated error pattern detection and learning
├── kg_relationship_manager.py          # Relationship pattern management and versioning
├── kg_semantic_analyzer.py             # Enhanced semantic relationship detection
├── kg_threshold_optimizer.py           # Dynamic confidence threshold optimization
└── kg_validator.py                     # Real-time domain validation against constraints
```

**Purpose**: Knowledge graph services for semantic validation, relationship management, and intelligent error detection.

- **kg_canonical_manager.py**: Manages canonical entity forms with aliases and domain-specific rules
- **kg_client.py**: Provides robust Neo4j connectivity with clustering support and retry mechanisms
- **kg_error_pattern_detector.py**: Automatically detects and learns from recurring error patterns
- **kg_relationship_manager.py**: Manages relationship patterns with updates and effectiveness tracking
- **kg_semantic_analyzer.py**: Implements advanced semantic distance calculations and scoring
- **kg_threshold_optimizer.py**: Dynamically optimizes confidence thresholds based on validation feedback
- **kg_validator.py**: Validates entities against comprehensive domain constraints in real-time

### Utilities (`utils/`)

```
utils/
├── __init__.py                          # Utils package initialization
├── logging.py                          # Independent logging system with PostgreSQL integration
├── paths.py                            # Path management and workspace directory utilities
├── resource_lock_manager.py            # Resource locking for concurrent operations
└── responses.py                        # Standardized API response formatting
```

**Purpose**: Utility functions, helpers, and cross-cutting concerns.

- **logging.py**: Provides structured logging with direct PostgreSQL access for system_logs
- **paths.py**: Manages storage paths with logical-to-physical path resolution and normalization
- **resource_lock_manager.py**: Handles resource locking for safe concurrent operations
- **responses.py**: Standardizes API response formats and error handling

## Database Schema (`db/`)

```
db/
└── sql/
    ├── 001_core.sql                     # Core database schema with system_logs table
    ├── 002_multi_user.sql               # Multi-user extensions and session management
    └── 003_session_integration.sql      # Session integration and resource tracking
```

**Purpose**: PostgreSQL schema definitions and database migrations.

## Knowledge Graph Schema (`kg/`)

```
kg/
└── cypher/
    └── 001_constraints.cypher           # Neo4j constraints and index definitions
```

**Purpose**: Neo4j graph database setup and constraint definitions.

## Documentation (`docs/`)

```
docs/
├── 1_introduction.md                    # Project overview, technologies, and methodologies
├── 2_project_structure.md               # This file - project structure documentation
├── 3_how_to_run_this_project.md         # Comprehensive setup and execution guide
├── development_notes.md                 # Development guidelines and security requirements
├── multi_user_architecture.md          # Multi-user production architecture guide
└── multi_user_implementation_summary.md # Implementation status and feature summary
```

**Purpose**: Comprehensive project documentation and architectural guidance.

- **1_introduction.md**: Comprehensive project overview covering core technologies, ensemble learning approach, GROBID integration, Neo4j knowledge graphs, and system methodologies
- **2_project_structure.md**: Detailed codebase organization and architectural documentation
- **3_how_to_run_this_project.md**: Complete setup and execution guide covering environment configuration, GitHub integration, storage backends, and development workflows with emphasis on model-tokenizer compatibility

## Development and Testing

### Notebooks (`notebooks/`)

```
notebooks/
├── model_training_finetuning.ipynb     # Model training and fine-tuning workflows
└── polymer_extractor.ipynb             # Polymer extraction analysis and experimentation
```

**Purpose**: Interactive development, model training, and data analysis.

### API Testing (`postman/`)

```
postman/
├── README.md                            # Postman collections documentation
├── documentation.postman_collection.json # Documentation API test collection
├── grobid.postman_collection.json      # GROBID service test collection
├── models.postman_collection.json      # Model synchronization test collection
├── session.postman_collection.json     # Session management test collection
└── setup.postman_collection.json       # System setup test collection
```

**Purpose**: Comprehensive API testing with pre-configured request collections.

### Test Suite (`tests/`)

```
tests/
├── __init__.py                          # Tests package initialization
├── test_database.py                    # Database functionality testing
├── test_logging.py                     # Logging system testing
├── test_neo4j.py                       # Neo4j integration testing
├── test_setup.py                       # Basic setup service testing
├── test_setup_comprehensive.py         # Comprehensive setup validation
└── test_storage.py                     # Storage system testing
```

**Purpose**: Automated testing suite for application components and integration testing.

## Working Directory (`workspace/`)

```
workspace/
├── public/                              # Default storage path for processed data
│   ├── datasets_dir/                    # Training and evaluation datasets
│   │   ├── testing/                     # Test dataset storage
│   │   ├── testing_dir/                 # Test processing workspace
│   │   ├── training/                    # Training dataset storage
│   │   └── training_dir/                # Training processing workspace
│   ├── downloads/                       # Downloaded files and assets
│   ├── exports_dir/                     # Processed data exports and results
│   ├── extracted_xml_dir/               # GROBID-extracted XML files
│   ├── full_reports_dir/                # Generated analysis reports
│   ├── models/                          # Model artifacts and checkpoints
│   ├── processed_xml_dir/               # Post-processed XML with annotations
│   ├── raw_inputs_dir/                  # Raw input files and documents
│   ├── samples_dir/                     # Sample data for testing and development
│   ├── system_logs/                     # Application logs and debugging information
│   └── test_files/                      # Test files for validation
└── testing_research_papers/             # Research papers for testing and validation
```

**Purpose**: Data processing workspace with organized storage for different data types and processing stages.

## Key Architectural Patterns

### 1. Layered Architecture
- **API Layer**: FastAPI endpoints for external communication
- **Service Layer**: Business logic and domain operations
- **Repository Layer**: Data access abstraction
- **Storage Layer**: Database and file storage management

### 2. Repository Pattern
- Abstract base repository for common operations
- Specialized repositories for different data types
- Clean separation between business logic and data access

### 3. Knowledge Graph Integration
- Semantic validation and relationship management
- Error pattern detection and learning
- Dynamic threshold optimization

### 4. Multi-Backend Storage
- Configurable storage backends (local, Appwrite, S3)
- Unified storage interface with routing strategies
- Flexible deployment options

### 5. Multi-User Session Management
- User isolation with configurable resource sharing
- Session lifecycle management
- Resource allocation and quota tracking

This structure provides a scalable, maintainable architecture that supports the complex requirements of polymer literature extraction while maintaining clear separation of concerns and enabling future enhancements.
