# polymer_extractor/storage/bucket_manager.py

"""
BucketManager for Polymer NLP Extractor.

Provides a high-level abstraction over Appwrite's Storage API:
- Manage buckets (create, fetch, list, delete)
- Manage files (upload, download, list, delete)

All operations log to both local and Appwrite logs for traceability.
"""

import os
from appwrite.id import ID
from appwrite.input_file import InputFile
from appwrite.exception import AppwriteException
from polymer_extractor.storage.appwrite_client import get_storage_service
from polymer_extractor.utils.logging import Logger

logger = Logger()


class BucketManager:
    """
    High-level manager for Appwrite storage buckets and files.

    Attributes
    ----------
    storage : appwrite.services.storage.Storage
        Appwrite Storage service instance.

    Methods
    -------
    create_bucket(bucket_id, name, file_security=False)
        Create a new bucket if it does not already exist.
    delete_bucket(bucket_id)
        Delete a bucket by its ID.
    get_bucket(bucket_id)
        Retrieve details of a bucket.
    list_buckets()
        List all buckets in the project.
    upload_file(bucket_id, file_path, file_id=None)
        Upload a file to a bucket.
    download_file(bucket_id, file_id, dest_path)
        Download a file from a bucket.
    delete_file(bucket_id, file_id)
        Delete a file from a bucket.
    list_files(bucket_id)
        List all files in a bucket.
    """

    def __init__(self):
        """
        Initialize the BucketManager with an authenticated Appwrite Storage service.
        """
        self.storage = get_storage_service()

    # === BUCKET OPERATIONS ===
    def create_bucket(self, bucket_id: str, name: str, file_security: bool = False) -> dict:
        """
        Create a new bucket in Appwrite if it does not already exist.

        Parameters
        ----------
        bucket_id : str
            Unique identifier for the bucket.
        name : str
            Human-readable name for the bucket.
        file_security : bool, optional
            Enable file-level security. Defaults to False.

        Returns
        -------
        dict
            Bucket details.

        Raises
        ------
        AppwriteException
            If the API call fails.
        """
        try:
            self.get_bucket(bucket_id)
            logger.debug(f"Bucket '{bucket_id}' already exists. Skipping creation.",
                         source="bucket_manager", event_type="create_bucket")
            return {"$id": bucket_id, "status": "exists"}
        except AppwriteException as e:
            if e.code == 404:
                result = self.storage.create_bucket(
                    bucket_id=bucket_id,
                    name=name,
                    file_security=file_security
                )
                logger.info(f"Created bucket '{bucket_id}'",
                            source="bucket_manager", event_type="create_bucket")
                return result
            else:
                logger.error(f"Failed to create bucket '{bucket_id}'",
                             source="bucket_manager", error=e, event_type="create_bucket")
                raise

    def delete_bucket(self, bucket_id: str) -> None:
        """
        Delete an existing bucket by its ID.

        Parameters
        ----------
        bucket_id : str
            Unique identifier of the bucket to delete.

        Raises
        ------
        AppwriteException
            If the API call fails.
        """
        try:
            self.storage.delete_bucket(bucket_id)
            logger.warning(f"Deleted bucket '{bucket_id}'",
                           source="bucket_manager", event_type="delete_bucket")
        except AppwriteException as e:
            logger.error(f"Failed to delete bucket '{bucket_id}'",
                         source="bucket_manager", error=e, event_type="delete_bucket")
            raise

    def get_bucket(self, bucket_id: str) -> dict:
        """
        Retrieve details of a specific bucket.

        Parameters
        ----------
        bucket_id : str
            Unique identifier of the bucket.

        Returns
        -------
        dict
            Bucket details.

        Raises
        ------
        AppwriteException
            If the API call fails.
        """
        try:
            result = self.storage.get_bucket(bucket_id)
            logger.debug(f"Fetched bucket '{bucket_id}'",
                         source="bucket_manager", event_type="get_bucket")
            return result
        except AppwriteException as e:
            logger.error(f"Failed to fetch bucket '{bucket_id}'",
                         source="bucket_manager", error=e, event_type="get_bucket")
            raise

    def list_buckets(self) -> list:
        """
        List all buckets in the Appwrite project.

        Returns
        -------
        list
            List of bucket objects.

        Raises
        ------
        AppwriteException
            If the API call fails.
        """
        try:
            response = self.storage.list_buckets()
            logger.debug("Listed all buckets",
                         source="bucket_manager", event_type="list_buckets")
            return response['buckets']
        except AppwriteException as e:
            logger.error("Failed to list buckets",
                         source="bucket_manager", error=e, event_type="list_buckets")
            raise

    # === FILE OPERATIONS ===
    def upload_file(self, bucket_id: str, file_path: str, file_id: str = None) -> dict:
        """
        Upload a file to a specific bucket.

        Parameters
        ----------
        bucket_id : str
            ID of the bucket to upload the file to.
        file_path : str
            Path to the local file.
        file_id : str, optional
            Custom file ID. If None, a unique ID is generated.

        Returns
        -------
        dict
            Details of the uploaded file.

        Raises
        ------
        AppwriteException
            If the API call fails.
        """
        try:
            fid = file_id or ID.unique()
            input_file = InputFile.from_path(file_path)
            result = self.storage.create_file(
                bucket_id=bucket_id,
                file_id=fid,
                file=input_file
            )
            logger.info(f"Uploaded file '{os.path.basename(file_path)}' to bucket '{bucket_id}'",
                        source="bucket_manager", event_type="upload_file")
            return result
        except AppwriteException as e:
            logger.error(f"Failed to upload file '{file_path}' to bucket '{bucket_id}'",
                         source="bucket_manager", error=e, event_type="upload_file")
            raise

    def download_file(self, bucket_id: str, file_id: str, dest_path: str) -> None:
        """
        Download a file from a bucket to a local path.

        Parameters
        ----------
        bucket_id : str
            ID of the bucket containing the file.
        file_id : str
            ID of the file to download.
        dest_path : str
            Local path to save the downloaded file.

        Raises
        ------
        AppwriteException
            If the API call fails.
        """
        try:
            response = self.storage.get_file_download(bucket_id, file_id)
            with open(dest_path, 'wb') as f:
                f.write(response)
            logger.info(f"Downloaded file '{file_id}' from bucket '{bucket_id}' to '{dest_path}'",
                        source="bucket_manager", event_type="download_file")
        except AppwriteException as e:
            logger.error(f"Failed to download file '{file_id}' from bucket '{bucket_id}'",
                         source="bucket_manager", error=e, event_type="download_file")
            raise

    def delete_file(self, bucket_id: str, file_id: str) -> None:
        """
        Delete a file from a bucket.

        Parameters
        ----------
        bucket_id : str
            ID of the bucket.
        file_id : str
            ID of the file to delete.

        Raises
        ------
        AppwriteException
            If the API call fails.
        """
        try:
            self.storage.delete_file(bucket_id, file_id)
            logger.warning(f"Deleted file '{file_id}' from bucket '{bucket_id}'",
                           source="bucket_manager", event_type="delete_file")
        except AppwriteException as e:
            logger.error(f"Failed to delete file '{file_id}' from bucket '{bucket_id}'",
                         source="bucket_manager", error=e, event_type="delete_file")
            raise


    # === Get File by ID ===
    def get_file(self, bucket_id: str, file_id: str) -> dict:
        """
        Retrieve details of a specific file in a bucket.

        Parameters
        ----------
        bucket_id : str
            ID of the bucket.
        file_id : str
            ID of the file.

        Returns
        -------
        dict
            File details.

        Raises
        ------
        AppwriteException
            If the API call fails.
        """
        try:
            result = self.storage.get_file(bucket_id, file_id)
            logger.debug(f"Fetched file '{file_id}' from bucket '{bucket_id}'",
                         source="bucket_manager", event_type="get_file")
            return result
        except AppwriteException as e:
            logger.error(f"Failed to fetch file '{file_id}' from bucket '{bucket_id}'",
                         source="bucket_manager", error=e, event_type="get_file")
            raise


    # === Get file id from file name ===
    def get_file_url(self, bucket_id: str, file_name: str) -> str:
        """
        Retrieve the file ID by its name in a specific bucket.

        Parameters
        ----------
        bucket_id : str
            ID of the bucket.
        file_name : str
            Name of the file to search for.

        Returns
        -------
        str
            File ID if found, otherwise None.

        Raises
        ------
        AppwriteException
            If the API call fails.
        """
        try:
            files = self.list_files(bucket_id)
            for file in files:
                if file['name'] == file_name:
                    logger.debug(f"Found file '{file_name}' with ID '{file['$id']}'",
                                 source="bucket_manager", event_type="get_file_id_by_name")
                    return file['$id']
            logger.warning(f"File '{file_name}' not found in bucket '{bucket_id}'",
                           source="bucket_manager", event_type="get_file_id_by_name")
            return None
        except AppwriteException as e:
            logger.error(f"Failed to get file ID for '{file_name}' in bucket '{bucket_id}'",
                         source="bucket_manager", error=e, event_type="get_file_id_by_name")
            raise

    def list_files(self, bucket_id: str) -> list:
        """
        List all files in a specific bucket.

        Parameters
        ----------
        bucket_id : str
            ID of the bucket.

        Returns
        -------
        list
            List of file objects.

        Raises
        ------
        AppwriteException
            If the API call fails.
        """
        try:
            response = self.storage.list_files(bucket_id)
            logger.debug(f"Listed files in bucket '{bucket_id}'",
                         source="bucket_manager", event_type="list_files")
            return response['files']
        except AppwriteException as e:
            logger.error(f"Failed to list files in bucket '{bucket_id}'",
                         source="bucket_manager", error=e, event_type="list_files")
            raise
