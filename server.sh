#!/bin/bash

# Enhanced startup script with Docker service management
# Usage: ./server.sh [--services-only] [--app-only] [--help]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure system logs directory exists
mkdir -p workspace/system_logs

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to validate and update .env with defaults
validate_env_defaults() {
    print_status "Validating environment configuration..."
    
    # Create .env if it doesn't exist
    if [[ ! -f .env ]]; then
        print_status "Creating .env file with default values..."
        touch .env
    fi
    
    # Check and set database defaults from docker-compose
    if ! grep -q "^POSTGRES_DB=" .env || [[ -z "$(grep "^POSTGRES_DB=" .env | cut -d'=' -f2)" ]]; then
        echo "POSTGRES_DB=polymer_extractor" >> .env
        print_status "Added default POSTGRES_DB to .env"
    fi
    
    if ! grep -q "^POSTGRES_USER=" .env || [[ -z "$(grep "^POSTGRES_USER=" .env | cut -d'=' -f2)" ]]; then
        echo "POSTGRES_USER=pnlp_db_user" >> .env
        print_status "Added default POSTGRES_USER to .env"
    fi
    
    if ! grep -q "^POSTGRES_PASSWORD=" .env || [[ -z "$(grep "^POSTGRES_PASSWORD=" .env | cut -d'=' -f2)" ]]; then
        echo "POSTGRES_PASSWORD=9MFiCQtz2PYZdChRK7VAMWtTKGTQZFKqjFdU" >> .env
        print_status "Added default POSTGRES_PASSWORD to .env"
    fi
    
    if ! grep -q "^NEO4J_USER=" .env || [[ -z "$(grep "^NEO4J_USER=" .env | cut -d'=' -f2)" ]]; then
        echo "NEO4J_USER=neo4j" >> .env
        print_status "Added default NEO4J_USER to .env"
    fi
    
    if ! grep -q "^NEO4J_PASSWORD=" .env || [[ -z "$(grep "^NEO4J_PASSWORD=" .env | cut -d'=' -f2)" ]]; then
        echo "NEO4J_PASSWORD=37njY9TNEnmUxATqUGBvUZj9EqFDyxWvLspX" >> .env
        print_status "Added default NEO4J_PASSWORD to .env"
    fi
    
    if ! grep -q "^NEO4J_TRUST_ALL=" .env || [[ -z "$(grep "^NEO4J_TRUST_ALL=" .env | cut -d'=' -f2)" ]]; then
        echo "NEO4J_TRUST_ALL=true" >> .env
        print_status "Added default NEO4J_TRUST_ALL to .env"
    fi
    
    # Reload environment
    if [[ -f .env ]]; then
        set -a
        source .env
        set +a
    fi
}

# Function to ensure database exists
ensure_database_exists() {
    print_status "Ensuring database exists..."
    
    # Check if database exists, create if not
    DB_EXISTS=$(docker exec polymer_postgres psql -U "${POSTGRES_USER:-pnlp_db_user}" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB:-polymer_extractor}'")
    
    if [[ -z "$DB_EXISTS" ]]; then
        print_status "Creating database: ${POSTGRES_DB:-polymer_extractor}"
        docker exec polymer_postgres psql -U "${POSTGRES_USER:-pnlp_db_user}" -d postgres -c "CREATE DATABASE \"${POSTGRES_DB:-polymer_extractor}\";"
        print_success "Database created successfully"
    else
        print_status "Database already exists: ${POSTGRES_DB:-polymer_extractor}"
    fi
    
    # Check for old database name and suggest cleanup
    OLD_DB_EXISTS=$(docker exec polymer_postgres psql -U "${POSTGRES_USER:-pnlp_db_user}" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='polymer_extractor_db'")
    if [[ -n "$OLD_DB_EXISTS" ]]; then
        print_warning "Old database 'polymer_extractor_db' found. Consider dropping it to avoid confusion."
        print_status "To remove: docker exec polymer_postgres psql -U ${POSTGRES_USER:-pnlp_db_user} -d postgres -c \"DROP DATABASE polymer_extractor_db;\""
    fi
}
show_help() {
    cat << EOF
Enhanced Polymer NLP Extractor Server Manager

Usage: ./server.sh [OPTIONS]

Options:
    --services-only     Start only Docker services (PostgreSQL, Neo4j, GROBID)
    --app-only         Start only the Python application (assumes services are running)
    --stop-services    Stop all Docker services
    --restart-services Restart all Docker services
    --status          Show status of services and application
    --help            Show this help message

Examples:
    ./server.sh                    # Start services + application
    ./server.sh --services-only    # Start only Docker services
    ./server.sh --app-only         # Start only Python app
    ./server.sh --status           # Check service status

Environment Variables:
    API_HOST          API server host (default: 127.0.0.1)
    API_PORT          API server port (default: 8000)
    POSTGRES_PORT     PostgreSQL port (default: 5432)
    NEO4J_PORT        Neo4j port (default: 7687)
    GROBID_PORT       GROBID port (default: 8070)

For more configuration options, see .env.example
EOF
}

# Function to check if Docker is available and accessible
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        print_error "Please install Docker to use containerized services"
        return 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not available"
        print_error "Please install Docker Compose"
        return 1
    fi
    
    # Test Docker access
    if ! docker ps &> /dev/null; then
        print_error "Cannot access Docker daemon"
        print_error ""
        print_error "This usually means you need to:"
        print_error "1. Add your user to the docker group:"
        print_error "   sudo usermod -aG docker \$USER"
        print_error "   (then log out and back in)"
        print_error ""
        print_error "2. Or run with sudo:"
        print_error "   sudo ./server.sh --services-only"
        print_error ""
        print_error "3. Or check if Docker daemon is running:"
        print_error "   sudo systemctl status docker"
        return 1
    fi
    
    return 0
}

# Function to run docker command with fallback to sudo
run_docker_compose() {
    local args="$@"
    
    # Try regular docker compose first
    if docker compose version &> /dev/null; then
        if docker compose $args; then
            return 0
        else
            local exit_code=$?
            if [[ $exit_code -eq 1 ]] && [[ "$(docker compose $args 2>&1)" == *"permission denied"* ]]; then
                print_warning "Permission denied, trying with sudo..."
                sudo docker compose $args
            else
                return $exit_code
            fi
        fi
    else
        # Fallback to docker-compose
        if docker-compose $args; then
            return 0
        else
            local exit_code=$?
            if [[ $exit_code -eq 1 ]] && [[ "$(docker-compose $args 2>&1)" == *"permission denied"* ]]; then
                print_warning "Permission denied, trying with sudo..."
                sudo docker-compose $args
            else
                return $exit_code
            fi
        fi
    fi
}

# Function to check if services are running
check_service_port() {
    local port=$1
    local service_name=$2
    
    if command -v nc &> /dev/null; then
        if nc -z localhost "$port" 2>/dev/null; then
            return 0
        fi
    elif command -v telnet &> /dev/null; then
        if echo "quit" | telnet localhost "$port" &>/dev/null; then
            return 0
        fi
    else
        # Fallback: try to connect with curl/wget
        if command -v curl &> /dev/null; then
            if curl -s --connect-timeout 2 "localhost:$port" &>/dev/null; then
                return 0
            fi
        fi
    fi
    return 1
}

# Function to wait for service to be ready
wait_for_service() {
    local port=$1
    local service_name=$2
    local max_attempts=${3:-30}
    local attempt=1

    print_status "Waiting for $service_name to be ready on port $port..."
    
    while [ $attempt -le $max_attempts ]; do
        if check_service_port "$port" "$service_name"; then
            print_success "$service_name is ready on port $port"
            return 0
        fi
        
        if [ $((attempt % 5)) -eq 0 ]; then
            print_status "Still waiting for $service_name... (attempt $attempt/$max_attempts)"
        fi
        
        sleep 2
        ((attempt++))
    done
    
    print_error "$service_name failed to start on port $port after $((max_attempts * 2)) seconds"
    return 1
}

# Function to start Docker services
start_services() {
    print_status "Starting Docker services..."
    
    # Validate environment first
    validate_env_defaults
    
    if ! check_docker; then
        return 1
    fi

    # Check if compose file exists
    if [ ! -f "docker-compose.services.yml" ]; then
        print_error "docker-compose.services.yml not found"
        return 1
    fi

    # Start services using the wrapper function
    run_docker_compose -f docker-compose.services.yml up -d

    if [ $? -eq 0 ]; then
        print_success "Docker services started"
        
        # Wait for services to be ready
        wait_for_service "${POSTGRES_PORT:-5432}" "PostgreSQL" 30
        wait_for_service "${NEO4J_PORT:-7687}" "Neo4j" 30  
        wait_for_service "${GROBID_PORT:-8070}" "GROBID" 60
        
        # Ensure the database exists
        ensure_database_exists
        
        return 0
    else
        print_error "Failed to start Docker services"
        return 1
    fi
}

# Function to stop Docker services
stop_services() {
    print_status "Stopping Docker services..."
    
    if ! check_docker; then
        return 1
    fi

    if [ -f "docker-compose.services.yml" ]; then
        run_docker_compose -f docker-compose.services.yml down
        print_success "Docker services stopped"
    else
        print_warning "docker-compose.services.yml not found, nothing to stop"
    fi
}

# Function to show service status
show_status() {
    print_status "Checking service status..."
    
    # Check Docker services
    if check_docker && [ -f "docker-compose.services.yml" ]; then
        print_status "Docker services:"
        run_docker_compose -f docker-compose.services.yml ps
        echo
    fi

    # Check individual ports
    services=(
        "PostgreSQL:${POSTGRES_PORT:-5432}"
        "Neo4j:${NEO4J_PORT:-7687}"
        "GROBID:${GROBID_PORT:-8070}"
        "API Server:${API_PORT:-8000}"
    )

    print_status "Port status:"
    for service_info in "${services[@]}"; do
        IFS=':' read -r service_name port <<< "$service_info"
        if check_service_port "$port" "$service_name"; then
            echo -e "  ${GREEN}✓${NC} $service_name (port $port) - Running"
        else
            echo -e "  ${RED}✗${NC} $service_name (port $port) - Not accessible"
        fi
    done
}

# Function to start the Python application
start_application() {
    print_status "Starting Python application..."
    
    # Load environment variables
    if [ -f .env ]; then
        print_status "Loading environment from .env file..."
        set -a
        source .env
        set +a
    else
        print_warning ".env file not found, using defaults"
    fi

    # Set default values
    export API_HOST=${API_HOST:-127.0.0.1}
    export API_PORT=${API_PORT:-8000}
    export API_BASE_URL=${API_BASE_URL:-http://$API_HOST:$API_PORT}
    export POSTGRES_HOST=${POSTGRES_HOST:-localhost}
    export POSTGRES_PORT=${POSTGRES_PORT:-5432}
    export NEO4J_HOST=${NEO4J_HOST:-localhost}
    export NEO4J_PORT=${NEO4J_PORT:-7687}
    export GROBID_HOST=${GROBID_HOST:-localhost}
    export GROBID_PORT=${GROBID_PORT:-8070}

    print_status "Configuration:"
    echo "  API Server: $API_BASE_URL"
    echo "  PostgreSQL: $POSTGRES_HOST:$POSTGRES_PORT"
    echo "  Neo4j: $NEO4J_HOST:$NEO4J_PORT"
    echo "  GROBID: $GROBID_HOST:$GROBID_PORT"
    echo

    # Check if virtual environment exists and activate it
    if [ -d ".venv" ]; then
        print_status "Activating virtual environment..."
        source .venv/bin/activate
    elif [ -d "venv" ]; then
        print_status "Activating virtual environment..."
        source venv/bin/activate
    else
        print_warning "No virtual environment found, using system Python"
    fi

    # Check if required services are accessible
    print_status "Checking service connectivity..."
    all_services_ready=true
    
    if ! check_service_port "${POSTGRES_PORT}" "PostgreSQL"; then
        print_warning "PostgreSQL not accessible on port ${POSTGRES_PORT}"
        all_services_ready=false
    fi
    
    if ! check_service_port "${NEO4J_PORT}" "Neo4j"; then
        print_warning "Neo4j not accessible on port ${NEO4J_PORT}"
        all_services_ready=false
    fi
    
    if ! check_service_port "${GROBID_PORT}" "GROBID"; then
        print_warning "GROBID not accessible on port ${GROBID_PORT}"
        all_services_ready=false
    fi

    if [ "$all_services_ready" = false ]; then
        print_warning "Some services are not accessible. The application may not function correctly."
        print_status "Consider running: ./server.sh --services-only"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Startup cancelled"
            return 1
        fi
    fi

    # Start the application
    print_status "Starting uvicorn server..."
    print_success "Server will be available at: $API_BASE_URL"
    print_status "Press Ctrl+C to stop the server"
    print_status "Logs will be written to: workspace/system_logs/api_server.log"
    echo

    exec uvicorn polymer_extractor.main:app \
        --host "$API_HOST" \
        --port "$API_PORT" \
        --reload \
        --reload-dir polymer_extractor \
        --reload-dir tests \
        --reload-dir scripts \
        --log-level info \
        2>&1 | tee workspace/system_logs/api_server.log
}

# Parse command line arguments
case "${1:-}" in
    --services-only)
        start_services
        ;;
    --app-only)
        start_application
        ;;
    --stop-services)
        stop_services
        ;;
    --restart-services)
        print_status "Restarting Docker services..."
        stop_services
        sleep 2
        start_services
        ;;
    --status)
        show_status
        ;;
    --help|-h)
        show_help
        ;;
    "")
        # Default: start services then application
        print_status "Starting full stack (services + application)..."
        if start_services; then
            sleep 2
            start_application
        else
            print_error "Failed to start services, not starting application"
            exit 1
        fi
        ;;
    *)
        print_error "Unknown option: $1"
        echo
        show_help
        exit 1
        ;;
esac
