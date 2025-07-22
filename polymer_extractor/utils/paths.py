# polymer_extractor/utils/paths.py

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# === Root Directories ===
# Automatically resolve PROJECT_ROOT as absolute path one level up from this file
PROJECT_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
WORKSPACE_DIR: str = os.path.join(PROJECT_ROOT, "workspace")

# === Core Workspace Directories ===
RAW_INPUT_DIR: str = os.path.join(WORKSPACE_DIR, "raw_inputs")           # PDFs and supplementary files
EXTRACTED_XML_DIR: str = os.path.join(WORKSPACE_DIR, "extracted_xml")    # GROBID TEI XML outputs
SAMPLES_DIR: str = os.path.join(WORKSPACE_DIR, "samples")                # Processed text samples (spans, windows, tokens)

DATASETS_DIR: str = os.path.join(WORKSPACE_DIR, "datasets")
MODELS_DIR: str = os.path.join(WORKSPACE_DIR, "models")                  # Locally saved fine-tuned models
LOGS_DIR: str = os.path.join(WORKSPACE_DIR, "system_logs")               # Audit and system logs
EXPORTS_DIR: str = os.path.join(WORKSPACE_DIR, "exports")                # Human-readable results (txt, csv)

# Dataset subdirectories
TRAINING_DATA_DIR: str = os.path.join(DATASETS_DIR, "training")
TESTING_DATA_DIR: str = os.path.join(DATASETS_DIR, "testing")

# Appwrite Configuration

# === Appwrite Buckets === #
APPWRITE_MODEL_BUCKET_PREFIX: str = "polymer_model_bucket"               # Versioned buckets like polymer_model_bucket_V1.0
APPWRITE_LOGS_BUCKET: str = "system_logs_bucket"                         # Bucket for system logs

# === Appwrite Collections === #
APPWRITE_EXTRACTION_COLLECTION: str = "extraction_metadata"              # Extraction results metadata
APPWRITE_FILE_METADATA_COLLECTION: str = "file_metadata"                 # PDF-level metadata (DOI, title, authors)
APPWRITE_MODELS_METADATA_COLLECTION: str = "models_metadata"             # Model version tracking
APPWRITE_LOGS_COLLECTION: str = "system_logs"                            # Logs collection in Appwrite


def ensure_directories() -> None:
    """
    Create all required directories under WORKSPACE_DIR if they do not exist.

    Notes
    -----
    This ensures the folder hierarchy is initialized for local operations before any
    file read/write operations.
    """
    directories = [
        WORKSPACE_DIR, RAW_INPUT_DIR, EXTRACTED_XML_DIR, SAMPLES_DIR,
        DATASETS_DIR, TRAINING_DATA_DIR, TESTING_DATA_DIR,
        MODELS_DIR, LOGS_DIR, EXPORTS_DIR
    ]
    for dir_path in directories:
        os.makedirs(dir_path, exist_ok=True)


def print_project_paths() -> None:
    """
    Print a structured summary of all major project paths and Appwrite configurations.

    Outputs
    -------
    Displays the resolved absolute paths and Appwrite configurations for
    verification and debugging purposes.
    """
    divider = "-" * 70
    print(f"\n{divider}\nPolymer NLP Project Path Configuration\n{divider}")
    print(f"Project Root:                 {PROJECT_ROOT}")
    print(f"Workspace Directory:          {WORKSPACE_DIR}\n")

    print("Raw & Extracted Content:")
    print(f"  Raw Inputs:                 {RAW_INPUT_DIR}")
    print(f"  Extracted XML:              {EXTRACTED_XML_DIR}")
    print(f"  Samples Directory:          {SAMPLES_DIR}\n")

    print("Datasets:")
    print(f"  Training Data:              {TRAINING_DATA_DIR}")
    print(f"  Testing Data:               {TESTING_DATA_DIR}\n")

    print("Models & Logs:")
    print(f"  Models Directory:           {MODELS_DIR}")
    print(f"  System Logs:                {LOGS_DIR}")
    print(f"  Exports Directory:          {EXPORTS_DIR}\n")

    print("Appwrite Configuration:")
    print(f"  Model Bucket Prefix:        {APPWRITE_MODEL_BUCKET_PREFIX}")
    print(f"  Extraction Metadata:        {APPWRITE_EXTRACTION_COLLECTION}")
    print(f"  File Metadata:              {APPWRITE_FILE_METADATA_COLLECTION}")
    print(f"  Models Metadata:            {APPWRITE_MODELS_METADATA_COLLECTION}")
    print(f"  Logs Collection:            {APPWRITE_LOGS_COLLECTION}")
    print(f"{divider}\n")


# Automatically ensure directories exist at import
ensure_directories()
