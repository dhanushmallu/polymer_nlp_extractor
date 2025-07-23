# Changelog for Project Structure
- /notebook unchanged
- /api: adds `groundtruth.py`, `preprocessing.py`
- /services: renames fine_tuning.py to `fine_tune_service.py`, adds `groundtruth_service.py`, `preprocessing_service.py`, renames `tei_processing.py` to `tei_processing_service.py`, moves `templates.py` to `constants/` package, renames `token_packing.py` to `token_packing_service.py`, renames `ensemble_inference.py` to `ensemble_inference_service.py`, renames `evaluation_testing.py` to `evaluation_service.py`, renames `tokenizer_audit.py` to `tokenizer_service.py`
- splits `constants.py` into `/services/constants/` package with:
  - configuration_constants.py: contains CONTENT_MARKERS, SCIENTIFIC_SECTIONS, ENTITY_TYPES, EXPORT_FORMATS and MEASUREMENT_PATTERNS
  - greek_letters.py: contains UPPERCASE_GREEK_LETTERS, LOWERCASE_GREEK_LETTERS, NAMED_GREEK_LETTERS
  - material_names.py: contains MATERIAL_NAMES
  - templates.py: contains SENTENCE_TEMPLATES
  - polymer_names.py: contains POLYMER_NAMES
  - property_names.py: contains PROPERTY_NAMES
  - property_tables.py: contains PROPERTY_TABLE
  - scientific_symbols.py: contains SCIENTIFIC_SYMBOLS
  - scientific_units.py: contains SCIENTIFIC_UNITS
  - value_formats.py: contains VALUE_FORMATS
- /storage: renames `database.py` to `database_manager.py`, renames `bucket.py` to `bucket_manager.py`
- /utils: adds `file_utils.py`, `lexicon_guard.py`

```angular2html
polymer_nlp_extractor/
│
├── polymer_extractor/
│   ├── __init__.py
│   ├── model_config.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── inference.py
│   │   ├── finetune.py
│   │   ├── grobid.py
│   │   ├── evaluation.py
│   │   ├── setup.py
│   │   ├── session.py
│   │   ├── groundtruth.py
│   │   ├── preprocessing.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── fine_tune_service.py
│   │   ├── groundtruth_service.py
│   │   ├── preprocessing_service.py
│   │   ├── tei_processing_service.py
│   │   ├── token_packing_service.py
│   │   ├── ensemble_inference_service.py
│   │   ├── evaluation_service.py
│   │   ├── tokenizer_service.py
│   │   ├── grobid_service.py
│   │   ├── setup_service.py
│   │   ├── constants/
│   │   │   ├── configuration_constants.py
│   │   │   ├── greek_letters.py
│   │   │   ├── material_names.py
│   │   │   ├── templates.py
│   │   │   ├── polymer_names.py
│   │   │   ├── property_names.py
│   │   │   ├── property_tables.py
│   │   │   ├── scientific_symbols.py
│   │   │   ├── scientific_units.py
│   │   │   ├── value_formats.py
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── appwrite_client.py
│   │   ├── database_manager.py
│   │   ├── bucket_manager.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── paths.py
│   │   ├── logging.py
│   │   ├── preprocessing.py
│   │   ├── validators.py
│   │   ├── file_utils.py
│   │   ├── lexicon_guard.py
│   │
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   ├── grobid_cli.py
│   │   ├── setup_cli.py
│   │
│   ├── main.py
│   ├── config.py
│
├── notebooks/
│   ├── polymer_extractor.ipynb
│
├── workspace/
│   ├── models/ # holds all models
│   │   ├── tokenizers # contains models that have been extended by tokenization eg. model_name_extended
│   ├── reports/ # 
│   ├── extracted_xml/ # holds pdfs converted to xml but not yet cleaned
│   ├── ground_truth/ # saves any uploaded testing data before processing
│   ├── processed_xml/ # holds the xml files that have been cleaned
│   ├── system_logs/
│   ├── public/grobid # holds grobid sample data
│   ├── raw_inputs/ # houses uploaded pdfs ready for processing
│   ├── samples/ # contains tokenization output (like model_name/<file_name>_tei_sentences.txt, model_name/<file_name>_tei_tagless.txt, model_name/<file_name>_tei_token_windows.json)
│   ├── system_logs/ # where system logs are housed. Contains api.log, system.log and user.log
│   ├── grobid-0.8.2/  # contains the root location of grobid server
│   ├── datasets/
│   │   ├── training/ # saves processed trainging data (when testing is done, the testing data is copied here)
│   │   ├── testing/ # saves processed (realigned) testing data
│   ├── exports/
│
├── pyproject.toml
├── requirements.txt
├── Dockerfile
├── Procfile
├── .env
├── README.md
```
