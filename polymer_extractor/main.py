from fastapi import FastAPI

from api import groundtruth, preprocessing, setup, grobid, finetune  # Import API modules

app = FastAPI(
    title="Polymer NLP Extractor API",
    description="API for managing polymer NLP extraction workflows",
    version="1.0.0"
)

# Include Setup API router
app.include_router(setup.router, prefix="/api", tags=["Setup"])

# Include GROBID API router
app.include_router(grobid.router, prefix="/api", tags=["GROBID"])

# Include Ground Truth API router
app.include_router(groundtruth.router, prefix="/api", tags=["Ground Truth"])

# Include Preprocessing API router
app.include_router(preprocessing.router, prefix="/api", tags=["Preprocessing"])

# Include Fine-Tuning API router
app.include_router(finetune.router, prefix="/api", tags=["Fine-Tuning"])

@app.get("/")
def root():
    """
    Root endpoint for health check.
    """
    return {"status": "ok", "message": "Polymer NLP API is running."}
