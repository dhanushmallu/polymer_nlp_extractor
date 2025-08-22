import atexit
import signal
import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Import setup service for database connectivity checks
from polymer_extractor.services.setup_service import SetupService

# Import server manager from root level (moved in Phase 3)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server_manager import ServerManager

# Phase 0D: Removed finetune import as training is now handled exclusively by notebook
from api import groundtruth, preprocessing, setup, grobid, ensemble_inference, evaluation, models_sync, session, documentation

# Global setup service instance
setup_service = None
server_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan with service connectivity checks and proper shutdown handlers.
    
    Note: Services (PostgreSQL, Neo4j, GROBID) should be started externally via:
    - Docker: ./server.sh services
    - Manual: Start services individually
    
    This app only connects to existing services, does not manage them.
    """
    global setup_service, server_manager
    
    # Startup
    print("Starting Polymer NLP Extractor API...")
    print("Checking service connectivity...")
    
    try:
        setup_service = SetupService()
        server_manager = ServerManager()
        
        # Register shutdown handlers
        def shutdown_handler(signum, frame):
            print(f"\nReceived signal {signum}, initiating graceful shutdown...")
            if server_manager:
                server_manager._cleanup_on_exit()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)
        atexit.register(lambda: server_manager._cleanup_on_exit() if server_manager else None)
        
        # Check service connectivity (not start services)
        health_result = setup_service.check_health()
        
        # Check if critical services are accessible
        critical_failures = []
        services = health_result.get("services", {})
        
        if "postgres" in services:
            postgres_result = services["postgres"]
            if postgres_result.get("status") != "healthy":
                critical_failures.append(f"PostgreSQL: {postgres_result.get('details', {}).get('error', 'Not accessible')}")
        
        if "neo4j" in services:
            neo4j_result = services["neo4j"] 
            if neo4j_result.get("status") != "healthy":
                critical_failures.append(f"Neo4j: {neo4j_result.get('details', {}).get('error', 'Not accessible')}")
        
        if critical_failures:
            print("Critical services are not accessible:")
            for failure in critical_failures:
                print(f"   - {failure}")
            print("")
            print("To start services with Docker:")
            print("   ./server.sh services")
            print("")
            print("For manual setup, see README.md database setup instructions")
            print("Check service status: ./server.sh status")
            print("")
            print("Application cannot start without required databases")
            sys.exit(1)
        
        print("All required services are accessible")
        
        # Initialize database schemas if needed (non-destructive)
        print("Initializing system components...")
        try:
            init_result = setup_service.initialize(admin_user="system", force_model_sync=False)
            if init_result.get("success", False):
                print("System initialization completed successfully")
            else:
                print(f"Warning: System initialization had issues: {init_result.get('message', 'Unknown error')}")
                # Don't exit - may be recoverable
        except Exception as e:
            print(f"Warning: System initialization failed: {str(e)}")
            # Don't exit - continue with degraded functionality
        
    except Exception as e:
        print(f"Critical error during startup: {str(e)}")
        print("Unable to initialize setup service. Check database connectivity.")
        sys.exit(1)
    
    yield
    
    # Shutdown
    print("Application shutting down...")
    if server_manager:
        server_manager._cleanup_on_exit()
    print("Note: External services (Docker containers) continue running")
    print("   Use './server.sh clean' to stop Docker services")


app = FastAPI(
    title="Polymer NLP Extractor API",
    description="API for managing polymer NLP extraction workflows (Phase 0D - Inference Only)",
    version="1.0.0",
    lifespan=lifespan
)

# Include Setup API router
app.include_router(setup.router, prefix="/api", tags=["Setup"])

# Include Session Management API router
app.include_router(session.router, prefix="/api", tags=["Session"])

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

# Include Models Sync API router (Phase 2 enhancement)
app.include_router(models_sync.router, prefix="/api", tags=["Models Sync"])

# Include Documentation API router
app.include_router(documentation.router, prefix="/api", tags=["Documentation"])


@app.get("/")
def root():
    """
    Root endpoint providing API navigation and status information.
    
    Returns
    -------
    Dict[str, Any]
        API status and available endpoint information
    """
    return {
        "status": "ok", 
        "message": "Polymer NLP Extractor API is running (Phase 0D - Inference Only)",
        "version": "1.0.0",
        "endpoints": {
            "setup": "/api/setup/* - System initialization and health monitoring",
            "grobid": "/api/grobid/* - PDF extraction and TEI processing", 
            "groundtruth": "/api/groundtruth/* - Ground truth data management",
            "preprocessing": "/api/preprocessing/* - Data preprocessing workflows",
            "inference": "/api/inference/* - Ensemble model inference",
            "evaluation": "/api/evaluation/* - Model evaluation and metrics",
            "documentation": "/api/docs/* - Project documentation and guides"
        },
        "documentation": {
            "api_docs": "/docs",
            "project_docs": "/api/docs-ui",
            "files_api": "/api/docs"
        },
        "help": "/help",
        "server_management": "Use ./server.sh for Docker service management",
        "training": "Use notebooks/model_training_finetuning.ipynb for model training"
    }


@app.get("/help")
def help_endpoint():
    """
    Help endpoint providing comprehensive API usage information.
    
    Returns
    -------
    Dict[str, Any]
        Detailed API usage guidance and examples
    """
    return {
        "title": "Polymer NLP Extractor API - Help",
        "description": "Comprehensive API for polymer literature extraction and analysis",
        "getting_started": {
            "1_check_services": {
                "endpoint": "GET /api/setup/health",
                "description": "Check if all required services are running",
                "example": "curl http://localhost:8000/api/setup/health"
            },
            "2_initialize_system": {
                "endpoint": "POST /api/setup/initialize", 
                "description": "Initialize database schemas and check models",
                "example": "curl -X POST http://localhost:8000/api/setup/initialize"
            },
            "3_process_documents": {
                "endpoint": "POST /api/grobid/process",
                "description": "Extract structured data from PDF documents",
                "example": "See /docs for detailed request schemas"
            }
        },
        "main_workflows": {
            "pdf_extraction": [
                "POST /api/grobid/process - Convert PDF to structured TEI XML",
                "POST /api/preprocessing/clean - Clean and normalize extracted text", 
                "POST /api/inference/predict - Run ensemble models for entity extraction"
            ],
            "evaluation": [
                "POST /api/groundtruth/upload - Upload ground truth datasets",
                "POST /api/evaluation/run - Evaluate model performance",
                "GET /api/evaluation/results - Retrieve evaluation metrics"
            ],
            "system_management": [
                "GET /api/setup/health - Monitor system health",
                "POST /api/setup/reset - Reset system data (development only)"
            ]
        },
        "service_management": {
            "start_services": "./server.sh services",
            "check_status": "./server.sh status", 
            "stop_services": "./server.sh clean",
            "note": "Services are managed via ./server.sh script, not API endpoints"
        },
        "training": {
            "location": "notebooks/model_training_finetuning.ipynb",
            "note": "Model training is handled exclusively through Jupyter notebooks in Phase 0D"
        },
        "documentation": {
            "interactive_docs": "/docs",
            "openapi_schema": "/openapi.json",
            "postman_collection": "postman/setup.postman_collection.json"
        },
        "support": {
            "issues": "Check logs in workspace/public/logs/",
            "database": "Use ./server.sh status to check database connectivity",
            "models": "Ensure models are present in workspace/public/models/"
        }
    }
