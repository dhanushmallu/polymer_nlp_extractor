# polymer_extractor/storage/bucket_manager.py

"""
BucketManager for Polymer NLP Extractor.

Provides a high-level abstraction over universal storage backends:
- Local filesystem storage
- Appwrite cloud storage
- S3-compatible storage

All operations log for traceability and support multiple storage backends.
"""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from polymer_extractor.storage.bucket_client import get_bucket_client
from polymer_extractor.utils.logging import Logger

logger = Logger()


class BucketManager:
    """
    High-level manager for universal storage operations.

    Attributes
    ----------
    client : BucketClient
        Universal storage client instance.

    Methods
    -------
    upload_file(file_path, content, metadata=None)
        Upload a file to storage.
    download_file(file_path)
        Download a file from storage.
    delete_file(file_path)
        Delete a file from storage.
    list_files(folder="")
        List all files in a storage folder.
    file_exists(file_path)
        Check if a file exists in storage.
    get_file_metadata(file_path)
        Get file metadata from storage.
    """

    def __init__(self):
        """
        Initialize the BucketManager with a universal storage client.
        """
        self.client = get_bucket_client()
        logger.info(f"BucketManager initialized with {self.client.get_backend_type()} backend",
                   source="bucket_manager", event_type="startup")

    # === FILE OPERATIONS ===
    def upload_file(self, file_path: str, content: Union[bytes, str], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Upload a file to storage.

        Parameters
        ----------
        file_path : str
            Path where file should be stored.
        content : bytes or str
            File content. If str, will be encoded as UTF-8.
        metadata : dict, optional
            Additional metadata to store with file.

        Returns
        -------
        dict
            File information including ID, size, timestamps.

        Raises
        ------
        Exception
            If the upload fails.
        """
        try:
            # Convert string content to bytes if needed
            if isinstance(content, str):
                content = content.encode('utf-8')
                if metadata is None:
                    metadata = {}
                metadata.setdefault('encoding', 'utf-8')
            
            result = self.client.upload_file(file_path, content, metadata)
            logger.info(f"Uploaded file to {file_path}",
                       source="bucket_manager", event_type="upload_file")
            return result
        except Exception as e:
            logger.error(f"Failed to upload file to {file_path}",
                        source="bucket_manager", error=e, event_type="upload_file")
            raise

    def upload_file_from_path(self, source_path: str, dest_path: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Upload a file from local filesystem to storage.

        Parameters
        ----------
        source_path : str
            Path to local file to upload.
        dest_path : str
            Destination path in storage.
        metadata : dict, optional
            Additional metadata to store with file.

        Returns
        -------
        dict
            File information including ID, size, timestamps.

        Raises
        ------
        FileNotFoundError
            If the source file does not exist.
        Exception
            If the upload fails.
        """
        try:
            if not os.path.exists(source_path):
                raise FileNotFoundError(f"Source file not found: {source_path}")
            
            with open(source_path, 'rb') as f:
                content = f.read()
            
            # Add file information to metadata
            if metadata is None:
                metadata = {}
            metadata.update({
                'original_name': os.path.basename(source_path),
                'source_path': source_path
            })
            
            return self.upload_file(dest_path, content, metadata)
        except Exception as e:
            logger.error(f"Failed to upload file from {source_path} to {dest_path}",
                        source="bucket_manager", error=e, event_type="upload_file_from_path")
            raise

    def download_file(self, file_path: str) -> bytes:
        """
        Download a file from storage.

        Parameters
        ----------
        file_path : str
            Path to file in storage.

        Returns
        -------
        bytes
            File content as bytes.

        Raises
        ------
        Exception
            If the download fails.
        """
        try:
            content = self.client.download_file(file_path)
            logger.info(f"Downloaded file from {file_path}",
                       source="bucket_manager", event_type="download_file")
            return content
        except Exception as e:
            logger.error(f"Failed to download file from {file_path}",
                        source="bucket_manager", error=e, event_type="download_file")
            raise

    def download_file_to_path(self, file_path: str, dest_path: str) -> bool:
        """
        Download a file from storage to local filesystem.

        Parameters
        ----------
        file_path : str
            Path to file in storage.
        dest_path : str
            Local path where file should be saved.

        Returns
        -------
        bool
            True if download was successful.

        Raises
        ------
        Exception
            If the download fails.
        """
        try:
            content = self.download_file(file_path)
            
            # Create destination directory if it doesn't exist
            dest_dir = os.path.dirname(dest_path)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)
            
            with open(dest_path, 'wb') as f:
                f.write(content)
            
            logger.info(f"Downloaded file from {file_path} to {dest_path}",
                       source="bucket_manager", event_type="download_file_to_path")
            return True
        except Exception as e:
            logger.error(f"Failed to download file from {file_path} to {dest_path}",
                        source="bucket_manager", error=e, event_type="download_file_to_path")
            raise

    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file from storage.

        Parameters
        ----------
        file_path : str
            Path to file in storage.

        Returns
        -------
        bool
            True if file was deleted successfully.

        Raises
        ------
        Exception
            If the deletion fails.
        """
        try:
            result = self.client.delete_file(file_path)
            if result:
                logger.info(f"Deleted file {file_path}",
                           source="bucket_manager", event_type="delete_file")
            else:
                logger.warning(f"File {file_path} was not found for deletion",
                              source="bucket_manager", event_type="delete_file")
            return result
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}",
                        source="bucket_manager", error=e, event_type="delete_file")
            raise

    def list_files(self, folder: str = "") -> List[Dict[str, Any]]:
        """
        List all files in a storage folder.

        Parameters
        ----------
        folder : str, optional
            Folder path to list (empty for root).

        Returns
        -------
        list
            List of file information dictionaries.

        Raises
        ------
        Exception
            If the listing fails.
        """
        try:
            files = self.client.list_files(folder)
            logger.debug(f"Listed {len(files)} files in folder '{folder}'",
                        source="bucket_manager", event_type="list_files")
            return files
        except Exception as e:
            logger.error(f"Failed to list files in folder '{folder}'",
                        source="bucket_manager", error=e, event_type="list_files")
            raise

    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in storage.

        Parameters
        ----------
        file_path : str
            Path to file in storage.

        Returns
        -------
        bool
            True if file exists.
        """
        try:
            exists = self.client.file_exists(file_path)
            logger.debug(f"File {file_path} exists: {exists}",
                        source="bucket_manager", event_type="file_exists")
            return exists
        except Exception as e:
            logger.error(f"Failed to check if file {file_path} exists",
                        source="bucket_manager", error=e, event_type="file_exists")
            # Return False on error rather than raising
            return False

    def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Get file metadata from storage.

        Parameters
        ----------
        file_path : str
            Path to file in storage.

        Returns
        -------
        dict
            File metadata including size, timestamps, etc.

        Raises
        ------
        Exception
            If getting metadata fails.
        """
        try:
            metadata = self.client.get_file_metadata(file_path)
            logger.debug(f"Retrieved metadata for file {file_path}",
                        source="bucket_manager", event_type="get_file_metadata")
            return metadata
        except Exception as e:
            logger.error(f"Failed to get metadata for file {file_path}",
                        source="bucket_manager", error=e, event_type="get_file_metadata")
            raise

    def get_backend_type(self) -> str:
        """
        Get the current storage backend type.

        Returns
        -------
        str
            Backend type (local, appwrite, s3).
        """
        return self.client.get_backend_type()

    def test_connection(self) -> bool:
        """
        Test storage backend connection.

        Returns
        -------
        bool
            True if connection is working.
        """
        try:
            result = self.client.test_connection()
            logger.info(f"Storage connection test: {'passed' if result else 'failed'}",
                       source="bucket_manager", event_type="test_connection")
            return result
        except Exception as e:
            logger.error("Storage connection test failed",
                        source="bucket_manager", error=e, event_type="test_connection")
            return False

    # === LEGACY COMPATIBILITY METHODS ===
    # These methods provide backward compatibility with the old Appwrite-specific interface
    
    def create_bucket(self, bucket_id: str, name: str, file_security: bool = False) -> dict:
        """
        Legacy method for backward compatibility.
        
        Note: With universal storage, bucket creation is handled automatically.
        This method now returns a success status for compatibility.
        """
        logger.warning("create_bucket() is deprecated. Universal storage handles bucket creation automatically.",
                      source="bucket_manager")
        return {"$id": bucket_id, "status": "auto_managed", "name": name}

    def delete_bucket(self, bucket_id: str) -> bool:
        """
        Legacy method for backward compatibility.
        
        Note: With universal storage, bucket deletion is not supported.
        This method now returns False for compatibility.
        """
        logger.warning("delete_bucket() is deprecated. Universal storage does not support bucket deletion.",
                      source="bucket_manager")
        return False

    def get_bucket(self, bucket_id: str) -> dict:
        """
        Legacy method for backward compatibility.
        
        Note: With universal storage, bucket information is abstracted away.
        This method now returns a generic bucket info for compatibility.
        """
        logger.warning("get_bucket() is deprecated. Universal storage abstracts bucket details.",
                      source="bucket_manager")
        return {
            "$id": bucket_id,
            "name": bucket_id,
            "fileSecurity": False,
            "backend": self.get_backend_type()
        }

    def list_buckets(self) -> list:
        """
        Legacy method for backward compatibility.
        
        Note: With universal storage, bucket listing is not applicable.
        This method now returns a single default bucket for compatibility.
        """
        logger.warning("list_buckets() is deprecated. Universal storage uses a single logical bucket.",
                      source="bucket_manager")
        return [
            {
                "$id": "default",
                "name": "Default Storage",
                "backend": self.get_backend_type()
            }
        ]
