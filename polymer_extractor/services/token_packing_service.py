# polymer_extractor/services/token_packing.py

"""
Token Packing Service for Polymer NLP Extractor.

Features:
---------
- Sentence-aware token packing (no mid-span cuts)
- Span-safe windowing using tokenizer offset_mapping
- Uses extended tokenizer (if available) for each model
- Preserves sentence boundaries and overlap
- Saves outputs to local SAMPLES_DIR for auditability
- No Appwrite storage (complies with new storage logic)
"""

import os
import json
import re
from typing import List, Dict, Any, Tuple
from pathlib import Path
from lxml import etree

from nltk.tokenize.punkt import PunktSentenceTokenizer, PunktParameters
from transformers import AutoTokenizer, PreTrainedTokenizerFast

from polymer_extractor.utils.paths import SAMPLES_DIR, WORKSPACE_DIR
from polymer_extractor.utils.logging import Logger
from polymer_extractor.model_config import ENSEMBLE_MODELS

logger = Logger()


class TokenPackingService:
    def __init__(self, max_tokens: int = 512, overlap_sentences: int = 1):
        self.max_tokens = max_tokens
        self.overlap_sentences = overlap_sentences
        self.models = ENSEMBLE_MODELS

    def process(self, tei_path: str) -> Dict[str, Any]:
        base_name = Path(tei_path).stem
        logger.info(f"Starting token packing for {base_name}", source="TokenPackingService.process")

        # Extract clean plain text from XML
        raw_text = self._extract_text(tei_path)
        sentences = self._split_sentences(raw_text)
        sentence_offsets = self._compute_sentence_offsets(sentences, raw_text)

        results = {}
        for model in self.models:
            model_name = model.name
            model_id = model.model_id
            
            # Load appropriate tokenizer
            tokenizer_path = os.path.join(WORKSPACE_DIR, "models", "tokenizers", f"{model_name}_extended")
            if os.path.exists(tokenizer_path):
                logger.info(f"Loading extended tokenizer from {tokenizer_path}", source="TokenPackingService")
                tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, use_fast=True)
            else:
                logger.info(f"Loading base tokenizer for {model_name}", source="TokenPackingService")
                tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=True)

            output_dir = os.path.join(SAMPLES_DIR, f"{model_name}_outputs")
            os.makedirs(output_dir, exist_ok=True)

            sentence_map_path = os.path.join(output_dir, f"{base_name}_sentence_offsets.json")
            with open(sentence_map_path, "w", encoding="utf-8") as f:
                json.dump(sentence_offsets, f, indent=2, ensure_ascii=False)

            # Create token windows
            windows = self._pack_windows(sentences, sentence_offsets, tokenizer, model_name)

            windows_path = os.path.join(output_dir, f"{base_name}_token_windows.json")
            with open(windows_path, "w", encoding="utf-8") as f:
                json.dump(windows, f, indent=2, ensure_ascii=False)

            results[model_name] = {
                "success": True,
                "model_name": model_name,
                "model_id": model_id,
                "source_tei": tei_path,
                "windows_file": windows_path,
                "sentence_map_file": sentence_map_path,
                "num_windows": len(windows),
                "num_sentences": len(sentences),
            }

        return {
            "success": True,
            "source_tei": tei_path,
            "num_sentences": len(sentences),
            "models_processed": results
        }

    def _extract_text(self, tei_path: str) -> str:
        tree = etree.parse(tei_path)
        raw = " ".join(tree.xpath("//text()"))
        return re.sub(r"\s+", " ", raw).strip()


    # TODO: During ensembly implement sentence rejoining logic as guided by README
    def _split_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences with domain-aware refinement.

        - Uses PunktSentenceTokenizer for initial split.
        - Further splits any sentence exceeding max token threshold using:
            • Semicolons (;)
            • Scientific clause joiners (e.g. 'which', 'while', 'although')
            • Commas and 'and'/'or' when repeated
        - Ensures no resulting sentence alone exceeds `max_tokens`.
        """
        punkt_params = PunktParameters()
        punkt_params.abbrev_types = {"e.g", "i.e", "Fig", "Dr", "vs"}
        splitter = PunktSentenceTokenizer(punkt_params)

        initial_sents = splitter.tokenize(text)
        refined_sents = []

        scientific_split_patterns = [
            r";",                      # semicolon
            r"\b(which|while|although|because|whereas)\b",  # clause joiners
            r"\band\b",                # and/or in complex clauses
            r"\bor\b"
        ]

        compound_split_re = re.compile("|".join(scientific_split_patterns), re.IGNORECASE)

        for sent in initial_sents:
            # If sentence is already fine, keep it
            tokenized = AutoTokenizer.from_pretrained("bert-base-uncased", use_fast=True)(sent)
            if len(tokenized["input_ids"]) <= self.max_tokens:
                refined_sents.append(sent)
                continue

            # Split with domain-aware clause boundaries
            parts = re.split(compound_split_re, sent)
            parts = [p.strip(",;:. ") for p in parts if len(p.strip()) > 10]

            # Recombine conservatively if some fragments too small
            buffer = ""
            for part in parts:
                if not buffer:
                    buffer = part
                    continue
                joined = buffer + " " + part
                joined_len = len(AutoTokenizer.from_pretrained("bert-base-uncased", use_fast=True)(joined)["input_ids"])
                if joined_len <= self.max_tokens:
                    buffer = joined
                else:
                    refined_sents.append(buffer.strip())
                    buffer = part
            if buffer:
                refined_sents.append(buffer.strip())

        logger.info(
            f"Split {len(initial_sents)} initial sentences into {len(refined_sents)} domain-aware sentences.",
            source="TokenPackingService._split_sentences",
            category="preprocessing",
            event_type="sentence_split"
        )
        return refined_sents


    def _compute_sentence_offsets(self, sentences: List[str], full_text: str) -> List[Dict[str, Any]]:
        """Compute char offsets of each sentence within the full text."""
        offsets = []
        cursor = 0
        for idx, sent in enumerate(sentences):
            start = full_text.find(sent, cursor)
            if start == -1:
                continue
            end = start + len(sent)
            offsets.append({
                "sentence_id": idx,
                "text": sent,
                "char_start": start,
                "char_end": end
            })
            cursor = end
        return offsets

    def _pack_windows(self, sentences: List[str], sentence_offsets: List[Dict[str, Any]], tokenizer: PreTrainedTokenizerFast, model_name: str) -> List[Dict[str, Any]]:
        """Pack full sentences into windows with preserved spans and metadata."""
        windows = []
        buffer, sentence_meta = [], []
        current_len = 0
        idx = 0

        for i, sent in enumerate(sentences):
            tokenized = tokenizer(sent, return_attention_mask=False, return_token_type_ids=False)
            token_len = len(tokenized["input_ids"])

            if current_len + token_len > self.max_tokens:
                if buffer:
                    window = self._create_window(buffer, sentence_meta, len(windows), tokenizer, model_name)
                    windows.append(window)
                    buffer = buffer[-self.overlap_sentences:] if self.overlap_sentences else []
                    sentence_meta = sentence_meta[-self.overlap_sentences:]
                    current_len = sum(len(tokenizer(s, return_attention_mask=False)["input_ids"]) for s in buffer)

            buffer.append(sent)
            sentence_meta.append(sentence_offsets[i])
            current_len += token_len

        if buffer:
            window = self._create_window(buffer, sentence_meta, len(windows), tokenizer, model_name)
            windows.append(window)

        return windows

    def _create_window(self, sentences: List[str], sentence_meta: List[Dict[str, Any]], window_index: int, tokenizer: PreTrainedTokenizerFast, model_name: str) -> Dict[str, Any]:
        joined_text = " ".join(sentences)
        encoded = tokenizer(
            joined_text,
            return_offsets_mapping=True,
            max_length=self.max_tokens,
            truncation=True,
            padding="max_length"
        )

        return {
            "window_id": f"{model_name}_win_{window_index:04d}",
            "text": joined_text,
            "sentence_meta": sentence_meta,
            "input_ids": encoded["input_ids"],
            "attention_mask": encoded["attention_mask"],
            "offset_mapping": encoded["offset_mapping"]
        }
