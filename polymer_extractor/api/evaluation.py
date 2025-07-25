"""
polymer_extractor/api/evaluation.py

Evaluation API Router for Polymer NLP Extractor.

Endpoints:
---------
- POST /api/evaluate: Evaluate extracted entities against ground truth

"""

import os
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from polymer_extractor.services.evaluation_service import EvaluationService
from polymer_extractor.utils.logging import Logger

router = APIRouter(
    prefix="/evaluate",
    tags=["Evaluation"],
    responses={
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"}
    }
)

logger = Logger()


class EvaluationRequest(BaseModel):
    tei_path: str = Field(..., description="Full path to TEI XML file that was evaluated")
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

    Parameters
    ----------
    req : EvaluationRequest
        Contains TEI file path and optional span match threshold.

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

    if not os.path.exists(req.tei_path):
        raise HTTPException(status_code=404, detail=f"TEI file not found: {req.tei_path}")

    try:
        evaluator = EvaluationService()
        results = evaluator.evaluate(tei_path=req.tei_path, span_match_threshold=req.span_match_threshold)

        logger.info(
            message=f"Evaluation completed for {req.tei_path}",
            source="api.evaluation.evaluate_entities",
            category="api",
            event_type="request_completed"
        )
        return results

    except Exception as e:
        logger.error(
            message=f"Evaluation failed: {e}",
            source="api.evaluation.evaluate_entities",
            error=e,
            category="system",
            event_type="evaluation_failed"
        )
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")
