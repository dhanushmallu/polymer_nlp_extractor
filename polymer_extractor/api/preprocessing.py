"""
polymer_extractor.api.preprocessing

Preprocessing API Router for Polymer NLP Extractor.

Endpoints:
  - POST /api/preprocess/tei: Clean and prepare TEI XML (standalone testing)
  - POST /api/preprocess/tokenize: Audit and extend tokenizers (standalone testing)
  - POST /api/preprocess/packtoken: Pack tokenized sentences into windows (standalone testing)
  - POST /api/preprocess: Full pipeline (TEI → Tokenizer Audit → Token Packing)


"""

import os
from typing import Dict, Any, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from polymer_extractor.services.tei_processing_service import TEIProcessingService
# Phase 0D: Removed TokenizerService import as tokenization is now handled in training notebook
from polymer_extractor.services.token_packing_service import TokenPackingService
from polymer_extractor.utils.logging import Logger
from polymer_extractor.utils import responses as R

logger = Logger()

router = APIRouter(
    prefix="/preprocess",
    tags=["Preprocessing"],
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "File not found"},
        500: {"description": "Internal Server Error"},
    },
)


class TokenPackRequest(BaseModel):
    """
    Request body for /api/preprocess/tokenpack
    """
    tei_path: str = Field(
        ...,
        description="Path to cleaned TEI XML file. Accepts: relative paths, absolute paths, storage paths, or URLs."
    )


class TEIProcessRequest(BaseModel):
    """
    Request body for /api/preprocess/tei
    """
    tei_path: str = Field(
        ...,
        description="Path to the TEI XML file for cleaning and metadata extraction. Accepts: relative paths, absolute paths, storage paths, or URLs."
    )


@router.post(
    "/tokenize",
    summary="Deprecated - Tokenizer management moved to training notebook",
    deprecated=True
)
def deprecated_tokenizer_audit(force: Optional[bool] = Query(
    default=False,
    description="Deprecated parameter - tokenization is now handled in training notebook."
)) -> Dict[str, Any]:
    """
    Deprecated endpoint - tokenizer management is now handled exclusively by the training notebook.
    
    Phase 0D: This endpoint has been removed as tokenizer extension and management
    is now performed during model training in the Jupyter notebook.

    Parameters
    ----------
    force : bool, optional
        Deprecated parameter.

    Returns
    -------
    dict
        Deprecation notice and redirect information.
    """
    logger.info(
        message=f"Deprecated tokenizer audit endpoint accessed",
        source="api.preprocessing.deprecated_tokenizer_audit",
        category="api",
        event_type="deprecated_access"
    )
    
    return {
        "status": "deprecated",
        "message": "Tokenizer audit API has been removed in Phase 0D. Use the training notebook instead.",
        "redirect": "Use notebooks/model_training_finetuning.ipynb for tokenizer management",
        "phase": "0D",
        "training_location": "notebooks/model_training_finetuning.ipynb",
        "reason": "Tokenizer extension is now performed during model training for consistency"
    }


@router.post(
    "/tei",
    summary="Clean and process a TEI XML file for downstream tasks"
)
def preprocess_tei(req: TEIProcessRequest) -> Dict[str, Any]:
    """
    Clean and process a TEI XML file for downstream tasks.

    Steps:
    -------
      1. Clean TEI XML (remove tags, preserve sentences)
      2. Extract metadata (DOI, title, authors, etc.)
      3. Save cleaned text locally and to Appwrite
    """
    logger.info(
        message=f"Received TEI processing request: tei_path={req.tei_path}",
        source="api.preprocessing.preprocess_tei",
        category="api",
        event_type="request_received"
    )

    # Use flexible path resolution instead of absolute path requirement
    from polymer_extractor.utils.paths import service_path_handler
    
    try:
        # Determine file type from the input path for proper resolution
        file_type = "processed_xml"  # Default for TEI processing endpoint
        
        # Smart file type detection based on path patterns
        if req.tei_path.startswith("extracted_xml/"):
            file_type = "extracted_xml"
        elif req.tei_path.startswith("processed_xml/"):
            file_type = "processed_xml"
        elif "extracted_xml" in req.tei_path:
            file_type = "extracted_xml"
        elif "processed_xml" in req.tei_path or "_cleaned" in req.tei_path:
            file_type = "processed_xml"
        
        # Resolve the input path to local filesystem path for processing
        local_path, storage_path = service_path_handler.resolve_input_path(req.tei_path, file_type)
        
        # Check if the local file exists (for actual processing)
        if not os.path.exists(local_path):
            logger.error(
                message=f"TEI file not found at resolved path: {local_path} (from input: {req.tei_path})",
                source="api.preprocessing.preprocess_tei",
                category="api",
                event_type="file_not_found"
            )
            raise R.raise_http(404, status_label="failure", message="TEI file not found", details={"input": req.tei_path, "resolved": local_path})
        
        logger.info(
            message=f"Processing TEI file: {req.tei_path} -> {local_path}",
            source="api.preprocessing.preprocess_tei",
            category="api",
            event_type="path_resolved"
        )
        
    except Exception as e:
        logger.error(
            message=f"Failed to resolve TEI path: {req.tei_path}",
            source="api.preprocessing.preprocess_tei",
            category="api",
            event_type="path_resolution_failed",
            error=e
        )
        raise R.raise_http(400, status_label="failure", message="Invalid path format", details={"input": req.tei_path})

    try:
        service = TEIProcessingService()
        # Pass the resolved local path to the service
        result = service.process(local_path)
        
        # Enhance result with path information
        result["input_path"] = req.tei_path
        result["resolved_local_path"] = local_path
        result["resolved_storage_path"] = storage_path
        
        logger.info(
            message=f"TEI processing completed for {req.tei_path}",
            source="api.preprocessing.preprocess_tei",
            category="api",
            event_type="request_completed",
        )
        return R.ok(result, message="TEI processing completed")
    except Exception as e:
        logger.error(
            message=f"TEI processing failed: {e}",
            source="api.preprocessing.preprocess_tei",
            error=e,
            category="system",
            event_type="processing_error",
        )
        raise R.raise_http(500, status_label="error", message="TEI processing failed", details={"error": str(e)})

@router.post(
    "/tokenpack",
    summary="Pack tokenized sentences into model-compatible token windows"
)
def pack_token_windows(req: TokenPackRequest) -> Dict[str, Any]:
    """
    Perform token packing for a TEI file across all ensemble models.

    Parameters
    ----------
    req : TokenPackRequest
        The request body with TEI path.

    Returns
    -------
    dict
        Summary of saved sentence and window files for all models.
    """
    logger.info(
        message=f"Received token packing request: tei_path='{req.tei_path}'",
        source="api.preprocessing.pack_token_windows",
        category="api",
        event_type="request_received"
    )

    if not os.path.isfile(req.tei_path):
        logger.error(
            message=f"TEI file does not exist: {req.tei_path}",
            source="api.preprocessing.pack_token_windows",
            category="api",
            event_type="file_missing"
        )
        raise R.raise_http(404, status_label="failure", message="TEI file not found", details={"path": req.tei_path})

    try:
        service = TokenPackingService()
        result = service.process(tei_path=req.tei_path)

        logger.info(
            message=f"Token packing completed for all models on {req.tei_path}",
            source="api.preprocessing.pack_token_windows",
            category="api",
            event_type="request_completed",
        )
        return R.ok(result, message="Token packing completed")

    except Exception as e:
        logger.error(
            message=f"Token packing failed: {e}",
            source="api.preprocessing.pack_token_windows",
            error=e,
            category="system",
            event_type="packing_failed"
        )
        raise R.raise_http(500, status_label="error", message="Token packing failed", details={"error": str(e)})
