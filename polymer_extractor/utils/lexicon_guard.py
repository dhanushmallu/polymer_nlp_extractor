"""
LexiconGuard V4.1: Auto-manages artifacts for all ensemble models.

Features:
---------
- Dynamic model discovery (from ENSEMBLE_MODELS)
- Artifact lifecycle (tokenizing, fine-tuning, ensembling)
- Local folder/zip check
- Appwrite fetch and restore
- Centralized zipping/unzipping
- Unified dataset terms (training + testing)
"""

import hashlib
import json
from datetime import datetime
import os
from typing import Callable, Any, Dict, Optional, Union
import pandas as pd

from polymer_extractor.model_config import ENSEMBLE_MODELS
from polymer_extractor.storage.database_manager import DatabaseManager
from polymer_extractor.storage.bucket_manager import BucketManager
from polymer_extractor.utils.paths import WORKSPACE_DIR
from polymer_extractor.utils.file_utils import (
    zip_directory, unzip_archive, sanitize_name
)
from polymer_extractor.utils.logging import Logger

logger = Logger()

# Directories
GUARD_META_DIR = os.path.join(WORKSPACE_DIR, "lexicon_guard")
ARTIFACTS_DIR = os.path.join(WORKSPACE_DIR, "artifacts")
DATASETS_DIR = os.path.join(WORKSPACE_DIR, "datasets", "training")

# Ensure directories exist
os.makedirs(GUARD_META_DIR, exist_ok=True)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)
os.makedirs(DATASETS_DIR, exist_ok=True)


class LexiconGuard:
    def __init__(
        self,
        artifact_type: str = "extended",  # One of: extended, finetuned, ensembled
        db_collection: str = "models_metadata"
    ):
        self.artifact_type = artifact_type.lower()
        if self.artifact_type not in {"extended", "finetuned", "ensembled"}:
            raise ValueError("artifact_type must be one of: extended, finetuned, ensembled")

        self.models = [model.model_id for model in ENSEMBLE_MODELS]
        self.db = DatabaseManager()
        self.bucket = BucketManager()
        self.collection = db_collection

    def _get_safe_name(self, model_name: str) -> str:
        """Return sanitized model name with artifact type suffix"""
        return f"{sanitize_name(model_name)}_{self.artifact_type}"

    def compute_hash(self, terms: list[str]) -> str:
        """Compute MD5 hash of sorted terms"""
        joined = "||".join(sorted(terms)).encode("utf-8")
        digest = hashlib.md5(joined).hexdigest()
        logger.info(
            message=f"Computed terms_hash={digest}",
            source="LexiconGuard.compute_hash",
            category="system",
            event_type="hash_computed"
        )
        return digest

    def _load_stored(self, safe_name: str) -> Dict[str, Any]:
        """Load metadata from local disk or Appwrite"""
        meta_path = os.path.join(GUARD_META_DIR, f"{safe_name}_lexicon.json")
        if os.path.exists(meta_path):
            try:
                data = json.loads(open(meta_path, encoding="utf-8").read())
                logger.info(
                    message=f"Loaded local metadata for {safe_name}",
                    source="LexiconGuard._load_stored",
                    category="system",
                    event_type="local_meta_loaded"
                )
                return data
            except Exception as e:
                logger.error(
                    message=f"Failed reading {meta_path}",
                    source="LexiconGuard._load_stored",
                    category="system",
                    event_type="local_meta_error",
                    error=e
                )
        try:
            docs = self.db.list_documents(self.collection, queries=[{"model_name": safe_name}])
            if docs:
                logger.info(
                    message=f"Loaded remote metadata for {safe_name}",
                    source="LexiconGuard._load_stored",
                    category="system",
                    event_type="remote_meta_loaded"
                )
                return {
                    "terms_hash": docs[0].get("terms_hash"),
                    "artifact_file_id": docs[0].get("artifact_file_id"),
                    "updated_on": docs[0].get("updated_on")
                }
        except Exception as e:
            logger.error(
                message=f"Failed loading remote metadata for {safe_name}",
                source="LexiconGuard._load_stored",
                category="system",
                event_type="remote_meta_error",
                error=e
            )
        return {}

    def _restore_from_remote(self, bucket_id: str, artifact_zip: str, artifact_folder: str, artifact_file_id: str):
        """Download and extract artifact from Appwrite"""
        logger.info(
            message=f"Restoring {artifact_folder} artifact from Appwrite...",
            source="LexiconGuard._restore_from_remote",
            category="system",
            event_type="artifact_restore"
        )
        self.bucket.download_file(bucket_id, artifact_file_id, artifact_zip)
        unzip_archive(artifact_zip, artifact_folder)

    def _check_local_artifact(self, artifact_folder: str, artifact_zip: str) -> bool:
        """Check if artifact folder or zip exists locally"""
        if os.path.exists(artifact_folder) and os.listdir(artifact_folder):
            logger.info(
                message=f"Found local artifact folder: {artifact_folder}",
                source="LexiconGuard._check_local_artifact",
                category="system",
                event_type="local_artifact_found"
            )
            return True
        if os.path.exists(artifact_zip):
            logger.info(
                message=f"Found local artifact zip: {artifact_zip}",
                source="LexiconGuard._check_local_artifact",
                category="system",
                event_type="local_artifact_zip_found"
            )
            unzip_archive(artifact_zip, artifact_folder)
            return True
        return False

    def _merge_dataset_terms(self) -> list[str]:
        merged_df = pd.DataFrame()
        try:
            datasets = self.db.list_documents("datasets_metadata", queries=[{"type": ["training", "testing"]}])
            for ds in datasets:
                file_id = ds.get("appwrite_file_id")
                dataset_name = ds.get("dataset_name") + ".csv"
                local_path = os.path.join(DATASETS_DIR, dataset_name)

                self.bucket.download_file("datasets_bucket", file_id, local_path)

                df = pd.read_csv(local_path, dtype=str).fillna("")
                df = df.rename(columns=lambda c: c.split("_")[0])  # Drop suffixes/prefixes
                df = df.drop(columns=["filename", "heading"], errors="ignore")
                merged_df = pd.concat([merged_df, df], ignore_index=True)
        except Exception as e:
            logger.error(
                message="Dataset merging failed",
                source="LexiconGuard._merge_dataset_terms",
                category="system",
                event_type="dataset_merge_error",
                error=e
            )

        unique_terms = pd.unique(merged_df.stack().dropna())
        logger.info(
            message=f"Collected {len(unique_terms)} unique dataset terms.",
            source="LexiconGuard._merge_dataset_terms",
            category="system",
            event_type="dataset_terms_collected"
        )
        return unique_terms.tolist()

    def guard_all(
        self,
        terms: list[str],
        action: Callable[[str], Any],
        extra_metadata: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Guard artifacts for all ensemble models.
        """
        dataset_terms = self._merge_dataset_terms()
        full_terms = list(set(terms).union(set(dataset_terms)))
        results = {}

        for model_name in self.models:
            safe_name = self._get_safe_name(model_name)
            artifact_folder = os.path.join(ARTIFACTS_DIR, safe_name)
            artifact_zip = os.path.join(ARTIFACTS_DIR, f"{safe_name}.zip")
            bucket_id = f"{safe_name}_bucket"

            current_hash = self.compute_hash(full_terms)
            stored = self._load_stored(safe_name)

            if not force and stored.get("terms_hash") == current_hash:
                if self._check_local_artifact(artifact_folder, artifact_zip):
                    logger.info(
                        message=f"{safe_name}: Lexicon unchanged and local artifact found. Skipping rebuild.",
                        source="LexiconGuard.guard_all",
                        category="system",
                        event_type="guard_skipped"
                    )
                    results[safe_name] = {"ran": False, "terms_hash": current_hash}
                    continue
                elif stored.get("artifact_file_id"):
                    self._restore_from_remote(bucket_id, artifact_zip, artifact_folder, stored["artifact_file_id"])
                    results[safe_name] = {"ran": False, "terms_hash": current_hash}
                    continue

            result = action(model_name)

            archive_path = zip_directory(artifact_folder, artifact_zip)
            self.bucket.create_bucket(bucket_id, f"{safe_name} bucket")
            upload_resp = self.bucket.upload_file(bucket_id, str(archive_path))
            artifact_file_id = upload_resp.get("$id")

            record = {
                "model_name": safe_name,
                "artifact_type": self.artifact_type,
                "terms_hash": current_hash,
                "updated_on": datetime.utcnow().isoformat() + "Z",
                "artifact_file_id": artifact_file_id,
                **(extra_metadata or {})
            }
            self._save_local(safe_name, record)
            self._save_remote(record)

            results[safe_name] = {
                "ran": True,
                "terms_hash": current_hash,
                "result": result,
                "artifact_archive": str(archive_path),
                "artifact_file_id": artifact_file_id
            }

        return results

    def _save_local(self, safe_name: str, record: Dict[str, Any]):
        """Save metadata locally"""
        meta_path = os.path.join(GUARD_META_DIR, f"{safe_name}_lexicon.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
        logger.info(
            message=f"Saved local metadata: {meta_path}",
            source="LexiconGuard._save_local",
            category="system",
            event_type="local_meta_saved"
        )

    def _save_remote(self, record: Dict[str, Any]):
        """Save metadata in Appwrite"""
        docs = self.db.list_documents(self.collection, queries=[{"model_name": record["model_name"]}])
        if docs:
            doc_id = docs[0]["$id"]
            self.db.update_document(self.collection, doc_id, record)
        else:
            self.db.create_document(self.collection, record)
        logger.info(
            message=f"Saved remote metadata for {record['model_name']}",
            source="LexiconGuard._save_remote",
            category="system",
            event_type="remote_meta_saved"
        )
