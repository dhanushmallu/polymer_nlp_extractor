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

# Multi-backend Configuration
STORAGE_BACKENDS_ACTIVE = os.getenv("STORAGE_BACKENDS_ACTIVE", "local").split(",")
STORAGE_STRATEGY = os.getenv("STORAGE_STRATEGY", "primary")

# Appwrite Storage Configuration
APPWRITE_STORAGE_ENDPOINT = os.getenv("APPWRITE_STORAGE_ENDPOINT")
APPWRITE_STORAGE_PROJECT_ID = os.getenv("APPWRITE_STORAGE_PROJECT_ID")
APPWRITE_STORAGE_API_KEY = os.getenv("APPWRITE_STORAGE_API_KEY")
APPWRITE_ENABLED = os.getenv("APPWRITE_ENABLED", "false").lower() == "true"

# S3 Storage Configuration
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
S3_ENABLED = os.getenv("S3_ENABLED", "false").lower() == "true"


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
    
    @abstractmethod
    def create_bucket(self, bucket_name: str) -> Dict[str, Any]:
        """Create a new bucket/container."""
        pass
    
    @abstractmethod
    def delete_bucket(self, bucket_name: str) -> bool:
        """Delete a bucket/container."""
        pass
    
    @abstractmethod
    def list_buckets(self) -> List[Dict[str, Any]]:
        """List all buckets/containers."""
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
    
    def create_bucket(self, bucket_name: str) -> Dict[str, Any]:
        """Create a new bucket (folder) in local storage."""
        try:
            bucket_path = Path(self.base_path) / bucket_name
            bucket_path.mkdir(parents=True, exist_ok=True)
            
            return {
                '$id': bucket_name,
                'name': bucket_name,
                'status': 'created',
                'path': str(bucket_path),
                'backend': 'local'
            }
        except Exception as e:
            logger.error(f"Local storage bucket creation failed for {bucket_name}", error=e, source="bucket_client")
            raise
    
    def delete_bucket(self, bucket_name: str) -> bool:
        """Delete a bucket (folder) from local storage."""
        try:
            bucket_path = Path(self.base_path) / bucket_name
            if bucket_path.exists() and bucket_path.is_dir():
                shutil.rmtree(bucket_path)
                return True
            return False
        except Exception as e:
            logger.error(f"Local storage bucket deletion failed for {bucket_name}", error=e, source="bucket_client")
            return False
    
    def list_buckets(self) -> List[Dict[str, Any]]:
        """List all buckets (folders) in local storage."""
        try:
            storage_path = Path(self.base_path)
            if not storage_path.exists():
                return []
            
            buckets = []
            for item in storage_path.iterdir():
                if item.is_dir():
                    buckets.append({
                        '$id': item.name,
                        'name': item.name,
                        'backend': 'local',
                        'path': str(item)
                    })
            return buckets
        except Exception as e:
            logger.error(f"Local storage bucket listing failed", error=e, source="bucket_client")
            return []


class BucketClient:
    """
    Universal bucket client with multi-backend support.
    
    Supports multiple storage backends simultaneously with configurable strategies:
    - primary: Use only primary backend
    - replica: Write to all backends, read from primary
    - failover: Switch to backup if primary fails
    - sync: Keep all backends synchronized
    """
    
    def __init__(self):
        """Initialize bucket client with configured storage backends."""
        self.backends = self._create_backends()
        self.strategy = STORAGE_STRATEGY
        self.primary_backend = self.backends[0] if self.backends else None
        
        logger.info(f"BucketClient initialized with {len(self.backends)} backends: {[type(b).__name__ for b in self.backends]}", 
                   source="bucket_client", event_type="startup")
        logger.info(f"Storage strategy: {self.strategy}", source="bucket_client", event_type="startup")
    
    def _create_backends(self) -> List[StorageBackend]:
        """Create storage backends based on active configuration."""
        backends = []
        
        for backend_name in STORAGE_BACKENDS_ACTIVE:
            backend_name = backend_name.strip()
            try:
                if backend_name == "local":
                    backends.append(LocalStorageBackend(STORAGE_PATH))
                    logger.info("Local storage backend activated", source="bucket_client")
                    
                elif backend_name == "appwrite" and APPWRITE_ENABLED:
                    # Import only when needed
                    try:
                        from appwrite.client import Client
                        from appwrite.services.storage import Storage
                        
                        if not all([APPWRITE_STORAGE_ENDPOINT, APPWRITE_STORAGE_PROJECT_ID, 
                                   APPWRITE_STORAGE_API_KEY]):
                            logger.warning("Appwrite backend skipped: missing configuration", source="bucket_client")
                            continue
                        
                        # Create Appwrite backend (defined above)
                        backends.append(self._create_appwrite_backend())
                        logger.info("Appwrite storage backend activated", source="bucket_client")
                        
                    except ImportError:
                        logger.error("Appwrite backend skipped: SDK not installed", source="bucket_client")
                        
                elif backend_name == "s3" and S3_ENABLED:
                    # Import only when needed
                    try:
                        import boto3
                        
                        if not all([S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY]):
                            logger.warning("S3 backend skipped: missing configuration", source="bucket_client")
                            continue
                        
                        # Create S3 backend (defined above)
                        backends.append(self._create_s3_backend())
                        logger.info("S3 storage backend activated", source="bucket_client")
                        
                    except ImportError:
                        logger.error("S3 backend skipped: boto3 not installed", source="bucket_client")
                        
                else:
                    logger.warning(f"Unknown or disabled backend: {backend_name}", source="bucket_client")
                    
            except Exception as e:
                logger.error(f"Failed to initialize {backend_name} backend", error=e, source="bucket_client")
        
        if not backends:
            # Fallback to local storage
            backends.append(LocalStorageBackend(STORAGE_PATH))
            logger.warning("No backends configured, falling back to local storage", source="bucket_client")
        
        return backends
    
    def _create_appwrite_backend(self) -> StorageBackend:
        """Create Appwrite backend instance."""
        from appwrite.client import Client
        from appwrite.services.storage import Storage
        
        class AppwriteStorageBackend(StorageBackend):
            def __init__(self):
                self.client = Client()
                self.client.set_endpoint(APPWRITE_STORAGE_ENDPOINT)
                self.client.set_project(APPWRITE_STORAGE_PROJECT_ID)
                self.client.set_key(APPWRITE_STORAGE_API_KEY)
                self.storage = Storage(self.client)
                self._bucket_cache = {}  # Cache created buckets
            
            def upload(self, file_path: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
                try:
                    # Extract bucket name from file path
                    bucket_name = file_path.split('/')[0] if '/' in file_path else 'default'
                    file_name = file_path.split('/', 1)[1] if '/' in file_path else file_path
                    
                    # Ensure bucket exists
                    bucket_id = self._ensure_bucket_exists(bucket_name)
                    
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        temp_file.write(content)
                        temp_file.flush()
                        
                        result = self.storage.create_file(
                            bucket_id=bucket_id,
                            file_id=file_name.replace('/', '_'),
                            file=temp_file.name
                        )
                        
                        os.unlink(temp_file.name)
                        
                        return {
                            '$id': result['$id'],
                            'name': result['name'],
                            'path': file_path,
                            'size': result['sizeOriginal'],
                            'mimeType': result['mimeType'],
                            'dateCreated': result['$createdAt'],
                            'dateUpdated': result['$updatedAt']
                        }
                except Exception as e:
                    logger.error(f"Appwrite upload failed for {file_path}", error=e, source="bucket_client")
                    raise
            
            def download(self, file_path: str) -> bytes:
                try:
                    bucket_name = file_path.split('/')[0] if '/' in file_path else 'default'
                    file_name = file_path.split('/', 1)[1] if '/' in file_path else file_path
                    bucket_id = self._get_bucket_id(bucket_name)
                    
                    file_id = file_name.replace('/', '_')
                    result = self.storage.get_file_download(bucket_id=bucket_id, file_id=file_id)
                    return result
                except Exception as e:
                    logger.error(f"Appwrite download failed for {file_path}", error=e, source="bucket_client")
                    raise
            
            def delete(self, file_path: str) -> bool:
                try:
                    bucket_name = file_path.split('/')[0] if '/' in file_path else 'default'
                    file_name = file_path.split('/', 1)[1] if '/' in file_path else file_path
                    bucket_id = self._get_bucket_id(bucket_name)
                    
                    file_id = file_name.replace('/', '_')
                    self.storage.delete_file(bucket_id=bucket_id, file_id=file_id)
                    return True
                except Exception as e:
                    logger.error(f"Appwrite delete failed for {file_path}", error=e, source="bucket_client")
                    return False
            
            def list_files(self, folder: str = "") -> List[Dict[str, Any]]:
                try:
                    if folder:
                        bucket_name = folder.split('/')[0]
                        bucket_id = self._get_bucket_id(bucket_name)
                    else:
                        # List files from all buckets
                        all_files = []
                        for bucket_name, bucket_id in self._bucket_cache.items():
                            try:
                                result = self.storage.list_files(bucket_id=bucket_id)
                                for file in result.get('files', []):
                                    all_files.append({
                                        '$id': file['$id'],
                                        'name': f"{bucket_name}/{file['name']}",
                                        'size': file['sizeOriginal'],
                                        'mimeType': file['mimeType'],
                                        'dateCreated': file['$createdAt'],
                                        'dateUpdated': file['$updatedAt']
                                    })
                            except:
                                continue
                        return all_files
                    
                    result = self.storage.list_files(bucket_id=bucket_id)
                    files = []
                    for file in result.get('files', []):
                        files.append({
                            '$id': file['$id'],
                            'name': f"{bucket_name}/{file['name']}",
                            'size': file['sizeOriginal'],
                            'mimeType': file['mimeType'],
                            'dateCreated': file['$createdAt'],
                            'dateUpdated': file['$updatedAt']
                        })
                    return files
                except Exception as e:
                    logger.error(f"Appwrite list failed for folder {folder}", error=e, source="bucket_client")
                    return []
            
            def exists(self, file_path: str) -> bool:
                try:
                    bucket_name = file_path.split('/')[0] if '/' in file_path else 'default'
                    file_name = file_path.split('/', 1)[1] if '/' in file_path else file_path
                    bucket_id = self._get_bucket_id(bucket_name)
                    
                    file_id = file_name.replace('/', '_')
                    self.storage.get_file(bucket_id=bucket_id, file_id=file_id)
                    return True
                except:
                    return False
            
            def get_metadata(self, file_path: str) -> Dict[str, Any]:
                try:
                    bucket_name = file_path.split('/')[0] if '/' in file_path else 'default'
                    file_name = file_path.split('/', 1)[1] if '/' in file_path else file_path
                    bucket_id = self._get_bucket_id(bucket_name)
                    
                    file_id = file_name.replace('/', '_')
                    result = self.storage.get_file(bucket_id=bucket_id, file_id=file_id)
                    return {
                        'size': result['sizeOriginal'],
                        'mimeType': result['mimeType'],
                        'dateCreated': result['$createdAt'],
                        'dateUpdated': result['$updatedAt'],
                        'name': result['name']
                    }
                except Exception as e:
                    logger.error(f"Appwrite metadata failed for {file_path}", error=e, source="bucket_client")
                    raise
            
            def create_bucket(self, bucket_name: str) -> Dict[str, Any]:
                """Create a new bucket in Appwrite."""
                try:
                    # Generate a valid bucket ID (Appwrite has specific requirements)
                    bucket_id = f"bucket_{bucket_name.lower().replace('_', '-')}"
                    
                    result = self.storage.create_bucket(
                        bucket_id=bucket_id,
                        name=bucket_name
                    )
                    
                    # Cache the bucket
                    self._bucket_cache[bucket_name] = bucket_id
                    
                    return {
                        '$id': result['$id'],
                        'name': result['name'],
                        'status': 'created',
                        'backend': 'appwrite'
                    }
                except Exception as e:
                    logger.error(f"Appwrite bucket creation failed for {bucket_name}", error=e, source="bucket_client")
                    raise
            
            def delete_bucket(self, bucket_name: str) -> bool:
                """Delete a bucket from Appwrite."""
                try:
                    bucket_id = self._get_bucket_id(bucket_name)
                    self.storage.delete_bucket(bucket_id=bucket_id)
                    
                    # Remove from cache
                    if bucket_name in self._bucket_cache:
                        del self._bucket_cache[bucket_name]
                    
                    return True
                except Exception as e:
                    logger.error(f"Appwrite bucket deletion failed for {bucket_name}", error=e, source="bucket_client")
                    return False
            
            def list_buckets(self) -> List[Dict[str, Any]]:
                """List all buckets in Appwrite."""
                try:
                    result = self.storage.list_buckets()
                    buckets = []
                    for bucket in result.get('buckets', []):
                        buckets.append({
                            '$id': bucket['$id'],
                            'name': bucket['name'],
                            'backend': 'appwrite'
                        })
                    return buckets
                except Exception as e:
                    logger.error(f"Appwrite bucket listing failed", error=e, source="bucket_client")
                    return []
            
            def _ensure_bucket_exists(self, bucket_name: str) -> str:
                """Ensure bucket exists and return its ID."""
                if bucket_name in self._bucket_cache:
                    return self._bucket_cache[bucket_name]
                
                # Try to find existing bucket
                try:
                    buckets = self.list_buckets()
                    for bucket in buckets:
                        if bucket['name'] == bucket_name:
                            bucket_id = bucket['$id']
                            self._bucket_cache[bucket_name] = bucket_id
                            return bucket_id
                except:
                    pass
                
                # Create new bucket
                try:
                    result = self.create_bucket(bucket_name)
                    return result['$id']
                except Exception as e:
                    logger.error(f"Failed to ensure bucket exists: {bucket_name}", error=e, source="bucket_client")
                    raise
            
            def _get_bucket_id(self, bucket_name: str) -> str:
                """Get bucket ID for a bucket name."""
                if bucket_name in self._bucket_cache:
                    return self._bucket_cache[bucket_name]
                
                # Try to find the bucket
                try:
                    buckets = self.list_buckets()
                    for bucket in buckets:
                        if bucket['name'] == bucket_name:
                            bucket_id = bucket['$id']
                            self._bucket_cache[bucket_name] = bucket_id
                            return bucket_id
                except:
                    pass
                
                raise ValueError(f"Bucket not found: {bucket_name}")
        
        return AppwriteStorageBackend()
    
    def _create_s3_backend(self) -> StorageBackend:
        """Create S3 backend instance."""
        import boto3
        
        class S3StorageBackend(StorageBackend):
            def __init__(self):
                session = boto3.Session(
                    aws_access_key_id=S3_ACCESS_KEY_ID,
                    aws_secret_access_key=S3_SECRET_ACCESS_KEY,
                    region_name=S3_REGION
                )
                self.s3 = session.client('s3', endpoint_url=S3_ENDPOINT_URL)
                self.region = S3_REGION
                self._bucket_cache = set()  # Cache created buckets
            
            def upload(self, file_path: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
                try:
                    # Extract bucket name from file path
                    bucket_name = file_path.split('/')[0] if '/' in file_path else 'default'
                    key = file_path.split('/', 1)[1] if '/' in file_path else file_path
                    
                    # Ensure bucket exists
                    self._ensure_bucket_exists(bucket_name)
                    
                    s3_metadata = {}
                    if metadata:
                        s3_metadata = {k: str(v) for k, v in metadata.items() if k != 'mimeType'}
                    
                    self.s3.put_object(
                        Bucket=bucket_name,
                        Key=key,
                        Body=content,
                        ContentType=metadata.get('mimeType', 'application/octet-stream') if metadata else 'application/octet-stream',
                        Metadata=s3_metadata
                    )
                    
                    response = self.s3.head_object(Bucket=bucket_name, Key=key)
                    
                    return {
                        '$id': file_path,
                        'name': os.path.basename(file_path),
                        'path': file_path,
                        'size': response['ContentLength'],
                        'mimeType': response.get('ContentType', 'application/octet-stream'),
                        'dateCreated': response['LastModified'].isoformat(),
                        'dateUpdated': response['LastModified'].isoformat()
                    }
                except Exception as e:
                    logger.error(f"S3 upload failed for {file_path}", error=e, source="bucket_client")
                    raise
            
            def download(self, file_path: str) -> bytes:
                try:
                    bucket_name = file_path.split('/')[0] if '/' in file_path else 'default'
                    key = file_path.split('/', 1)[1] if '/' in file_path else file_path
                    
                    response = self.s3.get_object(Bucket=bucket_name, Key=key)
                    return response['Body'].read()
                except Exception as e:
                    logger.error(f"S3 download failed for {file_path}", error=e, source="bucket_client")
                    raise
            
            def delete(self, file_path: str) -> bool:
                try:
                    bucket_name = file_path.split('/')[0] if '/' in file_path else 'default'
                    key = file_path.split('/', 1)[1] if '/' in file_path else file_path
                    
                    self.s3.delete_object(Bucket=bucket_name, Key=key)
                    return True
                except Exception as e:
                    logger.error(f"S3 delete failed for {file_path}", error=e, source="bucket_client")
                    return False
            
            def list_files(self, folder: str = "") -> List[Dict[str, Any]]:
                try:
                    if folder:
                        bucket_name = folder.split('/')[0]
                        prefix = folder.split('/', 1)[1] if '/' in folder else ""
                    else:
                        # List files from all buckets
                        all_files = []
                        for bucket_name in self._bucket_cache:
                            try:
                                paginator = self.s3.get_paginator('list_objects_v2')
                                pages = paginator.paginate(Bucket=bucket_name)
                                
                                for page in pages:
                                    for obj in page.get('Contents', []):
                                        all_files.append({
                                            '$id': obj['Key'],
                                            'name': f"{bucket_name}/{os.path.basename(obj['Key'])}",
                                            'size': obj['Size'],
                                            'mimeType': 'application/octet-stream',
                                            'dateCreated': obj['LastModified'].isoformat(),
                                            'dateUpdated': obj['LastModified'].isoformat()
                                        })
                            except:
                                continue
                        return all_files
                    
                    paginator = self.s3.get_paginator('list_objects_v2')
                    pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
                    
                    files = []
                    for page in pages:
                        for obj in page.get('Contents', []):
                            files.append({
                                '$id': obj['Key'],
                                'name': f"{bucket_name}/{os.path.basename(obj['Key'])}",
                                'size': obj['Size'],
                                'mimeType': 'application/octet-stream',
                                'dateCreated': obj['LastModified'].isoformat(),
                                'dateUpdated': obj['LastModified'].isoformat()
                            })
                    return files
                except Exception as e:
                    logger.error(f"S3 list failed for folder {folder}", error=e, source="bucket_client")
                    return []
            
            def exists(self, file_path: str) -> bool:
                try:
                    bucket_name = file_path.split('/')[0] if '/' in file_path else 'default'
                    key = file_path.split('/', 1)[1] if '/' in file_path else file_path
                    
                    self.s3.head_object(Bucket=bucket_name, Key=key)
                    return True
                except:
                    return False
            
            def get_metadata(self, file_path: str) -> Dict[str, Any]:
                try:
                    bucket_name = file_path.split('/')[0] if '/' in file_path else 'default'
                    key = file_path.split('/', 1)[1] if '/' in file_path else file_path
                    
                    response = self.s3.head_object(Bucket=bucket_name, Key=key)
                    return {
                        'size': response['ContentLength'],
                        'mimeType': response.get('ContentType', 'application/octet-stream'),
                        'dateCreated': response['LastModified'].isoformat(),
                        'dateUpdated': response['LastModified'].isoformat(),
                        'name': os.path.basename(file_path),
                        'metadata': response.get('Metadata', {})
                    }
                except Exception as e:
                    logger.error(f"S3 metadata failed for {file_path}", error=e, source="bucket_client")
                    raise
            
            def create_bucket(self, bucket_name: str) -> Dict[str, Any]:
                """Create a new S3 bucket."""
                try:
                    if self.region == 'us-east-1':
                        # us-east-1 doesn't require LocationConstraint
                        self.s3.create_bucket(Bucket=bucket_name)
                    else:
                        self.s3.create_bucket(
                            Bucket=bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.region}
                        )
                    
                    # Add to cache
                    self._bucket_cache.add(bucket_name)
                    
                    return {
                        '$id': bucket_name,
                        'name': bucket_name,
                        'status': 'created',
                        'backend': 's3'
                    }
                except Exception as e:
                    logger.error(f"S3 bucket creation failed for {bucket_name}", error=e, source="bucket_client")
                    raise
            
            def delete_bucket(self, bucket_name: str) -> bool:
                """Delete an S3 bucket."""
                try:
                    # First, delete all objects in the bucket
                    paginator = self.s3.get_paginator('list_objects_v2')
                    pages = paginator.paginate(Bucket=bucket_name)
                    
                    for page in pages:
                        objects = page.get('Contents', [])
                        if objects:
                            delete_keys = [{'Key': obj['Key']} for obj in objects]
                            self.s3.delete_objects(
                                Bucket=bucket_name,
                                Delete={'Objects': delete_keys}
                            )
                    
                    # Then delete the bucket
                    self.s3.delete_bucket(Bucket=bucket_name)
                    
                    # Remove from cache
                    self._bucket_cache.discard(bucket_name)
                    
                    return True
                except Exception as e:
                    logger.error(f"S3 bucket deletion failed for {bucket_name}", error=e, source="bucket_client")
                    return False
            
            def list_buckets(self) -> List[Dict[str, Any]]:
                """List all S3 buckets."""
                try:
                    response = self.s3.list_buckets()
                    buckets = []
                    for bucket in response.get('Buckets', []):
                        bucket_name = bucket['Name']
                        buckets.append({
                            '$id': bucket_name,
                            'name': bucket_name,
                            'backend': 's3',
                            'dateCreated': bucket['CreationDate'].isoformat()
                        })
                        # Add to cache
                        self._bucket_cache.add(bucket_name)
                    return buckets
                except Exception as e:
                    logger.error(f"S3 bucket listing failed", error=e, source="bucket_client")
                    return []
            
            def _ensure_bucket_exists(self, bucket_name: str):
                """Ensure bucket exists, create if it doesn't."""
                if bucket_name in self._bucket_cache:
                    return
                
                try:
                    # Check if bucket exists
                    self.s3.head_bucket(Bucket=bucket_name)
                    self._bucket_cache.add(bucket_name)
                except:
                    # Bucket doesn't exist, create it
                    try:
                        self.create_bucket(bucket_name)
                    except Exception as e:
                        logger.error(f"Failed to ensure S3 bucket exists: {bucket_name}", error=e, source="bucket_client")
                        raise
        
        return S3StorageBackend()
    
    def _execute_strategy(self, operation: str, *args, **kwargs) -> Any:
        """Execute operation based on configured strategy."""
        if self.strategy == "primary":
            return self._execute_primary(operation, *args, **kwargs)
        elif self.strategy == "replica":
            return self._execute_replica(operation, *args, **kwargs)
        elif self.strategy == "failover":
            return self._execute_failover(operation, *args, **kwargs)
        elif self.strategy == "sync":
            return self._execute_sync(operation, *args, **kwargs)
        else:
            logger.warning(f"Unknown strategy {self.strategy}, falling back to primary", source="bucket_client")
            return self._execute_primary(operation, *args, **kwargs)
    
    def _execute_primary(self, operation: str, *args, **kwargs) -> Any:
        """Execute operation on primary backend only."""
        if not self.primary_backend:
            raise ValueError("No primary backend available")
        
        method = getattr(self.primary_backend, operation)
        return method(*args, **kwargs)
    
    def _execute_replica(self, operation: str, *args, **kwargs) -> Any:
        """Execute write operations on all backends, read operations on primary."""
        write_operations = {'upload', 'delete'}
        
        if operation in write_operations:
            # Write to all backends
            results = []
            errors = []
            
            for i, backend in enumerate(self.backends):
                try:
                    method = getattr(backend, operation)
                    result = method(*args, **kwargs)
                    results.append(result)
                    logger.debug(f"Replica write success on backend {i}", source="bucket_client")
                except Exception as e:
                    errors.append(f"Backend {i}: {str(e)}")
                    logger.error(f"Replica write failed on backend {i}", error=e, source="bucket_client")
            
            if not results:
                raise Exception(f"All replica writes failed: {errors}")
            
            return results[0]  # Return primary result
        else:
            # Read from primary
            return self._execute_primary(operation, *args, **kwargs)
    
    def _execute_failover(self, operation: str, *args, **kwargs) -> Any:
        """Execute operation with automatic failover to backup backends."""
        for i, backend in enumerate(self.backends):
            try:
                method = getattr(backend, operation)
                result = method(*args, **kwargs)
                if i > 0:
                    logger.info(f"Failover successful to backend {i}", source="bucket_client")
                return result
            except Exception as e:
                logger.warning(f"Backend {i} failed, trying next", error=e, source="bucket_client")
                if i == len(self.backends) - 1:
                    raise Exception(f"All backends failed for operation {operation}")
        
        raise Exception("No backends available")
    
    def _execute_sync(self, operation: str, *args, **kwargs) -> Any:
        """Execute operation on all backends and ensure consistency."""
        write_operations = {'upload', 'delete'}
        
        if operation in write_operations:
            # Write to all backends and verify consistency
            results = []
            errors = []
            
            for i, backend in enumerate(self.backends):
                try:
                    method = getattr(backend, operation)
                    result = method(*args, **kwargs)
                    results.append(result)
                except Exception as e:
                    errors.append(f"Backend {i}: {str(e)}")
                    logger.error(f"Sync write failed on backend {i}", error=e, source="bucket_client")
            
            if len(results) != len(self.backends):
                logger.warning(f"Sync inconsistency: {len(results)}/{len(self.backends)} succeeded", source="bucket_client")
            
            if not results:
                raise Exception(f"All sync writes failed: {errors}")
            
            return results[0]  # Return first successful result
        else:
            # Read from primary with verification
            return self._execute_primary(operation, *args, **kwargs)
    
    def upload_file(self, file_path: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Upload file content to storage using configured strategy.
        
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
        return self._execute_strategy('upload', file_path, content, metadata)
    
    def download_file(self, file_path: str) -> bytes:
        """
        Download file content from storage.
        
        Parameters
        ----------
        file_path : str
            Path to file to download
            
        Returns
        -------
        bytes
            File content as bytes
        """
        return self._execute_strategy('download', file_path)
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete file from storage using configured strategy.
        
        Parameters
        ----------
        file_path : str
            Path to file to delete
            
        Returns
        -------
        bool
            True if file was deleted successfully
        """
        return self._execute_strategy('delete', file_path)
    
    def list_files(self, folder: str = "") -> List[Dict[str, Any]]:
        """
        List files in storage folder.
        
        Parameters
        ----------
        folder : str, optional
            Folder path to list files from
            
        Returns
        -------
        list
            List of file information dictionaries
        """
        return self._execute_strategy('list_files', folder)
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if file exists in storage.
        
        Parameters
        ----------
        file_path : str
            Path to check
            
        Returns
        -------
        bool
            True if file exists
        """
        return self._execute_strategy('exists', file_path)
    
    def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Get file metadata from storage.
        
        Parameters
        ----------
        file_path : str
            Path to file
            
        Returns
        -------
        dict
            File metadata including size, timestamps, MIME type
        """
        return self._execute_strategy('get_metadata', file_path)
    
    def get_storage_info(self) -> Dict[str, Any]:
        """
        Get information about active storage backends and strategy.
        
        Returns
        -------
        dict
            Storage configuration information
        """
        return {
            'strategy': self.strategy,
            'backends': [type(backend).__name__ for backend in self.backends],
            'primary_backend': type(self.primary_backend).__name__ if self.primary_backend else None,
            'backend_count': len(self.backends),
            'active_backends': STORAGE_BACKENDS_ACTIVE,
            'appwrite_enabled': APPWRITE_ENABLED,
            's3_enabled': S3_ENABLED
        }
    
    def create_bucket(self, bucket_name: str) -> Dict[str, Any]:
        """
        Create a new bucket/container using configured strategy.
        
        Parameters
        ----------
        bucket_name : str
            Name of the bucket to create
            
        Returns
        -------
        dict
            Bucket creation result
        """
        return self._execute_strategy('create_bucket', bucket_name)
    
    def delete_bucket(self, bucket_name: str) -> bool:
        """
        Delete a bucket/container using configured strategy.
        
        Parameters
        ----------
        bucket_name : str
            Name of the bucket to delete
            
        Returns
        -------
        bool
            True if bucket was deleted successfully
        """
        return self._execute_strategy('delete_bucket', bucket_name)
    
    def list_buckets(self) -> List[Dict[str, Any]]:
        """
        List all buckets/containers.
        
        Returns
        -------
        list
            List of bucket information dictionaries
        """
        return self._execute_strategy('list_buckets')


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
