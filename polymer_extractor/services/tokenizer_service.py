# polymer_extractor/services/tokenizer_service.py

"""
TokenizerService for Polymer NLP Extractor

Features:
---------
- Audits and extends Hugging Face tokenizers for scientific term coverage
- Pulls and harmonizes terms from training and testing datasets in Appwrite
- Deduplicates and canonicalizes labels using fuzzy matching
- Saves extended tokenizers locally to models/tokenizers/
- Supports force overwrite and selective build
"""

import os
import re
import zipfile
import pandas as pd
from typing import Dict, Any, Set, List, Tuple
from transformers import AutoTokenizer, PreTrainedTokenizerFast

from polymer_extractor.model_config import ENSEMBLE_MODELS
from polymer_extractor.utils.logging import Logger
from polymer_extractor.storage.database_manager import DatabaseManager
from polymer_extractor.storage.bucket_manager import BucketManager
from polymer_extractor.services.constants.polymer_names import POLYMER_NAMES
from polymer_extractor.services.constants.property_names import PROPERTY_NAMES
from polymer_extractor.services.constants.material_names import MATERIAL_NAMES
from polymer_extractor.services.constants.property_table import PROPERTY_TABLE
from polymer_extractor.services.constants.value_formats import VALUE_FORMATS
from polymer_extractor.services.constants.scientific_units import SCIENTIFIC_UNITS
from polymer_extractor.services.constants.scientific_symbols import SCIENTIFIC_SYMBOLS
from polymer_extractor.services.constants.greek_letters import (
    LOWERCASE_GREEK_LETTERS, UPPERCASE_GREEK_LETTERS, NAMED_GREEK_LETTERS
)
from polymer_extractor.utils.paths import (
    TOKENIZERS_DIR, TRAINING_DATA_DIR, TESTING_DATA_DIR
)

logger = Logger()
db = DatabaseManager()
bucket = BucketManager()


class TokenizerService:
    """
    TokenizerService to extend Hugging Face tokenizers with domain-specific terms.
    """

    def __init__(self):
        self.models = ENSEMBLE_MODELS
        self.tokenizer_dir = TOKENIZERS_DIR

    def audit_and_extend_all(self, force: bool = False) -> Dict[str, Any]:
        logger.info("Starting tokenizer audit and extension", source="TokenizerService.audit_and_extend_all")

        # Pull dataset terms and merge with constants
        all_terms = self._harvest_terms_from_datasets()
        static_terms = self._fetch_static_terms()
        combined_terms = all_terms | static_terms
        combined_terms = self._canonicalize_terms(combined_terms)
        combined_terms = self._deduplicate_fuzzy_matches(combined_terms)

        results = {}
        for model in self.models:
            model_name = model.name
            model_id = model.model_id
            try:
                result = self._audit_and_extend_single(model_name, model_id, combined_terms, force)
                results[model_name] = result
            except Exception as e:
                logger.error(f"Tokenizer failed for {model_name} ({model_id}): {e}",
                             source="TokenizerService.audit_and_extend_all", error=e)
                results[model_name] = {"success": False, "error": str(e)}

        return results

    def _harvest_terms_from_datasets(self) -> Set[str]:
        logger.info("Harvesting labeled terms from datasets_metadata",
                    source="TokenizerService._harvest_terms_from_datasets")

        datasets = db.list_documents("datasets_metadata")
        term_set = set()

        for doc in datasets:
            file_type = doc.get("type")
            file_name = doc.get("original_filename")  # FIXED
            dataset_id = doc.get("dataset_name")
            file_url = doc.get("file_url")

            if file_type not in ["training", "testing"] or not file_name:
                logger.warning(f"Skipping dataset (invalid): dataset_name={dataset_id}, file_name={file_name}",
                            source="TokenizerService._harvest_terms_from_datasets")
                continue

            local_dir = TRAINING_DATA_DIR if file_type == "training" else TESTING_DATA_DIR
            local_path = os.path.join(local_dir, file_name)

            bucket.download_file("datasets_bucket", file_url, local_path)

            try:
                df = pd.read_csv(local_path)
                for col in df.columns:
                    if re.match(r"(polymer|property|value|unit|symbol|material)_\d+", col.lower()):
                        df[col] = df[col].astype(str).fillna("").str.strip()
                        term_set.update(df[col].unique())
            except Exception as e:
                logger.error(f"Failed parsing dataset: {dataset_id} ({file_name}): {e}",
                            source="TokenizerService._harvest_terms_from_datasets", error=e)


        return {t for t in term_set if t and len(t) >= 2}

    def _audit_and_extend_single(self, model_name: str, model_id: str, terms: Set[str], force: bool = False) -> Dict[str, Any]:
        tokenizer_output_dir = os.path.join(self.tokenizer_dir, f"{model_name}_extended")

        if os.path.exists(tokenizer_output_dir) and not force:
            logger.info(f"Tokenizer already exists for {model_name}, skipping...",
                        source="TokenizerService._audit_and_extend_single")
            return {"success": True, "skipped": True, "path": tokenizer_output_dir}

        tokenizer: PreTrainedTokenizerFast = AutoTokenizer.from_pretrained(model_id, use_fast=True)
        base_vocab_size = len(tokenizer)

        split_terms, _ = self._audit_terms(tokenizer, terms)
        new_tokens = tokenizer.add_tokens(split_terms)
        special_tokens = self._add_special_tokens(tokenizer)

        os.makedirs(tokenizer_output_dir, exist_ok=True)
        tokenizer.save_pretrained(tokenizer_output_dir)

        return {
            "success": True,
            "model_name": model_name,
            "model_id": model_id,
            "base_vocab_size": base_vocab_size,
            "new_tokens_added": new_tokens,
            "special_tokens_added": special_tokens,
            "tokenizer_dir": tokenizer_output_dir
        }

    def _fetch_static_terms(self) -> Set[str]:
        terms = set(POLYMER_NAMES + PROPERTY_NAMES + MATERIAL_NAMES +
                    VALUE_FORMATS + SCIENTIFIC_UNITS + SCIENTIFIC_SYMBOLS)
        for row in PROPERTY_TABLE:
            terms.add(row.get("property", ""))
            terms.update(row.get("aliases", []))
        return {t.strip() for t in terms if t.strip()}

    def _canonicalize_terms(self, terms: Set[str]) -> Set[str]:
        return {re.sub(r"\b(s|es)$", "", t.lower().strip()) for t in terms}

    def _deduplicate_fuzzy_matches(self, terms: Set[str], threshold: float = 0.92) -> Set[str]:
        from difflib import SequenceMatcher
        deduped = set()
        for term in sorted(terms, key=lambda x: len(x), reverse=True):
            if not any(SequenceMatcher(None, term, existing).ratio() >= threshold for existing in deduped):
                deduped.add(term)
        return deduped

    def _audit_terms(self, tokenizer: PreTrainedTokenizerFast, terms: Set[str]) -> Tuple[List[str], List[str]]:
        split, whole = [], []
        for term in terms:
            toks = tokenizer.tokenize(term)
            if len(toks) > 1 or any(tok.startswith("##") for tok in toks):
                split.append(term)
            else:
                whole.append(term)
        return split, whole

    def _add_special_tokens(self, tokenizer: PreTrainedTokenizerFast) -> int:
        specials = list(set(
            LOWERCASE_GREEK_LETTERS +
            UPPERCASE_GREEK_LETTERS +
            NAMED_GREEK_LETTERS +
            SCIENTIFIC_UNITS +
            SCIENTIFIC_SYMBOLS +
            ["°C", "ΔH", "kJ/mol"]
        ))
        tokenizer.add_special_tokens({"additional_special_tokens": specials})
        return len(specials)
