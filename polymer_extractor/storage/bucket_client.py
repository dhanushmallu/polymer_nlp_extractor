# polymer_extractor/storage/bucket_client.py

"""
Universal Bucket Client for Polymer NLP Extractor.

This module provides a unified storage interface supporting multiple backends:
- Local filesystem storage
- Appwrite cloud storage  
- S3-compatible storage

The storage backend is configurable via environment variables.
Logger is used for error reporting and operation tracking.
"""

import os
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, BinaryIO
from abc import ABC, abstractmethod
from datetime import datetime

from dotenv import load_dotenv
from polymer_extractor.utils.logging import Logger

# Initialize logger
logger = Logger()

# === Load Environment Variables ===
load_dotenv()

# === Storage Configuration ===
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
STORAGE_PATH = os.getenv("STORAGE_PATH", "./workspace/public")

# Appwrite Storage Configuration
APPWRITE_STORAGE_ENDPOINT = os.getenv("APPWRITE_STORAGE_ENDPOINT")
APPWRITE_STORAGE_PROJECT_ID = os.getenv("APPWRITE_STORAGE_PROJECT_ID")
APPWRITE_STORAGE_API_KEY = os.getenv("APPWRITE_STORAGE_API_KEY")
APPWRITE_STORAGE_BUCKET_ID = os.getenv("APPWRITE_STORAGE_BUCKET_ID")

# S3 Storage Configuration
S3_BUCKET = os.getenv("S3_BUCKET")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    def upload(self, file_path: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Upload file content to storage."""
        pass
    
    @abstractmethod
    def download(self, file_path: str) -> bytes:
        """Download file content from storage."""
        pass
    
    @abstractmethod
    def delete(self, file_path: str) -> bool:
        """Delete file from storage."""
        pass
    
    @abstractmethod
    def list_files(self, folder: str = "") -> List[Dict[str, Any]]:
        """List files in storage folder."""
        pass
    
    @abstractmethod
    def exists(self, file_path: str) -> bool:
        """Check if file exists in storage."""
        pass
    
    @abstractmethod
    def get_metadata(self, file_path: str) -> Dict[str, Any]:
        """Get file metadata."""
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_full_path(self, file_path: str) -> Path:
        """Get full filesystem path for file."""
        return self.base_path / file_path.lstrip('/')
    
    def upload(self, file_path: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Upload file to local storage."""
        try:
            full_path = self._get_full_path(file_path)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file content
            with open(full_path, 'wb') as f:
                f.write(content)
            
            # Write metadata if provided
            if metadata:
                metadata_path = full_path.with_suffix(full_path.suffix + '.meta')
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f)
            
            file_stat = full_path.stat()
            return {
                '$id': file_path,
                'name': full_path.name,
                'path': file_path,
                'size': file_stat.st_size,
                'mimeType': metadata.get('mimeType', 'application/octet-stream') if metadata else 'application/octet-stream',
                'dateCreated': datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                'dateUpdated': datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            }
        except Exception as e:
            logger.error(f"Local storage upload failed for {file_path}", error=e, source="bucket_client")
            raise
    
    def download(self, file_path: str) -> bytes:
        """Download file from local storage."""
        try:
            full_path = self._get_full_path(file_path)
            with open(full_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Local storage download failed for {file_path}", error=e, source="bucket_client")
            raise
    
    def delete(self, file_path: str) -> bool:
        """Delete file from local storage."""
        try:
            full_path = self._get_full_path(file_path)
            if full_path.exists():
                full_path.unlink()
                # Also delete metadata file if it exists
                metadata_path = full_path.with_suffix(full_path.suffix + '.meta')
                if metadata_path.exists():
                    metadata_path.unlink()
                return True
            return False
        except Exception as e:
            logger.error(f"Local storage delete failed for {file_path}", error=e, source="bucket_client")
            raise
    
    def list_files(self, folder: str = "") -> List[Dict[str, Any]]:
        """List files in local storage folder."""
        try:
            folder_path = self._get_full_path(folder)
            if not folder_path.exists():
                return []
            
            files = []
            for file_path in folder_path.rglob('*'):
                if file_path.is_file() and not file_path.suffix == '.meta':
                    relative_path = str(file_path.relative_to(self.base_path))
                    file_stat = file_path.stat()
                    files.append({
                        '$id': relative_path,
                        'name': file_path.name,
                        'path': relative_path,
                        'size': file_stat.st_size,
                        'mimeType': self._guess_mime_type(file_path.name),
                        'dateCreated': datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                        'dateUpdated': datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                    })
            return files
        except Exception as e:
            logger.error(f"Local storage list failed for folder {folder}", error=e, source="bucket_client")
            raise
    
    def exists(self, file_path: str) -> bool:
        """Check if file exists in local storage."""
        return self._get_full_path(file_path).exists()
    
    def get_metadata(self, file_path: str) -> Dict[str, Any]:
        """Get file metadata from local storage."""
        try:
            full_path = self._get_full_path(file_path)
            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            file_stat = full_path.stat()
            metadata = {
                '$id': file_path,
                'name': full_path.name,
                'path': file_path,
                'size': file_stat.st_size,
                'mimeType': self._guess_mime_type(full_path.name),
                'dateCreated': datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                'dateUpdated': datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            }
            
            # Load custom metadata if available
            metadata_path = full_path.with_suffix(full_path.suffix + '.meta')
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    custom_metadata = json.load(f)
                    metadata.update(custom_metadata)
            
            return metadata
        except Exception as e:
            logger.error(f"Local storage metadata failed for {file_path}", error=e, source="bucket_client")
            raise
    
    def _guess_mime_type(self, filename: str) -> str:
        """Guess MIME type from file extension."""
        ext = Path(filename).suffix.lower()
        mime_types = {
            '.txt': 'text/plain',
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.csv': 'text/csv',
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.zip': 'application/zip'
        }
        return mime_types.get(ext, 'application/octet-stream')


class BucketClient:
    """
    Universal bucket client with pluggable storage backends.
    
    Supports local filesystem, Appwrite cloud storage, and S3-compatible storage.
    The backend is selected via the STORAGE_BACKEND environment variable.
    """
    
    def __init__(self):
        """Initialize bucket client with configured storage backend."""
        self.backend = self._create_backend()
        logger.info(f"BucketClient initialized with {STORAGE_BACKEND} backend", 
                   source="bucket_client", event_type="startup")
    
    def _create_backend(self) -> StorageBackend:
        """Create appropriate storage backend based on configuration."""
        if STORAGE_BACKEND == "local":
            return LocalStorageBackend(STORAGE_PATH)
        elif STORAGE_BACKEND == "appwrite":
            # Import only when needed to avoid dependency issues
            try:
                from appwrite.client import Client
                from appwrite.services.storage import Storage
                
                if not all([APPWRITE_STORAGE_ENDPOINT, APPWRITE_STORAGE_PROJECT_ID, 
                           APPWRITE_STORAGE_API_KEY, APPWRITE_STORAGE_BUCKET_ID]):
                    raise ValueError("Missing required Appwrite storage configuration")
                
                # Create a minimal Appwrite storage backend
                class AppwriteStorageBackend(StorageBackend):
                    def __init__(self):
                        self.client = Client()
                        self.client.set_endpoint(APPWRITE_STORAGE_ENDPOINT)
                        self.client.set_project(APPWRITE_STORAGE_PROJECT_ID)
                        self.client.set_key(APPWRITE_STORAGE_API_KEY)
                        self.storage = Storage(self.client)
                        self.bucket_id = APPWRITE_STORAGE_BUCKET_ID
                    
                    def upload(self, file_path: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
                        # Simplified Appwrite upload - implement as needed
                        raise NotImplementedError("Appwrite backend upload not fully implemented")
                    
                    def download(self, file_path: str) -> bytes:
                        raise NotImplementedError("Appwrite backend download not fully implemented")
                    
                    def delete(self, file_path: str) -> bool:
                        raise NotImplementedError("Appwrite backend delete not fully implemented")
                    
                    def list_files(self, folder: str = "") -> List[Dict[str, Any]]:
                        result = self.storage.list_files(bucket_id=self.bucket_id)
                        return result.get('files', [])
                    
                    def exists(self, file_path: str) -> bool:
                        return False  # Simplified for now
                    
                    def get_metadata(self, file_path: str) -> Dict[str, Any]:
                        raise NotImplementedError("Appwrite backend metadata not fully implemented")
                
                return AppwriteStorageBackend()
            except ImportError:
                raise ImportError("Appwrite SDK not installed. Install with: pip install appwrite")
        elif STORAGE_BACKEND == "s3":
            # Import only when needed to avoid dependency issues  
            try:
                import boto3
                
                if not all([S3_BUCKET, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY]):
                    raise ValueError("Missing required S3 storage configuration")
                
                # Create a minimal S3 storage backend
                class S3StorageBackend(StorageBackend):
                    def __init__(self):
                        session = boto3.Session(
                            aws_access_key_id=S3_ACCESS_KEY_ID,
                            aws_secret_access_key=S3_SECRET_ACCESS_KEY,
                            region_name=S3_REGION
                        )
                        self.s3 = session.client('s3', endpoint_url=S3_ENDPOINT_URL)
                        self.bucket = S3_BUCKET
                    
                    def upload(self, file_path: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
                        raise NotImplementedError("S3 backend upload not fully implemented")
                    
                    def download(self, file_path: str) -> bytes:
                        raise NotImplementedError("S3 backend download not fully implemented")
                    
                    def delete(self, file_path: str) -> bool:
                        raise NotImplementedError("S3 backend delete not fully implemented")
                    
                    def list_files(self, folder: str = "") -> List[Dict[str, Any]]:
                        raise NotImplementedError("S3 backend list not fully implemented")
                    
                    def exists(self, file_path: str) -> bool:
                        return False  # Simplified for now
                    
                    def get_metadata(self, file_path: str) -> Dict[str, Any]:
                        raise NotImplementedError("S3 backend metadata not fully implemented")
                
                return S3StorageBackend()
            except ImportError:
                raise ImportError("boto3 not installed. Install with: pip install boto3")
        else:
            raise ValueError(f"Unsupported storage backend: {STORAGE_BACKEND}")
    
    def upload_file(self, file_path: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Upload file content to storage.
        
        Parameters
        ----------
        file_path : str
            Path where file should be stored
        content : bytes
            File content as bytes
        metadata : dict, optional
            Additional metadata to store with file
            
        Returns
        -------
        dict
            File information including ID, size, timestamps
        """
        return self.backend.upload(file_path, content, metadata)
    
    def download_file(self, file_path: str) -> bytes:
        """
        Download file content from storage.
        
        Parameters
        ----------
        file_path : str
            Path to file in storage
            
        Returns
        -------
        bytes
            File content as bytes
        """
        return self.backend.download(file_path)
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete file from storage.
        
        Parameters
        ----------
        file_path : str
            Path to file in storage
            
        Returns
        -------
        bool
            True if file was deleted successfully
        """
        return self.backend.delete(file_path)
    
    def list_files(self, folder: str = "") -> List[Dict[str, Any]]:
        """
        List files in storage folder.
        
        Parameters
        ----------
        folder : str, optional
            Folder path to list (empty for root)
            
        Returns
        -------
        list
            List of file information dictionaries
        """
        return self.backend.list_files(folder)
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if file exists in storage.
        
        Parameters
        ----------
        file_path : str
            Path to file in storage
            
        Returns
        -------
        bool
            True if file exists
        """
        return self.backend.exists(file_path)
    
    def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Get file metadata from storage.
        
        Parameters
        ----------
        file_path : str
            Path to file in storage
            
        Returns
        -------
        dict
            File metadata including size, timestamps, etc.
        """
        return self.backend.get_metadata(file_path)
    
    def get_backend_type(self) -> str:
        """
        Get the current storage backend type.
        
        Returns
        -------
        str
            Backend type (local, appwrite, s3)
        """
        return STORAGE_BACKEND
    
    def test_connection(self) -> bool:
        """
        Test storage backend connection.
        
        Returns
        -------
        bool
            True if connection is working
        """
        try:
            # Test by listing files in root
            self.backend.list_files("")
            return True
        except Exception as e:
            logger.error(f"Storage backend connection test failed", error=e, source="bucket_client")
            return False


def get_bucket_client() -> BucketClient:
    """
    Get configured bucket client instance.
    
    Returns
    -------
    BucketClient
        Configured bucket client
    """
    return BucketClient()


# Legacy compatibility functions (deprecated)
def get_storage_service():
    """
    Legacy function for backward compatibility.
    
    Deprecated: Use get_bucket_client() instead.
    """
    logger.warning("get_storage_service() is deprecated. Use get_bucket_client() instead.", 
                  source="bucket_client")
    return get_bucket_client()


def get_client():
    """
    Legacy function for backward compatibility.
    
    Deprecated: Use get_bucket_client() instead.
    """
    logger.warning("get_client() is deprecated. Use get_bucket_client() instead.", 
                  source="bucket_client")
    return get_bucket_client()


def get_database_service():
    """
    Legacy function for backward compatibility.
    
    Deprecated: Database functionality moved to database_manager.py
    """
    logger.warning("get_database_service() is deprecated. Database functionality moved to database_manager.py", 
                  source="bucket_client")
    raise NotImplementedError("Database functionality moved to database_manager.py")


def get_database_id():
    """
    Legacy function for backward compatibility.
    
    Deprecated: Database functionality moved to database_manager.py
    """
    logger.warning("get_database_id() is deprecated. Database functionality moved to database_manager.py", 
                  source="bucket_client")
    raise NotImplementedError("Database functionality moved to database_manager.py")


def test_connection() -> bool:
    """
    Legacy function for backward compatibility.
    
    Deprecated: Use get_bucket_client().test_connection() instead.
    """
    logger.warning("test_connection() is deprecated. Use get_bucket_client().test_connection() instead.", 
                  source="bucket_client")
    client = get_bucket_client()
    return client.test_connection()
