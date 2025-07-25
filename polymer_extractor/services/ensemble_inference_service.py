import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import torch
from torch.nn.functional import softmax
from transformers import AutoTokenizer, AutoModelForTokenClassification

from polymer_extractor.model_config import (
    ENSEMBLE_MODELS,
    LABELS,
    LABEL2ID,
    ID2LABEL,
    get_entity_threshold
)
from polymer_extractor.services.constants.property_table import PROPERTY_TABLE
from polymer_extractor.services.token_packing_service import TokenPackingService
from polymer_extractor.storage.database_manager import DatabaseManager
from polymer_extractor.utils.logging import Logger
from polymer_extractor.utils.paths import WORKSPACE_DIR

logger = Logger()
db = DatabaseManager()

STOPWORDS = {"of", "the", "at", "in", "to", "for", "on"}
REMOVE_SUFFIXES = [" based", " derived", " containing"]


class EnsembleInferenceService:
    def __init__(self):
        self.models_cfg = ENSEMBLE_MODELS
        self.models_dir = Path(WORKSPACE_DIR) / "models" / "finetuned"
        self.results_dir = Path(WORKSPACE_DIR) / "exports"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def run_inference(self, tei_path: str) -> Dict[str, Any]:
        logger.info(f"[EnsembleInference] Starting pipeline for {tei_path}",
                    source="EnsembleInferenceService.run_inference")

        base_name = Path(tei_path).stem
        all_predictions = []

        packing_service = TokenPackingService()
        packing_result = packing_service.process(tei_path)
        windows = None

        for model_cfg in self.models_cfg:
            model_name = model_cfg.name
            model_path = self.models_dir / model_name

            tokenizer_path = Path(WORKSPACE_DIR) / "models" / "tokenizers" / f"{model_name}_extended"
            tokenizer = AutoTokenizer.from_pretrained(
                tokenizer_path if tokenizer_path.exists() else model_cfg.model_id,
                use_fast=True
            )

            model = AutoModelForTokenClassification.from_pretrained(
                model_path,
                num_labels=len(LABELS),
                id2label=ID2LABEL,
                label2id=LABEL2ID
            ).eval()

            if torch.cuda.is_available():
                model.cuda()

            if windows is None:
                windows_path = packing_result["models_processed"][model_name]["windows_file"]
                with open(windows_path, "r", encoding="utf-8") as f:
                    windows = json.load(f)

            preds = self._infer_model(model, tokenizer, windows, model_name)
            all_predictions.append(preds)

            del model
            torch.cuda.empty_cache()

        merged_preds = self._merge_predictions(all_predictions)
        final_results = self._ensemble_vote_and_postprocess(merged_preds)

        self._save_results(final_results, base_name)

        return {
            "success": True,
            "tei_file": tei_path,
            "models_used": [m.name for m in self.models_cfg],
            "num_entities": sum(len(v) for v in final_results.values()),
            "output_file": str(self.results_dir / f"{base_name}_ensemble_results.json")
        }

    def _infer_model(self, model, tokenizer, windows, model_name: str) -> List[Dict[str, Any]]:
        predictions = []
        for win in windows:
            inputs = {
                "input_ids": torch.tensor([win["input_ids"]]),
                "attention_mask": torch.tensor([win["attention_mask"]])
            }
            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}

            with torch.no_grad():
                outputs = model(**inputs)
                probs = softmax(outputs.logits, dim=-1).cpu().numpy()[0]
                pred_ids = np.argmax(probs, axis=-1)

            for idx, label_id in enumerate(pred_ids):
                if ID2LABEL[label_id] == "O":
                    continue

                offset = win["offset_mapping"][idx]
                if offset[0] == offset[1]:
                    continue

                predictions.append({
                    "label": ID2LABEL[label_id],
                    "text": win["text"][offset[0]:offset[1]],
                    "char_start": offset[0],
                    "char_end": offset[1],
                    "confidence": float(probs[idx][label_id]),
                    "model": model_name
                })
        return predictions

    def _merge_predictions(self, all_predictions: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        return [p for preds in all_predictions for p in preds]

    def _ensemble_vote_and_postprocess(self, predictions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        clustered = defaultdict(list)
        for pred in predictions:
            entity_type = pred["label"].split("-")[-1]
            clustered[entity_type].append(pred)

        final_results = defaultdict(list)
        for entity_type, preds in clustered.items():
            preds.sort(key=lambda x: x["char_start"])

            while preds:
                cluster = [preds.pop(0)]
                i = 0
                while i < len(preds):
                    if preds[i]["char_start"] <= cluster[-1]["char_end"]:
                        cluster.append(preds.pop(i))
                    else:
                        i += 1

                conf_scores = []
                for c in cluster:
                    model_cfg = next(m for m in ENSEMBLE_MODELS if m.name == c["model"])
                    conf_scores.append(c["confidence"] * model_cfg.get_dynamic_weight(entity_type))

                avg_conf = np.mean(conf_scores)
                threshold = get_entity_threshold(entity_type, [], "simple_majority", conf_scores)

                if avg_conf >= threshold:
                    best_span = max(cluster, key=lambda x: x["confidence"])
                    cleaned_text = self._clean_span(best_span["text"])
                    if cleaned_text:
                        final_results[entity_type].append({
                            "text": cleaned_text,
                            "char_start": best_span["char_start"],
                            "char_end": best_span["char_end"],
                            "confidence": round(avg_conf, 4),
                            "models_voted": [c["model"] for c in cluster]
                        })

        return dict(final_results)

    def _clean_span(self, text: str) -> str:
        """Fix token joins, remove suffixes, and trim stopwords."""
        text = text.replace("##", "")
        text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        # Remove unwanted suffixes if not canonical
        for suffix in REMOVE_SUFFIXES:
            if text.lower().endswith(suffix):
                base = text[: -len(suffix)].strip()
                if base.lower() not in [p["property"].lower() for p in PROPERTY_TABLE]:
                    text = base

        # Remove trailing stopwords
        parts = text.split()
        while parts and parts[-1].lower() in STOPWORDS:
            parts.pop()
        return " ".join(parts)

    def _save_results(self, results: Dict[str, Any], base_name: str):
        local_path = self.results_dir / f"{base_name}_ensemble_results.json"
        with open(local_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        json_str = json.dumps(results, ensure_ascii=False)
        truncated = json_str[:500000]

        try:
            db.create_document("extraction_metadata", {
                "file_name": base_name,
                "extracted_entities": truncated,
                "full_json_path": str(local_path)
            })
        except Exception as e:
            logger.error(f"Appwrite save failed: {e}",
                         source="EnsembleInferenceService._save_results", error=e)
