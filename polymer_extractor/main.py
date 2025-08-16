import atexit
import signal
import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

# Import setup service for database connectivity checks
from polymer_extractor.services.setup_service import SetupService

# Phase 0D: Removed finetune import as training is now handled exclusively by notebook
from api import groundtruth, preprocessing, setup, grobid, ensemble_inference, evaluation

# Global setup service instance
setup_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan with service connectivity checks.
    
    Note: Services (PostgreSQL, Neo4j, GROBID) should be started externally via:
    - Docker: ./server.sh --services-only
    - Manual: Start services individually
    
    This app only connects to existing services, does not manage them.
    """
    global setup_service
    
    # Startup
    print("🚀 Starting Polymer NLP Extractor API...")
    print("🔍 Checking service connectivity...")
    
    setup_service = SetupService()
    
    # Check service connectivity (not start services)
    health_result = setup_service.health_check_all()
    
    # Check if critical services are accessible
    critical_failures = []
    if "postgres" in health_result["databases"]:
        postgres_result = health_result["databases"]["postgres"]
        if postgres_result.get("status") != "healthy":
            critical_failures.append(f"PostgreSQL: {postgres_result.get('error', 'Not accessible')}")
    
    if "neo4j" in health_result["databases"]:
        neo4j_result = health_result["databases"]["neo4j"] 
        if neo4j_result.get("status") != "healthy":
            critical_failures.append(f"Neo4j: {neo4j_result.get('error', 'Not accessible')}")
    
    if critical_failures:
        print("❌ Critical services are not accessible:")
        for failure in critical_failures:
            print(f"   - {failure}")
        print("")
        print("🐳 To start services with Docker:")
        print("   ./server.sh --services-only")
        print("")
        print("📖 For manual setup, see README.md database setup instructions")
        print("🔍 Check service status: ./server.sh --status")
        print("")
        print("🛑 Application cannot start without required databases")
        sys.exit(1)
    
    print("✅ All required services are accessible")
    
    # Initialize database schemas if needed
    print("🔧 Initializing database schemas...")
    init_result = setup_service.initialize_system()
    if not init_result["success"]:
        print(f"⚠️  Warning: Schema initialization had issues: {init_result.get('message', 'Unknown error')}")
        # Don't exit - may be recoverable
    
    yield
    
    # Shutdown
    print("🛑 Application shutting down...")
    print("� Note: External services (Docker containers) continue running")
    print("   Use './server.sh --stop-services' to stop Docker services")


app = FastAPI(
    title="Polymer NLP Extractor API",
    description="API for managing polymer NLP extraction workflows (Phase 0D - Inference Only)",
    version="1.0.0",
    lifespan=lifespan
)

# Include Setup API router
app.include_router(setup.router, prefix="/api", tags=["Setup"])

# Include GROBID API router
app.include_router(grobid.router, prefix="/api", tags=["GROBID"])

# Include Ground Truth API router
app.include_router(groundtruth.router, prefix="/api", tags=["Ground Truth"])

# Include Preprocessing API router
app.include_router(preprocessing.router, prefix="/api", tags=["Preprocessing"])

# Phase 0D: Fine-Tuning API removed - training is now handled exclusively by the notebook
# Inference services only consume pre-trained models

# Include Ensemble Inference API router
app.include_router(ensemble_inference.router, prefix="/api", tags=["Inference"])

# Include Evaluation API router
app.include_router(evaluation.router, prefix="/api", tags=["Evaluation"])

@app.get("/")
def root():
    """
    Root endpoint for health check.
    """
    return {"status": "ok", "message": "Polymer NLP API is running (Phase 0D - Inference Only)."}


@app.get("/api/servers/status")
def get_server_status():
    """
    Get status of all external services (Docker containers or manual installations).
    """
    global setup_service
    if not setup_service:
        raise HTTPException(status_code=503, detail="Setup service not initialized")
    
    return setup_service.health_check_all()


@app.post("/api/servers/start/{service_name}")
def start_service(service_name: str):
    """
    Service management endpoint - returns information about Docker service management.
    
    Note: This API does not start services directly. Services should be managed via:
    - Docker: ./server.sh --services-only
    - Manual: See README.md for setup instructions
    """
    return {
        "message": f"This API does not manage {service_name} directly",
        "docker_command": f"./server.sh --services-only",
        "manual_setup": "See README.md for manual installation instructions",
        "status_check": f"./server.sh --status",
        "note": "External services should be started independently of this API"
    }


@app.post("/api/servers/stop/{service_name}")
def stop_service(service_name: str):
    """
    Service management endpoint - returns information about Docker service management.
    
    Note: This API does not stop services directly. Services should be managed via:
    - Docker: ./server.sh --stop-services
    - Manual: Stop services through your system's service manager
    """
    return {
        "message": f"This API does not manage {service_name} directly",
        "docker_command": "./server.sh --stop-services",
        "manual_setup": "Use your system's service manager (systemctl, brew services, etc.)",
        "status_check": "./server.sh --status",
        "note": "External services should be managed independently of this API"
    }

@app.get("/api/finetune", deprecated=True)
def deprecated_finetune():
    """
    Deprecated endpoint - training is now handled exclusively by the notebook.
    """
    return {
        "status": "deprecated",
        "message": "Fine-tuning API has been removed in Phase 0D. Use the training notebook instead.",
        "redirect": "Use notebooks/model_training_finetuning.ipynb for all training operations",
        "phase": "0D",
        "training_location": "notebooks/model_training_finetuning.ipynb"
    }

@app.post("/api/finetune", deprecated=True)  
def deprecated_finetune_post():
    """
    Deprecated endpoint - training is now handled exclusively by the notebook.
    """
    return {
        "status": "deprecated", 
        "message": "Fine-tuning API has been removed in Phase 0D. Use the training notebook instead.",
        "redirect": "Use notebooks/model_training_finetuning.ipynb for all training operations",
        "phase": "0D",
        "training_location": "notebooks/model_training_finetuning.ipynb"
    }
