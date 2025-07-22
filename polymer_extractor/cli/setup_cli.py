# polymer_extractor/cli/setup_cli.py

from typer import Typer, echo
from polymer_extractor.services.setup_service import SetupService, upload_dummy_pdf
from polymer_extractor.storage.database_manager import DatabaseManager
from polymer_extractor.storage.bucket_manager import BucketManager
from polymer_extractor.utils.logging import Logger

setup_app = Typer(help="Appwrite setup management CLI.")
logger = Logger()

setup_service = SetupService()
db_manager = DatabaseManager()
bucket_manager = BucketManager()


@setup_app.command("analyze")
def analyze_system():
    """
    Analyze current Appwrite resources: collections and buckets.
    """
    echo("Analyzing Appwrite system...")
    try:
        collections = db_manager.list_collections()
        buckets = bucket_manager.list_buckets()

        echo("\nCollections:")
        for col in collections:
            echo(f" - {col['$id']} ({len(col['attributes'])} attributes)")

        echo("\nBuckets:")
        for bkt in buckets:
            echo(f" - {bkt['$id']}")

        logger.info("System analysis completed successfully.", source="setup_cli",
                    category="cli", event_type="analyze_system")
    except Exception as e:
        logger.error("Failed to analyze system.", source="setup_cli",
                     category="cli", event_type="analyze_error", error=e)
        echo(f"Error analyzing system: {e}")


@setup_app.command("reset")
def reset_system():
    """
    Reset Appwrite schema: drop and recreate all resources.
    WARNING: This deletes all data except system_logs.
    """
    echo("Resetting Appwrite schema...")
    try:
        # Delete collections
        collections = db_manager.list_collections()
        for col in collections:
            if col['$id'] != "system_logs":
                db_manager.delete_collection(col['$id'])
                echo(f"Deleted collection: {col['$id']}")

        # Delete buckets
        buckets = bucket_manager.list_buckets()
        for bkt in buckets:
            bucket_manager.delete_bucket(bkt['$id'])
            echo(f"Deleted bucket: {bkt['$id']}")

        # Reinitialize
        setup_service.initialize_all_resources()
        echo("Schema reset and reinitialized successfully.")
        logger.info("Schema reset completed successfully.", source="setup_cli",
                    category="cli", event_type="reset_system")
    except Exception as e:
        logger.error("Failed to reset system.", source="setup_cli",
                     category="cli", event_type="reset_error", error=e)
        echo(f"Error resetting system: {e}")


@setup_app.command("init")
def initialize_resources():
    """
    Initialize Appwrite resources: collections and buckets.
    """
    echo("Initializing Appwrite resources...")
    try:
        setup_service.initialize_all_resources()
        echo("Resources initialized successfully.")
        logger.info("Resources initialized successfully.", source="setup_cli",
                    category="cli", event_type="init_resources")
    except Exception as e:
        logger.error("Failed to initialize resources.", source="setup_cli",
                     category="cli", event_type="init_error", error=e)
        echo(f"Error initializing resources: {e}")


@setup_app.command("upload-dummy")
def upload_dummy():
    """
    Upload the dummy PDF to GROBID bucket and save metadata.
    """
    echo("Uploading dummy PDF...")
    try:
        upload_dummy_pdf()
        echo("Dummy PDF uploaded and metadata saved.")
        logger.info("Dummy PDF uploaded successfully.", source="setup_cli",
                    category="cli", event_type="upload_dummy")
    except Exception as e:
        logger.error("Failed to upload dummy PDF.", source="setup_cli",
                     category="cli", event_type="upload_dummy_error", error=e)
        echo(f"Error uploading dummy PDF: {e}")
