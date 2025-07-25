"""
polymer_extractor/api/inference.py

Inference API Router for Polymer NLP Extractor.

Endpoints:
  - POST /api/infer/ensemble: Runs full ensemble inference on a processed TEI XML file.


"""

import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from polymer_extractor.services.ensemble_inference_service import EnsembleInferenceService
from polymer_extractor.utils.logging import Logger

logger = Logger()

router = APIRouter(
    prefix="/infer",
    tags=["Inference"],
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "File Not Found"},
        500: {"description": "Internal Server Error"}
    }
)

class InferenceRequest(BaseModel):
    """Request body for /api/infer/ensemble"""
    tei_path: str = Field(..., description="Absolute path to processed TEI XML file.")


@router.post("/ensemble", summary="Run ensemble inference on a processed TEI XML file")
def run_ensemble_inference(req: InferenceRequest):
    """
    Runs the full ensemble inference pipeline on a given TEI XML file.

    Steps:
    --------
    1. Loads fine-tuned models and tokenizers (extended if available).
    2. Performs token packing (sentence-aware windowing).
    3. Runs inference for each model and collects predictions.
    4. Applies confidence-weighted ensemble voting with postprocessing.
    5. Saves final results to Appwrite and locally.

    Returns
    -------
    dict
        Inference summary including models used, number of entities extracted, and result file path.
    """
    logger.info(
        message=f"Received inference request for {req.tei_path}",
        source="api.inference.run_ensemble_inference",
        category="api",
        event_type="request_received"
    )

    if not os.path.isabs(req.tei_path) or not os.path.exists(req.tei_path):
        logger.error(
            message=f"TEI file not found: {req.tei_path}",
            source="api.inference.run_ensemble_inference",
            category="api",
            event_type="file_not_found"
        )
        raise HTTPException(status_code=404, detail=f"TEI file not found: {req.tei_path}")

    try:
        service = EnsembleInferenceService()
        result = service.run_inference(req.tei_path)

        logger.info(
            message=f"Inference completed successfully for {req.tei_path}",
            source="api.inference.run_ensemble_inference",
            category="api",
            event_type="request_completed"
        )
        return result

    except Exception as e:
        logger.error(
            message=f"Inference failed for {req.tei_path}: {e}",
            source="api.inference.run_ensemble_inference",
            error=e,
            category="system",
            event_type="inference_error"
        )
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")
