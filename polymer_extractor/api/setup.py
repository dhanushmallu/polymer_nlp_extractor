# polymer_extractor/setup/setup.py

from fastapi import APIRouter, HTTPException

from polymer_extractor.services.setup_service import SetupService, upload_dummy_pdf
from polymer_extractor.storage.bucket_manager import BucketManager
from polymer_extractor.storage.database_manager import DatabaseManager
from polymer_extractor.utils.logging import Logger

router = APIRouter()
logger = Logger()
setup = SetupService()
db_manager = DatabaseManager()
bucket_manager = BucketManager()


@router.get("/setup/analyze")
def analyze_system():
    """
    Analyze current Appwrite resources: collections and buckets.

    Returns
    -------
    dict
        Summary of existing collections and buckets.
    """
    try:
        collections = db_manager.list_collections()
        buckets = bucket_manager.list_buckets()
        logger.info("System analysis performed successfully.", source="setup_api",
                    category="api", event_type="analyze_system")
        return {
            "collections": [col['$id'] for col in collections],
            "buckets": [bkt['$id'] for bkt in buckets]
        }
    except Exception as e:
        logger.error("Failed to analyze system.", source="setup_api",
                     category="api", event_type="analyze_error", error=e)
        raise HTTPException(status_code=500, detail="Failed to analyze system.")


@router.post("/setup/reset")
def reset_system():
    """
    Drop and recreate all project-specific Appwrite resources.

    WARNING: This will delete all collections and buckets except system_logs.
    """
    try:
        # Delete collections
        collections = db_manager.list_collections()
        for col in collections:
            if col['$id'] != "system_logs":  # Skip Logger's autonomous collection
                db_manager.delete_collection(col['$id'])

        # Delete buckets
        buckets = bucket_manager.list_buckets()
        for bkt in buckets:
            bucket_manager.delete_bucket(bkt['$id'])

        # Reinitialize
        setup.initialize_all_resources()
        logger.info("System reset and reinitialized successfully.",
                    source="setup_api", category="api", event_type="reset_system")
        return {"status": "success", "message": "System reset and reinitialized successfully."}
    except Exception as e:
        logger.error("Failed to reset system.", source="setup_api",
                     category="api", event_type="reset_error", error=e)
        raise HTTPException(status_code=500, detail="Failed to reset system.")


@router.post("/setup/init")
def initialize_resources():
    """
    Initialize all required Appwrite resources without deleting existing ones.

    Returns
    -------
    dict
        Status of initialization.
    """
    try:
        setup.initialize_all_resources()
        logger.info("Resources initialized successfully.",
                    source="setup_api", category="api", event_type="init_resources")
        return {"status": "success", "message": "Resources initialized successfully."}
    except Exception as e:
        logger.error("Failed to initialize resources.", source="setup_api",
                     category="api", event_type="init_error", error=e)
        raise HTTPException(status_code=500, detail="Failed to initialize resources.")


@router.post("/setup/upload-dummy")
def upload_dummy():
    """
    Upload the dummy PDF to GROBID bucket and save its metadata.

    Returns
    -------
    dict
        Status of upload.
    """
    try:
        upload_dummy_pdf()
        logger.info("Dummy PDF uploaded successfully.",
                    source="setup_api", category="api", event_type="upload_dummy")
        return {"status": "success", "message": "Dummy PDF uploaded and metadata saved."}
    except Exception as e:
        logger.error("Failed to upload dummy PDF.", source="setup_api",
                     category="api", event_type="upload_dummy_error", error=e)
        raise HTTPException(status_code=500, detail="Failed to upload dummy PDF.")
