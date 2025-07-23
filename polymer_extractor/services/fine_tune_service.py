"""
polymer_extractor/services/fine_tune_service.py

Fine-Tuning Service for Polymer NLP Extractor (Synthetic Focus)

Features:
---------
- Generates synthetic dataset (>20K samples) using constants + templates
- Uses extended tokenizers for domain consistency
- Configures Hugging Face Trainer
- Tracks training via Weights & Biases (wandb)
- Saves checkpoints locally and uploads models to Appwrite
"""

import os
import random
from pathlib import Path
from typing import Dict, Any, Optional, List
import torch
import gc
from datetime import datetime

import evaluate
import pandas as pd
import wandb
from datasets import Dataset, DatasetDict
from transformers import (
    AutoTokenizer,
    AutoModelForTokenClassification,
    Trainer,
    TrainingArguments,
    DataCollatorForTokenClassification,
    EarlyStoppingCallback
)
from tqdm import tqdm

from polymer_extractor.model_config import (
    ENSEMBLE_MODELS, LABELS, LABEL2ID, ID2LABEL
)
from polymer_extractor.services.constants import POLYMER_NAMES, PROPERTY_NAMES, SCIENTIFIC_UNITS, VALUE_FORMATS, \
    MATERIAL_NAMES, SCIENTIFIC_SYMBOLS
from polymer_extractor.services.templates import SENTENCE_TEMPLATES
from polymer_extractor.storage.bucket_manager import BucketManager
from polymer_extractor.utils.logging import Logger
from polymer_extractor.utils.paths import WORKSPACE_DIR, MODELS_DIR

logger = Logger()
bucket_manager = BucketManager()


class FineTuneService:
    """
    Fine-Tunes ensemble models on synthetic datasets (>20K samples).
    """

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or MODELS_DIR
        os.makedirs(self.output_dir, exist_ok=True)
        wandb.login()

    def run(self) -> Dict[str, Any]:
        """
        Fine-tune all ensemble models on synthetic dataset.
        """
        logger.info(
            "Starting synthetic fine-tuning for all ensemble models.",
            source="finetune.run",
            category="training",
            event_type="pipeline_start"
        )

        results = {}
        dataset = self._generate_synthetic_dataset(num_samples=25000)

        for model_cfg in ENSEMBLE_MODELS:
            try:
                logger.info(
                    f"Fine-tuning model: {model_cfg.name}",
                    source="finetune.run",
                    category="training",
                    event_type="model_start"
                )

                model_dir = os.path.join(self.output_dir, f"{self._sanitize_name(model_cfg.name)}_finetuned")
                result = self._fine_tune_model(model_cfg, dataset, model_dir)
                results[model_cfg.name] = result

                # Upload model to Appwrite
                bucket_id = f"{self._sanitize_name(model_cfg.name)}_bucket"
                zip_path = self._zip_model(model_dir)
                bucket_manager.create_bucket(bucket_id, f"Fine-tuned model bucket for {model_cfg.name}")
                bucket_manager.upload_file(bucket_id, zip_path)

            except Exception as e:
                logger.error(
                    f"Fine-tuning failed for {model_cfg.name}: {e}",
                    source="finetune.run",
                    error=e,
                    category="training",
                    event_type="model_error"
                )
                results[model_cfg.name] = {"success": False, "error": str(e)}

        logger.info(
            "Fine-tuning completed for all models.",
            source="finetune.run",
            category="training",
            event_type="pipeline_complete"
        )
        return results

    def _generate_synthetic_dataset(self, num_samples: int) -> DatasetDict:
        """
        Generate synthetic dataset using constants + templates.

        Parameters
        ----------
        num_samples : int
            Total number of synthetic examples.

        Returns
        -------
        DatasetDict
            Hugging Face dataset split into train/validation.
        """
        logger.info(
            f"Generating {num_samples} synthetic samples...",
            source="finetune._generate_synthetic_dataset",
            category="data",
            event_type="synthetic_generation"
        )

        examples = []
        for _ in range(num_samples):
            polymer = random.choice(POLYMER_NAMES)
            property_name = random.choice(PROPERTY_NAMES)
            unit = random.choice(SCIENTIFIC_UNITS)
            symbol = random.choice(SCIENTIFIC_SYMBOLS)
            value = random.choice(VALUE_FORMATS)
            material = random.choice(MATERIAL_NAMES)
            template = random.choice(SENTENCE_TEMPLATES)

            sentence = template.format(
                polymer=polymer,
                property=property_name,
                unit=unit,
                symbol=symbol,
                value=value,
                material=material
            )

            tokens, labels = self._tokenize_and_label(sentence, polymer, property_name, unit, symbol, value, material)
            examples.append({"tokens": tokens, "labels": labels})

        # Convert to DataFrame and split
        df = pd.DataFrame(examples)
        df = df.sample(frac=1.0).reset_index(drop=True)  # Shuffle
        train_size = int(0.9 * len(df))
        train_df, val_df = df.iloc[:train_size], df.iloc[train_size:]

        logger.info(
            f"Synthetic dataset: {len(train_df)} train / {len(val_df)} validation",
            source="finetune._generate_synthetic_dataset",
            category="data",
            event_type="synthetic_ready"
        )

        return DatasetDict({
            "train": Dataset.from_pandas(train_df),
            "validation": Dataset.from_pandas(val_df)
        })

    def _tokenize_and_label(self, sentence: str, polymer: str, property_name: str, value: str, symbol: str, unit: str,
                            material: str) -> (List[str], List[int]):
        """
        Tokenize sentence and apply BIO labels.

        Parameters
        ----------
        sentence : str
            Full synthetic sentence.
        polymer, property_name, value, unit : str
            Entities to label.

        Returns
        -------
        tuple
            (tokens, labels)
        """
        tokens = sentence.split()
        labels = ["O"] * len(tokens)

        def label_entity(entity: str, label_prefix: str):
            if not entity or not entity.strip():
                return  # Skip empty or None entities

            entity_tokens = entity.split()
            print(f"Entity: {entity[:10]}... Tokens: {entity_tokens[:10]}")  # Debugging: Print first 10 characters and tokens
            for i, token in enumerate(tokens):
                if token == entity_tokens[0] and tokens[i:i + len(entity_tokens)] == entity_tokens:
                    labels[i] = f"B-{label_prefix}"
                    for j in range(1, len(entity_tokens)):
                        labels[i + j] = f"I-{label_prefix}"

        label_entity(polymer, "POLYMER")
        label_entity(property_name, "PROPERTY")
        label_entity(value, "VALUE")
        label_entity(unit, "UNIT")
        label_entity(material, "MATERIAL")
        label_entity(symbol, "SYMBOL")

        # Convert to integer IDs
        label_ids = [LABEL2ID.get(label, 0) for label in labels]
        return tokens, label_ids

    def _setup_device(self):
        """Set up device for training (CUDA or CPU)."""
        if torch.cuda.is_available():
            n_gpus = torch.cuda.device_count()
            gpu_names = [torch.cuda.get_device_name(i) for i in range(n_gpus)]
            logger.info(f"CUDA available: {n_gpus} GPU(s): {gpu_names}", source="fine_tune_service")
            return "cuda"
        else:
            logger.warning("CUDA unavailable: training will use CPU.", source="fine_tune_service")
            return "cpu"

    def _clear_gpu_memory(self):
        """Clear GPU memory to prevent out-of-memory errors."""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
            logger.info("GPU memory cleared.", source="fine_tune_service")

    def _get_safe_batch_size(self):
        """Determine batch size based on available GPU memory."""
        if not torch.cuda.is_available():
            return 4
        mem_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
        return 16 if mem_total >= 24 else 8 if mem_total >= 12 else 4

    def _fine_tune_model(self, model_cfg, dataset: DatasetDict, model_dir: str) -> Dict[str, Any]:
        """Fine-tune a single model with enhanced stability and logging."""
        self._clear_gpu_memory()
        device = self._setup_device()

        # Load tokenizer and model
        tokenizer = AutoTokenizer.from_pretrained(model_cfg.model_id, use_fast=True)
        model = AutoModelForTokenClassification.from_pretrained(
            model_cfg.model_id, num_labels=len(LABELS), id2label=ID2LABEL, label2id=LABEL2ID
        ).to(device)

        # Tokenize dataset
        tokenized_ds = dataset.map(
            lambda x: self._tokenize_and_label(x, tokenizer),
            batched=True,
            remove_columns=dataset["train"].column_names
        )

        # Training arguments
        batch_size = self._get_safe_batch_size()
        train_args = TrainingArguments(
            output_dir=model_dir,
            learning_rate=model_cfg.training_config.get("lr", 2e-5),
            num_train_epochs=model_cfg.training_config.get("epochs", 5),
            per_device_train_batch_size=batch_size,
            gradient_accumulation_steps=max(1, 32 // batch_size),
            weight_decay=model_cfg.training_config.get("weight_decay", 0.01),
            eval_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            logging_dir=os.path.join(model_dir, "logs"),
            logging_steps=50,
            save_total_limit=2,
            report_to=["wandb"] if wandb.run else [],
            fp16=torch.cuda.is_available(),
            gradient_checkpointing=True,
            max_grad_norm=1.0
        )

        # Trainer
        trainer = Trainer(
            model=model,
            args=train_args,
            train_dataset=tokenized_ds["train"],
            eval_dataset=tokenized_ds["validation"],
            tokenizer=tokenizer,
            data_collator=DataCollatorForTokenClassification(tokenizer),
            compute_metrics=self._compute_metrics,
            callbacks=[EarlyStoppingCallback(early_stopping_patience=3)]
        )

        # Train and save model
        logger.info(f"Starting fine-tuning for {model_cfg.name}...", source="fine_tune_service")
        trainer.train()
        trainer.save_model(model_dir)
        logger.info(f"Model saved to {model_dir}", source="fine_tune_service")

        # Evaluate model
        evaluation_results = trainer.evaluate()
        logger.info(f"Evaluation results: {evaluation_results}", source="fine_tune_service")

        self._clear_gpu_memory()
        return {"success": True, "evaluation_results": evaluation_results, "saved_dir": model_dir}

    def _compute_metrics(self, eval_pred):
        """Compute evaluation metrics using seqeval."""
        predictions, labels = eval_pred
        predictions = predictions.argmax(axis=-1)
        true_preds, true_labels = [], []
        for pred_seq, label_seq in zip(predictions, labels):
            true_preds.append([ID2LABEL[p] for p, l in zip(pred_seq, label_seq) if l != -100])
            true_labels.append([ID2LABEL[l] for p, l in zip(pred_seq, label_seq) if l != -100])
        results = evaluate.load("seqeval").compute(predictions=true_preds, references=true_labels)
        logger.info(f"Metrics: Precision={results['overall_precision']:.4f}, Recall={results['overall_recall']:.4f}, F1={results['overall_f1']:.4f}", source="fine_tune_service")
        return results

    def _zip_model(self, model_dir: str) -> str:
        zip_path = f"{model_dir}.zip"
        os.system(f"zip -r {zip_path} {model_dir}")
        logger.info(
            f"Zipped model directory: {zip_path}",
            source="finetune._zip_model",
            category="storage",
            event_type="model_zipped"
        )
        return zip_path

    @staticmethod
    def _sanitize_name(name: str) -> str:
        return name.replace("/", "_").replace(" ", "_")
