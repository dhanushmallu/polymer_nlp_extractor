from fastapi import FastAPI
from polymer_extractor.api import setup, grobid  # Import API modules

app = FastAPI(
    title="Polymer NLP Extractor API",
    description="API for managing polymer NLP extraction workflows",
    version="1.0.0"
)

# Include Setup API router
app.include_router(setup.router, prefix="/api", tags=["Setup"])

# Include GROBID API router
app.include_router(grobid.router, prefix="/api", tags=["GROBID"])

@app.get("/")
def root():
    """
    Root endpoint for health check.
    """
    return {"status": "ok", "message": "Polymer NLP API is running."}
