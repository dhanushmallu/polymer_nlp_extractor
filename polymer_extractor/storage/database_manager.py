"""
DatabaseManager for Polymer NLP Extractor.

Provides high-level abstraction for Appwrite Databases API:
- Manage collections and attributes
- CRUD operations on documents

Methods
-------
create_collection(collection_id: str, name: str, document_security: bool = False) -> dict
    Create a new collection.

delete_collection(collection_id: str) -> None
    Delete a collection by its ID.

get_collection(collection_id: str) -> dict
    Fetch details of a collection.

list_collections() -> list
    List all collections in the database.

create_attribute(collection_id: str, attr_type: str, key: str, **kwargs) -> dict
    Create an attribute of any supported type in a collection.

delete_attribute(collection_id: str, key: str) -> None
    Delete an attribute from a collection.

create_document(collection_id: str, data: dict, document_id: str = None) -> dict
    Create a document in a collection.

get_document(collection_id: str, document_id: str) -> dict
    Fetch a document by ID.

update_document(collection_id: str, document_id: str, data: dict) -> dict
    Update an existing document.

delete_document(collection_id: str, document_id: str) -> None
    Delete a document by ID.

list_documents(collection_id: str, queries: list = None) -> list
    List all documents in a collection.
"""

# polymer_extractor/storage/database_manager.py

from appwrite.exception import AppwriteException
from appwrite.id import ID

from polymer_extractor.storage.appwrite_client import get_database_service, get_database_id
from polymer_extractor.utils.logging import Logger

logger = Logger()


class DatabaseManager:
    """
    High-level abstraction for Appwrite database operations.
    """

    def __init__(self):
        self.db = get_database_service()
        self.database_id = get_database_id()

    # === COLLECTION OPERATIONS ===
    def create_collection(self, collection_id: str, name: str, document_security: bool = False) -> dict:
        """
        Create a new collection.

        Parameters
        ----------
        collection_id : str
            Unique collection identifier.
        name : str
            Human-readable collection name.
        document_security : bool, optional
            Enable document-level permissions. Defaults to False.

        Returns
        -------
        dict
            Created collection details.
        """
        try:
            # Check existence
            self.get_collection(collection_id)
            logger.debug(f"Collection '{collection_id}' already exists. Skipping creation.",
                         source="database_manager", event_type="create_collection")
            return {"$id": collection_id, "status": "exists"}
        except AppwriteException as e:
            if e.code == 404:
                # Create only if not found
                result = self.db.create_collection(
                    database_id=self.database_id,
                    collection_id=collection_id,
                    name=name,
                    document_security=document_security
                )
                logger.info(f"Created collection '{collection_id}'",
                            source="database_manager", event_type="create_collection")
                return result
            else:
                logger.error(f"Failed to create collection '{collection_id}'",
                             source="database_manager", error=e, event_type="create_collection")
                raise

    def delete_collection(self, collection_id: str) -> None:
        """
        Delete a collection by its ID.

        Parameters
        ----------
        collection_id : str
            Unique collection identifier.
        """
        try:
            self.db.delete_collection(self.database_id, collection_id)
            logger.warning(f"Deleted collection '{collection_id}'", source="database_manager",
                           event_type="delete_collection")
        except AppwriteException as e:
            logger.error(f"Failed to delete collection '{collection_id}'", source="database_manager", error=e,
                         event_type="delete_collection")
            raise

    def get_collection(self, collection_id: str) -> dict:
        """
        Fetch details of a collection.

        Parameters
        ----------
        collection_id : str
            Unique collection identifier.

        Returns
        -------
        dict
            Collection details.
        """
        try:
            result = self.db.get_collection(self.database_id, collection_id)
            logger.debug(f"Fetched collection '{collection_id}'", source="database_manager",
                         event_type="get_collection")
            return result
        except AppwriteException as e:
            logger.error(f"Failed to fetch collection '{collection_id}'", source="database_manager", error=e,
                         event_type="get_collection")
            raise

    def list_collections(self) -> list:
        """
        List all collections in the database.

        Returns
        -------
        list
            List of collections.
        """
        try:
            response = self.db.list_collections(self.database_id)
            logger.debug("Listed all collections", source="database_manager", event_type="list_collections")
            return response['collections']
        except AppwriteException as e:
            logger.error("Failed to list collections", source="database_manager", error=e,
                         event_type="list_collections")
            raise

    # === ATTRIBUTE OPERATIONS ===
    def create_attribute(self, collection_id: str, attr_type: str, key: str, **kwargs) -> dict:
        """
        Create an attribute of any supported type in a collection.

        Parameters
        ----------
        collection_id : str
            Target collection ID.
        attr_type : str
            Attribute type ('string', 'integer', 'float', 'boolean', 'datetime', 'enum', 'ip', 'email', 'url', 'relationship').
        key : str
            Attribute key (name).
        kwargs : dict
            Additional parameters required for the attribute type.

        Returns
        -------
        dict
            Created attribute details.

        Raises
        ------
        ValueError
            If the attribute type is not supported.
        AppwriteException
            If API call fails.
        """
        try:
            # Check if attribute exists
            collection = self.get_collection(collection_id)
            if any(attr['key'] == key for attr in collection['attributes']):
                logger.debug(f"Attribute '{key}' already exists in '{collection_id}'. Skipping creation.",
                             source="database_manager", event_type="create_attribute")
                return {"key": key, "status": "exists"}

            # Create attribute if not found
            method = getattr(self.db, f"create_{attr_type}_attribute", None)
            if not method:
                raise ValueError(f"Unsupported attribute type: {attr_type}")

            result = method(
                database_id=self.database_id,
                collection_id=collection_id,
                key=key,
                **kwargs
            )
            logger.info(f"Created {attr_type} attribute '{key}' in '{collection_id}'",
                        source="database_manager", event_type="create_attribute")
            return result
        except AppwriteException as e:
            logger.error(f"Failed to create {attr_type} attribute '{key}' in '{collection_id}'",
                         source="database_manager", error=e, event_type="create_attribute")
            raise

    def delete_attribute(self, collection_id: str, key: str) -> None:
        """
        Delete an attribute from a collection.

        Parameters
        ----------
        collection_id : str
            Target collection ID.
        key : str
            Attribute key (name).
        """
        try:
            self.db.delete_attribute(self.database_id, collection_id, key)
            logger.warning(f"Deleted attribute '{key}' from '{collection_id}'", source="database_manager",
                           event_type="delete_attribute")
        except AppwriteException as e:
            logger.error(f"Failed to delete attribute '{key}' from '{collection_id}'", source="database_manager",
                         error=e, event_type="delete_attribute")
            raise

    # === DOCUMENT OPERATIONS ===
    def create_document(self, collection_id: str, data: dict, document_id: str = None) -> dict:
        """
        Create a document in a collection.

        Parameters
        ----------
        collection_id : str
            Target collection ID.
        data : dict
            Document data.
        document_id : str, optional
            Unique document ID. Defaults to None.

        Returns
        -------
        dict
            Created document details.
        """
        try:
            doc_id = document_id or ID.unique()
            result = self.db.create_document(
                database_id=self.database_id,
                collection_id=collection_id,
                document_id=doc_id,
                data=data
            )
            logger.info(f"Created document in '{collection_id}': {doc_id}", source="database_manager",
                        event_type="create_document")
            return result
        except AppwriteException as e:
            logger.error(f"Failed to create document in '{collection_id}'", source="database_manager", error=e,
                         event_type="create_document")
            raise

    def get_document(self, collection_id: str, document_id: str) -> dict:
        """
        Fetch a document by ID.

        Parameters
        ----------
        collection_id : str
            Target collection ID.
        document_id : str
            Document ID.

        Returns
        -------
        dict
            Document details.
        """
        try:
            result = self.db.get_document(self.database_id, collection_id, document_id)
            logger.debug(f"Fetched document '{document_id}' from '{collection_id}'", source="database_manager",
                         event_type="get_document")
            return result
        except AppwriteException as e:
            logger.error(f"Failed to fetch document '{document_id}' from '{collection_id}'", source="database_manager",
                         error=e, event_type="get_document")
            raise

    def update_document(self, collection_id: str, document_id: str, data: dict) -> dict:
        """
        Update an existing document.

        Parameters
        ----------
        collection_id : str
            Target collection ID.
        document_id : str
            Document ID.
        data : dict
            Updated document data.

        Returns
        -------
        dict
            Updated document details.
        """
        try:
            result = self.db.update_document(
                database_id=self.database_id,
                collection_id=collection_id,
                document_id=document_id,
                data=data
            )
            logger.info(f"Updated document '{document_id}' in '{collection_id}'", source="database_manager",
                        event_type="update_document")
            return result
        except AppwriteException as e:
            logger.error(f"Failed to update document '{document_id}' in '{collection_id}'", source="database_manager",
                         error=e, event_type="update_document")
            raise

    def delete_document(self, collection_id: str, document_id: str) -> None:
        """
        Delete a document by ID.

        Parameters
        ----------
        collection_id : str
            Target collection ID.
        document_id : str
            Document ID.
        """
        try:
            self.db.delete_document(self.database_id, collection_id, document_id)
            logger.warning(f"Deleted document '{document_id}' from '{collection_id}'", source="database_manager",
                           event_type="delete_document")
        except AppwriteException as e:
            logger.error(f"Failed to delete document '{document_id}' from '{collection_id}'", source="database_manager",
                         error=e, event_type="delete_document")
            raise

    def list_documents(self, collection_id: str, queries: list = None) -> list:
        """
        List all documents in a collection.

        Parameters
        ----------
        collection_id : str
            Target collection ID.
        queries : list, optional
            Query filters. Defaults to None.

        Returns
        -------
        list
            List of documents.
        """
        try:
            response = self.db.list_documents(
                database_id=self.database_id,
                collection_id=collection_id,
                queries=queries or []
            )
            logger.debug(f"Listed documents in '{collection_id}'", source="database_manager",
                         event_type="list_documents")
            return response['documents']
        except AppwriteException as e:
            logger.error(f"Failed to list documents in '{collection_id}'", source="database_manager", error=e,
                         event_type="list_documents")
            raise
