# polymer_extractor/api/grobid.py

"""
GROBID API Router for Polymer NLP Extractor.

Summary
-------
Session-aware REST endpoints for GROBID document processing with multi-file support,
comprehensive validation, and unified response formatting. Provides enterprise-grade
document processing capabilities with session isolation and parallel processing.

Key Features
------------
- Session-aware document processing with user isolation
- Multi-file upload with intelligent validation and parallel processing
- Zip file upload and batch processing with extraction
- Comprehensive error handling with standardized responses
- File validation with corruption detection and format filtering
- Integration with unified storage and session management systems

Routes Overview
--------------
- POST /grobid/process/upload: Process single uploaded document with session
- POST /grobid/process/multiple: Process multiple files with session context
- POST /grobid/process/zip: Process zip file containing multiple documents
- POST /grobid/process/file: Process local file by path (legacy compatibility)
- GET /grobid/server/status: Check GROBID server status and health
- GET /grobid/download/tei/{filename}: Download processed TEI XML file
- GET /grobid/list/tei: List processed TEI XML files for session
- GET /grobid/health: Comprehensive health check for service dependencies

Session Integration
------------------
All processing endpoints require session_id and user_id for proper isolation.
Session validation ensures users can only access their own processing results.
File storage is automatically scoped to user sessions for security.

Examples
--------
>>> # Process single document
>>> POST /grobid/process/upload
>>> {
>>>   "session_id": "session_123",
>>>   "user_id": "user_456", 
>>>   "file": <uploaded_file>
>>> }
>>> 
>>> # Process multiple files
>>> POST /grobid/process/multiple
>>> {
>>>   "session_id": "session_123",
>>>   "user_id": "user_456",
>>>   "files": [<file1>, <file2>, <file3>]
>>> }

Notes
-----
- All responses use standardized response envelope from responses.py
- File validation prevents processing of corrupted or unsupported files
- Session-aware storage ensures proper user isolation and security
- Parallel processing optimizes performance for multi-file operations
"""

import os
import tempfile
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel

from polymer_extractor.services.grobid_service import GrobidService
from polymer_extractor.storage.session_manager import get_session_manager
from polymer_extractor.utils.logging import get_logger
from polymer_extractor.utils.paths import get_storage_path, path_resolver
from polymer_extractor.utils import responses as R

logger = get_logger()

# Initialize router and services
router = APIRouter(prefix="/grobid", tags=["GROBID"])
grobid_service = GrobidService()
session_manager = get_session_manager()


# === Request/Response Models ===

class SessionRequest(BaseModel):
    """Base model for session-aware requests."""
    session_id: str
    user_id: str

class ProcessingResult(BaseModel):
    """Response model for individual document processing results."""
    success: bool
    file_path: Optional[str] = None
    original_file: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    storage_tei_path: Optional[str] = None
    storage_pdf_path: Optional[str] = None
    error: Optional[str] = None

class MultiFileProcessingResult(BaseModel):
    """Response model for multi-file processing results."""
    session_id: str
    user_id: str
    total_files: int
    successful: int
    failed: int
    results: List[ProcessingResult]
    errors: List[str] = []

class ServerStatusResult(BaseModel):
    """Response model for server status checks."""
    server_available: bool
    server_url: str
    message: str

# === Helper Functions ===

async def validate_session(session_id: str, user_id: str):
    """
    Validate session and user access.
    
    Parameters
    ----------
    session_id : str
        Session identifier to validate.
    user_id : str
        User identifier for session ownership.
        
    Raises
    ------
    HTTPException
        If session is invalid or user doesn't have access.
    """
    try:
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied to session")
    except Exception as e:
        logger.error(f"Session validation failed", source="grobid_api", session_id=session_id, user_id=user_id, error=e)
        raise HTTPException(status_code=400, detail=f"Session validation failed: {str(e)}")

def save_upload_file(upload_file: UploadFile, temp_dir: Path) -> Path:
    """
    Save uploaded file to temporary directory with validation.
    
    Parameters
    ----------
    upload_file : UploadFile
        FastAPI uploaded file object.
    temp_dir : Path
        Temporary directory for file storage.
        
    Returns
    -------
    Path
        Path to saved file.
        
    Raises
    ------
    HTTPException
        If file save fails or file is invalid.
    """
    try:
        # Sanitize filename
        safe_filename = "".join(c for c in upload_file.filename if c.isalnum() or c in '._-')
        if not safe_filename:
            safe_filename = f"upload_{upload_file.filename[-10:]}" if upload_file.filename else "upload_file"
            
        file_path = temp_dir / safe_filename
        
        # Ensure unique filename
        counter = 1
        while file_path.exists():
            stem = Path(safe_filename).stem
            ext = Path(safe_filename).suffix
            file_path = temp_dir / f"{stem}_{counter}{ext}"
            counter += 1
        
        # Save file
        with open(file_path, 'wb') as f:
            content = upload_file.file.read()
            if not content:
                raise ValueError("Uploaded file is empty")
            f.write(content)
            
        return file_path
        
    except Exception as e:
        logger.error(f"Failed to save upload file", source="grobid_api", filename=upload_file.filename, error=e)
        raise HTTPException(status_code=400, detail=f"Failed to save uploaded file: {str(e)}")

# === SERVER STATUS ENDPOINTS ===

@router.get("/server/status")
async def check_server_status():
    """
    Check if the GROBID server is running and reachable.

    Returns
    -------
    dict
        Standardized response with server status information.

    Examples
    --------
    >>> GET /grobid/server/status
    >>> {
    >>>   "status": "success",
    >>>   "data": {
    >>>     "server_available": true,
    >>>     "server_url": "http://localhost:8070",
    >>>     "message": "GROBID server is running"
    >>>   }
    >>> }

    Notes
    -----
    - Uses standardized response envelope from responses.py
    - Provides server URL and availability status
    - Includes diagnostic message for troubleshooting
    """
    try:
        server_available = grobid_service.check_server_status()
        
        result = ServerStatusResult(
            server_available=server_available,
            server_url=grobid_service.grobid_server_url,
            message="GROBID server is running" if server_available else "GROBID server is not available"
        )
        
        logger.info("GROBID server status checked", source="grobid_api", available=server_available)
        
        if server_available:
            return R.ok(data=result.dict(), message="GROBID server is healthy")
        else:
            return R.error(message="GROBID server is not available", code=503, details=result.dict())
            
    except Exception as e:
        logger.error("GROBID server status check failed", source="grobid_api", error=e)
        return R.error(
            message="Failed to check GROBID server status",
            code=500,
            details={"error": str(e)},
            exception=e
        )

# === DOCUMENT PROCESSING ENDPOINTS ===

@router.post("/process/upload")
async def process_uploaded_document(
    session_id: str = Form(..., description="Session identifier for processing context"),
    user_id: str = Form(..., description="User identifier for session validation"),
    file: UploadFile = File(..., description="Document file to process"),
    filename_stem: Optional[str] = Form(None, description="Custom filename stem for output files")
):
    """
    Process single uploaded document with session context.

    Parameters
    ----------
    session_id : str
        Active session identifier for resource isolation.
    user_id : str
        User identifier for session validation and storage isolation.
    file : UploadFile
        Document file to process (PDF, XML, HTML).
    filename_stem : str, optional
        Custom filename stem to use for output files.

    Returns
    -------
    dict
        Standardized response with processing results and storage paths.

    Examples
    --------
    >>> POST /grobid/process/upload
    >>> Content-Type: multipart/form-data
    >>> session_id=session_123&user_id=user_456&file=document.pdf
    >>> 
    >>> Response:
    >>> {
    >>>   "status": "success",
    >>>   "data": {
    >>>     "session_id": "session_123",
    >>>     "metadata": {"title": "Document Title", "doi": "10.1234/example"},
    >>>     "storage_tei_path": "extracted_xml/user_456/session_123/document.tei.xml"
    >>>   }
    >>> }

    Notes
    -----
    - Validates session before processing
    - Supports PDF, XML, HTML input formats with automatic conversion
    - Files are stored with session isolation for security
    - Processing continues even if storage fails (non-blocking)
    """
    await validate_session(session_id, user_id)
    
    # Create temporary directory for file processing
    with tempfile.TemporaryDirectory(prefix=f"grobid_upload_{session_id}_") as temp_dir:
        temp_path = Path(temp_dir)
        
        try:
            # Save uploaded file
            file_path = save_upload_file(file, temp_path)
            
            logger.info(
                "Processing uploaded document",
                source="grobid_api",
                session_id=session_id,
                user_id=user_id,
                filename=file.filename,
                content_type=file.content_type
            )
            
            # Process document with session context
            result = grobid_service.process_document_with_session(
                session_id=session_id,
                file_path=file_path,
                user_id=user_id,
                filename_stem=filename_stem,
                original_filename=file.filename
            )
            
            # Create response data
            response_data = {
                "session_id": session_id,
                "user_id": user_id,
                "original_filename": file.filename,
                "metadata": result.get("metadata", {}),
                "storage_tei_path": result.get("storage_tei_path"),
                "storage_pdf_path": result.get("storage_pdf_path"),
                "storage_success": result.get("storage_success", False),
                "processing_completed": True
            }
            
            if result.get("storage_errors"):
                response_data["storage_warnings"] = result["storage_errors"]
            
            logger.info(
                "Document processing completed via upload",
                source="grobid_api",
                session_id=session_id,
                filename=file.filename,
                storage_success=result.get("storage_success", False)
            )
            
            return R.ok(
                data=response_data,
                message=f"Document processed successfully: {file.filename}"
            )
            
        except ValueError as e:
            logger.warning(
                "Document processing validation failed",
                source="grobid_api",
                session_id=session_id,
                filename=file.filename,
                error=e
            )
            return R.failure(
                message="Document validation failed",
                code=400,
                details={"filename": file.filename, "error": str(e)}
            )
            
        except Exception as e:
            logger.error(
                "Document processing failed via upload",
                source="grobid_api",
                session_id=session_id,
                filename=file.filename,
                error=e
            )
@router.post("/process/multiple")
async def process_multiple_documents(
    session_id: str = Form(..., description="Session identifier for processing context"),
    user_id: str = Form(..., description="User identifier for session validation"),
    files: List[UploadFile] = File(..., description="Multiple document files to process"),
    parallel: bool = Form(True, description="Whether to process files in parallel")
):
    """
    Process multiple uploaded documents with session context and parallel execution.

    Parameters
    ----------
    session_id : str
        Active session identifier for resource isolation.
    user_id : str
        User identifier for session validation.
    files : List[UploadFile]
        List of document files to process.
    parallel : bool, default=True
        Whether to process files in parallel or sequentially.

    Returns
    -------
    dict
        Standardized response with batch processing results.

    Examples
    --------
    >>> POST /grobid/process/multiple
    >>> Content-Type: multipart/form-data
    >>> session_id=session_123&user_id=user_456&files=doc1.pdf&files=doc2.html
    >>> 
    >>> Response:
    >>> {
    >>>   "status": "success",
    >>>   "data": {
    >>>     "total_files": 2,
    >>>     "successful": 2,
    >>>     "failed": 0,
    >>>     "results": [...]
    >>>   }
    >>> }

    Notes
    -----
    - Individual file failures don't stop batch processing
    - Parallel processing improves performance for multiple files
    - All files are validated before processing begins
    - Session isolation maintained for all processed files
    """
    await validate_session(session_id, user_id)
    
    if not files:
        return R.failure(message="No files provided for processing", code=400)
    
    # Create temporary directory for file processing
    with tempfile.TemporaryDirectory(prefix=f"grobid_multi_{session_id}_") as temp_dir:
        temp_path = Path(temp_dir)
        saved_files = []
        
        try:
            # Save all uploaded files
            for upload_file in files:
                try:
                    file_path = save_upload_file(upload_file, temp_path)
                    saved_files.append(file_path)
                except Exception as e:
                    logger.warning(
                        f"Failed to save uploaded file, skipping",
                        source="grobid_api",
                        filename=upload_file.filename,
                        error=e
                    )
                    continue
            
            if not saved_files:
                return R.failure(message="No valid files could be saved for processing", code=400)
            
            logger.info(
                "Processing multiple uploaded documents",
                source="grobid_api",
                session_id=session_id,
                user_id=user_id,
                file_count=len(saved_files),
                parallel=parallel
            )
            
            # Process files with session context
            results = grobid_service.process_multiple_files(
                session_id=session_id,
                file_paths=saved_files,
                user_id=user_id,
                parallel=parallel
            )
            
            # Create response data
            response_data = {
                "session_id": session_id,
                "user_id": user_id,
                "total_files": results["total_files"],
                "successful": results["successful"],
                "failed": results["failed"],
                "parallel_processing": parallel,
                "results": results["results"]
            }
            
            if results.get("errors"):
                response_data["processing_errors"] = results["errors"]
            
            logger.info(
                "Multi-file processing completed",
                source="grobid_api",
                session_id=session_id,
                successful=results["successful"],
                failed=results["failed"]
            )
            
            status_message = f"Processed {results['successful']} of {results['total_files']} files successfully"
            if results["failed"] > 0:
                status_message += f" ({results['failed']} failed)"
            
            return R.ok(data=response_data, message=status_message)
            
        except Exception as e:
            logger.error(
                "Multi-file processing failed",
                source="grobid_api",
                session_id=session_id,
                error=e
            )
            return R.error(
                message="Multi-file processing failed",
                code=500,
                details={"file_count": len(files), "error": str(e)},
                exception=e
            )

@router.post("/process/zip")
async def process_zip_upload(
    session_id: str = Form(..., description="Session identifier for processing context"),
    user_id: str = Form(..., description="User identifier for session validation"),
    zip_file: UploadFile = File(..., description="Zip file containing documents to process"),
    max_files: int = Form(50, description="Maximum number of files to extract from zip")
):
    """
    Process zip file containing multiple documents with extraction and validation.

    Parameters
    ----------
    session_id : str
        Active session identifier for resource isolation.
    user_id : str
        User identifier for session validation.
    zip_file : UploadFile
        Zip file containing documents to process.
    max_files : int, default=50
        Maximum number of files to extract and process.

    Returns
    -------
    dict
        Standardized response with zip processing results.

    Examples
    --------
    >>> POST /grobid/process/zip
    >>> Content-Type: multipart/form-data
    >>> session_id=session_123&user_id=user_456&zip_file=documents.zip
    >>> 
    >>> Response:
    >>> {
    >>>   "status": "success",
    >>>   "data": {
    >>>     "zip_file": "documents.zip",
    >>>     "files_extracted": 5,
    >>>     "files_processed": 4,
    >>>     "files_failed": 1
    >>>   }
    >>> }

    Notes
    -----
    - Validates zip file integrity before extraction
    - Filters files by supported formats during extraction
    - Individual file validation prevents corruption from stopping processing
    - Automatic cleanup of temporary extraction directory
    """
    await validate_session(session_id, user_id)
    
    # Validate zip file
    if not zip_file.filename.lower().endswith('.zip'):
        return R.failure(message="File must be a zip archive", code=400)
    
    # Create temporary directory for zip processing
    with tempfile.TemporaryDirectory(prefix=f"grobid_zip_{session_id}_") as temp_dir:
        temp_path = Path(temp_dir)
        
        try:
            # Save uploaded zip file
            zip_path = save_upload_file(zip_file, temp_path)
            
            logger.info(
                "Processing uploaded zip file",
                source="grobid_api",
                session_id=session_id,
                user_id=user_id,
                zip_filename=zip_file.filename,
                max_files=max_files
            )
            
            # Process zip with session context
            results = grobid_service.process_zip_upload(
                session_id=session_id,
                zip_file_path=zip_path,
                user_id=user_id,
                max_files=max_files
            )
            
            # Create response data
            response_data = {
                "session_id": session_id,
                "user_id": user_id,
                "zip_file": zip_file.filename,
                "files_extracted": results["files_extracted"],
                "files_processed": results["files_processed"],
                "files_failed": results["files_failed"],
                "max_files_limit": max_files,
                "results": results["results"]
            }
            
            if results.get("errors"):
                response_data["processing_errors"] = results["errors"]
            
            logger.info(
                "Zip processing completed",
                source="grobid_api",
                session_id=session_id,
                zip_filename=zip_file.filename,
                extracted=results["files_extracted"],
                processed=results["files_processed"]
            )
            
            if results["files_extracted"] == 0:
                return R.failure(
                    message="No valid files found in zip archive",
                    code=400,
                    details=response_data
                )
            
            status_message = f"Extracted {results['files_extracted']} files, processed {results['files_processed']} successfully"
            if results["files_failed"] > 0:
                status_message += f" ({results['files_failed']} failed)"
            
            return R.ok(data=response_data, message=status_message)
            
        except ValueError as e:
            logger.warning(
                "Zip processing validation failed",
                source="grobid_api",
                session_id=session_id,
                zip_filename=zip_file.filename,
                error=e
            )
            return R.failure(
                message="Zip file validation failed",
                code=400,
                details={"zip_file": zip_file.filename, "error": str(e)}
            )
            
        except Exception as e:
            logger.error(
                "Zip processing failed",
                source="grobid_api",
                session_id=session_id,
                zip_filename=zip_file.filename,
                error=e
            )
            return R.error(
                message="Zip processing failed",
                code=500,
                details={"zip_file": zip_file.filename, "error": str(e)},
                exception=e
            )

# === LEGACY COMPATIBILITY ENDPOINTS ===

@router.post("/process/file")
async def process_file_by_path(
    file_path: str = Form(..., description="Local file path to process"),
    filename_stem: Optional[str] = Form(None, description="Custom filename stem for output files")
):
    """
    Process local file by path (legacy compatibility endpoint).

    Parameters
    ----------
    file_path : str
        Local file system path to document.
    filename_stem : str, optional
        Custom filename stem for output files.

    Returns
    -------
    dict
        Standardized response with processing results.

    Notes
    -----
    - Legacy endpoint for backward compatibility
    - Does not use session management
    - For new applications, prefer session-aware endpoints
    """
    try:
        logger.warning(
            "Using legacy file processing endpoint",
            source="grobid_api",
            file_path=file_path
        )
        
        # Use legacy processing method
        result = grobid_service.process_document(
            file_path=file_path,
            filename_stem=filename_stem
        )
        
        response_data = {
            "original_file": result.get("original_file"),
            "metadata": result.get("metadata", {}),
            "storage_tei_path": result.get("storage_tei_path"),
            "storage_pdf_path": result.get("storage_pdf_path"),
            "storage_success": result.get("storage_success", False),
            "legacy_processing": True
        }
        
        if result.get("storage_errors"):
            response_data["storage_warnings"] = result["storage_errors"]
        
        logger.info(
            "Legacy file processing completed",
            source="grobid_api",
            file_path=file_path,
            storage_success=result.get("storage_success", False)
        )
        
        return R.ok(
            data=response_data,
            message=f"Document processed successfully (legacy mode): {Path(file_path).name}"
        )
        
    except ValueError as e:
        logger.warning(
            "Legacy file processing validation failed",
            source="grobid_api",
            file_path=file_path,
            error=e
        )
        return R.failure(
            message="Document validation failed",
            code=400,
            details={"file_path": file_path, "error": str(e)}
        )
        
    except Exception as e:
        logger.error(
            "Legacy file processing failed",
            source="grobid_api",
            file_path=file_path,
            error=e
        )
# === FILE ACCESS ENDPOINTS ===

@router.get("/download/tei/{filename}")
async def download_tei_file(
    filename: str,
    session_id: str = Form(..., description="Session identifier for file access"),
    user_id: str = Form(..., description="User identifier for session validation")
):
    """
    Download processed TEI XML file with session validation.

    Parameters
    ----------
    filename : str
        Name of the TEI XML file to download.
    session_id : str
        Session identifier for access control.
    user_id : str
        User identifier for session validation.

    Returns
    -------
    FileResponse
        TEI XML file download response.

    Notes
    -----
    - Session validation ensures users can only access their own files
    - Files are served from session-scoped storage paths
    - Proper content-type headers for XML files
    """
    await validate_session(session_id, user_id)
    
    try:
        # Construct session-scoped file path
        storage_path = get_storage_path("extracted_xml", f"{user_id}/{session_id}/{filename}")
        local_path = path_resolver.to_local_path(storage_path)
        
        if not Path(local_path).exists():
            return R.failure(
                message="TEI file not found",
                code=404,
                details={"filename": filename, "session_id": session_id}
            )
        
        logger.info(
            "Serving TEI file download",
            source="grobid_api",
            session_id=session_id,
            user_id=user_id,
            filename=filename
        )
        
        return FileResponse(
            path=local_path,
            media_type="application/xml",
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(
            "TEI file download failed",
            source="grobid_api",
            session_id=session_id,
            filename=filename,
            error=e
        )
        return R.error(
            message="Failed to serve TEI file",
            code=500,
            details={"filename": filename, "error": str(e)},
            exception=e
        )

@router.get("/list/tei")
async def list_tei_files(
    session_id: str,
    user_id: str
):
    """
    List processed TEI XML files for session.

    Parameters
    ----------
    session_id : str
        Session identifier for file listing.
    user_id : str
        User identifier for session validation.

    Returns
    -------
    dict
        Standardized response with list of available TEI files.

    Notes
    -----
    - Lists only files accessible to the user's session
    - Includes file metadata and processing information
    - Sorted by processing date (newest first)
    """
    await validate_session(session_id, user_id)
    
    try:
        # Get session-scoped storage path
        session_storage_path = f"extracted_xml/{user_id}/{session_id}"
        local_session_dir = path_resolver.to_local_path(session_storage_path)
        
        files = []
        session_dir = Path(local_session_dir)
        
        if session_dir.exists():
            for file_path in session_dir.glob("*.tei.xml"):
                try:
                    file_stat = file_path.stat()
                    files.append({
                        "filename": file_path.name,
                        "size": file_stat.st_size,
                        "modified": file_stat.st_mtime,
                        "storage_path": get_storage_path("extracted_xml", f"{user_id}/{session_id}/{file_path.name}")
                    })
                except Exception as e:
                    logger.warning(
                        f"Failed to get file info",
                        source="grobid_api",
                        filename=file_path.name,
                        error=e
                    )
                    continue
        
        # Sort by modification time (newest first)
        files.sort(key=lambda x: x["modified"], reverse=True)
        
        logger.info(
            "Listed TEI files for session",
            source="grobid_api",
            session_id=session_id,
            user_id=user_id,
            file_count=len(files)
        )
        
        return R.ok(
            data={
                "session_id": session_id,
                "user_id": user_id,
                "file_count": len(files),
                "files": files
            },
            message=f"Found {len(files)} TEI files for session"
        )
        
    except Exception as e:
        logger.error(
            "TEI file listing failed",
            source="grobid_api",
            session_id=session_id,
            error=e
        )
        return R.error(
            message="Failed to list TEI files",
            code=500,
            details={"session_id": session_id, "error": str(e)},
            exception=e
        )

# === HEALTH CHECK ENDPOINTS ===

@router.get("/health")
async def comprehensive_health_check():
    """
    Comprehensive health check for GROBID service and dependencies.

    Returns
    -------
    dict
        Standardized response with health status of all components.

    Notes
    -----
    - Checks GROBID server availability
    - Validates storage system connectivity
    - Tests database connectivity
    - Reports session manager status
    """
    try:
        health_status = {
            "grobid_server": False,
            "storage_system": False,
            "database": False,
            "session_manager": False,
            "overall_status": "unhealthy"
        }
        
        # Check GROBID server
        try:
            health_status["grobid_server"] = grobid_service.check_server_status()
        except Exception as e:
            logger.warning("GROBID server health check failed", source="grobid_api", error=e)
        
        # Check storage system
        try:
            # Test storage connectivity by checking if we can list resources
            grobid_service.storage_manager.list_resources("", max_results=1)
            health_status["storage_system"] = True
        except Exception as e:
            logger.warning("Storage system health check failed", source="grobid_api", error=e)
        
        # Check database
        try:
            # Test database connectivity
            grobid_service.db_manager.list_records("extraction_metadata", limit=1)
            health_status["database"] = True
        except Exception as e:
            logger.warning("Database health check failed", source="grobid_api", error=e)
        
        # Check session manager
        try:
            # Test session manager basic functionality
            sessions = session_manager.list_active_sessions()
            health_status["session_manager"] = True
        except Exception as e:
            logger.warning("Session manager health check failed", source="grobid_api", error=e)
        
        # Determine overall status
        if all(health_status[key] for key in ["grobid_server", "storage_system", "database", "session_manager"]):
            health_status["overall_status"] = "healthy"
        elif health_status["grobid_server"] and health_status["storage_system"]:
            health_status["overall_status"] = "degraded"
        else:
            health_status["overall_status"] = "unhealthy"
        
        # Log health check result
        logger.info(
            "Health check completed",
            source="grobid_api",
            overall_status=health_status["overall_status"],
            **{k: v for k, v in health_status.items() if k != "overall_status"}
        )
        
        if health_status["overall_status"] == "healthy":
            return R.healthy(
                data=health_status,
                message="All GROBID service components are healthy"
            )
        elif health_status["overall_status"] == "degraded":
            return R.partial(
                data=health_status,
                message="GROBID service is operational but some components are degraded"
            )
        else:
            return R.error(
                message="GROBID service is unhealthy",
                code=503,
                details=health_status
            )
        
    except Exception as e:
        logger.error("Health check failed", source="grobid_api", error=e)
        return R.error(
            message="Health check failed",
            code=500,
            details={"error": str(e)},
            exception=e
        )
