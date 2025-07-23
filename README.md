- Requires Java Version <17
- if using window, ensure git is installed


### `ensemble_inference.py` — TODOs for Robust Span Assembly and Voting

#### 1. Merge Overlapping Spans Across Windows

* Use `char_start` and `char_end` from `offset_mapping` to:

  * Identify predictions from different windows that refer to the same span.
  * Cluster spans with significant overlap (e.g., Jaccard > 0.5, or ≥50% char overlap).
* Reconstruct the canonical span by majority vote or confidence weighting.

#### 2. Handle Sentence-Level Split Recovery

* Some long domain-aware sentences are split for token safety (e.g., `glass transition temperature of` split from `glass transition temperature`).
* Reassemble these during the ensemble step by:

  * Tracking sentence-level ancestry (`sentence_id` from metadata).
  * Merging adjacent sentence spans only if they match domain-aware patterns (e.g., `PROPERTY_NAME` continued).

#### 3. Normalize and Clean Spans

* Strip subtoken artifacts like `##`, extra hyphens, or token-joined compounds.
* Re-inject proper spacing (e.g., `"polymerwas"` becomes `"polymer was"` if tokenization failed).
* Remove trailing stopwords like `"of"`, `"at"`, `"the"` unless needed for scientific meaning.

#### 4. Confidence-Based Voting

* For each model:

  * Include prediction confidence if available.
  * Weigh high-confidence models more heavily (e.g., PolymerNER > BioBERT).
* For each span cluster:

  * Accept only if supported by two or more models or a strong model with high confidence.
  * Optionally log disagreement for manual review.

#### 5. Ensure Slot Alignment

* Ensure that predicted spans are assigned to correct entity slots:

  * e.g., `Tg` → `Symbol`, not `Value`
* If two slots compete (e.g., same span in both `Symbol` and `Property`), resolve by:

  * Using `PROPERTY_TABLE` lookup.
  * Checking surrounding context in the original sentence.

#### 6. Retain Traceability

* Store metadata with every final span:

  ```json
  {
    "label": "Property",
    "text": "glass transition temperature",
    "char_start": 1420,
    "char_end": 1450,
    "sentence_ids": [12, 13],
    "voted_from": ["PolymerNER", "MatSciBERT"],
    "confidence_avg": 0.87
  }
  ```

#### 7. Drop or Flag Weak/Noisy Spans

* Spans that:

  * Are predicted by only one weak model,
  * Are shorter than 2 characters,
  * Are fully lowercase stopwords or punctuation only,
  * Or duplicate others
* Should be dropped or flagged as `"rejected_by_ensemble"`.

---

### Bonus (Optional Later)

* Add CLI debug option: `--show-voting-matrix` to print how each model voted per span.
* Save rejected span clusters to `ensemble_rejected.json` for auditing.
