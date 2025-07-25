# polymer_extractor/api/groundtruth.py

"""
Ground Truth API for Polymer NLP Extractor.

Provides REST endpoints for:
- Uploading ground truth datasets (CSV/JSON)
- Listing available datasets
- Retrieving a specific dataset
- Deleting datasets and their metadata

Endpoints:
- POST   /api/groundtruth/upload
- GET    /api/groundtruth/list
- GET    /api/groundtruth/get/{dataset_id}
- DELETE /api/groundtruth/remove/{dataset_id}
"""

from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

from polymer_extractor.services.groundtruth_service import GroundTruthService
from polymer_extractor.utils.logging import Logger

logger = Logger()

router = APIRouter(
    prefix="/groundtruth",
    tags=["Ground Truth"]
)

# Initialize GroundTruthService
gt_service = GroundTruthService()

# === Pydantic Models ===

class UploadResponse(BaseModel):
    success: bool
    message: str
    dataset_name: str
    metadata: Dict[str, Any]
    local_path: str
    storage_success: bool
    storage_errors: List[str]


class DatasetListResponse(BaseModel):
    count: int
    datasets: List[Dict[str, Any]]


class DeleteResponse(BaseModel):
    success: bool
    message: str
    dataset_id: str


# === API Endpoints ===

@router.post("/upload", response_model=UploadResponse)
async def upload_ground_truth(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Ground truth dataset (CSV or JSON)"),
    target_input: str = None
):
    """
    Upload and process a ground truth dataset.

    Supports CSV and JSON file formats. Automatically cleans, aligns, and
    standardizes data. Saves processed dataset locally and uploads to Appwrite.

    Parameters
    ----------
    file : UploadFile
        Uploaded ground truth file.
    target_input : str, optional
        Target input filename that this ground truth is associated with.
        This allows you to specify which input file this ground truth data
        is designed to test against (e.g., "057.pdf", "research_paper.xml").

    Returns
    -------
    UploadResponse
        Metadata and status of the upload and processing.
    """
    logger.info(f"Received upload request for ground truth file: {file.filename}", source="groundtruth_api")

    # Validate file extension
    allowed_extensions = {'.csv', '.json'}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Allowed types: {', '.join(allowed_extensions)}"
        )

    # Save uploaded file to temp location
    temp_dir = gt_service.ground_truth_dir / "uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file_path = temp_dir / file.filename

    try:
        with open(temp_file_path, "wb") as buffer:
            buffer.write(await file.read())

        logger.info(f"Saved uploaded file to temporary path: {temp_file_path}", source="groundtruth_api")

        # Process file with optional target_input
        result = gt_service.process_ground_truth_file(temp_file_path, target_input=target_input)

        # Clean up temp file in background
        background_tasks.add_task(temp_file_path.unlink)

        return UploadResponse(
            success=True,
            message=f"Successfully processed and stored dataset: {file.filename}",
            dataset_name=Path(result['local_path']).stem,
            metadata=result['metadata'],
            local_path=result['local_path'],
            storage_success=result['storage_success'],
            storage_errors=result['storage_errors']
        )

    except Exception as e:
        logger.error(f"Failed to process ground truth file: {file.filename}", source="groundtruth_api", error=e)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.get("/list", response_model=DatasetListResponse)
async def list_ground_truth_datasets():
    """
    List all available processed ground truth datasets.

    Returns
    -------
    DatasetListResponse
        List of datasets with metadata.
    """
    try:
        datasets = gt_service.list_ground_truth_datasets()
        return DatasetListResponse(count=len(datasets), datasets=datasets)
    except Exception as e:
        logger.error("Failed to list ground truth datasets", source="groundtruth_api", error=e)
        raise HTTPException(status_code=500, detail=f"Failed to list datasets: {str(e)}")


@router.get("/get/{dataset_id}", response_class=FileResponse)
async def download_ground_truth_dataset(dataset_id: str):
    """
    Download a specific processed ground truth dataset as CSV.

    Parameters
    ----------
    dataset_id : str
        Unique identifier of the dataset.

    Returns
    -------
    FileResponse
        Processed CSV file.
    """
    try:
        df = gt_service.get_ground_truth_dataset(dataset_id)
        temp_file = gt_service.ground_truth_dir / f"{dataset_id}_download.csv"
        df.to_csv(temp_file, index=False)

        logger.info(f"Prepared dataset for download: {dataset_id}", source="groundtruth_api")
        return FileResponse(
            path=temp_file,
            filename=temp_file.name,
            media_type='text/csv',
            background=lambda: temp_file.unlink()
        )

    except Exception as e:
        logger.error(f"Failed to retrieve ground truth dataset: {dataset_id}", source="groundtruth_api", error=e)
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")


@router.delete("/remove/{dataset_id}", response_model=DeleteResponse)
async def delete_ground_truth_dataset(dataset_id: str):
    """
    Delete a specific ground truth dataset and its metadata.

    Parameters
    ----------
    dataset_id : str
        Unique identifier of the dataset.

    Returns
    -------
    DeleteResponse
        Confirmation of deletion.
    """
    try:
        # Delete metadata from Appwrite
        gt_service.db_manager.delete_document("datasets_metadata", dataset_id)
        logger.info(f"Deleted dataset metadata: {dataset_id}", source="groundtruth_api")

        # Delete local and cloud file (best effort)
        metadata = gt_service.db_manager.get_document("datasets_metadata", dataset_id)
        local_path = Path(metadata.get('local_path', ''))
        if local_path.exists():
            local_path.unlink()
            logger.info(f"Deleted local ground truth file: {local_path}", source="groundtruth_api")

        file_id = metadata.get('appwrite_file_id')
        if file_id:
            gt_service.bucket_manager.delete_file("datasets_bucket", file_id)
            logger.info(f"Deleted ground truth file from Appwrite: {file_id}", source="groundtruth_api")

        return DeleteResponse(
            success=True,
            message=f"Dataset deleted successfully: {dataset_id}",
            dataset_id=dataset_id
        )

    except Exception as e:
        logger.error(f"Failed to delete ground truth dataset: {dataset_id}", source="groundtruth_api", error=e)
        raise HTTPException(status_code=500, detail=f"Failed to delete dataset: {str(e)}")
