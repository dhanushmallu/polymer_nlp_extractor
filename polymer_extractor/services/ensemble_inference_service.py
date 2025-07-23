# polymer_extractor/services/ensemble_inference.py

"""
Ensemble Inference Service for Polymer NLP Extractor.

Runs inference using all fine-tuned models in the ensemble and aggregates predictions
through a robust voting strategy that balances label confidence, frequency, and alignment.

Author: Dhanush Mallu <dhanush@example.com>
"""

import os
import json
from typing import Dict, List, Any
from collections import defaultdict, Counter

import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification
from polymer_extractor.model_config import ENSEMBLE_MODELS, LABELS, ID2LABEL
from polymer_extractor.utils.paths import WORKSPACE_DIR, EXPORTS_DIR
from polymer_extractor.utils.logging import Logger

logger = Logger()


class EnsembleInferenceService:
    """
    Runs ensemble-based inference across all configured models.
    """

    def __init__(self, model_names: List[str] = None):
        self.models = []
        self.tokenizers = []
        self.model_names = model_names or [m.name for m in ENSEMBLE_MODELS]
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._load_models()

    def _load_models(self):
        """Load all models and their tokenizers from local fine-tuned paths."""
        for model_cfg in ENSEMBLE_MODELS:
            if model_cfg.name not in self.model_names:
                continue

            model_path = os.path.join(WORKSPACE_DIR, "models", f"{self._sanitize_name(model_cfg.name)}_finetuned")
            tokenizer_path = os.path.join(WORKSPACE_DIR, "tokenizers", f"{self._sanitize_name(model_cfg.model_id)}_extended")

            tokenizer = AutoTokenizer.from_pretrained(tokenizer_path if os.path.exists(tokenizer_path) else model_cfg.model_id, use_fast=True)
            model = AutoModelForTokenClassification.from_pretrained(model_path).to(self.device)
            model.eval()

            self.models.append(model)
            self.tokenizers.append(tokenizer)

            logger.info(
                f"Loaded model/tokenizer: {model_cfg.name}",
                source="ensemble_inference._load_models",
                category="inference",
                event_type="model_loaded"
            )

    def run_inference(self, windows_path: str, output_name: str = "ensemble_predictions") -> Dict[str, Any]:
        """
        Perform inference across all tokenized windows using ensemble strategy.

        Parameters
        ----------
        windows_path : str
            Path to token windows JSON file from preprocessing.
        output_name : str
            Name to use when saving final results.

        Returns
        -------
        dict
            Structured predictions by sentence and entity type.
        """
        with open(windows_path, "r", encoding="utf-8") as f:
            windows = json.load(f)

        results = defaultdict(list)

        for window in windows:
            input_ids = torch.tensor([window["input_ids"]]).to(self.device)
            attention_mask = torch.tensor([window["attention_mask"]]).to(self.device)

            all_logits = []
            for model in self.models:
                with torch.no_grad():
                    logits = model(input_ids=input_ids, attention_mask=attention_mask).logits
                    all_logits.append(logits)

            # Stack and average logits
            avg_logits = torch.stack(all_logits).mean(dim=0)
            predictions = torch.argmax(avg_logits, dim=-1).squeeze().tolist()

            tokens = self.tokenizers[0].convert_ids_to_tokens(window["input_ids"])
            spans = self._extract_labeled_spans(tokens, predictions)

            for span in spans:
                label = span["label"]
                results[label].append({
                    "text": span["text"],
                    "confidence": span["confidence"],
                    "source_window": window["window_id"]
                })

        # Save results
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        output_file = os.path.join(EXPORTS_DIR, f"{output_name}.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        logger.info(
            f"Ensemble predictions saved: {output_file}",
            source="ensemble_inference.run_inference",
            category="inference",
            event_type="results_saved"
        )

        return {
            "success": True,
            "model_count": len(self.models),
            "output_file": output_file,
            "extracted_labels": list(results.keys())
        }

    def _extract_labeled_spans(self, tokens: List[str], labels: List[int]) -> List[Dict[str, Any]]:
        """Extract labeled spans from token sequence using BIO tags."""
        spans = []
        buffer = []
        current_label = None

        for token, label_id in zip(tokens, labels):
            label = ID2LABEL.get(label_id, "O")
            if label == "O":
                if buffer:
                    spans.append({
                        "text": self._clean_token(" ".join(buffer)),
                        "label": current_label,
                        "confidence": 1.0
                    })
                    buffer = []
                    current_label = None
                continue

            prefix, tag = label.split("-", 1)
            if prefix == "B" or (current_label and tag != current_label):
                if buffer:
                    spans.append({
                        "text": self._clean_token(" ".join(buffer)),
                        "label": current_label,
                        "confidence": 1.0
                    })
                buffer = [token]
                current_label = tag
            else:
                buffer.append(token)

        if buffer:
            spans.append({
                "text": self._clean_token(" ".join(buffer)),
                "label": current_label,
                "confidence": 1.0
            })

        return spans

    def _clean_token(self, text: str) -> str:
        """Clean token strings (remove subtoken prefixes and spacing artifacts)."""
        text = text.replace(" ##", "")
        text = text.replace("##", "")
        text = text.replace(" .", ".")
        return text.strip()

    @staticmethod
    def _sanitize_name(name: str) -> str:
        return name.replace("/", "_").replace(" ", "_")
