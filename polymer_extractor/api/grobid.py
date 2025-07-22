# polymer_extractor/api/grobid.py

"""
GROBID API Router for Polymer NLP Extractor.

Provides REST endpoints for GROBID server management and document processing:
- Server lifecycle management (start/stop/status)
- Document processing with support for PDF, XML, and HTML
- File upload and batch processing capabilities
- Metadata extraction and storage integration

Routes:
- POST /grobid/server/start: Start GROBID server
- POST /grobid/server/stop: Stop GROBID server
- GET /grobid/server/status: Check GROBID server status
- POST /grobid/process/upload: Process uploaded document file
- POST /grobid/process/file: Process local file by path
- POST /grobid/process/batch: Process multiple files in batch
- GET /grobid/download/tei/{filename}: Download processed TEI XML file
- GET /grobid/list/tei: List all processed TEI XML files
- GET /grobid/health: Comprehensive health check for GROBID service and dependencies

The API is designed to be resilient with proper error handling and
non-blocking storage operations to ensure core processing always succeeds.
"""

import os
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

from polymer_extractor.services.grobid_service import GrobidService
from polymer_extractor.utils.logging import Logger
from polymer_extractor.utils.paths import WORKSPACE_DIR

logger = Logger()

# Initialize router
router = APIRouter(prefix="/grobid", tags=["GROBID"])

# Initialize GROBID service
grobid_service = GrobidService()


# === Response Models ===

class ServerStatusResponse(BaseModel):
    """Response model for server status checks."""
    status: str
    message: str
    server_url: str


class ProcessingResult(BaseModel):
    """Response model for document processing results."""
    success: bool
    message: str
    original_file: Optional[str] = None
    pdf_file: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    local_tei_path: Optional[str] = None
    storage_success: bool = False
    storage_errors: List[str] = []


class BatchProcessingResult(BaseModel):
    """Response model for batch processing results."""
    total_files: int
    successful: int
    failed: int
    results: List[ProcessingResult]


# === Server Management Endpoints ===

@router.post("/server/start", response_model=ServerStatusResponse)
async def start_grobid_server(
        grobid_home: Optional[str] = Form(default=None, description="Path to GROBID installation directory")
):
    """
    Start the GROBID server.

    Parameters
    ----------
    grobid_home : str, optional
        Custom path to GROBID installation. Defaults to workspace/grobid-0.8.2

    Returns
    -------
    ServerStatusResponse
        Server status and connection details.
    """
    try:
        if grobid_home is None:
            grobid_home = os.path.join(WORKSPACE_DIR, "grobid-0.8.2")

        logger.info("Starting GROBID server via API request", source="grobid_api", event_type="server_start")

        grobid_service.start_server(grobid_home=grobid_home)

        return ServerStatusResponse(
            status="started",
            message="GROBID server started successfully",
            server_url=grobid_service.grobid_server_url
        )

    except Exception as e:
        logger.error("Failed to start GROBID server via API", source="grobid_api", error=e, event_type="server_start")
        raise HTTPException(status_code=500, detail=f"Failed to start GROBID server: {str(e)}")


@router.post("/server/stop", response_model=ServerStatusResponse)
async def stop_grobid_server():
    """
    Stop the GROBID server.

    Returns
    -------
    ServerStatusResponse
        Server shutdown confirmation.
    """
    try:
        logger.info("Stopping GROBID server via API request", source="grobid_api", event_type="server_stop")

        grobid_service.stop_server()

        return ServerStatusResponse(
            status="stopped",
            message="GROBID server stopped successfully",
            server_url=grobid_service.grobid_server_url
        )

    except Exception as e:
        logger.error("Failed to stop GROBID server via API", source="grobid_api", error=e, event_type="server_stop")
        raise HTTPException(status_code=500, detail=f"Failed to stop GROBID server: {str(e)}")


@router.get("/server/status", response_model=ServerStatusResponse)
async def check_server_status():
    """
    Check if the GROBID server is running and reachable.

    Returns
    -------
    ServerStatusResponse
        Current server status.
    """
    try:
        grobid_service.check_server_status()

        return ServerStatusResponse(
            status="running",
            message="GROBID server is alive and responding",
            server_url=grobid_service.grobid_server_url
        )

    except Exception as e:
        logger.warning("GROBID server status check failed", source="grobid_api", error=e, event_type="server_status")
        return ServerStatusResponse(
            status="unreachable",
            message=f"GROBID server is not responding: {str(e)}",
            server_url=grobid_service.grobid_server_url
        )


# === Document Processing Endpoints ===

@router.post("/process/upload", response_model=ProcessingResult)
async def process_uploaded_file(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(..., description="Document file to process (PDF, XML, HTML)")
):
    """
    Process an uploaded document file.

    Supports PDF, XML, and HTML files. Non-PDF files are automatically
    converted to PDF before processing.

    Parameters
    ----------
    file : UploadFile
        The uploaded document file.

    Returns
    -------
    ProcessingResult
        Processing results including metadata and file paths.
    """
    temp_path = None
    try:
        # Validate file type
        allowed_extensions = {'.pdf', '.xml', '.html', '.htm'}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
            )

        # Get original filename stem for consistent naming
        original_stem = Path(file.filename).stem

        # Create temporary file with original name structure
        temp_dir = Path(tempfile.gettempdir())
        temp_filename = f"{original_stem}_{int(time.time())}{file_ext}"
        temp_path = temp_dir / temp_filename

        # Save uploaded file to temporary location with meaningful name
        with open(temp_path, 'wb') as temp_file:
            content = await file.read()
            temp_file.write(content)

        # Process the document with original filename
        result = grobid_service.process_document(temp_path, filename_stem=original_stem,
                                                 original_filename=file.filename)

        # Clean up temporary file in background
        background_tasks.add_task(cleanup_temp_file, temp_path)

        return ProcessingResult(
            success=True,
            message=f"Successfully processed {file.filename}",
            original_file=file.filename,
            pdf_file=result.get('pdf_file'),
            metadata=result.get('metadata', {}),
            local_tei_path=result.get('local_tei_path'),
            storage_success=result.get('storage_success', False),
            storage_errors=result.get('storage_errors', [])
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Processing failed for uploaded file", source="grobid_api", error=e)
        if temp_path and temp_path.exists():
            background_tasks.add_task(cleanup_temp_file, temp_path)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.post("/process/file", response_model=ProcessingResult)
async def process_local_file(
        file_path: str = Form(..., description="Path to local file to process")
):
    """
    Process a local file by its file path.

    Parameters
    ----------
    file_path : str
        Absolute path to the file to process.

    Returns
    -------
    ProcessingResult
        Processing results including metadata and file paths.
    """
    path = Path(file_path)

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    if not path.is_file():
        raise HTTPException(status_code=400, detail=f"Path is not a file: {file_path}")

    try:
        logger.info(f"Processing local file: {file_path}", source="grobid_api", event_type="process_local")

        result = grobid_service.process_document(path)

        return ProcessingResult(
            success=True,
            message=f"Successfully processed {path.name}",
            original_file=str(path),
            pdf_file=result.get('pdf_file'),
            metadata=result.get('metadata', {}),
            local_tei_path=result.get('local_tei_path'),
            storage_success=result.get('storage_success', False),
            storage_errors=result.get('storage_errors', [])
        )

    except Exception as e:
        logger.error(f"Failed to process local file: {file_path}", source="grobid_api", error=e,
                     event_type="process_local")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.post("/process/batch", response_model=BatchProcessingResult)
async def process_batch_files(
        background_tasks: BackgroundTasks,
        files: List[UploadFile] = File(..., description="Multiple files to process")
):
    """
    Process multiple uploaded files in batch.

    Parameters
    ----------
    files : List[UploadFile]
        List of files to process.

    Returns
    -------
    BatchProcessingResult
        Batch processing results with individual file results.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    logger.info(f"Starting batch processing of {len(files)} files", source="grobid_api", event_type="batch_process")

    results = []
    temp_files = []
    successful = 0
    failed = 0

    for file in files:
        if not file.filename:
            results.append(ProcessingResult(
                success=False,
                message="No filename provided",
                original_file=None
            ))
            failed += 1
            continue

        # Validate file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in grobid_service.supported_formats:
            results.append(ProcessingResult(
                success=False,
                message=f"Unsupported file type: {file_ext}",
                original_file=file.filename
            ))
            failed += 1
            continue

        temp_file = None
        try:
            # Get original filename stem for consistent naming
            original_stem = Path(file.filename).stem

            # Save uploaded file to temporary location with original name
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_path = Path(temp_file.name)
                temp_files.append(temp_path)

            # Process the document with original filename stem
            result = grobid_service.process_document(temp_path, filename_stem=original_stem)

            results.append(ProcessingResult(
                success=True,
                message=f"Successfully processed {file.filename}",
                original_file=file.filename,
                pdf_file=result.get('pdf_file'),
                metadata=result.get('metadata', {}),
                local_tei_path=result.get('local_tei_path'),
                storage_success=result.get('storage_success', False),
                storage_errors=result.get('storage_errors', [])
            ))
            successful += 1

        except Exception as e:
            logger.error(f"Failed to process file in batch: {file.filename}", source="grobid_api", error=e,
                         event_type="batch_process")

            results.append(ProcessingResult(
                success=False,
                message=f"Processing failed: {str(e)}",
                original_file=file.filename
            ))
            failed += 1

            # Clean up on error
            if temp_file and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)

    # Clean up all temp files in background
    for temp_path in temp_files:
        background_tasks.add_task(cleanup_temp_file, temp_path)

    logger.info(f"Batch processing completed: {successful} successful, {failed} failed", source="grobid_api",
                event_type="batch_process")

    return BatchProcessingResult(
        total_files=len(files),
        successful=successful,
        failed=failed,
        results=results
    )


# === File Download Endpoints ===

@router.get("/download/tei/{filename}")
async def download_tei_file(filename: str):
    """
    Download a processed TEI XML file.

    Parameters
    ----------
    filename : str
        Name of the TEI file to download.

    Returns
    -------
    FileResponse
        The requested TEI XML file.
    """
    from polymer_extractor.utils.paths import EXTRACTED_XML_DIR

    # Ensure safe filename (no path traversal)
    filename = os.path.basename(filename)
    if not filename.endswith('.tei.xml'):
        filename += '.tei.xml'

    file_path = Path(EXTRACTED_XML_DIR) / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"TEI file not found: {filename}")

    logger.info(f"Downloading TEI file: {filename}", source="grobid_api", event_type="download_tei")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type='application/xml'
    )


@router.get("/list/tei")
async def list_tei_files():
    """
    List all available processed TEI XML files.

    Returns
    -------
    Dict
        List of available TEI files with metadata.
    """
    from polymer_extractor.utils.paths import EXTRACTED_XML_DIR

    tei_dir = Path(EXTRACTED_XML_DIR)

    if not tei_dir.exists():
        return {"files": [], "count": 0}

    files = []
    for tei_file in tei_dir.glob("*.tei.xml"):
        stat = tei_file.stat()
        files.append({
            "filename": tei_file.name,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "path": str(tei_file)
        })

    # Sort by modification time (newest first)
    files.sort(key=lambda x: x["modified"], reverse=True)

    logger.info(f"Listed {len(files)} TEI files", source="grobid_api", event_type="list_tei")

    return {
        "files": files,
        "count": len(files)
    }


# === Health Check Endpoints ===

@router.get("/health")
async def health_check():
    """
    Comprehensive health check for GROBID service and dependencies.

    Returns
    -------
    Dict
        Health status of all components.
    """
    health_status = {
        "grobid_service": "unknown",
        "grobid_server": "unknown",
        "appwrite_storage": "unknown",
        "appwrite_database": "unknown",
        "overall": "unknown"
    }

    # Check GROBID server
    try:
        grobid_service.check_server_status()
        health_status["grobid_server"] = "healthy"
    except Exception:
        health_status["grobid_server"] = "unhealthy"

    # Check Appwrite storage
    try:
        grobid_service.bucket_manager.list_buckets()
        health_status["appwrite_storage"] = "healthy"
    except Exception:
        health_status["appwrite_storage"] = "unhealthy"

    # Check Appwrite database
    try:
        grobid_service.db_manager.list_collections()
        health_status["appwrite_database"] = "healthy"
    except Exception:
        health_status["appwrite_database"] = "unhealthy"

    # Overall service status
    health_status["grobid_service"] = "healthy"

    # Determine overall health
    unhealthy_components = [k for k, v in health_status.items() if v == "unhealthy" and k != "overall"]
    if not unhealthy_components:
        health_status["overall"] = "healthy"
    elif len(unhealthy_components) == 1 and "grobid_server" in unhealthy_components:
        health_status["overall"] = "degraded"  # Core processing works, just server down
    else:
        health_status["overall"] = "unhealthy"

    # Set appropriate HTTP status code
    status_code = 200 if health_status["overall"] in ["healthy", "degraded"] else 503

    return JSONResponse(
        content=health_status,
        status_code=status_code
    )


# === Utility Functions ===

def cleanup_temp_file(file_path: Path):
    """
    Background task to clean up temporary files.

    Parameters
    ----------
    file_path : Path
        Path to temporary file to delete.
    """
    try:
        if file_path.exists():
            os.unlink(file_path)
            logger.debug(f"Cleaned up temporary file: {file_path}", source="grobid_api", event_type="cleanup")
    except Exception as e:
        logger.warning(f"Failed to clean up temporary file: {file_path}", source="grobid_api", error=e,
                       event_type="cleanup")
