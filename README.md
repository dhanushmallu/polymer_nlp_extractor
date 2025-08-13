# Polymer NLP Extractor

A comprehensive Natural Language Processing pipeline for extracting polymer-related entities from scientific literature using ensemble machine learning models and knowledge graphs.

## Overview

This project extracts polymer entities (POLYMER, PROPERTY, VALUE, UNIT, SYMBOL) from research papers using:
- **Ensemble ML Models**: Multiple transformer models for robust entity recognition
- **Knowledge Graph**: Neo4j-powered semantic validation and relationship modeling
- **PostgreSQL**: Structured data storage and analytics
- **Appwrite**: File storage and bucket management

## Prerequisites

- Python 3.8+
- Docker & Docker Compose (recommended)
- PostgreSQL 15+
- Neo4j 5.15+

---

## Installation Guide

### 1. Neo4j Installation

#### Option A: Docker (Recommended)
```bash
# Create docker-compose.yml for databases
cat > docker-compose.yml << 'EOF'
version: '3.8'
services:
  neo4j:
    image: neo4j:5.15
    container_name: polymer_neo4j
    ports:
      - "7474:7474"  # Browser interface
      - "7687:7687"  # Bolt protocol
    environment:
      - NEO4J_AUTH=neo4j/polymer123
      - NEO4J_PLUGINS=["apoc"]
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs

  postgres:
    image: postgres:15
    container_name: polymer_postgres
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=polymer_nlp
      - POSTGRES_USER=polymer_user
      - POSTGRES_PASSWORD=polymer123
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  neo4j_data:
  neo4j_logs:
  postgres_data:
EOF

# Start both databases
docker-compose up -d
```

#### Option B: Native Installation (Linux/Ubuntu)
```bash
# Add Neo4j repository
wget -O - https://debian.neo4j.com/neotechnology.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/neotechnology.gpg
echo 'deb [signed-by=/etc/apt/keyrings.neotechnology.gpg] https://debian.neo4j.com stable latest' | sudo tee /etc/apt/sources.list.d/neo4j.list
sudo apt update && sudo apt install neo4j

# Start Neo4j service
sudo systemctl enable neo4j
sudo systemctl start neo4j
```

#### Option C: macOS (Intel/Silicon)
```bash
# Install via Homebrew
brew install neo4j

# Start Neo4j
brew services start neo4j
```

### 2. PostgreSQL Installation

#### Linux/Ubuntu
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib

# Start PostgreSQL
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Create database and user
sudo -u postgres psql << 'EOF'
CREATE DATABASE polymer_nlp;
CREATE USER polymer_user WITH PASSWORD 'polymer123';
GRANT ALL PRIVILEGES ON DATABASE polymer_nlp TO polymer_user;
\q
EOF
```

#### macOS (Intel/Silicon)
```bash
# Install PostgreSQL
brew install postgresql@15

# Start PostgreSQL service
brew services start postgresql@15

# Create database
createdb polymer_nlp
```

### 3. macOS Silicon/Intel Compatibility

#### WeasyPrint Dependencies (macOS)
WeasyPrint requires additional system dependencies on macOS:

```bash
# Install system dependencies via Homebrew
brew install cairo pango gdk-pixbuf libffi

# For Silicon Macs, ensure proper linking
export PKG_CONFIG_PATH="/opt/homebrew/lib/pkgconfig"
export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"

# For Intel Macs
export PKG_CONFIG_PATH="/usr/local/lib/pkgconfig"
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"

# Add to your shell profile (.zshrc or .bash_profile)
echo 'export PKG_CONFIG_PATH="/opt/homebrew/lib/pkgconfig"' >> ~/.zshrc
echo 'export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"' >> ~/.zshrc
```

#### Additional macOS Dependencies
```bash
# Install other required system packages
brew install libxml2 libxslt

# For GROBID PDF processing
brew install openjdk@11
sudo ln -sfn /opt/homebrew/opt/openjdk@11/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk-11.jdk
```

### 4. Python Package Installation

#### Clone and Install Project
```bash
# Clone the repository
git clone <repository-url>
cd polymer_nlp_extractor

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e .

# Install additional dependencies
pip install -r requirements.txt
```

#### Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configurations
nano .env
```

**Required Environment Variables:**
```bash
# Appwrite Configuration
APPWRITE_ENDPOINT=https://cloud.appwrite.io/v1
APPWRITE_PROJECT_ID=your_project_id
APPWRITE_API_KEY=your_api_key
APPWRITE_DATABASE_ID=your_database_id
APPWRITE_BUCKET_ID=your_bucket_id

# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=polymer_nlp
POSTGRES_USER=polymer_user
POSTGRES_PASSWORD=polymer123

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=polymer123

# ML Configuration
WANDB_API_KEY=your_wandb_key
HF_TOKEN=your_huggingface_token

# GROBID Configuration
GROBID_API_URL=http://localhost:8070
```

### 5. Running with Uvicorn

#### Start the API Server
```bash
# Activate virtual environment
source venv/bin/activate

# Start the FastAPI server
uvicorn polymer_extractor.main:app --host 0.0.0.0 --port 8000 --reload

# For production
uvicorn polymer_extractor.main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### Development Mode
```bash
# Run with auto-reload for development
uvicorn polymer_extractor.main:app --reload --log-level debug
```

#### Docker Deployment
```bash
# Build Docker image
docker build -t polymer-nlp-extractor .

# Run container
docker run -d \
  --name polymer-api \
  -p 8000:8000 \
  -v $(pwd)/.env:/app/.env \
  polymer-nlp-extractor
```

### 6. API Endpoints Usage

#### Available Endpoints
Based on the API structure, the following endpoints are available:

##### Setup & Configuration
```bash
# Initialize system resources
POST /api/setup/initialize
curl -X POST "http://localhost:8000/api/setup/initialize"

# Reset system (development only)
POST /api/setup/reset
curl -X POST "http://localhost:8000/api/setup/reset"
```

##### Document Processing
```bash
# Upload and process PDF via GROBID
POST /api/grobid/process
curl -X POST "http://localhost:8000/api/grobid/process" \
  -F "file=@path/to/paper.pdf"

# Process TEI XML
POST /api/preprocessing/tei
curl -X POST "http://localhost:8000/api/preprocessing/tei" \
  -H "Content-Type: application/json" \
  -d '{"tei_path": "/path/to/file.xml"}'

# Token packing
POST /api/preprocessing/tokenpack
curl -X POST "http://localhost:8000/api/preprocessing/tokenpack" \
  -H "Content-Type: application/json" \
  -d '{"tei_path": "/path/to/cleaned_file.xml"}'
```

##### Machine Learning Operations
```bash
# Fine-tune models
POST /api/finetune/train
curl -X POST "http://localhost:8000/api/finetune/train" \
  -H "Content-Type: application/json" \
  -d '{"models": ["bert", "distilbert"], "epochs": 3}'

# Run ensemble inference
POST /api/inference/ensemble
curl -X POST "http://localhost:8000/api/inference/ensemble" \
  -H "Content-Type: application/json" \
  -d '{"tei_path": "/path/to/processed_file.xml"}'

# Evaluate model performance
POST /api/evaluation/evaluate
curl -X POST "http://localhost:8000/api/evaluation/evaluate" \
  -H "Content-Type: application/json" \
  -d '{"tei_path": "/path/to/file.xml", "threshold": 0.70}'
```

##### Ground Truth Management
```bash
# Upload ground truth data
POST /api/groundtruth/upload
curl -X POST "http://localhost:8000/api/groundtruth/upload" \
  -F "file=@training_data.csv" \
  -F "type=training"

# List available datasets
GET /api/groundtruth/datasets
curl "http://localhost:8000/api/groundtruth/datasets?type=testing"
```

##### Session Management
```bash
# Create extraction session
POST /api/session/create
curl -X POST "http://localhost:8000/api/session/create" \
  -H "Content-Type: application/json" \
  -d '{"session_name": "experiment_1", "config": {...}}'

# Get session results
GET /api/session/{session_id}/results
curl "http://localhost:8000/api/session/12345/results"
```

## Testing the Installation

### 1. Verify Database Connections
```bash
# Test PostgreSQL
psql -h localhost -U polymer_user -d polymer_nlp -c "SELECT version();"

# Test Neo4j (browser)
open http://localhost:7474
# Login: neo4j/polymer123
```

### 2. Test API Health
```bash
# Check API health
curl http://localhost:8000/health

# Test setup initialization
curl -X POST http://localhost:8000/api/setup/initialize
```

### 3. Run Sample Processing
```bash
# Process a sample PDF
curl -X POST "http://localhost:8000/api/grobid/process" \
  -F "file=@workspace/raw_inputs/sample.pdf"
```

## Project Structure

```
polymer_nlp_extractor/
├── polymer_extractor/           # Main package
│   ├── api/                    # FastAPI endpoints
│   ├── services/               # Business logic services
│   ├── storage/                # Database clients
│   ├── repositories/           # Data access layer
│   ├── knowledge_graph/        # Neo4j integration
│   └── utils/                  # Utilities
├── workspace/                  # Processing workspace
│   ├── models/                 # ML models
│   ├── datasets/               # Training data
│   └── exports/                # Results
├── notebooks/                  # Jupyter notebooks
└── model_updates/              # Documentation
```

## Development

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest tests/ -v
```

### Jupyter Notebook
```bash
# Start Jupyter for notebooks
jupyter lab notebooks/
```

## Troubleshooting

### Common Issues

#### WeasyPrint Installation (macOS)
```bash
# If WeasyPrint fails to install
For Apple Silicon (M series) Macs, use the following command to ensure Homebrew installs packages for the correct architecture:

```bash
arch -arm64 brew install cairo pango gdk-pixbuf libffi
```
pip install --no-cache-dir WeasyPrint
```

#### Neo4j Connection Issues
```bash
# Check if Neo4j is running
docker ps | grep neo4j
# or
sudo systemctl status neo4j
```

#### PostgreSQL Permission Issues
```bash
# Fix PostgreSQL permissions
sudo -u postgres createuser --superuser $USER
createdb polymer_nlp
```

### Log Locations
- **API Logs**: `workspace/system_logs/`
- **Neo4j Logs**: Docker volume `neo4j_logs` or `/var/log/neo4j/`
- **PostgreSQL Logs**: `/var/log/postgresql/`

## Documentation

- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **Model Updates**: [`model_updates/`](model_updates/)
- **Project Structure**: [`project_structure.md`](project_structure.md)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and test thoroughly
4. Submit a pull request

## License

[Add your license information here]