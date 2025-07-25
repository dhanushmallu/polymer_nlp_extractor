""""""

"""
polymer_extractor.api.finetune

Fine-Tuning API Router for Polymer NLP Extractor.

Endpoints:
  - POST /api/finetune: Trigger fine-tuning of one or all models


"""

import os
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

# from polymer_extractor.services.fine_tune_service import FineTuneService
from polymer_extractor.model_config import ENSEMBLE_MODELS
from polymer_extractor.utils.logging import Logger

logger = Logger()

router = APIRouter(
    prefix="/finetune",
    tags=["Fine-Tuning"],
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "Model or dataset not found"},
        500: {"description": "Internal Server Error"},
    },
)


# class FineTuneRequest(BaseModel):
#     """
#     Request body for /api/finetune
#     """
#     model_name: Optional[str] = Field(
#         default=None,
#         description="Optional model name to fine-tune (defaults to all ensemble models)"
#     )
#     epochs: Optional[int] = Field(
#         default=None,
#         description="Override number of epochs for this run"
#     )
#     learning_rate: Optional[float] = Field(
#         default=None,
#         description="Override learning rate for this run"
#     )
#     weight_decay: Optional[float] = Field(
#         default=None,
#         description="Override weight decay for this run"
#     )


# @router.post(
#     "/",
#     summary="Trigger fine-tuning of NLP models",
#     response_description="Fine-tuning summary"
# )
# def run_finetune(req: FineTuneRequest) -> Dict[str, Any]:
#     """
#     Fine-tune one or all ensemble models.

#     Parameters
#     ----------
#     req : FineTuneRequest
#         - model_name: Optional[str]
#         - epochs: Optional[int]
#         - learning_rate: Optional[float]
#         - weight_decay: Optional[float]

#     Returns
#     -------
#     dict
#         Summary of fine-tuned models and their locations
#     """
#     logger.info(
#         message=f"Received fine-tune request: model={req.model_name or 'ALL'}, "
#                 f"epochs={req.epochs}, lr={req.learning_rate}, wd={req.weight_decay}",
#         source="api.finetune.run_finetune",
#         category="api",
#         event_type="request_received"
#     )

#     try:
#         service = FineTuneService()

#         if req.model_name:
#             # Validate model existence
#             model_cfg = next((m for m in ENSEMBLE_MODELS if m.name == req.model_name), None)
#             if not model_cfg:
#                 logger.error(
#                     message=f"Model not found: {req.model_name}",
#                     source="api.finetune.run_finetune",
#                     category="api",
#                     event_type="model_not_found"
#                 )
#                 raise HTTPException(status_code=404, detail=f"Model '{req.model_name}' not found.")

#             logger.info(
#                 message=f"Fine-tuning single model: {req.model_name}",
#                 source="api.finetune.run_finetune",
#                 category="api",
#                 event_type="single_model_start"
#             )
#             result = service._fine_tune_model(
#                 model_cfg,
#                 dataset=service._generate_synthetic_dataset(num_samples=25000),
#                 model_dir=os.path.join(service.output_dir, f"{service._sanitize_name(req.model_name)}_finetuned")
#             )
#             return {
#                 "success": True,
#                 "message": f"Fine-tuning completed for model: {req.model_name}",
#                 "result": result
#             }

#         # Fine-tune all models
#         logger.info(
#             "Fine-tuning all ensemble models...",
#             source="api.finetune.run_finetune",
#             category="api",
#             event_type="all_models_start"
#         )
#         results = service.run()
#         return {
#             "success": True,
#             "message": "Fine-tuning completed for all models.",
#             "results": results
#         }

#     except Exception as e:
#         logger.error(
#             message=f"Fine-tuning failed: {e}",
#             source="api.finetune.run_finetune",
#             error=e,
#             category="system",
#             event_type="finetune_error"
#         )
#         raise HTTPException(status_code=500, detail=f"Fine-tuning failed: {str(e)}")
