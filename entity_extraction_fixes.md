# Entity Label Extraction Issues - Analysis and Resolution

## Issues Identified

Based on the analysis of system logs, ensemble results, and code review, several critical issues were identified that were causing poor entity label extraction:

### 1. **Entity Boundary Detection Problems**
- **Issue**: The ensemble results showed fragmented entities like "Epo", "EVO)-ba", "CANs). T" instead of complete meaningful entities like "Epoxidized vegetable oil (EVO)-based epoxy systems"
- **Root Cause**: The token-level predictions were not being properly aggregated into complete entity spans. Only individual BIO tokens were being extracted without considering full entity boundaries.
- **Fix Applied**: Enhanced the prediction processing in `EnsembleInferenceService._infer_model()` to:
  - Expand B- tags to include their full I- tag sequences
  - Validate entity text quality (minimum 2 characters, contains alphanumeric)
  - Proper text extraction from token offset mappings

### 2. **Overly Strict Confidence Thresholds**
- **Issue**: Base confidence thresholds were too high (0.70-0.82), causing many valid entities to be rejected
- **Root Cause**: Conservative thresholds in `DynamicThresholds.BASE_THRESHOLDS`
- **Fix Applied**: Reduced thresholds to more reasonable levels:
  - POLYMER: 0.82 → 0.65
  - MATERIAL: 0.80 → 0.62  
  - PROPERTY: 0.75 → 0.60
  - VALUE: 0.72 → 0.58
  - UNIT: 0.72 → 0.58
  - SYMBOL: 0.70 → 0.55
  - GLOBAL: 0.75 → 0.60

### 3. **Strict Ensemble Voting Criteria**
- **Issue**: Ensemble voting required too strong consensus and too many model votes
- **Root Cause**: `has_consensus = consensus_ratio <= 0.5` and `min_votes = 2` were too restrictive
- **Fix Applied**: Made voting more lenient:
  - Consensus ratio: 0.5 → 0.7 (allows more text variation)
  - Minimum votes: 2 → 1 (single model can contribute valid entities)

### 4. **Poor Text Cleaning for Scientific Terms**
- **Issue**: The `_clean_span()` function was over-aggressive in removing content, including scientific notation and compound names
- **Root Cause**: Generic text cleaning not suited for scientific terminology
- **Fix Applied**: Enhanced cleaning logic to:
  - Preserve scientific notation and parentheses
  - Maintain hyphenated compounds
  - Only remove suffixes when they're clearly linguistic, not scientific
  - Better handling of internal stopwords in scientific names

### 5. **Inadequate Entity Clustering**
- **Issue**: Overlapping predictions weren't being properly merged
- **Root Cause**: Simple overlap detection didn't handle adjacent or nearly-adjacent predictions
- **Fix Applied**: Improved clustering to:
  - Handle adjacency within 3 characters
  - Consider span lengths when sorting (prefer longer spans)
  - Update cluster boundaries dynamically

### 6. **Aggressive Sentence Splitting**
- **Issue**: Token packing was creating too many sentence fragments, breaking entity contexts
- **Root Cause**: Overly aggressive regex-based splitting
- **Fix Applied**: More conservative sentence splitting:
  - Only split at strong boundaries (semicolons, major conjunctions)
  - Preserve entity contexts by avoiding comma-based splits
  - Filter out very short fragments (< 20 characters)

## Expected Improvements

After these fixes, the ensemble results should show:

1. **Complete Entity Extraction**: Instead of "Epo", "EVO)-ba", expect "Epoxidized vegetable oil (EVO)-based epoxy systems"
2. **Higher Entity Recall**: More valid entities should pass the threshold tests
3. **Better Text Quality**: Cleaner, more meaningful entity text
4. **Improved Entity Boundaries**: Proper start/end positions for entities
5. **Reduced Fragmentation**: Fewer partial or broken entity mentions

## Validation Steps

The fixes target the core issues identified in the analysis:
- System logs showed tokenizer extension working (2837 tokens added to PolymerNER)
- Current ensemble results showed fragmented entities with poor boundaries
- Code review revealed overly strict thresholds and inadequate boundary detection

These changes should significantly improve entity extraction quality while maintaining precision through the ensemble voting mechanism.
