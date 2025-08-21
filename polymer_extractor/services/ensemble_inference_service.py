"""
Enhanced ensemble inference service with complete rewrite implementing all improvements:

1. No reliance on serialized token IDs - full re-tokenization during inference
2. Complete offset mapping recomputation using inference tokenizer  
3. Full span retention with no trimming in _clean_span()
4. VALUE-UNIT semantic boosting using ENTITY_RELATIONSHIP_PATTERNS
5. Dynamic postprocessing_steps activation
6. Strategy-specific metadata logging
7. Adaptive ensemble strategies with fallback mechanisms
"""

import json
import re
import os
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from itertools import combinations
from datetime import datetime
import math
from difflib import SequenceMatcher

import numpy as np
import torch
from torch.nn.functional import softmax
from transformers import AutoTokenizer, AutoModelForTokenClassification
from lxml import etree

from polymer_extractor.model_config import (
    ENSEMBLE_MODELS,
    LABELS,
    LABEL2ID,
    ID2LABEL,
    get_entity_threshold,
    get_model_by_name,
    EnsembleStrategy,
    ENTITY_RELATIONSHIP_PATTERNS,
    DynamicThresholds,
    VALIDATION_CONFIDENCE_ADJUSTMENTS,
    get_validation_boost,
    ENTITY_SEMANTIC_GROUPS,
    PROCESSING_CONFIG,
    POST_PROCESSING_CONFIG,
    get_ensemble_strategy_config
)
from polymer_extractor.services.constants.property_table import PROPERTY_TABLE
from polymer_extractor.services.token_packing_service import TokenPackingService
from polymer_extractor.services.enhanced_merging_service import StrictSentenceProcessor
from polymer_extractor.storage.database_manager import DatabaseManager
from polymer_extractor.utils.logging import Logger
from polymer_extractor.utils.paths import WORKSPACE_DIR

# Initialize logger
logger = Logger()


class JSONSerializable:
    """Utility class to handle JSON serialization of numpy and torch types."""
    
    @staticmethod
    def convert_to_json_serializable(obj):
        """Convert numpy/torch types to JSON-serializable Python types."""
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.float64, np.float32, np.floating)):
            return float(obj)
        elif isinstance(obj, (np.ndarray, torch.Tensor)):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {key: JSONSerializable.convert_to_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [JSONSerializable.convert_to_json_serializable(item) for item in obj]
        else:
            return obj

    @staticmethod
    def safe_json_dumps(obj, **kwargs):
        """Safely serialize objects to JSON with automatic type conversion."""
        try:
            return json.dumps(obj, **kwargs)
        except TypeError:
            # Convert problematic types and try again
            converted_obj = JSONSerializable.convert_to_json_serializable(obj)
            return json.dumps(converted_obj, **kwargs)


@dataclass
@dataclass
class PredictionCandidate:
    """Enhanced prediction candidate with full metadata."""
    text: str
    char_start: int
    char_end: int
    entity_type: str
    label: str
    confidence: float
    calibrated_confidence: float
    model: str
    window_id: str
    token_position: int
    context_snippet: str = ""
    validation_flags: List[str] = None
    semantic_relationships: List[Dict[str, Any]] = None
    postprocessing_applied: List[str] = None
    validation_boosts_applied: List[str] = None
    strategies_attempted: List[str] = None

    def __post_init__(self):
        if self.validation_flags is None:
            self.validation_flags = []
        if self.semantic_relationships is None:
            self.semantic_relationships = []
        if self.postprocessing_applied is None:
            self.postprocessing_applied = []
        if self.validation_boosts_applied is None:
            self.validation_boosts_applied = []
        if self.strategies_attempted is None:
            self.strategies_attempted = []

@dataclass 
class ClusterVote:
    """Represents a vote in an entity cluster."""
    prediction: PredictionCandidate
    weight: float
    confidence_score: float
    semantic_boost: float = 0.0
    validation_boost: float = 0.0
    
@dataclass
class EnsembleCluster:
    """Complete cluster with voting metadata."""
    entity_type: str
    votes: List[ClusterVote]
    consensus_text: str
    consensus_span: Tuple[int, int]
    final_confidence: float
    strategy_used: str
    processing_metadata: Dict[str, Any]

class SemanticAnalyzer:
    """Handles semantic relationship detection and confidence boosting."""
    
    def __init__(self):
        self.relationship_patterns = ENTITY_RELATIONSHIP_PATTERNS
    
    def detect_relationships(self, predictions: List[PredictionCandidate], 
                           window_text: str) -> Dict[str, List[Dict[str, Any]]]:
        """Detect semantic relationships between entities."""
        relationships = defaultdict(list)
        
        # Sort predictions by position
        sorted_preds = sorted(predictions, key=lambda p: p.char_start)
        
        for i, pred1 in enumerate(sorted_preds):
            for j, pred2 in enumerate(sorted_preds[i+1:], i+1):
                relationship = self._analyze_pair(pred1, pred2, window_text)
                if relationship:
                    relationships[relationship['type']].append(relationship)
                    
        return dict(relationships)
    
    def _analyze_pair(self, pred1: PredictionCandidate, pred2: PredictionCandidate, 
                     context: str) -> Optional[Dict[str, Any]]:
        """Analyze a pair of predictions for semantic relationships."""
        distance = abs(pred1.char_start - pred2.char_start)
        
        # VALUE-UNIT pairs
        if self._is_value_unit_pair(pred1, pred2):
            pattern = self.relationship_patterns["VALUE_UNIT_PAIRS"]
            if distance <= pattern["distance_threshold"] * 10:  # Convert token distance to char estimate
                return {
                    'type': 'VALUE_UNIT_PAIR',
                    'entities': [pred1.text, pred2.text],
                    'confidence_boost': pattern["confidence_boost"],
                    'distance': distance,
                    'strength': max(0, 1 - (distance / (pattern["distance_threshold"] * 20)))
                }
        
        # PROPERTY-VALUE relationships
        if self._is_property_value_pair(pred1, pred2):
            pattern = self.relationship_patterns["PROPERTY_VALUE_RELATIONSHIPS"]
            if distance <= pattern["distance_threshold"] * 15:
                return {
                    'type': 'PROPERTY_VALUE_PAIR',
                    'entities': [pred1.text, pred2.text],
                    'confidence_boost': pattern["confidence_boost"],
                    'distance': distance,
                    'strength': max(0, 1 - (distance / (pattern["distance_threshold"] * 30)))
                }
        
        # POLYMER-PROPERTY associations
        if self._is_polymer_property_pair(pred1, pred2):
            pattern = self.relationship_patterns["POLYMER_PROPERTY_ASSOCIATIONS"]
            if distance <= pattern["distance_threshold"] * 20:
                return {
                    'type': 'POLYMER_PROPERTY_PAIR',
                    'entities': [pred1.text, pred2.text],
                    'confidence_boost': pattern["confidence_boost"],
                    'distance': distance,
                    'strength': max(0, 1 - (distance / (pattern["distance_threshold"] * 40)))
                }
        
        return None
    
    def _is_value_unit_pair(self, pred1: PredictionCandidate, pred2: PredictionCandidate) -> bool:
        """Check if two predictions form a VALUE-UNIT pair using semantic groups."""
        types = {pred1.entity_type, pred2.entity_type}
        # Use ENTITY_SEMANTIC_GROUPS to check for critical pairs
        critical_pairs = ENTITY_SEMANTIC_GROUPS.get("CRITICAL_PAIRS", [])
        return types == {"VALUE", "UNIT"} or ("VALUE", "UNIT") in critical_pairs or ("UNIT", "VALUE") in critical_pairs
    
    def _is_property_value_pair(self, pred1: PredictionCandidate, pred2: PredictionCandidate) -> bool:
        """Check if two predictions form a PROPERTY-VALUE pair using semantic groups."""
        types = {pred1.entity_type, pred2.entity_type}
        critical_pairs = ENTITY_SEMANTIC_GROUPS.get("CRITICAL_PAIRS", [])
        return types == {"PROPERTY", "VALUE"} or ("PROPERTY", "VALUE") in critical_pairs or ("VALUE", "PROPERTY") in critical_pairs
    
    def _is_polymer_property_pair(self, pred1: PredictionCandidate, pred2: PredictionCandidate) -> bool:
        """Check if two predictions form a POLYMER-PROPERTY pair using semantic groups."""
        types = {pred1.entity_type, pred2.entity_type}
        critical_pairs = ENTITY_SEMANTIC_GROUPS.get("CRITICAL_PAIRS", [])
        return types == {"POLYMER", "PROPERTY"} or ("POLYMER", "PROPERTY") in critical_pairs or ("PROPERTY", "POLYMER") in critical_pairs

class PostProcessor:
    """Handles dynamic postprocessing steps."""
    
    def __init__(self):
        self.property_table = {p.get("property", "").lower(): p for p in PROPERTY_TABLE}
        self.processing_config = PROCESSING_CONFIG
        self.postprocessing_config = POST_PROCESSING_CONFIG
        self.confidence_thresholds = self.postprocessing_config.get("CONFIDENCE_THRESHOLDS", {})
        
    def apply_postprocessing_steps(self, prediction: PredictionCandidate, 
                                 steps: List[str]) -> PredictionCandidate:
        """Apply specified postprocessing steps."""
        processed = prediction
        
        for step in steps:
            if step == "unit_standardization":
                processed = self._standardize_units(processed)
            elif step == "polymer_validation":
                processed = self._validate_polymer(processed)
            elif step == "synonym_resolution":
                processed = self._resolve_synonyms(processed)
            elif step == "physics_validation":
                processed = self._validate_physics(processed)
            elif step == "dimensional_analysis":
                processed = self._dimensional_analysis(processed)
            elif step == "general_validation":
                processed = self._general_validation(processed)
            elif step == "confidence_calibration":
                processed = self._calibrate_confidence(processed)
                
        return processed
    
    def _standardize_units(self, pred: PredictionCandidate) -> PredictionCandidate:
        """Standardize unit representations."""
        if pred.entity_type != "UNIT":
            return pred
            
        text = pred.text
        original_text = text
        
        # Common unit standardizations
        unit_mappings = {
            "°C": "°C", "celsius": "°C", "deg C": "°C", "degC": "°C",
            "K": "K", "kelvin": "K",
            "MPa": "MPa", "mpa": "MPa", "megapascal": "MPa",
            "GPa": "GPa", "gpa": "GPa", "gigapascal": "GPa",
            "kJ/mol": "kJ/mol", "kj/mol": "kJ/mol", "kJmol−1": "kJ/mol", "kJ mol−1": "kJ/mol",
            "g/mol": "g/mol", "gmol−1": "g/mol", "g mol−1": "g/mol",
            "nm": "nm", "nanometer": "nm", "nanometers": "nm",
            "μm": "μm", "micrometer": "μm", "micrometers": "μm", "micron": "μm",
            "mm": "mm", "millimeter": "mm", "millimeters": "mm",
            "cm": "cm", "centimeter": "cm", "centimeters": "cm",
            "m": "m", "meter": "m", "meters": "m",
            "%": "%", "percent": "%", "pct": "%",
            "wt%": "wt%", "wt.%": "wt%", "weight%": "wt%", "weight percent": "wt%"
        }
        
        # Apply standardization
        standardized = unit_mappings.get(text.lower(), text)
        if standardized != text:
            pred.text = standardized
            pred.postprocessing_applied.append("unit_standardization")
            validation_type = "UNIT_STANDARDIZED"
            pred.validation_flags.append(validation_type)
            # Apply the configured confidence boost
            boost = get_validation_boost(validation_type)
            pred.calibrated_confidence = min(pred.calibrated_confidence + boost, 1.0)
            pred.validation_boosts_applied.append(f"{validation_type}:+{boost}")
            
        return pred
    
    def _validate_polymer(self, pred: PredictionCandidate) -> PredictionCandidate:
        """Validate and enhance polymer predictions."""
        if pred.entity_type != "POLYMER":
            return pred
            
        text = pred.text.lower()
        
        # Common polymer patterns and validations
        polymer_patterns = [
            r"poly\w+", r"\w+ene$", r"\w+ane$", r"\w+yne$",
            r"pvc", r"pet", r"abs", r"pmma", r"ptfe", r"peek",
            r"\w+mer$", r"\w+polymer$"
        ]
        
        # Check if text matches polymer patterns
        if any(re.search(pattern, text) for pattern in polymer_patterns):
            validation_type = "POLYMER_PATTERN_MATCH"
            pred.validation_flags.append(validation_type)
            # Apply the configured confidence boost instead of hardcoded value
            boost = get_validation_boost(validation_type)
            pred.calibrated_confidence = min(pred.calibrated_confidence + boost, 1.0)
            pred.validation_boosts_applied.append(f"{validation_type}:+{boost}")
            
        pred.postprocessing_applied.append("polymer_validation")
        return pred
    
    def _resolve_synonyms(self, pred: PredictionCandidate) -> PredictionCandidate:
        """Resolve entity synonyms to canonical forms with confidence boost."""
        # This would contain extensive synonym mappings
        text_lower = pred.text.lower().strip()
        
        # Basic synonym mappings for common cases
        synonym_mappings = {
            # Units
            "celsius": "°C", "centigrade": "°C", "deg c": "°C",
            "kelvin": "K", "degrees kelvin": "K",
            "pascal": "Pa", "pascals": "Pa",
            
            # Polymers  
            "polyethylene": "PE", "polypropylene": "PP", "polystyrene": "PS",
            "poly(ethylene)": "PE", "poly(propylene)": "PP",
            
            # Properties
            "glass transition temperature": "Tg", "melting temperature": "Tm",
            "elastic modulus": "E", "young's modulus": "E"
        }
        
        canonical_form = synonym_mappings.get(text_lower)
        if canonical_form:
            pred.text = canonical_form
            validation_type = "FUZZY_CANONICAL_MATCH"
            pred.validation_flags.append(validation_type)
            boost = get_validation_boost(validation_type)
            pred.calibrated_confidence = min(pred.calibrated_confidence + boost, 1.0)
            pred.validation_boosts_applied.append(f"{validation_type}:+{boost}")
        
        pred.postprocessing_applied.append("synonym_resolution")
        return pred
    
    def _validate_physics(self, pred: PredictionCandidate) -> PredictionCandidate:
        """Validate physics-related entities."""
        if pred.entity_type not in ["PROPERTY", "SYMBOL", "VALUE"]:
            return pred
        
        text_lower = pred.text.lower().strip()
        
        # Physics property patterns and validations
        physics_patterns = {
            "PROPERTY": [
                r".*temperature$", r".*modulus$", r".*strength$", r".*energy$",
                r".*pressure$", r".*viscosity$", r".*density$", r".*conductivity$"
            ],
            "SYMBOL": [
                r"^[A-Z][a-z]?[0-9]*$",  # Element symbols
                r"^[A-Za-z]+[0-9]+$",    # Chemical formulas
                r"^[GTEKPMμnmkc]?[a-zA-Z]+$"  # Unit symbols with prefixes
            ],
            "VALUE": [
                r"^\d+\.?\d*$",          # Numeric values
                r"^\d+\.?\d*[eE][+-]?\d+$",  # Scientific notation
                r"^\d+[-–]\d+$"          # Ranges
            ]
        }
        
        entity_patterns = physics_patterns.get(pred.entity_type, [])
        if any(re.search(pattern, text_lower) for pattern in entity_patterns):
            validation_type = "SCIENTIFIC_PATTERN_MATCH"
            pred.validation_flags.append(validation_type)
            boost = get_validation_boost(validation_type)
            pred.calibrated_confidence = min(pred.calibrated_confidence + boost, 1.0)
            pred.validation_boosts_applied.append(f"{validation_type}:+{boost}")
            
        pred.postprocessing_applied.append("physics_validation")
        return pred
    
    def _dimensional_analysis(self, pred: PredictionCandidate) -> PredictionCandidate:
        """Perform dimensional analysis on units and values with validation boosts."""
        if pred.entity_type not in ["UNIT", "VALUE"]:
            return pred
        
        text = pred.text.strip()
        
        # Unit dimensional validation
        if pred.entity_type == "UNIT":
            # Check for valid dimensional patterns
            dimensional_patterns = [
                r".*[Pp]a$",         # Pressure units (Pa, MPa, GPa)
                r".*[Gg]$",          # Mass units (g, kg, mg)
                r".*[Mm]$",          # Length units (m, cm, mm, nm)
                r".*[KkCc]$",        # Temperature units (K, °C)
                r".*[Jj]/mol$",      # Energy per mol units
                r".*[Mm]ol$",        # Molecular units
                r".*%$",             # Percentage units
                r".*[Ss]$"           # Time units (s, ms)
            ]
            
            if any(re.search(pattern, text) for pattern in dimensional_patterns):
                validation_type = "UNIT_VALIDATION_PASS"
                pred.validation_flags.append(validation_type)
                boost = get_validation_boost(validation_type)
                pred.calibrated_confidence = min(pred.calibrated_confidence + boost, 1.0)
                pred.validation_boosts_applied.append(f"{validation_type}:+{boost}")
        
        # Value dimensional validation
        elif pred.entity_type == "VALUE":
            # Check for valid numeric patterns
            numeric_patterns = [
                r"^\d+\.?\d*$",                    # Simple numbers
                r"^\d+\.?\d*[eE][+-]?\d+$",       # Scientific notation
                r"^\d+\.?\d*\s*[×x]\s*10\^?[+-]?\d+$",  # Scientific with multiplication
                r"^\d+[-–]\d+$",                  # Ranges
                r"^[<>~≈≤≥]\s*\d+\.?\d*$"         # Comparison operators
            ]
            
            if any(re.search(pattern, text) for pattern in numeric_patterns):
                validation_type = "SCIENTIFIC_PATTERN_MATCH"
                pred.validation_flags.append(validation_type)
                boost = get_validation_boost(validation_type)
                pred.calibrated_confidence = min(pred.calibrated_confidence + boost, 1.0)
                pred.validation_boosts_applied.append(f"{validation_type}:+{boost}")
                
        pred.postprocessing_applied.append("dimensional_analysis")
        return pred
    
    def _general_validation(self, pred: PredictionCandidate) -> PredictionCandidate:
        """Apply general validation rules with context coherence checking."""
        text = pred.text.strip()
        
        # General coherence checks
        coherence_passed = True
        
        # Check for reasonable entity length
        if len(text) < 1 or len(text) > 100:
            coherence_passed = False
        
        # Check for non-empty, meaningful text
        if not text or text.isspace() or len(text.replace(' ', '')) < 1:
            coherence_passed = False
        
        # Check for reasonable character composition
        if text and not any(c.isalnum() for c in text):
            coherence_passed = False
        
        # Apply context coherence boost if validation passes
        if coherence_passed:
            validation_type = "CONTEXT_COHERENCE" 
            pred.validation_flags.append(validation_type)
            boost = get_validation_boost(validation_type)
            pred.calibrated_confidence = min(pred.calibrated_confidence + boost, 1.0)
            pred.validation_boosts_applied.append(f"{validation_type}:+{boost}")
        
        # Check for exact matches with known canonical forms
        canonical_entities = {
            # Common exact matches for polymer science
            "POLYMER": ["PE", "PP", "PS", "PVC", "PTFE", "PMMA", "PET", "PA", "PC"],
            "PROPERTY": ["Tg", "Tm", "E", "σ", "ε", "η", "ρ", "Cp", "λ"],
            "UNIT": ["°C", "K", "Pa", "MPa", "GPa", "g/mol", "kJ/mol", "nm", "μm", "mm", "cm", "m", "%", "wt%"],
            "SYMBOL": ["C", "H", "O", "N", "S", "Si", "Al", "Fe", "Cu", "Zn"]
        }
        
        entity_canonicals = canonical_entities.get(pred.entity_type, [])
        if text in entity_canonicals:
            validation_type = "EXACT_CANONICAL_MATCH"
            pred.validation_flags.append(validation_type)
            boost = get_validation_boost(validation_type)
            pred.calibrated_confidence = min(pred.calibrated_confidence + boost, 1.0)
            pred.validation_boosts_applied.append(f"{validation_type}:+{boost}")
                
        pred.postprocessing_applied.append("general_validation")
        return pred
    
    def _calibrate_confidence(self, pred: PredictionCandidate) -> PredictionCandidate:
        """Calibrate confidence based on various factors using domain expertise."""
        original_confidence = pred.calibrated_confidence
        
        # Domain expertise adjustment based on model specialization
        model_cfg = get_model_by_name(pred.model)
        if model_cfg:
            expertise_score = model_cfg.expertise.entity_weights.get(pred.entity_type, 1.0)
            if expertise_score > 1.5:  # High expertise
                validation_type = "DOMAIN_EXPERTISE_MATCH"
                pred.validation_flags.append(validation_type)
                boost = get_validation_boost(validation_type)
                pred.calibrated_confidence = min(pred.calibrated_confidence + boost, 1.0)
                pred.validation_boosts_applied.append(f"{validation_type}:+{boost}")
        
        # Text quality-based calibration
        text = pred.text.strip()
        
        # Boost for complete scientific terms (multi-word entities)
        if ' ' in text and len(text.split()) >= 2:
            word_count = len(text.split())
            if word_count >= 3:  # Complex scientific terms
                boost = 0.03
                pred.calibrated_confidence = min(pred.calibrated_confidence + boost, 1.0) 
                pred.validation_boosts_applied.append(f"MULTI_WORD_TERM:+{boost}")
        
        # Entity type specific calibration
        type_calibrations = {
            "POLYMER": 0.02,    # Polymer entities often well-defined
            "PROPERTY": 0.01,   # Properties can be variable
            "UNIT": 0.03,       # Units are typically clear-cut
            "VALUE": -0.01,     # Values can be ambiguous
            "SYMBOL": 0.02      # Symbols are typically precise
        }
        
        type_adjustment = type_calibrations.get(pred.entity_type, 0.0)
        if type_adjustment != 0.0:
            pred.calibrated_confidence = max(0.1, min(pred.calibrated_confidence + type_adjustment, 1.0))
            if type_adjustment > 0:
                pred.validation_boosts_applied.append(f"TYPE_CALIBRATION:+{type_adjustment}")
        
        # Log significant calibration changes
        confidence_change = pred.calibrated_confidence - original_confidence
        if abs(confidence_change) > 0.05:
            pred.validation_flags.append("SIGNIFICANT_CALIBRATION")
            
        pred.postprocessing_applied.append("confidence_calibration")
        return pred


class CrossModelEntityConsolidator:
    """
    Implements sentence-based fuzzy matching for single-source-of-truth entity resolution.
    Uses the original TEI document as ground truth for sentence boundaries.
    """
    
    def __init__(self):
        self.similarity_threshold = 0.8
        self.overlap_threshold = 0.5
        logger.info("CrossModelEntityConsolidator initialized", 
                   source="CrossModelEntityConsolidator.__init__")
    
    def consolidate_by_sentences(self, predictions: List[PredictionCandidate], 
                               tei_path: str) -> List[Dict[str, Any]]:
        """
        Consolidate entities using sentence-based fuzzy matching against source TEI.
        
        Process:
        1. Extract sentences from source TEI with character positions
        2. Map each prediction to its source sentence
        3. Group predictions by sentence
        4. Apply fuzzy matching within each sentence group
        5. Select best entities using span coverage and model expertise
        """
        logger.info(f"Starting sentence-based consolidation for {len(predictions)} predictions",
                   source="CrossModelEntityConsolidator.consolidate_by_sentences")
        
        # Extract sentences from source TEI
        sentences = self._extract_sentences_from_tei(tei_path)
        logger.info(f"Extracted {len(sentences)} sentences from source TEI",
                   source="CrossModelEntityConsolidator.consolidate_by_sentences")
        
        # Map predictions to sentences
        sentence_predictions = self._map_predictions_to_sentences(predictions, sentences)
        
        # Consolidate within each sentence
        consolidated_entities = []
        for sentence_id, sentence_preds in sentence_predictions.items():
            if not sentence_preds:
                continue
                
            sentence_info = sentences[sentence_id]
            sentence_entities = self._consolidate_sentence_predictions(
                sentence_preds, sentence_info
            )
            consolidated_entities.extend(sentence_entities)
        
        logger.info(f"Consolidated to {len(consolidated_entities)} entities",
                   source="CrossModelEntityConsolidator.consolidate_by_sentences")
        
        return consolidated_entities
    
    def _extract_sentences_from_tei(self, tei_path: str) -> Dict[int, Dict[str, Any]]:
        """Extract sentences from TEI with character positions, preserving paragraph structure."""
        try:
            tree = etree.parse(tei_path)
            
            # Extract text while preserving paragraph boundaries
            paragraphs = []
            for p_elem in tree.xpath("//ns0:p", namespaces={"ns0": "http://www.tei-c.org/ns/1.0"}):
                p_text = " ".join(p_elem.xpath(".//text()")).strip()
                if p_text and len(p_text) > 10:  # Filter very short paragraphs
                    paragraphs.append(p_text)
            
            # If no paragraphs found, fall back to all text
            if not paragraphs:
                all_text = " ".join(tree.xpath("//text()"))
                all_text = re.sub(r'\s+', ' ', all_text).strip()
                paragraphs = [all_text]
            
            # Join all paragraphs to create full document text with proper spacing
            full_text = " ".join(paragraphs)
            full_text = re.sub(r'\s+', ' ', full_text).strip()
            
            # Split into sentences using enhanced patterns
            sentence_patterns = [
                r'\.(?=\s+[A-Z])',  # Period followed by space and capital
                r'\.(?=\s+\d)',     # Period followed by space and digit (for numbered lists)
                r'\!(?=\s+[A-Z])',  # Exclamation followed by space and capital
                r'\?(?=\s+[A-Z])',  # Question mark followed by space and capital
                r'\.(?=\s+Fig\.)',  # Period before "Fig."
                r'\.(?=\s+Table)', # Period before "Table"
            ]
            
            sentences = {}
            current_pos = 0
            sentence_id = 0
            
            # Enhanced sentence splitting
            for match in re.finditer('|'.join(sentence_patterns), full_text):
                end_pos = match.end()
                sentence_text = full_text[current_pos:end_pos].strip()
                
                if len(sentence_text) > 15:  # Filter very short sentences
                    # Find which paragraph this sentence belongs to
                    paragraph_id = self._find_paragraph_for_position(current_pos, paragraphs, full_text)
                    
                    sentences[sentence_id] = {
                        "text": sentence_text,
                        "char_start": current_pos,
                        "char_end": end_pos,
                        "sentence_id": sentence_id,
                        "paragraph_id": paragraph_id,
                        "full_document_text": full_text  # Store full text for reference
                    }
                    sentence_id += 1
                
                current_pos = end_pos
            
            # Add final sentence if exists
            if current_pos < len(full_text):
                final_text = full_text[current_pos:].strip()
                if len(final_text) > 15:
                    paragraph_id = self._find_paragraph_for_position(current_pos, paragraphs, full_text)
                    sentences[sentence_id] = {
                        "text": final_text,
                        "char_start": current_pos,
                        "char_end": len(full_text),
                        "sentence_id": sentence_id,
                        "paragraph_id": paragraph_id,
                        "full_document_text": full_text
                    }
            
            logger.info(f"Extracted {len(sentences)} sentences from {len(paragraphs)} paragraphs",
                       source="CrossModelEntityConsolidator._extract_sentences_from_tei")
            
            return sentences
            
        except Exception as e:
            logger.error(f"Failed to extract sentences from TEI: {e}",
                        source="CrossModelEntityConsolidator._extract_sentences_from_tei", error=e)
            return {}
    
    def _find_paragraph_for_position(self, position: int, paragraphs: List[str], full_text: str) -> int:
        """Find which paragraph contains the given character position."""
        current_pos = 0
        for i, paragraph in enumerate(paragraphs):
            para_end = current_pos + len(paragraph)
            if current_pos <= position <= para_end:
                return i
            current_pos = para_end + 1  # +1 for space between paragraphs
        return len(paragraphs) - 1  # Default to last paragraph
    
    def _map_predictions_to_sentences(self, predictions: List[PredictionCandidate], 
                                    sentences: Dict[int, Dict[str, Any]]) -> Dict[int, List[PredictionCandidate]]:
        """Map each prediction to its containing sentence with proper character position handling."""
        sentence_predictions = defaultdict(list)
        
        # Get the full document text for reference
        full_doc_text = None
        if sentences:
            first_sentence = next(iter(sentences.values()))
            full_doc_text = first_sentence.get('full_document_text', '')
        
        if not full_doc_text:
            logger.warning("No full document text available for sentence mapping",
                          source="CrossModelEntityConsolidator._map_predictions_to_sentences")
            return {}
        
        for pred in predictions:
            # Try to find the prediction text in the full document
            pred_text = pred.text.strip()
            if not pred_text:
                continue
                
            # Find all occurrences of this text in the document
            doc_positions = []
            start_pos = 0
            while True:
                found_pos = full_doc_text.find(pred_text, start_pos)
                if found_pos == -1:
                    break
                doc_positions.append((found_pos, found_pos + len(pred_text)))
                start_pos = found_pos + 1
            
            if not doc_positions:
                # Try fuzzy matching for partial matches
                logger.debug(f"Could not find exact match for prediction text: '{pred_text}'",
                           source="CrossModelEntityConsolidator._map_predictions_to_sentences")
                continue
            
            # Find the best sentence match for each document position
            best_sentence_id = None
            best_doc_position = None
            best_overlap = 0
            
            for doc_start, doc_end in doc_positions:
                for sentence_id, sentence_info in sentences.items():
                    # Check if this document position overlaps with sentence
                    overlap_start = max(doc_start, sentence_info['char_start'])
                    overlap_end = min(doc_end, sentence_info['char_end'])
                    
                    if overlap_start < overlap_end:
                        overlap_ratio = (overlap_end - overlap_start) / (doc_end - doc_start)
                        if overlap_ratio > best_overlap:
                            best_overlap = overlap_ratio
                            best_sentence_id = sentence_id
                            best_doc_position = (doc_start, doc_end)
            
            if best_sentence_id is not None and best_overlap > self.overlap_threshold:
                # Update prediction with document-based character positions
                pred_copy = pred
                pred_copy.char_start = best_doc_position[0]
                pred_copy.char_end = best_doc_position[1]
                sentence_predictions[best_sentence_id].append(pred_copy)
                
                logger.debug(f"Mapped prediction '{pred_text}' to sentence {best_sentence_id}",
                           source="CrossModelEntityConsolidator._map_predictions_to_sentences")
        
        logger.info(f"Mapped {sum(len(preds) for preds in sentence_predictions.values())} predictions to {len(sentence_predictions)} sentences",
                   source="CrossModelEntityConsolidator._map_predictions_to_sentences")
        
        return dict(sentence_predictions)
    
    def _consolidate_sentence_predictions(self, predictions: List[PredictionCandidate], 
                                        sentence_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Consolidate predictions within a single sentence using fuzzy matching."""
        if len(predictions) <= 1:
            return [self._convert_prediction_to_entity(pred, sentence_info) for pred in predictions]
        
        # Group by entity type first
        by_type = defaultdict(list)
        for pred in predictions:
            by_type[pred.entity_type].append(pred)
        
        consolidated = []
        for entity_type, type_preds in by_type.items():
            # Apply fuzzy matching within entity type
            clusters = self._create_fuzzy_clusters(type_preds)
            
            for cluster in clusters:
                best_entity = self._select_best_from_cluster(cluster, sentence_info)
                consolidated.append(best_entity)
        
        return consolidated
    
    def _create_fuzzy_clusters(self, predictions: List[PredictionCandidate]) -> List[List[PredictionCandidate]]:
        """Create clusters of similar predictions using fuzzy text matching."""
        if len(predictions) <= 1:
            return [predictions]
        
        clusters = []
        used_indices = set()
        
        for i, pred1 in enumerate(predictions):
            if i in used_indices:
                continue
            
            cluster = [pred1]
            used_indices.add(i)
            
            for j, pred2 in enumerate(predictions[i+1:], i+1):
                if j in used_indices:
                    continue
                
                # Check for fuzzy text similarity
                similarity = SequenceMatcher(None, pred1.text.lower(), pred2.text.lower()).ratio()
                
                # Check for span overlap
                overlap_start = max(pred1.char_start, pred2.char_start)
                overlap_end = min(pred1.char_end, pred2.char_end)
                span_overlap = max(0, overlap_end - overlap_start)
                span_union = max(pred1.char_end, pred2.char_end) - min(pred1.char_start, pred2.char_start)
                overlap_ratio = span_overlap / span_union if span_union > 0 else 0
                
                # Cluster if similar text OR overlapping spans
                if similarity > self.similarity_threshold or overlap_ratio > self.overlap_threshold:
                    cluster.append(pred2)
                    used_indices.add(j)
            
            clusters.append(cluster)
        
        return clusters
    
    def _select_best_from_cluster(self, cluster: List[PredictionCandidate], 
                                sentence_info: Dict[str, Any]) -> Dict[str, Any]:
        """Select the best entity from a cluster based on span coverage and model expertise."""
        if len(cluster) == 1:
            return self._convert_prediction_to_entity(cluster[0], sentence_info)
        
        # Score each prediction
        scored_predictions = []
        for pred in cluster:
            score = self._calculate_entity_score(pred)
            scored_predictions.append((score, pred))
        
        # Sort by score (highest first)
        scored_predictions.sort(key=lambda x: x[0], reverse=True)
        best_pred = scored_predictions[0][1]
        
        # Create entity with voting information
        entity = self._convert_prediction_to_entity(best_pred, sentence_info)
        entity['cluster_size'] = len(cluster)
        entity['models_voted'] = [pred.model for pred in cluster]
        entity['consolidation_reason'] = f"Best of {len(cluster)} predictions (score: {scored_predictions[0][0]:.3f})"
        
        return entity
    
    def _calculate_entity_score(self, pred: PredictionCandidate) -> float:
        """
        Calculate a score for entity selection with emphasis on span length.
        
        Prioritization criteria (as requested):
        1. Entity with most span (e.g., "glass transition temperature" vs "glass transition")
        2. Model expertise and configuration requirements
        3. Confidence levels
        """
        score = 0.0
        
        # PRIORITY 1: Span length (increased weight for longer spans)
        span_length = pred.char_end - pred.char_start
        normalized_length = min(span_length / 100.0, 1.0)  # Normalize to [0,1] with higher max
        score += normalized_length * 0.5  # Increased weight from 0.2 to 0.5
        
        # Additional boost for significantly longer spans
        if span_length > 20:  # Longer technical terms get extra boost
            score += 0.15
        
        # PRIORITY 2: Base confidence
        score += pred.confidence * 0.25  # Reduced from 0.4 to make room for span priority
        
        # PRIORITY 3: Model expertise (config requirements)
        model_expertise = self._get_model_expertise(pred.model, pred.entity_type)
        score += model_expertise * 0.2  # Reduced from 0.3
        
        # Quality checks
        # Penalize very short entities (likely incomplete)
        if span_length < 3:
            score -= 0.3  # Increased penalty
        
        # Boost for complete words (no partial words)
        if pred.text.isalpha() or ' ' in pred.text:
            score += 0.1
        
        # Boost for validation flags (config requirements met)
        if pred.validation_flags:
            score += len(pred.validation_flags) * 0.05
            
        # Boost for validation boosts applied (expert selection)
        if pred.validation_boosts_applied:
            score += len(pred.validation_boosts_applied) * 0.05
        
        return score
    
    def _get_model_expertise(self, model_name: str, entity_type: str) -> float:
        """Get model expertise weight for entity type."""
        try:
            model_cfg = next((m for m in ENSEMBLE_MODELS if m.name == model_name), None)
            if model_cfg and hasattr(model_cfg, 'expertise'):
                return model_cfg.expertise.entity_weights.get(entity_type, 1.0)
        except:
            pass
        return 1.0
    
    def _convert_prediction_to_entity(self, pred: PredictionCandidate, 
                                    sentence_info: Dict[str, Any]) -> Dict[str, Any]:
        """Convert prediction to final entity format with full paragraph context."""
        entity = {
            "text": pred.text,
            "char_start": pred.char_start,
            "char_end": pred.char_end,
            "confidence": pred.confidence,
            "entity_type": pred.entity_type,
            "model": pred.model,
            "window_id": pred.window_id,
            "sentence_id": sentence_info['sentence_id'],
            "sentence_text": sentence_info['text'],  # Full sentence from source TEI
            "paragraph_id": sentence_info.get('paragraph_id', -1),
            "context_snippet": pred.context_snippet,
            "validation_flags": pred.validation_flags or [],
            "postprocessing_applied": pred.postprocessing_applied or [],
            "validation_boosts_applied": pred.validation_boosts_applied or [],
            "strategies_attempted": pred.strategies_attempted or [],
            "cluster_size": 1,
            "models_voted": [pred.model],
            "consolidation_reason": "single_prediction"
        }
        
        # Add full document reference for char position validation
        if 'full_document_text' in sentence_info:
            entity["source_document_length"] = len(sentence_info['full_document_text'])
            
        return entity


class EnsembleInferenceService:
    """
    Complete rewrite of ensemble inference service with all improvements:
    - No serialized token usage
    - Full offset mapping recomputation  
    - Complete span retention
    - Semantic relationship boosting
    - Dynamic postprocessing
    - Adaptive ensemble strategies
    """
    
    def __init__(self):
        self.models_cfg = ENSEMBLE_MODELS
        self.models_dir = Path(WORKSPACE_DIR) / "models" / "finetuned"
        self.results_dir = Path(WORKSPACE_DIR) / "exports"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.semantic_analyzer = SemanticAnalyzer()
        self.postprocessor = PostProcessor()
        
        # Strategy tracking - Initialize missing tracking features
        self.strategy_performance = defaultdict(list)
        self.current_strategy = EnsembleStrategy.ADAPTIVE_VOTING
        self.strategies_attempted = []
        self.strategy_switches = []
        self.postprocessing_applied = defaultdict(list)
        self.validation_boosts_applied = defaultdict(float)
        
        # Store document text for window context extraction
        self.document_windows = {}  # Store window texts by window_id
        
        # Initialize sentence-based consolidator
        self.entity_consolidator = None  # Will be initialized when needed

    def _find_window_files(self, base_name: str, model_name: str) -> str:
        """
        Robust file discovery with multiple fallback patterns.
        Addresses the critical file path mismatch issue.
        """
        from polymer_extractor.utils.paths import SAMPLES_DIR
        
        model_dir = Path(SAMPLES_DIR) / f"{model_name}_outputs"
        
        # Multiple patterns to try in priority order
        patterns = [
            f"{base_name}_token_windows.json",           # Original expected pattern
            f"{base_name}.tei_token_windows.json",       # Actual TokenPacking output pattern  
            f"{base_name}_windows.json",                 # Fallback pattern
            f"{base_name}.xml_token_windows.json",       # Alternative pattern
        ]
        
        for pattern in patterns:
            file_path = model_dir / pattern
            if file_path.exists():
                logger.info(f"Found window file using pattern: {pattern}",
                           source="EnsembleInferenceService._find_window_files",
                           context={"model": model_name, "pattern": pattern})
                return str(file_path)
        
        # If no file found, log the issue and raise descriptive error
        logger.error(f"No window file found for model {model_name}",
                    source="EnsembleInferenceService._find_window_files",
                    context={
                        "base_name": base_name,
                        "model_name": model_name,
                        "searched_patterns": patterns,
                        "model_dir": str(model_dir),
                        "dir_exists": model_dir.exists(),
                        "dir_contents": list(model_dir.iterdir()) if model_dir.exists() else []
                    })
        
        raise FileNotFoundError(
            f"Window file not found for {model_name}. "
            f"Searched patterns: {patterns} in {model_dir}"
        )

    def run_inference(self, tei_path: str, use_sentence_consolidation: bool = True) -> Dict[str, Any]:
        """
        Complete inference pipeline with all improvements implemented.
        
        Key changes:
        1. No reliance on serialized token IDs
        2. Full re-tokenization during inference
        3. Complete offset mapping recomputation
        4. Semantic relationship detection and boosting
        5. Dynamic postprocessing activation
        6. Adaptive ensemble strategies
        """
        logger.info(f"[EnsembleInference] Starting enhanced pipeline for {tei_path}",
                    source="EnsembleInferenceService.run_inference")

        base_name = Path(tei_path).stem
        all_predictions = []
        inference_metadata = {
            "models_processed": 0,
            "models_failed": 0,
            "total_windows": 0,
            "total_predictions": 0,
            "strategy_switches": [],
            "postprocessing_stats": defaultdict(int),
            "semantic_relationships": defaultdict(int),
            "validation_boosts_applied": defaultdict(int)
        }

        # Initialize token packing with enhanced configuration
        packing_service = TokenPackingService()
        try:
            packing_result = packing_service.process(tei_path)
            if not packing_result.get("success", False):
                raise ValueError(f"Token packing failed: {packing_result}")
        except Exception as e:
            logger.error(f"Token packing failed for {tei_path}: {e}",
                        source="EnsembleInferenceService.run_inference", error=e)
            raise

        # Process each model
        model_windows = {}  # Store windows per model to avoid reloading
        
        for model_cfg in self.models_cfg:
            model_name = model_cfg.name
            model_path = self.models_dir / model_name

            try:
                logger.info(f"Processing model {model_name}",
                           source="EnsembleInferenceService.run_inference")

                # Load model first to get vocabulary size
                model = AutoModelForTokenClassification.from_pretrained(
                    model_path,
                    num_labels=len(LABELS),
                    id2label=ID2LABEL,
                    label2id=LABEL2ID,
                    torch_dtype=torch.float32
                ).eval()

                # Move model to appropriate device
                if torch.cuda.is_available():
                    model.cuda()
                else:
                    model.cpu()  # Ensure model is on CPU

                # Load model-specific tokenizer to avoid vocabulary mismatches
                tokenizer = self._get_model_specific_tokenizer(model_name, model_cfg.model_id, model.config.vocab_size)

                # Ensure tokenizer has pad token
                if tokenizer.pad_token is None:
                    tokenizer.pad_token = tokenizer.eos_token

                # Load windows for this model using robust file discovery
                try:
                    windows_path = self._find_window_files(base_name, model_name)
                    with open(windows_path, "r", encoding="utf-8") as f:
                        windows = json.load(f)
                    
                    logger.info(f"Loaded {len(windows)} windows for {model_name}",
                               source="EnsembleInferenceService.run_inference",
                               context={"windows_path": windows_path, "window_count": len(windows)})
                        
                except FileNotFoundError as e:
                    logger.error(f"Window file not found for {model_name}: {e}",
                               source="EnsembleInferenceService.run_inference", error=e)
                    inference_metadata["models_failed"] += 1
                    continue
                
                model_windows[model_name] = windows
                inference_metadata["total_windows"] = max(inference_metadata["total_windows"], len(windows))
                
                # Run enhanced inference - NO USE OF SERIALIZED TOKENS
                predictions = self._infer_model_complete_retokenization(
                    model, tokenizer, windows, model_name, model_cfg
                )
                all_predictions.extend(predictions)
                
                inference_metadata["models_processed"] += 1
                inference_metadata["total_predictions"] += len(predictions)
                
                logger.info(f"Model {model_name} completed: {len(predictions)} predictions",
                           source="EnsembleInferenceService.run_inference")

            except Exception as e:
                inference_metadata["models_failed"] += 1
                logger.error(f"Model {model_name} failed: {e}",
                           source="EnsembleInferenceService.run_inference",
                           context={
                               "model_name": model_name,
                               "model_path": str(model_path),
                               "error_type": type(e).__name__
                           },
                           error=e)
                continue
            finally:
                # Clean up model resources
                if 'model' in locals():
                    del model
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

        # Validate we have predictions
        if not all_predictions:
            raise ValueError("No models produced valid predictions")

        # Enhanced semantic analysis across all predictions
        logger.info("Performing semantic relationship analysis",
                   source="EnsembleInferenceService.run_inference")
        
        all_relationships = self._detect_global_relationships(all_predictions, model_windows)
        inference_metadata["semantic_relationships"] = {
            k: len(v) for k, v in all_relationships.items()
        }

        # Apply semantic boosting
        boosted_predictions = self._apply_semantic_boosting(all_predictions, all_relationships)
        
        # Choose consolidation method based on user preference and TEI availability
        if use_sentence_consolidation:
            logger.info("Attempting sentence-based consolidation using TEI source",
                       source="EnsembleInferenceService.run_inference")
            
            try:
                # Initialize sentence-based consolidator
                consolidator = CrossModelEntityConsolidator()
                sentence_entities = consolidator.consolidate_by_sentences(boosted_predictions, tei_path)
                
                if sentence_entities:
                    # Convert to the expected format for compatibility
                    final_results = defaultdict(list)
                    for entity in sentence_entities:
                        entity_type = entity.get('entity_type', 'UNKNOWN')
                        final_results[entity_type].append(entity)
                    
                    # Create minimal processing metadata for sentence-based approach
                    processing_metadata = {
                        "consolidation_method": "sentence_based",
                        "sentences_processed": len(set(e.get('sentence_id', -1) for e in sentence_entities)),
                        "tei_source": tei_path,
                        "total_entities_consolidated": len(sentence_entities)
                    }
                    
                    logger.info(f"Sentence-based consolidation successful: {len(sentence_entities)} entities",
                               source="EnsembleInferenceService.run_inference")
                else:
                    # Fall back to traditional processing
                    logger.warning("Sentence-based consolidation returned no entities, falling back to traditional",
                                 source="EnsembleInferenceService.run_inference")
                    raise ValueError("No entities from sentence consolidation")
                    
            except Exception as e:
                logger.error(f"Sentence-based consolidation failed: {e}, falling back to traditional",
                           source="EnsembleInferenceService.run_inference", error=e)
                use_sentence_consolidation = False
        
        if not use_sentence_consolidation:
            # Enhanced ensemble processing with adaptive strategies (traditional approach)
            logger.info("Starting adaptive ensemble voting and postprocessing",
                       source="EnsembleInferenceService.run_inference")
            
            final_results, processing_metadata = self._adaptive_ensemble_processing(boosted_predictions)
            processing_metadata["consolidation_method"] = "traditional"
        inference_metadata.update(processing_metadata)

        # Apply Strict Sentence Processing Pipeline for clean, accurate results
        logger.info("Applying strict sentence processing pipeline",
                   source="EnsembleInferenceService.run_inference")
        
        try:
            strict_processor = StrictSentenceProcessor()
            processed_result = strict_processor.process_ensemble_results(
                dict(final_results), tei_path, base_name
            )
            
            # Extract entities from processed result
            processed_entities = processed_result.get("entities", [])
            
            # Reorganize by entity type for consistency
            final_results = defaultdict(list)
            for entity in processed_entities:
                entity_type = entity.get('entity_type', 'UNKNOWN')
                final_results[entity_type].append(entity)
            
            # Update inference metadata with processing stats
            inference_metadata.update({
                "consolidation_method": "strict_sentence_processing",
                "sentences_processed": processed_result.get("sentence_count", 0),
                "tei_source": tei_path,
                "total_entities_consolidated": processed_result.get("entity_count", 0)
            })
            
            logger.info(f"Strict sentence processing completed successfully",
                       source="EnsembleInferenceService.run_inference",
                       context={
                           "final_entity_count": sum(len(entities) for entities in final_results.values()),
                           "entity_breakdown": {k: len(v) for k, v in final_results.items()},
                           "processing_stats": processed_result.get("processing_stats", {})
                       })
            
        except Exception as e:
            logger.error(f"Strict sentence processing failed, using original results: {e}",
                        source="EnsembleInferenceService.run_inference", error=e)
            # Continue with original results if processing fails
            inference_metadata["consolidation_method"] = "traditional"

        # Create comprehensive results with metadata separation
        extraction_results = {entity_type: entities for entity_type, entities in final_results.items()}
        
        detailed_metadata = {
            "source_file": tei_path,
            "processing_timestamp": logger.log.__dict__.get('timestamp', ''),
            "models_configuration": {
                model.name: {
                    "model_id": model.model_id,
                    "base_weight": model.base_weight,
                    "expertise": asdict(model.expertise),
                    "postprocessing_steps": model.postprocessing_steps
                } for model in self.models_cfg
            },
            "inference_statistics": inference_metadata,
            "ensemble_strategy_performance": dict(self.strategy_performance),
            "entity_relationship_analysis": all_relationships,
            "processing_configuration": {
                "max_tokens": packing_service.max_tokens,
                "buffer_limit": packing_service.buffer_limit,
                "overlap_sentences": packing_service.overlap_sentences,
                "confidence_thresholds": DynamicThresholds.BASE_THRESHOLDS,
                "semantic_patterns": ENTITY_RELATIONSHIP_PATTERNS,
                "validation_confidence_adjustments": VALIDATION_CONFIDENCE_ADJUSTMENTS,
                "entity_semantic_groups": ENTITY_SEMANTIC_GROUPS,
                "processing_config": PROCESSING_CONFIG,
                "postprocessing_config": POST_PROCESSING_CONFIG
            },
            "quality_metrics": {
                "total_entities_extracted": sum(len(v) for v in final_results.values()),
                "entity_distribution": {k: len(v) for k, v in final_results.items()},
                "average_confidence_by_type": self._calculate_confidence_stats(final_results),
                "semantic_coherence_score": self._calculate_coherence_score(all_relationships),
                "strategy_effectiveness": self._calculate_strategy_effectiveness()
            }
        }
        
        # Save results with separated metadata
        self._save_enhanced_results(extraction_results, detailed_metadata, base_name)

        return {
            "success": True,
            "tei_file": tei_path,
            "models_used": [m.name for m in self.models_cfg if inference_metadata["models_processed"] > 0],
            "processing_stats": inference_metadata,
            "num_entities": sum(len(v) for v in final_results.values()),
            "entity_breakdown": {k: len(v) for k, v in final_results.items()},
            "output_files": {
                "results": str(self.results_dir / f"{base_name}_ensemble_results.json")
            },
            "semantic_relationships": len(all_relationships),
            "strategy_used": self.current_strategy.value
        }

    def _infer_model_complete_retokenization(self, model, tokenizer, windows: List[Dict], 
                                           model_name: str, model_cfg) -> List[PredictionCandidate]:
        """
        Complete inference with full re-tokenization - NO USE OF SERIALIZED TOKENS.
        
        This method completely avoids any serialized input_ids, attention_mask, or offset_mapping.
        Everything is recomputed using the inference tokenizer to ensure perfect alignment.
        """
        predictions = []
        
        for win_idx, window in enumerate(windows):
            try:
                # Extract just the text - ignore any serialized token data
                window_text = window["text"]
                window_id = window.get("window_id", f"win_{win_idx}")
                
                # Store window text for later context extraction
                self.document_windows[window_id] = window_text
                
                # COMPLETE RE-TOKENIZATION - this is the key fix
                try:
                    encoding = tokenizer(
                        window_text,
                        return_offsets_mapping=True,
                        return_attention_mask=True,
                        truncation=True,
                        max_length=512,
                        padding="max_length",
                        return_tensors="pt"
                    )
                except Exception as e:
                    logger.error(
                        f"Tokenization failed for {model_name} window {win_idx}: {e}",
                        source="EnsembleInferenceService._infer_model_complete_retokenization",
                        context={
                            "window_id": window_id,
                            "model": model_name,
                            "text_length": len(window_text),
                            "text_preview": window_text[:200]
                        },
                        error=e
                    )
                    continue
                
                # Extract freshly computed values
                input_ids = encoding["input_ids"].squeeze(0)
                attention_mask = encoding["attention_mask"].squeeze(0)
                offset_mapping = encoding["offset_mapping"].squeeze(0)
                
                # Enhanced validation with fallback
                max_token_id = input_ids.max().item()
                if max_token_id >= tokenizer.vocab_size:
                    logger.warning(
                        f"Invalid token ID in {model_name} window {win_idx}, attempting fallback",
                        source="EnsembleInferenceService._infer_model_complete_retokenization",
                        context={
                            "window_id": window_id,
                            "model": model_name,
                            "max_token_id": max_token_id,
                            "vocab_size": tokenizer.vocab_size,
                            "text_preview": window_text[:200]
                        }
                    )
                    
                    # Try fallback with base tokenizer if this was extended
                    if hasattr(tokenizer, 'name_or_path') and 'extended' in str(tokenizer.name_or_path):
                        try:
                            base_tokenizer = AutoTokenizer.from_pretrained(model_cfg.model_id, use_fast=True)
                            if base_tokenizer.pad_token is None:
                                base_tokenizer.pad_token = base_tokenizer.eos_token
                                
                            fallback_encoding = base_tokenizer(
                                window_text,
                                return_offsets_mapping=True,
                                return_attention_mask=True,
                                truncation=True,
                                max_length=512,
                                padding="max_length",
                                return_tensors="pt"
                            )
                            
                            input_ids = fallback_encoding["input_ids"].squeeze(0)
                            attention_mask = fallback_encoding["attention_mask"].squeeze(0)
                            offset_mapping = fallback_encoding["offset_mapping"].squeeze(0)
                            
                            # Validate fallback
                            if input_ids.max().item() >= base_tokenizer.vocab_size:
                                logger.error(f"Fallback tokenizer also failed for {model_name} window {win_idx}",
                                           source="EnsembleInferenceService._infer_model_complete_retokenization")
                                continue
                            else:
                                logger.info(f"Fallback tokenizer succeeded for {model_name} window {win_idx}",
                                          source="EnsembleInferenceService._infer_model_complete_retokenization")
                                tokenizer = base_tokenizer  # Use base tokenizer for remaining windows
                        except Exception as e:
                            logger.error(f"Fallback tokenizer failed for {model_name} window {win_idx}: {e}",
                                       source="EnsembleInferenceService._infer_model_complete_retokenization")
                            continue
                    else:
                        continue

                # Move to appropriate device based on model's device
                device = next(model.parameters()).device
                device_inputs = {
                    "input_ids": input_ids.unsqueeze(0).to(device),
                    "attention_mask": attention_mask.unsqueeze(0).to(device)
                }

                # Model inference
                with torch.no_grad():
                    outputs = model(**device_inputs)
                    logits = outputs.logits.squeeze(0)  # Remove batch dimension
                    probs = softmax(logits, dim=-1).cpu().numpy()
                    pred_ids = np.argmax(probs, axis=-1)

                # Convert back to CPU for offset processing
                offset_mapping = offset_mapping.cpu().numpy()

                # Process predictions with enhanced confidence calculation
                current_entity = None
                entity_start_idx = None
                entity_tokens = []
                
                for token_idx, (label_id, token_probs, offset) in enumerate(zip(pred_ids, probs, offset_mapping)):
                    label = ID2LABEL[label_id]
                    
                    # Skip special tokens and O labels
                    if label == "O" or offset[0] == offset[1]:
                        # End current entity if exists
                        if current_entity is not None:
                            self._finalize_entity(
                                predictions, current_entity, entity_tokens, entity_start_idx,
                                window_text, model_name, model_cfg, window_id, probs
                            )
                            current_entity = None
                            entity_tokens = []
                            entity_start_idx = None
                        continue
                    
                    entity_type = label.split("-")[-1]
                    label_prefix = label.split("-")[0]
                    
                    # Handle B- tags (beginning of entity)
                    if label_prefix == "B":
                        # Finalize previous entity if exists
                        if current_entity is not None:
                            self._finalize_entity(
                                predictions, current_entity, entity_tokens, entity_start_idx,
                                window_text, model_name, model_cfg, window_id, probs
                            )
                        
                        # Start new entity
                        current_entity = entity_type
                        entity_start_idx = token_idx
                        entity_tokens = [(token_idx, label_id, token_probs, offset)]
                    
                    # Handle I- tags (inside entity)
                    elif label_prefix == "I" and current_entity == entity_type:
                        entity_tokens.append((token_idx, label_id, token_probs, offset))
                    
                    # Handle I- tag without corresponding B- tag
                    elif label_prefix == "I":
                        # Start new entity (treat as B-)
                        current_entity = entity_type
                        entity_start_idx = token_idx
                        entity_tokens = [(token_idx, label_id, token_probs, offset)]

                # Finalize any remaining entity
                if current_entity is not None:
                    self._finalize_entity(
                        predictions, current_entity, entity_tokens, entity_start_idx,
                        window_text, model_name, model_cfg, window_id, probs
                    )
                    
            except Exception as e:
                logger.error(
                    f"Inference failed for {model_name} window {win_idx}: {e}",
                    source="EnsembleInferenceService._infer_model_complete_retokenization",
                    context={
                        "window_id": window.get("window_id", f"win_{win_idx}"),
                        "model": model_name,
                        "error_type": type(e).__name__,
                        "text_preview": window.get("text", "")[:200]
                    },
                    error=e
                )
                continue
                
        logger.info(
            f"Model {model_name}: {len(windows)} windows → {len(predictions)} predictions",
            source="EnsembleInferenceService._infer_model_complete_retokenization",
            context={
                "model": model_name,
                "windows_processed": len(windows),
                "predictions_generated": len(predictions)
            }
        )
        
        return predictions

    def _finalize_entity(self, predictions: List[PredictionCandidate], entity_type: str,
                        entity_tokens, start_idx: int, window_text: str, model_name: str,
                        model_cfg, window_id: str, all_probs):
        """Finalize and validate an entity prediction."""
        if not entity_tokens:
            return
            
        # Calculate span boundaries - ensure Python int types
        first_offset = entity_tokens[0][3]
        last_offset = entity_tokens[-1][3]
        char_start = int(first_offset[0])  # Convert numpy types to Python int
        char_end = int(last_offset[1])     # Convert numpy types to Python int
        
        # Extract entity text
        entity_text = window_text[char_start:char_end].strip()
        
        # Skip if entity text is too short or meaningless
        if len(entity_text) < 2 or not any(c.isalnum() for c in entity_text):
            return
        
        # Calculate confidence scores
        token_confidences = [probs[label_id] for _, label_id, probs, _ in entity_tokens]
        raw_confidence = float(np.mean(token_confidences))
        
        # Apply model-specific calibration
        calibrated_confidence = raw_confidence
        if model_cfg and hasattr(model_cfg, 'expertise'):
            entity_weight = model_cfg.expertise.entity_weights.get(entity_type, 1.0)
            calibrated_confidence = min(raw_confidence * entity_weight, 1.0)

        # Create prediction candidate - ensure all numeric types are JSON-serializable
        prediction = PredictionCandidate(
            text=entity_text,
            char_start=char_start,  # Already converted to int above
            char_end=char_end,      # Already converted to int above
            entity_type=entity_type,
            label=f"B-{entity_type}",  # Simplified label representation
            confidence=raw_confidence,
            calibrated_confidence=calibrated_confidence,
            model=model_name,
            window_id=window_id,
            token_position=int(start_idx),  # Ensure Python int type
            context_snippet=self._extract_context_snippet(window_text, char_start, char_end)
        )
        
        # Add token count information for structured output
        prediction.merged_from_tokens = len(entity_tokens)
        prediction.token_count = len(entity_tokens)
        
        # Apply postprocessing steps if defined for this model
        if model_cfg.postprocessing_steps:
            prediction = self.postprocessor.apply_postprocessing_steps(
                prediction, model_cfg.postprocessing_steps
            )
        
        predictions.append(prediction)

    def _extract_context_snippet(self, text: str, char_start: int, char_end: int, 
                                context_size: int = 50) -> str:
        """Extract context snippet around entity."""
        snippet_start = max(0, char_start - context_size)
        snippet_end = min(len(text), char_end + context_size)
        
        snippet = text[snippet_start:snippet_end]
        entity_in_snippet = text[char_start:char_end]
        
        # Mark the entity in the snippet
        relative_start = char_start - snippet_start
        relative_end = char_end - snippet_start
        
        return (snippet[:relative_start] + 
                f"[{entity_in_snippet}]" + 
                snippet[relative_end:])

    def _detect_global_relationships(self, predictions: List[PredictionCandidate],
                                   model_windows: Dict[str, List[Dict]]) -> Dict[str, List[Dict[str, Any]]]:
        """Detect semantic relationships across all predictions."""
        all_relationships = defaultdict(list)
        
        # Group predictions by window for relationship detection
        window_predictions = defaultdict(list)
        for pred in predictions:
            window_predictions[pred.window_id].append(pred)
        
        # Analyze relationships within each window
        for window_id, window_preds in window_predictions.items():
            if len(window_preds) < 2:
                continue
                
            # Get window text (from any model's windows - they should be the same)
            window_text = ""
            for model_name, windows in model_windows.items():
                for window in windows:
                    if window.get("window_id", "") == window_id:
                        window_text = window["text"]
                        break
                if window_text:
                    break
            
            if not window_text:
                continue
            
            # Detect relationships in this window
            window_relationships = self.semantic_analyzer.detect_relationships(window_preds, window_text)
            
            # Merge into global relationships
            for rel_type, relationships in window_relationships.items():
                all_relationships[rel_type].extend(relationships)
        
        return dict(all_relationships)

    def _apply_semantic_boosting(self, predictions: List[PredictionCandidate],
                               relationships: Dict[str, List[Dict[str, Any]]]) -> List[PredictionCandidate]:
        """Apply confidence boosting based on semantic relationships."""
        # Create a lookup for entities in relationships
        relationship_entities = set()
        entity_boosts = defaultdict(float)
        
        for rel_type, rel_list in relationships.items():
            for relationship in rel_list:
                entities = relationship.get('entities', [])
                boost = relationship.get('confidence_boost', 0.0) * relationship.get('strength', 1.0)
                
                for entity_text in entities:
                    relationship_entities.add(entity_text)
                    entity_boosts[entity_text] += boost
        
        # Apply boosts to matching predictions
        boosted_predictions = []
        for pred in predictions:
            if pred.text in relationship_entities:
                boost = min(entity_boosts[pred.text], 0.2)  # Cap boost at 0.2
                pred.calibrated_confidence = min(pred.calibrated_confidence + boost, 1.0)
                pred.semantic_relationships.append({
                    'boost_applied': boost,
                    'total_relationships': len([r for r in relationships.values() for rel in r if pred.text in rel.get('entities', [])])
                })
                
                logger.debug(
                    f"Applied semantic boost to {pred.entity_type}: {pred.text} (+{boost:.3f})",
                    source="EnsembleInferenceService._apply_semantic_boosting",
                    context={
                        "entity_type": pred.entity_type,
                        "entity_text": pred.text,
                        "boost_applied": boost,
                        "new_confidence": pred.calibrated_confidence
                    }
                )
            
            boosted_predictions.append(pred)
        
        return boosted_predictions

    def _adaptive_ensemble_processing(self, predictions: List[PredictionCandidate]) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
        """
        Adaptive ensemble processing with strategy switching and comprehensive metadata.
        
        Implements multiple ensemble strategies with dynamic switching based on performance.
        """
        processing_metadata = {
            "strategies_attempted": [],
            "strategy_performance": {},
            "clusters_processed": 0,
            "clusters_accepted": 0,
            "clusters_rejected": 0,
            "postprocessing_applied": defaultdict(int),
            "validation_boosts": defaultdict(int)
        }
        
        # Group predictions by entity type
        entity_groups = defaultdict(list)
        for pred in predictions:
            entity_groups[pred.entity_type].append(pred)
        
        final_results = defaultdict(list)
        
        for entity_type, entity_predictions in entity_groups.items():
            logger.info(f"Processing {len(entity_predictions)} {entity_type} predictions",
                       source="EnsembleInferenceService._adaptive_ensemble_processing")
            
            # Create clusters of overlapping predictions
            clusters = self._create_enhanced_clusters(entity_predictions)
            processing_metadata["clusters_processed"] += len(clusters)
            
            # Process each cluster with adaptive strategy
            for cluster in clusters:
                result = self._process_cluster_with_strategy(cluster, entity_type)
                
                if result["accepted"]:
                    final_results[entity_type].append(result["entity"])
                    processing_metadata["clusters_accepted"] += 1
                    
                    # Track strategy performance
                    strategy = result["strategy_used"]
                    if strategy not in processing_metadata["strategy_performance"]:
                        processing_metadata["strategy_performance"][strategy] = {"successes": 0, "attempts": 0}
                    processing_metadata["strategy_performance"][strategy]["successes"] += 1
                else:
                    processing_metadata["clusters_rejected"] += 1
                
                # Update strategy attempt count
                strategy = result["strategy_used"]
                if strategy not in processing_metadata["strategy_performance"]:
                    processing_metadata["strategy_performance"][strategy] = {"successes": 0, "attempts": 0}
                processing_metadata["strategy_performance"][strategy]["attempts"] += 1
                
                # Track postprocessing and validation
                if "postprocessing_applied" in result:
                    for step in result["postprocessing_applied"]:
                        processing_metadata["postprocessing_applied"][step] += 1
                
                if "validation_boosts" in result:
                    for boost_type in result["validation_boosts"]:
                        processing_metadata["validation_boosts"][boost_type] += 1
        
        return dict(final_results), processing_metadata

    def _create_enhanced_clusters(self, predictions: List[PredictionCandidate]) -> List[List[PredictionCandidate]]:
        """Create clusters of overlapping predictions with enhanced proximity detection."""
        if not predictions:
            return []
        
        # Sort predictions by position
        sorted_preds = sorted(predictions, key=lambda p: (p.char_start, -p.char_end))
        clusters = []
        
        while sorted_preds:
            current_cluster = [sorted_preds.pop(0)]
            cluster_start = current_cluster[0].char_start
            cluster_end = current_cluster[0].char_end
            
            # Find all overlapping or adjacent predictions
            i = 0
            while i < len(sorted_preds):
                pred = sorted_preds[i]
                
                # Check for overlap or close proximity (within 5 characters)
                if (pred.char_start <= cluster_end + 5 and pred.char_end >= cluster_start - 5):
                    current_cluster.append(sorted_preds.pop(i))
                    # Update cluster boundaries
                    cluster_start = min(cluster_start, pred.char_start)
                    cluster_end = max(cluster_end, pred.char_end)
                else:
                    i += 1
            
            clusters.append(current_cluster)
        
        return clusters

    def _process_cluster_with_strategy(self, cluster: List[PredictionCandidate], 
                                     entity_type: str) -> Dict[str, Any]:
        """Process a cluster using adaptive ensemble strategies."""
        
        # Determine best strategy for this cluster
        strategy = self._select_optimal_strategy(cluster, entity_type)
        
        # Apply the selected strategy
        if strategy == EnsembleStrategy.WEIGHTED_CONFIDENCE:
            result = self._apply_weighted_confidence_strategy(cluster, entity_type)
        elif strategy == EnsembleStrategy.EXPERT_CONSENSUS:
            result = self._apply_expert_consensus_strategy(cluster, entity_type)
        elif strategy == EnsembleStrategy.SEMANTIC_AWARE:
            result = self._apply_semantic_aware_strategy(cluster, entity_type)
        elif strategy == EnsembleStrategy.DYNAMIC_THRESHOLD:
            result = self._apply_dynamic_threshold_strategy(cluster, entity_type)
        else:  # ADAPTIVE_VOTING (default)
            result = self._apply_adaptive_voting_strategy(cluster, entity_type)
        
        result["strategy_used"] = strategy.value
        return result

    def _select_optimal_strategy(self, cluster: List[PredictionCandidate], 
                               entity_type: str) -> EnsembleStrategy:
        """Select the optimal ensemble strategy for this cluster."""
        
        # Get cluster characteristics
        model_diversity = len(set(pred.model for pred in cluster))
        confidence_spread = max(pred.calibrated_confidence for pred in cluster) - min(pred.calibrated_confidence for pred in cluster)
        has_semantic_relationships = any(pred.semantic_relationships for pred in cluster)
        
        # Strategy selection logic
        if model_diversity >= 4 and confidence_spread > 0.3:
            # High model diversity with disagreement -> use expert consensus
            return EnsembleStrategy.EXPERT_CONSENSUS
        elif has_semantic_relationships:
            # Semantic relationships detected -> use semantic aware
            return EnsembleStrategy.SEMANTIC_AWARE
        elif confidence_spread < 0.1:
            # High agreement -> use weighted confidence
            return EnsembleStrategy.WEIGHTED_CONFIDENCE
        elif entity_type in ["VALUE", "UNIT"]:  # These benefit from dynamic thresholds
            return EnsembleStrategy.DYNAMIC_THRESHOLD
        else:
            # Default to adaptive voting
            return EnsembleStrategy.ADAPTIVE_VOTING

    def _apply_weighted_confidence_strategy(self, cluster: List[PredictionCandidate], 
                                          entity_type: str) -> Dict[str, Any]:
        """Apply weighted confidence ensemble strategy."""
        if not cluster:
            return {"accepted": False, "reason": "empty_cluster"}
        
        # Get strategy configuration
        strategy_config = get_ensemble_strategy_config(EnsembleStrategy.WEIGHTED_CONFIDENCE)
        params = strategy_config.get("parameters", {})
        
        confidence_power = params.get("confidence_power", 1.5)
        expertise_weight = params.get("expertise_weight", 1.2)
        min_models_required = params.get("min_models_required", 2)
        
        # Check minimum models requirement
        if len(cluster) < min_models_required:
            return {"accepted": False, "reason": f"insufficient_models_{len(cluster)}_min_{min_models_required}"}
        
        # Calculate weighted confidence scores
        total_weight = 0
        weighted_confidence_sum = 0
        model_votes = {}
        
        for pred in cluster:
            model_cfg = get_model_by_name(pred.model)
            if model_cfg:
                # Apply configuration parameters
                base_weight = model_cfg.get_dynamic_weight(entity_type) * expertise_weight
                confidence_weighted = pow(pred.calibrated_confidence, confidence_power)
                final_weight = base_weight * confidence_weighted
                
                weighted_conf = pred.calibrated_confidence * final_weight
                total_weight += final_weight
                weighted_confidence_sum += weighted_conf
                
                # Store detailed voting information compatible with structured output
                model_votes[pred.model] = {
                    "label": f"B-{entity_type}" if pred.model not in model_votes else f"I-{entity_type}",
                    "confidence": pred.calibrated_confidence,
                    "weight": final_weight,
                    "weighted_score": weighted_conf,
                    "text": pred.text,
                    "span": (pred.char_start, pred.char_end),
                    "config_applied": {
                        "confidence_power": confidence_power,
                        "expertise_weight": expertise_weight,
                        "base_weight": base_weight
                    }
                }
        
        if total_weight == 0:
            return {"accepted": False, "reason": "no_valid_weights"}
        
        avg_weighted_confidence = weighted_confidence_sum / total_weight
        
        # Select best prediction (highest weighted confidence)
        best_pred = max(cluster, key=lambda p: (
            get_model_by_name(p.model).get_dynamic_weight(entity_type) * p.calibrated_confidence 
            if get_model_by_name(p.model) else p.calibrated_confidence
        ))
        
        # Apply threshold
        threshold = get_entity_threshold(entity_type, [], "weighted_confidence", [p.calibrated_confidence for p in cluster])
        
        if avg_weighted_confidence >= threshold:
            # Count merged tokens if available
            merged_tokens = getattr(best_pred, 'merged_from_tokens', 1)
            if hasattr(best_pred, 'token_count'):
                merged_tokens = best_pred.token_count
                
            return {
                "accepted": True,
                "entity": {
                    "text": best_pred.text,  # Full text preserved
                    "char_start": best_pred.char_start,
                    "char_end": best_pred.char_end,
                    "confidence": round(avg_weighted_confidence, 4),
                    "final_confidence": round(avg_weighted_confidence, 4),
                    "entity_type": entity_type,
                    "label": getattr(best_pred, 'label', f'B-{entity_type}'),
                    "window_id": getattr(best_pred, 'window_id', 'unknown_window'),
                    "context_snippet": getattr(best_pred, 'context_snippet', ''),
                    "processing_metadata": {
                        "model_votes": model_votes,
                        "models_voted": list(model_votes.keys()),
                        "vote_details": model_votes,
                        "threshold_used": round(threshold, 4),
                        "cluster_size": len(cluster),
                        "token_count": merged_tokens,
                        "decision_reason": f"Merged from {merged_tokens} tokens: avg_weighted_conf ({avg_weighted_confidence:.3f}) >= threshold ({threshold:.3f})",
                        "strategy": "weighted_confidence",
                        "validation_flags": getattr(best_pred, 'validation_flags', []),
                        "semantic_relationships": getattr(best_pred, 'semantic_relationships', []),
                        "postprocessing_applied": getattr(best_pred, 'postprocessing_applied', [])
                    }
                },
                "strategy_used": "weighted_confidence"
            }
        else:
            return {
                "accepted": False,
                "reason": "below_threshold",
                "confidence": avg_weighted_confidence,
                "threshold": threshold,
                "strategy_used": "weighted_confidence"
            }

    def _apply_expert_consensus_strategy(self, cluster: List[PredictionCandidate], 
                                       entity_type: str) -> Dict[str, Any]:
        """Apply expert consensus strategy - defer to expert models."""
        if not cluster:
            return {"accepted": False, "reason": "empty_cluster"}
        
        # Get strategy configuration
        strategy_config = get_ensemble_strategy_config(EnsembleStrategy.EXPERT_CONSENSUS)
        params = strategy_config.get("parameters", {})
        
        expertise_threshold = params.get("expertise_threshold", 1.5)
        consensus_requirement = params.get("consensus_requirement", 0.7)
        fallback_strategy = params.get("fallback_strategy", "weighted_confidence")
        
        # Find expert models for this entity type
        expert_predictions = []
        regular_predictions = []
        
        for pred in cluster:
            model_cfg = get_model_by_name(pred.model)
            if model_cfg:
                expertise_weight = model_cfg.expertise.entity_weights.get(entity_type, 1.0)
                if expertise_weight >= expertise_threshold:  # Use configured threshold
                    expert_predictions.append(pred)
                else:
                    regular_predictions.append(pred)
        
        # If we have expert predictions, use them exclusively
        if expert_predictions:
            target_predictions = expert_predictions
            consensus_type = "expert"
        else:
            target_predictions = regular_predictions
            consensus_type = "regular"
        
        if not target_predictions:
            return {"accepted": False, "reason": "no_valid_predictions"}
        
        # Calculate consensus
        confidence_scores = [p.calibrated_confidence for p in target_predictions]
        avg_confidence = np.mean(confidence_scores)
        
        # Check for consensus using configured requirement
        text_votes = Counter(p.text.lower().strip() for p in target_predictions)
        most_common_text, vote_count = text_votes.most_common(1)[0]
        consensus_ratio = vote_count / len(target_predictions)
        
        if consensus_ratio < consensus_requirement:
            # Fall back to configured strategy
            if fallback_strategy == "weighted_confidence":
                return self._apply_weighted_confidence_strategy(cluster, entity_type)
            else:
                return {"accepted": False, "reason": f"insufficient_consensus_{consensus_ratio:.2f}_required_{consensus_requirement}"}
        
        # We have consensus - find best prediction with the consensus text
        best_pred = max(
            [p for p in target_predictions if p.text.lower().strip() == most_common_text],
            key=lambda p: p.calibrated_confidence
        )
        
        threshold = get_entity_threshold(entity_type, [], "expert_consensus", confidence_scores)
        
        if avg_confidence >= threshold:
                return {
                    "accepted": True,
                    "entity": {
                        "text": best_pred.text,  # Full text preserved
                        "char_start": best_pred.char_start,
                        "char_end": best_pred.char_end,
                        "confidence": round(avg_confidence, 4),
                        "entity_type": entity_type,
                        "models_voted": [p.model for p in target_predictions],
                        "consensus_type": consensus_type,
                        "consensus_ratio": round(consensus_ratio, 3),
                        "threshold_used": round(threshold, 4),
                        "cluster_size": len(cluster),
                        "strategy": "expert_consensus"
                    }
                }
        
        return {
            "accepted": False,
            "reason": "insufficient_consensus",
            "consensus_ratio": consensus_ratio,
            "required_ratio": 0.7
        }

    def _apply_semantic_aware_strategy(self, cluster: List[PredictionCandidate], 
                                     entity_type: str) -> Dict[str, Any]:
        """Apply semantic-aware ensemble strategy."""
        if not cluster:
            return {"accepted": False, "reason": "empty_cluster"}
        
        # Calculate base confidence
        base_confidences = [p.calibrated_confidence for p in cluster]
        avg_base_confidence = np.mean(base_confidences)
        
        # Apply semantic relationship boosts
        semantic_boost = 0.0
        total_relationships = 0
        
        for pred in cluster:
            if pred.semantic_relationships:
                for rel in pred.semantic_relationships:
                    semantic_boost += rel.get('boost_applied', 0.0)
                    total_relationships += rel.get('total_relationships', 0)
        
        if len(cluster) > 0:
            semantic_boost = semantic_boost / len(cluster)  # Average boost per prediction
        
        # Calculate semantic-aware confidence
        semantic_confidence = min(avg_base_confidence + semantic_boost, 1.0)
        
        # Select best prediction
        best_pred = max(cluster, key=lambda p: p.calibrated_confidence + sum(
            rel.get('boost_applied', 0.0) for rel in p.semantic_relationships
        ))
        
        # Dynamic threshold based on relationships
        context_indicators = ["semantic_relationships"] if total_relationships > 0 else []
        threshold = get_entity_threshold(entity_type, context_indicators, "semantic_aware", base_confidences)
        
        if semantic_confidence >= threshold:
            return {
                "accepted": True,
                "entity": {
                    "text": best_pred.text,  # Full text preserved
                    "char_start": best_pred.char_start,
                    "char_end": best_pred.char_end,
                    "confidence": round(semantic_confidence, 4),
                    "base_confidence": round(avg_base_confidence, 4),
                    "semantic_boost": round(semantic_boost, 4),
                    "entity_type": entity_type,
                    "models_voted": [p.model for p in cluster],
                    "semantic_relationships": total_relationships,
                    "threshold_used": round(threshold, 4),
                    "cluster_size": len(cluster),
                    "strategy": "semantic_aware"
                }
            }
        else:
            return {
                "accepted": False,
                "reason": "below_semantic_threshold",
                "semantic_confidence": semantic_confidence,
                "threshold": threshold
            }

    def _apply_dynamic_threshold_strategy(self, cluster: List[PredictionCandidate], 
                                        entity_type: str) -> Dict[str, Any]:
        """Apply dynamic threshold strategy with context-aware thresholding."""
        if not cluster:
            return {"accepted": False, "reason": "empty_cluster"}
        
        # Get strategy configuration
        strategy_config = get_ensemble_strategy_config(EnsembleStrategy.DYNAMIC_THRESHOLD)
        params = strategy_config.get("parameters", {})
        
        adaptation_rate = params.get("adaptation_rate", 0.1)
        context_sensitivity = params.get("context_sensitivity", 1.0)
        agreement_sensitivity = params.get("agreement_sensitivity", 1.2)
        
        # Analyze cluster characteristics
        confidences = [p.calibrated_confidence for p in cluster]
        models = [p.model for p in cluster]
        
        # Determine context indicators with sensitivity adjustment
        context_indicators = []
        if len(set(models)) >= 3:
            context_indicators.append("high_entity_density")
        if np.std(confidences) < 0.05 * context_sensitivity:
            context_indicators.append("high_agreement")
        if entity_type in ["VALUE", "UNIT"]:
            context_indicators.append("technical_domain")
        
        # Check for semantic relationships
        has_relationships = any(pred.semantic_relationships for pred in cluster)
        if has_relationships:
            context_indicators.append("semantic_relationships")
        
        # Determine ensemble agreement level
        unique_texts = len(set(p.text.lower().strip() for p in cluster))
        if unique_texts == 1:
            agreement = "unanimous"
        elif unique_texts <= len(cluster) * 0.3:
            agreement = "strong_majority"
        elif unique_texts <= len(cluster) * 0.6:
            agreement = "simple_majority"
        else:
            agreement = "no_consensus"
        
        # Calculate dynamic threshold
        threshold = get_entity_threshold(entity_type, context_indicators, agreement, confidences)
        
        avg_confidence = np.mean(confidences)
        best_pred = max(cluster, key=lambda p: p.calibrated_confidence)
        
        if avg_confidence >= threshold:
            return {
                "accepted": True,
                "entity": {
                    "text": best_pred.text,  # Full text preserved
                    "char_start": best_pred.char_start,
                    "char_end": best_pred.char_end,
                    "confidence": round(avg_confidence, 4),
                    "entity_type": entity_type,
                    "models_voted": models,
                    "context_indicators": context_indicators,
                    "agreement_level": agreement,
                    "threshold_used": round(threshold, 4),
                    "cluster_size": len(cluster),
                    "strategy": "dynamic_threshold"
                }
            }
        else:
            return {
                "accepted": False,
                "reason": "below_dynamic_threshold",
                "confidence": avg_confidence,
                "threshold": threshold,
                "agreement": agreement
            }

    def _apply_adaptive_voting_strategy(self, cluster: List[PredictionCandidate], 
                                      entity_type: str) -> Dict[str, Any]:
        """Apply adaptive voting strategy - combines multiple approaches using configuration."""
        if not cluster:
            return {"accepted": False, "reason": "empty_cluster"}
        
        # Get strategy configuration
        strategy_config = get_ensemble_strategy_config(EnsembleStrategy.ADAPTIVE_VOTING)
        params = strategy_config.get("parameters", {})
        
        strategy_weights = params.get("strategy_weights", {
            "weighted_confidence": 0.4,
            "expert_consensus": 0.3,
            "semantic_aware": 0.3
        })
        adaptation_window = params.get("adaptation_window", 100)
        performance_threshold = params.get("performance_threshold", 0.85)
        
        # Try multiple strategies and combine results
        strategies_results = {}
        
        # Try weighted confidence
        weighted_result = self._apply_weighted_confidence_strategy(cluster, entity_type)
        strategies_results["weighted_confidence"] = weighted_result.get("accepted", False)
        
        # Try expert consensus
        expert_result = self._apply_expert_consensus_strategy(cluster, entity_type)
        strategies_results["expert_consensus"] = expert_result.get("accepted", False)
        
        # Try semantic aware
        semantic_result = self._apply_semantic_aware_strategy(cluster, entity_type)
        strategies_results["semantic_aware"] = semantic_result.get("accepted", False)
        
        # Count successes and apply weighted combination
        successful_strategies = sum(strategies_results.values())
        
        if successful_strategies >= 2:  # Majority of strategies accept
            # Use weighted combination based on configuration
            best_result = None
            best_score = 0
            
            # Calculate weighted scores for each successful strategy
            if weighted_result.get("accepted", False):
                score = strategy_weights.get("weighted_confidence", 0.4)
                if score > best_score:
                    best_score = score
                    best_result = weighted_result
                    
            if expert_result.get("accepted", False):
                score = strategy_weights.get("expert_consensus", 0.3)
                if score > best_score:
                    best_score = score
                    best_result = expert_result
                    
            if semantic_result.get("accepted", False):
                score = strategy_weights.get("semantic_aware", 0.3)
                if score > best_score:
                    best_score = score
                    best_result = semantic_result
            
            if best_result:
                result = best_result
                result["strategy"] = "adaptive_voting"
                result["entity"]["strategy"] = "adaptive_voting"
                result["entity"]["strategies_succeeded"] = successful_strategies
                result["entity"]["strategy_breakdown"] = strategies_results
                result["entity"]["best_strategy_weight"] = best_score
            
            return result
        else:
            return {
                "accepted": False,
                "reason": "insufficient_strategy_agreement",
                "strategies_succeeded": successful_strategies,
                "strategy_breakdown": strategies_results
            }

    def _calculate_confidence_stats(self, results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, float]:
        """Calculate confidence statistics by entity type."""
        stats = {}
        for entity_type, entities in results.items():
            if entities:
                confidences = [e.get("confidence", 0.0) for e in entities]
                stats[entity_type] = round(np.mean(confidences), 4)
            else:
                stats[entity_type] = 0.0
        return stats

    def _calculate_coherence_score(self, relationships: Dict[str, List[Dict[str, Any]]]) -> float:
        """Calculate semantic coherence score based on relationships."""
        if not relationships:
            return 0.0
        
        total_relationships = sum(len(rels) for rels in relationships.values())
        relationship_strengths = []
        
        for rel_type, rel_list in relationships.items():
            for rel in rel_list:
                relationship_strengths.append(rel.get('strength', 0.0))
        
        if relationship_strengths:
            return round(np.mean(relationship_strengths), 4)
        return 0.0

    def _calculate_strategy_effectiveness(self) -> Dict[str, float]:
        """Calculate effectiveness scores for different strategies."""
        effectiveness = {}
        for strategy, performance in self.strategy_performance.items():
            if len(performance) > 0:
                effectiveness[strategy] = round(np.mean(performance), 4)
            else:
                effectiveness[strategy] = 0.0
        return effectiveness

    def _create_structured_results(self, results: Dict[str, List[Dict[str, Any]]], 
                                 metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create structured window-based results ordered by character positions for manual verification."""
        
        # Collect all entities with their positions
        all_entities = []
        for entity_type, entities in results.items():
            for entity in entities:
                all_entities.append({
                    **entity,
                    "entity_type": entity_type
                })
        
        # Sort by character position for better manual verification
        all_entities.sort(key=lambda x: (x.get('char_start', 0), x.get('char_end', 0)))
        
        # Group entities by window_id
        windows_map = defaultdict(list)
        for entity in all_entities:
            window_id = entity.get('window_id', 'unknown_window')
            windows_map[window_id].append(entity)
        
        # Create structured output
        structured_results = []
        
        for window_id in sorted(windows_map.keys()):
            window_entities = windows_map[window_id]
            
            # Get window text (from first entity's context or metadata)
            window_text = ""
            if window_entities:
                # Try to reconstruct window text from entities
                window_text = self._reconstruct_window_text(window_entities)
            
            # Group entities by type within window
            entities_by_type = defaultdict(list)
            for entity in window_entities:
                entity_type = entity['entity_type']
                
                # Create enhanced entity representation
                enhanced_entity = {
                    "text": entity.get('text', ''),
                    "start_char": int(entity.get('char_start', 0)),
                    "end_char": int(entity.get('char_end', 0)),
                    "confidence": float(entity.get('confidence', 0.0)),
                    "accepted": entity.get('final_confidence', 0.0) > 0.0,
                    "accept_reason": entity.get('processing_metadata', {}).get('decision_reason', 'N/A'),
                    "models_voted": self._create_model_votes_detail(entity),
                    "merged_from_tokens": entity.get('processing_metadata', {}).get('token_count', 1)
                }
                
                entities_by_type[entity_type].append(enhanced_entity)
            
            # Sort entities within each type by position
            for entity_type in entities_by_type:
                entities_by_type[entity_type].sort(key=lambda x: (x['start_char'], x['end_char']))
            
            # Create window result
            window_result = {
                "window_id": window_id,
                "sentence": window_text,
                "entities": dict(entities_by_type)
            }
            
            structured_results.append(window_result)
        
        return structured_results
    
    def _reconstruct_window_text(self, entities: List[Dict[str, Any]]) -> str:
        """Attempt to reconstruct window text from entity positions."""
        if not entities:
            return ""
        
        # Try to get from context snippet if available
        for entity in entities:
            context = entity.get('context_snippet', '')
            if context and len(context) > 100:  # Reasonable context length
                return context
        
        # Fallback: get from processing metadata
        for entity in entities:
            metadata = entity.get('processing_metadata', {})
            if 'window_text' in metadata:
                return metadata['window_text']
        
        # Last resort: create placeholder
        window_id = entities[0].get('window_id', 'unknown')
        return f"[Window text for {window_id} - reconstruct from source if needed]"
    
    def _create_model_votes_detail(self, entity: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create detailed model voting information for manual verification."""
        votes = []
        
        # Get voting information from processing metadata
        processing_meta = entity.get('processing_metadata', {})
        model_votes = processing_meta.get('model_votes', [])
        
        if not model_votes and 'model' in entity:
            # Fallback: create single vote entry
            votes.append({
                "model": entity.get('model', 'unknown'),
                "label": entity.get('label', 'B-UNKNOWN'),
                "confidence": float(entity.get('confidence', 0.0)),
                "weight": float(processing_meta.get('model_weight', 1.0)),
                "weighted_conf": float(entity.get('calibrated_confidence', entity.get('confidence', 0.0))),
                "ensemble_result": "accepted" if entity.get('final_confidence', 0.0) > 0.0 else "rejected",
                "reason": processing_meta.get('decision_reason', 'Standard processing')
            })
        else:
            # Use detailed voting information
            for vote in model_votes:
                votes.append({
                    "model": vote.get('model', 'unknown'),
                    "label": vote.get('label', 'B-UNKNOWN'), 
                    "confidence": float(vote.get('confidence', 0.0)),
                    "weight": float(vote.get('weight', 1.0)),
                    "weighted_conf": float(vote.get('weighted_confidence', 0.0)),
                    "ensemble_result": vote.get('result', 'unknown'),
                    "reason": vote.get('reason', 'N/A')
                })
        
        return votes

    def _extract_window_text(self, entity_pos: int, window_start: int, window_end: int) -> str:
        """Extract text for window context using stored window texts."""
        # Try to find the best matching window text
        best_match = ""
        best_length = 0
        
        for window_id, window_text in self.document_windows.items():
            if len(window_text) > best_length:
                best_match = window_text
                best_length = len(window_text)
        
        if best_match:
            # Try to extract a reasonable context around the entity position
            context_start = max(0, entity_pos - 200)
            context_end = min(len(best_match), entity_pos + 800)
            context = best_match[context_start:context_end]
            
            # Clean up the context
            context = context.strip()
            if len(context) > 1000:
                # Truncate to reasonable length
                context = context[:1000] + "..."
            
            return context
        
        return f"[Text context around position {entity_pos}]"

    def _create_model_votes_detail(self, entity: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create detailed model voting information for the structured output."""
        
        # Check if we have detailed voting information from model_votes
        if "model_votes" in entity:
            model_votes = entity["model_votes"]
            detailed_votes = []
            
            for model_name, vote_info in model_votes.items():
                vote_detail = {
                    "model": model_name,
                    "label": vote_info.get("label", f"B-{entity.get('entity_type', 'UNKNOWN')}"),
                    "confidence": round(float(vote_info.get("confidence", 0.0)), 10),
                    "weight": round(float(vote_info.get("weight", 1.0)), 2),
                    "weighted_conf": round(float(vote_info.get("weighted_score", 0.0)), 10),
                    "ensemble_result": "accepted",
                    "reason": f"weighted_conf ({float(vote_info.get('weighted_score', 0.0)):.3f}) >= threshold; model expertise/weight: {float(vote_info.get('weight', 1.0)):.2f}"
                }
                detailed_votes.append(vote_detail)
            
            return detailed_votes
        
        # Check if we have vote_details (legacy format)
        elif "vote_details" in entity:
            return self._convert_vote_details_to_structured(entity["vote_details"], entity)
        
        # Fallback: create single vote from basic entity information
        return [{
            "model": entity.get("models_voted", [entity.get("model", "Unknown")])[0],
            "label": f"B-{entity.get('entity_type', 'UNKNOWN')}",
            "confidence": round(float(entity.get("confidence", 0.0)), 10),
            "weight": 1.0,
            "weighted_conf": round(float(entity.get("confidence", 0.0)), 10),
            "ensemble_result": "accepted",
            "reason": f"confidence ({float(entity.get('confidence', 0.0)):.3f}) >= threshold"
        }]

    def _convert_vote_details_to_structured(self, vote_details: Dict[str, Any], entity: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert vote_details format to structured format."""
        detailed_votes = []
        
        for model_name, vote_info in vote_details.items():
            vote_detail = {
                "model": model_name,
                "label": f"B-{entity.get('entity_type', 'UNKNOWN')}",
                "confidence": round(float(vote_info.get("confidence", 0.0)), 10),
                "weight": round(float(vote_info.get("weight", 1.0)), 2),
                "weighted_conf": round(float(vote_info.get("weighted_score", 0.0)), 10),
                "ensemble_result": "accepted",
                "reason": f"weighted_conf ({float(vote_info.get('weighted_score', 0.0)):.3f}) >= threshold; model expertise/weight: {float(vote_info.get('weight', 1.0)):.2f}"
            }
            detailed_votes.append(vote_detail)
        
        return detailed_votes

    def _get_model_specific_tokenizer(self, model_name: str, model_id: str, model_vocab_size: int):
        """
        Get the appropriate tokenizer for each model to avoid vocabulary mismatches.
        
        This eliminates the 'Extended tokenizer too large' warnings by using the 
        exact tokenizer each model was trained with.
        """
        # First, try to use extended tokenizer if it exists and is compatible
        extended_tokenizer_path = Path(WORKSPACE_DIR) / "models" / "tokenizers" / f"{model_name}_extended"
        
        if extended_tokenizer_path.exists():
            try:
                extended_tokenizer = AutoTokenizer.from_pretrained(extended_tokenizer_path, use_fast=True)
                actual_vocab_size = len(extended_tokenizer)
                
                # Allow up to 5% vocabulary expansion for extended tokenizers
                if actual_vocab_size <= model_vocab_size * 1.05:
                    logger.info(
                        f"Using compatible extended tokenizer for {model_name} (vocab: {actual_vocab_size})",
                        source="EnsembleInferenceService._get_model_specific_tokenizer"
                    )
                    return extended_tokenizer
                else:
                    logger.info(
                        f"Extended tokenizer for {model_name} exceeds model capacity ({actual_vocab_size} vs {model_vocab_size}), using base tokenizer",
                        source="EnsembleInferenceService._get_model_specific_tokenizer",
                        context={
                            "strategy": "fallback_to_base",
                            "extended_vocab_size": actual_vocab_size,
                            "model_vocab_size": model_vocab_size
                        }
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to load extended tokenizer for {model_name}: {e}",
                    source="EnsembleInferenceService._get_model_specific_tokenizer"
                )
        
        # Use model-specific base tokenizer
        base_tokenizer_id = self._get_base_tokenizer_id(model_name, model_id)
        tokenizer = AutoTokenizer.from_pretrained(base_tokenizer_id, use_fast=True)
        
        logger.info(
            f"Using base tokenizer for {model_name}: {base_tokenizer_id} (vocab: {len(tokenizer)})",
            source="EnsembleInferenceService._get_model_specific_tokenizer"  
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

    def _save_enhanced_results(self, results: Dict[str, List[Dict[str, Any]]], 
                             metadata: Dict[str, Any], base_name: str):
        """Save results to single ensemble_results.json file with strict processing applied."""
        
        # Update metadata to reflect strict sentence processing
        enhanced_metadata = metadata.copy()
        enhanced_metadata["processing_pipeline"] = enhanced_metadata.get("processing_pipeline", [])
        enhanced_metadata["processing_pipeline"].append("strict_sentence_processor")
        enhanced_metadata["strict_processing_applied"] = True
        
        # Recalculate quality metrics after strict processing
        total_entities = sum(len(entities) for entities in results.values())
        if total_entities > 0:
            # Calculate average confidence from processed results
            all_confidences = []
            for entities in results.values():
                for entity in entities:
                    if isinstance(entity, dict) and 'confidence' in entity:
                        all_confidences.append(entity['confidence'])
            
            avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
            
            # Update quality metrics
            enhanced_metadata["quality_metrics"]["total_entities_extracted"] = total_entities
            enhanced_metadata["quality_metrics"]["average_confidence"] = avg_confidence
            enhanced_metadata["quality_metrics"]["entity_type_distribution"] = {
                entity_type: len(entities) for entity_type, entities in results.items()
            }
        
        # Create single comprehensive results file
        comprehensive_results = {
            "metadata": enhanced_metadata,
            "entities": results,
            "processing_summary": {
                "total_entities": total_entities,
                "entity_breakdown": {k: len(v) for k, v in results.items()},
                "processing_method": "strict_sentence_processing",
                "confidence_thresholds_applied": True,
                "single_file_output": True
            }
        }
        
        # Save single results file
        results_path = self.results_dir / f"{base_name}_ensemble_results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            f.write(JSONSerializable.safe_json_dumps(comprehensive_results, indent=2, ensure_ascii=False))
        
        # Save to database (truncated results only)
        try:
            results_str = JSONSerializable.safe_json_dumps(results, ensure_ascii=False)
            truncated_results = results_str[:500000] if len(results_str) > 500000 else results_str
            
            # Get processing strategy summary
            strategy_summary = JSONSerializable.safe_json_dumps(
                enhanced_metadata.get("ensemble_strategy_performance", {}), ensure_ascii=False
            )[:2048]
            
            db = DatabaseManager()
            db.create_record("extraction_results", {
                "file_name": base_name,
                "extracted_entities": truncated_results,
                "results_file_path": str(results_path),
                "total_entities": enhanced_metadata["quality_metrics"]["total_entities_extracted"],
                "processing_strategy": strategy_summary,
                "ensemble_strategy": enhanced_metadata.get("ensemble_strategy", "unknown"),
                "average_confidence": enhanced_metadata["quality_metrics"].get("average_confidence", 0.0),
                "processed_on": datetime.now().isoformat() + "Z",
                "model_version": "ensemble_v1.0_strict",
                "status": "success",
                "processing_notes": f"Strict sentence processing completed. Single file output: {results_path}"
            })
            
            logger.info(
                f"Saved strict processing results for {base_name}",
                source="EnsembleInferenceService._save_enhanced_results",
                context={
                    "results_file": str(results_path),
                    "total_entities": enhanced_metadata["quality_metrics"]["total_entities_extracted"],
                    "strict_processing": True,
                    "single_file_output": True
                }
            )
        except Exception as e:
            logger.error(f"Database save failed: {e}",
                        source="EnsembleInferenceService._save_enhanced_results", 
                        error=e)
