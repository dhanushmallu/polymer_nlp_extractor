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

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from polymer_extractor.services.tei_processing_service import TEIProcessingService
from polymer_extractor.services.tokenizer_service import TokenizerService
from polymer_extractor.services.token_packing_service import TokenPackingService
from polymer_extractor.utils.logging import Logger

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
        description="Absolute filesystem path to cleaned TEI XML file."
    )


class TEIProcessRequest(BaseModel):
    """
    Request body for /api/preprocess/tei
    """
    tei_path: str = Field(
        ...,
        description="Absolute filesystem path to the TEI XML file for cleaning and metadata extraction."
    )


@router.post(
    "/tokenize",
    summary="Audit and extend all tokenizers (standalone testing)"
)
def audit_and_extend_tokenizers(force: Optional[bool] = Query(
    default=False,
    description="Force re-audit and rebuild even if lexicon unchanged."
)) -> Dict[str, Any]:
    """
    Audit and extend tokenizers for all ensemble models.

    Parameters
    ----------
    force : bool, optional
        Force rebuild even if lexicon unchanged. Defaults to False.

    Returns
    -------
    dict
        Audit results for each model.
    """
    logger.info(
        message=f"Received tokenizer audit request with force={force}",
        source="api.preprocessing.audit_and_extend_tokenizers",
        category="api",
        event_type="request_received"
    )
    try:
        tokenizer_service = TokenizerService()
        audit_results = tokenizer_service.audit_and_extend_all(force=force)

        logger.info(
            message="Tokenizer audit completed successfully.",
            source="api.preprocessing.audit_and_extend_tokenizers",
            category="api",
            event_type="request_completed"
        )
        return {
            "success": True,
            "message": "All tokenizers audited and extended successfully.",
            "force_rebuild": force,
            "audit_results": audit_results
        }
    except Exception as e:
        logger.error(
            message=f"Tokenizer audit failed: {e}",
            source="api.preprocessing.audit_and_extend_tokenizers",
            error=e,
            category="system",
            event_type="tokenizer_audit_error"
        )
        raise HTTPException(status_code=500, detail=f"Tokenizer audit failed: {str(e)}")


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

    if not os.path.isabs(req.tei_path) or not os.path.exists(req.tei_path):
        logger.error(
            message=f"TEI file not found: {req.tei_path}",
            source="api.preprocessing.preprocess_tei",
            category="api",
            event_type="file_not_found"
        )
        raise HTTPException(status_code=404, detail=f"TEI file not found: {req.tei_path}")

    try:
        service = TEIProcessingService()
        result = service.process(req.tei_path)
        logger.info(
            message=f"TEI processing completed for {req.tei_path}",
            source="api.preprocessing.preprocess_tei",
            category="api",
            event_type="request_completed"
        )
        return result
    except Exception as e:
        logger.error(
            message=f"TEI processing failed: {e}",
            source="api.preprocessing.preprocess_tei",
            error=e,
            category="system",
            event_type="processing_error"
        )
        raise HTTPException(status_code=500, detail=f"TEI processing failed: {str(e)}")

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
        raise HTTPException(status_code=404, detail=f"TEI file not found: {req.tei_path}")

    try:
        service = TokenPackingService()
        result = service.process(tei_path=req.tei_path)

        logger.info(
            message=f"Token packing completed for all models on {req.tei_path}",
            source="api.preprocessing.pack_token_windows",
            category="api",
            event_type="request_completed"
        )

        return result

    except Exception as e:
        logger.error(
            message=f"Token packing failed: {e}",
            source="api.preprocessing.pack_token_windows",
            error=e,
            category="system",
            event_type="packing_failed"
        )
        raise HTTPException(status_code=500, detail=f"Token packing failed: {str(e)}")
