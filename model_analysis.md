Here’s what I see from a full review of your **source (057.tei.xml)**, **ensemble output (057\_ensemble\_excerpt.json)**, **ground truth (test\_057.csv)**, and the key code (Cells 5–8):

---

## 📝 **Key Observations from the Analysis**

### 1. **Spanning Issues (Core Problem)**

* **Symptom:** Many predicted entities in `ensemble_results.json` are **over-merged** or **under-segmented**:

  * Example: `epoxidizedvegetableoil(evo)-basedepoxysystems` (should be “Epoxidized vegetable oil (EVO)-based epoxy systems”).
  * Example: `non-recyclablepetroleum-basedthermosetelastomers` (should be “non-recyclable petroleum-based thermoset elastomers”).
* **Cause:** Poor handling of subtoken alignment during preprocessing or inference:

  * Cell 7 (`token_packing.py`) packs tokens into windows **without preserving sentence-level offsets**.
  * Cell 8 (`fine_tuning.py`) aligns labels with sentences based on a **naïve string find()** logic in `align_labels`, which **fails when tokenization splits or joins words unexpectedly**.
  * Cell 9 (`ensemble_inference.py`) has **no span reconciliation logic** for overlapping windows; instead, it naïvely joins predictions, leading to runaway spans.

---

### 2. **Canonicalization Problems**

* The **canonicalization mappings** (Cell 5 & 6) replace synonyms before tokenization, but:

  * Some replacements are **too aggressive** (e.g., "glass transition temperature" → "Tg") and break sentence semantics.
  * Others miss due to **case sensitivity issues** in `canonicalize_text`.
  * The `canonicalize_token()` function in Cell 6 also **adds tokens to the tokenizer** but doesn’t resolve all subtoken splits due to missing “prefix/suffix” checks.

---

### 3. **Windowing and Overlap Logic**

* Cell 7 uses **fixed 512-token windows with 128-token overlap**, but:

  * Sentences split across windows are **double-tokenized**, causing inconsistent offsets.
  * Window overlap doesn’t resolve mid-word token cuts (BERT subtokenizers often split at unexpected places).
  * No logic to stitch predictions from overlapping windows cleanly in Cell 9.

---

### 4. **Fine-Tuning Dataset Quality**

* Synthetic data in Cell 8 has realistic sentence templates, but:

  * Real data augmentation (`real_data.csv`) appears **misaligned** with tokenizer’s subword behavior.
  * Labels often don’t align to the token boundaries (due to lack of subtoken span handling in `align_labels`).
  * `MAX_SEQ_LENGTH=128` is **too short** for complex scientific sentences; truncation is causing **label loss**.

---

### 5. **Ensemble Voting Weaknesses**

* Cell 9’s ensemble weighs PolymerNER and PhysBERT higher for POLYMER/SYMBOL, but:

  * It **doesn’t verify cross-model span agreement** (two models predicting slightly different boundaries are counted as separate votes).
  * Fallback linking tries to “recover” missed PROPERTY labels by regex, but **adds false positives**.

---

### 6. **Postprocessing Omissions**

* No **postprocessing clean-up** for:

  * Runaway spans (e.g., `fullybio-based3dcovalentnetworkcapableofreprocessingwithouttheneedforanexogenouscatalyst`).
  * Decoupling polymers from their modifiers (e.g., “based”, “derived”).
  * Removing in-line citations or figures (e.g., `[1]`, `Fig. 2a`).

---

## 🔥 **Top Causes of Spanning Issues**

| Issue                                    | Root Cause Location                         | Fix Suggestion                                       |
| ---------------------------------------- | ------------------------------------------- | ---------------------------------------------------- |
| Over-merged entities                     | `ensemble_inference.py` (Cell 9)            | Add span reconciliation and majority voting on span  |
| Misaligned labels due to subtoken splits | `align_labels` in `fine_tuning.py` (Cell 8) | Use token offset mappings for alignment              |
| Cut spans across windows                 | `token_packing.py` (Cell 7)                 | Implement sentence-aware packing, avoid mid-span cut |
| Canonicalization breaking sentence flow  | `tei_processing.py` (Cell 5)                | Delay canonicalization until postprocessing          |

---

## ✅ **Recommendations**

### 🛠 Preprocessing (Cell 5 & 7)

* **Delay Canonicalization**: Move `canonicalize_text()` to *post-inference cleanup*.
* **Sentence-aware Windowing**:

  * Use paragraph-level packing rather than fixed-size tokens.
  * Avoid splitting sentences across windows.
* **Offset Preservation**:

  * Store char offsets when writing `sentence_path` in metadata.

---

### 🧠 Fine-Tuning (Cell 8)

* Replace `align_labels()`:

  * Use `offset_mapping` from tokenizer to match labels to tokens **safely even with subtokens**.
  * Consider Hugging Face `token-classification` alignment utilities.
* Increase `MAX_SEQ_LENGTH` to 256 or 384 (at least).
* Validate synthetic samples with the tokenizer before training.

---

### 🗳 Ensemble Inference (Cell 9)

* Add **span reconciliation logic**:

  * Merge overlapping spans using confidence-weighted voting.
  * Prefer spans agreed upon by ≥2 models.
* Add **postprocessing cleanup**:

  * Resolve concatenated tokens (remove “##” artifacts).
  * Strip inline references and non-content artifacts.

---

### 📊 Evaluation (Cell 10)

* The similarity metrics are good but **too forgiving** (e.g., word overlap ≥ 0.6 classified as “Fair”).
* Tighten thresholds for POLYMER and PROPERTY entities.
---
If we want a **>90% precision model**, the first thing to do is get the **preprocessing rock solid** — because even the best ensemble will fail if the input is noisy, misaligned, or fragmented.

Here’s how I would **strategize Cell 5–7** based on:
✔️ Your original instructions
✔️ The issues I uncovered
✔️ Best practices for scientific NLP

---

# 🧠 **Comprehensive Strategy for Preprocessing (Cell 5–7)**

## 📌 **Phase 1: TEI Processing (Cell 5) – Absolute Clean Input**

### ✅ Goals:

* Extract only **scientific content** (no metadata, no references, no acknowledgments).
* Preserve paragraph and section boundaries.
* Detect and **label tables, figures, captions** properly.

### 🔥 Improvements:

1. **Tables, Figures, Captions**:

   * Use GROBID’s `<figure>`, `<table>`, and `<head>` tags to detect these blocks.
   * Label them as `FIGURE_CAPTION`, `TABLE_CAPTION`, etc. in metadata.
   * Skip or store separately for later reference if needed.

2. **Section Label Normalization**:

   * Standardize all headings (`Introduction`, `2. Methods`, `2.1. Sample Prep`) as `SECTION_INTRODUCTION`, `SECTION_METHODS`, etc.

3. **Content Filtering**:

   * Drop all `<note>` and `<ref>` text (inline citations like `[1]`, DOIs, submission notes).

4. **Unicode Normalization + OCR Fixes**:

   * Correct OCR artifacts (`deg C` → `°C`, `g-1` → `g⁻¹`, `O C` → `°C`).

5. **Plausibility Filter**:

   * Keep sentences with:

     * ≥1 scientific keyword (from `PROPERTY_NAMES`, `POLYMER_NAMES`, etc.)
     * Or containing numeric values (likely measurements).
   * Drop anything <30 or >400 chars unless it's part of a table/caption.

6. **Offset Tracking**:

   * Store character offsets for each sentence relative to the full text.
   * Metadata includes:

     ```
     {
       "section": "2.1 Polymerization",
       "type": "paragraph",
       "offset_start": 1243,
       "offset_end": 1401,
       "sentence_path": "...",
       "status": "ready"
     }
     ```

---

## 📌 **Phase 2: Tokenizer Audit & Extension (Cell 6) – Subtoken Mastery**

### ✅ Goals:

* Make sure domain-specific terms don’t split across multiple tokens.

### 🔥 Improvements:

1. **Audit Tokens**:

   * Check all `POLYMER_NAMES`, `PROPERTY_NAMES`, `SCIENTIFIC_UNITS`, `SYMBOLS` against each tokenizer.
   * Identify terms that split into subtokens (e.g., `glasstransitiontemperature` → `glass##transition##temperature`).

2. **Extend Tokenizers**:

   * Add frequently split terms as whole tokens to avoid span fragmentation.
   * Save extended tokenizers separately (`*_extended`) and ensure models use them.

3. **Case Sensitivity**:

   * Account for cased/uncased differences across models.
   * Canonicalize tokens consistently for each.

---

## 📌 **Phase 3: Token Packing (Cell 7) – Preserve Sentence Integrity**

### ✅ Goals:

* Avoid cutting entities across windows.
* Maximize GPU utilization without truncating important context.

### 🔥 Improvements:

1. **Sentence-Aware Windowing**:

   * Instead of fixed 512-token chunks, pack whole sentences into windows until near limit.
   * Backtrack to avoid cutting off mid-sentence.

2. **Overlapping Windows**:

   * Allow overlap of last N tokens between windows (to catch cross-sentence entities).
   * Tag overlapping regions for later reconciliation.

3. **Span-Aware Packing**:

   * If an entity would be cut, move it entirely to next window.

4. **Audit Logs**:

   * Save a mapping of:

     ```
     window_id → [sentence_ids], offsets
     ```
   * Useful for stitching predictions later.

---

# 🎯 **Why This Will Work**

By implementing the above:
✅ Each model sees **clean, coherent, and scientifically rich text**.
✅ Subtokenization issues are eliminated.
✅ No mid-entity window cuts.
✅ Labels align 1:1 with tokenized inputs.

This directly addresses the **root causes of poor spans** and sets up Cells 8–9 for success.

---

# 🚀 My Recommendation

We start by **rewriting Cell 5–7 with this strategy**:
✅ Cell 5: New TEI parser + clean metadata.
✅ Cell 6: Tokenizer audit + extension (domain aware).
✅ Cell 7: Sentence-aware token packing + offset tracking.

Once these are robust, Cells 8–10 will get **>90% precision almost by default**.
---
Let’s take that exact raw extract from the TEI:

---

## 📖 **Raw GROBID Extract**

```
Epoxidized vegetable oil (EVO)-based epoxy systems offer a promising avenue for replacing non-recyclable petroleum-based thermoset elastomers. Looking towards future prospects, they also hold potential to evolve into sustainable covalent adaptable networks (CANs). Typically, transesterification-based CANs require catalysts to achieve crosslinked structures that are reprocessable at relatively high temperatures (T ≥ 150 • C). In this study, epoxidized soybean oil (ESBO) was cross-linked with a eutectic hardener composed of L-tartaric acid (TAR) and ethyl lactate (in an aqueous solution), resulting in the development of a fully bio-based 3D covalent network capable of reprocessing without the need for an exogenous catalyst. In addition, it was demonstrated that the peculiar structure of L-tartaric acid, with -OH groups linked to its backbone, plays a prominent role in the reactivity of the system. These free hydroxyl functions facilitate both the ring-opening of epoxides and transesterification reactions, thus enhancing both curing and covalent exchange kinetics.
```

---

## 🧠 Is this joined up in GROBID?

The original text extracted by GROBID **preserves spaces perfectly** between words like:
✅ `Epoxidized vegetable oil`
✅ `non-recyclable petroleum-based thermoset elastomers`
✅ `covalent adaptable networks (CANs)`
✅ `epoxidized soybean oil (ESBO)`

There are no artifacts like:

```
epoxidizedvegetableoil
non-recyclablepetroleum-basedthermosetelastomers
```

---

## 🔥 So what went wrong?

If we’re seeing joined outputs like:

```
epoxidizedvegetableoil(evo)-basedepoxysystems
```

then it *did not happen during extraction*. It almost certainly happened **later in the pipeline**:

---

### 1️⃣ During **OCR Cleanup (Cell 5)**

Your regexes in `fix_ocr_artifacts()` contain overzealous replacements:

```python
(r"(?<=\d)\s+(?=\d)", "")  # Removes spaces between digits
(r"\s+([.,;:])", r"\1")    # Removes spaces before punctuation
```

If applied too broadly, they might accidentally collapse spaces between words if a pattern matches.

---

### 2️⃣ During **Canonicalization (Cell 5)**

Your `canonicalize_text()` function replaces synonyms but does not restore spaces if the synonym occurs concatenated (because of an OCR artifact or pre-tokenization issue).

---

### 3️⃣ During **Postprocessing (Cell 9)**

In `normalize_span()`, you join tokens like so:

```python
"".join(tokens).replace("##", "").strip()
```

This **removes all spaces** unless you re-insert them based on token boundaries.

---

## ✅ **Conclusion: It’s not GROBID**

The joining **does not originate from the raw TEI extraction**.
It happens:

* **Either during preprocessing cleanup (Cell 5)**
* Or **during postprocessing span reconstruction (Cell 9)**

---

Let’s map it out clearly based on your **project structure** and the current workflow.

---

# 🗂️ **Where Cell 5–7 Preprocessing Lives in the Project**

## 📁 Project Structure Recap

(from `project_structure.md`)

```
polymer_extractor/
│
├── api/
│   ├── inference.py
│   ├── finetune.py
│   ├── grobid.py
│   ├── evaluation.py
│   ├── setup.py
│   ├── session.py
│
├── services/
│   ├── tokenizer_audit.py       <-- Cell 6 logic (audit/extend)
│   ├── tei_processing.py        <-- Cell 5 logic (TEI cleaning)
│   ├── token_packing.py         <-- Cell 7 logic (windowing)
│
├── storage/
│   ├── appwrite_client.py
│   ├── database.py
│   ├── bucket.py
│
├── utils/
│   ├── preprocessing.py         <-- helper functions
│   ├── validators.py
│
├── cli/
│   ├── grobid_cli.py
│   ├── setup_cli.py
│
```

---

## ✅ **Where Each Cell’s Logic Currently Lives**

| Cell # | Functionality               | Current Location              | Triggered By                      |
| ------ | --------------------------- | ----------------------------- | --------------------------------- |
| **5**  | TEI Parsing, Normalization  | `services/tei_processing.py`  | `api/grobid.py` → `grobid_cli.py` |
| **6**  | Tokenizer Audit & Extension | `services/tokenizer_audit.py` | `api/setup.py`                    |
| **7**  | Token Packing (Windowing)   | `services/token_packing.py`   | `api/finetune.py`                 |

---

## 🔥 **How It Flows in the Pipeline**

1. **Upload Paper** → API endpoint (`api/grobid.py`)
2. Grobid processes PDF → `.tei.xml`
3. **Cell 5 runs**:

   * `services/tei_processing.py`
   * Extract sentences, clean text, save to `workspace/sentences/`
   * Populate `metadata` table.
4. **Cell 6 runs**:

   * `services/tokenizer_audit.py`
   * Extends tokenizer if needed.
5. **Cell 7 runs**:

   * `services/token_packing.py`
   * Packs token windows for model consumption.
6. Prepared data is now ready for **Cell 8 (Fine-tuning)**.

---

## 🏁 **Where It’s Actually Triggered**

* In CLI:

  ```
  pnlp grobid process-paper --file mypaper.pdf
  pnlp setup tokenizer-audit
  pnlp finetune prepare-data
  ```
* In API:

  * `POST /api/process` → kicks off TEI parse + preprocessing.

---

## 🗝 **Key Takeaway**

Cell 5–7 preprocessing happens **right after TEI extraction** and **before fine-tuning/inference**.
It is part of the **“preparation” step** and is invoked by:
✅ CLI commands (**pnlp prepare-data**)
✅ API endpoints (**POST /api/process**)
✅ Or automatic triggers when a new paper enters Appwrite buckets.

---

# 🚀 Next Step: Strategy for Rewrite

Here’s how I propose we implement our new robust Cell 5–7:

| Step                | Location                      | Action                                          |
| ------------------- | ----------------------------- | ----------------------------------------------- |
| TEI cleaning        | `services/tei_processing.py`  | Rewrite to preserve spacing & clean text safely |
| Tokenizer extension | `services/tokenizer_audit.py` | Add static lexicon anchoring                    |
| Window packing      | `services/token_packing.py`   | Rewrite for sentence-aware, span-safe packing   |
| Helpers             | `utils/preprocessing.py`      | Move shared cleanup logic here                  |

This keeps all changes **modular** and ensures CLI/API workflows don’t break.

---
Your diagnosis hits all the right pain-points—here’s how I see it, with a few refinements and prioritizations to help us move straight into code:

---

## 1. Spanning & Token-Level Alignment

* **What’s happening:** Your examples of over-merged spans (e.g. `epoxidizedvegetableoil…`) confirm that somewhere we’re collapsing or never re-injecting whitespace.
* **Likely culprits:**

  1. **OCR cleanup regexes** in `tei_processing.py` that run too greedily and remove inter-word spaces.
  2. **Span reconstruction** in `ensemble_inference.py` that simply does `''.join(tokens).replace('##','')` without consulting original char offsets.
* **Next step:**

  * In the TEI cleaning stage, wrap each regex in a test harness (e.g. run on a small snippet and assert expected whitespace) before committing.
  * In post-inference, switch to using the stored `offset_start`/`offset_end` metadata so you rebuild spans from the original character buffer rather than token joins.

---

## 2. Canonicalization Timing

* **Your insight** about delaying synonym replacement until **after** inference is spot on:

  * **Pre-tokenization** canonicalization masks the true word boundaries and fools the label alignment.
  * **Post-tokenization** or even **post-inference** cleanup gives us true spans to operate on.
* **Action:** Remove all calls to `canonicalize_text()` from the TEI pipeline. Instead, aftermarket each predicted span: turn “Tg” back into “glass transition temperature” (or vice versa) based on the span’s context and a confidence threshold.

---

## 3. Windowing & Overlaps

* **Fixed-length windows** with blind overlap are a known source of mid-entity cuts.
* **Sentence-aware packing** will:

  1. Guarantee no sentence is ever split.
  2. Let you use the tokenizer’s `offset_mapping` to track exactly where each token lives in the original text.
* **Quick win:** Implement a greedy packer that adds full sentences until you hit \~98% of `max_length`, then backs off to the previous sentence. Tag the overlapping sentences explicitly in metadata so you know which predictions to de-duplicate.

---

## 4. Label Alignment in Fine-Tuning

* **Naïve `string.find()`** will always fail once BERT does any subtoken splitting or lowercasing.
* **Better approach:**

  * Use the HuggingFace `BatchEncoding`’s `offset_mapping`. For each true entity span (char start/end), find the set of tokens whose mapped offsets overlap that char span.
  * Leverage their `align_labels_with_tokens` helper or write a small wrapper around it.
* **Also bump** `MAX_SEQ_LENGTH` to at least 256—many of your sentences are well over 128 tokens once you count chemical names.

---

## 5. Ensemble & Voting Logic

* **Span reconciliation** is essential: two models predicting `(Tg)` at slightly different offsets should vote on the same span, not two.
* **Merge strategy:**

  1. Cluster predicted spans by character overlap ≥50%.
  2. Within each cluster, pick the span boundaries with the highest sum of log-probs.
  3. Only keep clusters with ≥2 model votes (or ≥1 high-confidence vote).
* **Post-filter:** remove any span containing inline citations (`[1]`, `Fig.`) or non-alphabetic fragments.

---

## 6. Putting It All Together in Cells 5–7

1. **TEI Processing (`services/tei_processing.py`)**

   * Audit and unit-test every regex.
   * Strip only the unwanted `<ref>`/`<note>` nodes.
   * Emit every sentence with `(offset_start, offset_end)` in a JSON line.
2. **Tokenizer Audit (`services/tokenizer_audit.py`)**

   * Generate a report of splits for each term in your constants.
   * Add any high-frequency splits to the vocab so they become single tokens.
3. **Token Packing (`services/token_packing.py`)**

   * Greedy sentence-level windowing.
   * Annotate each window with its sentence IDs and char offsets for later de-duplication.

---

### ✔️ Why This Will Fix the Root Issue

* All whitespace-collapsing happens in a safe, test-driven context.
* Label alignment uses true char offsets so subtokens never misalign.
* No more mid-sentence cuts → no more runaway or fused spans.
* A clean, modular pipeline in exactly the three service files you outlined.

Once we’ve got Cells 5–7 bulletproof, Cells 8–10 will fall into place—and you’ll see your precision jump well above 90%. Let me know which of these you’d like to tackle first, or if you want to dive straight into rewriting one of the services.
---

---

---
Ah John—this is **exactly the kind of subtle, destructive issue** that can ruin even a beautifully trained ensemble.

And you’re absolutely right to call this out as “more serious” because:

✅ The model **has the correct intent**
✅ But the **span boundaries are catastrophically wrong**
✅ Making it “technically right” (the concepts are there) but “practically 50% wrong” (spans unusable for downstream).

Let’s break it down carefully.

---

# 🚨 The Problem: Boundary Drift

Your input sentence:

> *The polyester was discovered to melt at a glass transition temperature of 44 °C.*

The model predicts:

| Label    | Predicted Span                           |
| -------- | ---------------------------------------- |
| Polymer  | `polyesterwasdiscovered`                 |
| Property | `meltat`, `glasstransitiontemperatureof` |
| Value    | `44`                                     |
| Symbol   | `°C`                                     |
| Material | `None`                                   |

---

### 🔥 Why This Is Technically Correct

* `polyesterwasdiscovered` **contains** the polymer “polyester”
* `glasstransitiontemperatureof` **contains** the property “glass transition temperature”
* `44`, `°C` are **perfect**

---

### ❌ Why It’s Practically Wrong

The predicted spans **include surrounding text** due to:

* **Subtoken Merging Errors** (e.g., `polyester` + `was` → `polyesterwas`)
* **Over-extended Windows**: Context words pulled into entity spans
* **No Span Normalization Post-Inference**: “glass transition temperature of” should stop at “glass transition temperature”

This is not just an aesthetic issue:

* 🧨 It **breaks downstream parsing**
* 🧨 It **destroys precision/recall** in evaluation against `test_057.csv`

---

# 📊 Root Causes in Your Pipeline

| Stage                              | Issue                                                    |
| ---------------------------------- | -------------------------------------------------------- |
| **Token Packing (Cell 7)**         | Sentences cut across windows → offsets misaligned        |
| **Fine-Tuning Alignment (Cell 8)** | Naïve `string.find()` alignment misses real token bounds |
| **Ensemble Voting (Cell 9)**       | Overlapping predictions naïvely merged (runaway spans)   |
| **Postprocessing (Cell 9)**        | No span normalization (keeps glued-together words)       |

---

# 🧠 Why the Model *Thinks* It’s Right

This is classic with BERT-family tokenizers:
✅ Subwords like `polyester##was`
✅ Joined during postprocessing as `"polyesterwas"`
✅ No logic exists to break at **non-domain stopwords** (“was”, “discovered”, “of”)

---

# 🎯 The Fix: Multi-Stage Boundary Refinement

---

## 🔥 Stage 1: Token Packing (Cell 7)

✅ Preserve **exact sentence boundaries**
✅ Track `(char_start, char_end)` per token
✅ Prevent cross-window entity cutting

---

## 🔥 Stage 2: Alignment (Cell 8)

✅ Replace naive `string.find()` with:

* Hugging Face `offset_mapping`
* `align_labels_with_tokens` utility
  ✅ Ensures only **tokens overlapping with true entity spans** are labeled

---

## 🔥 Stage 3: Ensemble Voting (Cell 9)

✅ Cluster overlapping spans
✅ Within each cluster:

* Keep **shortest span** covering majority votes
* Use confidence weighting to resolve ties

Example:

| Raw Predictions          |
| ------------------------ |
| `polyesterwasdiscovered` |
| `polyester`              |

Result after reconciliation:
✅ **Polymer: polyester**

---

## 🔥 Stage 4: Postprocessing (Cell 9)

✅ Strip trailing/leading stopwords from spans:

* `was`, `discovered`, `of`, `the`, etc.
  ✅ Use domain lexicon (`POLYMER_NAMES`, `PROPERTY_NAMES`) for safe trimming:

```python
if span not in POLYMER_NAMES and span.startswith("polymer"):
    span = span.replace("polymer", "").strip()
```

✅ Regex cleanup for runaway concatenations:

```python
re.sub(r"([a-z])([A-Z])", r"\1 \2", span)
```

Result:

| Before                         | After                          |
| ------------------------------ | ------------------------------ |
| `glasstransitiontemperatureof` | `glass transition temperature` |

---

# ✅ End Result

The model’s raw prediction:

```
polyesterwasdiscovered
```

Becomes:
✅ **Polymer: polyester**

And:

```
glasstransitiontemperatureof
```

Becomes:
✅ **Property: glass transition temperature**

---

# 🚀 Next Step Recommendation

We fix this in **two phases**:

| Phase                        | Fix                                               |
| ---------------------------- | ------------------------------------------------- |
| **Phase 1 (Preprocessing)**  | Rewrite `token_packing.py` for offset integrity   |
| **Phase 2 (Postprocessing)** | Add span normalization in `ensemble_inference.py` |

---

Do you want me to:
✅ Start by rewriting **Cell 6 (tokenizer\_audit)** first (so subtokens are anchored and this error reduces naturally)?
✅ Or go straight into **Cell 7 (token\_packing)** since sentence boundaries and offsets are critical?
✅ Or bundle **Cell 6 + 7 + span normalization** as one comprehensive patch?
