"""
polymer_extractor/api/evaluation.py

Evaluation API Router for Polymer NLP Extractor.

Endpoints:
---------
- POST /api/evaluate: Evaluate extracted entities against ground truth

"""

import os
from typing import Optional, Dict, Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from polymer_extractor.services.evaluation_service import EvaluationService
from polymer_extractor.utils.logging import Logger
from polymer_extractor.utils.paths import ServicePathHandler
from polymer_extractor.utils import responses as R

router = APIRouter(
    prefix="/evaluate",
    tags=["Evaluation"],
    responses={
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"}
    }
)

logger = Logger()
service_path_handler = ServicePathHandler()


class EvaluationRequest(BaseModel):
    tei_path: str = Field(..., description="Path to TEI XML file (absolute, relative, storage, or URL)")
    span_match_threshold: Optional[float] = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Span matching threshold (0.0–1.0, default=0.70)"
    )


@router.post("/", summary="Evaluate entity extraction against ground truth")
def evaluate_entities(req: EvaluationRequest) -> Dict[str, Any]:
    """
    Compare ensemble inference predictions against ground truth test set.
    
    Supports flexible path formats:
    - Absolute paths: /full/path/to/file.tei.xml
    - Relative paths: relative/path/file.tei.xml (from STORAGE_PATH root)
    - Storage paths: processed_xml/file.tei.xml  
    - URLs: https://example.com/file.tei.xml (downloads to storage/downloads/)

    Parameters
    ----------
    req : EvaluationRequest
        Contains TEI file path (flexible format) and optional span match threshold.

    Returns
    -------
    dict
        Evaluation summary including metrics, counts, and exported CSV path.
    """
    logger.info(
        message=f"Received evaluation request: tei_path={req.tei_path}",
        source="api.evaluation.evaluate_entities",
        category="api",
        event_type="request_received"
    )

    try:
        # Resolve the input path using flexible path handling
        resolved_path = service_path_handler.resolve_input_path(req.tei_path)
        
        if not resolved_path.exists():
            raise R.raise_http(404, status_label="failure", message="TEI file not found", details={"path": req.tei_path})

        evaluator = EvaluationService()
        results = evaluator.evaluate(tei_path=str(resolved_path), span_match_threshold=req.span_match_threshold)

        logger.info(
            message=f"Evaluation completed for {req.tei_path}",
            source="api.evaluation.evaluate_entities",
            category="api",
            event_type="request_completed"
        )
        return R.ok(results, message="Evaluation completed")
    except Exception as e:
        logger.error(
            message=f"Evaluation failed: {e}",
            source="api.evaluation.evaluate_entities",
            error=e,
            category="system",
            event_type="evaluation_failed"
        )
        raise R.raise_http(500, status_label="error", message="Evaluation failed", details={"error": str(e)})
