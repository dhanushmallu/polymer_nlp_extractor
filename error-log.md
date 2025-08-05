Based on a full review of the *prior error log*, here is a **consolidated and extended master error register**, integrating all distinct, complementary, and preemptively useful observations from both logs.

This final version includes:

* ❌ All confirmed errors from current comparison logs
* ➕ Additional *preemptive red flags* and structural issues from the archived notes that did **not yet** show in the current output but **must be guarded against**
* No truncation or summarization — full clarity is retained
* No analysis, solutions, or root causes included — strictly error-level diagnostics

---

# MASTER ERROR REGISTER — ENSEMBLE OUTPUT PATHOLOGIES

**Primary Source Files**

* **Expected:** `sample_expected_result_from_model.json`
* **Actual:** `sample_of_what_the model_currently_produces.057.tei_cleaned.tei_enseble_results.json`
* **Archived Diagnostic Supplement:** `057.tei_cleaned.tei_ensemble_results.json` vs `057.expected_excerpt_results.json`

---

### 1. **Missing or Corrupted Sentence Anchors**

| Type                             | Description                                                                                    | Example                                                                          |
| -------------------------------- | ---------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| ❌ Missing Sentence Content       | `sentence` field is empty (`""`), and `sentences` array is empty (`[]`) in all output entries. | `"sentence": ""`                                                                 |
| ❌ No Sentence Alignment Metadata | `sentence_id` or other window trace fields not preserved.                                      | No way to trace entity to a sentence or paragraph window.                        |
| ➕ Mislinked Token-Text Reuse     | Same sentence fragments reused across unrelated spans or models.                               | `"epoxy"` appears in different contexts but is bound to a generic sentence stub. |

---

### 2. **Malformed or Canonical-Like Window IDs**

| Type                       | Description                                                                                          | Example                            |
| -------------------------- | ---------------------------------------------------------------------------------------------------- | ---------------------------------- |
| ❌ Synthetic Window IDs     | Output uses sequential IDs like `ensemble_win_000X` rather than preserving original `model_win_00X`. | `"window_id": "ensemble_win_0002"` |
| ❌ Loss of Model Provenance | No trace of which model generated the original window.                                               | All traceability lost per entity   |

---

### 3. **Severe Token Fragmentation and Mid-Word Breaks**

| Type                      | Description                                                                                        | Example                     |
| ------------------------- | -------------------------------------------------------------------------------------------------- | --------------------------- |
| ❌ Hard Truncation         | Tokens such as `"epo"`, `"pec"`, `"geta"` appear in isolation without meaningful boundaries.       | `"oxi"`, `"curi"`, `"iza"`  |
| ❌ Midword Cuts            | Entities such as `"epoxidized"` or `"transition"` are not reconstructed, only partial forms exist. | `"Epo"`, `"oxi"`, `"sitio"` |
| ❌ Single-Character Tokens | Repeated entity detections with single letters or punctuation.                                     | `"T"`, `"A"`, `"I"`, `"R"`  |
| ➕ Unsafe Hyphenation      | Breakpoints like `"(EVO)-based"` incorrectly split into `"EVO)-ba"` and `"sed"`.                   | `"EVO)-ba"`                 |

---

### 4. **Overgeneration of Noisy Spans**

| Type                        | Description                                                                             | Example                            |
| --------------------------- | --------------------------------------------------------------------------------------- | ---------------------------------- |
| ❌ Non-word or Broken Tokens | Detections such as `"irep"`, `"eva"`, `"reac"` that do not exist as valid words.        | `"eva"`, `"pec"`                   |
| ❌ Acronym Flooding          | Technical abbreviations misclassified due to absence of semantic filter.                | `"TG"`, `"DMA"`, `"DTG"`, `"FTIR"` |
| ❌ Caption/Legend Pollution  | Non-content labels (e.g., `"Figure"`, `"Table"`, `"Fig. A"`) misclassified as entities. | `"Fig. G"`, `"Table D"`            |

---

### 5. **Redundant or Conflicting Entities**

| Type                           | Description                                                                                  | Example                                            |
| ------------------------------ | -------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| ❌ Duplicates Within Windows    | Same span appears more than once with minimal offset changes.                                | `"CAN"` detected twice in same window.             |
| ❌ Slot Collisions              | Same span appears under different entity types.                                              | `"T"` labeled as both `SYMBOL` and `PROPERTY`.     |
| ❌ Overlapping Near-Duplicates  | Nearly identical text fragments with shifted boundaries all labeled as separate entities.    | `"EVO"` and `"EVO)-ba"` both labeled as `POLYMER`. |
| ➕ Slot Spillage in Entity Dict | Invalid combinations where one type's tokens are misaligned into another's dictionary entry. | `"glass"` in `POLYMER`, `"oil"` in `MATERIAL`.     |

---

### 6. **Broken or Incorrect Span Alignment**

| Type                       | Description                                                               | Example                                            |
| -------------------------- | ------------------------------------------------------------------------- | -------------------------------------------------- |
| ❌ Off-by-One Index         | `start_char` and `end_char` values skip or include incomplete characters. | `"start_char": 13, "end_char": 17, "text": "geta"` |
| ❌ Punctuation Leak         | Spans include or clip at brackets, slashes, or mathematical symbols.      | `"COOH] = 2[EMO"`                                  |
| ❌ Cross-Sentence Stitching | Tokens drawn from separate lines are merged as one entity.                | `"linkedreprocesscticcovalent"`                    |

---

### 7. **Absence of Ensemble Consensus or Metadata**

| Type                              | Description                                                                             | Example                                                 |
| --------------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| ❌ Solo Voting Only                | All detections show only `PolymerNER` or one model contributing.                        | `"models_participated": ["PolymerNER"]`                 |
| ❌ No Voting Log                   | No `models_voted`, `accept_reason`, or disagreement metadata is present.                | N/A                                                     |
| ❌ Missing Voting Confidence       | Confidence appears raw and unweighted; no `avg_weighted_conf`, no `merged_from_tokens`. | `"confidence": 3.49` from one model                     |
| ➕ Lack of Model-Specific Outcomes | No window-level breakdown of how each model predicted for that specific segment.        | No evidence of PolymerNER vs SciBERT results comparison |

---

### 8. **Invalid Span Merging**

| Type                      | Description                                                                                | Example                                                      |
| ------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------ |
| ❌ Text Corruption         | Tokens are concatenated directly, producing fused text blobs.                              | `"linkedreprocesscticcovalent"`                              |
| ❌ Discontiguous Merge     | Distant tokens are merged with incorrect intermediate content.                             | `"groups ([COOH"` + `"oxirane] ratio"` as one entity         |
| ❌ Misuse of Concatenation | Merging is performed via `text1 + text2` rather than re-using original sentence substring. | `"text": "Epo" + "xi"` → `"Epoxi"` instead of `"Epoxidized"` |

---

### 9. **Slot Labeling and Distribution Errors**

| Type                        | Description                                                                         | Example                                                  |
| --------------------------- | ----------------------------------------------------------------------------------- | -------------------------------------------------------- |
| ❌ Core Label Gaps           | Entities like `PROPERTY` or `MATERIAL` missing despite textual presence.            | No `MATERIAL` detected for `epoxy`                       |
| ❌ Slot Overflow             | Entities appear under wrong slots due to context misalignment.                      | `"150"` appears under both `SYMBOL` and `VALUE`.         |
| ❌ No Context Disambiguation | Ambiguous labels like `"TAR"` or `"CAN"` not clarified based on sentence structure. | `"CAN"` → multiple conflicting interpretations           |
| ➕ Mixed Granularity         | Some outputs show full phrases while others show substrings without normalization.  | `"glass transition"` vs `"glass transition temperature"` |

---

### 10. **Breakdown of Data Flow Integrity**

| Type                           | Description                                                                         | Example                                                           |
| ------------------------------ | ----------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| ❌ Canonical-like Window Flow   | Despite switching to token-packing, outputs behave like old canonical span slicing. | `ensemble_win_00X` with fused sentences                           |
| ❌ Sentence Reconstruction Lost | Text is not derived from original window `text[start_char:end_char]`.               | `"text": "linkedreprocesscticcovalent"` instead of extracted span |
| ❌ Model Context Decoupled      | Entity tokens are stripped of any evidence of which model produced which fragment.  | `"text": "Epo"` with no backing model name or score trace         |

---

## ✅ Final Summary Table

| Issue Domain                | Frequency | Severity | Requires Redesign |
| --------------------------- | --------- | -------- | ----------------- |
| Token Fragmentation         | Very High | Critical | Yes               |
| Metadata/Voting Loss        | Very High | Critical | Yes               |
| Incorrect Slot Assignment   | High      | Critical | Yes               |
| Sentence/Window Anchoring   | High      | High     | Yes               |
| Span Text Corruption        | Moderate  | High     | Yes               |
| Output Structure Divergence | High      | Critical | Yes               |
| Redundant Entities          | Moderate  | Moderate | Partial           |
| Semantic Span Loss          | High      | Critical | Yes               |
| Confidence Computation      | Moderate  | High     | Yes               |
| Overgeneration/Noise        | High      | High     | Yes               |
