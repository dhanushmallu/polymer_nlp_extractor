#!/bin/bash
# Polymer NLP Extractor - Service Orchestrator
# Usage: ./server.sh [command] [options]
# Commands: start|services|app|stop|restart|clean|reset|purge|logs|status|help

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure required directories exist
mkdir -p workspace/public/system_logs
PIDFILE="workspace/public/system_logs/uvicorn.pid"

# Helper functions for output
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERR]${NC} $1"; }

# Check if a command exists
has() { command -v "$1" >/dev/null 2>&1; }

# Load environment variables with defaults
load_env() {
    if [[ -f .env ]]; then
        set -a
        # shellcheck disable=SC1091
        . ./.env
        set +a
    fi
    
    # Set defaults for all required ports
    export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
    export NEO4J_PORT="${NEO4J_PORT:-7687}"
    export NEO4J_HTTP_PORT="${NEO4J_HTTP_PORT:-7474}"
    export GROBID_PORT="${GROBID_PORT:-8070}"
    export PGADMIN_PORT="${PGADMIN_PORT:-5050}"
    export API_HOST="${API_HOST:-127.0.0.1}"
    export API_PORT="${API_PORT:-8000}"
}

# Get Docker Compose command (prefer 'docker compose' over 'docker-compose')
get_compose_cmd() {
    if docker compose version >/dev/null 2>&1; then
        echo "docker compose"
    elif has docker-compose; then
        echo "docker-compose"
    else
        err "Neither 'docker compose' nor 'docker-compose' found"
        return 1
    fi
}

# Execute Docker Compose with fallback to sudo if needed
compose() {
    local cmd
    cmd=$(get_compose_cmd) || return 1
    
    if $cmd "$@"; then
        return 0
    elif [[ "$EUID" -ne 0 ]]; then
        warn "Retrying with sudo..."
        sudo $cmd "$@"
    else
        return 1
    fi
}

# Check if a port is open
port_open() {
    local port=$1
    if has nc; then
        nc -z 127.0.0.1 "$port" >/dev/null 2>&1
    else
        (echo > /dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1
    fi
}

# Check what process is using a specific port
check_port_usage() {
    local port=$1
    if has ss; then
        ss -tlnp | grep ":$port " | head -1
    elif has netstat; then
        netstat -tlnp 2>/dev/null | grep ":$port " | head -1
    else
        return 1
    fi
}

# Safely resolve port conflicts for critical services
resolve_port_conflicts() {
    load_env
    
    local conflicts_found=false
    local critical_ports=(
        "$POSTGRES_PORT:PostgreSQL"
        "$NEO4J_PORT:Neo4j Bolt"
        "$NEO4J_HTTP_PORT:Neo4j HTTP"
        "$GROBID_PORT:GROBID"
    )
    
    info "Checking for port conflicts..."
    
    for port_service in "${critical_ports[@]}"; do
        local port="${port_service%%:*}"
        local service="${port_service##*:}"
        
        if port_open "$port"; then
            local usage
            usage=$(check_port_usage "$port" 2>/dev/null || echo "unknown process")
            
            # Check if it's our own Docker container
            if echo "$usage" | grep -q "docker-proxy\|containerd"; then
                info "$service port $port is used by Docker container (OK)"
                continue
            fi
            
            warn "$service port $port is in use by: $usage"
            conflicts_found=true
            
            # Handle specific known conflicts
            case "$port" in
                5432)
                    if echo "$usage" | grep -q "postgres"; then
                        info "Attempting to stop system PostgreSQL service..."
                        if systemctl is-active --quiet postgresql 2>/dev/null; then
                            warn "System PostgreSQL service is running"
                            echo -n "Stop system PostgreSQL to free port 5432? [Y/n]: "
                            read -r confirm
                            if [[ "$confirm" =~ ^[Nn]$ ]]; then
                                err "Cannot start Docker PostgreSQL while system PostgreSQL is running"
                                err "Either:"
                                err "  1. Stop system PostgreSQL: sudo systemctl stop postgresql"
                                err "  2. Change POSTGRES_PORT in .env to use a different port"
                                return 1
                            else
                                if sudo systemctl stop postgresql 2>/dev/null; then
                                    success "System PostgreSQL stopped"
                                    # Also stop specific instances
                                    sudo systemctl stop 'postgresql@*' 2>/dev/null || true
                                    sleep 2
                                else
                                    err "Failed to stop system PostgreSQL"
                                    return 1
                                fi
                            fi
                        fi
                    fi
                    ;;
                7474|7687)
                    if echo "$usage" | grep -q "neo4j\|java"; then
                        warn "System Neo4j service may be running"
                        info "You may need to stop it: sudo systemctl stop neo4j"
                    fi
                    ;;
            esac
        fi
    done
    
    if [[ "$conflicts_found" == "true" ]]; then
        info "Rechecking ports after conflict resolution..."
        sleep 3
        
        for port_service in "${critical_ports[@]}"; do
            local port="${port_service%%:*}"
            local service="${port_service##*:}"
            
            if port_open "$port"; then
                local usage
                usage=$(check_port_usage "$port" 2>/dev/null || echo "unknown process")
                if ! echo "$usage" | grep -q "docker-proxy\|containerd"; then
                    err "$service port $port is still in use: $usage"
                    err "Please resolve manually before starting services"
                    return 1
                fi
            fi
        done
    fi
    
    success "Port conflict check completed"
    return 0
}

# Wait for a port to become available with exponential backoff
wait_port() {
    local port=$1 name=$2 max_wait=${3:-60}
    local count=0
    local sleep_time=1
    
    info "Waiting for $name on port $port..."
    while [[ $count -lt $max_wait ]]; do
        if port_open "$port"; then
            success "$name is ready on port $port"
            return 0
        fi
        
        sleep $sleep_time
        count=$((count + sleep_time))
        
        # Exponential backoff: 1s, 2s, 3s, 3s, 3s...
        if [[ $sleep_time -lt 3 ]]; then
            sleep_time=$((sleep_time + 1))
        fi
    done
    
    warn "$name not ready after ${max_wait}s (port $port)"
    return 1
}

# Wait for Docker container to be healthy
wait_container_healthy() {
    local container_name=$1 service_name=$2 max_wait=${3:-90}
    local count=0
    
    info "Waiting for $service_name container to be healthy..."
    while [[ $count -lt $max_wait ]]; do
        local health_status
        health_status=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "no-health")
        
        case "$health_status" in
            "healthy")
                success "$service_name container is healthy"
                return 0
                ;;
            "starting")
                # Continue waiting
                ;;
            "unhealthy")
                warn "$service_name container is unhealthy, but continuing..."
                return 1
                ;;
            "no-health")
                # No health check defined, just check if running
                local status
                status=$(docker inspect --format='{{.State.Status}}' "$container_name" 2>/dev/null || echo "not-found")
                if [[ "$status" == "running" ]]; then
                    success "$service_name container is running (no health check)"
                    return 0
                fi
                ;;
        esac
        
        sleep 3
        count=$((count + 3))
    done
    
    warn "$service_name container not healthy after ${max_wait}s"
    return 1
}

# Test HTTP endpoint availability with retries
test_http() {
    local url=$1 name=$2 max_retries=${3:-3}
    local retry=0
    
    if ! has curl; then
        warn "curl not available; skipping HTTP test for $name"
        return 0
    fi
    
    while [[ $retry -lt $max_retries ]]; do
        local code
        code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 --connect-timeout 5 "$url" 2>/dev/null || echo "000")
        
        if [[ "$code" =~ ^(2|3)[0-9][0-9]$ ]] || [[ "$code" == "401" ]]; then
            success "$name HTTP endpoint is healthy (status $code)"
            return 0
        elif [[ "$code" == "000" ]]; then
            warn "$name HTTP endpoint unreachable (attempt $((retry + 1))/$max_retries)"
        else
            warn "$name HTTP endpoint returned status $code (attempt $((retry + 1))/$max_retries)"
        fi
        
        retry=$((retry + 1))
        if [[ $retry -lt $max_retries ]]; then
            sleep 5
        fi
    done
    
    warn "$name HTTP endpoint not ready after $max_retries attempts"
    return 1
}

# Start all infrastructure services
services_up() {
    local with_pgadmin=${1:-true}
    load_env
    
    if [[ ! -f docker-compose.services.yml ]]; then
        err "docker-compose.services.yml not found"
        return 1
    fi
    
    # Check and resolve port conflicts before starting services
    if ! resolve_port_conflicts; then
        err "Port conflicts detected. Please resolve them manually or use different ports."
        err "Edit .env file to change port numbers if needed."
        return 1
    fi
    
    info "Starting infrastructure services..."
    
    # Start core services (postgres, neo4j, grobid)
    if [[ "$with_pgadmin" == "true" ]]; then
        info "Starting services with pgAdmin..."
        compose -f docker-compose.services.yml --profile admin up -d
    else
        info "Starting core services only..."
        compose -f docker-compose.services.yml up -d postgres neo4j grobid
    fi
    
    # Wait for containers to be healthy and ports ready
    info "Waiting for services to initialize..."
    
    # PostgreSQL - wait for both container health and port
    wait_container_healthy "polymer_postgres" "PostgreSQL" 60 || true
    wait_port "$POSTGRES_PORT" "PostgreSQL" 30 || true
    
    # Neo4j - more time needed for initialization
    wait_container_healthy "polymer_neo4j" "Neo4j" 90 || true
    wait_port "$NEO4J_PORT" "Neo4j Bolt" 45 || true
    wait_port "$NEO4J_HTTP_PORT" "Neo4j HTTP" 45 || true
    
    # GROBID - can take time to warm up
    wait_container_healthy "polymer_grobid" "GROBID" 120 || true
    wait_port "$GROBID_PORT" "GROBID" 60 || true
    
    # pgAdmin if requested
    if [[ "$with_pgadmin" == "true" ]]; then
        wait_container_healthy "polymer_pgadmin" "pgAdmin" 60 || true
        wait_port "$PGADMIN_PORT" "pgAdmin" 30 || true
    fi
    
    # Give services extra time to fully initialize
    info "Allowing services extra time to fully initialize..."
    sleep 10
    
    # Test HTTP endpoints with retries
    info "Testing HTTP endpoints..."
    test_http "http://localhost:$NEO4J_HTTP_PORT/browser/" "Neo4j Browser" 3 || \
    test_http "http://localhost:$NEO4J_HTTP_PORT/" "Neo4j HTTP" 3 || true
    
    test_http "http://localhost:$GROBID_PORT/api/isalive" "GROBID API" 3 || true
    
    if [[ "$with_pgadmin" == "true" ]]; then
        test_http "http://localhost:$PGADMIN_PORT/login" "pgAdmin Login" 3 || \
        test_http "http://localhost:$PGADMIN_PORT/" "pgAdmin" 3 || true
    fi
    
    success "Infrastructure services startup complete"
    
    # Show final status
    info "Final service status:"
    compose -f docker-compose.services.yml ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
}

# Start only pgAdmin (assumes postgres is already running)
pgadmin_only() {
    load_env
    info "Starting pgAdmin only..."
    
    # Check if postgres is running first
    if ! port_open "$POSTGRES_PORT"; then
        err "PostgreSQL must be running before starting pgAdmin"
        err "Start PostgreSQL first with: ./server.sh services --no-pgadmin"
        return 1
    fi
    
    compose -f docker-compose.services.yml --profile admin up -d pgadmin
    
    wait_container_healthy "polymer_pgadmin" "pgAdmin" 60 || true
    wait_port "$PGADMIN_PORT" "pgAdmin" 30 || true
    
    # Give pgAdmin time to initialize
    sleep 5
    
    test_http "http://localhost:$PGADMIN_PORT/login" "pgAdmin Login" 3 || \
    test_http "http://localhost:$PGADMIN_PORT/" "pgAdmin" 3 || true
    
    success "pgAdmin started successfully"
    info "pgAdmin available at: http://localhost:$PGADMIN_PORT"
    info "Default credentials: admin@example.com / admin123"
}

# Stop all infrastructure services
services_down() {
    if [[ -f docker-compose.services.yml ]]; then
        info "Stopping infrastructure services..."
        compose -f docker-compose.services.yml down --remove-orphans || true
        success "Infrastructure services stopped"
    else
        warn "docker-compose.services.yml not found"
    fi
}

# Start the FastAPI application
app_start() {
    local dev_mode=${1:-false}
    load_env
    
    # Critical: Activate virtual environment per project guidelines
    if [[ -f .venv/bin/activate ]]; then
        # shellcheck disable=SC1091
        source .venv/bin/activate
        info "Virtual environment activated"
    else
        err "Virtual environment not found at .venv/bin/activate"
        err "Please create the virtual environment first"
        return 1
    fi
    
    # Check if API is already running
    if port_open "$API_PORT"; then
        warn "API port $API_PORT is already in use"
        return 1
    fi
    
    # Verify that required services are running
    local missing_services=()
    if ! port_open "$POSTGRES_PORT"; then
        missing_services+=("PostgreSQL:$POSTGRES_PORT")
    fi
    if ! port_open "$NEO4J_PORT"; then
        missing_services+=("Neo4j:$NEO4J_PORT")
    fi
    
    if [[ ${#missing_services[@]} -gt 0 ]]; then
        err "Required services are not running:"
        for service in "${missing_services[@]}"; do
            err "  - $service"
        done
        err "Start services first with: ./server.sh services"
        return 1
    fi
    
    info "Starting Polymer NLP Extractor API on $API_HOST:$API_PORT..."
    
    # Ensure logs directory exists
    mkdir -p workspace/public/system_logs
    
    if [[ "$dev_mode" == "true" ]]; then
        # Development mode - foreground with reload
        info "Starting in development mode with auto-reload..."
        info "Watching: Python files, excluding cypher, logs, cache, and data folders"
        python3 -m uvicorn polymer_extractor.main:app \
            --host "$API_HOST" \
            --port "$API_PORT" \
            --log-level info \
            --reload \
            --reload-include "*.py" \
            --reload-include "*.yaml" \
            --reload-include "*.yml" \
            --reload-include "*.json" \
            --reload-exclude "**/kg/cypher/**" \
            --reload-exclude "**/workspace/**" \
            --reload-exclude "**/__pycache__/**" \
            --reload-exclude "**/.*" \
            --reload-exclude "**/logs/**" \
            --reload-exclude "**/node_modules/**"
    else
        # Production mode - background without reload
        python3 -m uvicorn polymer_extractor.main:app \
            --host "$API_HOST" \
            --port "$API_PORT" \
            --log-level info \
            > workspace/public/system_logs/api.log 2>&1 &
        
        local api_pid=$!
        echo "$api_pid" > "$PIDFILE"
        disown || true
        
        # Wait for API to be ready with better timing
        if wait_port "$API_PORT" "API" 60; then
            # Extra verification that API is actually responding
            sleep 3
            if test_http "http://$API_HOST:$API_PORT/" "API Health" 2; then
                success "API started successfully (PID: $api_pid)"
                info "API available at: http://$API_HOST:$API_PORT"
                info "API logs: workspace/public/system_logs/api.log"
                info "API health: http://$API_HOST:$API_PORT/"
            else
                warn "API port is open but not responding to HTTP requests"
                info "Check logs: workspace/public/system_logs/api.log"
            fi
        else
            err "API failed to start properly"
            if [[ -f workspace/public/system_logs/api.log ]]; then
                err "Recent API logs:"
                tail -10 workspace/public/system_logs/api.log | sed 's/^/  /'
            fi
            return 1
        fi
    fi
}

# Stop the FastAPI application
app_stop() {
    info "Stopping API..."
    
    # Stop via PID file
    if [[ -f "$PIDFILE" ]]; then
        local pid
        pid=$(cat "$PIDFILE" 2>/dev/null || echo "")
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            info "Stopping API (PID: $pid)"
            kill -TERM "$pid" 2>/dev/null || true
            
            # Wait for graceful shutdown
            local count=0
            while [[ $count -lt 10 ]] && kill -0 "$pid" 2>/dev/null; do
                sleep 1
                ((count++))
            done
            
            # Force kill if still running
            if kill -0 "$pid" 2>/dev/null; then
                warn "Force killing API process"
                kill -KILL "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$PIDFILE"
    fi
    
    # Kill any remaining uvicorn processes for this app
    pkill -f "uvicorn.*polymer_extractor.main:app" 2>/dev/null || true
    
    success "API stopped"
}

# Clear database locks (Docker connections)
clear_database_locks() {
    local force=${1:-false}
    load_env  # Ensure environment is loaded
    
    info "Clearing database locks..."
    
    # Check if PostgreSQL container is running
    if docker ps --filter name=polymer_postgres --format '{{.Names}}' | grep -q polymer_postgres; then
        info "Terminating active PostgreSQL connections..."
        
        # Terminate connections to our database (preserve system databases)
        local db_name="${POSTGRES_DB:-polymer_extractor}"
        docker exec polymer_postgres psql -U "${POSTGRES_USER:-postgres}" -c "
            SELECT pg_terminate_backend(pid) 
            FROM pg_stat_activity 
            WHERE datname = '$db_name' 
            AND pid <> pg_backend_pid();" 2>/dev/null || true
        
        # Brief pause then restart container to clear any remaining locks
        info "Restarting PostgreSQL container to clear locks..."
        docker restart polymer_postgres >/dev/null 2>&1 || true
        
        # Wait for PostgreSQL to be ready again
        wait_port "$POSTGRES_PORT" "PostgreSQL" 30 || true
        
        success "Database locks cleared"
    else
        warn "PostgreSQL container not running - no locks to clear"
    fi
}

# Clean shutdown (stop everything but keep data)
clean_all() {
    info "Performing clean shutdown (keeping data)..."
    
    # Clear any database locks before stopping
    clear_database_locks
    
    app_stop
    services_down
    
    # Remove any leftover containers
    if has docker; then
        docker ps -aq --filter name=polymer_ 2>/dev/null | xargs -r docker rm -f 2>/dev/null || true
    fi
    
    success "Clean shutdown complete"
}

# Reset (stop everything and remove volumes)
reset_all() {
    local force=${1:-false}
    
    if [[ "$force" != "true" ]]; then
        echo -n "This will remove all data volumes. Continue? [y/N]: "
        read -r confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            warn "Reset cancelled"
            return 0
        fi
    fi
    
    info "Performing reset (removing data volumes)..."
    
    # Clear database locks before reset
    clear_database_locks
    
    app_stop
    
    if [[ -f docker-compose.services.yml ]]; then
        compose -f docker-compose.services.yml down -v --remove-orphans || true
    fi
    
    success "Reset complete - all data removed"
}

# Purge (remove everything including images)
purge_all() {
    local force=${1:-false}
    
    if [[ "$force" != "true" ]]; then
        echo -n "This will remove containers, images, volumes, and networks. Continue? [y/N]: "
        read -r confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            warn "Purge cancelled"
            return 0
        fi
    fi
    
    info "Performing purge (removing everything)..."
    
    # Clear database locks before purge
    clear_database_locks
    
    app_stop
    
    if [[ -f docker-compose.services.yml ]]; then
        compose -f docker-compose.services.yml down -v --rmi all --remove-orphans || true
    fi
    
    # Clean up any remaining polymer-related Docker resources
    if has docker; then
        docker ps -a --filter name=polymer_ --format '{{.Names}}' 2>/dev/null | xargs -r docker rm -f 2>/dev/null || true
        docker images --filter reference='*polymer*' --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | xargs -r docker rmi -f 2>/dev/null || true
        docker images --filter reference='*grobid*' --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | xargs -r docker rmi -f 2>/dev/null || true
        docker images --filter reference='*postgres*' --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | xargs -r docker rmi -f 2>/dev/null || true
        docker images --filter reference='*neo4j*' --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | xargs -r docker rmi -f 2>/dev/null || true
        docker images --filter reference='*pgadmin*' --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | xargs -r docker rmi -f 2>/dev/null || true
        docker volume ls --filter name=polymer --format '{{.Name}}' 2>/dev/null | xargs -r docker volume rm 2>/dev/null || true
        docker network ls --filter name=polymer --format '{{.Name}}' 2>/dev/null | xargs -r docker network rm 2>/dev/null || true
    fi
    
    success "Purge complete - everything removed"
}

# Show service logs
show_logs() {
    local follow=${1:-false}
    
    if [[ ! -f docker-compose.services.yml ]]; then
        err "docker-compose.services.yml not found"
        return 1
    fi
    
    if [[ "$follow" == "true" ]]; then
        info "Following service logs (Ctrl+C to stop)..."
        compose -f docker-compose.services.yml --profile admin logs -f
    else
        info "Showing recent service logs..."
        compose -f docker-compose.services.yml --profile admin logs --tail=50
    fi
}

# Show status of all services
show_status() {
    load_env
    
    echo
    info "=== Infrastructure Services Status ==="
    if [[ -f docker-compose.services.yml ]]; then
        compose -f docker-compose.services.yml ps --no-trunc || true
    else
        warn "docker-compose.services.yml not found"
    fi
    
    echo
    info "=== Port Status ==="
    local services=(
        "API:$API_PORT"
        "PostgreSQL:$POSTGRES_PORT"
        "Neo4j HTTP:$NEO4J_HTTP_PORT"
        "Neo4j Bolt:$NEO4J_PORT"
        "GROBID:$GROBID_PORT"
        "pgAdmin:$PGADMIN_PORT"
    )
    
    for service_port in "${services[@]}"; do
        local name="${service_port%%:*}"
        local port="${service_port##*:}"
        if port_open "$port"; then
            echo -e "  ${GREEN}✓${NC} $name (port $port) - Running"
        else
            echo -e "  ${YELLOW}✗${NC} $name (port $port) - Stopped"
        fi
    done
    
    echo
    info "=== Service URLs ==="
    echo "  API:           http://$API_HOST:$API_PORT"
    echo "  Neo4j Browser: http://localhost:$NEO4J_HTTP_PORT"
    echo "  GROBID API:    http://localhost:$GROBID_PORT"
    echo "  pgAdmin:       http://localhost:$PGADMIN_PORT"
    
    echo
    info "=== Recent API Logs ==="
    if [[ -f workspace/public/system_logs/api.log ]]; then
        tail -n 5 workspace/public/system_logs/api.log 2>/dev/null || echo "  No recent logs"
    else
        echo "  No API log file found"
    fi
}

# Initialize database schema (clean slate)
db_init() {
    local force=${1:-false}
    load_env
    
    # Critical: Activate virtual environment per project guidelines
    if [[ -f .venv/bin/activate ]]; then
        # shellcheck disable=SC1091
        source .venv/bin/activate
        info "Virtual environment activated"
    else
        err "Virtual environment not found at .venv/bin/activate"
        return 1
    fi
    
    # Check if PostgreSQL is running
    if ! port_open "$POSTGRES_PORT"; then
        err "PostgreSQL is not running. Start services first with: ./server.sh services"
        return 1
    fi
    
    # Check if schema file exists
    if [[ ! -f db/sql/001_core.sql ]]; then
        err "Schema file not found: db/sql/001_core.sql"
        return 1
    fi
    
    if [[ "$force" != "true" ]]; then
        echo -n "This will DROP and RECREATE all database tables and data. Continue? [y/N]: "
        read -r confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            warn "Database initialization cancelled"
            return 0
        fi
    fi
    
    info "Initializing database schema..."
    
    # Use environment variables for connection
    local db_host="${POSTGRES_HOST:-localhost}"
    local db_port="${POSTGRES_PORT:-5432}"
    local db_name="${POSTGRES_DB:-polymer_extractor}"
    local db_user="${POSTGRES_USER:-pnlp_db_user}"
    
    # Set PGPASSWORD from environment
    export PGPASSWORD="${POSTGRES_PASSWORD}"
    
    # Execute schema with proper error handling
    if psql -h "$db_host" -p "$db_port" -U "$db_user" -d "$db_name" -f db/sql/001_core.sql; then
        success "Database schema initialized successfully"
        info "All tables recreated with clean structure"
    else
        err "Failed to initialize database schema"
        err "Check PostgreSQL logs and connection settings"
        return 1
    fi
    
    # Clear password from environment
    unset PGPASSWORD
}

# Clear all data from tables (keep structure)
db_clear() {
    local force=${1:-false}
    load_env
    
    # Critical: Activate virtual environment per project guidelines
    if [[ -f .venv/bin/activate ]]; then
        # shellcheck disable=SC1091
        source .venv/bin/activate
        info "Virtual environment activated"
    else
        err "Virtual environment not found at .venv/bin/activate"
        return 1
    fi
    
    # Check if PostgreSQL is running
    if ! port_open "$POSTGRES_PORT"; then
        err "PostgreSQL is not running. Start services first with: ./server.sh services"
        return 1
    fi
    
    if [[ "$force" != "true" ]]; then
        echo -n "This will DELETE ALL DATA from all tables (keeping structure). Continue? [y/N]: "
        read -r confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            warn "Database clear cancelled"
            return 0
        fi
    fi
    
    info "Clearing all data from database tables..."
    
    # Clear any database locks before data operations
    clear_database_locks
    
    # Use environment variables for connection
    local db_host="${POSTGRES_HOST:-localhost}"
    local db_port="${POSTGRES_PORT:-5432}"
    local db_name="${POSTGRES_DB:-polymer_extractor}"
    local db_user="${POSTGRES_USER:-pnlp_db_user}"
    
    # Set PGPASSWORD from environment
    export PGPASSWORD="${POSTGRES_PASSWORD}"
    
    # Clear data from all tables in dependency order
    local clear_sql="
    -- Disable foreign key checks temporarily
    SET session_replication_role = replica;
    
    -- Clear all tables in dependency order
    TRUNCATE TABLE model_configurations CASCADE;
    TRUNCATE TABLE extraction_metadata CASCADE;
    TRUNCATE TABLE datasets_metadata CASCADE;
    TRUNCATE TABLE research_papers CASCADE;
    TRUNCATE TABLE sessions CASCADE;
    
    -- Re-enable foreign key checks
    SET session_replication_role = DEFAULT;
    
    -- Reset sequences
    ALTER SEQUENCE IF EXISTS research_papers_id_seq RESTART WITH 1;
    ALTER SEQUENCE IF EXISTS sessions_id_seq RESTART WITH 1;
    ALTER SEQUENCE IF EXISTS datasets_metadata_id_seq RESTART WITH 1;
    ALTER SEQUENCE IF EXISTS extraction_metadata_id_seq RESTART WITH 1;
    ALTER SEQUENCE IF EXISTS model_configurations_id_seq RESTART WITH 1;
    "
    
    if echo "$clear_sql" | psql -h "$db_host" -p "$db_port" -U "$db_user" -d "$db_name"; then
        success "All table data cleared successfully"
        info "Table structures preserved, sequences reset"
    else
        err "Failed to clear database data"
        err "Check PostgreSQL logs and connection settings"
        return 1
    fi
    
    # Clear password from environment
    unset PGPASSWORD
}

# Initialize Neo4j knowledge graph schema
kg_init() {
    local force=${1:-false}
    load_env
    
    # Critical: Activate virtual environment per project guidelines
    if [[ -f .venv/bin/activate ]]; then
        # shellcheck disable=SC1091
        source .venv/bin/activate
        info "Virtual environment activated"
    else
        err "Virtual environment not found at .venv/bin/activate"
        return 1
    fi
    
    # Check if Neo4j is running
    if ! port_open "$NEO4J_PORT"; then
        err "Neo4j is not running. Start services first with: ./server.sh services"
        return 1
    fi
    
    # Check if constraints file exists
    if [[ ! -f kg/cypher/001_constraints.cypher ]]; then
        err "Neo4j constraints file not found: kg/cypher/001_constraints.cypher"
        return 1
    fi
    
    if [[ "$force" != "true" ]]; then
        echo -n "This will CLEAR all Neo4j data and RECREATE constraints/indexes. Continue? [y/N]: "
        read -r confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            warn "Knowledge graph initialization cancelled"
            return 0
        fi
    fi
    
    info "Initializing Neo4j knowledge graph schema..."
    
    # Use python to initialize Neo4j via the existing client
    local init_kg_script="
import os
import sys
sys.path.append('.')
from polymer_extractor.storage.neo4j_client import Neo4jClient

try:
    client = Neo4jClient()
    
    with client.driver.session() as session:
        # Clear all existing data first
        print('Clearing existing data...')
        result = session.run('MATCH ()-[r]-() DELETE r RETURN count(r) as deleted_rels')
        deleted_rels = result.single()['deleted_rels']
        
        result = session.run('MATCH (n) DELETE n RETURN count(n) as deleted_nodes')
        deleted_nodes = result.single()['deleted_nodes']
        
        print(f'Cleared {deleted_rels} relationships and {deleted_nodes} nodes')
        
        # Read and execute constraints file
        with open('kg/cypher/001_constraints.cypher', 'r') as f:
            cypher_content = f.read()
        
        # Split by semicolons and execute each statement
        statements = [stmt.strip() for stmt in cypher_content.split(';') if stmt.strip()]
        
        print(f'Executing {len(statements)} schema statements...')
        for i, statement in enumerate(statements, 1):
            try:
                session.run(statement)
                print(f'Statement {i}/{len(statements)}: OK')
            except Exception as e:
                print(f'Statement {i}/{len(statements)}: WARNING - {e}')
                # Continue with other statements
        
        print('Knowledge graph schema initialized successfully')
    
    client.close()
except Exception as e:
    print(f'Error initializing knowledge graph: {e}')
    sys.exit(1)
"
    
    if python3 -c "$init_kg_script"; then
        success "Knowledge graph schema initialized successfully"
        info "Constraints and indexes created from kg/cypher/001_constraints.cypher"
    else
        err "Failed to initialize knowledge graph schema"
        err "Check Neo4j connection settings and cypher file syntax"
        return 1
    fi
}

# Show Neo4j status and schema information
kg_status() {
    load_env
    
    # Critical: Activate virtual environment per project guidelines
    if [[ -f .venv/bin/activate ]]; then
        # shellcheck disable=SC1091
        source .venv/bin/activate
        info "Virtual environment activated"
    else
        err "Virtual environment not found at .venv/bin/activate"
        return 1
    fi
    
    # Check if Neo4j is running
    if ! port_open "$NEO4J_PORT"; then
        err "Neo4j is not running. Start services first with: ./server.sh services"
        return 1
    fi
    
    info "Retrieving Neo4j knowledge graph status..."
    
    # Use python to get Neo4j status via the existing client
    local status_kg_script="
import os
import sys
sys.path.append('.')
from polymer_extractor.storage.neo4j_client import Neo4jClient

try:
    client = Neo4jClient()
    
    with client.driver.session() as session:
        print('=== Neo4j Knowledge Graph Status ===')
        print()
        
        # Node counts by label
        print('Node Counts by Label:')
        result = session.run('CALL db.labels() YIELD label RETURN label ORDER BY label')
        labels = [record['label'] for record in result]
        
        if labels:
            for label in labels:
                count_result = session.run(f'MATCH (n:{label}) RETURN count(n) as count')
                count = count_result.single()['count']
                print(f'  {label}: {count:,} nodes')
        else:
            print('  No node labels found')
        
        print()
        
        # Relationship counts by type
        print('Relationship Counts by Type:')
        result = session.run('CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType')
        rel_types = [record['relationshipType'] for record in result]
        
        if rel_types:
            for rel_type in rel_types:
                count_result = session.run(f'MATCH ()-[r:{rel_type}]-() RETURN count(r) as count')
                count = count_result.single()['count']
                print(f'  {rel_type}: {count:,} relationships')
        else:
            print('  No relationship types found')
        
        print()
        
        # Total counts
        total_nodes_result = session.run('MATCH (n) RETURN count(n) as total')
        total_nodes = total_nodes_result.single()['total']
        
        total_rels_result = session.run('MATCH ()-[r]-() RETURN count(r) as total')
        total_rels = total_rels_result.single()['total']
        
        print(f'Total Nodes: {total_nodes:,}')
        print(f'Total Relationships: {total_rels:,}')
        print()
        
        # Constraints
        print('Constraints:')
        try:
            result = session.run('SHOW CONSTRAINTS')
            constraints = list(result)
            if constraints:
                for constraint in constraints:
                    print(f'  {constraint.get(\"name\", \"unnamed\")}: {constraint.get(\"description\", \"no description\")}')
            else:
                print('  No constraints found')
        except:
            print('  Could not retrieve constraints (may require newer Neo4j version)')
        
        print()
        
        # Indexes
        print('Indexes:')
        try:
            result = session.run('SHOW INDEXES')
            indexes = list(result)
            if indexes:
                for index in indexes:
                    print(f'  {index.get(\"name\", \"unnamed\")}: {index.get(\"labelsOrTypes\", \"unknown\")} - {index.get(\"properties\", \"unknown\")}')
            else:
                print('  No indexes found')
        except:
            print('  Could not retrieve indexes (may require newer Neo4j version)')
        
    client.close()
except Exception as e:
    print(f'Error retrieving knowledge graph status: {e}')
    sys.exit(1)
"
    
    if python3 -c "$status_kg_script"; then
        success "Knowledge graph status retrieved successfully"
    else
        err "Failed to retrieve knowledge graph status"
        err "Check Neo4j connection settings"
        return 1
    fi
}

# Clear Neo4j graph database
kg_clear() {
    local force=${1:-false}
    load_env
    
    # Critical: Activate virtual environment per project guidelines
    if [[ -f .venv/bin/activate ]]; then
        # shellcheck disable=SC1091
        source .venv/bin/activate
        info "Virtual environment activated"
    else
        err "Virtual environment not found at .venv/bin/activate"
        return 1
    fi
    
    # Check if Neo4j is running
    if ! port_open "$NEO4J_PORT"; then
        err "Neo4j is not running. Start services first with: ./server.sh services"
        return 1
    fi
    
    if [[ "$force" != "true" ]]; then
        echo -n "This will DELETE ALL NODES AND RELATIONSHIPS from Neo4j. Continue? [y/N]: "
        read -r confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            warn "Knowledge graph clear cancelled"
            return 0
        fi
    fi
    
    info "Clearing all data from Neo4j knowledge graph..."
    
    # Use python to clear Neo4j via the existing client
    local clear_kg_script="
import os
import sys
sys.path.append('.')
from polymer_extractor.storage.neo4j_client import Neo4jClient

try:
    client = Neo4jClient()
    
    # Clear all nodes and relationships
    with client.driver.session() as session:
        # Delete all relationships first
        result = session.run('MATCH ()-[r]-() DELETE r RETURN count(r) as deleted_rels')
        deleted_rels = result.single()['deleted_rels']
        
        # Delete all nodes
        result = session.run('MATCH (n) DELETE n RETURN count(n) as deleted_nodes')
        deleted_nodes = result.single()['deleted_nodes']
        
        print(f'Deleted {deleted_rels} relationships and {deleted_nodes} nodes')
    
    client.close()
    print('Knowledge graph cleared successfully')
except Exception as e:
    print(f'Error clearing knowledge graph: {e}')
    sys.exit(1)
"
    
    if python3 -c "$clear_kg_script"; then
        success "Knowledge graph cleared successfully"
    else
        err "Failed to clear knowledge graph"
        err "Check Neo4j connection settings and logs"
        return 1
    fi
}

# Prevent system services from conflicting (optional management command)
manage_system_services() {
    local action=${1:-status}  # status, disable, enable
    
    case "$action" in
        status)
            info "=== System Service Status ==="
            echo "PostgreSQL:"
            if systemctl is-enabled postgresql >/dev/null 2>&1; then
                echo "  Service: enabled (will start on boot)"
            else
                echo "  Service: disabled"
            fi
            
            if systemctl is-active postgresql >/dev/null 2>&1; then
                echo "  Status: active/running"
            else
                echo "  Status: inactive/stopped"
            fi
            
            # Check for specific PostgreSQL instances
            if systemctl list-units --type=service 'postgresql@*' --no-legend 2>/dev/null | grep -q active; then
                echo "  Active instances:"
                systemctl list-units --type=service 'postgresql@*' --no-legend 2>/dev/null | while read -r unit rest; do
                    echo "    $unit"
                done
            fi
            
            echo
            echo "Neo4j:"
            if systemctl list-unit-files neo4j.service >/dev/null 2>&1; then
                if systemctl is-enabled neo4j >/dev/null 2>&1; then
                    echo "  Service: enabled (will start on boot)"
                else
                    echo "  Service: disabled"
                fi
                
                if systemctl is-active neo4j >/dev/null 2>&1; then
                    echo "  Status: active/running"
                else
                    echo "  Status: inactive/stopped"
                fi
            else
                echo "  Service: not installed"
            fi
            ;;
        disable)
            warn "This will disable system PostgreSQL and Neo4j services from auto-starting"
            echo -n "Continue? [y/N]: "
            read -r confirm
            if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
                warn "Operation cancelled"
                return 0
            fi
            
            info "Disabling system services..."
            
            # Stop and disable PostgreSQL
            if systemctl is-active postgresql >/dev/null 2>&1; then
                sudo systemctl stop postgresql || true
                sudo systemctl stop 'postgresql@*' || true
            fi
            if systemctl is-enabled postgresql >/dev/null 2>&1; then
                sudo systemctl disable postgresql || true
            fi
            
            # Stop and disable Neo4j if installed
            if systemctl list-unit-files neo4j.service >/dev/null 2>&1; then
                if systemctl is-active neo4j >/dev/null 2>&1; then
                    sudo systemctl stop neo4j || true
                fi
                if systemctl is-enabled neo4j >/dev/null 2>&1; then
                    sudo systemctl disable neo4j || true
                fi
            fi
            
            success "System services disabled"
            warn "Note: This prevents PostgreSQL/Neo4j from starting automatically on boot"
            warn "Use 'manage-services enable' to re-enable if needed"
            ;;
        enable)
            info "Re-enabling system services..."
            
            if systemctl list-unit-files postgresql.service >/dev/null 2>&1; then
                sudo systemctl enable postgresql || true
            fi
            
            if systemctl list-unit-files neo4j.service >/dev/null 2>&1; then
                sudo systemctl enable neo4j || true
            fi
            
            success "System services re-enabled"
            ;;
        *)
            err "Unknown action: $action"
            err "Use: status, disable, or enable"
            return 1
            ;;
    esac
}

# Show help
show_help() {
    cat << 'EOF'
Polymer NLP Extractor - Service Management

USAGE:
    ./server.sh [COMMAND] [OPTIONS]

COMMANDS:
    start              Start infrastructure services and API (default)
    services           Start only infrastructure services (postgres, neo4j, grobid)
    app                Start only the API in background (requires services to be running)
    app-dev            Start only the API in foreground with auto-reload (development mode)
                       Watches: *.py, *.yaml, *.yml, *.json files
                       Excludes: cypher/, workspace/, logs/, cache/, hidden files
    pgadmin-only       Start only pgAdmin (requires postgres to be running)
    stop               Stop API and infrastructure services
    restart            Restart all services
    clean              Stop everything (keep data volumes)
    reset              Stop everything and remove data volumes
    purge              Remove everything (containers, images, volumes, networks)
    clear-locks        Clear database locks (helpful when operations hang)
    logs               Show service logs
    status             Show status of all services and ports
    db-init            Initialize/recreate database schema (drops and recreates tables)
    db-clear           Clear all data from tables (keeps table structure)
    kg-init            Initialize/recreate Neo4j schema (clears data and applies constraints)
    kg-clear           Clear all data from Neo4j knowledge graph
    kg-status          Show detailed Neo4j knowledge graph status and statistics
    manage-services    Manage system services that may conflict (status/disable/enable)
    help               Show this help message

OPTIONS:
    --no-pgadmin       Don't start pgAdmin (for services/start commands)
    --follow-logs      Follow logs in real-time (for logs command)
    --force            Skip confirmation prompts (for reset/purge/db-init/db-clear/kg-init/kg-clear commands)

EXAMPLES:
    ./server.sh                    # Start everything (services + API)
    ./server.sh services           # Start only infrastructure services
    ./server.sh services --no-pgadmin  # Start services without pgAdmin
    ./server.sh app                # Start only the API in background
    ./server.sh app-dev            # Start only the API in foreground with auto-reload
    ./server.sh clear-locks        # Clear database locks if operations hang
    ./server.sh logs --follow-logs # Follow service logs
    ./server.sh reset --force      # Reset without confirmation
    ./server.sh status             # Check status of all services
    ./server.sh db-init            # Recreate database schema (with confirmation)
    ./server.sh db-init --force    # Recreate database schema (no confirmation)
    ./server.sh db-clear           # Clear all table data (with confirmation)
    ./server.sh kg-init            # Initialize Neo4j schema (with confirmation)
    ./server.sh kg-clear --force   # Clear Neo4j data (no confirmation)
    ./server.sh kg-status          # Show Neo4j graph statistics
    ./server.sh manage-services status    # Check system service conflicts
    ./server.sh manage-services disable   # Disable conflicting system services

SERVICE URLS:
    API:           http://127.0.0.1:8000
    Neo4j Browser: http://localhost:7474
    GROBID API:    http://localhost:8070
    pgAdmin:       http://localhost:5050

NOTES:
    - Virtual environment (.venv) must exist before starting the API
    - Infrastructure services run in Docker containers
    - API runs directly on the host using the virtual environment
    - 'app-dev' watches only development files (*.py, *.yaml, *.yml, *.json)
    - 'app-dev' excludes cypher/, workspace/, logs/, cache/, and hidden files from reload
    - Use 'clean' for normal shutdown, 'reset' to clear data, 'purge' for complete cleanup
    - Database commands require PostgreSQL to be running (use 'services' first)
    - Knowledge graph commands require Neo4j to be running (use 'services' first)
    - Use 'clear-locks' if database operations hang due to connection locks
    - 'db-init' drops and recreates all tables (complete schema reset)
    - 'db-clear' removes all data but keeps table structure
    - 'kg-init' clears all data and applies constraints from kg/cypher/001_constraints.cypher
    - 'kg-clear' removes all nodes and relationships from Neo4j
    - 'kg-status' shows detailed statistics about the knowledge graph
    - 'manage-services' helps resolve port conflicts with system services
    - If services fail to start due to port conflicts, check system PostgreSQL/Neo4j services
EOF
}

# Parse command line arguments
CMD=${1:-start}
SUBCMD=""

# Handle manage-services specially since it has subcommands
if [[ "$CMD" == "manage-services" ]]; then
    SUBCMD="${2:-status}"
    shift 2 || true
else
    shift || true
fi

WITH_PGADMIN=true
FOLLOW_LOGS=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-pgadmin)
            WITH_PGADMIN=false
            ;;
        --follow-logs)
            FOLLOW_LOGS=true
            ;;
        --force)
            FORCE=true
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            warn "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
    shift
done

# Execute commands
case "$CMD" in
    start)
        services_up "$WITH_PGADMIN"
        app_start
        if [[ "$FOLLOW_LOGS" == "true" ]]; then
            show_logs true
        fi
        ;;
    services)
        services_up "$WITH_PGADMIN"
        ;;
    app)
        app_start
        ;;
    app-dev)
        app_start true
        ;;
    pgadmin-only)
        pgadmin_only
        ;;
    stop)
        app_stop
        services_down
        ;;
    restart)
        app_stop || true
        services_down || true
        services_up "$WITH_PGADMIN"
        app_start
        ;;
    clean)
        clean_all
        ;;
    reset)
        reset_all "$FORCE"
        ;;
    purge)
        purge_all "$FORCE"
        ;;
    clear-locks)
        clear_database_locks "$FORCE"
        ;;
    logs)
        show_logs "$FOLLOW_LOGS"
        ;;
    status)
        show_status
        ;;
    db-init)
        db_init "$FORCE"
        ;;
    db-clear)
        db_clear "$FORCE"
        ;;
    kg-init)
        kg_init "$FORCE"
        ;;
    kg-clear)
        kg_clear "$FORCE"
        ;;
    kg-status)
        kg_status
        ;;
    manage-services)
        manage_system_services "$SUBCMD"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        err "Unknown command: $CMD"
        echo "Use --help for usage information"
        exit 1
        ;;
esac