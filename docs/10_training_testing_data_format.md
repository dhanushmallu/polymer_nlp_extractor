# 10: Training and Testing Data Format Specification

## Overview

This document provides the official specification for training and testing data formats used in the Polymer NLP Extractor project. This format is designed to maximize compatibility with the ensemble learning system and ensure consistent, high-quality model training.

## Dataset Structure Requirements

### File Organization

Each training/testing dataset must contain exactly two files:

```
dataset_name/
├── metadata.json          # Paper metadata and provenance information
└── data.csv              # Entity-labeled sentences for training/testing
```

### metadata.json Structure

```json
{
    "title": "Complete research paper title",
    "authors": ["Author One", "Author Two", "Author Three"],
    "abstract": "Full abstract text of the research paper",
    "doi": "10.1000/journal.doi.identifier",
    "publication_date": "2024-01-15",
    "journal_name": "Full Journal Name",
    "dataset_type": "training",
    "extraction_date": "2024-08-22",
    "extractor": "AI-assisted" 
}
```

### data.csv Structure

The CSV file must contain the following columns:

```csv
sentence,polymer,property,symbol,value,unit
```

**Column Specifications:**

- **sentence**: Complete sentence text being analyzed
- **polymer**: Polymer entities found in the sentence
- **property**: Material property entities found in the sentence  
- **symbol**: Scientific symbols, formulae, or notation found in the sentence
- **value**: Numerical values and measurements found in the sentence
- **unit**: Units of measurement found in the sentence

## Data Format Rules

### Value Column Requirements

**CRITICAL**: The `value` column must contain ONLY numerical representations.

**Non-Negotiable Rule**: If both numerical and word forms exist in a sentence, ALWAYS use the numerical form and discard the word form.

**Examples**:
- Sentence contains "thirty MPa" and "30 MPa" → Extract ONLY "30", discard "thirty"
- Sentence contains "twenty-five degrees" and "25°C" → Extract ONLY "25", discard "twenty-five"
- Sentence contains only "thirty MPa" → Extract "30" (convert to numerical)
- Sentence contains ranges: "20-30 MPa" → Extract "20-30"

### Label Encoding Format

**All entity labels must be enclosed in quotes** (single or double quotes acceptable).

**Multiple Entity Formats** (all valid):

#### JSON Object Format:
```csv
sentence,polymer,property,symbol,value,unit
"The PMMA and PS showed tensile strength of 65 MPa.","{"polymer_1": "PMMA", "polymer_2": "PS"}","{"property_1": "tensile strength"}","","{"value_1": "65"}","{"unit_1": "MPa"}"
```

#### Simple Quoted Format:
```csv
sentence,polymer,property,symbol,value,unit
"PMMA showed excellent properties.","PMMA","tensile strength","","65","MPa"
```

#### Mixed Numbering Systems (all acceptable):
```csv
# Numerical indexing
"{"polymer_1": "PMMA", "polymer_2": "PS", "polymer_3": "PLA"}"

# Alphabetical indexing  
"{"polymer_a": "PMMA", "polymer_b": "PS", "polymer_c": "PLA"}"

# Roman numeral indexing
"{"polymer_i": "PMMA", "polymer_ii": "PS", "polymer_iii": "PLA"}"

# Mixed indexing (valid but not recommended)
"{"polymer_1": "PMMA", "polymer_b": "PS", "polymer_iii": "PLA"}"
```

## Example Dataset

### Example: Multi-Entity Sentence

```csv
sentence,polymer,property,symbol,value,unit
"The poly(methyl methacrylate) (PMMA) and polystyrene exhibited tensile strength (σ) of 65 MPa and glass transition temperature (Tg) of 105°C respectively.","{"polymer_1": "poly(methyl methacrylate)", "polymer_2": "PMMA", "polymer_3": "polystyrene"}","{"property_1": "tensile strength", "property_2": "glass transition temperature"}","{"symbol_1": "σ", "symbol_2": "Tg"}","{"value_1": "65", "value_2": "105"}","{"unit_1": "MPa", "unit_2": "°C"}"
```

### Example: Single Entity Sentence

```csv
sentence,polymer,property,symbol,value,unit
"PMMA showed excellent tensile strength.","PMMA","tensile strength","","",""
```

### Example: Mixed Format Handling

```csv
sentence,polymer,property,symbol,value,unit
"The polymer showed twenty-five MPa strength and 105°C transition.","polymer","{"property_1": "strength", "property_2": "transition"}","","{"value_1": "25", "value_2": "105"}","{"unit_1": "MPa", "unit_2": "°C"}"
```

## Data Quality Requirements

### Mandatory Quote Enclosure

Every non-empty cell must be enclosed in quotes:

```csv
# CORRECT:
"sentence text","PMMA","tensile strength","σ","65","MPa"

# INCORRECT:  
sentence text,PMMA,tensile strength,σ,65,MPa
```

### Empty Cell Handling

Empty cells should contain empty quoted strings:

```csv
# CORRECT:
"The PMMA polymer was tested.","PMMA","","","",""

# INCORRECT:
"The PMMA polymer was tested.","PMMA",,,,
```

### Case Sensitivity

Case sensitivity does not matter for any column, but consistency within a dataset is recommended:

```csv
# All acceptable:
"PMMA"
"pmma"  
"Pmma"
```

## Validation Rules

### Pre-Processing Validation

1. **Numerical Value Check**: Scan `value` column for word forms of numbers
2. **Quote Enclosure Check**: Verify all non-empty cells are quoted
3. **JSON Format Check**: Validate JSON objects in multi-entity cells
4. **Empty Cell Check**: Ensure empty cells use `""` format

### Quality Assurance

1. **Sentence-Entity Alignment**: Verify extracted entities actually appear in sentence text
2. **Numerical Consistency**: Confirm values match numerical forms in sentence
3. **Unit-Value Pairing**: Check that units logically correspond to values
4. **Property-Value Relationship**: Validate semantic relationships between properties and values

## Implementation Notes

### Current System Compatibility

The evaluation service in `evaluation_service.py` expects this format and handles:
- Fuzzy matching for entity text variations
- JSON object parsing for multi-entity labels
- Case-insensitive comparisons
- Quote-enclosed string processing

### Future Optimizations

This format provides a solid foundation and may be enhanced with:
- Standardized indexing systems (numerical preferred for consistency)
- Optional confidence scores for extracted entities
- Character-level position information for advanced tokenization
- Support for hierarchical entity relationships and nested structures

## Processing Guidelines

### AI-Assisted Extraction

When using AI for data extraction, provide this format specification along with the comprehensive prompt from Document 9 to ensure consistency and compatibility with the ensemble learning system.

### Manual Annotation

For manual annotation, use this format as the target structure, ensuring all rules are followed for maximum compatibility with the training pipeline and model configuration requirements.

### Batch Processing

When processing multiple papers, maintain consistent formatting across all datasets while allowing for natural variation in entity types and quantities per sentence.

---

**Note**: This specification is designed for production use with the Polymer NLP Extractor's ensemble learning system. Updates will be versioned and documented to maintain backward compatibility.
