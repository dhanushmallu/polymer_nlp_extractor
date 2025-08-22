# 03. How to Run This Project

## Overview

This guide provides comprehensive instructions for running the Polymer NLP Extractor across different environments and use cases. The project supports multiple deployment scenarios from development to production, with flexible storage backends and containerized services.

## Prerequisites and Platform Support

### Supported Platforms

**Windows is not supported.** This project is designed exclusively for Unix-based systems:

- **Linux**: Ubuntu 20.04+, Debian 11+
- **macOS Intel**: x86_64 architecture
- **macOS Apple Silicon**: M1/M2/M3 processors

**Windows users** must use WSL2 (Windows Subsystem for Linux) with Ubuntu distribution.

### Required Software

- **Python 3.8+**: Core runtime environment
- **Docker & Docker Compose**: Required for infrastructure services (PostgreSQL, Neo4j, GROBID)
- **Git**: Repository management and version control
- **Node.js & npm**: Optional (required only for Appwrite storage backend)
- **Internet connection**: Package installation and model downloads

### System Resources

- **Minimum**: 8GB RAM, 4GB free disk space
- **Recommended**: 16GB RAM, 10GB free disk space
- **GROBID Processing**: Additional 4GB heap memory allocation

## Environment Setup

### 1. Prerequisites and GitHub Integration

Before starting the project, you need to set up a companion repository for models and configure essential environment variables. This setup is crucial for the project's model synchronization and storage functionality.

#### GitHub Repository Setup

The project requires a separate **polymer_nlp_models** repository to store trained models and tokenizers. This separation keeps the main codebase clean while providing version control for large model files.

**Create the Models Repository:**

1. **Create New Repository**:
   ```bash
   # On GitHub.com, create a new repository named: polymer_nlp_models
   # Make it Private (recommended) or Public based on your needs
   # Initialize with README.md
   ```

2. **Repository Structure**:

   ```
   polymer_nlp_models/
   ├── README.md
   ├── finetuned-1.0/                    # Versioned finetuned models directory
   │   ├── model_1/                      # Individual model directory
   │   │   ├── config.json               # Model configuration
   │   │   ├── pytorch_model.bin         # Model weights
   │   │   └── tokenizer_config.json     # Model-specific tokenizer config
   │   ├── model_2/
   │   │   ├── config.json
   │   │   ├── pytorch_model.bin
   │   │   └── tokenizer_config.json
   │   └── ...
   ├── tokenizers-1.0/                  # Versioned tokenizers directory  
   │   ├── model_1_extended/             # Tokenizer for model_1
   │   │   ├── tokenizer_config.json     # Tokenizer configuration
   │   │   ├── vocab.txt                 # Vocabulary file
   │   │   ├── special_tokens_map.json   # Special tokens mapping
   │   │   └── tokenizer.json            # Tokenizer state
   │   ├── model_2_extended/             # Tokenizer for model_2
   │   │   ├── tokenizer_config.json
   │   │   ├── vocab.txt
   │   │   ├── special_tokens_map.json
   │   │   └── tokenizer.json
   │   └── ...
   └── metadata/                         # Optional: version tracking
       ├── compatibility_matrix.json
       └── release_notes.md
   ```

3. **Initial Setup Commands**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/polymer_nlp_models.git
   cd polymer_nlp_models
   
   # Create initial versioned directories (version 1.0)
   mkdir -p finetuned-1.0 tokenizers-1.0 metadata
   
   # Create example model structure (replace with your actual models)
   mkdir -p finetuned-1.0/model_example
   mkdir -p tokenizers-1.0/model_example_extended
   
   echo "# Polymer NLP Models Repository" > README.md
   echo "This repository contains versioned polymer NLP models and tokenizers." >> README.md
   echo "" >> README.md
   echo "## Structure" >> README.md
   echo "- \`finetuned-X.Y/\`: Versioned finetuned models" >> README.md
   echo "- \`tokenizers-X.Y/\`: Versioned tokenizers matching models" >> README.md
   echo "- \`metadata/\`: Version compatibility information" >> README.md
   
   git add . && git commit -m "Initial versioned repository structure"
   git push origin main
   ```

#### GitHub Token Configuration

The project uses GitHub integration for model synchronization and version management. The GitHub token is required for the storage client to access model repositories programmatically.

**Why GitHub Token is Required** (as referenced in `storage_client.py`):
- **Model Synchronization**: Automatic downloading of compatible model-tokenizer pairs
- **Version Management**: Tracking model versions and compatibility matrices
- **Secure Access**: Private repository access for proprietary models
- **Batch Operations**: Efficient bulk downloads and updates
- **Release Management**: Integration with GitHub releases for model versioning

**Generate GitHub Token**:

1. **Navigate to GitHub Settings**:
   ```
   GitHub.com → Settings → Developer settings → Personal access tokens → Tokens (classic)
   ```

2. **Create New Token**:
   - Name: `polymer_nlp_extractor_models`
   - Expiration: 90 days (recommended) or No expiration (less secure)
   - Scopes required:
     ```
     ✓ repo (Full control of private repositories)
     ✓ read:packages (Download packages from GitHub Package Registry)
     ✓ write:packages (Upload packages to GitHub Package Registry) [optional]
     ```

3. **Copy Token**: Save the generated token immediately (it won't be shown again)

#### Essential Environment Variables

The project requires several environment variables for proper operation. These control storage backends, API access, and model management.

**Storage Backend Keys**:

**AWS S3 Setup** (if using S3 storage):
1. **Create AWS Account**: Visit [AWS Console](https://aws.amazon.com/console/)
2. **Create IAM User**:
   ```bash
   # In AWS Console: IAM → Users → Add User
   # User name: polymer-nlp-extractor
   # Access type: Programmatic access
   ```
3. **Attach S3 Policy**:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:GetObject",
           "s3:PutObject",
           "s3:DeleteObject",
           "s3:ListBucket",
           "s3:CreateBucket"
         ],
         "Resource": [
           "arn:aws:s3:::polymer-extractor-*",
           "arn:aws:s3:::polymer-extractor-*/*"
         ]
       }
     ]
   }
   ```
4. **Get Credentials**: Copy Access Key ID and Secret Access Key

**Appwrite Setup** (if using Appwrite storage):
1. **Create Account**: Visit [Appwrite Cloud](https://cloud.appwrite.io)
2. **Create Project**: Name it "Polymer NLP Extractor"
3. **Create API Key**:
   ```bash
   # In Appwrite Console: Overview → Integrations → API Keys
   # Name: polymer-nlp-storage
   # Scopes: files.read, files.write, buckets.read, buckets.write
   ```
4. **Create Storage Bucket**:
   ```bash
   # In Appwrite Console: Storage → Create Bucket
   # Bucket ID: polymer-extractor-data
   # Permissions: Role-based (configure as needed)
   ```

### 2. Environment Configuration

#### Template to Production Environment

The project provides a comprehensive environment template that must be customized for your specific setup.

**Copy and Configure Environment File**:
```bash
cp .env.example .env
nano .env  # or use your preferred editor
```

**Critical Configuration Areas**:

```bash
# === CORE API CONFIGURATION ===
API_HOST=127.0.0.1
API_PORT=8000

# === GITHUB INTEGRATION (REQUIRED) ===
# This is essential for model synchronization and version management
GITHUB_TOKEN=your_github_token_here                    # Personal access token from GitHub

# === MODEL SYNCHRONIZATION CONFIGURATION ===
# Option 1: Unified Repository (Recommended)
MODELS_REPOSITORY_URL=https://github.com/YOUR_USERNAME/polymer_nlp_models
MODELS_VERSION=1.0                                     # Model version to sync (matches versioned directories)

# Option 2: Separate Repositories (Legacy - if not using unified repo)
# TOKENIZERS_REMOTE_URL=https://github.com/YOUR_USERNAME/polymer_tokenizers
# FINETUNED_REMOTE_URL=https://github.com/YOUR_USERNAME/polymer_finetuned_models

# === STORAGE BACKEND SELECTION ===
# Choose your primary storage strategy
STORAGE_BACKEND=local                                   # Options: local, appwrite, s3
STORAGE_PATH=./workspace/public                         # For local storage
STORAGE_STRATEGY=primary                                # Options: primary, replica, failover, sync

# For multi-backend setup (advanced):
# STORAGE_BACKENDS_ACTIVE=local,s3                     # Comma-separated list
# STORAGE_STRATEGY=replica                              # Use replica for redundancy

# === AWS S3 CONFIGURATION (if using S3) ===
# AWS_ACCESS_KEY_ID=your_aws_access_key
# AWS_SECRET_ACCESS_KEY=your_aws_secret_key
# AWS_REGION=us-east-1
# S3_BUCKET_NAME=polymer-extractor-data
# S3_ENABLED=true

# === APPWRITE CONFIGURATION (if using Appwrite) ===
# APPWRITE_STORAGE_ENDPOINT=https://cloud.appwrite.io/v1
# APPWRITE_STORAGE_PROJECT_ID=your_project_id
# APPWRITE_STORAGE_API_KEY=your_api_key
# APPWRITE_ENABLED=true

# === DATABASE CONFIGURATION (Docker managed) ===
POSTGRES_DB=polymer_extractor
POSTGRES_USER=pnlp_db_user
POSTGRES_PASSWORD=generate_secure_password_here        # Use strong password
POSTGRES_PORT=5432

# === KNOWLEDGE GRAPH CONFIGURATION ===
NEO4J_USER=neo4j
NEO4J_PASSWORD=generate_secure_password_here           # Use strong password
NEO4J_PORT=7687
NEO4J_HTTP_PORT=7474

# === SERVICE PORTS (customize if conflicts exist) ===
GROBID_PORT=8070
PGADMIN_PORT=5050

# === ADMIN INTERFACE (optional) ===
PGADMIN_DEFAULT_EMAIL=admin@example.com
PGADMIN_DEFAULT_PASSWORD=secure_admin_password
```

#### Security and Best Practices

**Password Generation**:
```bash
# Generate secure passwords for databases
openssl rand -base64 32    # For POSTGRES_PASSWORD
openssl rand -base64 32    # For NEO4J_PASSWORD
openssl rand -base64 24    # For PGADMIN_DEFAULT_PASSWORD
```

**Environment File Security**:
```bash
# Set proper permissions on .env file
chmod 600 .env

# Verify .env is in .gitignore (it should be by default)
grep -q "^\.env$" .gitignore && echo "✓ .env is properly ignored" || echo "⚠ Add .env to .gitignore"
```

**Storage Strategy Selection Guide**:
- **local**: Development, single-system deployments, fastest performance
- **appwrite**: Cloud deployment, built-in CDN, managed backups
- **s3**: Enterprise deployment, unlimited scale, AWS ecosystem integration
- **Multi-backend**: Production systems requiring redundancy and failover

#### Model and Tokenizer Compatibility

**Critical Compatibility Requirements**:

The project uses ensemble machine learning with multiple models that must be trained together with their corresponding tokenizers. **Model-tokenizer mismatches will result in poor extraction performance and unreliable results.**

**Compatibility Matrix**:
```bash
# CORRECT: Matched pairs (trained together)
base_tokenizer_v1    ↔ base_model_v1         ✓ Compatible
finetuned_tokenizer_v2 ↔ finetuned_model_v2   ✓ Compatible

# INCORRECT: Mismatched pairs (will cause poor results)
base_tokenizer_v1    ↔ finetuned_model_v2     ✗ Incompatible
finetuned_tokenizer_v2 ↔ base_model_v1        ✗ Incompatible
```

**Why Compatibility Matters**:
1. **Vocabulary Mismatch**: Different tokenizers create different vocabulary mappings
2. **Encoding Differences**: Token IDs may not correspond to expected text segments
3. **Special Tokens**: Custom tokens added during fine-tuning won't be recognized
4. **Sequence Length**: Different tokenizers may produce different sequence lengths
5. **Ensemble Interference**: Mismatched models produce inconsistent predictions

**Ensuring Compatibility**:
```bash
# 1. Always train tokenizer and model together
# 2. Use version tags to match components
# 3. Store compatibility metadata in your models repository
# 4. Test extraction quality after model updates
# 5. Use the project's model synchronization features
```

**Model Repository Organization**:
```bash
# Required naming convention for your polymer_nlp_models repository:
# The system expects VERSIONED directories with semantic versioning

# CURRENT VERSION: 1.0 (modify MODELS_VERSION in .env to match)
finetuned-1.0/                    # Versioned finetuned models directory
├── bert_base/                    # Individual model name
│   ├── config.json               # Model configuration (REQUIRED)
│   ├── pytorch_model.bin         # Model weights (REQUIRED)
│   └── tokenizer_config.json     # Optional model-specific config
├── roberta_polymer/              # Another model
│   ├── config.json
│   ├── pytorch_model.bin
│   └── tokenizer_config.json
└── ...

tokenizers-1.0/                  # Versioned tokenizers directory
├── bert_base_extended/           # Tokenizer for bert_base model
│   ├── tokenizer_config.json     # Tokenizer configuration (REQUIRED)
│   ├── vocab.txt                 # Vocabulary file
│   ├── special_tokens_map.json   # Special tokens mapping
│   └── tokenizer.json            # Tokenizer state
├── roberta_polymer_extended/     # Tokenizer for roberta_polymer model
│   ├── tokenizer_config.json
│   ├── vocab.txt
│   ├── special_tokens_map.json
│   └── tokenizer.json
└── ...

# FUTURE VERSIONS: When you upgrade models
finetuned-1.1/                    # Next version
tokenizers-1.1/                  # Matching tokenizer version

# CRITICAL: Version numbers must match between directories
# finetuned-X.Y must have corresponding tokenizers-X.Y
# Set MODELS_VERSION=X.Y in .env to sync specific version
```

**Version Compatibility Rules**:
```bash
# ✓ CORRECT: Matching versions (will work)
finetuned-1.0/ + tokenizers-1.0/     # Compatible pair
finetuned-1.1/ + tokenizers-1.1/     # Compatible pair

# ✗ INCORRECT: Mismatched versions (will cause errors)
finetuned-1.0/ + tokenizers-1.1/     # Version mismatch
finetuned-1.1/ + tokenizers-1.0/     # Version mismatch

# Model-Tokenizer Pairing within same version:
finetuned-1.0/bert_base → tokenizers-1.0/bert_base_extended     ✓
finetuned-1.0/roberta_polymer → tokenizers-1.0/roberta_polymer_extended ✓
```

**Verification Commands**:
```bash
# After setup, verify your configuration:
source .venv/bin/activate

# Test GitHub token access
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user

# Test storage backend connectivity
python3 -c "
from polymer_extractor.storage.storage_client import get_storage_client
client = get_storage_client()
print(client.test_connection())
"

# Sync models from GitHub (this will validate configuration)
python3 -c "
from polymer_extractor.services.models_sync_service import ModelsSyncService
service = ModelsSyncService()
result = service.sync_models_from_github()
print(f'Sync success: {result[\"success\"]}')
if not result['success']:
    print(f'Errors: {result[\"errors\"]}')
else:
    print(f'Models synced: {result[\"models_synced\"]}')
    print(f'Tokenizers synced: {result[\"tokenizers_synced\"]}')
"

# Verify model-tokenizer compatibility after sync
python3 -c "
from polymer_extractor.services.models_sync_service import ModelsSyncService
service = ModelsSyncService()
result = service.validate_models_versions()
print(f'Validation success: {result[\"valid\"]}')
print(f'Compatible pairs: {result[\"compatible_pairs\"]}')
if not result['valid']:
    print(f'Issues: {result[\"recommended_actions\"]}')
"
```

**Common Validation Issues and Solutions**:
```bash
# Issue: "No finetuned-* directory found in repository"
# Solution: Ensure your repository has finetuned-X.Y directory (e.g., finetuned-1.0)

# Issue: "No tokenizers-* directory found in repository"  
# Solution: Ensure your repository has tokenizers-X.Y directory (e.g., tokenizers-1.0)

# Issue: "Version mismatch between models and tokenizers"
# Solution: Ensure version numbers match (finetuned-1.0 needs tokenizers-1.0)

# Issue: "Missing model file: config.json"
# Solution: Each model directory must contain config.json and pytorch_model.bin

# Issue: "Missing tokenizer file: tokenizer_config.json"
# Solution: Each tokenizer directory must contain tokenizer_config.json
```

### 3. Initial Project Setup

**Linux Installation:**
```bash
git clone <repository-url>
cd polymer_nlp_extractor
python3 -m venv .venv
source .venv/bin/activate
pip3 install -e .
pip3 install -r requirements.txt
```

**macOS Intel Installation:**
```bash
git clone <repository-url>
cd polymer_nlp_extractor
python3 -m venv .venv
source .venv/bin/activate
pip3 install -e .
pip3 install -r requirements.txt
```

**macOS Apple Silicon Installation:**
```bash
git clone <repository-url>
cd polymer_nlp_extractor
arch -arm64 python3 -m venv .venv
source .venv/bin/activate
arch -arm64 pip3 install -e .
arch -arm64 pip3 install -r requirements.txt
```

### 2. Environment Configuration

Create and configure your environment file:

```bash
cp .env.example .env
nano .env  # or use your preferred editor
```

**Essential Configuration Variables:**
```bash
# API Server Configuration
API_HOST=127.0.0.1
API_PORT=8000

# Storage Backend Selection (local | appwrite | s3)
STORAGE_BACKEND=local
STORAGE_PATH=./workspace/public

# Database Configuration (Docker managed)
POSTGRES_DB=polymer_extractor
POSTGRES_USER=pnlp_db_user
POSTGRES_PASSWORD=<secure_password>

# Neo4j Knowledge Graph
NEO4J_USER=neo4j
NEO4J_PASSWORD=<secure_password>

# Service Ports (customize if conflicts exist)
POSTGRES_PORT=5432
NEO4J_PORT=7687
NEO4J_HTTP_PORT=7474
GROBID_PORT=8070
PGADMIN_PORT=5050
```

## Docker Infrastructure Setup

### Docker Installation

**Linux (Ubuntu/Debian):**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# Log out and back in, or restart system
```

**macOS (Both Intel and Apple Silicon):**
```bash
# Intel
brew install --cask docker

# Apple Silicon
arch -arm64 brew install --cask docker
```

### Docker Permission Setup (Linux Only)

```bash
sudo usermod -aG docker $USER
newgrp docker
docker ps  # Test permissions
```

If permission errors persist, the `server.sh` script will detect and provide guidance.

### Infrastructure Services

The project uses containerized services orchestrated via `docker-compose.services.yml`:

- **PostgreSQL**: Primary relational database for metadata and results
- **Neo4j**: Knowledge graph database for semantic validation
- **GROBID**: Document processing service for PDF to XML conversion
- **pgAdmin**: Optional database administration interface

## Running the Project

### Quick Start (Recommended)

The `server.sh` script provides comprehensive service management:

```bash
# Start all services and API
./server.sh

# Alternative: Start services only, then API separately
./server.sh services
./server.sh app
```

### Development Workflows

#### Option 1: Complete Automated Workflow
```bash
./server.sh                    # Start everything (services + API)
# API available at: http://127.0.0.1:8000
# Services automatically initialized and health-checked
```

#### Option 2: Services with Manual API Control
```bash
./server.sh services           # Start infrastructure services once
./server.sh app               # Start API (can restart independently)
./server.sh app stop         # Stop API while keeping services running
```

#### Option 3: Development with Database Admin
```bash
./server.sh pgadmin           # Start services + pgAdmin interface
# pgAdmin available at: http://localhost:5050
# Default credentials: admin@example.com / admin123
```

#### Option 4: Manual API Development
```bash
./server.sh services          # Start services once
# Then run API manually for debugging:
source .venv/bin/activate
uvicorn polymer_extractor.main:app --host 127.0.0.1 --port 8000 --reload
```

### Daily Development Pattern

```bash
# Morning: Start services
./server.sh services

# Development: Start/restart API as needed
./server.sh app              # Start API
./server.sh app stop        # Stop API for code changes
./server.sh app             # Restart API

# Evening: Clean shutdown
./server.sh stop            # Stop everything
```

## Service Management Commands

### Core Commands

```bash
# Service Lifecycle
./server.sh services         # Start infrastructure services
./server.sh app             # Start FastAPI application
./server.sh stop            # Stop all services
./server.sh restart         # Restart all services

# Monitoring and Debugging
./server.sh status          # Check service health and ports
./server.sh logs            # View service logs (follow mode)
./server.sh logs postgres   # View specific service logs

# Maintenance
./server.sh clean           # Stop services, free ports (keep data)
./server.sh reset           # Remove all data volumes
./server.sh purge           # Remove everything including images
```

### Advanced Service Options

```bash
# Database Administration
./server.sh pgadmin         # Start with pgAdmin interface
./server.sh db-init         # Initialize database schema
./server.sh db-clear        # Clear data (keep structure)

# Knowledge Graph Management
./server.sh kg-init         # Initialize Neo4j constraints
./server.sh kg-status       # Show graph database status
./server.sh kg-clear        # Clear knowledge graph data

# Port Conflict Resolution
./server.sh manage-services stop postgresql  # Stop system PostgreSQL
./server.sh manage-services stop neo4j       # Stop system Neo4j
```

## Storage Backend Configuration

The project supports multiple storage backends with flexible routing strategies:

### Local Storage (Default)
```bash
# .env configuration
STORAGE_BACKEND=local
STORAGE_PATH=./workspace/public
```

Files stored in: `./workspace/public/` with automatic directory creation.

### Multi-Backend Setup
```bash
# Enable multiple backends simultaneously
STORAGE_BACKENDS_ACTIVE=local,appwrite,s3
STORAGE_STRATEGY=sync  # sync | replica | failover | primary
```

**Storage Strategies:**
- **primary**: Use only the first backend
- **replica**: Read from primary, write to all backends
- **failover**: Use backup backends if primary fails
- **sync**: Read/write from all backends simultaneously

### AWS S3 Configuration
```bash
# .env configuration for S3
STORAGE_BACKEND=s3
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
S3_BUCKET_NAME=polymer-extractor-bucket
```

### Appwrite Configuration
```bash
# .env configuration for Appwrite
STORAGE_BACKEND=appwrite
APPWRITE_ENDPOINT=https://cloud.appwrite.io/v1
APPWRITE_PROJECT_ID=your_project_id
APPWRITE_API_KEY=your_api_key
APPWRITE_BUCKET_ID=polymer-extractor-bucket
```

## Service Access Points

### API Endpoints

- **Main API**: http://127.0.0.1:8000
- **Swagger Documentation**: http://127.0.0.1:8000/docs
- **ReDoc Documentation**: http://127.0.0.1:8000/redoc
- **Project Documentation**: http://127.0.0.1:8000/api/docs-ui
- **Health Check**: http://127.0.0.1:8000/api/servers/status

### Database Interfaces

- **Neo4j Browser**: http://localhost:7474
- **pgAdmin Interface**: http://localhost:5050 (when enabled)
- **GROBID API**: http://localhost:8070

### Service Health Verification

```bash
# Check all services
./server.sh status

# Test individual endpoints
curl http://127.0.0.1:8000/                           # API health
curl http://localhost:8070/api/isalive                # GROBID status
curl http://localhost:7474/                           # Neo4j browser
```

## API Testing with Postman

The project includes comprehensive Postman collections for API testing:

### Available Collections

- **setup.postman_collection.json**: System initialization and configuration
- **session.postman_collection.json**: User and session management
- **grobid.postman_collection.json**: PDF processing and document conversion
- **models.postman_collection.json**: Model synchronization and management
- **documentation.postman_collection.json**: Documentation API testing

### Using Postman Collections

1. **Import Collections**:
   ```bash
   # Open Postman
   # File → Import → Select files from postman/ directory
   ```

2. **Configure Environment Variables**:
   ```json
   {
     "pnlp": "http://127.0.0.1:8000",
     "session_id": "demo_session",
     "user_id": "demo_user"
   }
   ```

3. **Run Collection Tests**:
   - Start with `setup` collection for system initialization
   - Use `session` collection for user management
   - Test document processing with `grobid` collection
   - Verify model operations with `models` collection

## Troubleshooting Common Issues

### Port Conflicts

```bash
# Check port usage
./server.sh status

# Resolve conflicts automatically
./server.sh services  # Script detects and provides resolution guidance

# Manual resolution
sudo lsof -i :5432    # Check PostgreSQL port
sudo lsof -i :7687    # Check Neo4j port
sudo lsof -i :8070    # Check GROBID port
```

### Service Startup Issues

```bash
# View detailed logs
./server.sh logs

# Check individual service health
docker ps --filter name=polymer_postgres
docker ps --filter name=polymer_neo4j
docker ps --filter name=polymer_grobid

# Restart specific service
docker restart polymer_postgres
```

### Database Connection Issues

```bash
# Clear database locks
./server.sh clean

# Reinitialize database
./server.sh reset
./server.sh db-init
```

### Storage Backend Issues

```bash
# Verify storage configuration
ls -la workspace/public/  # Local storage check

# Test storage connectivity
curl -X GET http://127.0.0.1:8000/api/setup/check-storage
```

## Performance Optimization

### Memory Configuration

**GROBID Memory Tuning** (in docker-compose.services.yml):
```yaml
grobid:
  environment:
    JAVA_OPTS: "-Xmx4g"  # Adjust based on available memory
```

**Docker Resource Limits**:
```bash
# Monitor resource usage
docker stats

# Adjust Docker Desktop settings:
# Settings → Resources → Advanced
# Recommended: 8GB RAM, 4 CPUs
```

### Database Performance

```bash
# PostgreSQL optimization
./server.sh logs postgres  # Monitor query performance

# Neo4j optimization
./server.sh kg-status      # Check graph statistics
```

## Production Deployment

### Production Environment Setup

```bash
# Production environment configuration
cp .env.example .env.production
# Configure production values:
# - Secure passwords
# - Production storage backend
# - Monitoring endpoints
# - Resource limits
```

### Production Service Management

```bash
# Start production services
./server.sh services --no-pgadmin

# Monitor production health
./server.sh status
./server.sh logs --tail=100
```

### Security Considerations

- **Environment Variables**: Never commit `.env` files to version control
- **Database Security**: Use strong passwords and network isolation
- **API Security**: Configure authentication and rate limiting
- **Storage Security**: Use IAM roles and encrypted storage backends
- **Container Security**: Regular image updates and vulnerability scanning

## Development Best Practices

### Code Development Workflow

```bash
# Always activate virtual environment first
source .venv/bin/activate

# Keep services running during development
./server.sh services

# Restart API after code changes
./server.sh app stop
./server.sh app

# Test changes with Postman collections
# Import and run relevant collection tests
```

### Database Schema Changes

```bash
# Reset database for schema changes
./server.sh reset
./server.sh db-init

# Or clear data only
./server.sh db-clear
```

### Knowledge Graph Updates

```bash
# Update knowledge graph schema
./server.sh kg-clear
./server.sh kg-init

# Verify changes
./server.sh kg-status
```

This comprehensive guide covers all major aspects of running the Polymer NLP Extractor project across different environments and use cases. Refer to **1. Introduction** for system overview and **2. Project Structure** for detailed architectural information.
