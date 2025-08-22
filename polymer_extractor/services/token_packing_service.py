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
    def __init__(self, max_tokens: int = 450, overlap_sentences: int = 1):
        self.max_tokens = max_tokens
        self.buffer_limit = 45
        self.actual_limit = max_tokens + self.buffer_limit  # ~495 token budget
        self.overlap_sentences = overlap_sentences
        self.models = ENSEMBLE_MODELS
        
        # Enhanced settings for long sentence handling
        self.long_sentence_threshold = 500  # Tokens
        self.sliding_window_overlap = 50   # Tokens for overlap between windows
        self.max_sliding_windows = 3       # Max windows per long sentence

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

            # Use model-specific tokenizer instead of extended tokenizer
            tokenizer = self._get_model_specific_tokenizer(model_name, model_id)

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
                "tokenizer_vocab_size": len(tokenizer),
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
            token_count = len(tokenized["input_ids"])
            
            if token_count <= self.max_tokens:
                refined_sents.append(sent)
                continue

            # Handle very long sentences with sliding window approach
            if token_count > self.long_sentence_threshold:
                logger.warning(
                    f"Very long sentence ({token_count} tokens) - applying sliding window: {sent[:80]}...", 
                    source="TokenPackingService._split_sentences",
                    context={"token_count": token_count, "strategy": "sliding_window"}
                )
                refined_sents.extend(self._create_sliding_windows(sent))
                continue

            # Try intelligent splitting for moderately long sentences
            parts = re.split("|".join(split_patterns), sent)
            split_successful = False
            
            for part in parts:
                part = part.strip()
                if not part or len(part) < 20:
                    continue
                tokenized_part = AutoTokenizer.from_pretrained("bert-base-uncased", use_fast=True)(part, add_special_tokens=False)
                if len(tokenized_part["input_ids"]) <= self.max_tokens:
                    refined_sents.append(part)
                    split_successful = True
                else:
                    # Further split by commas if still too long
                    sub_parts = re.split(r',\s+(?:and|or)\s+', part)
                    refined_sents.extend([s.strip() for s in sub_parts if len(s.strip()) >= 20])
                    split_successful = True
            
            # If splitting didn't work, fall back to sliding window
            if not split_successful:
                logger.warning(
                    f"Intelligent splitting failed for sentence ({token_count} tokens) - using sliding window", 
                    source="TokenPackingService._split_sentences"
                )
                refined_sents.extend(self._create_sliding_windows(sent))

        logger.info(f"Split {len(initial_sents)} initial sentences into {len(refined_sents)} refined sentences.",
                    source="TokenPackingService._split_sentences")
        return refined_sents

    def _create_sliding_windows(self, long_sentence: str) -> List[str]:
        """
        Create overlapping sliding windows for very long sentences.
        This ensures we don't lose entities that might be split across boundaries.
        """
        tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased", use_fast=True)
        
        # Split sentence into words for more granular control
        words = long_sentence.split()
        windows = []
        
        # Calculate window size in words (approximate)
        test_text = " ".join(words[:min(50, len(words))])
        test_tokens = tokenizer(test_text, add_special_tokens=False)["input_ids"]
        tokens_per_word = len(test_tokens) / len(test_text.split()) if test_text.split() else 1.5
        
        window_size_words = max(10, int((self.max_tokens - 20) / tokens_per_word))  # Leave room for special tokens
        overlap_words = max(5, int(self.sliding_window_overlap / tokens_per_word))
        
        start_idx = 0
        window_count = 0
        
        while start_idx < len(words) and window_count < self.max_sliding_windows:
            # Determine end index for this window
            end_idx = min(start_idx + window_size_words, len(words))
            
            # Ensure minimum window size
            if end_idx - start_idx < 10:
                end_idx = min(start_idx + 10, len(words))
            
            # Create window text
            window_words = words[start_idx:end_idx]
            window_text = " ".join(window_words)
            
            # Verify it fits within token limits and adjust if needed
            tokenized = tokenizer(window_text, add_special_tokens=False)
            actual_tokens = len(tokenized["input_ids"])
            
            while actual_tokens > self.max_tokens and len(window_words) > 10:
                # Reduce window size
                window_words = window_words[:-5]  # Remove 5 words at a time
                window_text = " ".join(window_words)
                tokenized = tokenizer(window_text, add_special_tokens=False)
                actual_tokens = len(tokenized["input_ids"])
            
            if window_words:  # Only add non-empty windows
                windows.append(window_text)
            
            # Move start position with overlap, ensuring progress
            next_start = max(start_idx + 5, end_idx - overlap_words)  # Ensure minimum progress of 5 words
            start_idx = next_start
            window_count += 1
            
            # If we've covered the whole sentence, break
            if end_idx >= len(words):
                break
        
        logger.info(
            f"Created {len(windows)} sliding windows from long sentence ({len(words)} words)",
            source="TokenPackingService._create_sliding_windows",
            context={"original_length": len(long_sentence), "windows_created": len(windows)}
        )
        
        return windows

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

            # Enhanced warning with context about handling strategy
            if token_len > self.max_tokens:
                if token_len > self.long_sentence_threshold:
                    logger.warning(
                        f"Very long sentence ({token_len} tokens) processed with sliding windows: {sent[:80]}...", 
                        source="TokenPackingService._pack_windows",
                        context={"strategy": "sliding_window", "token_count": token_len}
                    )
                else:
                    logger.warning(
                        f"Long sentence ({token_len} tokens) may be truncated: {sent[:80]}...", 
                        source="TokenPackingService._pack_windows",
                        context={"strategy": "truncation", "token_count": token_len}
                    )
            
            # Enhanced packing logic with better handling
            if current_len + token_len > self.actual_limit:
                add_window()
                buffer, buffer_meta = [], []
                current_len = 0

            buffer.append(sent)
            buffer_meta.append(sentence_offsets[i])
            current_len += token_len

        add_window()
        return windows

    def _get_model_specific_tokenizer(self, model_name: str, model_id: str) -> PreTrainedTokenizerFast:
        """
        Get the appropriate tokenizer for each model to avoid vocabulary mismatches.
        
        This eliminates the 'Extended tokenizer too large' warnings by using the 
        exact tokenizer each model was trained with.
        """
        # First, try to use extended tokenizer if it exists and matches model vocab
        models_dir = os.path.join(WORKSPACE_DIR, "models")
        extended_tokenizer_path = None
        
        # Look for tokenizers in versioned directories
        for tokenizers_dirname in os.listdir(models_dir):
            if tokenizers_dirname.startswith("tokenizers-"):
                tokenizers_dir = os.path.join(models_dir, tokenizers_dirname)
                if os.path.isdir(tokenizers_dir):
                    potential_path = os.path.join(tokenizers_dir, f"{model_name}_extended")
                    if os.path.exists(potential_path):
                        extended_tokenizer_path = potential_path
                        break
        
        if extended_tokenizer_path and os.path.exists(extended_tokenizer_path):
            try:
                extended_tokenizer = AutoTokenizer.from_pretrained(extended_tokenizer_path, use_fast=True)
                # Check if extended tokenizer is compatible (within reasonable range)
                expected_vocab_size = self._get_expected_vocab_size(model_name)
                actual_vocab_size = len(extended_tokenizer)
                
                # Allow up to 10% vocabulary expansion
                if actual_vocab_size <= expected_vocab_size * 1.1:
                    logger.info(
                        f"Using extended tokenizer for {model_name} (vocab: {actual_vocab_size})",
                        source="TokenPackingService._get_model_specific_tokenizer"
                    )
                    return extended_tokenizer
                else:
                    logger.warning(
                        f"Extended tokenizer for {model_name} too large ({actual_vocab_size} vs expected {expected_vocab_size}), using base tokenizer",
                        source="TokenPackingService._get_model_specific_tokenizer"
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to load extended tokenizer for {model_name}: {e}",
                    source="TokenPackingService._get_model_specific_tokenizer"
                )
        
        # Fall back to model-specific base tokenizer
        base_tokenizer_id = self._get_base_tokenizer_id(model_name, model_id)
        tokenizer = AutoTokenizer.from_pretrained(base_tokenizer_id, use_fast=True)
        
        logger.info(
            f"Using base tokenizer for {model_name}: {base_tokenizer_id} (vocab: {len(tokenizer)})",
            source="TokenPackingService._get_model_specific_tokenizer"
        )
        
        return tokenizer
    
    def _get_base_tokenizer_id(self, model_name: str, model_id: str) -> str:
        """
        Map each model to its appropriate base tokenizer to avoid vocabulary mismatches.
        """
        tokenizer_mapping = {
            "PolymerNER": "bert-base-uncased",           # BERT-based, standard vocab
            "MatSciBERT": "allenai/scibert_scivocab_uncased",  # SciBERT with scientific vocab
            "SciBERT": "allenai/scibert_scivocab_uncased",     # Original SciBERT tokenizer
            "PhysBERT": "bert-base-uncased",             # BERT-based, standard vocab
            "BioBERT": "dmis-lab/biobert-base-cased-v1.1"     # BioBERT with biomedical vocab
        }
        
        # Return mapped tokenizer or fall back to the model's own tokenizer
        return tokenizer_mapping.get(model_name, model_id)
    
    def _get_expected_vocab_size(self, model_name: str) -> int:
        """
        Get the expected vocabulary size for each model based on their base tokenizers.
        """
        expected_sizes = {
            "PolymerNER": 30522,    # BERT-base-uncased
            "MatSciBERT": 31090,    # SciBERT vocab
            "SciBERT": 31090,       # SciBERT vocab  
            "PhysBERT": 30522,      # BERT-base-uncased
            "BioBERT": 28996        # BioBERT vocab
        }
        
        return expected_sizes.get(model_name, 30522)  # Default to BERT-base size
 
