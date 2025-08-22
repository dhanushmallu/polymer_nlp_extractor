# Training-specific constants for model fine-tuning and configuration
# Phase 0B Enhanced Constants

from typing import Dict, Set, Any

# Scientific stopwords for enhanced tokenization
SCIENTIFIC_STOPWORDS: Dict[str, Set[str]] = {
    # Common scientific connectors that should be preserved
    "scientific_preserve": {
        "nm", "μm", "mm", "cm", "m", "kg", "g", "mg", "μg", "°C", "K", 
        "MPa", "GPa", "Pa", "Hz", "kHz", "MHz", "GHz", "eV", "keV", "MeV",
        "mol", "mM", "μM", "nM", "pM", "wt%", "v/v", "w/w", "rpm", "ppm",
        "THz", "GW", "MW", "kW", "mW", "μW", "nW", "pW", "J", "kJ", "mJ",
        "V", "mV", "μV", "A", "mA", "μA", "nA", "Ω", "kΩ", "MΩ", "F", "μF",
        "pF", "nF", "H", "mH", "μH", "T", "mT", "μT", "G", "mG", "Wb", "lm",
        "cd", "lx", "Bq", "Gy", "Sv", "kat", "mol/L", "M", "N", "dyne", "bar"
    },
    
    # General stopwords to handle carefully during tokenization
    "general_stopwords": {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", 
        "for", "of", "with", "by", "from", "up", "about", "into", "through", 
        "during", "before", "after", "above", "below", "between", "among",
        "while", "although", "though", "since", "because", "if", "unless",
        "until", "whether", "either", "neither", "both", "all", "any", "some",
        "many", "few", "several", "each", "every", "most", "more", "less"
    },
    
    # Scientific transition words to preserve context
    "scientific_transitions": {
        "where", "when", "which", "that", "this", "these", "those",
        "such", "due", "owing", "resulting", "leading", "causing",
        "indicating", "showing", "demonstrating", "revealing", "suggesting",
        "implying", "confirming", "establishing", "proving", "evidencing",
        "corresponding", "related", "associated", "linked", "connected",
        "attributed", "assigned", "designated", "characterized", "defined"
    },
    
    # Scientific measurement contexts
    "measurement_contexts": {
        "measured", "observed", "detected", "recorded", "monitored",
        "determined", "calculated", "estimated", "evaluated", "assessed",
        "analyzed", "quantified", "characterized", "identified", "found",
        "obtained", "achieved", "reached", "exhibited", "displayed",
        "demonstrated", "showed", "indicated", "revealed", "suggested"
    }
}

# Enhanced confidence thresholds per entity type (Phase 0B)
ENHANCED_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "POLYMER": {
        "base_threshold": 0.7,
        "high_confidence": 0.85,
        "low_confidence": 0.6,
        "semantic_boost": 0.1,  # Boost for semantically coherent contexts
        "context_boost": 0.05,  # Additional boost for strong context
        "min_length": 3,        # Minimum character length for polymer names
        "max_length": 100       # Maximum character length for polymer names
    },
    "PROPERTY": {
        "base_threshold": 0.75,
        "high_confidence": 0.9,
        "low_confidence": 0.65,
        "semantic_boost": 0.15,
        "context_boost": 0.08,
        "min_length": 3,
        "max_length": 80
    },
    "VALUE": {
        "base_threshold": 0.8,
        "high_confidence": 0.95,
        "low_confidence": 0.7,
        "semantic_boost": 0.2,   # Higher boost for numerical values
        "context_boost": 0.1,
        "min_length": 1,
        "max_length": 20,
        "number_boost": 0.15     # Additional boost for clear numerical patterns
    },
    "UNIT": {
        "base_threshold": 0.85,
        "high_confidence": 0.95,
        "low_confidence": 0.75,
        "semantic_boost": 0.25,  # Highest boost for scientific units
        "context_boost": 0.15,
        "min_length": 1,
        "max_length": 15,
        "scientific_unit_boost": 0.2  # Extra boost for known scientific units
    },
    "SYMBOL": {
        "base_threshold": 0.8,
        "high_confidence": 0.9,
        "low_confidence": 0.7,
        "semantic_boost": 0.15,
        "context_boost": 0.1,
        "min_length": 1,
        "max_length": 10,
        "greek_letter_boost": 0.1  # Boost for Greek letters
    }
}

# Advanced tokenization patterns for Phase 0B
TOKENIZATION_PATTERNS: Dict[str, str] = {
    # Scientific notation patterns
    "scientific_notation": r"[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?",
    "scientific_range": r"[-+]?[0-9]*\.?[0-9]+\s*[-–—~]\s*[-+]?[0-9]*\.?[0-9]+",
    "percentage": r"[0-9]*\.?[0-9]+\s*%",
    "temperature": r"[-+]?[0-9]*\.?[0-9]+\s*°?[CFK]",
    "pressure": r"[0-9]*\.?[0-9]+\s*(Pa|MPa|GPa|bar|atm|psi)",
    "molecular_weight": r"[0-9]*\.?[0-9]+\s*(g/mol|kg/mol|Da|kDa|MDa)",
    "concentration": r"[0-9]*\.?[0-9]+\s*(M|mM|μM|nM|pM|mol/L|g/L|mg/mL)",
    "frequency": r"[0-9]*\.?[0-9]+\s*(Hz|kHz|MHz|GHz|THz)",
    "voltage": r"[0-9]*\.?[0-9]+\s*(V|mV|μV|kV)",
    "current": r"[0-9]*\.?[0-9]+\s*(A|mA|μA|nA|pA)",
    "time": r"[0-9]*\.?[0-9]+\s*(s|ms|μs|ns|ps|min|h|hr)",
    "length": r"[0-9]*\.?[0-9]+\s*(m|mm|μm|nm|pm|km|cm)",
    "area": r"[0-9]*\.?[0-9]+\s*(m²|mm²|cm²|μm²|nm²)",
    "volume": r"[0-9]*\.?[0-9]+\s*(m³|L|mL|μL|nL|pL)",
    "mass": r"[0-9]*\.?[0-9]+\s*(kg|g|mg|μg|ng|pg)",
    "angle": r"[0-9]*\.?[0-9]+\s*(°|deg|rad|mrad)",
    "energy": r"[0-9]*\.?[0-9]+\s*(J|kJ|mJ|eV|keV|MeV|GeV|cal|kcal)"
}

# Enhanced semantic coherence patterns
SEMANTIC_COHERENCE_PATTERNS: Dict[str, Dict[str, Any]] = {
    "value_unit_pairs": {
        "temperature": ["°C", "K", "°F", "C", "F"],
        "pressure": ["Pa", "MPa", "GPa", "bar", "atm", "psi", "torr", "mmHg"],
        "molecular_weight": ["g/mol", "kg/mol", "Da", "kDa", "MDa"],
        "time": ["s", "ms", "μs", "ns", "ps", "min", "h", "hr", "d"],
        "length": ["m", "mm", "μm", "nm", "pm", "km", "cm", "in", "ft"],
        "mass": ["kg", "g", "mg", "μg", "ng", "pg", "lb", "oz"],
        "frequency": ["Hz", "kHz", "MHz", "GHz", "THz"],
        "voltage": ["V", "mV", "μV", "kV", "MV"],
        "current": ["A", "mA", "μA", "nA", "pA", "kA"],
        "energy": ["J", "kJ", "mJ", "eV", "keV", "MeV", "GeV", "cal", "kcal"],
        "concentration": ["M", "mM", "μM", "nM", "pM", "mol/L", "g/L", "mg/mL"],
        "percentage": ["%", "percent", "wt%", "vol%", "at%"],
        "ratio": ["ratio", "fraction", "proportion", "/", ":"]
    },
    
    "property_value_contexts": {
        "thermal": ["temperature", "melting", "glass transition", "decomposition", "crystallization"],
        "mechanical": ["modulus", "strength", "strain", "stress", "hardness", "toughness"],
        "electrical": ["conductivity", "resistivity", "permittivity", "voltage", "current"],
        "optical": ["transparency", "refractive index", "absorbance", "transmittance"],
        "chemical": ["concentration", "purity", "pH", "molecular weight", "viscosity"],
        "dimensional": ["thickness", "diameter", "length", "width", "height", "area", "volume"]
    },
    
    "polymer_property_associations": {
        "thermoplastic": ["melting point", "glass transition", "melt flow index"],
        "thermoset": ["curing temperature", "crosslink density", "gel time"],
        "elastomer": ["elongation", "modulus", "tear strength", "compression set"],
        "fiber": ["tensile strength", "modulus", "elongation", "denier"],
        "film": ["thickness", "transparency", "barrier properties", "tear strength"],
        "foam": ["density", "compression strength", "thermal conductivity"]
    }
}

# Over-merging prevention criteria (Phase 0B)
OVER_MERGING_PREVENTION: Dict[str, Any] = {
    "max_entity_length": 50,  # Maximum characters for any single entity
    "max_word_count": 8,      # Maximum words in a single entity
    "forbidden_combinations": [
        # Prevent merging across sentence boundaries
        [".", "POLYMER"], [".", "PROPERTY"], [".", "VALUE"], [".", "UNIT"],
        # Prevent merging unrelated concepts
        ["POLYMER", "and", "POLYMER"],  # Two different polymers
        ["VALUE", "to", "VALUE"],       # Range of values (should be separate)
        ["PROPERTY", "of", "PROPERTY"], # Different properties
    ],
    "separation_indicators": [
        "and", "or", "but", "however", "while", "whereas", "although",
        "respectively", "separately", "individually", "distinctly",
        ",", ";", ":", "-", "–", "—", "/", "\\", "|"
    ],
    "semantic_boundaries": [
        "temperature", "pressure", "time", "concentration", "pH",
        "voltage", "current", "frequency", "wavelength", "intensity"
    ]
}

# Enhanced sentence splitting improvements (Phase 0B)
SENTENCE_SPLITTING_ENHANCEMENTS: Dict[str, Any] = {
    "abbreviation_exceptions": [
        # Common scientific abbreviations that shouldn't trigger sentence splits
        "et al.", "e.g.", "i.e.", "vs.", "cf.", "viz.", "ca.", "approx.",
        "Fig.", "Figs.", "Tab.", "Tabs.", "Eq.", "Eqs.", "Ref.", "Refs.",
        "Vol.", "No.", "pp.", "p.", "min.", "max.", "avg.", "std.", "dev.",
        "wt.", "vol.", "mol.", "temp.", "conc.", "diam.", "thick.", "dens.",
        "TGA", "DSC", "GPC", "NMR", "IR", "UV", "XRD", "SEM", "TEM",
        "FTIR", "HPLC", "GC", "MS", "LC", "PVC", "PE", "PP", "PS", "PET"
    ],
    
    "measurement_patterns": [
        # Patterns that indicate measurements and shouldn't be split
        r"\d+\.?\d*\s*[°]?[CFK]",      # Temperature
        r"\d+\.?\d*\s*(MPa|GPa|Pa)",    # Pressure/Modulus
        r"\d+\.?\d*\s*(g/mol|kg/mol)",  # Molecular weight
        r"\d+\.?\d*\s*[%]",             # Percentage
        r"\d+\.?\d*\s*(Hz|kHz|MHz)",    # Frequency
        r"\d+\.?\d*\s*(V|mV|μV)",       # Voltage
        r"\d+\.?\d*\s*(A|mA|μA)",       # Current
        r"\d+\.?\d*\s*(m|mm|μm|nm)",    # Length
        r"\d+\.?\d*\s*(s|ms|μs|min|h)", # Time
    ],
    
    "special_characters": {
        # Characters that require special handling
        "greek_letters": ["α", "β", "γ", "δ", "ε", "ζ", "η", "θ", "ι", "κ", "λ", "μ", "ν", "ξ", "ο", "π", "ρ", "σ", "τ", "υ", "φ", "χ", "ψ", "ω"],
        "mathematical": ["±", "≈", "≤", "≥", "≠", "∞", "∑", "∏", "∫", "∂", "∇", "×", "·", "°", "′", "″"],
        "chemical": ["→", "←", "↔", "⇌", "↑", "↓", "⊕", "⊖", "⊗", "⊘"],
        "subscripts": ["₀", "₁", "₂", "₃", "₄", "₅", "₆", "₇", "₈", "₉", "ₐ", "ₑ", "ₒ", "ₓ", "ₙ"],
        "superscripts": ["⁰", "¹", "²", "³", "⁴", "⁵", "⁶", "⁷", "⁸", "⁹", "⁺", "⁻", "⁼", "⁽", "⁾"]
    },
    
    "context_preservation": {
        # Contexts that should be preserved during sentence splitting
        "chemical_formulas": r"[A-Z][a-z]?[₀-₉]*([A-Z][a-z]?[₀-₉]*)*",
        "polymer_names": r"poly\([^)]+\)|P[A-Z]{2,}|[A-Z]{2,}[0-9]*",
        "scientific_names": r"[A-Z][a-z]+-[A-Z][a-z]+|[A-Z][a-z]+\s+[a-z]+",
        "measurements": r"\d+\.?\d*\s*[a-zA-Zμ°]+",
        "ranges": r"\d+\.?\d*\s*[-–—~]\s*\d+\.?\d*",
        "equations": r"[A-Za-z]+\s*=\s*[^.]+",
        "citations": r"\[[0-9,\s-]+\]|\([^)]*[0-9]{4}[^)]*\)"
    }
}

# Model training configuration constants
MODEL_TRAINING_CONFIG: Dict[str, Any] = {
    # Base training parameters
    "default_learning_rate": 2e-5,
    "default_batch_size": 8,
    "default_eval_batch_size": 8,
    "default_epochs": 5,
    "default_weight_decay": 0.01,
    "default_gradient_accumulation_steps": 4,
    
    # Dynamic adjustments based on dataset size
    "dataset_size_adjustments": {
        "large_dataset_threshold": 50000,
        "small_dataset_threshold": 10000,
        "large_dataset_lr_factor": 0.8,    # Reduce LR for large datasets
        "small_dataset_lr_factor": 1.2,    # Increase LR for small datasets
    },
    
    # Early stopping configuration
    "early_stopping": {
        "patience": 3,
        "threshold": 0.001,
        "metric": "eval_loss",
        "mode": "min"
    },
    
    # Model saving configuration
    "model_saving": {
        "save_total_limit": 3,
        "save_strategy": "epoch",
        "eval_strategy": "epoch",
        "load_best_model_at_end": True,
        "metric_for_best_model": "eval_loss",
        "greater_is_better": False
    },
    
    # Hardware optimization
    "hardware_optimization": {
        "fp16": True,  # Enable if CUDA available
        "dataloader_pin_memory": False,
        "dataloader_num_workers": 2,
        "remove_unused_columns": False
    },
    
    # Advanced training features
    "advanced_features": {
        "warmup_ratio": 0.1,
        "lr_scheduler_type": "cosine",
        "label_smoothing_factor": 0.1,
        "logging_steps": 50,
        "logging_first_step": True
    }
}

# GitHub integration constants
GITHUB_INTEGRATION_CONFIG: Dict[str, Any] = {
    "release_name_template": "Enhanced Models v{version} (Phase 0B)",
    "release_notes_template": """# Enhanced Model Release v{version} (Phase 0B)

## 🚀 Enhanced Features
- ✅ MATERIAL entity removal (Phase 0 compliance)
- ✅ Extended vocabulary for scientific terminology  
- ✅ Enhanced tokenization handling
- ✅ Paired model-tokenizer creation
- ✅ Improved training pipeline

## 📦 Models Included
{model_list}

## 🔧 Installation
Download the model packages and use with transformers:

```python
from transformers import AutoModelForTokenClassification, AutoTokenizer

# Extract downloaded package first
# tar -xzf model_name_enhanced_v{version}.tar.gz

# Load model and tokenizer (must be used together)
model = AutoModelForTokenClassification.from_pretrained('./model_name_enhanced_v{version}/model')
tokenizer = AutoTokenizer.from_pretrained('./model_name_enhanced_v{version}/tokenizer')
```

## 📋 Requirements
- transformers >= 4.21.0
- torch >= 1.12.0  
- python >= 3.8

Generated by polymer_nlp_extractor (Phase 0B Enhanced Pipeline)
""",
    
    "package_components": {
        "model": "PyTorch model files",
        "tokenizer": "Enhanced tokenizer with extended vocabulary",
        "metadata": "Training and configuration metadata",
        "readme": "Installation and usage instructions"
    },
    
    "compatibility_requirements": {
        "transformers_version": ">=4.21.0",
        "torch_version": ">=1.12.0",
        "python_version": ">=3.8"
    }
}

# Export all constants for easy importing
__all__ = [
    "SCIENTIFIC_STOPWORDS",
    "ENHANCED_THRESHOLDS", 
    "TOKENIZATION_PATTERNS",
    "SEMANTIC_COHERENCE_PATTERNS",
    "OVER_MERGING_PREVENTION",
    "SENTENCE_SPLITTING_ENHANCEMENTS",
    "MODEL_TRAINING_CONFIG",
    "GITHUB_INTEGRATION_CONFIG"
]
