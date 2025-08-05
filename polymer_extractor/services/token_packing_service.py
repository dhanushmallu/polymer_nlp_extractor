# polymer_extractor/services/token_packing.py

"""
Token Packing Service for Polymer NLP Extractor.

Features:
---------
- Sentence-aware, span-safe windowing using tokenizer offset_mapping
- Avoids storing token ids (no `input_ids`, `attention_mask`)
- Compatible with ensemble model config (model_config.py)
- Saves plain sentence text + traceable window metadata
- Fully model-tokenizer aware; vocab overflows eliminated
"""

import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any

from lxml import etree
from nltk.tokenize.punkt import PunktSentenceTokenizer, PunktParameters
from transformers import AutoTokenizer, PreTrainedTokenizerFast

from polymer_extractor.model_config import ENSEMBLE_MODELS
from polymer_extractor.utils.logging import Logger
from polymer_extractor.utils.paths import SAMPLES_DIR, WORKSPACE_DIR

logger = Logger()


class TokenPackingService:
    def __init__(self, max_tokens: int = 440, overlap_sentences: int = 1):
        self.max_tokens = max_tokens
        self.buffer_limit = 45
        self.actual_limit = max_tokens + self.buffer_limit  # 485 token budget
        self.overlap_sentences = overlap_sentences
        self.models = ENSEMBLE_MODELS

    def process(self, tei_path: str) -> Dict[str, Any]:
        base_name = Path(tei_path).stem
        logger.info(f"Starting token packing for {base_name}", source="TokenPackingService.process")

        raw_text = self._extract_text(tei_path)
        sentences = self._split_sentences(raw_text)
        sentence_offsets = self._compute_sentence_offsets(sentences, raw_text)

        results = {}
        for model in self.models:
            model_name = model.name
            model_id = model.model_id

            # Load tokenizer (use extended version if available)
            tokenizer_path = os.path.join(WORKSPACE_DIR, "models", "tokenizers", f"{model_name}_extended")
            tokenizer = AutoTokenizer.from_pretrained(tokenizer_path if os.path.exists(tokenizer_path) else model_id, use_fast=True)

            output_dir = os.path.join(SAMPLES_DIR, f"{model_name}_outputs")
            os.makedirs(output_dir, exist_ok=True)

            sentence_map_path = os.path.join(output_dir, f"{base_name}.tei_sentence_offsets.json")
            with open(sentence_map_path, "w", encoding="utf-8") as f:
                json.dump(sentence_offsets, f, indent=2, ensure_ascii=False)

            windows = self._pack_windows(sentences, sentence_offsets, tokenizer, model_name)

            windows_path = os.path.join(output_dir, f"{base_name}.tei_token_windows.json")
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
                "num_sentences": len(sentences)
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

    def _split_sentences(self, text: str) -> List[str]:
        punkt_params = PunktParameters()
        punkt_params.abbrev_types = {"e.g", "i.e", "Fig", "Dr", "vs"}
        splitter = PunktSentenceTokenizer(punkt_params)

        initial_sents = splitter.tokenize(text)
        refined_sents = []

        split_patterns = [
            r";",
            r"\b(which|while|although|because|whereas)\b",
            r"\band\b", r"\bor\b"
        ]

        for sent in initial_sents:
            tokenized = AutoTokenizer.from_pretrained("bert-base-uncased", use_fast=True)(sent, add_special_tokens=False)
            if len(tokenized["input_ids"]) <= self.max_tokens:
                refined_sents.append(sent)
                continue

            parts = re.split("|".join(split_patterns), sent)
            for part in parts:
                part = part.strip()
                if not part or len(part) < 20:
                    continue
                tokenized_part = AutoTokenizer.from_pretrained("bert-base-uncased", use_fast=True)(part, add_special_tokens=False)
                if len(tokenized_part["input_ids"]) <= self.max_tokens:
                    refined_sents.append(part)
                else:
                    sub_parts = re.split(r',\s+(?:and|or)\s+', part)
                    refined_sents.extend([s.strip() for s in sub_parts if len(s.strip()) >= 20])

        logger.info(f"Split {len(initial_sents)} initial sentences into {len(refined_sents)} refined sentences.",
                    source="TokenPackingService._split_sentences")
        return refined_sents

    def _compute_sentence_offsets(self, sentences: List[str], full_text: str) -> List[Dict[str, Any]]:
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

    def _pack_windows(self, sentences: List[str], sentence_offsets: List[Dict[str, Any]],
                      tokenizer: PreTrainedTokenizerFast, model_name: str) -> List[Dict[str, Any]]:

        windows = []
        buffer, buffer_meta = [], []
        current_len = 0

        def add_window():
            if buffer:
                joined_text = " ".join(buffer)
                encoded = tokenizer(joined_text, return_offsets_mapping=True, truncation=True,
                                    max_length=512, padding="max_length")
                token_count = len([tid for tid in encoded["input_ids"] if tid != tokenizer.pad_token_id])

                if token_count > 512:
                    logger.critical(
                        f"[TokenPacking] Packed token count exceeds limit: {token_count}",
                        source="TokenPackingService._pack_windows",
                        context={"model": model_name, "text_sample": joined_text[:100]}
                    )
                    return  # Skip invalid window

                windows.append({
                    "window_id": f"{model_name}_win_{len(windows):04d}",
                    "text": joined_text,
                    "sentence_meta": buffer_meta,
                    "char_start": buffer_meta[0]["char_start"],
                    "char_end": buffer_meta[-1]["char_end"],
                    "model": model_name,
                    "sentence_count": len(buffer),
                    "tokenizer_trace": {
                        "token_count": token_count,
                        "within_limit": token_count <= 512
                    }
                })

        for i, sent in enumerate(sentences):
            tokenized = tokenizer(sent, return_attention_mask=False, return_token_type_ids=False)
            token_len = len(tokenized["input_ids"])

            if token_len > self.max_tokens:
                logger.warning(f"Long sentence ({token_len} tokens): {sent[:80]}", source="TokenPackingService._pack_windows")

            if current_len + token_len > self.actual_limit:
                add_window()
                buffer, buffer_meta = [], []
                current_len = 0

            buffer.append(sent)
            buffer_meta.append(sentence_offsets[i])
            current_len += token_len

        add_window()
        return windows
 
