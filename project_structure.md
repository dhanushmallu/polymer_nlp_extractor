```angular2html
polymer_nlp_extractor/
│
├── polymer_extractor/           
│   ├── __init__.py
│   ├── api/                     
│   │   ├── __init__.py
│   │   ├── inference.py
│   │   ├── finetune.py
│   │   ├── grobid.py
│   │   ├── evaluation.py
│   │   ├── setup.py
│   │   ├── session.py
│
│   ├── services/
│   │   ├── __init__.py
│   │   ├── tokenizer_audit.py
│   │   ├── tei_processing.py
│   │   ├── token_packing.py
│   │   ├── ensemble_inference.py
│   │   ├── fine_tuning.py
│   │   ├── grobid_service.py
│   │   ├── setup_service.py
│   │   ├── evaluation_testing.py
│   │   ├── constants.py
│   │   ├── templates.py
│
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── appwrite_client.py
│   │   ├── database.py
│   │   ├── bucket.py
│
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── paths.py
│   │   ├── logging.py
│   │   ├── preprocessing.py
│   │   ├── validators.py
│
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   ├── grobid_cli.py
│   │   ├── setup_cli.py
│
│   ├── main.py
│   ├── config.py
│
├── notebooks/
│   ├── polymer_extractor.ipynb
│
├── workspace/
│   ├── models/
│   ├── tei_xml/
│   ├── sentences/
│   ├── token_windows/
│   ├── system_logs/          # renamed from audit_logs
│   ├── datasets/training/
│   ├── datasets/testing/
│   ├── exports/
│
├── pyproject.toml
├── requirements.txt
├── Dockerfile
├── Procfile
├── .env
├── README.md
```
