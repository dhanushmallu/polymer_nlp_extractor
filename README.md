# Polymer NLP Extractor

A comprehensive Natural Language Processing pipeline for extracting polymer-related entities from scientific literature using ensemble machine learning models and knowledge graphs.

## 🚨 **Platform Compatibility**

**IMPORTANT**: This project **does not support Windows**. It is designed for and tested on:

- ✅ **Linux** (Ubuntu 20.04+, Debian 11+)
- ✅ **macOS** (Intel and Apple Silicon)

Windows users should use WSL2 (Windows Subsystem for Linux) with Ubuntu.

## Overview

This project extracts polymer entities (POLYMER, PROPERTY, VALUE, UNIT, SYMBOL) from research papers using:

- **Ensemble ML Models**: Multiple transformer models for robust entity recognition
- **Knowledge Graph**: Neo4j-powered semantic validation and relationship modeling
- **PostgreSQL**: Structured data storage with automated schema management
- **GROBID**: Document processing for scientific PDFs
- **Docker Services**: Containerized infrastructure for easy deployment

## Prerequisites

- **Python 3.8+** 
- **Docker** and **Docker Compose** (required for services)
- **Git** (for repository management)
- **Internet connection** for downloads and package installation

## 🚀 **Quick Start (Recommended)**

### **1. Clone and Setup Project**

```bash
# Clone the repository
git clone <repository-url>
cd polymer_nlp_extractor

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux

# Install project dependencies
pip3 install -e .
pip3 install -r requirements.txt
```

### **2. Environment Configuration**

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configurations (optional - defaults work for Docker setup)
nano .env
```

### **3. Start Infrastructure Services**

```bash
# Start all services (PostgreSQL, Neo4j, GROBID) in Docker
./server.sh --services-only

# This will:
# - Start PostgreSQL on port 5432
# - Start Neo4j on port 7687 (web UI: http://localhost:7474)
# - Start GROBID on port 8070
# - All services run in isolated Docker containers
```

### **4. Start Application**

```bash
# Start the Python API (in a new terminal if needed)
./server.sh --app-only

# Or start everything together:
./server.sh
```

### **5. Verify Installation**

```bash
# Check service status
./server.sh --status

# Test API
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/api/servers/status
```

🎉 **You're ready to go!** The API will be available at `http://127.0.0.1:8000`

---

## 🐳 **Docker Services Setup (Recommended)**

The easiest way to run this project is using Docker for infrastructure services. This approach provides:

### **Key Benefits:**

- ✅ **No manual database installation** required
- ✅ **No root privileges** needed for your application
- ✅ **Services run in isolation** (safe container privileges)
- ✅ **Consistent across environments** (dev/staging/production)
- ✅ **Easy cleanup** and management
- ✅ **Fast startup** - Services start independently
- ✅ **Hot reload** - Python changes don't restart services
- ✅ **Production-ready** - Mirrors cloud deployment patterns

### **How It Works:**

1. **Infrastructure Services** (PostgreSQL, Neo4j, GROBID) run in Docker containers
2. **Your Python Application** runs natively and connects to containerized services
3. **Clean separation** eliminates root privilege issues
4. **Environment variables** provide seamless configuration

### **Docker Requirements**

```bash
# Install Docker (Linux)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# Restart your computer to apply group changes

# Install Docker (macOS)
# Download Docker Desktop from https://www.docker.com/products/docker-desktop
# Or use Homebrew:
brew install --cask docker

# Verify Docker installation
docker --version
docker compose version
```

**NOTE: Rembember to restart your Computer to apply all changes. If Deploying to a server, Log out and Log in back again to apply Group Changes.** 

### **Docker Permission Setup (Linux)**

**Important**: On Linux, Docker requires special permissions. You'll need to add your user to the docker group:

```bash
# Add your user to the docker group (one-time setup)
sudo usermod -aG docker $USER

# Apply the change (choose one):
newgrp docker                    # Apply immediately
# OR log out and back in         # Apply permanently

# Verify group membership
groups $USER | grep docker

# Test Docker access
docker ps
```

**If you encounter permission errors:**

```bash
# Error: "permission denied while trying to connect to the Docker daemon socket"
# Solution: Our enhanced script automatically handles this

./server.sh --services-only
# Script will detect permission issues and guide you or use sudo automatically
```

### **Service Management Commands**

```bash
# Start all services
./server.sh --services-only

# Check what's running
./server.sh --status

# Stop all services
./server.sh --stop-services

# Restart services
./server.sh --restart-services

# View service logs
docker compose -f docker-compose.services.yml logs
```

---

## 🛠 **Manual Installation (Advanced)**

If you prefer to install services manually or need custom configurations:

### **GROBID Installation**

GROBID is required for PDF processing. Choose your installation method:

#### **Option A: Docker GROBID (Recommended)**

```bash
# GROBID will be automatically started with other services
./server.sh --services-only
```

#### **Option B: Manual GROBID Installation**

**Linux:**

```bash
# Install Java 11 or higher
sudo apt update
sudo apt install openjdk-11-jdk

# Download and extract GROBID
cd workspace/
wget https://github.com/kermitt2/grobid/archive/0.8.2.zip
unzip 0.8.2.zip
cd grobid-0.8.2

# Build GROBID
./gradlew clean install

# Start GROBID server
./gradlew run
```

**macOS:**

```bash
# Install Java (Intel Macs)
brew install openjdk@11

# Install Java (Apple Silicon Macs)
arch -arm64 brew install openjdk@11

# Add Java to PATH
echo 'export PATH="/opt/homebrew/opt/openjdk@11/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Download and extract GROBID
cd workspace/
curl -L https://github.com/kermitt2/grobid/archive/0.8.2.zip -o grobid-0.8.2.zip
unzip grobid-0.8.2.zip
cd grobid-0.8.2

# Build GROBID (Apple Silicon compatibility)
arch -arm64 ./gradlew clean install

# Start GROBID server
arch -arm64 ./gradlew run
```

### **PostgreSQL Manual Setup**

#### **Install PostgreSQL**

**Linux (Ubuntu/Debian):**

```bash
# Update package list
sudo apt update

# Install PostgreSQL and additional tools
sudo apt install postgresql postgresql-contrib

# Start and enable PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**macOS:**

```bash
# Intel Macs
brew install postgresql
brew services start postgresql

# Apple Silicon Macs
arch -arm64 brew install postgresql
arch -arm64 brew services start postgresql
```

#### **Create Database and User**

```bash
# Switch to PostgreSQL user
sudo -u postgres psql

# Create database and user:
CREATE DATABASE polymer_db;
CREATE USER polymer_user WITH PASSWORD 'polymer_pass';
GRANT ALL PRIVILEGES ON DATABASE polymer_db TO polymer_user;
ALTER USER polymer_user CREATEDB;
\q
```

### **Neo4j Manual Setup**

#### **Install Neo4j**

**Linux (Ubuntu/Debian):**

```bash
# Add Neo4j repository
wget -O - https://debian.neo4j.com/neotechnology.gpg.key | sudo apt-key add -
echo 'deb https://debian.neo4j.com stable latest' | sudo tee /etc/apt/sources.list.d/neo4j.list

# Update and install
sudo apt update
sudo apt install neo4j

# Start Neo4j service
sudo systemctl start neo4j
sudo systemctl enable neo4j
```

**macOS:**

```bash
# Intel Macs
brew install neo4j
brew services start neo4j

# Apple Silicon Macs  
arch -arm64 brew install neo4j
arch -arm64 brew services start neo4j

# Alternative: Neo4j Desktop (supports both architectures)
# Download from https://neo4j.com/download/
```

#### **Configure Neo4j Authentication**

```bash
# Set initial password (command line)
neo4j-admin set-initial-password polymer_pass

# Or via web browser:
# 1. Open http://localhost:7474
# 2. Login with neo4j/neo4j (default)
# 3. Set new password to 'polymer_pass'
```

#### **Create Database**

```bash
# Connect via cypher-shell
cypher-shell -u neo4j -p polymer_pass

# Create database (if using Neo4j 4.0+)
CREATE DATABASE polymer_extractor_graph;
:use polymer_extractor_graph;
:exit
```

---

## 🔧 **Environment Configuration**

### **Required Environment Variables**

Copy and edit the environment file:

```bash
cp .env.example .env
nano .env  # Edit with your preferred editor
```

**Key Variables for Docker Setup:**

```bash
# API Server Configuration
API_HOST=127.0.0.1
API_PORT=8000

# Database Credentials (used by Docker containers)
POSTGRES_DB=polymer_db
POSTGRES_USER=polymer_user
POSTGRES_PASSWORD=polymer_pass

NEO4J_USER=neo4j
NEO4J_PASSWORD=polymer_pass

# Service Ports (Docker will map to these)
POSTGRES_PORT=5432
NEO4J_PORT=7687
GROBID_PORT=8070
```

**For Manual Installations:**
Update the credentials to match your manually created databases.

---

## 🚀 **Running the Application**

### **Development Workflow**

**Option 1: Full Stack (Services + Application)**

```bash
# Start everything together
./server.sh

# Services start first, then application
# API available at: http://127.0.0.1:8000
```

**Option 2: Separate Services and Application (Recommended for Development)**

```bash
# Terminal 1: Start services once
./server.sh --services-only

# Terminal 2: Start/stop application as needed
./server.sh --app-only
# Ctrl+C to stop app, services keep running

# Work on code, restart app anytime
./server.sh --app-only
```


**Option 3: Manual Service Management**

```bash
# If you have services installed manually
./server.sh --app-only

# The app will connect to your existing services
```

### **Daily Development Pattern**

```bash
# Morning: Start services once (they persist)
./server.sh --services-only

# Work: Start/stop Python app as needed
./server.sh --app-only     # Start app
# Make changes, restart app
# Ctrl+C, then restart

# Evening: Stop services when done
./server.sh --stop-services
```

### **Service Management**

```bash
# Check what's running
./server.sh --status

# Stop Docker services (keeps data)
./server.sh --stop-services

# Restart services
./server.sh --restart-services

# View Docker service logs
docker compose -f docker-compose.services.yml logs -f
```

---

## 📚 **API Documentation**

Once running, access interactive API documentation:

- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc
- **Service Status**: http://127.0.0.1:8000/api/servers/status

### **Quick API Test**

```bash
# Test API health
curl http://127.0.0.1:8000/

# Check service connectivity
curl http://127.0.0.1:8000/api/servers/status

# Test GROBID processing
curl -X POST http://127.0.0.1:8000/api/grobid/process \
  -F "file=@your_document.pdf"
```

---

## 🧪 **Apple Silicon Compatibility**

**Special Notes for Apple Silicon (M1/M2/M3) Macs:**

### **Architecture-Specific Commands**

```bash
# Use arch prefix for native Apple Silicon performance
arch -arm64 brew install postgresql
arch -arm64 brew install neo4j
arch -arm64 brew install openjdk@11

# Python virtual environment
arch -arm64 python3 -m venv .venv
source .venv/bin/activate
arch -arm64 pip3 install -e .
```

### **Docker on Apple Silicon**

```bash
# Docker Desktop automatically handles architecture
# No special commands needed for Docker containers
./server.sh --services-only
```

### **Java/GROBID on Apple Silicon**

```bash
# Ensure Java is ARM64 native
arch -arm64 java -version

# Build GROBID with ARM64 compatibility
cd workspace/grobid-0.8.2
arch -arm64 ./gradlew clean install
arch -arm64 ./gradlew run
```

---

## ⚠️ **Troubleshooting**

### **Common Issues**

**Docker Permission Errors (Linux):**

```bash
# Error: "permission denied while trying to connect to the Docker daemon socket"

# Solution 1: Add user to docker group (recommended)
sudo usermod -aG docker $USER
newgrp docker  # Apply immediately
docker ps      # Test access

# Solution 2: Use our enhanced script (auto-detects and guides)
./server.sh --services-only
# Script will detect permission issues and use sudo automatically

# Solution 3: Manual sudo usage
sudo ./server.sh --services-only
```

**Services Not Starting:**

```bash
# Check Docker status
docker --version
docker compose version

# Check if Docker daemon is running
sudo systemctl status docker    # Linux
docker info                     # General check

# Check port conflicts
./server.sh --status
lsof -i :5432 -i :7687 -i :8070 -i :8000

# View service logs
docker compose -f docker-compose.services.yml logs -f
```

**Docker Installation Issues:**

```bash
# Verify Docker installation
docker --version
docker compose version

# Install Docker if missing (Linux)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Desktop (macOS)
brew install --cask docker
```

**Permission Issues:**

```bash
# Make startup script executable
chmod +x server.sh

# Check file permissions
ls -la server.sh

# Fix if needed
chmod 755 server.sh
```

**Database Connection Issues:**

```bash
# Test PostgreSQL connection
psql -h localhost -U polymer_user -d polymer_db

# Test Neo4j connection  
cypher-shell -u neo4j -p polymer_pass

# Check GROBID
curl http://localhost:8070/api/isalive
```

**Apple Silicon Issues:**

```bash
# Force ARM64 architecture
export ARCHFLAGS="-arch arm64"
arch -arm64 pip3 install --upgrade pip

# Use Rosetta for compatibility issues
arch -x86_64 brew install <package>
```

---

## 📁 **Project Structure**

```
polymer_nlp_extractor/
├── polymer_extractor/          # Main application code
│   ├── api/                    # FastAPI route handlers
│   ├── services/               # Business logic services
│   ├── storage/                # Database clients and managers
│   └── utils/                  # Utilities and helpers
├── notebooks/                  # Jupyter notebooks for training
├── workspace/                  # Data, models, and processing files
├── docker-compose.services.yml # Docker services configuration
├── server.sh            # Enhanced startup script
├── .env.example               # Environment template
└── README.md                  # This file
```

# 3. Set new password

```

#### Create Database (Neo4j 4.0+)
```cypher
# Connect via Neo4j Browser (http://localhost:7474) or cypher-shell
# Create your database:
CREATE DATABASE your_graph_database_name;

# Switch to your database:
:use your_graph_database_name;
```

#### Test Connection

```bash
# Test connection via cypher-shell
cypher-shell -u your_username -p your_password -d your_graph_database_name

# You should see Neo4j prompt
your_username@your_graph_database_name> :exit
```

### 3. Environment Configuration

Update your `.env` file with the database credentials you created:

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your database configurations
nano .env
```

**Required Database Variables** (use your actual values):

```bash
# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=your_database_name
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=your_username
NEO4J_PASSWORD=your_neo4j_password
NEO4J_DATABASE=your_graph_database_name
```

### 4. Verify Database Setup

Before proceeding with the application setup, verify both databases are accessible:

```bash
# Test PostgreSQL connection
psql -h localhost -U your_username -d your_database_name -c "SELECT version();"

# Test Neo4j connection
echo "RETURN 'Neo4j is working!' AS message;" | cypher-shell -u your_username -p your_password -d your_graph_database_name
```

**🎯 Important Notes:**

- Replace `your_database_name`, `your_username`, `your_password`, etc. with your actual values
- Ensure both databases are running before starting the application
- The application will automatically create all necessary tables and schemas
- For production deployments, use strong passwords and consider SSL/TLS connections

---

## Installation Guide

### 1. Python Package Installation

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

## 💾 **Data Management**

### **Database Persistence**

**Docker Services:**

- Data is automatically persisted in Docker volumes
- Stopping containers preserves all data
- Data survives container restarts and rebuilds

```bash
# View Docker volumes
docker volume ls

# Backup data (optional)
docker compose -f docker-compose.services.yml exec postgres pg_dump -U polymer_user polymer_db > backup.sql
```

**Manual Installations:**

- Follow your system's standard backup procedures
- PostgreSQL: Use `pg_dump` for backups
- Neo4j: Use `neo4j-admin dump` for backups

### **Service URLs**

When running (Docker or manual):

- **API Server**: http://127.0.0.1:8000
- **PostgreSQL**: localhost:5432
- **Neo4j Browser**: http://localhost:7474
- **GROBID API**: http://localhost:8070
- **pgAdmin** (optional): http://localhost:5050

### **pgAdmin Setup (PostgreSQL Visual Interface)**

pgAdmin provides a web-based interface to view and manage PostgreSQL tables interactively.

**Starting pgAdmin:**
```bash
# Start pgAdmin along with other services
docker-compose --profile admin -f docker-compose.services.yml up -d
```

**Initial Setup:**
1. Open http://localhost:5050 in your browser
2. **Set Master Password**: When prompted, create a master password (this secures your pgAdmin session - choose something memorable)
3. **Connect to PostgreSQL Server**:
   - Right-click "Servers" → "Register" → "Server"
   - **General Tab**:
     - Name: `Polymer Extractor DB`
   - **Connection Tab**:
     - Host: `postgres` (Docker container name)
     - Port: `5432`
     - Maintenance database: `polymer_extractor`
     - Username: `pnlp_db_user`
     - Password: `9MF****jFdU`
   - Click "Save"

**Viewing Tables:**
- Navigate: Servers → Polymer Extractor DB → Databases → polymer_extractor → Schemas → public → Tables
- Right-click any table → "View/Edit Data" → "All Rows" to see table contents

**Available Tables:**
- `research_papers` - Main paper metadata
- `paper_sections` - Extracted paper sections
- `polymer_entities` - Identified polymer mentions
- `property_measurements` - Extracted property data
- `processing_metadata` - Processing status and metrics

**Notes:**
- Master password is session-based and provides security for your pgAdmin workspace
- PostgreSQL credentials are from the `.env` file configuration
- pgAdmin data persists in Docker volume `pgadmin_data`

---

## 🏗 **Development & Production**

### **Development Mode**

```bash
# Full development stack
./server.sh

# API runs with auto-reload enabled
# Services persist between application restarts
```

### **Production Considerations**

**Environment Variables:**

```bash
# Production settings
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING

# Use strong passwords
POSTGRES_PASSWORD=your_strong_password
NEO4J_PASSWORD=your_strong_password

# Enable SSL/TLS for databases (recommended)
```

**Docker Production:**

```bash
# Use production Docker Compose file
# (Create docker-compose.prod.yml with production settings)
docker compose -f docker-compose.prod.yml up -d
```

---

## 🤝 **Contributing**

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes** following the coding standards
4. **Test thoroughly** using the provided test suite
5. **Submit a pull request** with detailed description

### **Development Setup for Contributors**

```bash
# Clone your fork
git clone https://github.com/yourusername/polymer_nlp_extractor.git
cd polymer_nlp_extractor

# Set up development environment
python3 -m venv .venv
source .venv/bin/activate
pip3 install -e .[dev]  # Install with development dependencies

# Start services for testing
./server.sh --services-only

# Run tests
python3 -m pytest tests/
```

---

## 📄 **License**

[Add your license information here]

---

## 🆘 **Support**

**Documentation:**

- **API Docs**: http://127.0.0.1:8000/docs (when running)
- **Service Status**: http://127.0.0.1:8000/api/servers/status

**Common Commands:**

```bash
# Get help
./server.sh --help

# Check service status
./server.sh --status

# View logs
docker compose -f docker-compose.services.yml logs -f

# Restart everything
./server.sh --restart-services
./server.sh --app-only
```

**Issues:**

- Check existing issues in the repository
- Create new issues with detailed reproduction steps
- Include system information (OS, architecture, Docker version)

**Quick Health Check:**

```bash
# Verify everything is working
curl http://127.0.0.1:8000/api/servers/status | python3 -m json.tool
```

# Activate virtual environment

source .venv/bin/activate

# Start the FastAPI server using the startup script (recommended)

./server.sh

# Or start manually with environment variables

uvicorn polymer_extractor.main:app --host ${API_HOST:-127.0.0.1} --port ${API_PORT:-8000} --reload

```

#### Initialize Database Schema
```bash
# In another terminal, initialize the database schemas
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/init"

# Check system health
curl "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/databases/health"
```

**🔧 What the Application Does Automatically:**

- Creates all necessary tables in PostgreSQL
- Sets up indexes and constraints
- Creates Neo4j node labels and relationships
- Deploys Cypher constraints
- Validates schema integrity

**🚫 What the Application Does NOT Do:**

- Create databases (you must do this manually)
- Create database users (you must do this manually)
- Start/stop database services (you manage this)
- Install database software (you must do this manually)

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

### 4. Running with Uvicorn

#### Start the API Server

```bash
# Activate virtual environment
source .venv/bin/activate

# Recommended: Use the startup script (loads environment automatically)
./server.sh

# Manual: Start with environment variables
uvicorn polymer_extractor.main:app --host ${API_HOST:-127.0.0.1} --port ${API_PORT:-8000} --reload

# For production
uvicorn polymer_extractor.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000} --workers 4
```

#### Development Mode

```bash
# Run with auto-reload for development (uses environment variables)
uvicorn polymer_extractor.main:app --reload --log-level debug --host ${API_HOST:-127.0.0.1} --port ${API_PORT:-8000}
```

#### Docker Deployment

```bash
# Build Docker image
docker build -t polymer-nlp-extractor .

# Run container (databases still auto-managed)
docker run -d \
  --name polymer-api \
  -p 8000:8000 \
  -v $(pwd)/.env:/app/.env \
  -v /var/run/docker.sock:/var/run/docker.sock \
  polymer-nlp-extractor
```

### 5. API Endpoints Usage

#### Available Endpoints

Based on the API structure, the following endpoints are available:

**Note:** Replace `${API_BASE_URL}` with your configured API base URL (default: `http://127.0.0.1:8000`)

##### Setup & Database Management

```bash
# Initialize complete system (databases + Appwrite)
POST /api/setup/init
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/init"

# Check database health
GET /api/setup/databases/health
curl "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/databases/health"

# Start database services
POST /api/setup/databases/start
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/databases/start"

# Stop database services  
POST /api/setup/databases/stop
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/databases/stop"

# Restart database services
POST /api/setup/databases/restart
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/databases/restart"

# Bootstrap databases with schema deployment
POST /api/setup/databases/bootstrap
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/databases/bootstrap"

# Reset system (development only)
POST /api/setup/reset
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/reset"
```

##### Server Management (New)

```bash
# Check server status
GET /api/servers/status
curl "${API_BASE_URL:-http://127.0.0.1:8000}/api/servers/status"

# Start specific service
POST /api/servers/start/{service_name}
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/servers/start/postgresql"
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/servers/start/neo4j"
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/servers/start/grobid"

# Stop specific service
POST /api/servers/stop/{service_name}
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/servers/stop/grobid"
```

##### Document Processing

```bash
# Upload and process PDF via GROBID
POST /api/grobid/process
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/grobid/process" \
  -F "file=@path/to/paper.pdf"

# Process TEI XML
POST /api/preprocessing/tei
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/preprocessing/tei" \
  -H "Content-Type: application/json" \
  -d '{"tei_path": "/path/to/file.xml"}'

# Token packing
POST /api/preprocessing/tokenpack
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/preprocessing/tokenpack" \
  -H "Content-Type: application/json" \
  -d '{"tei_path": "/path/to/cleaned_file.xml"}'
```

##### Machine Learning Operations

```bash
# Fine-tune models (deprecated - use notebook instead)
POST /api/finetune/train
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/finetune/train" \
  -H "Content-Type: application/json" \
  -d '{"models": ["bert", "distilbert"], "epochs": 3}'

# Run ensemble inference
POST /api/inference/ensemble
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/inference/ensemble" \
  -H "Content-Type: application/json" \
  -d '{"tei_path": "/path/to/processed_file.xml"}'

# Evaluate model performance
POST /api/evaluation/evaluate
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/evaluation/evaluate" \
  -H "Content-Type: application/json" \
  -d '{"tei_path": "/path/to/file.xml", "threshold": 0.70}'
```

##### Ground Truth Management

```bash
# Upload ground truth data
POST /api/groundtruth/upload
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/groundtruth/upload" \
  -F "file=@training_data.csv" \
  -F "type=training"

# List available datasets
GET /api/groundtruth/datasets
curl "${API_BASE_URL:-http://127.0.0.1:8000}/api/groundtruth/datasets?type=testing"
```

##### Session Management

```bash
# Create extraction session
POST /api/session/create
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/session/create" \
  -H "Content-Type: application/json" \
  -d '{"session_name": "experiment_1", "config": {...}}'

# Get session results
GET /api/session/{session_id}/results
curl "${API_BASE_URL:-http://127.0.0.1:8000}/api/session/12345/results"
```

## Testing the Installation

### 1. Verify System Health

```bash
# Check overall API health
curl ${API_BASE_URL:-http://127.0.0.1:8000}/health

# Check database health specifically
curl "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/databases/health"

# Test system initialization
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/init"
```

### 2. Database Connection Verification

```bash
# The system automatically verifies database connections during startup
# Check the logs or health endpoint for connection status

# Manual verification (if needed):
# PostgreSQL: databases are auto-managed, no manual connection needed
# Neo4j: access browser interface at http://localhost:7474 (auto-started)
```

### 3. Run Sample Processing

```bash
# Process a sample PDF
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/grobid/process" \
  -F "file=@workspace/raw_inputs/sample.pdf"
```

## Database Management

### Automatic Features

- **Auto-startup**: Databases start automatically when the API server starts
- **Health monitoring**: Continuous health checking with automatic restart attempts  
- **Schema management**: PostgreSQL schema and Neo4j constraints deployed automatically
- **Safe shutdown**: Graceful database shutdown when API server stops
- **Docker integration**: Databases run in isolated Docker containers

### Manual Database Operations

```bash
# Start databases manually
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/databases/start"

# Stop databases manually  
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/databases/stop"

# Restart databases
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/databases/restart"

# Check database health
curl "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/databases/health"

# Full database bootstrap (schema + constraints)
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/databases/bootstrap"
```

### Database Access

- **PostgreSQL**: `localhost:5432` (auto-managed via Docker)
- **Neo4j Browser**: `http://localhost:7474` (auto-managed via Docker) 
- **Neo4j Bolt**: `bolt://localhost:7687` (auto-managed via Docker)

Default credentials are automatically configured from environment variables.

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

#### Database Connection Issues

```bash
# Check if database services are running
curl "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/databases/health"

# Restart database services
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/databases/restart"

# View Docker container status
docker ps | grep -E "(polymer_postgres|polymer_neo4j)"
```

#### Docker Issues

```bash
# Ensure Docker is running
docker --version
docker-compose --version

# Check database containers
docker-compose -f docker-compose.yml ps

# View database logs
docker logs polymer_postgres
docker logs polymer_neo4j
```

#### WeasyPrint Installation (macOS)

```bash
# If WeasyPrint fails to install
# For Apple Silicon (M series) Macs:
arch -arm64 brew install cairo pango gdk-pixbuf libffi
pip install --no-cache-dir WeasyPrint
```

#### Schema Deployment Issues

```bash
# Re-deploy database schema
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/databases/bootstrap"

# Check database logs for errors
docker logs polymer_postgres
docker logs polymer_neo4j
```

### Log Locations

- **API Logs**: `workspace/system_logs/`
- **Database Logs**: 
  - PostgreSQL: `docker logs polymer_postgres`
  - Neo4j: `docker logs polymer_neo4j`
- **Docker Compose Logs**: `docker-compose -f docker-compose.yml logs`

### Manual Database Recovery

If automatic database management fails:

```bash
# Stop all database containers
docker-compose -f docker-compose.yml down

# Remove database volumes (WARNING: deletes all data)
docker volume rm polymer_nlp_extractor_postgres_data
docker volume rm polymer_nlp_extractor_neo4j_data

# Restart system
curl -X POST "${API_BASE_URL:-http://127.0.0.1:8000}/api/setup/databases/bootstrap"
```

## Documentation

- **API Documentation**: ${API_BASE_URL:-http://127.0.0.1:8000}/docs (Swagger UI)
- **Model Updates**: [`model_updates/`](model_updates/)
- **Project Structure**: [`project_structure.md`](project_structure.md)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and test thoroughly
4. Submit a pull request

## License

[Add your license information here]
