"""
Enhanced model configurations and hyperparameters for intelligent ensemble operations.
Provides dynamic thresholding, performance tracking, and adaptive ensemble strategies.
"""
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import statistics
import numpy as np

# Enhanced label configuration with semantic groupings
LABELS = [
    "O",
    "B-PROPERTY", "I-PROPERTY",
    "B-SYMBOL", "I-SYMBOL",
    "B-VALUE", "I-VALUE",
    "B-UNIT", "I-UNIT",
    "B-POLYMER", "I-POLYMER",
    "B-MATERIAL", "I-MATERIAL"
]

LABEL2ID = {label: idx for idx, label in enumerate(LABELS)}
ID2LABEL = {idx: label for label, idx in LABEL2ID.items()}

# Entity type semantic groupings for intelligent processing
ENTITY_SEMANTIC_GROUPS = {
    "QUANTITATIVE": ["VALUE", "UNIT", "SYMBOL"],
    "MATERIAL_RELATED": ["POLYMER", "MATERIAL"],
    "DESCRIPTIVE": ["PROPERTY"],
    "CRITICAL_PAIRS": [("VALUE", "UNIT"), ("PROPERTY", "VALUE"), ("POLYMER", "PROPERTY")]
}

class EnsembleStrategy(Enum):
    """Ensemble voting strategies."""
    WEIGHTED_CONFIDENCE = "weighted_confidence"
    EXPERT_CONSENSUS = "expert_consensus"
    DYNAMIC_THRESHOLD = "dynamic_threshold"
    SEMANTIC_AWARE = "semantic_aware"
    ADAPTIVE_VOTING = "adaptive_voting"

class ConfidenceMode(Enum):
    """Confidence calculation modes."""
    STATIC = "static"
    ADAPTIVE = "adaptive"
    PERFORMANCE_BASED = "performance_based"
    CONTEXT_AWARE = "context_aware"

@dataclass
class ModelExpertise:
    """Advanced model expertise configuration."""
    entity_weights: Dict[str, float]
    context_strengths: Dict[str, float] = field(default_factory=dict)
    error_patterns: List[str] = field(default_factory=list)
    reliability_score: float = 1.0
    specialization_domains: List[str] = field(default_factory=list)

@dataclass
class EnsembleModel:
    """Enhanced model configuration for ensemble operations."""
    name: str
    model_id: str
    base_weight: float
    expertise: ModelExpertise
    performance_history: Dict[str, List[float]] = field(default_factory=dict)
    training_config: Dict[str, Any] = field(default_factory=dict)
    preprocessing_requirements: List[str] = field(default_factory=list)
    postprocessing_steps: List[str] = field(default_factory=list)

    def get_dynamic_weight(self, entity_type: str, context: str = "general") -> float:
        """Calculate dynamic weight based on expertise and performance."""
        base = self.base_weight
        expertise_multiplier = self.expertise.entity_weights.get(entity_type, 1.0)
        context_multiplier = self.expertise.context_strengths.get(context, 1.0)
        reliability_factor = self.expertise.reliability_score

        # Performance-based adjustment
        if entity_type in self.performance_history:
            recent_performance = np.mean(self.performance_history[entity_type][-10:])
            performance_factor = min(recent_performance / 0.8, 1.2)  # Cap at 20% boost
        else:
            performance_factor = 1.0

        return base * expertise_multiplier * context_multiplier * reliability_factor * performance_factor

# Enhanced ensemble model configurations
ENSEMBLE_MODELS = [
    EnsembleModel(
        name="PolymerNER",
        model_id="pranav-s/PolymerNER",
        base_weight=1.6,
        expertise=ModelExpertise(
            entity_weights={
                "POLYMER": 2.2,
                "MATERIAL": 1.8,
                "PROPERTY": 1.4,
                "SYMBOL": 1.2,
                "VALUE": 1.1,
                "UNIT": 1.0
            },
            context_strengths={
                "polymer_synthesis": 2.0,
                "polymer_characterization": 1.8,
                "mechanical_properties": 1.6,
                "thermal_properties": 1.4
            },
            reliability_score=1.0,
            specialization_domains=["polymer_science", "materials_engineering"]
        ),
        training_config={"lr": 2e-5, "epochs": 7, "weight_decay": 0.021},
        preprocessing_requirements=["polymer_canonicalization", "chemistry_normalization"],
        postprocessing_steps=["polymer_validation", "synonym_resolution"]
    ),

    EnsembleModel(
        name="MatSciBERT",
        model_id="m3rg-iitd/matscibert",
        base_weight=1.3,
        expertise=ModelExpertise(
            entity_weights={
                "MATERIAL": 2.0,
                "PROPERTY": 1.5,
                "POLYMER": 1.2,
                "SYMBOL": 1.1,
                "VALUE": 1.0,
                "UNIT": 1.0
            },
            context_strengths={
                "materials_science": 2.0,
                "crystallography": 1.8,
                "electronic_properties": 1.6,
                "mechanical_properties": 1.4
            },
            reliability_score=0.95,
            specialization_domains=["materials_science", "condensed_matter"]
        ),
        training_config={"lr": 2e-5, "epochs": 5, "weight_decay": 0.01},
        preprocessing_requirements=["materials_normalization", "scientific_notation"],
        postprocessing_steps=["materials_validation", "unit_standardization"]
    ),

    EnsembleModel(
        name="SciBERT",
        model_id="allenai/scibert_scivocab_uncased",
        base_weight=1.1,
        expertise=ModelExpertise(
            entity_weights={
                "PROPERTY": 1.3,
                "VALUE": 1.2,
                "UNIT": 1.2,
                "SYMBOL": 1.1,
                "POLYMER": 1.0,
                "MATERIAL": 1.0
            },
            context_strengths={
                "general_science": 1.5,
                "experimental_methods": 1.4,
                "data_analysis": 1.3
            },
            reliability_score=0.9,
            specialization_domains=["general_science", "interdisciplinary"]
        ),
        training_config={"lr": 2e-5, "epochs": 5, "weight_decay": 0.01},
        preprocessing_requirements=["scientific_normalization"],
        postprocessing_steps=["general_validation", "confidence_calibration"]
    ),

    EnsembleModel(
        name="PhysBERT",
        model_id="thellert/physbert_cased",
        base_weight=1.0,
        expertise=ModelExpertise(
            entity_weights={
                "SYMBOL": 1.8,
                "VALUE": 1.6,
                "UNIT": 1.6,
                "PROPERTY": 1.3,
                "POLYMER": 0.8,
                "MATERIAL": 0.9
            },
            context_strengths={
                "physics": 1.8,
                "thermodynamics": 1.6,
                "quantum_mechanics": 1.4,
                "statistical_mechanics": 1.3
            },
            reliability_score=0.85,
            specialization_domains=["physics", "physical_chemistry"]
        ),
        training_config={"lr": 2.5e-5, "epochs": 6, "weight_decay": 0.015},
        preprocessing_requirements=["physics_notation", "symbol_normalization"],
        postprocessing_steps=["physics_validation", "dimensional_analysis"]
    ),

    EnsembleModel(
        name="BioBERT",
        model_id="dmis-lab/biobert-v1.1",
        base_weight=0.7,
        expertise=ModelExpertise(
            entity_weights={
                "POLYMER": 0.6,
                "MATERIAL": 0.7,
                "PROPERTY": 0.8,
                "SYMBOL": 0.5,
                "VALUE": 0.6,
                "UNIT": 0.5
            },
            context_strengths={
                "biomedical": 1.2,
                "biochemistry": 1.0,
                "biomaterials": 1.4
            },
            reliability_score=0.75,
            specialization_domains=["biomedical", "biochemistry"]
        ),
        training_config={"lr": 1.8e-5, "epochs": 4, "weight_decay": 0.008},
        preprocessing_requirements=["biomedical_normalization"],
        postprocessing_steps=["biomedical_validation"]
    )
]

# Dynamic confidence thresholds based on ensemble agreement and context
class DynamicThresholds:
    """Dynamic threshold calculator for adaptive confidence management."""

    BASE_THRESHOLDS = {
        "POLYMER": 0.82,
        "MATERIAL": 0.80,
        "PROPERTY": 0.75,
        "VALUE": 0.72,
        "UNIT": 0.72,
        "SYMBOL": 0.70,
        "GLOBAL": 0.75
    }

    CONTEXT_MODIFIERS = {
        "high_entity_density": -0.05,  # Lower threshold in dense contexts
        "low_entity_density": 0.03,   # Raise threshold in sparse contexts
        "technical_domain": -0.02,    # Lower for technical content
        "experimental_data": -0.03,   # Lower for experimental contexts
        "review_article": 0.02,       # Raise for review contexts
        "synthesis_procedure": -0.04   # Lower for synthesis descriptions
    }

    ENSEMBLE_AGREEMENT_MODIFIERS = {
        "unanimous": -0.08,      # All models agree
        "strong_majority": -0.05, # 4/5 or 3/4 models agree
        "simple_majority": 0.0,  # 3/5 models agree
        "weak_consensus": 0.03,  # 2/3 models agree
        "no_consensus": 0.08     # Less than majority agreement
    }

    @classmethod
    def calculate_threshold(cls, entity_type: str, context_indicators: List[str],
                          ensemble_agreement: str, model_confidences: List[float]) -> float:
        """Calculate dynamic threshold based on context and ensemble state."""
        base = cls.BASE_THRESHOLDS.get(entity_type, cls.BASE_THRESHOLDS["GLOBAL"])

        # Apply context modifiers
        context_adjustment = sum(
            cls.CONTEXT_MODIFIERS.get(indicator, 0.0)
            for indicator in context_indicators
        )

        # Apply ensemble agreement modifier
        agreement_adjustment = cls.ENSEMBLE_AGREEMENT_MODIFIERS.get(
            ensemble_agreement, 0.0
        )

        # Apply confidence distribution adjustment
        if model_confidences:
            confidence_std = np.std(model_confidences)
            if confidence_std > 0.2:  # High disagreement
                distribution_adjustment = 0.05
            elif confidence_std < 0.05:  # High agreement
                distribution_adjustment = -0.03
            else:
                distribution_adjustment = 0.0
        else:
            distribution_adjustment = 0.0

        final_threshold = base + context_adjustment + agreement_adjustment + distribution_adjustment
        return max(0.3, min(0.95, final_threshold))  # Clamp between reasonable bounds

# Validation and confidence boosting configurations
VALIDATION_CONFIDENCE_ADJUSTMENTS = {
    "EXACT_CANONICAL_MATCH": 0.15,
    "FUZZY_CANONICAL_MATCH": 0.10,
    "PROPERTY_TABLE_MATCH": 0.12,
    "SCIENTIFIC_PATTERN_MATCH": 0.08,
    "UNIT_VALIDATION_PASS": 0.06,
    "CONTEXT_COHERENCE": 0.05,
    "CROSS_REFERENCE_VALIDATION": 0.07,
    "DOMAIN_EXPERTISE_MATCH": 0.04
}

# Advanced ensemble strategies configuration
ENSEMBLE_STRATEGIES = {
    EnsembleStrategy.WEIGHTED_CONFIDENCE: {
        "description": "Weight votes by model confidence and expertise",
        "parameters": {
            "confidence_power": 1.5,
            "expertise_weight": 1.2,
            "min_models_required": 2
        }
    },

    EnsembleStrategy.EXPERT_CONSENSUS: {
        "description": "Defer to expert models for their specializations",
        "parameters": {
            "expertise_threshold": 1.5,
            "consensus_requirement": 0.7,
            "fallback_strategy": "weighted_confidence"
        }
    },

    EnsembleStrategy.DYNAMIC_THRESHOLD: {
        "description": "Adapt thresholds based on context and agreement",
        "parameters": {
            "adaptation_rate": 0.1,
            "context_sensitivity": 1.0,
            "agreement_sensitivity": 1.2
        }
    },

    EnsembleStrategy.SEMANTIC_AWARE: {
        "description": "Consider semantic relationships between entities",
        "parameters": {
            "relationship_weight": 0.3,
            "coherence_bonus": 0.05,
            "conflict_penalty": -0.08
        }
    },

    EnsembleStrategy.ADAPTIVE_VOTING: {
        "description": "Combine multiple strategies based on performance",
        "parameters": {
            "strategy_weights": {
                "weighted_confidence": 0.4,
                "expert_consensus": 0.3,
                "semantic_aware": 0.3
            },
            "adaptation_window": 100,
            "performance_threshold": 0.85
        }
    }
}

# Processing and validation configurations
PROCESSING_CONFIG = {
    "PROXIMITY_WINDOW": 128,
    "MAX_SEQUENCE_LENGTH": 512,
    "MIN_ENTITY_LENGTH": 2,
    "MAX_ENTITY_GAPS": 3,
    "CONTEXT_WINDOW_SIZE": 64,
    "DUPLICATE_SIMILARITY_THRESHOLD": 0.9,
    "RELATIONSHIP_DETECTION_WINDOW": 64,
    "COHERENCE_CHECK_WINDOW": 32
}

POST_PROCESSING_CONFIG = {
    # start with confidence thresholds
    "CONFIDENCE_THRESHOLDS": {
        "POLYMER": 0.82,
        "MATERIAL": 0.80,
        "PROPERTY": 0.75,
        "VALUE": 0.72,
        "UNIT": 0.72,
        "SYMBOL": 0.70,
        "GLOBAL": 0.75
    },
    "ENTITY_MERGE_THRESHOLD": 0.85,  # Similarity threshold for merging entities
    "ENTITY_SPLIT_THRESHOLD": 0.7,   # Threshold for splitting entities
    "ENTITY_VALIDATION_STRATEGIES": [
        "EXACT_CANONICAL_MATCH",
        "FUZZY_CANONICAL_MATCH",
        "PROPERTY_TABLE_MATCH",
        "SCIENTIFIC_PATTERN_MATCH",
        "UNIT_VALIDATION_PASS",
        "CONTEXT_COHERENCE",
        "CROSS_REFERENCE_VALIDATION",
        "DOMAIN_EXPERTISE_MATCH"
    ],
}

# Performance tracking configuration
PERFORMANCE_TRACKING = {
    "METRICS": [
        "precision", "recall", "f1_score", "accuracy",
        "confidence_calibration", "agreement_rate"
    ],
    "TRACKING_WINDOW": 1000,  # Number of recent predictions to track
    "UPDATE_FREQUENCY": 50,   # Update model weights every N predictions
    "PERFORMANCE_DECAY": 0.95,  # Decay factor for older performance data
    "MIN_SAMPLES_FOR_UPDATE": 20  # Minimum samples before updating weights
}

# Entity relationship patterns for semantic awareness
ENTITY_RELATIONSHIP_PATTERNS = {
    "VALUE_UNIT_PAIRS": {
        "distance_threshold": 5,  # tokens
        "confidence_boost": 0.1,
        "required_confidence": 0.6
    },
    "PROPERTY_VALUE_RELATIONSHIPS": {
        "distance_threshold": 10,
        "confidence_boost": 0.08,
        "required_confidence": 0.65
    },
    "POLYMER_PROPERTY_ASSOCIATIONS": {
        "distance_threshold": 20,
        "confidence_boost": 0.06,
        "required_confidence": 0.7
    },
    "MATERIAL_CONTEXT_COHERENCE": {
        "distance_threshold": 50,
        "confidence_boost": 0.04,
        "required_confidence": 0.75
    }
}

# Model-specific error patterns and corrections
MODEL_ERROR_PATTERNS = {
    "PolymerNER": {
        "common_errors": ["over_segmentation_polymer_names", "unit_confusion"],
        "correction_strategies": ["merge_polymer_segments", "unit_validation"]
    },
    "MatSciBERT": {
        "common_errors": ["material_property_confusion", "symbol_misclassification"],
        "correction_strategies": ["context_disambiguation", "symbol_validation"]
    },
    "SciBERT": {
        "common_errors": ["generic_entity_over_prediction", "boundary_errors"],
        "correction_strategies": ["specificity_filtering", "boundary_refinement"]
    },
    "PhysBERT": {
        "common_errors": ["polymer_under_prediction", "unit_over_prediction"],
        "correction_strategies": ["polymer_context_boost", "unit_filtering"]
    },
    "BioBERT": {
        "common_errors": ["biomedical_bias", "low_confidence_predictions"],
        "correction_strategies": ["domain_adaptation", "confidence_calibration"]
    }
}

# Export configuration for easy access
def get_model_by_name(name: str) -> Optional[EnsembleModel]:
    """Get model configuration by name."""
    for model in ENSEMBLE_MODELS:
        if model.name == name:
            return model
    return None

def get_entity_threshold(entity_type: str, context_indicators: List[str] = None,
                        ensemble_agreement: str = "simple_majority",
                        model_confidences: List[float] = None) -> float:
    """Get dynamic threshold for entity type."""
    return DynamicThresholds.calculate_threshold(
        entity_type, context_indicators or [], ensemble_agreement, model_confidences or []
    )

def get_validation_boost(validation_type: str) -> float:
    """Get confidence boost for validation type."""
    return VALIDATION_CONFIDENCE_ADJUSTMENTS.get(validation_type, 0.0)

def get_ensemble_strategy_config(strategy: EnsembleStrategy) -> Dict[str, Any]:
    """Get configuration for ensemble strategy."""
    return ENSEMBLE_STRATEGIES.get(strategy, ENSEMBLE_STRATEGIES[EnsembleStrategy.WEIGHTED_CONFIDENCE])

# Backward compatibility with existing code
HYPERPARAMETERS = {
    model.name: model.training_config for model in ENSEMBLE_MODELS
}

ENTITY_CONFIDENCE_THRESHOLDS = DynamicThresholds.BASE_THRESHOLDS.copy()