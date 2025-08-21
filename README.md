# Polymer NLP Extractor

A comprehensive Natural Language Processing pipeline for extracting polymer-related entities from scientific literature using ensemble machine learning models and knowledge graphs.

## 🚨 **Platform Support**

**WINDOWS IS NOT SUPPORTED** - This project is designed exclusively for Unix-based systems:

- ✅ **Linux** (Ubuntu 20.04+, Debian 11+)
- ✅ **macOS Intel** (x86_64)
- ✅ **macOS Apple Silicon** (M1/M2/M3)

**Windows users must use WSL2 (Windows Subsystem for Linux) with Ubuntu.**

## Overview

This project extracts polymer entities (POLYMER, PROPERTY, VALUE, UNIT, SYMBOL) from research papers using:

- **Ensemble ML Models**: Multiple transformer models for robust entity recognition
- **Knowledge Graph**: Neo4j-powered semantic validation and relationship modeling
- **PostgreSQL**: Structured data storage with automated schema management
- **Flexible Storage**: Local, Appwrite, or S3 backends for file management
- **GROBID**: Document processing for scientific PDFs
- **Docker Services**: Containerized infrastructure for easy deployment

## Prerequisites

- **Python 3.8+** 
- **Docker** and **Docker Compose** (required for services)
- **Git** (for repository management)
- **Node.js** and **npm** (optional - required for Appwrite storage backend)
- **Internet connection** for downloads and package installation

## 🚀 **Quick Start**

### **1. Clone and Setup**

**Linux:**
```bash
git clone <repository-url>
cd polymer_nlp_extractor
python3 -m venv .venv
source .venv/bin/activate
pip3 install -e .
pip3 install -r requirements.txt
```

**macOS Intel:**
```bash
git clone <repository-url>
cd polymer_nlp_extractor
python3 -m venv .venv
source .venv/bin/activate
pip3 install -e .
pip3 install -r requirements.txt
```

**macOS Apple Silicon:**
```bash
git clone <repository-url>
cd polymer_nlp_extractor
arch -arm64 python3 -m venv .venv
source .venv/bin/activate
arch -arm64 pip3 install -e .
arch -arm64 pip3 install -r requirements.txt
```

### **2. Environment Configuration**

```bash
cp .env.example .env
nano .env
```

### **3. Start Services**

```bash
./server.sh services
```

### **4. Verify Installation**

```bash
./server.sh status
curl http://127.0.0.1:8000/
```

🎉 **You're ready!** API available at `http://127.0.0.1:8000`

## 📁 **Storage Configuration**

This project supports flexible storage backends with multi-backend routing:

- **Local Storage** (default): Files stored in `workspace/public/`
- **Appwrite Storage**: Cloud storage with CDN and backup
- **S3 Storage**: AWS S3 or S3-compatible storage

### **Multi-Backend Strategies**

Configure multiple backends simultaneously with different routing strategies:

```bash
# .env configuration
STORAGE_BACKENDS_ACTIVE=local,appwrite,s3  # Active backends
STORAGE_STRATEGY=sync                       # sync | replica | failover | primary
```

**Strategies:**
- **primary**: Use only the first backend
- **replica**: Read from primary, write to all
- **failover**: Use backup if primary fails
- **sync**: Read/write from all backends simultaneously

### **Storage Backend Setup**

**Local Storage (Default):**
```bash
# No additional setup required
# Files stored in: ./workspace/public/
STORAGE_BACKEND=local
STORAGE_PATH=./workspace/public
```

**AWS S3 Storage Setup:**

1. **Create AWS Account** (if needed):
   - Visit [AWS Console](https://aws.amazon.com/console/)
   - Sign up for AWS Free Tier

2. **Create IAM User with Minimal Permissions**:
   ```bash
   # Go to AWS Console → IAM → Users → Add users
   # Username: polymer-storage-user
   # Access type: Programmatic access
   ```

3. **Create Custom Policy** (Recommended - Minimal Permissions):
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "PolymerStorageAccess",
         "Effect": "Allow",
         "Action": [
           "s3:GetObject",
           "s3:PutObject",
           "s3:DeleteObject",
           "s3:ListBucket",
           "s3:CreateBucket",
           "s3:DeleteBucket",
           "s3:GetBucketLocation"
         ],
         "Resource": [
           "arn:aws:s3:::polymer-*",
           "arn:aws:s3:::polymer-*/*"
         ]
       }
     ]
   }
   ```

4. **Alternative: Use Managed Policy** (Less Secure):
   - Attach `AmazonS3FullAccess` policy to user
   - **Warning**: This gives full S3 access - use only for testing

5. **Get Credentials**:
   - In IAM → Users → Your User → Security credentials
   - Click "Create access key" → "Application running outside AWS"
   - Copy both **Access Key ID** and **Secret Access Key**

6. **Configure in .env**:
   ```bash
   # S3 Configuration
   S3_ENABLED=true
   S3_REGION=us-east-1
   S3_ACCESS_KEY_ID=your-access-key-id-here
   S3_SECRET_ACCESS_KEY=your-secret-access-key-here
   # S3_ENDPOINT_URL=  # Leave empty for AWS, set for S3-compatible services
   ```

**Appwrite Storage Setup:**

1. **Create Appwrite Account**:
   - Visit [Appwrite Cloud](https://cloud.appwrite.io)
   - Create account and project

2. **Create Storage Bucket**:
   ```bash
   # In Appwrite Console → Storage → Create Bucket
   # Bucket ID: polymer-files
   # Name: Polymer Files
   # Permissions: Grant appropriate read/write access
   ```

3. **Create API Key with Proper Scopes**:
   ```bash
   # In Appwrite Console → Settings → API Keys → Create API Key
   # Required scopes:
   # ✅ files.read
   # ✅ files.write
   # ✅ buckets.read
   # ✅ buckets.write
   ```

4. **Configure in .env**:
   ```bash
   # Appwrite Configuration
   APPWRITE_ENABLED=true
   APPWRITE_STORAGE_ENDPOINT=https://cloud.appwrite.io/v1
   APPWRITE_STORAGE_PROJECT_ID=your-project-id
   APPWRITE_STORAGE_API_KEY=your-api-key-with-storage-permissions
   ```

**Security Best Practices:**

- **AWS S3**: Use IAM roles in production, never hardcode credentials
- **Appwrite**: Rotate API keys regularly, use environment-specific projects
- **Local**: Ensure proper file permissions on storage directory
- **Environment**: Never commit `.env` files to version control

**Bucket Management:**

The storage client automatically creates buckets as needed:
- S3: Creates buckets with proper region configuration
- Appwrite: Creates buckets with default permissions
- Local: Creates directories as filesystem "buckets"

## 🐳 **Docker Setup**

### **Installation**

**Linux:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# Restart your computer
```

**macOS Intel:**
```bash
brew install --cask docker
```

**macOS Apple Silicon:**
```bash
arch -arm64 brew install --cask docker
```

### **Permission Setup (Linux Only)**

```bash
sudo usermod -aG docker $USER
newgrp docker
docker ps
```

**If permission errors occur:**
```bash
./server.sh services
# Script detects permission issues and provides guidance
```

### **Service Management**

```bash
./server.sh services      # Start services
./server.sh pgadmin       # Start with pgAdmin
./server.sh status        # Check status
./server.sh stop          # Stop services
./server.sh clean         # Stop and free ports (keep data)
./server.sh reset         # Remove all data
./server.sh purge         # Remove everything
./server.sh logs          # View logs
```

## 🛠 **Manual Installation (Advanced)**

### **GROBID Installation**

**Option A: Docker GROBID (Recommended)**
```bash
./server.sh services
```

**Option B: Manual GROBID Installation**

**Linux:**
```bash
sudo apt update
sudo apt install openjdk-11-jdk
cd workspace/
wget https://github.com/kermitt2/grobid/archive/0.8.2.zip
unzip 0.8.2.zip
cd grobid-0.8.2
./gradlew clean install
./gradlew run
```

**macOS Intel:**
```bash
brew install openjdk@11
cd workspace/
curl -L https://github.com/kermitt2/grobid/archive/0.8.2.zip -o grobid-0.8.2.zip
unzip grobid-0.8.2.zip
cd grobid-0.8.2
./gradlew clean install
./gradlew run
```

**macOS Apple Silicon:**
```bash
arch -arm64 brew install openjdk@11
echo 'export PATH="/opt/homebrew/opt/openjdk@11/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
cd workspace/
curl -L https://github.com/kermitt2/grobid/archive/0.8.2.zip -o grobid-0.8.2.zip
unzip grobid-0.8.2.zip
cd grobid-0.8.2
arch -arm64 ./gradlew clean install
arch -arm64 ./gradlew run
```

### **PostgreSQL Manual Setup**

**Linux:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
sudo -u postgres psql
CREATE DATABASE polymer_extractor;
CREATE USER pnlp_db_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE polymer_extractor TO pnlp_db_user;
ALTER USER pnlp_db_user CREATEDB;
\q
```

**macOS Intel:**
```bash
brew install postgresql
brew services start postgresql
createdb polymer_extractor
createuser -s pnlp_db_user
```

**macOS Apple Silicon:**
```bash
arch -arm64 brew install postgresql
arch -arm64 brew services start postgresql
createdb polymer_extractor
createuser -s pnlp_db_user
```

### **Neo4j Manual Setup**

**Linux:**
```bash
wget -O - https://debian.neo4j.com/neotechnology.gpg.key | sudo apt-key add -
echo 'deb https://debian.neo4j.com stable latest' | sudo tee /etc/apt/sources.list.d/neo4j.list
sudo apt update
sudo apt install neo4j
sudo systemctl start neo4j
sudo systemctl enable neo4j
neo4j-admin set-initial-password your_password
```

**macOS Intel:**
```bash
brew install neo4j
brew services start neo4j
neo4j-admin set-initial-password your_password
```

**macOS Apple Silicon:**
```bash
arch -arm64 brew install neo4j
arch -arm64 brew services start neo4j
neo4j-admin set-initial-password your_password
```

## 🔧 **Environment Configuration**

```bash
cp .env.example .env
nano .env
```

### **Key Variables**

```bash
# API Server
API_HOST=127.0.0.1
API_PORT=8000

# Storage Backend (local | appwrite | s3)
STORAGE_BACKEND=local
STORAGE_PATH=./workspace/public

# Database (Docker defaults)
POSTGRES_DB=polymer_extractor
POSTGRES_USER=pnlp_db_user
POSTGRES_PASSWORD=9MFiCQtz2PYZdChRK7VAMWtTKGTQZFKqjFdU

# Neo4j (Docker defaults)
NEO4J_USER=neo4j
NEO4J_PASSWORD=37njY9TNEnmUxATqUGBvUZj9EqFDyxWvLspX

# pgAdmin (optional)
PGADMIN_DEFAULT_EMAIL=admin@example.com
PGADMIN_DEFAULT_PASSWORD=admin123
```

## 🚀 **Running the Application**

### **Development Workflow**

**Full Stack:**
```bash
./server.sh                 # Start everything
```
**Start API server separately for DEBUGGING**
>**NOTE:** GROBID, PosgreSQL and NEO4j must be running for the api to start, if you try running without them, the app will crash.

```
source .venv/bin/activate && cd /home/kibocha/workspace/polymer_nlp_extractor && uvicorn polymer_extractor.main:app --host 127.0.0.1 --port 8000
```

**Separate Services:**
```bash
./server.sh services        # Start services once
./server.sh app             # Start/stop app as needed
```

**With pgAdmin:**
```bash
./server.sh pgadmin         # Start services + pgAdmin
# pgAdmin: http://localhost:5050 (HTTP)
# Login: admin@example.com / admin123
```

### **Daily Pattern**

```bash
./server.sh services        # Morning: start services
./server.sh app             # Work: start/restart app
./server.sh stop            # Evening: stop everything
```

### **Service Commands**

```bash
./server.sh status          # Check status
./server.sh restart         # Restart services
./server.sh logs            # View logs
./server.sh clean           # Stop and free ports
./server.sh reset           # Remove data
./server.sh purge           # Remove everything
```

## 📚 **API Documentation**

- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc
- **Service Status**: http://127.0.0.1:8000/api/servers/status

### Postman collection

- Import `postman/setup.postman_collection.json` into Postman.
- Set the environment/global variable `pnlp` to your API base (default: `http://localhost:8000`).
- The collection includes: Setup Initialize, Clean Install, Reset, Health, and a legacy Analyze route.

### **Quick Test**

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/api/servers/status
curl -X POST http://127.0.0.1:8000/api/grobid/process -F "file=@your_document.pdf"
```

## 🗄️ **Database Management**

### **pgAdmin Web Interface**

```bash
./server.sh pgadmin
# Access: http://localhost:5050
# Login: admin@example.com / admin123
# PostgreSQL Host: postgres (container name)
```

### Add a server in pgAdmin (connection fields)

Use these values when registering a new server in pgAdmin (Servers → Register → Server):

1) General tab
- Name: polymer-postgres (any friendly name)

2) Connection tab
- Host name/address: postgres
- Port: 5432
- Maintenance database: polymer_extractor
- Username: pnlp_db_user
- Password: use the value from `.env` (POSTGRES_PASSWORD)
- Save password: Yes

3) SSL tab
- SSL mode: Disable

4) Advanced tab (optional)
- Role: leave blank
- Service: leave blank

5) Save
- Click Save; the server should appear under Servers → polymer-postgres.

Notes
- These values match docker-compose defaults where pgAdmin and PostgreSQL run on the same Compose network; the service hostname is `postgres`.
- If you override credentials, use your `.env` values (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB).
- pgAdmin UI runs at http://localhost:5050 (HTTP).

### **Direct Access**

```bash
docker exec -it polymer_postgres psql -U pnlp_db_user -d polymer_extractor
docker exec -it polymer_neo4j cypher-shell -u neo4j
# Neo4j browser: http://localhost:7474
```

## ⚠️ **Troubleshooting**

### **Docker Permission Issues (Linux Only)**

```bash
sudo usermod -aG docker $USER
newgrp docker
docker ps
# If issues persist: sudo ./server.sh services
```

### **Docker File Ownership Issues**

**Problem**: Docker containers may create files with container user ownership instead of your user.

**Solution**:
```bash
# Fix existing ownership issues
./fix-docker-ownership.sh

# Restart services to apply user mapping
./server.sh stop
./server.sh services
```

**Prevention**: The `docker-compose.services.yml` now includes user mapping using `DOCKER_UID` and `DOCKER_GID` variables to prevent this issue.

**Note**: If you see "UID: readonly variable" errors, the system automatically uses `DOCKER_UID`/`DOCKER_GID` instead of the system's readonly `UID`/`GID` variables.

### **Service Issues**

```bash
./server.sh status                    # Check status
./server.sh logs                      # View logs
lsof -i :5432 -i :7687 -i :8070      # Check port conflicts
./server.sh restart                   # Restart services
```

**Environment Variable Issues**: If you see database connectivity errors, ensure `.env` values don't have trailing comments that interfere with parsing.

**Address in Use Error**: If you see "Address already in use" on port 8000, wait a few seconds for the previous instance to fully shutdown or use:
```bash
pkill -f uvicorn                     # Kill existing uvicorn processes
./server.sh stop                     # Clean stop services
./server.sh                          # Restart
```

### **Database Connection Issues**

```bash
docker exec polymer_postgres psql -U pnlp_db_user -d polymer_extractor -c "SELECT version();"
docker exec polymer_neo4j cypher-shell -u neo4j -p your_password "RETURN 'OK'"
./server.sh clean
./server.sh services
```

### **Application Issues**

```bash
source .venv/bin/activate
pip3 install -e .
pip3 install -r requirements.txt
python3 --version                     # Should be 3.8+
./server.sh app
```

**Storage Upload Errors**: If you see `"BucketClient.upload_file() got an unexpected keyword argument 'local_path'"`, this has been fixed by updating the BucketClient API calls to use the correct parameters (`file_path`, `content`, `metadata`).

### **Platform-Specific Issues**

**Linux:**
```bash
sudo systemctl status docker
sudo systemctl stop postgresql        # Stop conflicting local services
sudo systemctl stop neo4j
```

**macOS Intel:**
```bash
brew services stop postgresql
brew services stop neo4j
```

**macOS Apple Silicon:**
```bash
arch -arm64 brew services stop postgresql
arch -arm64 brew services stop neo4j
export ARCHFLAGS="-arch arm64"
arch -arm64 pip3 install --upgrade pip
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
├── server.sh                   # Enhanced startup script
├── .env.example               # Environment template
└── README.md                  # This file
```

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes following the coding standards
4. Test thoroughly using the provided test suite
5. Submit a pull request with detailed description

## 📄 **License**

[Add your license information here]

---

For more detailed documentation, see the `model_updates/` directory and project structure documentation.

