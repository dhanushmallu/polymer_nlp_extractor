"""
polymer_extractor/api/inference.py

Inference API Router for Polymer NLP Extractor.

Endpoints:
  - POST /api/infer/ensemble: Runs full ensemble inference on a processed TEI XML file.


"""

import os
from fastapi import APIRouter
from pydantic import BaseModel, Field

from polymer_extractor.services.ensemble_inference_service import EnsembleInferenceService
from polymer_extractor.utils.logging import Logger
from polymer_extractor.utils.paths import ServicePathHandler
from polymer_extractor.utils import responses as R

logger = Logger()
service_path_handler = ServicePathHandler()

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
    tei_path: str = Field(..., description="Path to processed TEI XML file (absolute, relative, storage, or URL).")


@router.post("/ensemble", summary="Run ensemble inference on a processed TEI XML file")
def run_ensemble_inference(req: InferenceRequest):
    """
    Runs the full ensemble inference pipeline on a given TEI XML file.
    
    Supports flexible path formats:
    - Absolute paths: /full/path/to/file.tei.xml
    - Relative paths: relative/path/file.tei.xml (from STORAGE_PATH root)
    - Storage paths: processed_xml/file.tei.xml
    - URLs: https://example.com/file.tei.xml (downloads to storage/downloads/)

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

    try:
        # Resolve the input path using flexible path handling
        local_path, storage_path = service_path_handler.resolve_input_path(req.tei_path, file_type="processed_xml")

        if not os.path.exists(local_path):
            logger.error(
                message=f"TEI file not found: {req.tei_path}",
                source="api.inference.run_ensemble_inference",
                category="api",
                event_type="file_not_found"
            )
            raise R.raise_http(
                404,
                status_label="failure",
                message="TEI file not found",
                details={"path": req.tei_path, "resolved": local_path},
            )

        service = EnsembleInferenceService()
        result = service.run_inference(local_path)
        result.update(
            {
                "input_path": req.tei_path,
                "resolved_local_path": local_path,
                "resolved_storage_path": storage_path,
            }
        )

        logger.info(
            message=f"Inference completed successfully for {req.tei_path}",
            source="api.inference.run_ensemble_inference",
            category="api",
            event_type="request_completed",
        )
        return R.ok(result, message="Inference completed")

    except Exception as e:
        logger.error(
            message=f"Inference failed for {req.tei_path}: {e}",
            source="api.inference.run_ensemble_inference",
            error=e,
            category="system",
            event_type="inference_error",
        )
        raise R.raise_http(500, status_label="error", message="Inference failed", details={"error": str(e)})
