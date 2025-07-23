# polymer_extractor/setup/setup_service.py

"""
SetupService for Polymer NLP Extractor.

Bootstraps Appwrite collections and buckets required for the project.
"""
import os

from appwrite.exception import AppwriteException

from polymer_extractor.storage.appwrite_client import get_database_service, get_storage_service, get_database_id
from polymer_extractor.utils.logging import Logger

logger = Logger()


class SetupService:
    """
    Handles initialization of Appwrite collections and buckets.
    """

    def __init__(self):
        self.db = get_database_service()
        self.storage = get_storage_service()
        self.database_id = get_database_id()

    def create_collection(self, collection_id: str, name: str, attributes: list):
        """
        Create a collection with specified attributes if it does not exist.

        Parameters
        ----------
        collection_id : str
            Unique identifier for the collection.
        name : str
            Human-readable name of the collection.
        attributes : list
            List of tuples: (attr_type, attr_name, size_or_elements, required)
        """
        try:
            self.db.get_collection(self.database_id, collection_id)
            logger.info(f"Collection '{collection_id}' already exists.",
                        source="setup_service", category="system", event_type="collection_check")
        except AppwriteException as e:
            if e.code == 404:
                logger.info(f"Creating collection '{collection_id}'...",
                            source="setup_service", category="system", event_type="collection_create")
                self.db.create_collection(
                    database_id=self.database_id,
                    collection_id=collection_id,
                    name=name,
                    document_security=False
                )
                for attr in attributes:
                    attr_type, attr_name, size, required = attr
                    create_method = getattr(self.db, f"create_{attr_type}_attribute")

                    if attr_type == "enum":
                        create_method(
                            database_id=self.database_id,
                            collection_id=collection_id,
                            key=attr_name,
                            elements=size,
                            required=required
                        )
                    elif attr_type == "string":
                        create_method(
                            database_id=self.database_id,
                            collection_id=collection_id,
                            key=attr_name,
                            size=size,
                            required=required
                        )
                    else:
                        create_method(
                            database_id=self.database_id,
                            collection_id=collection_id,
                            key=attr_name,
                            required=required
                        )
                logger.info(f"Collection '{collection_id}' created with attributes.",
                            source="setup_service", category="system", event_type="collection_created")
            else:
                logger.error(f"Failed to check/create collection '{collection_id}'",
                             source="setup_service", error=e, event_type="collection_error")
                raise

    def create_bucket(self, bucket_id: str, name: str):
        """
        Create a bucket if it does not exist.

        Parameters
        ----------
        bucket_id : str
            Unique identifier for the bucket.
        name : str
            Human-readable name of the bucket.
        """
        try:
            self.storage.get_bucket(bucket_id)
            logger.info(f"[Setup] Bucket '{bucket_id}' already exists.", source="setup_service", category="system",
                        event_type="bucket_check")
        except AppwriteException as e:
            if e.code == 404:
                self.storage.create_bucket(bucket_id, name, file_security=False)
                logger.info(f"[Setup] Bucket '{bucket_id}' created.", source="setup_service", category="system",
                            event_type="bucket_create")
            else:
                logger.error(f"[Setup] Error checking/creating bucket '{bucket_id}': {e}", source="setup_service",
                             error=e, category="system", event_type="bucket_error")
                raise

    def initialize_all_resources(self):
        """
        Initialize all collections and buckets needed for the project.
        """
        logger.info("[Setup] Initializing all Appwrite resources...", source="setup_service", category="system",
                    event_type="init")

        # === Collections ===
        self.create_collection("file_metadata", "File Metadata", [
            ("string", "file_name", 255, True),
            ("string", "doi", 255, False),
            ("string", "title", 255, False),
            ("string", "authors", 5000, False),
            ("string", "journal", 255, False),
            ("datetime", "published_on", None, False),
            ("string", "grobid_version", 50, False),
            ("datetime", "processed_on", None, False),
            ("string", "file_url", 1024, False),
            ("string", "pdf_url", 1024, False),
        ])

        self.create_collection("extraction_metadata", "Extraction Metadata", [
            ("string", "file_id", 255, True),
            ("string", "extracted_entities", 50000, False),
            ("string", "model_version", 50, False),
            ("float", "confidence", None, False),
            ("datetime", "processed_on", None, False),
            ("enum", "status", ["pending", "success", "fail"], False),
            ("string", "remarks", 1024, False),
        ])

        self.create_collection("models_metadata", "Models Metadata", [
            ("string", "model_name", 255, True),
            ("string", "version", 50, True),
            ("string", "local_path", 1024, False),
            ("string", "bucket_path", 1024, False),
            ("datetime", "trained_on", None, False),
            ("string", "notes", 2048, False),
        ])

        self.create_collection("datasets_metadata", "Datasets Metadata", [
            ("string", "dataset_name", 255, True),
            ("enum", "type", ["training", "testing"], True),
            ("datetime", "created_on", None, False),
            ("string", "source", 1024, False),
            ("integer", "size", None, False),
            ("string", "notes", 2048, False),
            ("string", "original_filename", 255, False),
            ("string", "file_type", 50, False),
            ("datetime", "processed_at", None, False),
            ("string", "file_url", 1024, False),
            ("string", "appwrite_file_id", 255, False),
            ("string", "local_path", 1024, False),
            ("integer", "file_size", 2048, False),
            ("string", "statistics", 2000, False),
            ("string", "data_quality", 2000, False),
            ("string", "columns", 2000, False),
        ])

        # === Buckets ===
        self.create_bucket("datasets_bucket", "Datasets Bucket")
        self.create_bucket("raw_documents_bucket", "Raw Documents Bucket")
        self.create_bucket("processed_xml_bucket", "Processed XML Bucket")
        self.create_bucket("logs_bucket", "Logs Bucket")
        self.create_bucket("grobid_bucket", "GROBID Bucket")
        upload_dummy_pdf()

def upload_dummy_pdf():
    """
    Upload a dummy PDF to the GROBID bucket and save metadata in file_metadata collection.

    This ensures the GROBID pipeline has a test document to process,
    and the file_metadata collection tracks its presence.

    Returns
    -------
    None
    """

    from polymer_extractor.utils.paths import WORKSPACE_DIR
    from polymer_extractor.storage.database_manager import DatabaseManager
    from polymer_extractor.storage.bucket_manager import BucketManager

    dummy_pdf_path = os.path.join(WORKSPACE_DIR, "public", "grobid", "dummy_research_paper.pdf")

    if not os.path.exists(dummy_pdf_path):
        print("[Setup] Dummy PDF not found at expected path. Skipping upload.")
        return

    bucket_manager = BucketManager()
    db_manager = DatabaseManager()

    # === Ensure GROBID Bucket Exists ===
    try:
        bucket_manager.get_bucket("grobid_bucket")
        logger.info("GROBID bucket already exists.",
                    source="setup_service", category="system", event_type="bucket_check")
    except AppwriteException as e:
        if e.code == 404:
            logger.info("Creating 'grobid_bucket'...",
                        source="setup_service", category="system", event_type="bucket_create")
            try:
                bucket_manager.create_bucket("grobid_bucket", "GROBID Documents Bucket")
                logger.info("Created 'grobid_bucket' successfully.",
                            source="setup_service", category="system", event_type="bucket_created")
            except AppwriteException as ce:
                logger.error("Failed to create 'grobid_bucket'.",
                             source="setup_service", category="system", event_type="dummy_pdf_error", error=ce)
                return
        else:
            logger.error("Error checking GROBID bucket existence.",
                         source="setup_service", category="system", event_type="dummy_pdf_error", error=e)
            return

    # === Check if Metadata Already Exists ===
    try:
        existing_docs = db_manager.list_documents("file_metadata")
        if any(doc['file_name'] == "dummy_research_paper.pdf" for doc in existing_docs):
            logger.info("Dummy PDF metadata already exists in file_metadata collection.",
                        source="setup_service", category="system", event_type="dummy_pdf_exists")
            return
    except AppwriteException as e:
        logger.error("Error checking existing dummy PDF metadata.",
                     source="setup_service", category="system", event_type="dummy_pdf_error", error=e)
        return

    # === Upload PDF ===
    try:
        # check if file exists in the bucket before uploading
        existing_files = bucket_manager.list_files("grobid_bucket")
        if any(file['name'] == "dummy_research_paper.pdf" for file in existing_files):
            logger.info("Dummy PDF already exists in GROBID bucket. Skipping upload.",
                        source="setup_service", category="system", event_type="dummy_pdf_exists")
            return

        file_response = bucket_manager.upload_file(
            bucket_id="grobid_bucket",
            file_path=dummy_pdf_path
        )
        file_id = file_response['$id']
        logger.info(f"Uploaded dummy PDF to GROBID bucket: {file_id}",
                    source="setup_service", category="system", event_type="dummy_pdf_uploaded")
    except AppwriteException as e:
        logger.error("Failed to upload dummy PDF to GROBID bucket.",
                     source="setup_service", category="system", event_type="dummy_pdf_error", error=e)
        return

    # === Save Metadata (only non-null fields) ===
    metadata = {
        "document_id": file_id,
        "file_name": "dummy_research_paper.pdf",
        "title": "Dummy Research Paper",
        "authors": "John Doe, Jane Smith",
        "journal": "Journal of Testing",
        "grobid_version": "0.6.1"
        # published_on and processed_on omitted (None values)
    }

    try:
        db_manager.create_document(
            collection_id="file_metadata",
            data=metadata
        )
        logger.info("Saved metadata for dummy PDF to file_metadata collection.",
                    source="setup_service", category="system", event_type="dummy_pdf_metadata")
    except AppwriteException as e:
        logger.error("Failed to save metadata for dummy PDF.",
                     source="setup_service", category="system", event_type="dummy_pdf_error", error=e)
        return

# Upload dummy PDF to GROBID bucket
upload_dummy_pdf()


# === Shortcuts ===
setup = SetupService()
add_collection = setup.create_collection
add_bucket = setup.create_bucket
initialize_all = setup.initialize_all_resources
