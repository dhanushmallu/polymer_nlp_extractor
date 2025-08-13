# Changelog for Project Structure
- `/notebooks` unchanged
- `/api`: adds `groundtruth.py`, `preprocessing.py`
- `/services`: renames fine_tuning.py to `fine_tune_service.py`, adds `groundtruth_service.py`, `preprocessing_service.py`, renames `tei_processing.py` to `tei_processing_service.py`, moves `templates.py` to `constants/` package, renames `token_packing.py` to `token_packing_service.py`, renames `ensemble_inference.py` to `ensemble_inference_service.py`, renames `evaluation_testing.py` to `evaluation_service.py`, renames `tokenizer_audit.py` to `tokenizer_service.py`, adds knowledge graph services
- splits `constants.py` into `/services/constants/` package with:
  - configuration_constants.py: contains CONTENT_MARKERS, SCIENTIFIC_SECTIONS, ENTITY_TYPES, EXPORT_FORMATS and MEASUREMENT_PATTERNS
  - greek_letters.py: contains UPPERCASE_GREEK_LETTERS, LOWERCASE_GREEK_LETTERS, NAMED_GREEK_LETTERS
  - ~~material_names.py~~ (removed): previously contained MATERIAL_NAMES
  - templates.py: contains SENTENCE_TEMPLATES
  - polymer_names.py: contains POLYMER_NAMES
  - property_names.py: contains PROPERTY_NAMES
  - property_tables.py: contains PROPERTY_TABLE
  - scientific_symbols.py: contains SCIENTIFIC_SYMBOLS
  - scientific_units.py: contains SCIENTIFIC_UNITS
  - value_formats.py: contains VALUE_FORMATS
- `/storage`: renames `database.py` to `database_manager.py`, renames `bucket.py` to `bucket_manager.py`, adds PostgreSQL and Neo4j clients
- `/repositories`: **NEW** - implements repository pattern for database abstraction
- `/knowledge_graph`: **NEW** - dedicated knowledge graph services and validators
- `/utils`: adds `file_utils.py`, ~~lexicon_guard.py~~ (removed), ~~preprocessing.py~~ (removed), ~~validators.py~~ (removed)
- ~~`/cli`~~ (removed): previously contained CLI interfaces

```angular2html
polymer_nlp_extractor/
│
├── polymer_extractor/                                    # 🎯 Core application package
│   ├── __init__.py                                       # Package initialization and version info
│   ├── model_config.py                                   # 🧠 Central model configurations, ensemble settings, and thresholds
│   ├── api/                                              # 🌐 FastAPI endpoints and request handlers
│   │   ├── __init__.py                                   # API package initialization
│   │   ├── ensemble_inference.py                         # 🔮 Main inference API endpoints for ensemble processing
│   │   ├── finetune.py                                   # 🎓 Model fine-tuning API endpoints and training workflows
│   │   ├── grobid.py                                     # 📄 PDF to XML conversion API using GROBID service
│   │   ├── evaluation.py                                 # 📊 Model evaluation and performance assessment APIs
│   │   ├── setup.py                                      # ⚙️ System setup and configuration management APIs
│   │   ├── session.py                                    # 📋 Session management and tracking APIs
│   │   ├── groundtruth.py                                # ✅ Ground truth data handling and validation APIs
│   │   ├── preprocessing.py                              # 🔧 Data preprocessing and cleaning APIs
│   │
│   ├── services/                                         # 🛠️ Business logic and core processing services
│   │   ├── __init__.py                                   # Services package initialization
│   │   ├── enhanced_merging_service.py                   # 🔀 Advanced entity merging with TEI alignment and deduplication
│   │   ├── ensemble_inference_service.py                 # 🎯 Core ensemble inference engine with semantic boosting
│   │   ├── evaluation_service.py                         # 📈 Model evaluation, metrics calculation, and performance analysis
│   │   ├── fine_tune_service.py                          # 🎯 Model fine-tuning orchestration and training management
│   │   ├── fixed_ensemble_service.py                     # 🔧 Legacy ensemble service for backward compatibility
│   │   ├── grobid_service.py                             # 📑 GROBID integration for PDF processing and XML conversion
│   │   ├── groundtruth_service.py                        # 📝 Ground truth data processing and validation logic
│   │   ├── preprocessing_service.py                      # 🧹 Data preprocessing, cleaning, and transformation
│   │   ├── setup_service.py                              # 🔧 System initialization, dependency checks, and configuration
│   │   ├── tei_processing_service.py                     # 📜 TEI XML processing, sentence extraction, and text alignment
│   │   ├── token_packing_service.py                      # 📦 Tokenization and sequence packing for model input
│   │   ├── tokenizer_service.py                          # 🔤 Tokenizer management, extension, and vocabulary handling
│   │   ├── constants/                                    # 📚 Domain-specific constants and lookup tables
│   │   │   ├── __init__.py                               # Constants package initialization
│   │   │   ├── configuration_constants.py                # ⚙️ System configuration constants and content markers
│   │   │   ├── greek_letters.py                          # 🇬🇷 Greek letter mappings for scientific notation
│   │   │   ├── polymer_names.py                          # 🧪 Comprehensive polymer name database for recognition
│   │   │   ├── property_names.py                         # 🔬 Material property names and scientific terminology
│   │   │   ├── property_table.py                         # 📊 Standard property-value-unit relationships and ranges
│   │   │   ├── scientific_symbols.py                     # 🔣 Scientific symbols and mathematical notation
│   │   │   ├── scientific_units.py                       # 📏 Comprehensive units database with SI and imperial systems
│   │   │   ├── templates.py                              # 📝 Sentence templates for data augmentation and training
│   │   │   ├── value_formats.py                          # 🔢 Numerical value patterns and format recognition
│   │
│   ├── storage/                                          # 💾 Data persistence and database management
│   │   ├── __init__.py                                   # Storage package initialization
│   │   ├── appwrite_client.py                            # ☁️ Appwrite cloud storage integration for file management
│   │   ├── bucket_manager.py                             # 🗂️ File bucket operations, uploads, and downloads
│   │   ├── database_manager.py                           # 🗄️ Legacy Appwrite database operations and document management
│   │   ├── postgresql_client.py                          # 🐘 PostgreSQL client for relational data and complex queries
│   │   ├── neo4j_client.py                               # 🕸️ Neo4j graph database client for semantic relationships
│   │
│   ├── repositories/                                     # 🏛️ Repository pattern for clean data access abstraction
│   │   ├── __init__.py                                   # Repositories package initialization
│   │   ├── base_repository.py                            # 🏗️ Abstract base repository with common CRUD operations
│   │   ├── entity_repository.py                          # 🏷️ Entity data access, querying, and relationship management
│   │   ├── paper_repository.py                           # 📰 Research paper metadata storage and retrieval
│   │   ├── session_repository.py                         # 📊 Extraction session tracking and performance analytics
│   │   ├── validation_repository.py                      # ✅ Validation results storage and effectiveness tracking
│   │   ├── knowledge_graph_repository.py                 # 🧠 Knowledge graph data access and relationship caching
│   │
│   ├── knowledge_graph/                                  # 🧠 Intelligence layer for domain knowledge and validation
│   │   ├── __init__.py                                   # Knowledge graph package initialization
│   │   ├── kg_client.py                                  # 🔌 Neo4j knowledge graph client and connection management
│   │   ├── kg_validator.py                               # ✅ Real-time entity validation against domain constraints
│   │   ├── kg_semantic_analyzer.py                       # 🔍 Enhanced semantic relationship detection and scoring
│   │   ├── kg_relationship_manager.py                    # 🔗 Relationship pattern management and confidence boosting
│   │   ├── kg_error_pattern_detector.py                  # 🚨 Automated error pattern detection and learning system
│   │   ├── kg_threshold_optimizer.py                     # 📈 Dynamic confidence threshold optimization engine
│   │   ├── kg_canonical_manager.py                       # 📖 Canonical entity form management and standardization
│   │
│   ├── utils/                                            # 🛠️ Utility functions and helper modules
│   │   ├── __init__.py                                   # Utils package initialization
│   │   ├── paths.py                                      # 📁 Path management and workspace directory utilities
│   │   ├── logging.py                                    # 📝 Centralized logging configuration and context management
│   │   ├── file_utils.py                                 # 📂 File operations, compression, and archive management
│   │
│   ├── main.py                                           # 🚀 FastAPI application entry point and server initialization
│   ├── config.py                                         # ⚙️ Environment configuration and settings management
│
├── notebooks/                                            # 📓 Jupyter notebooks for interactive development and analysis
│   ├── polymer_extractor.ipynb                          # 🧪 Main research notebook for model experimentation and analysis
│
├── workspace/                                            # 💼 Working directory for data processing and model artifacts
│   ├── models/                                           # 🤖 Model storage and management directory
│   │   ├── tokenizers/                                   # 🔤 Extended tokenizers with domain-specific vocabulary
│   ├── reports/                                          # 📊 Generated reports and analysis outputs
│   ├── extracted_xml/                                    # 📄 Raw XML files from PDF conversion (unprocessed)
│   ├── ground_truth/                                     # ✅ Uploaded testing datasets before processing
│   ├── processed_xml/                                    # 📑 Cleaned and processed XML files ready for extraction
│   ├── system_logs/                                      # 📝 System operation logs and debugging information
│   ├── public/grobid/                                    # 🔧 GROBID sample data and configuration files
│   ├── raw_inputs/                                       # 📥 Uploaded PDF files awaiting processing
│   ├── samples/                                          # 🧪 Tokenization outputs and processing samples
│   │   │   # Contains: model_name/<file>_tei_sentences.txt, <file>_tei_tagless.txt, <file>_tei_token_windows.json
│   ├── system_logs/                                      # 📋 Categorized logs: api.log, system.log, user.log
│   ├── grobid-0.8.2/                                     # 🏭 GROBID server installation and runtime directory
│   ├── datasets/                                         # 📚 Training and testing dataset management
│   │   ├── training/                                     # 🎓 Processed training data and fine-tuning datasets
│   │   ├── testing/                                      # 🧪 Processed and realigned testing datasets
│   ├── exports/                                          # 📤 Final extraction results and processed outputs
│
├── model_updates/                                        # 📋 Comprehensive documentation and architectural guidance
│   ├── data_handling.md                                  # 📊 Data processing strategies and validation methodologies
│   ├── database_migration.md                             # 🗄️ Complete migration guide from Appwrite to PostgreSQL + Neo4j
│   ├── error-cause.md                                    # 🔍 Root cause analysis of model errors and performance issues
│   ├── error-log.md                                      # 📝 Detailed error logs and debugging information
│   ├── error-solutions.md                                # 🔧 Solutions and fixes for identified model problems
│   ├── evaluation_logic.md                               # 📈 Evaluation methodologies and performance metrics
│   ├── knowledge_graph_strategy.md                       # 🧠 Comprehensive knowledge graph implementation strategy
│   ├── model_performance_analysis.md                     # 📊 Performance analysis and optimization recommendations
│   ├── tokenization_and_finetuning.md                    # 🎯 Model training guidelines and tokenization strategies
│
├── pyproject.toml                                        # 📦 Python project configuration and dependency management
├── requirements.txt                                      # 📋 Python package dependencies and version specifications
├── Dockerfile                                            # 🐳 Docker containerization configuration for deployment
├── Procfile                                              # 🚀 Heroku deployment configuration and process definitions
├── .env                                                  # 🔑 Environment variables and secret configuration
├── README.md                                             # 📖 Project documentation and setup instructions
```

## New Components Overview

### 📁 `/repositories/` - Repository Pattern Implementation
**Purpose**: Database abstraction layer implementing repository pattern for clean service integration

- **`base_repository.py`**: 🏗️ **Abstract Foundation**
  - Defines common CRUD operations (Create, Read, Update, Delete)
  - Implements transaction management and connection pooling
  - Provides error handling and logging for database operations
  - Serves as base class for all specialized repositories

- **`entity_repository.py`**: 🏷️ **Entity Data Management**
  - Handles all entity-related database operations (POLYMER, PROPERTY, VALUE, UNIT, SYMBOL, MATERIAL)
  - Implements complex entity queries with confidence filtering and relationship joins
  - Manages entity merging, deduplication, and normalization
  - Provides entity search and retrieval with semantic grouping

- **`paper_repository.py`**: 📰 **Research Paper Operations**
  - Stores and retrieves research paper metadata (DOI, title, authors, journal)
  - Manages paper-sentence relationships and character position tracking
  - Handles file metadata and Appwrite storage references
  - Implements paper search and categorization functionality

- **`session_repository.py`**: 📊 **Processing Session Management**
  - Tracks extraction sessions with ensemble strategies and model configurations
  - Stores session performance metrics and processing statistics
  - Manages session-entity relationships and extraction results
  - Provides session analytics and performance comparison tools

- **`validation_repository.py`**: ✅ **Validation Results Tracking**
  - Stores validation results from all validation strategies
  - Tracks confidence adjustments and boost applications
  - Manages validation rule effectiveness and success rates
  - Provides validation analytics and performance insights

- **`knowledge_graph_repository.py`**: 🧠 **Knowledge Graph Data Access**
  - Caches frequently accessed knowledge graph relationships
  - Manages canonical entity forms and validation rules
  - Stores error patterns and correction strategies
  - Implements high-performance KG data retrieval with LRU caching

### 📁 `/knowledge_graph/` - Knowledge Graph Intelligence Layer
**Purpose**: Comprehensive knowledge graph services for semantic validation and enhancement

- **`kg_client.py`**: 🔌 **Neo4j Integration Hub**
  - Manages Neo4j database connections and query execution
  - Implements Cypher query building and optimization
  - Handles graph traversals for relationship discovery
  - Provides transaction management for graph operations
  - Includes connection pooling and retry mechanisms for reliability

- **`kg_validator.py`**: ✅ **Real-Time Domain Validation**
  - Validates entities against comprehensive domain constraints
  - Checks physical consistency (e.g., valid temperature ranges, unit compatibility)
  - Implements semantic coherence validation across related entities
  - Provides confidence adjustments based on validation results (+0.15 for exact matches)
  - Supports batch validation for improved performance

- **`kg_semantic_analyzer.py`**: 🔍 **Enhanced Relationship Intelligence**
  - Extends existing SemanticAnalyzer with knowledge graph capabilities
  - Detects VALUE-UNIT pairs with 0.12 confidence boost
  - Identifies PROPERTY-VALUE relationships with 0.10 boost
  - Discovers POLYMER-PROPERTY associations with 0.08 boost
  - Implements semantic distance calculations and relationship strength scoring

- **`kg_relationship_manager.py`**: 🔗 **Pattern Management System**
  - Manages all relationship patterns from ENTITY_RELATIONSHIP_PATTERNS
  - Caches relationship validations for performance optimization
  - Implements relationship strength calculations and distance thresholds
  - Provides relationship analytics and pattern effectiveness tracking
  - Handles relationship pattern updates and versioning

- **`kg_error_pattern_detector.py`**: 🚨 **Intelligent Error Learning**
  - Automatically detects recurring error patterns across models
  - Learns from model-specific errors (PolymerNER, MatSciBERT, etc.)
  - Implements error classification and frequency tracking
  - Provides automated correction suggestions and strategies
  - Supports continuous learning from new error occurrences

- **`kg_threshold_optimizer.py`**: 📈 **Dynamic Threshold Intelligence**
  - Implements DynamicThresholds class integration with knowledge graph validation
  - Adjusts confidence thresholds based on semantic relationships (-0.06 boost)
  - Considers context indicators (experimental vs. theoretical)
  - Applies ensemble agreement modifiers for threshold calculation
  - Provides threshold effectiveness analytics and optimization recommendations

- **`kg_canonical_manager.py`**: 📖 **Entity Standardization Hub**
  - Manages canonical forms for all entity types with aliases and variations
  - Implements fuzzy matching for entity normalization
  - Provides confidence boosts for canonical matches (+0.15 exact, +0.10 fuzzy)
  - Handles entity disambiguation and standardization
  - Supports domain-specific canonicalization rules

### 🔧 `/storage/` - Enhanced Database Clients
**Purpose**: Multi-database support with PostgreSQL and Neo4j integration

- **`postgresql_client.py`**: 🐘 **Relational Database Powerhouse**
  - Implements PostgreSQL connection management with connection pooling
  - Provides optimized SQL query execution with prepared statements
  - Handles complex analytical queries with comprehensive indexing
  - Supports transactions, migrations, and schema management
  - Includes performance monitoring and query optimization tools

- **`neo4j_client.py`**: 🕸️ **Graph Database Intelligence**
  - Manages Neo4j driver connections with clustering support
  - Implements Cypher query execution with parameter binding
  - Provides graph traversal optimization for relationship queries
  - Handles large-scale graph operations with batch processing
  - Includes graph analytics and performance monitoring

- **`appwrite_client.py`**: ☁️ **Cloud Storage Integration**
  - Retained for file storage operations and bucket management
  - Provides secure file upload/download with authentication
  - Handles file metadata and version management
  - Implements file access controls and sharing permissions

- **`database_manager.py`**: 🗄️ **Legacy Operations Support**
  - Maintains backward compatibility with existing Appwrite operations
  - Provides migration utilities for data transition
  - Handles legacy document-based queries during transition period

- **`bucket_manager.py`**: 🗂️ **File Management Hub**
  - Orchestrates file operations across storage systems
  - Provides unified interface for file access and management
  - Handles file compression, archiving, and cleanup operations

### 📊 `/model_updates/` - Documentation Hub
**Purpose**: Comprehensive documentation for model improvements and architectural decisions

- **`database_migration.md`**: 🗄️ **Migration Master Plan**
  - Complete strategy for migrating from Appwrite to PostgreSQL + Neo4j
  - Detailed schema designs with 12 essential tables and knowledge graph support
  - Migration phases, timelines, and implementation strategies
  - Performance benefits and architectural improvements documentation

- **`knowledge_graph_strategy.md`**: 🧠 **Intelligence Implementation Guide**
  - Comprehensive strategy for knowledge graph integration
  - Multi-layered entity ontology and relationship modeling
  - Advanced validation engine and confidence boosting specifications
  - Error pattern learning and threshold optimization strategies

- **`data_handling.md`**: 📊 **Data Processing Standards**
  - Guidelines for training/testing data format and validation
  - Knowledge graph integration strategies for data enhancement
  - Standardization procedures and quality assurance protocols

- **`evaluation_logic.md`**: 📈 **Assessment Methodologies**
  - Evaluation strategies and mapping techniques
  - Knowledge graph integration for evaluation enhancement
  - Performance metrics and accuracy measurement standards

- **`tokenization_and_finetuning.md`**: 🎯 **Training Excellence Guide**
  - Model training guidelines with knowledge graph integration
  - Tokenization strategies and vocabulary management
  - Fine-tuning optimization and performance enhancement techniques

- **`model_performance_analysis.md`**: 📊 **Performance Intelligence**
  - Comprehensive performance analysis and optimization strategies
  - Error analysis and improvement recommendations
  - Model comparison and effectiveness evaluation

- **`error-*.md` Files**: 🔍 **Error Intelligence Suite**
  - `error-cause.md`: Root cause analysis of model errors
  - `error-log.md`: Detailed error documentation and tracking
  - `error-solutions.md`: Solutions and fixes for identified problems

## Core Components Deep Dive

### 🎯 `/polymer_extractor/` - Main Application Package
**Purpose**: Core application logic with modular architecture for polymer NLP processing

#### 🌐 `/api/` - FastAPI Endpoints Layer
**Purpose**: RESTful API interface providing comprehensive access to all system capabilities

- **`ensemble_inference.py`**: 🔮 **Primary Inference Engine**
  - Main API endpoints for ensemble model processing and entity extraction
  - Handles batch and single document processing requests
  - Implements real-time inference with knowledge graph validation
  - Provides confidence scoring and semantic relationship detection
  - Supports multiple output formats (JSON, CSV, TEI-enhanced)

- **`finetune.py`**: 🎓 **Model Training Interface**
  - API endpoints for model fine-tuning and training orchestration
  - Handles training dataset upload, validation, and preprocessing
  - Manages training job scheduling and progress monitoring
  - Provides model performance metrics and evaluation results
  - Supports custom training configurations and hyperparameter tuning

- **`grobid.py`**: 📄 **Document Processing Gateway**
  - PDF to TEI-XML conversion API using GROBID service integration
  - Handles document upload, validation, and format checking
  - Manages GROBID server communication and error handling
  - Provides document structure analysis and metadata extraction
  - Supports batch document processing with progress tracking

- **`evaluation.py`**: 📊 **Performance Assessment Interface**
  - Model evaluation API with comprehensive metrics calculation
  - Handles ground truth comparison and accuracy assessment
  - Provides detailed performance analytics and visualizations
  - Supports custom evaluation criteria and scoring methods
  - Implements cross-validation and statistical significance testing

- **`setup.py`**: ⚙️ **System Configuration Hub**
  - System initialization and configuration management APIs
  - Handles dependency checking and environment validation
  - Manages model downloads and artifact synchronization
  - Provides system health monitoring and diagnostic tools
  - Supports configuration updates and parameter management

- **`session.py`**: 📋 **Session Management Interface**
  - Processing session creation, tracking, and management
  - Handles session-based authentication and access control
  - Provides session analytics and performance monitoring
  - Supports concurrent session management and resource allocation
  - Implements session persistence and recovery mechanisms

- **`groundtruth.py`**: ✅ **Ground Truth Management**
  - Ground truth dataset upload, validation, and management APIs
  - Handles annotation format validation and standardization
  - Provides ground truth quality assessment and statistics
  - Supports dataset versioning and annotation tracking
  - Implements ground truth comparison and diff analysis

- **`preprocessing.py`**: 🔧 **Data Preparation Interface**
  - Data preprocessing and cleaning API endpoints
  - Handles text normalization and format standardization
  - Provides data quality assessment and validation tools
  - Supports custom preprocessing pipelines and transformations
  - Implements batch processing with progress monitoring

#### 🛠️ `/services/` - Business Logic Layer
**Purpose**: Core processing services implementing sophisticated NLP and machine learning algorithms

- **`ensemble_inference_service.py`**: 🎯 **Intelligence Orchestration Engine**
  - Core ensemble inference engine with 5-model architecture (PolymerNER, MatSciBERT, SciBERT, PhysBERT, BioBERT)
  - Implements semantic boosting with VALUE-UNIT (+0.12), PROPERTY-VALUE (+0.10), POLYMER-PROPERTY (+0.08) confidence adjustments
  - Features dynamic threshold optimization with context-aware adjustments
  - Provides cross-model entity consolidation with span length prioritization
  - Integrates knowledge graph validation for real-time entity verification

- **`enhanced_merging_service.py`**: 🔀 **Precision Entity Consolidation**
  - Advanced sentence-by-sentence entity processing with strict TEI alignment
  - Implements intelligent adjacent entity merging (2-character tolerance)
  - Provides duplicate elimination and entity boundary optimization
  - Features complete word/phrase alignment from TEI source text
  - Supports entity replacement with complete TEI text for accuracy

- **`evaluation_service.py`**: 📈 **Performance Intelligence System**
  - Comprehensive model evaluation with precision, recall, F1-score calculations
  - Implements fuzzy matching for ground truth comparison (70% threshold)
  - Provides detailed performance analytics with model-specific insights
  - Features automated evaluation report generation with visualizations
  - Supports custom evaluation metrics and statistical analysis

- **`fine_tune_service.py`**: 🎯 **Training Optimization Engine**
  - Model fine-tuning orchestration with knowledge graph integration
  - Implements adaptive learning rate scheduling and regularization
  - Provides training progress monitoring and early stopping
  - Features model checkpoint management and version control
  - Supports distributed training and GPU optimization

- **`tei_processing_service.py`**: 📜 **Document Structure Intelligence**
  - TEI XML processing with precise sentence extraction and character mapping
  - Implements section-aware processing (abstract, introduction, methods, results)
  - Provides document structure analysis and metadata extraction
  - Features character position tracking for entity alignment
  - Supports batch document processing with error recovery

- **`token_packing_service.py`**: 📦 **Sequence Optimization Engine**
  - Intelligent tokenization with sequence length optimization (512 tokens max)
  - Implements sliding window processing for long documents
  - Provides context preservation across token boundaries
  - Features batch tokenization with memory optimization
  - Supports custom tokenizer configurations and vocabulary extensions

- **`tokenizer_service.py`**: 🔤 **Vocabulary Management System**
  - Tokenizer extension and vocabulary management for domain-specific terms
  - Implements dynamic vocabulary updates with polymer and materials science terms
  - Provides tokenizer artifact management and version control
  - Features compatibility checking across model architectures
  - Supports custom tokenization strategies and special token handling

#### 📚 `/services/constants/` - Domain Knowledge Base
**Purpose**: Comprehensive domain-specific constants and lookup tables for polymer science

- **`configuration_constants.py`**: ⚙️ **System Configuration Registry**
  - CONTENT_MARKERS: Document section identifiers and parsing rules
  - SCIENTIFIC_SECTIONS: Standard academic paper structure definitions
  - ENTITY_TYPES: Complete entity type definitions and hierarchies
  - EXPORT_FORMATS: Output format specifications and templates
  - MEASUREMENT_PATTERNS: Scientific measurement pattern recognition rules

- **`greek_letters.py`**: 🇬🇷 **Scientific Notation Support**
  - UPPERCASE_GREEK_LETTERS: Complete Greek alphabet for scientific symbols
  - LOWERCASE_GREEK_LETTERS: Lowercase variants for mathematical notation
  - NAMED_GREEK_LETTERS: Full name mappings for OCR and text processing

- **`polymer_names.py`**: 🧪 **Polymer Knowledge Database**
  - Comprehensive database of polymer names, abbreviations, and chemical identifiers
  - Includes common names, IUPAC nomenclature, and commercial brand names
  - Features polymer classification hierarchies and structural information
  - Supports fuzzy matching and synonym recognition

- **`property_names.py`**: 🔬 **Material Properties Lexicon**
  - Complete material property terminology and scientific names
  - Includes thermal, mechanical, optical, electrical, and chemical properties
  - Features property categorization and measurement context information
  - Supports property synonym recognition and standardization

- **`property_table.py`**: 📊 **Property-Value-Unit Knowledge Matrix**
  - Standard property-value-unit relationships with valid ranges
  - Includes experimental data ranges and typical measurement conditions
  - Features property validation rules and compatibility matrices
  - Supports property standardization and unit conversion

- **`scientific_symbols.py`**: 🔣 **Scientific Symbol Registry**
  - Comprehensive scientific and mathematical symbol database
  - Includes physics symbols, chemistry notation, and mathematical operators
  - Features symbol categorization and context-specific usage rules
  - Supports symbol recognition and normalization

- **`scientific_units.py`**: 📏 **Units Knowledge System**
  - Comprehensive units database with SI, imperial, and specialized systems
  - Includes unit conversion factors and dimensional analysis rules
  - Features unit compatibility checking and standardization
  - Supports complex unit expressions and compound units

- **`value_formats.py`**: 🔢 **Numerical Pattern Recognition**
  - Scientific notation patterns and numerical format recognition
  - Includes range expressions, uncertainty notation, and significant figures
  - Features value parsing and normalization rules
  - Supports complex numerical expressions and scientific formatting

### ❌ Deprecated Files
- `material_names.py`: Material names moved to constants integration
- `lexicon_guard.py`: Replaced by knowledge graph canonical management
- `utils/preprocessing.py`: Functionality moved to services layer
- `utils/validators.py`: Replaced by knowledge graph validation system
- `cli/`: Command-line interfaces removed in favor of API-first approach

## Workspace Structure Deep Dive

### 💼 `/workspace/` - Data Processing and Model Management Hub
**Purpose**: Centralized working directory for all data processing, model artifacts, and system operations

#### 🤖 `/models/` - Model Artifact Management
- **Purpose**: Centralized storage for all machine learning models and tokenizers
- **`/tokenizers/`**: Extended tokenizers with domain-specific vocabulary
  - Contains model-specific tokenizers (e.g., `polymer_ner_extended`, `matscibert_extended`)
  - Includes vocabulary extensions with polymer and materials science terms
  - Features tokenizer configuration files and special token mappings
  - Supports version control and compatibility tracking

#### 📊 `/reports/` - Analytics and Documentation Hub
- **Purpose**: Generated reports, analysis outputs, and performance documentation
- Contains evaluation reports, performance analytics, and model comparison studies
- Includes visualization outputs, charts, and statistical analysis results
- Features automated report generation from evaluation services
- Supports export to multiple formats (PDF, HTML, CSV)

#### 📄 `/extracted_xml/` - Raw Document Processing
- **Purpose**: Stores XML files from PDF conversion before cleaning and processing
- Contains GROBID-generated TEI-XML files with original document structure
- Includes metadata extraction results and document parsing information
- Features backup copies of raw conversion outputs for error recovery
- Supports batch processing with organized subdirectories by processing date

#### ✅ `/ground_truth/` - Reference Data Management
- **Purpose**: Uploaded testing datasets and reference annotations before processing
- Contains original ground truth files in various formats (CSV, JSON, XML)
- Includes metadata about annotation quality and dataset characteristics
- Features version control for ground truth updates and modifications
- Supports dataset validation and quality assessment tools

#### 📑 `/processed_xml/` - Clean Document Storage
- **Purpose**: Cleaned and processed XML files ready for entity extraction
- Contains TEI-XML files after cleaning, normalization, and sentence segmentation
- Includes character position mappings and sentence boundary information
- Features quality-checked documents with validated structure and content
- Supports optimized processing with pre-computed sentence statistics

#### 📝 `/system_logs/` - Comprehensive Logging System
- **Purpose**: Centralized logging for debugging, monitoring, and audit trails
- **`api.log`**: API request/response logging with performance metrics
- **`system.log`**: System-level operations, errors, and performance monitoring
- **`user.log`**: User activity tracking and session management
- Features log rotation, compression, and automated cleanup
- Supports real-time log monitoring and alerting systems

#### 🔧 `/public/grobid/` - GROBID Configuration Hub
- **Purpose**: GROBID service configuration files and sample data
- Contains GROBID configuration templates and processing examples
- Includes sample input/output pairs for testing and validation
- Features GROBID model configurations and language settings
- Supports GROBID service monitoring and health checking

#### 📥 `/raw_inputs/` - Document Intake System
- **Purpose**: Uploaded PDF files awaiting processing and conversion
- Contains user-uploaded research papers and documents
- Includes file validation results and metadata extraction
- Features automated file organization and duplicate detection
- Supports batch upload with progress tracking and error handling

#### 🧪 `/samples/` - Processing Output Repository
- **Purpose**: Tokenization outputs and intermediate processing results
- **File Structure by Model**:
  - `{model_name}/{file_name}_tei_sentences.txt`: Extracted sentences with metadata
  - `{model_name}/{file_name}_tei_tagless.txt`: Clean text without XML tags
  - `{model_name}/{file_name}_tei_token_windows.json`: Tokenized windows with positions
- Contains processing samples for debugging and quality assessment
- Features organized output structure for easy comparison across models
- Supports sample analysis and processing pipeline validation

#### 🏭 `/grobid-0.8.2/` - GROBID Service Runtime
- **Purpose**: Complete GROBID server installation and runtime environment
- Contains GROBID application files, models, and configuration
- Includes service startup scripts and monitoring tools
- Features automated service management and health monitoring
- Supports version management and update procedures

#### 📚 `/datasets/` - Training Data Management
- **Purpose**: Comprehensive dataset management for model training and evaluation
- **`/training/`**: Processed training datasets for model fine-tuning
  - Contains cleaned and validated training data in standard formats
  - Includes data augmentation results and synthetic examples
  - Features cross-validation splits and stratified sampling
  - Supports dataset versioning and lineage tracking
- **`/testing/`**: Processed and realigned testing datasets for evaluation
  - Contains evaluation datasets with ground truth alignments
  - Includes performance benchmark datasets and standard test suites
  - Features automated test data validation and quality checks
  - Supports A/B testing and comparative evaluation

#### 📤 `/exports/` - Final Output Management
- **Purpose**: Final extraction results and processed outputs for users
- Contains completed entity extraction results in multiple formats
- Includes ensemble processing outputs with confidence scores
- Features knowledge graph validation results and semantic relationships
- Supports export to user-specified formats with custom filtering
- Includes processing metadata and quality assessment reports

## Key Architectural Changes

### 🔄 Database Architecture Migration
- **From**: Appwrite-only document database
- **To**: Dual database architecture (PostgreSQL + Neo4j + Appwrite Storage)
- **Benefits**: Enhanced relational integrity, semantic relationship modeling, improved performance

### 🧠 Knowledge Graph Integration
- **New Layer**: Comprehensive domain knowledge integration
- **Features**: Real-time validation, confidence boosting, error pattern learning
- **Impact**: 15-20% precision improvement, 10-15% recall increase

### 🏗️ Repository Pattern Implementation
- **Architecture**: Clean separation between services and data access
- **Benefits**: Database agnostic services, improved testability, cleaner code organization
- **Integration**: Seamless integration with existing service layer

### 📈 Enhanced Service Architecture
- **Existing Services**: All existing services maintained and enhanced
- **New Capabilities**: Knowledge graph integration, improved validation, error learning
- **Backward Compatibility**: Full compatibility with existing model_config.py patterns

## Migration Impact

### ✅ Maintained Functionality
- All existing API endpoints preserved
- Model configurations and ensemble strategies intact
- Existing data processing pipelines operational
- Notebook functionality enhanced but unchanged

### 🚀 Enhanced Capabilities
- Real-time semantic validation
- Dynamic confidence optimization
- Automated error pattern detection
- Comprehensive relationship modeling
- Performance analytics and monitoring

### 🔧 Implementation Timeline
- **Phase 1** (Weeks 1-2): Core infrastructure and database setup
- **Phase 2** (Weeks 3-4): Knowledge graph integration and validation
- **Phase 3** (Weeks 5-6): Error learning and optimization features
- **Phase 4** (Weeks 7-8): Advanced features and production deployment
```
