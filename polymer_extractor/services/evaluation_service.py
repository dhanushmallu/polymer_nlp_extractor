"""
polymer_extractor/services/evaluation_service.py

EvaluationService for Polymer NLP Extractor.

Features:
---------
- Finds matching testing dataset from Appwrite (exact or fuzzy filename match)
- Downloads dataset and loads ground-truth entities
- Loads ensemble inference results (local JSON preferred, fallback to Appwrite)
- Aligns predictions and ground truth into a comparable long format
- Computes precision, recall, F1, and accuracy
- Saves evaluation metrics into models_metadata and full CSV in model_results bucket

Author: Dhanush Mallu <dhanush@example.com>
"""

import difflib
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple

import pandas as pd

from polymer_extractor.storage.bucket_manager import BucketManager
from polymer_extractor.storage.database_manager import DatabaseManager
from polymer_extractor.utils.logging import Logger
from polymer_extractor.utils.paths import WORKSPACE_DIR

logger = Logger()
db = DatabaseManager()
bucket = BucketManager()


class EvaluationService:
    def __init__(self):
        self.datasets_collection = "datasets_metadata"
        self.extraction_collection = "extraction_metadata"
        self.results_dir = Path(WORKSPACE_DIR) / "exports"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def evaluate(self, tei_path: str, span_match_threshold: float = 0.70) -> Dict[str, Any]:
        """
        Full evaluation pipeline.

        Parameters
        ----------
        tei_path : str
            Path to processed TEI XML file.
        span_match_threshold : float, optional
            Fuzzy match threshold for entity text comparison (default=0.70).

        Returns
        -------
        dict
            Evaluation summary with metrics and file paths.
        """
        base_name = Path(tei_path).stem
        logger.info(f"[Evaluation] Starting evaluation for {base_name}",
                    source="EvaluationService.evaluate")

        # 1. Find matching dataset
        dataset_entry = self._find_matching_dataset(base_name)
        if not dataset_entry:
            logger.error(f"No matching test dataset found for {base_name}",
                         source="EvaluationService.evaluate")
            return {"success": False, "message": "No matching testing dataset found."}

        # 2. Download and load dataset
        dataset_path = self._download_dataset(dataset_entry)
        groundtruth_df = pd.read_csv(dataset_path)

        # 3. Load predictions
        predictions = self._load_predictions(base_name)
        if not predictions:
            return {"success": False, "message": "No predictions found for evaluation."}

        # 4. Normalize both datasets
        gt_entities = self._normalize_groundtruth(groundtruth_df)
        pred_entities = self._normalize_predictions(predictions)

        # 5. Compute metrics
        metrics, detailed_df = self._compute_metrics(gt_entities, pred_entities, span_match_threshold)

        # 6. Save evaluation results
        csv_path = self.results_dir / f"evaluation_results_{base_name}.csv"
        detailed_df.to_csv(csv_path, index=False)

        self._save_to_metadata(base_name, metrics, csv_path)

        logger.info(f"[Evaluation] Completed evaluation for {base_name}",
                    source="EvaluationService.evaluate")

        return {
            "success": True,
            "file_evaluated": base_name,
            "matched_dataset": dataset_entry.get("original_filename"),
            "metrics": metrics,
            "summary": {
                "total_groundtruth_entities": len(gt_entities),
                "total_predicted_entities": len(pred_entities)
            },
            "results_csv": str(csv_path),
            "saved_to_models_metadata": True
        }

    def _find_matching_dataset(self, file_stem: str) -> Dict[str, Any]:
        """Find dataset entry in Appwrite matching the file name or fuzzy match."""
        datasets = db.list_documents(self.datasets_collection)
        candidates = [d for d in datasets if d.get("type") == "testing"]

        for entry in candidates:
            target_input = entry.get("target_input", "")
            if not target_input:
                continue
            if file_stem in target_input or target_input in file_stem:
                return entry
            # Handle underscore suffix case
            if "_" in file_stem and file_stem.split("_")[0] == Path(target_input).stem:
                return entry
        return None

    def _download_dataset(self, entry: Dict[str, Any]) -> str:
        """Download dataset CSV locally."""
        file_url = entry.get("file_url")
        file_name = entry.get("original_filename") or entry.get("dataset_name") + ".csv"
        local_path = Path(WORKSPACE_DIR) / "datasets" / "testing" / file_name
        os.makedirs(local_path.parent, exist_ok=True)

        try:
            bucket.download_file("datasets_bucket", file_url, str(local_path))
            return str(local_path)
        except Exception as e:
            logger.error(f"Failed to download dataset: {e}",
                         source="EvaluationService._download_dataset", error=e)
            raise

    def _load_predictions(self, base_name: str) -> Dict[str, Any]:
        """Load ensemble inference results (local JSON preferred, fallback Appwrite)."""
        local_json = self.results_dir / f"{base_name}_ensemble_results.json"
        if local_json.exists():
            with open(local_json, "r", encoding="utf-8") as f:
                return json.load(f)

        try:
            doc = db.get_document(self.extraction_collection, base_name)
            if doc and doc.get("extracted_entities"):
                return json.loads(doc["extracted_entities"])
        except Exception as e:
            logger.error(f"Failed to load predictions: {e}",
                         source="EvaluationService._load_predictions", error=e)
        return None

    def _normalize_groundtruth(self, df: pd.DataFrame) -> List[Dict[str, str]]:
        """Convert ground-truth CSV to long-format entity list."""
        entities = []
        entity_patterns = ["polymer", "property", "value", "unit", "symbol", "material"]

        for _, row in df.iterrows():
            sentence = row.get("sentence", "")
            for pattern in entity_patterns:
                cols = [c for c in df.columns if c.lower().startswith(pattern)]
                for c in cols:
                    val = str(row[c]).strip()
                    if val and val.lower() != "nan":
                        entities.append({
                            "sentence": sentence,
                            "entity_type": pattern.upper(),
                            "entity_text": val
                        })
        return entities

    def _normalize_predictions(self, predictions: Dict[str, Any]) -> List[Dict[str, str]]:
        """Convert predictions JSON to long-format entity list."""
        entities = []
        for ent_type, ents in predictions.items():
            for ent in ents:
                entities.append({
                    "sentence": None,  # sentence-level matching skipped
                    "entity_type": ent_type.upper(),
                    "entity_text": ent["text"].strip()
                })
        return entities

    def _compute_metrics(
            self,
            groundtruth: List[Dict[str, str]],
            predictions: List[Dict[str, str]],
            threshold: float
    ) -> Tuple[Dict[str, float], pd.DataFrame]:
        """Compute precision, recall, F1, accuracy with fuzzy span matching."""
        matches = []
        tp, fp, fn = 0, 0, 0

        gt_used = set()
        for pred in predictions:
            pred_text = pred["entity_text"].lower()
            pred_type = pred["entity_type"]

            best_match = None
            best_score = 0.0
            for i, gt in enumerate(groundtruth):
                if i in gt_used or gt["entity_type"] != pred_type:
                    continue
                score = difflib.SequenceMatcher(None, pred_text, gt["entity_text"].lower()).ratio()
                if score > best_score:
                    best_score = score
                    best_match = i

            if best_match is not None and best_score >= threshold:
                tp += 1
                gt_used.add(best_match)
                matches.append({**pred, "match": True, "similarity": round(best_score, 3)})
            else:
                fp += 1
                matches.append({**pred, "match": False, "similarity": round(best_score, 3)})

        fn = len(groundtruth) - len(gt_used)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = tp / len(groundtruth) if len(groundtruth) > 0 else 0

        metrics = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "accuracy": round(accuracy, 4),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn
        }

        return metrics, pd.DataFrame(matches)

    def _save_to_metadata(self, base_name: str, metrics: Dict[str, Any], csv_path: Path):
        """Save evaluation metrics to models_metadata and upload CSV."""
        try:
            bucket_id = "model_results_bucket"
            bucket.create_bucket(bucket_id, "Model evaluation results")
            uploaded = bucket.upload_file(bucket_id, str(csv_path))

            db.create_document("models_metadata", {
                "file_name": base_name,
                "metrics": json.dumps(metrics),
                "results_csv": uploaded.get("$id", ""),
                "timestamp": pd.Timestamp.now().isoformat()
            })

            logger.info(f"Saved evaluation results for {base_name}",
                        source="EvaluationService._save_to_metadata")
        except Exception as e:
            logger.error(f"Failed to save evaluation results: {e}",
                         source="EvaluationService._save_to_metadata", error=e)
