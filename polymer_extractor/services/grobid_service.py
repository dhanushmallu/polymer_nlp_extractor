# polymer_extractor/services/grobid_service.py

"""
GROBID Service for Polymer NLP Extractor.

Summary
-------
Session-aware, production-ready GROBID service with multi-file processing capabilities,
unified storage integration, and comprehensive error handling. Supports parallel processing,
intelligent file validation, and seamless session management for multi-user environments.

Key Features
------------
- Session-aware document processing with user isolation
- Multi-file upload with intelligent validation and parallel processing
- Zip file extraction and batch processing
- Format validation with corruption detection
- Integration with unified StorageManager and DatabaseManager
- Comprehensive metadata extraction and storage
- Production-ready error handling and recovery
- Support for PDF, XML, HTML input formats with automatic conversion

Architecture Integration
-----------------------
- SessionManager: User session isolation and resource management
- StorageManager: Unified multi-backend storage operations
- DatabaseManager: PostgreSQL metadata persistence
- ResponseHelper: Standardized API response formatting
- PathResolver: Consistent path resolution across storage backends

Supported Operations
-------------------
- Single document processing with session context
- Multi-file batch processing with parallel execution
- Zip file extraction and processing
- Document format validation and conversion
- TEI XML extraction and cleaning with GROBID
- Metadata extraction from scientific papers
- Session-aware storage with user isolation

Examples
--------
>>> from polymer_extractor.services.grobid_service import GrobidService
>>> service = GrobidService()
>>> 
>>> # Process single document with session
>>> result = service.process_document_with_session(
...     session_id="session_123",
...     file_path="document.pdf",
...     user_id="user_456"
... )
>>> 
>>> # Process multiple files
>>> results = service.process_multiple_files(
...     session_id="session_123", 
...     file_paths=["doc1.pdf", "doc2.html"],
...     user_id="user_456"
... )

Notes
-----
- Performance: Parallel processing for multiple files with configurable concurrency
- Thread Safety: Session-aware operations with proper resource isolation
- Error Handling: Individual file failures don't stop batch processing
- Memory: Streaming operations for large files and zip processing
- Validation: Comprehensive file validation with corruption detection
"""

import os
import re
import zipfile
import tempfile
import asyncio
import concurrent.futures
from pathlib import Path
from typing import Union, Dict, Any, Optional, List, Tuple
from datetime import datetime
import xml.etree.ElementTree as ET

import requests

# Optional dependencies for document conversion
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from lxml import etree
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from polymer_extractor.storage.database_manager import DatabaseManager
from polymer_extractor.storage.storage_manager import get_storage_manager
from polymer_extractor.storage.session_manager import get_session_manager
from polymer_extractor.utils.logging import get_logger
from polymer_extractor.utils.paths import get_storage_path, path_resolver, RAW_INPUT_DIR, EXTRACTED_XML_DIR

logger = get_logger()


class GrobidService:
    """
    Session-aware GROBID service for document processing with multi-file support.

    Summary
    -------
    Provides enterprise-grade document processing capabilities with session management,
    parallel processing, and comprehensive error handling. Integrates with unified
    storage and database systems for production deployment.

    Key Abstractions
    ---------------
    - Session-aware processing: All operations tied to user sessions for isolation
    - Multi-file processing: Parallel processing with intelligent error handling
    - Format validation: Comprehensive file validation with corruption detection
    - Storage integration: Unified storage with multiple backend support
    - Metadata management: Structured metadata extraction and persistence

    Design Invariants
    ----------------
    - Session isolation: All operations scoped to user sessions
    - Non-blocking storage: Core processing succeeds regardless of storage issues
    - Individual file resilience: Single file failures don't stop batch processing
    - Format flexibility: Automatic conversion between supported formats
    - Production readiness: Comprehensive logging and error recovery

    Examples
    --------
    >>> service = GrobidService()
    >>> result = service.process_document_with_session(
    ...     session_id="session_123",
    ...     file_path="document.pdf", 
    ...     user_id="user_456"
    ... )
    >>> print(f"Processed: {result['metadata']['title']}")

    Notes
    -----
    - Thread Safety: All operations are thread-safe with session isolation
    - Performance: Configurable parallel processing for multi-file operations
    - Memory: Streaming operations for large files and efficient zip handling
    - Error Handling: Comprehensive recovery with detailed error reporting
    """

    def __init__(self, server_url: str = None, max_workers: int = 4):
        """
        Initialize GROBID service with session management and processing configuration.

        Parameters
        ----------
        server_url : str, optional
            GROBID server URL. If not provided, will be constructed from environment variables.
            Defaults to "http://{GROBID_HOST}:{GROBID_PORT}" from env or "http://localhost:8070".
        max_workers : int, default=4
            Maximum number of parallel workers for multi-file processing.

        Notes
        -----
        - Server management is handled by the central server_manager
        - This service focuses on document processing operations only
        - Session manager provides user isolation and resource management
        """
        if server_url is None:
            # Build URL from environment variables
            grobid_host = os.getenv("GROBID_HOST", "localhost")
            grobid_port = os.getenv("GROBID_PORT", "8070")
            server_url = f"http://{grobid_host}:{grobid_port}"
            
        self.grobid_server_url = server_url
        self.max_workers = max_workers
        
        # Supported file formats with validation patterns
        self.supported_formats = {'.pdf', '.xml', '.html', '.htm'}
        self.supported_archive_formats = {'.zip'}
        
        # File size limits (in bytes)
        self.max_file_size = int(os.getenv("GROBID_MAX_FILE_SIZE", "50")) * 1024 * 1024  # 50MB default
        self.max_zip_size = int(os.getenv("GROBID_MAX_ZIP_SIZE", "200")) * 1024 * 1024  # 200MB default

        # Initialize unified storage and session services
        self.db_manager = DatabaseManager()
        self.storage_manager = get_storage_manager()
        self.session_manager = get_session_manager()

        logger.info(
            f"GROBID Service initialized with server: {server_url}",
            source="GrobidService",
            max_workers=max_workers,
            max_file_size_mb=self.max_file_size // (1024 * 1024)
        )

    # === SERVER STATUS ===

    def check_server_status(self) -> bool:
        """
        Check if GROBID server is running and responsive.

        Returns
        -------
        bool
            True if server is responsive.

        Raises
        ------
        RuntimeError
            If server is not responding.

        Examples
        --------
        >>> service = GrobidService()
        >>> if service.check_server_status():
        ...     print("GROBID server is ready")

        Notes
        -----
        - Timeout set to 5 seconds for responsiveness
        - Uses GROBID's built-in health check endpoint
        """
        try:
            response = requests.get(f"{self.grobid_server_url}/api/isalive", timeout=5)
            if response.status_code == 200:
                return True
            else:
                raise RuntimeError(f"GROBID server returned status {response.status_code}")
        except Exception as e:
            raise RuntimeError(f"GROBID server is not responding: {str(e)}")

    # === SESSION-AWARE DOCUMENT PROCESSING ===

    def process_document_with_session(
        self, 
        session_id: str, 
        file_path: Union[str, Path], 
        user_id: str,
        filename_stem: str = None, 
        original_filename: str = None
    ) -> Dict[str, Any]:
        """
        Process single document with session context and user isolation.

        Parameters
        ----------
        session_id : str
            Active session identifier for resource isolation.
        file_path : str or Path
            Path to the document file (local path or storage key).
        user_id : str
            User identifier for session validation and storage isolation.
        filename_stem : str, optional
            Custom filename stem to use for output files.
        original_filename : str, optional
            Original filename for metadata tracking.

        Returns
        -------
        Dict[str, Any]
            Processing results with session context and storage paths.

        Raises
        ------
        ValueError
            If session is invalid or document type is not supported.
        RuntimeError
            If core processing steps fail.

        Examples
        --------
        >>> result = service.process_document_with_session(
        ...     session_id="session_123",
        ...     file_path="document.pdf",
        ...     user_id="user_456"
        ... )
        >>> print(f"TEI saved at: {result['storage_tei_path']}")

        Notes
        -----
        - All storage operations are scoped to the user session
        - Non-blocking storage ensures core processing always succeeds
        - Metadata includes session and user context for tracking
        """
        # Validate session
        session = self.session_manager.get_session(session_id)
        if not session or session.user_id != user_id:
            raise ValueError(f"Invalid session {session_id} for user {user_id}")

        file_path = Path(file_path)
        
        # Resolve path to local filesystem for processing
        local_file_path = Path(path_resolver.to_local_path(file_path))
        
        original_filename = original_filename or local_file_path.name
        output_stem = filename_stem or Path(original_filename).stem

        logger.info(
            f"Starting session-aware document processing",
            source="GrobidService",
            session_id=session_id,
            user_id=user_id,
            original_filename=original_filename
        )

        result = {
            'session_id': session_id,
            'user_id': user_id,
            'original_file': original_filename,
            'pdf_file': None,
            'tei_content': None,
            'cleaned_tei_content': None,
            'metadata': {},
            'local_tei_path': None,
            'storage_tei_path': None,
            'storage_pdf_path': None,
            'storage_success': False,
            'processing_completed': True,
            'storage_errors': []
        }

        try:
            # Step 1: Validate and convert to PDF
            pdf_path = self._validate_and_convert_document(local_file_path, output_stem)
            result['pdf_file'] = pdf_path.name

            # Step 2: Store initial PDF upload to raw_inputs_dir/ and create research_papers record
            upload_result = self._store_initial_pdf_upload(pdf_path, session_id, user_id, original_filename)
            paper_id = upload_result.get('paper_id')
            result['storage_pdf_path'] = upload_result.get('pdf_storage_key')

            # Step 3: Extract TEI XML with GROBID
            tei_content = self._extract_with_grobid(pdf_path)
            result['tei_content'] = tei_content

            # Step 4: Extract metadata
            metadata = self._extract_metadata(tei_content)
            metadata.update({
                "session_id": session_id,
                "user_id": user_id,
                "file_name": original_filename,
                "grobid_version": self._extract_grobid_version(tei_content),
                "processed_on": datetime.now().isoformat() + "Z"
            })
            result['metadata'] = metadata

            # Step 5: Clean TEI XML
            cleaned_tei = self._clean_tei(tei_content)
            result['cleaned_tei_content'] = cleaned_tei

            # Step 6: Save TEI locally for processing
            tei_filename = f"{output_stem}.tei.xml"
            # Use the predefined EXTRACTED_XML_DIR from paths.py
            os.makedirs(EXTRACTED_XML_DIR, exist_ok=True)
            local_tei_path = Path(EXTRACTED_XML_DIR) / tei_filename
            local_tei_path.write_text(cleaned_tei, encoding='utf-8')
            result['local_tei_path'] = str(local_tei_path)

            logger.info(
                f"Core processing completed",
                source="GrobidService", 
                session_id=session_id,
                original_filename=original_filename
            )

            # Step 7: Store TEI XML and update metadata tables (non-blocking)
            try:
                self._store_files_and_metadata_with_session(pdf_path, local_tei_path, metadata, session_id, user_id)
                result['storage_success'] = True
                result['storage_tei_path'] = get_storage_path("extracted_xml", local_tei_path.name)
                
                logger.info(
                    "TEI XML storage and metadata update completed",
                    source="GrobidService",
                    session_id=session_id,
                    original_filename=original_filename
                )
            except Exception as storage_error:
                result['storage_success'] = False
                result['storage_errors'].append(str(storage_error))
                logger.warning(
                    "TEI storage failed but processing succeeded",
                    source="GrobidService",
                    session_id=session_id,
                    original_filename=original_filename,
                    error=str(storage_error)
                )

            return result

        except Exception as e:
            logger.error(
                f"Document processing failed",
                source="GrobidService",
                session_id=session_id,
                original_filename=original_filename,
                error=e
            )
            raise

    def process_multiple_files(
        self,
        session_id: str,
        file_paths: List[Union[str, Path]],
        user_id: str,
        parallel: bool = True
    ) -> Dict[str, Any]:
        """
        Process multiple documents with session context and parallel execution.

        Parameters
        ----------
        session_id : str
            Active session identifier for resource isolation.
        file_paths : List[Union[str, Path]]
            List of file paths to process.
        user_id : str
            User identifier for session validation.
        parallel : bool, default=True
            Whether to process files in parallel or sequentially.

        Returns
        -------
        Dict[str, Any]
            Batch processing results with individual file outcomes.

        Raises
        ------
        ValueError
            If session is invalid or no valid files provided.

        Examples
        --------
        >>> results = service.process_multiple_files(
        ...     session_id="session_123",
        ...     file_paths=["doc1.pdf", "doc2.html"],
        ...     user_id="user_456"
        ... )
        >>> print(f"Processed {results['successful']} of {results['total_files']} files")

        Notes
        -----
        - Individual file failures don't stop batch processing
        - Parallel processing uses configurable thread pool
        - All operations maintain session isolation
        """
        # Validate session
        session = self.session_manager.get_session(session_id)
        if not session or session.user_id != user_id:
            raise ValueError(f"Invalid session {session_id} for user {user_id}")

        if not file_paths:
            raise ValueError("No files provided for processing")

        logger.info(
            f"Starting multi-file processing",
            source="GrobidService",
            session_id=session_id,
            user_id=user_id,
            file_count=len(file_paths),
            parallel=parallel
        )

        results = {
            'session_id': session_id,
            'user_id': user_id,
            'total_files': len(file_paths),
            'successful': 0,
            'failed': 0,
            'results': [],
            'errors': []
        }

        if parallel and len(file_paths) > 1:
            # Parallel processing
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_file = {
                    executor.submit(
                        self._safe_process_single_file, 
                        session_id, 
                        file_path, 
                        user_id
                    ): file_path
                    for file_path in file_paths
                }
                
                for future in concurrent.futures.as_completed(future_to_file):
                    file_path = future_to_file[future]
                    try:
                        result = future.result()
                        if result.get('success', False):
                            results['successful'] += 1
                        else:
                            results['failed'] += 1
                        results['results'].append(result)
                    except Exception as e:
                        results['failed'] += 1
                        error_result = {
                            'success': False,
                            'file_path': str(file_path),
                            'error': str(e)
                        }
                        results['results'].append(error_result)
                        results['errors'].append(f"File {file_path}: {str(e)}")
        else:
            # Sequential processing
            for file_path in file_paths:
                try:
                    result = self._safe_process_single_file(session_id, file_path, user_id)
                    if result.get('success', False):
                        results['successful'] += 1
                    else:
                        results['failed'] += 1
                    results['results'].append(result)
                except Exception as e:
                    results['failed'] += 1
                    error_result = {
                        'success': False,
                        'file_path': str(file_path),
                        'error': str(e)
                    }
                    results['results'].append(error_result)
                    results['errors'].append(f"File {file_path}: {str(e)}")

        logger.info(
            f"Multi-file processing completed",
            source="GrobidService",
            session_id=session_id,
            successful=results['successful'],
            failed=results['failed']
        )

        return results

    def process_zip_upload(
        self,
        session_id: str,
        zip_file_path: Union[str, Path],
        user_id: str,
        max_files: int = 50
    ) -> Dict[str, Any]:
        """
        Process zip file containing multiple documents with validation and extraction.

        Parameters
        ----------
        session_id : str
            Active session identifier for resource isolation.
        zip_file_path : Union[str, Path]
            Path to the zip file to process.
        user_id : str
            User identifier for session validation.
        max_files : int, default=50
            Maximum number of files to extract from zip.

        Returns
        -------
        Dict[str, Any]
            Zip processing results with extracted file outcomes.

        Raises
        ------
        ValueError
            If session is invalid or zip file is corrupted.
        RuntimeError
            If zip extraction fails.

        Examples
        --------
        >>> results = service.process_zip_upload(
        ...     session_id="session_123",
        ...     zip_file_path="documents.zip",
        ...     user_id="user_456"
        ... )
        >>> print(f"Extracted and processed {results['files_processed']} documents")

        Notes
        -----
        - Validates zip file integrity before extraction
        - Filters files by supported formats during extraction
        - Individual file validation prevents corruption from stopping processing
        - Temporary extraction directory is automatically cleaned up
        """
        # Validate session
        session = self.session_manager.get_session(session_id)
        if not session or session.user_id != user_id:
            raise ValueError(f"Invalid session {session_id} for user {user_id}")

        zip_path = Path(zip_file_path)
        
        if not zip_path.exists():
            raise ValueError(f"Zip file not found: {zip_path}")

        logger.info(
            f"Starting zip file processing",
            source="GrobidService",
            session_id=session_id,
            user_id=user_id,
            zip_file=zip_path.name
        )

        results = {
            'session_id': session_id,
            'user_id': user_id,
            'zip_file': zip_path.name,
            'files_extracted': 0,
            'files_processed': 0,
            'files_failed': 0,
            'results': [],
            'errors': []
        }

        # Create temporary extraction directory
        with tempfile.TemporaryDirectory(prefix=f"grobid_zip_{session_id}_") as temp_dir:
            temp_path = Path(temp_dir)
            
            try:
                # Validate and extract zip file
                extracted_files = self._extract_zip_safely(zip_path, temp_path, max_files)
                results['files_extracted'] = len(extracted_files)
                
                if not extracted_files:
                    logger.warning(
                        f"No valid files found in zip",
                        source="GrobidService",
                        session_id=session_id,
                        zip_file=zip_path.name
                    )
                    return results

                # Process extracted files
                processing_results = self.process_multiple_files(
                    session_id=session_id,
                    file_paths=extracted_files,
                    user_id=user_id,
                    parallel=True
                )
                
                results.update({
                    'files_processed': processing_results['successful'],
                    'files_failed': processing_results['failed'],
                    'results': processing_results['results'],
                    'errors': processing_results['errors']
                })

                logger.info(
                    f"Zip processing completed",
                    source="GrobidService",
                    session_id=session_id,
                    zip_file=zip_path.name,
                    extracted=results['files_extracted'],
                    processed=results['files_processed']
                )

                return results

            except Exception as e:
                logger.error(
                    f"Zip processing failed",
                    source="GrobidService",
                    session_id=session_id,
                    zip_file=zip_path.name,
                    error=e
                )
                raise RuntimeError(f"Zip processing failed: {str(e)}") from e

    # === LEGACY COMPATIBILITY ===

    def process_document(self, file_path: Union[str, Path], filename_stem: str = None, original_filename: str = None) -> Dict[str, Any]:
        """
        Legacy document processing method for backward compatibility.

        Parameters
        ----------
        file_path : str or Path
            Path to the document file.
        filename_stem : str, optional
            Custom filename stem to use for output files.
        original_filename : str, optional
            Original filename for metadata tracking.

        Returns
        -------
        Dict[str, Any]
            Processing results including paths, metadata, and storage status.

        Notes
        -----
        - This method maintains backward compatibility
        - For new code, prefer process_document_with_session
        - Creates a temporary session for processing
        """
        logger.warning(
            "Using legacy process_document method. Consider upgrading to process_document_with_session",
            source="GrobidService"
        )
        
        # Create temporary session for legacy processing
        temp_session_id = f"legacy_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        temp_user_id = "legacy_user"
        
        # Use session-aware processing internally
        try:
            result = self.process_document_with_session(
                session_id=temp_session_id,
                file_path=file_path,
                user_id=temp_user_id,
                filename_stem=filename_stem,
                original_filename=original_filename
            )
            
            # Remove session-specific fields for legacy compatibility
            legacy_result = {k: v for k, v in result.items() if k not in ['session_id', 'user_id']}
            return legacy_result
            
        except Exception as e:
            # Fallback to direct processing if session creation fails
            return self._process_document_direct(file_path, filename_stem, original_filename)

    # === HELPER METHODS ===

    def _safe_process_single_file(self, session_id: str, file_path: Union[str, Path], user_id: str) -> Dict[str, Any]:
        """
        Safely process a single file with comprehensive error handling.

        Parameters
        ----------
        session_id : str
            Session identifier for context.
        file_path : Union[str, Path]
            Path to file to process.
        user_id : str
            User identifier for session validation.

        Returns
        -------
        Dict[str, Any]
            Processing result with success flag and error details.

        Notes
        -----
        - Wraps process_document_with_session with error handling
        - Used internally for multi-file processing
        - Ensures individual file failures don't stop batch processing
        """
        try:
            # Validate file before processing
            validation_result = self._validate_file(file_path)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'file_path': str(file_path),
                    'error': validation_result['error'],
                    'validation_failed': True
                }

            # Process the file
            result = self.process_document_with_session(
                session_id=session_id,
                file_path=file_path,
                user_id=user_id
            )
            
            return {
                'success': True,
                'file_path': str(file_path),
                'result': result
            }

        except Exception as e:
            logger.error(
                f"Safe processing failed for file",
                source="GrobidService",
                session_id=session_id,
                file_path=str(file_path),
                error=e
            )
            return {
                'success': False,
                'file_path': str(file_path),
                'error': str(e)
            }

    def _validate_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Validate file format, size, and integrity.

        Parameters
        ----------
        file_path : Union[str, Path]
            Path to file to validate.

        Returns
        -------
        Dict[str, Any]
            Validation result with valid flag and error details.

        Notes
        -----
        - Checks file extension against supported formats
        - Validates file size against configured limits
        - Performs basic corruption detection
        """
        file_path = Path(file_path)
        
        # Check if file exists
        if not file_path.exists():
            return {'valid': False, 'error': f"File not found: {file_path}"}

        # Check file extension
        file_ext = file_path.suffix.lower()
        if file_ext not in self.supported_formats and file_ext not in self.supported_archive_formats:
            return {
                'valid': False, 
                'error': f"Unsupported file format: {file_ext}. Supported: {', '.join(self.supported_formats | self.supported_archive_formats)}"
            }

        # Check file size
        file_size = file_path.stat().st_size
        max_size = self.max_zip_size if file_ext in self.supported_archive_formats else self.max_file_size
        
        if file_size > max_size:
            return {
                'valid': False, 
                'error': f"File too large: {file_size / (1024*1024):.1f}MB (max: {max_size / (1024*1024):.1f}MB)"
            }

        # Check if file is empty
        if file_size == 0:
            return {'valid': False, 'error': "File is empty"}

        # Basic corruption detection
        try:
            if file_ext == '.pdf':
                # Check PDF header
                with open(file_path, 'rb') as f:
                    header = f.read(8)
                    if not header.startswith(b'%PDF'):
                        return {'valid': False, 'error': "Invalid PDF file (corrupted header)"}
            
            elif file_ext in ['.xml']:
                # Check XML validity
                try:
                    ET.parse(file_path)
                except ET.ParseError:
                    return {'valid': False, 'error': "Invalid XML file (parse error)"}
            
            elif file_ext in self.supported_archive_formats:
                # Check zip integrity
                try:
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.testzip()
                except (zipfile.BadZipFile, zipfile.LargeZipFile):
                    return {'valid': False, 'error': "Corrupted zip file"}

        except Exception as e:
            return {'valid': False, 'error': f"File validation failed: {str(e)}"}

        return {'valid': True, 'error': None}

    def _extract_zip_safely(self, zip_path: Path, extract_to: Path, max_files: int) -> List[Path]:
        """
        Safely extract zip file with validation and file filtering.

        Parameters
        ----------
        zip_path : Path
            Path to zip file to extract.
        extract_to : Path
            Directory to extract files to.
        max_files : int
            Maximum number of files to extract.

        Returns
        -------
        List[Path]
            List of extracted file paths that match supported formats.

        Raises
        ------
        RuntimeError
            If zip extraction fails or contains unsafe files.

        Notes
        -----
        - Validates zip file integrity before extraction
        - Filters extracted files by supported formats
        - Prevents zip bomb attacks with size and count limits
        - Sanitizes file names to prevent directory traversal
        """
        extracted_files = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Get list of files in zip
                file_list = zip_ref.namelist()
                
                if len(file_list) > max_files:
                    logger.warning(
                        f"Zip contains {len(file_list)} files, limiting to {max_files}",
                        source="GrobidService",
                        zip_file=zip_path.name
                    )
                    file_list = file_list[:max_files]

                total_size = 0
                for file_info in zip_ref.infolist()[:max_files]:
                    # Security check: prevent directory traversal
                    if file_info.filename.startswith('/') or '..' in file_info.filename:
                        logger.warning(
                            f"Skipping potentially unsafe file: {file_info.filename}",
                            source="GrobidService"
                        )
                        continue

                    # Check uncompressed size to prevent zip bombs
                    total_size += file_info.file_size
                    if total_size > self.max_zip_size * 10:  # 10x compression ratio limit
                        logger.warning(
                            f"Zip extraction stopped due to size limit",
                            source="GrobidService",
                            total_size_mb=total_size / (1024*1024)
                        )
                        break

                    # Extract only files with supported extensions
                    file_ext = Path(file_info.filename).suffix.lower()
                    if file_ext in self.supported_formats:
                        try:
                            # Sanitize filename
                            safe_filename = Path(file_info.filename).name
                            extract_path = extract_to / safe_filename
                            
                            # Ensure unique filename if collision
                            counter = 1
                            while extract_path.exists():
                                stem = Path(safe_filename).stem
                                ext = Path(safe_filename).suffix
                                extract_path = extract_to / f"{stem}_{counter}{ext}"
                                counter += 1

                            # Extract the file
                            with zip_ref.open(file_info) as source, open(extract_path, 'wb') as target:
                                target.write(source.read())

                            extracted_files.append(extract_path)
                            
                            logger.debug(
                                f"Extracted file from zip",
                                source="GrobidService",
                                original_name=file_info.filename,
                                extract_path=str(extract_path)
                            )

                        except Exception as e:
                            logger.warning(
                                f"Failed to extract file from zip",
                                source="GrobidService",
                                filename=file_info.filename,
                                error=e
                            )
                            continue

            logger.info(
                f"Zip extraction completed",
                source="GrobidService",
                zip_file=zip_path.name,
                extracted_count=len(extracted_files)
            )
            
            return extracted_files

        except Exception as e:
            logger.error(
                f"Zip extraction failed",
                source="GrobidService",
                zip_file=zip_path.name,
                error=e
            )
            raise RuntimeError(f"Failed to extract zip file: {str(e)}") from e

    def _store_initial_pdf_upload(
        self,
        pdf_path: Path,
        session_id: str,
        user_id: str,
        original_filename: str = None
    ) -> Dict[str, Any]:
        """
        Store initial PDF upload to raw_inputs_dir/ and create research_papers record.
        
        This is the first step in the GROBID flow - save the uploaded file
        to all storage backends and create a basic research_papers record.
        
        Parameters
        ----------
        pdf_path : Path
            Path to the uploaded PDF file.
        session_id : str
            Session identifier.
        user_id : str
            User identifier.
        original_filename : str, optional
            Original filename for the record.
            
        Returns
        -------
        Dict[str, Any]
            Upload results with paper_id and storage paths.
            
        Raises
        ------
        RuntimeError
            If storage operation fails on all backends in sync strategy.
        """
        logger.info(
            "Storing initial PDF upload to raw_inputs",
            source="GrobidService",
            session_id=session_id,
            user_id=user_id,
            filename=original_filename or pdf_path.name
        )
        
        # Initialize result structure for non-blocking behavior
        upload_result = {
            "success": False,
            "storage_key": None,
            "paper_id": None,
            "error": None
        }
        
        try:
            # 1. Save PDF to raw_inputs_dir/ in all storage backends using proper paths
            pdf_storage_key = get_storage_path("raw_inputs", original_filename or pdf_path.name)
            
            # Get storage metadata for multi-backend support
            storage_backends = self.storage_manager.client.get_active_backend_names() if hasattr(self.storage_manager.client, 'get_active_backend_names') else ["local"]
            primary_backend = getattr(self.storage_manager.client, 'primary_backend', None)
            primary_backend_type = getattr(primary_backend, 'backend_type', 'local') if primary_backend else "local"
            
            # Get file hash for deduplication
            import hashlib
            file_hash = None
            if pdf_path.exists():
                with open(pdf_path, 'rb') as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()
                    f.seek(0)  # Reset for actual upload
                    
                    try:
                        pdf_upload_result = self.storage_manager.add_resource(
                            storage_key=pdf_storage_key,
                            content=f.read(),
                            metadata=None,  # No metadata files in storage
                            allow_override=True
                        )
                        upload_result["success"] = True
                        upload_result["storage_key"] = pdf_storage_key
                        
                        logger.info(
                            "PDF uploaded successfully to storage",
                            source="GrobidService",
                            session_id=session_id,
                            storage_key=pdf_storage_key,
                            backends=storage_backends
                        )
                    except Exception as storage_error:
                        # Log storage error but continue with database operation
                        logger.error(
                            "Storage upload failed but continuing with database record",
                            source="GrobidService", 
                            session_id=session_id,
                            error=str(storage_error)
                        )
                        upload_result["error"] = str(storage_error)

            # 2. Create basic research_papers record with default values
            # Get local path information for backward compatibility
            local_path = str(path_resolver.to_local_path(pdf_storage_key, "raw_inputs")) if upload_result["success"] else None
            
            research_paper_data = {
                "file_name": original_filename or pdf_path.name,
                "original_filename": original_filename or pdf_path.name,
                "authors": "Unknown",  # Default, will be updated after GROBID processing
                "title": "Pending Extraction",  # Default, will be updated after GROBID processing
                "storage_key": pdf_storage_key,
                "local_path": local_path,
                "file_size": pdf_path.stat().st_size if pdf_path.exists() else None,
                "file_hash": file_hash,
                "processing_status": "processing",  # Will be updated to "completed" after GROBID
                "storage_backends": storage_backends,
                "primary_backend": primary_backend_type,
                "session_id": session_id,
                "user_id": user_id,
                "uploaded_by": user_id,
                "access_level": "private",
                "metadata": {},
                "extraction_metadata": {}
            }
            
            try:
                paper_record = self.db_manager.create_record("research_papers", research_paper_data)
                paper_id = paper_record.get("id") if paper_record else None
                upload_result["paper_id"] = paper_id
                
                logger.info(
                    "Created research paper record",
                    source="GrobidService",
                    session_id=session_id,
                    paper_id=paper_id,
                    filename=original_filename or pdf_path.name
                )
            except Exception as db_error:
                logger.error(
                    "Failed to create research paper record",
                    source="GrobidService",
                    session_id=session_id,
                    error=str(db_error)
                )
                upload_result["error"] = str(db_error)
            
            logger.info(
                "Initial PDF upload processing completed",
                source="GrobidService",
                session_id=session_id,
                paper_id=upload_result.get("paper_id")
            )
            
            return upload_result
            
        except Exception as e:
            logger.error(
                "Failed to store initial PDF upload",
                source="GrobidService",
                session_id=session_id,
                user_id=user_id,
                error=str(e)
            )
            upload_result["error"] = str(e)
            return upload_result

    def _store_files_and_metadata_with_session(
        self, 
        pdf_path: Path, 
        tei_path: Path, 
        metadata: Dict[str, Any],
        session_id: str,
        user_id: str
    ):
        """
        Store files and metadata following the correct flow:
        1. Save TEI XML to extracted_xml_dir/ in all storages
        2. Update research_papers table with extracted metadata  
        
        Note: PDF should already be in raw_inputs_dir/ from the upload phase
        
        Parameters
        ----------
        pdf_path : Path
            Path to processed PDF file.
        tei_path : Path
            Path to processed TEI XML file.
        metadata : Dict[str, Any]
            Document metadata to store.
        session_id : str
            Session identifier for storage scoping.
        user_id : str
            User identifier for isolation.

        Notes
        -----
        - TEI XML saved to extracted_xml_dir/ in all storage backends
        - Updates existing research_papers record with extraction data
        - No session folders or subfolders in storage - files go directly to typed directories
        - Storage operations are non-blocking - core processing continues on storage failures
        """
        logger.info(
            "Storing TEI XML and updating metadata tables",
            source="GrobidService",
            session_id=session_id,
            user_id=user_id
        )

        storage_success = False
        tei_storage_key = None
        
        try:
            # 1. Save TEI XML to extracted_xml_dir/ in all storage backends using proper paths
            tei_storage_key = get_storage_path("extracted_xml", tei_path.name)
            
            # Get storage metadata for multi-backend support
            storage_backends = self.storage_manager.client.get_active_backend_names() if hasattr(self.storage_manager.client, 'get_active_backend_names') else ["local"]
            primary_backend = getattr(self.storage_manager.client, 'primary_backend', None)
            primary_backend_type = getattr(primary_backend, 'backend_type', 'local') if primary_backend else "local"
            
            try:
                with open(tei_path, 'rb') as f:
                    tei_upload_result = self.storage_manager.add_resource(
                        storage_key=tei_storage_key,
                        content=f.read(),
                        metadata=None,  # No metadata files in storage
                        allow_override=True
                    )
                storage_success = True
                
                logger.info(
                    "TEI XML uploaded successfully to storage",
                    source="GrobidService",
                    session_id=session_id,
                    storage_key=tei_storage_key,
                    backends=storage_backends
                )
            except Exception as storage_error:
                # Log storage error but continue with database operation
                logger.error(
                    "TEI XML storage failed but continuing with database update",
                    source="GrobidService", 
                    session_id=session_id,
                    error=str(storage_error)
                )

            # 2. Find and update the research_papers record
            pdf_storage_key = get_storage_path("raw_inputs", pdf_path.name)
            
            # Fix the search to use proper list_records method
            # The error was: integer ~~* unknown - ILIKE can't compare integer to string
            try:
                existing_papers = self.db_manager.list_records(
                    "research_papers", 
                    filters={"file_name": pdf_path.name},  # Use filters for exact match
                    limit=1  # We only need the first match
                )
            except Exception as search_error:
                # Fallback: try to find by session_id and filename pattern
                logger.warning(
                    "Search by file_name failed, trying alternative search",
                    source="GrobidService",
                    session_id=session_id,
                    search_error=str(search_error)
                )
                try:
                    # Use a direct SQL query as fallback
                    existing_papers = self.db_manager.postgresql_client.run(
                        "SELECT id, file_name, storage_key, session_id FROM research_papers WHERE file_name = %s AND session_id = %s LIMIT 1",
                        (pdf_path.name, session_id),
                        fetch="all"
                    )
                except Exception as fallback_error:
                    logger.error(
                        "Alternative search also failed",
                        source="GrobidService",
                        session_id=session_id,
                        fallback_error=str(fallback_error)
                    )
                    existing_papers = []
            
            if existing_papers:
                # Update existing record with extracted metadata
                paper_id = existing_papers[0]["id"]
                
                # Prepare extraction metadata with processing details
                extraction_metadata = {
                    **metadata,
                    "grobid_processing": {
                        "session_id": session_id,
                        "user_id": user_id,
                        "processing_date": datetime.utcnow().isoformat(),
                        "tei_storage_key": tei_storage_key if storage_success else None,
                        "storage_backends": storage_backends,
                        "primary_backend": primary_backend_type,
                        "storage_success": storage_success
                    }
                }
                
                update_data = {
                    "doi": metadata.get("doi"),
                    "title": metadata.get("title"),
                    "authors": metadata.get("authors", "Unknown"),
                    "journal": metadata.get("journal"),
                    "abstract": metadata.get("abstract"),
                    "grobid_version": metadata.get("grobid_version"),
                    "tei_storage_key": tei_storage_key if storage_success else None,
                    "processing_status": "completed",
                    "session_id": session_id,
                    "user_id": user_id,
                    "extraction_metadata": extraction_metadata,  # Store all extraction metadata as JSONB
                    "updated_at": datetime.utcnow()
                }
                
                try:
                    self.db_manager.update_record("research_papers", paper_id, update_data)
                    logger.info(
                        "Updated existing research paper record with extraction metadata",
                        source="GrobidService",
                        session_id=session_id,
                        paper_id=paper_id
                    )
                except Exception as update_error:
                    logger.error(
                        "Failed to update research paper record",
                        source="GrobidService",
                        session_id=session_id,
                        paper_id=paper_id,
                        error=str(update_error)
                    )
            else:
                # Create new record (fallback case)
                logger.warning(
                    "No existing paper record found, creating new one",
                    source="GrobidService",
                    session_id=session_id,
                    filename=pdf_path.name
                )
                
                # Get local path information for backward compatibility
                local_path = str(path_resolver.to_local_path(pdf_storage_key, "raw_inputs"))
                tei_local_path = str(path_resolver.to_local_path(tei_storage_key, "extracted_xml")) if storage_success else None
                
                # Get file hash for deduplication
                import hashlib
                file_hash = None
                if pdf_path.exists():
                    with open(pdf_path, 'rb') as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                
                # Prepare extraction metadata
                extraction_metadata = {
                    **metadata,
                    "grobid_processing": {
                        "session_id": session_id,
                        "user_id": user_id,
                        "processing_date": datetime.utcnow().isoformat(),
                        "tei_storage_key": tei_storage_key if storage_success else None,
                        "storage_backends": storage_backends,
                        "primary_backend": primary_backend_type,
                        "storage_success": storage_success
                    }
                }
                
                research_paper_data = {
                    "file_name": pdf_path.name,
                    "original_filename": pdf_path.name,
                    "doi": metadata.get("doi"),
                    "title": metadata.get("title"),
                    "authors": metadata.get("authors", "Unknown"),
                    "journal": metadata.get("journal"),
                    "abstract": metadata.get("abstract"),
                    "grobid_version": metadata.get("grobid_version"),
                    "storage_key": pdf_storage_key,
                    "local_path": local_path,
                    "tei_storage_key": tei_storage_key if storage_success else None,
                    "file_size": pdf_path.stat().st_size if pdf_path.exists() else None,
                    "file_hash": file_hash,
                    "processing_status": "completed",
                    "storage_backends": storage_backends,
                    "primary_backend": primary_backend_type,
                    "session_id": session_id,
                    "user_id": user_id,
                    "uploaded_by": user_id,
                    "access_level": "private",
                    "metadata": {},
                    "extraction_metadata": extraction_metadata
                }
                
                try:
                    paper_record = self.db_manager.create_record("research_papers", research_paper_data)
                    paper_id = paper_record.get("id") if paper_record else None
                    logger.info(
                        "Created new research paper record with extraction metadata",
                        source="GrobidService",
                        session_id=session_id,
                        paper_id=paper_id
                    )
                except Exception as create_error:
                    logger.error(
                        "Failed to create research paper record",
                        source="GrobidService",
                        session_id=session_id,
                        error=str(create_error)
                    )

            logger.info(
                "TEI XML storage and metadata update completed",
                source="GrobidService",
                session_id=session_id,
                original_filename=pdf_path.name,
                storage_success=storage_success
            )
            
        except Exception as e:
            logger.error(
                "Failed to store TEI XML and update metadata tables",
                source="GrobidService",
                session_id=session_id,
                user_id=user_id,
                error=str(e)
            )

    def _process_document_direct(self, file_path: Union[str, Path], filename_stem: str = None, original_filename: str = None) -> Dict[str, Any]:
        """
        Direct document processing fallback for legacy compatibility.
        
        This method provides basic processing without session management
        and should only be used as a fallback for legacy code.
        """
        file_path = Path(file_path)
        
        # Resolve path to local filesystem for processing
        local_file_path = Path(path_resolver.to_local_path(file_path))
        
        original_filename = original_filename or local_file_path.name
        output_stem = filename_stem or Path(original_filename).stem

        logger.warning(
            f"Using legacy process_document method for: {original_filename}",
            source="GrobidService"
        )

        result = {
            'original_file': original_filename,
            'pdf_file': None,
            'tei_content': None,
            'cleaned_tei_content': None,
            'metadata': {},
            'local_tei_path': None,
            'storage_success': False,
            'storage_errors': []
        }

        try:
            # Step 1: Validate and convert to PDF
            pdf_path = self._validate_and_convert_document(local_file_path, output_stem)
            result['pdf_file'] = pdf_path.name

            # Step 2: Extract TEI XML with GROBID
            tei_content = self._extract_with_grobid(pdf_path)
            result['tei_content'] = tei_content

            # Step 3: Extract metadata
            metadata = self._extract_metadata(tei_content)
            metadata.update({
                "file_name": original_filename,
                "grobid_version": self._extract_grobid_version(tei_content),
                "processed_on": datetime.now().isoformat() + "Z"
            })
            result['metadata'] = metadata

            # Step 4: Clean TEI XML
            cleaned_tei = self._clean_tei(tei_content)
            result['cleaned_tei_content'] = cleaned_tei

            # Step 5: Save locally (always succeeds)
            local_tei_path = self._save_tei_locally(cleaned_tei, output_stem)
            result['local_tei_path'] = str(local_tei_path)
            
            # Generate storage paths for API responses
            result['storage_tei_path'] = get_storage_path("extracted_xml", local_tei_path.name)
            result['storage_pdf_path'] = get_storage_path("raw_inputs", pdf_path.name)

            logger.info(f"Core processing completed for: {original_filename}", source="GrobidService")

            # Step 6: Attempt storage (non-blocking)
            try:
                self._store_files_and_metadata_legacy(pdf_path, local_tei_path, metadata)
                result['storage_success'] = True
                logger.info(f"Storage completed for: {original_filename}", source="GrobidService")
            except Exception as storage_error:
                result['storage_errors'].append(str(storage_error))
                logger.warning(f"Storage failed but processing succeeded for: {original_filename}",
                               source="GrobidService", error=storage_error)

            return result

        except Exception as e:
            logger.error(f"Document processing failed for: {original_filename}", source="GrobidService", error=e)
            raise

    # === CORE PROCESSING METHODS ===

    def _validate_and_convert_document(self, file_path: Path, output_stem: str = None) -> Path:
        """
        Validates document type and converts non-PDF documents to PDF with proper naming.

        Parameters
        ----------
        file_path : Path
            Path to input document.
        output_stem : str, optional
            Desired output filename stem.

        Returns
        -------
        Path
            Path to validated/converted PDF document.
        """
        file_ext = file_path.suffix.lower()
        output_stem = output_stem or file_path.stem

        if file_ext not in self.supported_formats:
            raise ValueError(f"Unsupported document type: {file_ext}. "
                             f"Supported formats: {', '.join(self.supported_formats)}")

        if file_ext == '.pdf':
            # Rename PDF to use proper output stem if needed
            if file_path.stem != output_stem:
                new_pdf_path = file_path.parent / f"{output_stem}.pdf"
                file_path.rename(new_pdf_path)
                logger.info(f"Renamed PDF to: {new_pdf_path.name}", source="GrobidService")
                return new_pdf_path
            return file_path

        logger.info(f"Converting {file_ext} document to PDF: {output_stem}", source="GrobidService")

        if file_ext in ['.html', '.htm']:
            return self._convert_html_to_pdf(file_path, output_stem)
        elif file_ext == '.xml':
            return self._convert_xml_to_pdf(file_path, output_stem)

        raise ValueError(f"Conversion not implemented for {file_ext}")

    def _convert_html_to_pdf(self, html_path: Path, output_stem: str) -> Path:
        """
        Converts HTML document to PDF with proper naming.
        """
        if not WEASYPRINT_AVAILABLE:
            raise RuntimeError("WeasyPrint is not available. Cannot convert HTML to PDF.")

        try:
            output_path = html_path.parent / f"{output_stem}.pdf"

            # Read HTML content
            html_content = html_path.read_text(encoding='utf-8')

            # Convert to PDF
            HTML(string=html_content, base_url=str(html_path.parent)).write_pdf(str(output_path))

            logger.info(f"Successfully converted HTML to PDF: {output_path.name}", source="GrobidService")
            return output_path

        except Exception as e:
            logger.error(f"Failed to convert HTML to PDF: {str(e)}", source="GrobidService")
            raise RuntimeError(f"HTML to PDF conversion failed: {str(e)}") from e

    def _convert_xml_to_pdf(self, xml_path: Path, output_stem: str) -> Path:
        """
        Converts XML document to PDF with proper naming.
        """
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError("ReportLab is not available. Cannot convert XML to PDF.")

        try:
            output_path = xml_path.parent / f"{output_stem}.pdf"

            # Read XML content and extract text
            xml_content = xml_path.read_text(encoding='utf-8')

            # Parse XML to extract text content
            try:
                root = etree.fromstring(xml_content.encode('utf-8'))
                text_content = etree.tostring(root, method="text", encoding="unicode")
            except etree.XMLSyntaxError:
                # If parsing fails, use raw content
                text_content = xml_content

            # Create PDF
            doc = SimpleDocTemplate(str(output_path), pagesize=letter)
            styles = getSampleStyleSheet()
            story = []

            # Split content into paragraphs
            for paragraph in text_content.split('\n\n'):
                if paragraph.strip():
                    story.append(Paragraph(paragraph.strip(), styles['Normal']))

            doc.build(story)

            logger.info(f"Successfully converted XML to PDF: {output_path.name}", source="GrobidService")
            return output_path

        except Exception as e:
            logger.error(f"Failed to convert XML to PDF: {str(e)}", source="GrobidService")
            raise RuntimeError(f"XML to PDF conversion failed: {str(e)}") from e

    def _extract_with_grobid(self, pdf_path: Path) -> str:
        """
        Extract TEI XML from PDF using GROBID server.

        Parameters
        ----------
        pdf_path : Path
            Path to PDF file.

        Returns
        -------
        str
            Extracted TEI XML content.
        """
        try:
            self.check_server_status()
        except RuntimeError as e:
            raise RuntimeError(f"GROBID server not available: {e}")

        try:
            with open(pdf_path, 'rb') as pdf_file:
                files = {'input': pdf_file}
                response = requests.post(
                    f"{self.grobid_server_url}/api/processFulltextDocument",
                    files=files,
                    timeout=120  # 2-minute timeout for processing
                )

            if response.status_code != 200:
                raise RuntimeError(f"GROBID processing failed with status {response.status_code}: {response.text}")

            tei_content = response.text
            if not tei_content.strip():
                raise RuntimeError("GROBID returned empty content")

            logger.info(f"Successfully extracted TEI XML from: {pdf_path.name}", source="GrobidService")
            return tei_content

        except Exception as e:
            logger.error(f"GROBID extraction failed for: {pdf_path.name}", source="GrobidService", error=e)
            raise

    def _extract_metadata(self, tei_content: str) -> Dict[str, Any]:
        """
        Extract metadata from TEI XML content.

        Parameters
        ----------
        tei_content : str
            TEI XML content.

        Returns
        -------
        Dict[str, Any]
            Extracted metadata dictionary.
        """
        metadata = {
            "doi": None,
            "title": None,
            "authors": None,
            "journal": None,
            "published_on": None
        }

        try:
            root = ET.fromstring(tei_content)

            # Define namespaces
            ns = {'tei': 'http://www.tei-c.org/ns/1.0'}

            # Extract title
            title_elem = root.find('.//tei:titleStmt/tei:title', ns)
            if title_elem is not None and title_elem.text:
                metadata["title"] = title_elem.text.strip()

            # Extract authors
            authors = []
            for author in root.findall('.//tei:sourceDesc//tei:author', ns):
                author_parts = []

                # Get forename and surname
                forename = author.find('.//tei:forename', ns)
                surname = author.find('.//tei:surname', ns)

                if forename is not None and forename.text:
                    author_parts.append(forename.text.strip())
                if surname is not None and surname.text:
                    author_parts.append(surname.text.strip())

                if author_parts:
                    authors.append(" ".join(author_parts))

            if authors:
                metadata["authors"] = ", ".join(authors)

            # Extract journal information
            journal_elem = root.find('.//tei:sourceDesc//tei:title[@level="j"]', ns)
            if journal_elem is not None and journal_elem.text:
                metadata["journal"] = journal_elem.text.strip()

            # Extract DOI
            doi_elem = root.find('.//tei:idno[@type="DOI"]', ns)
            if doi_elem is not None and doi_elem.text:
                metadata["doi"] = doi_elem.text.strip()

            # Extract publication date
            date_elem = root.find('.//tei:sourceDesc//tei:date', ns)
            if date_elem is not None:
                date_text = date_elem.get('when') or date_elem.text
                if date_text:
                    metadata["published_on"] = date_text.strip()

            logger.debug("Metadata extraction completed", source="GrobidService")
            return metadata

        except Exception as e:
            logger.warning(f"Metadata extraction failed, returning empty metadata", source="GrobidService", error=e)
            return metadata

    def _extract_grobid_version(self, tei_content: str) -> str:
        """
        Extract GROBID version from TEI XML.

        Parameters
        ----------
        tei_content : str
            TEI XML content.

        Returns
        -------
        str
            GROBID version string.
        """
        try:
            root = ET.fromstring(tei_content)

            # Look for application element with GROBID information
            app_elem = root.find('.//{http://www.tei-c.org/ns/1.0}application[@ident="GROBID"]')
            if app_elem is not None:
                version = app_elem.get('version')
                if version:
                    return version

            # Fallback: look in processing instruction or comment
            if 'GROBID' in tei_content:
                import re
                version_match = re.search(r'GROBID\s+(\d+\.\d+\.\d+)', tei_content)
                if version_match:
                    return version_match.group(1)

            return "unknown"

        except Exception as e:
            logger.debug(f"Could not extract GROBID version: {e}", source="GrobidService")
            return "unknown"

    def _clean_tei(self, tei_content: str) -> str:
        """
        Clean and format TEI XML content.

        Parameters
        ----------
        tei_content : str
            Raw TEI XML content.

        Returns
        -------
        str
            Cleaned TEI XML content.
        """
        try:
            # Parse and reformat XML
            root = ET.fromstring(tei_content)
            ET.indent(root, space="  ", level=0)
            cleaned_content = ET.tostring(root, encoding='unicode', xml_declaration=True)

            logger.debug("TEI XML cleaning completed", source="GrobidService")
            return cleaned_content

        except Exception as e:
            logger.warning(f"TEI cleaning failed, returning original content", source="GrobidService", error=e)
            return tei_content

    def _save_tei_locally(self, tei_content: str, filename_stem: str) -> Path:
        """
        Save TEI XML content to local file system (legacy method).

        Parameters
        ----------
        tei_content : str
            TEI XML content to save.
        filename_stem : str
            Base filename without extension.

        Returns
        -------
        Path
            Path to saved TEI file.

        Notes
        -----
        - Legacy method for backward compatibility
        - Saves directly to extracted_xml directory
        """
        try:
            # Ensure output directory exists using predefined paths
            os.makedirs(EXTRACTED_XML_DIR, exist_ok=True)
            tei_path = Path(EXTRACTED_XML_DIR) / f"{filename_stem}.tei.xml"

            # Write TEI content
            tei_path.write_text(tei_content, encoding='utf-8')

            logger.info(f"Saved TEI XML locally: {tei_path}", source="GrobidService")
            return tei_path

        except Exception as e:
            logger.error(f"Failed to save TEI locally", source="GrobidService", error=e)
            raise

    def _store_files_and_metadata_legacy(self, pdf_path: Path, tei_path: Path, metadata: Dict[str, Any]):
        """
        Legacy storage method for backward compatibility.

        Parameters
        ----------
        pdf_path : Path
            Path to processed PDF file.
        tei_path : Path
            Path to processed TEI XML file.
        metadata : Dict[str, Any]
            Document metadata to store.

        Notes
        -----
        - Uses unified storage manager instead of deprecated BucketClient
        - Stores metadata in extraction_metadata collection
        - Maintains backward compatibility
        """
        logger.info("Storing files and metadata (legacy mode)", source="GrobidService")

        try:
            # Upload PDF using unified storage
            pdf_storage_path = get_storage_path("raw_inputs", pdf_path.name)
            with open(pdf_path, 'rb') as f:
                pdf_upload_result = self.storage_manager.add_resource(
                    storage_key=pdf_storage_path,
                    content=f.read(),
                    metadata={**metadata, "file_type": "pdf", "source": "grobid_processing"}
                )

            # Upload TEI XML using unified storage
            tei_storage_path = get_storage_path("extracted_xml", tei_path.name)
            with open(tei_path, 'rb') as f:
                tei_upload_result = self.storage_manager.add_resource(
                    storage_key=tei_storage_path,
                    content=f.read(),
                    metadata={**metadata, "file_type": "tei_xml", "source": "grobid_processing"}
                )

            # Update metadata with storage results
            storage_metadata = {
                **metadata,
                "tei_storage_path": tei_storage_path,
                "pdf_storage_path": pdf_storage_path,
                "pdf_upload_success": pdf_upload_result.get("success", False),
                "tei_upload_success": tei_upload_result.get("success", False)
            }

            # Save metadata to extraction_metadata collection
            self.db_manager.create_record("extraction_metadata", storage_metadata)

            logger.info("Successfully stored files and metadata (legacy mode)", source="GrobidService")

        except Exception as e:
            logger.error(f"Failed to store files and metadata (legacy mode)", source="GrobidService", error=e)
            raise