"""
Models Synchronization API

Summary
-------
Provides REST API endpoints for GitHub-based models synchronization functionality.
Handles models and tokenizers downloads, version validation, and sync status checking.

This API supports:
- Synchronizing models from GitHub repositories
- Validating model-tokenizer version compatibility
- Checking sync status and current models state
- Force redownload with atomic rollback on failure

Examples
--------
POST /api/models/sync - Sync models from GitHub
GET /api/models/validate - Validate existing models
GET /api/models/status - Check current models state

Notes
-----
- Requires proper GitHub configuration in environment variables
- All operations are atomic with rollback on failure
- Integrates with protected bucket logic for models storage
- Provides detailed progress and error reporting
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import traceback

from polymer_extractor.services.models_sync_service import ModelsSyncService
from polymer_extractor.utils.logging import Logger

# Create router for models sync API
router = APIRouter()
logger = Logger()


class ModelsSyncRequest(BaseModel):
    """Request model for models sync operation."""
    force_redownload: bool = False


class ModelsSyncResponse(BaseModel):
    """Response model for models sync operation."""
    success: bool
    models_synced: int
    tokenizers_synced: int
    version_validated: bool
    download_details: Dict[str, Any] = {}
    validation_results: List[Dict[str, Any]] = []
    errors: List[str] = []
    duration_seconds: float


class ModelsValidationResponse(BaseModel):
    """Response model for models validation operation."""
    valid: bool
    models_checked: int
    compatible_pairs: int
    incompatible_pairs: int
    missing_components: List[str] = []
    validation_details: List[Dict[str, Any]] = []
    recommended_actions: List[str] = []


class ModelsStatusResponse(BaseModel):
    """Response model for models status operation."""
    models_directory_exists: bool
    models_count: int
    tokenizers_count: int
    github_configured: bool
    sync_ready: bool
    up_to_date: bool
    version_validated: bool
    configuration_status: Dict[str, str]
    configuration_errors: List[str] = []


@router.post('/models/sync', response_model=ModelsSyncResponse, 
            summary="Sync models from GitHub",
            description="Download and synchronize models and tokenizers from GitHub repositories")
async def sync_models(request: ModelsSyncRequest = ModelsSyncRequest()) -> ModelsSyncResponse:
    """
    Synchronize models and tokenizers from GitHub repositories.
    
    Summary
    -------
    Downloads latest models and tokenizers from configured GitHub repositories,
    validates version compatibility, and updates local models directory atomically.
    
    Parameters
    ----------
    request : ModelsSyncRequest
        Sync request parameters including force_redownload option
    
    Returns
    -------
    ModelsSyncResponse
        Sync results including counts, validation status, and any errors
    
    Raises
    ------
    HTTPException
        422: GitHub configuration missing or invalid
        500: Internal server error during sync
    
    Examples
    --------
    POST /api/models/sync
    {
        "force_redownload": true
    }
    
    Notes
    -----
    - Atomic operation: either fully succeeds or rolls back
    - Preserves existing models on failure
    - Requires GITHUB_TOKEN, TOKENIZERS_REMOTE_URL, FINETUNED_REMOTE_URL
    """
    try:
        logger.info("Starting models sync via API", source="models_sync_api", 
                   force_redownload=request.force_redownload)
        
        # Initialize sync service and perform sync
        sync_service = ModelsSyncService(logger=logger)
        result = sync_service.sync_models_from_github(force_redownload=request.force_redownload)
        
        # Create response
        response = ModelsSyncResponse(**result)
        
        if result["success"]:
            logger.info("Models sync API completed successfully", source="models_sync_api",
                       models_synced=result["models_synced"], 
                       tokenizers_synced=result["tokenizers_synced"])
        else:
            # Check if it's a configuration error vs runtime error
            config_errors = ["GITHUB_TOKEN", "TOKENIZERS_REMOTE_URL", "FINETUNED_REMOTE_URL"]
            is_config_error = any(error_keyword in str(result["errors"]) for error_keyword in config_errors)
            
            if is_config_error:
                logger.error("Models sync API failed due to configuration", source="models_sync_api", 
                           errors=result["errors"])
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "message": "GitHub configuration missing or invalid",
                        "errors": result["errors"]
                    }
                )
            else:
                logger.error("Models sync API failed", source="models_sync_api", 
                           errors=result["errors"])
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "message": "Internal server error during models sync",
                        "errors": result["errors"]
                    }
                )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Unexpected error in models sync API: {str(e)}"
        logger.error(error_msg, source="models_sync_api", error=str(e), 
                    traceback=traceback.format_exc())
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": error_msg,
                "errors": [error_msg]
            }
        )


@router.get('/models/validate', response_model=ModelsValidationResponse,
           summary="Validate models versions",
           description="Validate version compatibility between existing models and tokenizers")
async def validate_models() -> ModelsValidationResponse:
    """
    Validate version compatibility between existing models and tokenizers.
    
    Summary
    -------
    Checks all models and tokenizers in the models directory for version
    compatibility and structural completeness. Provides detailed analysis
    of each model-tokenizer pair.
    
    Returns
    -------
    ModelsValidationResponse
        Validation results including compatibility status and recommendations
    
    Raises
    ------
    HTTPException
        500: Internal server error during validation
    
    Examples
    --------
    GET /api/models/validate
    
    Notes
    -----
    - Checks for required model files (config.json, pytorch_model.bin)
    - Validates tokenizer files (tokenizer_config.json, vocab.txt)
    - Verifies version metadata consistency
    - Provides actionable recommendations for fixes
    """
    try:
        logger.info("Starting models validation via API", source="models_sync_api")
        
        # Initialize sync service and perform validation
        sync_service = ModelsSyncService(logger=logger)
        result = sync_service.validate_models_versions()
        
        # Create response
        response = ModelsValidationResponse(**result)
        
        if result["valid"]:
            logger.info("Models validation API completed successfully", source="models_sync_api",
                       models_checked=result["models_checked"],
                       compatible_pairs=result["compatible_pairs"])
        else:
            logger.warning("Models validation API found issues", source="models_sync_api",
                          incompatible_pairs=result["incompatible_pairs"],
                          missing_components=result["missing_components"])
        
        return response
        
    except Exception as e:
        error_msg = f"Unexpected error in models validation API: {str(e)}"
        logger.error(error_msg, source="models_sync_api", error=str(e), 
                    traceback=traceback.format_exc())
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": error_msg,
                "errors": [error_msg]
            }
        )


@router.get('/models/status', response_model=ModelsStatusResponse,
           summary="Get models status",
           description="Get current status of models directory and GitHub sync configuration")
async def get_models_status() -> ModelsStatusResponse:
    """
    Get current status of models directory and GitHub sync configuration.
    
    Summary
    -------
    Provides comprehensive status information about the current models directory,
    GitHub configuration, and sync readiness. Useful for debugging and monitoring.
    
    Returns
    -------
    ModelsStatusResponse
        Status information including directory state and configuration
    
    Raises
    ------
    HTTPException
        500: Internal server error during status check
    
    Examples
    --------
    GET /api/models/status
    
    Notes
    -----
    - Does not trigger any downloads or modifications
    - Safe to call frequently for monitoring
    - Provides detailed configuration diagnostics
    """
    try:
        logger.info("Getting models status via API", source="models_sync_api")
        
        # Initialize sync service and get status
        sync_service = ModelsSyncService(logger=logger)
        
        # Check current models state
        current_state = sync_service._check_current_models_state()
        
        # Check GitHub configuration
        config_validation = sync_service._validate_github_config()
        
        # Build comprehensive status
        response = ModelsStatusResponse(
            models_directory_exists=current_state["models_count"] > 0 or current_state["tokenizers_count"] > 0,
            models_count=current_state["models_count"],
            tokenizers_count=current_state["tokenizers_count"],
            github_configured=config_validation["valid"],
            sync_ready=config_validation["valid"],
            up_to_date=current_state["up_to_date"],
            version_validated=current_state["version_validated"],
            configuration_status={
                "github_token": "configured" if sync_service.github_token else "missing",
                "tokenizers_url": "configured" if sync_service.tokenizers_url else "missing",
                "finetuned_url": "configured" if sync_service.finetuned_url else "missing",
                "models_version": sync_service.models_version
            },
            configuration_errors=config_validation.get("errors", [])
        )
        
        logger.info("Models status API completed successfully", source="models_sync_api",
                   models_count=response.models_count,
                   tokenizers_count=response.tokenizers_count,
                   github_configured=response.github_configured)
        
        return response
        
    except Exception as e:
        error_msg = f"Unexpected error in models status API: {str(e)}"
        logger.error(error_msg, source="models_sync_api", error=str(e), 
                    traceback=traceback.format_exc())
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": error_msg,
                "errors": [error_msg]
            }
        )
