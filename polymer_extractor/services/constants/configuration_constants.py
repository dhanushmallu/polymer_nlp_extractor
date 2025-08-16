# Processing patterns
MEASUREMENT_PATTERNS = [
    r"(\d+\.?\d*)\s*([°]?[CFK])",  # Temperature
    r"(\d+\.?\d*)\s*(MPa|GPa|Pa)",  # Pressure/Modulus
    r"(\d+\.?\d*)\s*(g/mol|kg/mol)",  # Molecular weight
    r"(\d+\.?\d*)\s*([%])",  # Percentage
]

# Export formats
EXPORT_FORMATS = {
    "json": {
        "extension": ".json",
        "mime_type": "application/json"
    },
    "csv": {
        "extension": ".csv",
        "mime_type": "text/csv"
    },
    "xlsx": {
        "extension": ".xlsx",
        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    },
    "xml": {
        "extension": ".xml",
        "mime_type": "application/xml"
    },
    "txt": {
        "extension": ".txt",
        "mime_type": "text/plain"
    }
}

# Entity types
ENTITY_TYPES = ["polymer", "property", "value", "unit", "symbol"]

# Model configuration constants (Phase 0B)
MODEL_DEFAULT_CONFIG = {
    # GitHub integration settings
    "github_integration": {
        "upload_enabled": True,
        "version_strict": True,
        "auto_version_increment": False,
        "force_retrain": False,
        "paired_creation": True,
        "validate_compatibility": True
    },
    
    # Enhanced features (Phase 0B)
    "phase_0b_features": {
        "enhanced_sentence_splitting": True,
        "improved_vocabulary_extension": True,
        "advanced_confidence_thresholds": True,
        "semantic_coherence_validation": True,
        "over_merging_prevention": True,
        "material_entity_removal": True
    },
    
    # Training environment
    "training_environment": {
        "wandb_enabled": False,  # Set to True if WANDB_API_KEY available
        "logging_enabled": True,
        "verbose_training": True,
        "gpu_optimization": True
    },
    
    # File paths (relative to workspace)
    "paths": {
        "models_dir": "models/finetuned",
        "tokenizers_dir": "models/tokenizers", 
        "exports_dir": "exports",
        "training_data_dir": "datasets/training",
        "testing_data_dir": "datasets/testing"
    }
}

# Required environment variables for training
REQUIRED_ENV_VARS = [
    "TOKENIZERS_REMOTE_URL",
    "FINETUNED_REMOTE_URL",
    "MODELS_VERSION",
    "MODELS_ROOT"
]

# Optional environment variables
OPTIONAL_ENV_VARS = [
    "HF_TOKEN",          # For GitHub integration
    "WANDB_API_KEY",     # For experiment tracking
    "GITHUB_TOKEN"       # Alternative to HF_TOKEN
]

SCIENTIFIC_SECTIONS = [
    # all possible ways of naming abstract
    "abstract", "summary", "overview", "introduction", "background", "context",

    # all possible ways of naming introduction
    "introduction", "intro", "background", "context", "motivation", "purpose",

    # all possible ways of naming methods
    "methods", "methodology", "experimental", "approach", "procedure", "technique",

    # all possible ways of naming results
    "results", "findings", "outcomes", "data", "analysis", "observations",

    # all possible ways of naming discussion
    "discussion", "analysis", "interpretation", "conclusion", "implications",

    # all possible ways of naming conclusion
    "conclusion", "conclusions", "summary", "final thoughts", "closing remarks"
]

CONTENT_MARKERS = [
    # common content markers
    "introduction", "methods", "results", "discussion", "conclusion",

    # common section markers
    "section", "subsection", "part", "chapter", "paragraph",

    # common formatting markers
    "bold", "italic", "underline", "highlight", "code", "quote",

    # common list markers
    "bullet", "numbered", "unordered", "ordered"
]
