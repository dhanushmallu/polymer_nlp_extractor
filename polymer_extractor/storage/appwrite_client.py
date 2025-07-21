# polymer_extractor/storage/appwrite_client.py

"""
Appwrite Client Initializer for Polymer NLP Extractor.

This module provides a centralized way to initialize and access Appwrite services.
It ensures consistent configuration across all database and bucket operations.

Logger is used for error reporting and connection diagnostics.
"""

import os
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.services.storage import Storage
from appwrite.exception import AppwriteException
from dotenv import load_dotenv
from polymer_extractor.utils.logging import Logger

# Initialize logger
logger = Logger()

# === Load Environment Variables ===
load_dotenv()

# === Appwrite Configuration ===
APPWRITE_ENDPOINT = os.getenv("APPWRITE_ENDPOINT")
APPWRITE_PROJECT_ID = os.getenv("APPWRITE_PROJECT_ID")
APPWRITE_API_KEY = os.getenv("APPWRITE_API_KEY")
APPWRITE_DATABASE_ID = os.getenv("APPWRITE_DATABASE_ID")
APPWRITE_DEFAULT_BUCKET = os.getenv("APPWRITE_BUCKET_ID")  # Optional default bucket

# === Validate Configuration ===
required_envs = {
    "APPWRITE_ENDPOINT": APPWRITE_ENDPOINT,
    "APPWRITE_PROJECT_ID": APPWRITE_PROJECT_ID,
    "APPWRITE_API_KEY": APPWRITE_API_KEY,
    "APPWRITE_DATABASE_ID": APPWRITE_DATABASE_ID
}

missing_envs = [key for key, value in required_envs.items() if not value]
if missing_envs:
    logger.critical(
        f"Missing required Appwrite environment variables: {', '.join(missing_envs)}",
        source="appwrite_client",
        event_type="startup",
        user_action=False
    )
    raise EnvironmentError(
        f"[Appwrite Client ERROR] Missing required environment variables: {', '.join(missing_envs)}"
    )


def get_client() -> Client:
    """
    Initialize and return an authenticated Appwrite Client.

    Returns
    -------
    Client
        Configured Appwrite client instance.

    Raises
    ------
    EnvironmentError
        If required environment variables are missing.
    """
    try:
        client = Client()
        client.set_endpoint(APPWRITE_ENDPOINT)
        client.set_project(APPWRITE_PROJECT_ID)
        client.set_key(APPWRITE_API_KEY)
        logger.info(
            "Appwrite Client initialized successfully.",
            source="appwrite_client",
            event_type="startup"
        )
        return client
    except Exception as e:
        logger.error(
            "Failed to initialize Appwrite Client.",
            source="appwrite_client",
            error=e,
            event_type="startup"
        )
        raise


def get_database_service() -> Databases:
    """
    Get the Appwrite Databases service instance.

    Returns
    -------
    Databases
        Appwrite Databases service.
    """
    try:
        client = get_client()
        return Databases(client)
    except Exception as e:
        logger.error(
            "Failed to get Databases service.",
            source="appwrite_client",
            error=e,
            event_type="startup"
        )
        raise

def get_database_id() -> str:
    """
    Get the configured Appwrite database ID.

    Returns
    -------
    str
        Appwrite database ID.
    """
    return APPWRITE_DATABASE_ID


def get_storage_service() -> Storage:
    """
    Get the Appwrite Storage service instance.

    Returns
    -------
    Storage
        Appwrite Storage service.
    """
    try:
        client = get_client()
        return Storage(client)
    except Exception as e:
        logger.error(
            "Failed to get Storage service.",
            source="appwrite_client",
            error=e,
            event_type="startup"
        )
        raise


def test_connection() -> bool:
    """
    Test Appwrite connection and authentication.

    Returns
    -------
    bool
        True if connection is successful, False otherwise.
    """
    try:
        db = get_database_service()
        db.list_collections(APPWRITE_DATABASE_ID)
        logger.info(
            "Appwrite connection test successful.",
            source="appwrite_client",
            event_type="startup"
        )
        return True
    except AppwriteException as e:
        logger.critical(
            "Appwrite connection test failed.",
            source="appwrite_client",
            error=e,
            event_type="startup"
        )
        return False
