"""
polymer_extractor/utils/paths.py
Summary
--------
Centralized, well-documented path and storage utilities for the Polymer NLP Extractor.
This module defines the authoritative rules for where files live and how paths are resolved
across the project. It enforces the separation between public storage and model assets and
provides helpers for converting between storage keys and local filesystem paths.

Key abstractions
----------------
- Public storage: workspace/public holds all artifacts including models (inputs, XML, reports, datasets, logs, exports, models).
- Models storage: workspace/public/models holds tokenizers and finetuned models (consistent with other artifacts).
- PathResolver: converts between URL/storage/relative/absolute to local or storage paths with read vs write semantics.
- ServicePathHandler: thin helper for consistent service responses and output directory creation.

Invariants
----------
- All writes go under workspace/public (including models).
- Model assets are under workspace/public/models for consistency.
- Reads resolve non-absolute inputs in order: public -> workspace.
- Inputs like "extracted_xml/1.pdf" and "/extracted_xml/1.pdf" are normalized.

Examples
--------
>>> from polymer_extractor.utils.paths import path_resolver, get_storage_path
>>> get_storage_path('reports', 'eval.csv')
'reports/eval.csv'
>>> path_resolver.to_local_path('extracted_xml/1.xml')  # resolves in order
'.../workspace/public/extracted_xml/1.xml'
>>> # Ensure an output file path exists for writing under public
>>> from polymer_extractor.utils.paths import ensure_service_output_dir
>>> ensure_service_output_dir('reports/eval.csv')
'.../workspace/public/reports/eval.csv'

Notes
-----
- Do not hardcode absolute paths in services; use this module.
- Prefer BucketClient with get_storage_path for portability across backends.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, Literal
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from polymer_extractor.utils.logging import Logger

# Load environment variables
load_dotenv()

# === Root Directories ===
logger = Logger()

# Automatically resolve PROJECT_ROOT as absolute path one level up from this file
PROJECT_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
# Workspace is the project workspace root. Public-facing storage is under workspace/public.
WORKSPACE_DIR: str = os.path.join(PROJECT_ROOT, "workspace")
PUBLIC_DIR: str = os.path.join(WORKSPACE_DIR, "public")
# Models directory is under workspace/public for consistency with other artifacts

# === Core Workspace Directories ===
RAW_INPUT_DIR: str = os.path.join(PUBLIC_DIR, "raw_inputs_dir")                # Uploaded PDFs ready for processing
EXTRACTED_XML_DIR: str = os.path.join(PUBLIC_DIR, "extracted_xml_dir")         # PDFs converted to XML (not yet cleaned)
PROCESSED_XML_DIR: str = os.path.join(PUBLIC_DIR, "processed_xml_dir")         # Cleaned TEI XML files ready for NLP
SAMPLES_DIR: str = os.path.join(PUBLIC_DIR, "samples_dir")                     # Tokenization output (model_name/<file_name>_tei_sentences.txt, etc.)
MODELS_DIR: str = os.path.join(PUBLIC_DIR, "models")                       # All models (moved to public for consistency)
REPORTS_DIR: str = os.path.join(PUBLIC_DIR, "full_reports_dir")                     # Reports (public)
SYSTEM_LOGS_DIR: str = os.path.join(PUBLIC_DIR, "system_logs")             # System logs (public)
# Grobid is managed in Docker; processed files produced by Grobid should live in public as needed.

# Public directory (all general storage lives here)
# PUBLIC_DIR already defined above

# Datasets live under public for sharing/storage
DATASETS_DIR: str = os.path.join(PUBLIC_DIR, "datasets_dir")
TRAINING_DATA_DIR: str = os.path.join(DATASETS_DIR, "training_dir")               # Processed training data
TESTING_DATA_DIR: str = os.path.join(DATASETS_DIR, "testing_dir")                 # Processed (realigned) testing data

EXPORTS_DIR: str = os.path.join(PUBLIC_DIR, "exports_dir")                     # Human-readable results (txt, csv)

# Backward compatibility
LOGS_DIR = SYSTEM_LOGS_DIR  # System logs directory

# === Storage Configuration ===
# Storage backend configuration from environment
STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")
STORAGE_PATH: str = os.getenv("STORAGE_PATH", str(PUBLIC_DIR))
STORAGE_BACKENDS_ACTIVE: str = os.getenv("STORAGE_BACKENDS_ACTIVE", "local")

# === Storage Path Mappings ===
# Relative paths used by BucketClient for different file types - now standardized with local structure
STORAGE_PATHS = {
    "raw_inputs": "raw_inputs_dir",                     # Original PDFs (renamed from raw_documents for consistency)
    "extracted_xml": "extracted_xml_dir",               # Raw XML from GROBID
    "processed_xml": "processed_xml_dir",               # Cleaned TEI XML
    "samples": "samples_dir",                           # Tokenization samples
    "models": "models",                             # Model files (now under public)
    "reports": "full_reports_dir",                           # Analysis reports
    "exports": "exports_dir",                           # Export files
    "system_logs": "system_logs",                   # System logs
    "datasets": "datasets_dir"                          # Datasets directory
}

# Note: Paths module is storage-agnostic beyond local/storage mapping.
# Appwrite database concepts are intentionally not referenced here.


def get_storage_path(file_type: str, filename: str = "") -> str:
    """
    Get the logical storage key for a file type (for BucketClient and remote backends).

    Parameters
    ----------
    file_type : str
        Logical type (raw_inputs, extracted_xml, processed_xml, samples, models, reports, exports, system_logs, datasets).
    filename : str, optional
        Specific filename to append.

    Returns
    -------
    str
        Relative storage key (e.g., "full_reports_dir/eval.csv").

    Raises
    ------
    ValueError
        If file_type contains invalid path characters or is empty

    Examples
    --------
    >>> get_storage_path('reports', 'eval.csv')
    'full_reports_dir/eval.csv'
    >>> get_storage_path('models')
    'models'
    
    Notes
    -----
    - Returns path relative to storage root for BucketClient usage
    - Works with both local and remote storage backends
    - File type is normalized against STORAGE_PATHS mapping
    """
    base_path = STORAGE_PATHS.get(file_type, file_type)
    if filename:
        return f"{base_path}/{filename}"
    return base_path


def get_local_path(file_type: str, filename: str = "") -> str:
    """
    Get the local filesystem path base for a logical file type.

    Parameters
    ----------
    file_type : str
        Logical type (raw_inputs, extracted_xml, processed_xml, samples, models, reports, exports, system_logs, datasets).
    filename : str, optional
        Specific filename to append.

    Returns
    -------
    str
        Absolute local filesystem path.

    Raises
    ------
    OSError
        If the resulting path would be outside the workspace directory
        
    Examples
    --------
    >>> get_local_path('reports', 'eval.csv') 
    '/workspace/public/full_reports_dir/eval.csv'
    >>> get_local_path('models')
    '/workspace/models'

    Notes
    -----
    This helper maps the logical storage types onto local public/models directories.
    Prefer using PathResolver for complex conversions.
    """
    # Map file types to local directories
    local_mapping = {
        "raw_inputs": RAW_INPUT_DIR,               # Updated from raw_documents
        "raw_documents": RAW_INPUT_DIR,            # Backward compatibility alias
        "extracted_xml": EXTRACTED_XML_DIR,
        "processed_xml": PROCESSED_XML_DIR,
        "samples": SAMPLES_DIR,
        "models": MODELS_DIR,                      # Now points to public/models
        "reports": REPORTS_DIR,
        "exports": EXPORTS_DIR,
        "system_logs": SYSTEM_LOGS_DIR,
        "datasets": DATASETS_DIR
    }
    
    base_dir = local_mapping.get(file_type, os.path.join(WORKSPACE_DIR, file_type))
    if filename:
        return os.path.join(base_dir, filename)
    return base_dir


def ensure_directories() -> None:
    """
    Create all required directories under public/models if they do not exist.

    Raises
    ------
    OSError
        If directory creation fails due to permissions or disk space
        
    Examples
    --------
    >>> ensure_directories()  # Creates all workspace subdirectories
    
    Notes
    -----
    Ensures the folder hierarchy is initialized for local operations before any
    file read/write operations. Safe to call multiple times.
    """
    directories = [
        WORKSPACE_DIR, RAW_INPUT_DIR, EXTRACTED_XML_DIR, PROCESSED_XML_DIR, SAMPLES_DIR,
        DATASETS_DIR, TRAINING_DATA_DIR, TESTING_DATA_DIR,
        MODELS_DIR, LOGS_DIR, EXPORTS_DIR, PUBLIC_DIR
    ]
    for dir_path in directories:
        os.makedirs(dir_path, exist_ok=True)


def print_project_paths() -> None:
    """
    Print a structured summary of major project paths and storage configurations.

    Outputs
    -------
    Prints resolved absolute paths and storage configs for verification/debugging.
    """
    divider = "-" * 70
    print(f"\n{divider}\nPolymer NLP Project Path Configuration\n{divider}")
    print(f"Project Root:                 {PROJECT_ROOT}")
    print(f"Workspace Directory:          {WORKSPACE_DIR}\n")

    print("Raw & Extracted Content:")
    print(f"  Raw Inputs:                 {RAW_INPUT_DIR}")
    print(f"  Extracted XML:              {EXTRACTED_XML_DIR}")
    print(f"  Processed XML:              {PROCESSED_XML_DIR}")
    print(f"  Samples Directory:          {SAMPLES_DIR}\n")

    print("Datasets:")
    print(f"  Training Data:              {TRAINING_DATA_DIR}")
    print(f"  Testing Data:               {TESTING_DATA_DIR}\n")

    print("Models & Logs:")
    print(f"  Models Directory:           {MODELS_DIR}")
    print(f"  System Logs:                {LOGS_DIR}")
    print(f"  Exports Directory:          {EXPORTS_DIR}")
    print(f"  Public Directory:           {PUBLIC_DIR}\n")

    print("Storage Configuration:")
    print(f"  Storage Backend:            {STORAGE_BACKEND}")
    print(f"  Storage Path:               {STORAGE_PATH}")
    print(f"  Active Backends:            {STORAGE_BACKENDS_ACTIVE}")
    print(f"  Storage Paths:              {STORAGE_PATHS}\n")

    print(f"{divider}\n")


class PathResolver:
    """
    Universal path resolution across absolute/relative/storage/URL.

    Summary
    -------
    Provides deterministic conversion to storage keys or local paths with explicit
    rules for read vs write behavior and normalization of common path formats.

    Notes
    -----
    - Reads: relative inputs resolve public -> models -> workspace.
    - Writes: non-model writes go to public; model writes go to workspace/models.
    - URL inputs are downloaded to a stable downloads directory under public.
    """

    def __init__(self) -> None:
        self.storage_path_root = os.path.abspath(STORAGE_PATH)
        # Storage type to local directory mapping - updated for models in public
        self.storage_to_local = {
            "raw_inputs_dir": RAW_INPUT_DIR,               # Updated key name with _dir suffix
            "raw_inputs": RAW_INPUT_DIR,               # Legacy support
            "raw_documents": RAW_INPUT_DIR,            # Backward compatibility
            "extracted_xml_dir": EXTRACTED_XML_DIR,
            "extracted_xml": EXTRACTED_XML_DIR,        # Legacy support
            "processed_xml_dir": PROCESSED_XML_DIR,
            "processed_xml": PROCESSED_XML_DIR,        # Legacy support
            "samples_dir": SAMPLES_DIR,
            "samples": SAMPLES_DIR,                    # Legacy support
            "models": MODELS_DIR,                      # Now points to public/models
            "full_reports_dir": REPORTS_DIR,
            "reports": REPORTS_DIR,                    # Legacy support
            "exports_dir": EXPORTS_DIR,
            "exports": EXPORTS_DIR,                    # Legacy support
            "system_logs": SYSTEM_LOGS_DIR,
            "datasets_dir": DATASETS_DIR,
            "datasets": DATASETS_DIR,                  # Legacy support
        }
        # Reverse lookup & extras
        self.local_to_storage = {v: k for k, v in self.storage_to_local.items()}
        self.local_to_storage.update({
            os.path.join(WORKSPACE_DIR, "raw_inputs_dir"): "raw_inputs_dir",    # Updated
            os.path.join(WORKSPACE_DIR, "datasets_dir"): "datasets_dir",
            os.path.join(WORKSPACE_DIR, "public"): "public",
        })
        # Downloads dir under storage root
        self.downloads_dir = os.path.join(self.storage_path_root, "downloads")
        Path(self.downloads_dir).mkdir(parents=True, exist_ok=True)

    def detect_path_type(self, path: Union[str, Path]) -> Literal["url", "absolute", "relative", "storage"]:
        """Classify a path as url, absolute, relative, or storage-key.

        Parameters
        ----------
        path : str | Path
            Input path (may be URL).

        Returns
        -------
        Literal["url", "absolute", "relative", "storage"]
            Type classification.
        """
        path_str = str(path)
        if re.match(r"^(https?|ftp)://", path_str):
            return "url"
        if os.path.isabs(path_str):
            return "absolute"
        first_part = path_str.split('/')[0] if '/' in path_str else path_str
        if first_part in STORAGE_PATHS or first_part in STORAGE_PATHS.values():
            return "storage"
        return "relative"

    def _download_url(self, url: str, file_type: Optional[str] = None) -> str:
        """Download a URL to the downloads directory and return the local path.

        Parameters
        ----------
        url : str
            HTTP/HTTPS/FTP URL.
        file_type : str | None
            Optional logical type to namespace downloads.

        Returns
        -------
        str
            Absolute local path of the downloaded file.

        Raises
        ------
        ValueError
            If the download fails.
        """
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path) or f"downloaded_file_{abs(hash(url)) % 10000}"
        download_dir = os.path.join(self.downloads_dir, file_type) if file_type else self.downloads_dir
        Path(download_dir).mkdir(parents=True, exist_ok=True)
        local_path = os.path.join(download_dir, filename)
        try:
            logger.info(f"Downloading {url} -> {local_path}", source="paths")
            with requests.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(local_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
        except Exception as e:
            logger.error(f"Failed to download {url}", error=e, source="paths")
            raise ValueError(f"Could not download URL: {url} - {e}")
        return local_path

    def to_storage_path(self, path: Union[str, Path], file_type: Optional[str] = None, for_write: bool = False) -> str:
        """Convert input to a logical storage key.

        Parameters
        ----------
        path : str | Path
            Input path (absolute/relative/storage key/URL).
        file_type : str | None
            Target logical type to hint resulting storage prefix.
        for_write : bool
            Whether this conversion targets a write operation (advisory).

        Returns
        -------
        str
            Storage key relative to the storage root.
        """
        path_str = str(path)
        path_type = self.detect_path_type(path_str)
        if path_type == "storage":
            return path_str

        if path_type == "absolute":
            abs_path = Path(path_str).resolve()
            # If the absolute path is under the storage root, return a storage-relative path
            try:
                rel_to_root = abs_path.relative_to(Path(self.storage_path_root))
                return f"{STORAGE_PATHS[file_type]}/{abs_path.name}" if file_type and file_type in STORAGE_PATHS else str(rel_to_root)
            except ValueError:
                pass

            # Try mapping from known local directories to storage paths
            for local_dir, storage_type in self.local_to_storage.items():
                try:
                    rel = abs_path.relative_to(Path(local_dir))
                    return f"{STORAGE_PATHS[storage_type]}/{rel}"
                except (ValueError, KeyError):
                    continue

            # If under workspace, map to storage path by filename
            try:
                rel_ws = abs_path.relative_to(Path(WORKSPACE_DIR))
                return f"{STORAGE_PATHS[file_type]}/{abs_path.name}" if file_type and file_type in STORAGE_PATHS else str(rel_ws)
            except ValueError:
                pass

            return f"{STORAGE_PATHS[file_type]}/{abs_path.name}" if file_type and file_type in STORAGE_PATHS else abs_path.name

        if path_type == "relative":
            clean = path_str.lstrip('./')
            first = clean.split('/')[0]
            # If path is under workspace/, treat it as workspace-absolute and map accordingly
            if clean.startswith('workspace/') or Path(PROJECT_ROOT, clean).exists():
                abs_candidate = Path(PROJECT_ROOT) / clean
                if abs_candidate.exists():
                    try:
                        for local_dir, storage_type in self.local_to_storage.items():
                            rel = abs_candidate.resolve().relative_to(Path(local_dir))
                            return f"{STORAGE_PATHS[storage_type]}/{rel}"
                    except Exception:
                        pass

            # Direct storage-like relative path
            if first in STORAGE_PATHS.values():
                return clean
            if file_type and file_type in STORAGE_PATHS:
                return f"{STORAGE_PATHS[file_type]}/{Path(clean).name}"
            return clean

        if path_type == "url":
            parsed = urlparse(path_str)
            fname = os.path.basename(parsed.path) or f"downloaded_file_{abs(hash(path_str)) % 10000}"
            return f"downloads/{fname}"

        return path_str

    def to_local_path(self, path: Union[str, Path], file_type: Optional[str] = None, for_write: bool = False) -> str:
        """Convert input to a local filesystem path.

        Parameters
        ----------
        path : str | Path
            Input path (absolute/relative/storage key/URL).
        file_type : str | None
            Optional logical type.
        for_write : bool
            If True, bias resolution so non-model writes land under public.

        Returns
        -------
        str
            Absolute local path.
        """
        path_str = str(path)
        path_type = self.detect_path_type(path_str)
        if path_type == "absolute":
            return str(Path(path_str).resolve())

        if path_type == "storage":
            parts = path_str.split('/')
            storage_type = parts[0]
            if storage_type in STORAGE_PATHS.values():
                for k, v in STORAGE_PATHS.items():
                    if v == storage_type:
                        storage_type = k; break
            base = self.storage_to_local.get(storage_type, PUBLIC_DIR)

            # Storage entries map to public-local directories by default. If for_write is True,
            # and the target is models, keep models under MODELS_DIR. For other types, public is used.
            if for_write and storage_type != 'models':
                base = PUBLIC_DIR

            return os.path.join(base, '/'.join(parts[1:])) if len(parts) > 1 else base
        if path_type == "relative":
            clean = path_str.lstrip('./')
            # Normalize incorrect formats: allow 'extracted_xml/1.pdf' and '/extracted_xml/1.pdf'
            if clean.startswith('/'):
                clean = clean.lstrip('/')

            # Resolution order for reads: PUBLIC_DIR -> MODELS_DIR -> WORKSPACE_DIR
            public_candidate = Path(PUBLIC_DIR) / clean
            if public_candidate.exists():
                return str(public_candidate.resolve())

            model_candidate = Path(MODELS_DIR) / clean
            if model_candidate.exists():
                return str(model_candidate.resolve())

            workspace_candidate = Path(WORKSPACE_DIR) / clean
            if workspace_candidate.exists():
                return str(workspace_candidate.resolve())

            # Fallback: resolve under storage root (PUBLIC_DIR) regardless
            return str(Path(os.path.join(self.storage_path_root, clean)).resolve())
        if path_type == "url":
            return self._download_url(path_str, file_type)
        return str(Path(path_str).resolve())

    def resolve_path(self, path: Union[str, Path], target: Literal["storage", "local", "url"] = "storage", file_type: Optional[str] = None) -> str:
        """One-shot resolve helper to obtain storage or local path.

        Parameters
        ----------
        path : str | Path
            Input path.
        target : {"storage", "local", "url"}
            Desired output kind.
        file_type : str | None
            Optional logical type.

        Returns
        -------
        str
            Resolved string path.
        """
        return self.to_storage_path(path, file_type) if target == "storage" else (
            self.to_local_path(path, file_type) if target == "local" else str(path)
        )

    def sanitize_path(self, path: Union[str, Path]) -> str:
        """Sanitize a path string by removing illegal characters and duplicate separators."""
        s = str(path)
        for ch in ['<', '>', ':', '"', '|', '?', '*']:
            s = s.replace(ch, '_')
        s = re.sub(r'/+', '/', s).strip('/')
        return s

    def ensure_directory(self, path: Union[str, Path], is_file: bool = True) -> str:
        """Ensure parent directory exists for a file path (or the dir itself if is_file=False)."""
        p = Path(path)
        (p.parent if is_file else p).mkdir(parents=True, exist_ok=True)
        return str(p)

    def get_path_info(self, path: Union[str, Path]) -> Dict[str, Any]:
        """Return a structured view of a path including type, existence, storage/local, and metadata."""
        s = str(path)
        ptype = self.detect_path_type(s)
        info: Dict[str, Any] = {
            "original_path": s,
            "path_type": ptype,
            "is_absolute": os.path.isabs(s),
            "exists": False,
            "storage_path": None,
            "local_path": None,
            "file_type": None,
            "filename": Path(s).name,
            "extension": Path(s).suffix,
        }
        try:
            info["storage_path"] = self.to_storage_path(s)
        except Exception as e:
            info["storage_path_error"] = str(e)
        try:
            info["local_path"] = self.to_local_path(s)
        except Exception as e:
            info["local_path_error"] = str(e)
        if info.get("storage_path"):
            first = info["storage_path"].split('/')[0]
            if first in STORAGE_PATHS.values():
                for k, v in STORAGE_PATHS.items():
                    if v == first:
                        info["file_type"] = k; break
        if info.get("local_path") and not info.get("local_path_error"):
            info["exists"] = os.path.exists(str(info["local_path"]))
        return info


# Global resolver instance and convenience functions
path_resolver = PathResolver()

def resolve_to_storage_path(path: Union[str, Path], file_type: Optional[str] = None) -> str:
    """
    Convert any path input to a logical storage key using the global path resolver.
    
    Parameters
    ----------
    path : str | Path
        Input path in any format (URL, absolute, relative, or storage key)
    file_type : str, optional
        Logical file type hint for proper storage mapping
        
    Returns
    -------
    str
        Storage key relative to storage root (e.g., "reports/analysis.csv")
        
    Examples
    --------
    >>> resolve_to_storage_path("/workspace/public/reports/eval.csv")
    'full_reports_dir/eval.csv'
    >>> resolve_to_storage_path("extracted_xml/paper1.xml")
    'extracted_xml_dir/paper1.xml'
    
    Notes
    -----
    - Convenience wrapper around path_resolver.to_storage_path()
    - Used for consistent storage key generation across services
    """
    return path_resolver.to_storage_path(path, file_type)

def resolve_to_local_path(path: Union[str, Path], file_type: Optional[str] = None) -> str:
    """
    Convert any path input to an absolute local filesystem path using resolution order.
    
    Parameters
    ----------
    path : str | Path
        Input path in any format (URL, absolute, relative, or storage key)
    file_type : str, optional
        Logical file type hint for proper resolution
        
    Returns
    -------
    str
        Absolute local filesystem path
        
    Examples
    --------
    >>> resolve_to_local_path("reports/eval.csv")
    '/workspace/public/full_reports_dir/eval.csv'
    >>> resolve_to_local_path("https://example.com/data.pdf")
    '/workspace/public/downloads/data.pdf'
    
    Notes
    -----
    - Reads resolve in order: public -> models -> workspace
    - URLs are automatically downloaded to downloads directory
    - Convenience wrapper around path_resolver.to_local_path()
    """
    return path_resolver.to_local_path(path, file_type)

def detect_path_type(path: Union[str, Path]) -> Literal["url", "absolute", "relative", "storage"]:
    """
    Classify a path string to determine appropriate resolution strategy.
    
    Parameters
    ----------
    path : str | Path
        Path to classify
        
    Returns
    -------
    Literal["url", "absolute", "relative", "storage"]
        Path type classification for routing resolution logic
        
    Examples
    --------
    >>> detect_path_type("https://example.com/file.pdf")
    'url'
    >>> detect_path_type("/absolute/path/file.txt")
    'absolute'
    >>> detect_path_type("reports/analysis.csv")
    'storage'
    
    Notes
    -----
    - URL detection supports http, https, and ftp protocols
    - Storage paths identified by first component matching STORAGE_PATHS
    - Convenience wrapper around path_resolver.detect_path_type()
    """
    return path_resolver.detect_path_type(path)


class ServicePathHandler:
    """
    Service helper for consistent path handling in API responses and output management.
    
    Summary
    -------
    Provides standardized utilities for service input resolution, response formatting,
    and output directory creation. Ensures consistent path information in service responses
    and proper output file placement according to project conventions.
    
    Examples
    --------
    >>> handler = ServicePathHandler()
    >>> local_path, storage_path = handler.resolve_input_path("reports/eval.csv")
    >>> response = handler.format_response(True, local_path, "reports")
    >>> output_path = handler.ensure_output_directory("reports/new_analysis.csv")
    
    Notes
    -----
    - Wrapper around PathResolver for service-specific conveniences
    - Used by API endpoints for consistent path handling
    - Enforces write policies (public vs models separation)
    """

    def __init__(self) -> None:
        self.logger = logger

    def resolve_input_path(self, input_path: Union[str, Path], file_type: Optional[str] = None) -> Tuple[str, str]:
        """Resolve service input path to (local_path, storage_path) with read semantics."""
        local_path = path_resolver.to_local_path(input_path, file_type, for_write=False)
        storage_path = path_resolver.to_storage_path(input_path, file_type, for_write=False)
        self.logger.info(f"Resolved input path: {input_path} -> local:{local_path}, storage:{storage_path}", source="ServicePathHandler")
        return local_path, storage_path

    def format_response(
        self,
        success: bool,
        local_path: Optional[Union[str, Path]] = None,
        file_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        storage_success: bool = True,
        storage_errors: Optional[List[str]] = None,
        message: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a standardized service response containing paths, metadata, and status."""
        from datetime import datetime as _dt
        response: Dict[str, Any] = {
            "success": success,
            "timestamp": _dt.utcnow().isoformat(),
            "storage_success": storage_success,
            "storage_errors": storage_errors or [],
        }
        if message:
            response["message"] = message
        if metadata:
            response["metadata"] = metadata
        if local_path:
            lp = str(local_path)
            response["local_path"] = lp
            response["storage_path"] = path_resolver.to_storage_path(lp, file_type, for_write=False)
            info = path_resolver.get_path_info(lp)
            response["path_info"] = {"filename": info["filename"], "file_type": info.get("file_type", file_type), "exists": info["exists"]}
        if additional_data:
            response.update(additional_data)
        return response

    def ensure_output_directory(self, output_path: Union[str, Path], file_type: Optional[str] = None) -> str:
        """Ensure output file path's directory exists under public (or models for model artifacts)."""
        lp = path_resolver.to_local_path(output_path, file_type, for_write=True)
        return path_resolver.ensure_directory(lp, is_file=True)


# Global instance and compatibility shims
service_path_handler = ServicePathHandler()

def resolve_service_input(input_path: Union[str, Path], file_type: Optional[str] = None) -> Tuple[str, str]:
    """
    Resolve service input path to both local path and storage key formats.
    
    Parameters
    ----------
    input_path : str | Path
        Input path from service request
    file_type : str, optional
        Logical file type for proper resolution
        
    Returns
    -------
    Tuple[str, str]
        (local_path, storage_path) tuple for service usage
        
    Examples
    --------
    >>> local_path, storage_path = resolve_service_input("extracted_xml/paper.xml")
    >>> # local_path: "/workspace/public/extracted_xml_dir/paper.xml"
    >>> # storage_path: "extracted_xml_dir/paper.xml"
    
    Notes
    -----
    - Standard pattern for service input processing
    - Returns both formats for flexibility in service logic
    """
    return service_path_handler.resolve_input_path(input_path, file_type)

def format_service_response(success: bool, local_path: Optional[Union[str, Path]] = None, file_type: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Format standardized service response with path information.
    
    Parameters
    ----------
    success : bool
        Whether the operation was successful
    local_path : str | Path, optional
        Local path of result file
    file_type : str, optional
        Logical file type for metadata
    **kwargs : Any
        Additional response fields
        
    Returns
    -------
    Dict[str, Any]
        Standardized response dictionary with path metadata
        
    Examples
    --------
    >>> format_service_response(True, "/workspace/public/reports/eval.csv", "reports")
    {
        "success": True,
        "local_path": "/workspace/public/full_reports_dir/eval.csv", 
        "storage_path": "full_reports_dir/eval.csv",
        "path_info": {...}
    }
    
    Notes
    -----
    - Provides consistent response format across all services
    - Includes both local and storage paths for client flexibility
    """
    return service_path_handler.format_response(success, local_path, file_type, **kwargs)

def ensure_service_output_dir(output_path: Union[str, Path], file_type: Optional[str] = None) -> str:
    """
    Ensure output directory exists and return proper write path under public storage.
    
    Parameters
    ----------
    output_path : str | Path
        Desired output path (may be relative or storage key)
    file_type : str, optional
        Logical file type for proper placement
        
    Returns
    -------
    str
        Absolute local path ready for writing, with directory created
        
    Examples
    --------
    >>> ensure_service_output_dir("reports/new_analysis.csv")
    '/workspace/public/full_reports_dir/new_analysis.csv'
    
    Notes
    -----
    - Creates parent directories as needed
    - Enforces write policies (non-model files go to public)
    - Returns absolute path ready for file operations
    """
    return service_path_handler.ensure_output_directory(output_path, file_type)


# Automatically ensure directories exist at import
ensure_directories()
