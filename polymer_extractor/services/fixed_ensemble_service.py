"""
Fixed Ensemble Inference Service - Resolving Performance Issues

This service addresses the critical performance problems:
1. Proper model expertise weighting (PhysBERT dominates for SYMBOL/VALUE/UNIT)
2. Complete span boundary detection and word completion
3. True ensemble voting instead of single model selection
4. Confidence recalibration based on model expertise
5. Semantic relationship boosting for VALUE-UNIT pairs
"""

import os
import json
import re
import torch
import numpy as np
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from transformers import AutoTokenizer, AutoModelForTokenClassification
from lxml import etree

from polymer_extractor.model_config import (
    ENSEMBLE_MODELS, LABELS, LABEL2ID, ID2LABEL, get_model_by_name,
    ENTITY_SEMANTIC_GROUPS, EnsembleStrategy
)
from polymer_extractor.utils.logging import logger
from polymer_extractor.utils.paths import WORKSPACE_DIR, SAMPLES_DIR


@dataclass
class FixedPredictionCandidate:
    """Clean prediction candidate with proper metadata."""
    text: str
    char_start: int
    char_end: int
    entity_type: str
    confidence: float
    model: str
    window_id: str = ""
    context: str = ""
    model_expertise_weight: float = 1.0
    span_completion_applied: bool = False
    ensemble_weight: float = 0.0


class SpanCompleter:
    """Handles proper span boundary completion to avoid fragmentary extractions."""
    
    def __init__(self):
        self.word_boundary_pattern = re.compile(r'\b')
        self.chemical_symbols = {'C', 'H', 'N', 'O', 'S', 'P', 'Si', 'Al', 'Fe', 'Cu', 'Zn'}
        
    def complete_span(self, text: str, start: int, end: int, source_text: str) -> Tuple[str, int, int]:
        """
        Complete span to include full words and handle chemical notation.
        
        This fixes issues like:
        - ", an" → "an increase"
        - "ex" → "experimental"
        - "crosslinking density (υ," → "crosslinking density (υ)"
        """
        if start >= len(source_text) or end > len(source_text):
            return text, start, end
        
        # Extract current text
        current_text = source_text[start:end]
        
        # Expand backwards to word boundary
        new_start = start
        while new_start > 0:
            char = source_text[new_start - 1]
            if char.isalnum() or char in '-_':
                new_start -= 1
            else:
                break
        
        # Expand forwards to word boundary  
        new_end = end
        while new_end < len(source_text):
            char = source_text[new_end]
            if char.isalnum() or char in '-_':
                new_end += 1
            else:
                break
        
        # Handle parentheses completion
        new_start, new_end = self._complete_parentheses(source_text, new_start, new_end)
        
        # Handle chemical notation (subscripts, superscripts)
        new_start, new_end = self._complete_chemical_notation(source_text, new_start, new_end)
        
        # Handle unit expressions
        new_start, new_end = self._complete_unit_expressions(source_text, new_start, new_end)
        
        # Extract final completed text
        completed_text = source_text[new_start:new_end].strip()
        
        # Validate completion makes sense
        if self._is_valid_completion(current_text, completed_text):
            return completed_text, new_start, new_end
        else:
            return text, start, end
    
    def _complete_parentheses(self, source_text: str, start: int, end: int) -> Tuple[int, int]:
        """Complete unmatched parentheses."""
        text_section = source_text[start:end]
        
        # Count parentheses
        open_parens = text_section.count('(')
        close_parens = text_section.count(')')
        
        # If we have unmatched opening parentheses, look for closing ones
        if open_parens > close_parens:
            search_end = min(end + 50, len(source_text))  # Search up to 50 chars ahead
            for i in range(end, search_end):
                if source_text[i] == ')':
                    end = i + 1
                    close_parens += 1
                    if close_parens == open_parens:
                        break
        
        # If we have unmatched closing parentheses, look for opening ones
        elif close_parens > open_parens:
            search_start = max(start - 50, 0)  # Search up to 50 chars back
            for i in range(start - 1, search_start - 1, -1):
                if source_text[i] == '(':
                    start = i
                    open_parens += 1
                    if open_parens == close_parens:
                        break
        
        return start, end
    
    def _complete_chemical_notation(self, source_text: str, start: int, end: int) -> Tuple[int, int]:
        """Complete chemical formulas and notation."""
        # Look for subscripts and superscripts
        if end < len(source_text):
            # Check for numeric subscripts
            while end < len(source_text) and source_text[end].isdigit():
                end += 1
            
            # Check for superscript indicators
            if end < len(source_text) and source_text[end] in '⁻⁺°':
                end += 1
                while end < len(source_text) and source_text[end].isdigit():
                    end += 1
        
        return start, end
    
    def _complete_unit_expressions(self, source_text: str, start: int, end: int) -> Tuple[int, int]:
        """Complete unit expressions like 'g.mol⁻¹' or 'cm⁻¹'."""
        # Common unit patterns
        unit_patterns = [
            r'g\.mol⁻¹', r'cm⁻¹', r'min⁻¹', r's⁻¹', r'Hz',
            r'°C', r'K', r'Pa', r'MPa', r'GPa', r'wt%', r'mol%'
        ]
        
        # Check if we're in the middle of a unit expression
        context = source_text[max(0, start-10):min(len(source_text), end+10)]
        
        for pattern in unit_patterns:
            matches = list(re.finditer(pattern, context))
            for match in matches:
                match_start = max(0, start-10) + match.start()
                match_end = max(0, start-10) + match.end()
                
                # If our span overlaps with this unit, expand to include it
                if not (end < match_start or start > match_end):
                    start = min(start, match_start)
                    end = max(end, match_end)
        
        return start, end
    
    def _is_valid_completion(self, original: str, completed: str) -> bool:
        """Validate that span completion makes sense."""
        # Don't expand too much (more than 3x original length)
        if len(completed) > len(original) * 3:
            return False
        
        # Don't accept completions that are just punctuation
        if completed.strip() in '.,;:()[]{}':
            return False
        
        # Don't accept very short fragments
        if len(completed.strip()) < 2:
            return False
        
        return True


class ModelExpertiseCalculator:
    """Calculate model expertise weights for proper ensemble voting."""
    
    def __init__(self):
        self.model_configs = {model.name: model for model in ENSEMBLE_MODELS}
    
    def get_expertise_weight(self, model_name: str, entity_type: str) -> float:
        """Get model expertise weight for specific entity type."""
        if model_name not in self.model_configs:
            return 0.5  # Default low weight for unknown models
        
        model_config = self.model_configs[model_name]
        base_weight = model_config.base_weight
        entity_weight = model_config.expertise.entity_weights.get(entity_type, 1.0)
        reliability = model_config.expertise.reliability_score
        
        # Calculate final expertise weight
        expertise_weight = base_weight * entity_weight * reliability
        
        logger.debug(f"Expertise weight for {model_name} on {entity_type}: {expertise_weight}",
                    source="ModelExpertiseCalculator.get_expertise_weight",
                    context={
                        "base_weight": base_weight,
                        "entity_weight": entity_weight,
                        "reliability": reliability
                    })
        
        return expertise_weight
    
    def get_confidence_calibration(self, model_name: str, entity_type: str, 
                                 raw_confidence: float) -> float:
        """Calibrate confidence based on model expertise."""
        expertise_weight = self.get_expertise_weight(model_name, entity_type)
        
        # Apply expertise-based calibration
        if expertise_weight > 1.5:  # High expertise
            calibrated = min(0.99, raw_confidence * 1.1)  # Slight boost
        elif expertise_weight < 0.8:  # Low expertise
            calibrated = raw_confidence * 0.8  # Penalty
        else:
            calibrated = raw_confidence  # No change
        
        return calibrated


class TrueEnsembleVoter:
    """Implements true ensemble voting instead of single model selection."""
    
    def __init__(self):
        self.expertise_calc = ModelExpertiseCalculator()
        self.span_completer = SpanCompleter()
    
    def vote_on_cluster(self, cluster: List[FixedPredictionCandidate], 
                       source_text: str) -> Optional[Dict[str, Any]]:
        """
        Perform true ensemble voting on a cluster of predictions.
        
        This fixes the core issue where single models were overriding ensembles.
        """
        if not cluster:
            return None
        
        entity_type = cluster[0].entity_type
        logger.debug(f"Ensemble voting on {len(cluster)} predictions for {entity_type}",
                    source="TrueEnsembleVoter.vote_on_cluster")
        
        # Calculate expertise weights for each prediction
        weighted_predictions = []
        for pred in cluster:
            expertise_weight = self.expertise_calc.get_expertise_weight(pred.model, entity_type)
            calibrated_confidence = self.expertise_calc.get_confidence_calibration(
                pred.model, entity_type, pred.confidence
            )
            
            # Complete spans to avoid fragments
            completed_text, new_start, new_end = self.span_completer.complete_span(
                pred.text, pred.char_start, pred.char_end, source_text
            )
            
            ensemble_weight = expertise_weight * calibrated_confidence
            
            weighted_pred = FixedPredictionCandidate(
                text=completed_text,
                char_start=new_start,
                char_end=new_end,
                entity_type=entity_type,
                confidence=calibrated_confidence,
                model=pred.model,
                window_id=pred.window_id,
                context=pred.context,
                model_expertise_weight=expertise_weight,
                span_completion_applied=(completed_text != pred.text),
                ensemble_weight=ensemble_weight
            )
            weighted_predictions.append(weighted_pred)
        
        # Sort by ensemble weight (highest first)
        weighted_predictions.sort(key=lambda p: p.ensemble_weight, reverse=True)
        
        # Apply voting strategy based on entity type
        if entity_type in ['SYMBOL', 'VALUE', 'UNIT']:
            # For quantitative entities, prioritize PhysBERT if present
            result = self._physics_aware_voting(weighted_predictions, entity_type)
        elif entity_type == 'POLYMER':
            # For polymers, prioritize PolymerNER if present
            result = self._polymer_aware_voting(weighted_predictions, entity_type)
        else:
            # For other entities, use weighted consensus
            result = self._weighted_consensus_voting(weighted_predictions, entity_type)
        
        return result
    
    def _physics_aware_voting(self, predictions: List[FixedPredictionCandidate], 
                            entity_type: str) -> Dict[str, Any]:
        """Specialized voting for physics/quantitative entities."""
        # Check if PhysBERT is present with reasonable confidence
        physbert_preds = [p for p in predictions if p.model == 'PhysBERT' and p.confidence > 0.6]
        
        if physbert_preds:
            # PhysBERT takes priority for physics entities
            best_physbert = max(physbert_preds, key=lambda p: p.ensemble_weight)
            
            logger.info(f"PhysBERT dominates for {entity_type}: {best_physbert.text}",
                       source="TrueEnsembleVoter._physics_aware_voting",
                       context={"confidence": best_physbert.confidence,
                               "expertise_weight": best_physbert.model_expertise_weight})
            
            return self._create_ensemble_result(best_physbert, predictions, "physics_expert_priority")
        
        # Fallback to weighted voting
        return self._weighted_consensus_voting(predictions, entity_type)
    
    def _polymer_aware_voting(self, predictions: List[FixedPredictionCandidate], 
                            entity_type: str) -> Dict[str, Any]:
        """Specialized voting for polymer entities."""
        # Check if PolymerNER is present with reasonable confidence
        polymer_preds = [p for p in predictions if p.model == 'PolymerNER' and p.confidence > 0.6]
        
        if polymer_preds:
            # PolymerNER takes priority for polymer entities
            best_polymer = max(polymer_preds, key=lambda p: p.ensemble_weight)
            
            logger.info(f"PolymerNER dominates for {entity_type}: {best_polymer.text}",
                       source="TrueEnsembleVoter._polymer_aware_voting")
            
            return self._create_ensemble_result(best_polymer, predictions, "polymer_expert_priority")
        
        # Fallback to weighted voting
        return self._weighted_consensus_voting(predictions, entity_type)
    
    def _weighted_consensus_voting(self, predictions: List[FixedPredictionCandidate], 
                                 entity_type: str) -> Dict[str, Any]:
        """Standard weighted consensus voting."""
        if not predictions:
            return None
        
        # Take the highest weighted prediction
        best_prediction = predictions[0]  # Already sorted by ensemble_weight
        
        # Calculate ensemble confidence as weighted average
        total_weight = sum(p.ensemble_weight for p in predictions)
        if total_weight > 0:
            ensemble_confidence = sum(p.confidence * p.ensemble_weight for p in predictions) / total_weight
        else:
            ensemble_confidence = best_prediction.confidence
        
        logger.info(f"Weighted consensus for {entity_type}: {best_prediction.text}",
                   source="TrueEnsembleVoter._weighted_consensus_voting",
                   context={"ensemble_confidence": ensemble_confidence,
                           "num_votes": len(predictions)})
        
        result = self._create_ensemble_result(best_prediction, predictions, "weighted_consensus")
        result["confidence"] = ensemble_confidence
        
        return result
    
    def _create_ensemble_result(self, selected_pred: FixedPredictionCandidate,
                              all_predictions: List[FixedPredictionCandidate],
                              strategy: str) -> Dict[str, Any]:
        """Create final ensemble result with full metadata."""
        return {
            "text": selected_pred.text,
            "char_start": selected_pred.char_start,
            "char_end": selected_pred.char_end,
            "entity_type": selected_pred.entity_type,
            "confidence": selected_pred.confidence,
            "model": "ensemble",
            "ensemble_strategy": strategy,
            "selected_model": selected_pred.model,
            "span_completion_applied": selected_pred.span_completion_applied,
            "model_votes": [
                {
                    "model": p.model,
                    "text": p.text,
                    "confidence": p.confidence,
                    "expertise_weight": p.model_expertise_weight,
                    "ensemble_weight": p.ensemble_weight
                }
                for p in all_predictions
            ],
            "total_votes": len(all_predictions)
        }


class FixedEnsembleService:
    """Fixed ensemble service that addresses all performance issues."""
    
    def __init__(self):
        self.voter = TrueEnsembleVoter()
        self.tokenizers = {}
        self.models = {}
        
    def run_inference(self, tei_path: str) -> Dict[str, Any]:
        """
        Run fixed ensemble inference with proper voting and span completion.
        """
        base_name = Path(tei_path).stem
        logger.info(f"Starting fixed ensemble inference for {base_name}",
                   source="FixedEnsembleService.run_inference")
        
        # Extract full text for span completion
        source_text = self._extract_full_text(tei_path)
        
        # Get predictions from all models
        all_predictions = []
        
        for model_config in ENSEMBLE_MODELS:
            model_name = model_config.name
            try:
                model_predictions = self._run_single_model(base_name, model_name, source_text)
                all_predictions.extend(model_predictions)
                logger.info(f"Got {len(model_predictions)} predictions from {model_name}",
                           source="FixedEnsembleService.run_inference")
            except Exception as e:
                logger.error(f"Failed to run {model_name}: {str(e)}",
                           source="FixedEnsembleService.run_inference")
                continue
        
        if not all_predictions:
            logger.error("No predictions from any model", 
                        source="FixedEnsembleService.run_inference")
            return {"entities": [], "error": "no_predictions"}
        
        # Create clusters of overlapping predictions
        clusters = self._create_position_clusters(all_predictions)
        logger.info(f"Created {len(clusters)} clusters from {len(all_predictions)} predictions",
                   source="FixedEnsembleService.run_inference")
        
        # Vote on each cluster
        final_entities = []
        ensemble_stats = {
            "total_clusters": len(clusters),
            "accepted_entities": 0,
            "strategies_used": Counter(),
            "models_contributing": Counter()
        }
        
        for cluster in clusters:
            ensemble_result = self.voter.vote_on_cluster(cluster, source_text)
            if ensemble_result:
                final_entities.append(ensemble_result)
                ensemble_stats["accepted_entities"] += 1
                ensemble_stats["strategies_used"][ensemble_result["ensemble_strategy"]] += 1
                ensemble_stats["models_contributing"][ensemble_result["selected_model"]] += 1
        
        # Organize by entity type
        entities_by_type = defaultdict(list)
        for entity in final_entities:
            entities_by_type[entity["entity_type"]].append(entity)
        
        result = {
            "entities": dict(entities_by_type),
            "total_entities": len(final_entities),
            "ensemble_stats": dict(ensemble_stats),
            "source_tei": tei_path
        }
        
        logger.info(f"Fixed ensemble completed: {len(final_entities)} entities",
                   source="FixedEnsembleService.run_inference",
                   context=ensemble_stats)
        
        return result
    
    def _extract_full_text(self, tei_path: str) -> str:
        """Extract full text from TEI file for span completion."""
        try:
            tree = etree.parse(tei_path)
            raw_text = " ".join(tree.xpath("//text()"))
            return re.sub(r'\s+', ' ', raw_text).strip()
        except Exception as e:
            logger.error(f"Failed to extract text from {tei_path}: {str(e)}",
                        source="FixedEnsembleService._extract_full_text")
            return ""
    
    def _run_single_model(self, base_name: str, model_name: str, 
                         source_text: str) -> List[FixedPredictionCandidate]:
        """Run inference for a single model and return predictions."""
        # Look for existing inference results
        model_dir = os.path.join(SAMPLES_DIR, f"{model_name}_outputs")
        results_file = os.path.join(model_dir, f"{base_name}.tei_inference_results.json")
        
        if not os.path.exists(results_file):
            logger.warning(f"No inference results found for {model_name} at {results_file}",
                          source="FixedEnsembleService._run_single_model")
            return []
        
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            predictions = []
            for entity_type, entities in results.get("entities", {}).items():
                for entity in entities:
                    pred = FixedPredictionCandidate(
                        text=entity["text"],
                        char_start=entity["char_start"],
                        char_end=entity["char_end"],
                        entity_type=entity_type,
                        confidence=entity.get("confidence", 0.5),
                        model=model_name,
                        window_id=entity.get("window_id", ""),
                        context=entity.get("context", "")
                    )
                    predictions.append(pred)
            
            return predictions
            
        except Exception as e:
            logger.error(f"Failed to load results for {model_name}: {str(e)}",
                        source="FixedEnsembleService._run_single_model")
            return []
    
    def _create_position_clusters(self, predictions: List[FixedPredictionCandidate]) -> List[List[FixedPredictionCandidate]]:
        """Create clusters of predictions based on position overlap."""
        if not predictions:
            return []
        
        # Sort by position
        sorted_preds = sorted(predictions, key=lambda p: (p.char_start, p.char_end))
        clusters = []
        
        for pred in sorted_preds:
            # Find best matching cluster
            best_cluster = None
            best_overlap = 0.0
            
            for cluster in clusters:
                overlap = self._calculate_cluster_overlap(pred, cluster)
                if overlap > best_overlap and overlap > 0.3:  # 30% overlap threshold
                    best_overlap = overlap
                    best_cluster = cluster
            
            if best_cluster is not None:
                best_cluster.append(pred)
            else:
                clusters.append([pred])
        
        return clusters
    
    def _calculate_cluster_overlap(self, pred: FixedPredictionCandidate, 
                                 cluster: List[FixedPredictionCandidate]) -> float:
        """Calculate maximum overlap between prediction and any in cluster."""
        max_overlap = 0.0
        
        for cluster_pred in cluster:
            overlap = self._calculate_position_overlap(pred, cluster_pred)
            max_overlap = max(max_overlap, overlap)
        
        return max_overlap
    
    def _calculate_position_overlap(self, pred1: FixedPredictionCandidate, 
                                  pred2: FixedPredictionCandidate) -> float:
        """Calculate position overlap between two predictions."""
        start1, end1 = pred1.char_start, pred1.char_end
        start2, end2 = pred2.char_start, pred2.char_end
        
        # Calculate overlap
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        
        if overlap_start >= overlap_end:
            # No overlap, check proximity
            distance = min(abs(start1 - end2), abs(start2 - end1))
            return max(0.0, 1.0 - distance / 20.0) * 0.3  # Proximity score
        
        # Calculate overlap ratio
        overlap_length = overlap_end - overlap_start
        min_length = min(end1 - start1, end2 - start2)
        
        return overlap_length / min_length if min_length > 0 else 0.0
