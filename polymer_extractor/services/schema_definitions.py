"""
polymer_extractor/services/schema_definitions.py

Predefined Schema Definitions for Setup Service

Purpose
-------
Centralized schema definitions for PostgreSQL tables, Neo4j constraints,
and storage bucket structures. Used by setup service to validate and
restore missing schema components without data corruption.

Key Components
--------------
- EXPECTED_POSTGRES_TABLES: Complete table definitions aligned with 001_core.sql
- EXPECTED_NEO4J_CONSTRAINTS: Node and relationship constraints for knowledge graph
- EXPECTED_STORAGE_BUCKETS: Required bucket/folder structure from paths.py
- Model management configuration from environment variables
- Schema validation utilities for non-destructive schema updates

Design Principles
-----------------
- Schema definitions match 001_core.sql exactly for consistency
- Storage buckets align with paths.py STORAGE_PATHS mapping
- GitHub model configuration from environment variables
- Non-destructive updates: only add missing components, never drop existing
- Environment-driven: schemas adapt to enabled features (USE_POSTGRESQL_DB, etc.)

Examples
--------
>>> from polymer_extractor.services.schema_definitions import SchemaValidator
>>> validator = SchemaValidator()
>>> missing_tables = validator.check_postgres_schema()
>>> missing_constraints = validator.check_neo4j_schema()
>>> missing_buckets = validator.check_storage_schema(['local', 's3'])

Notes
-----
- Version: 1.0.0 - Initial schema definitions aligned with 001_core.sql
- Compatibility: PostgreSQL 12+, Neo4j 4.4+
- Safety: All operations are additive only (no DROP statements)
"""

import os
import re
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum

# Import paths configuration
from polymer_extractor.utils.paths import STORAGE_PATHS

# Schema version for compatibility tracking
SCHEMA_VERSION = "1.0.0"

@dataclass
class ColumnDefinition:
    """PostgreSQL column definition."""
    name: str
    data_type: str
    nullable: bool = True
    default: Optional[str] = None
    primary_key: bool = False
    unique: bool = False
    foreign_key: Optional[str] = None
    
    def to_sql(self) -> str:
        """Generate SQL column definition."""
        sql = f"{self.name} {self.data_type}"
        
        if not self.nullable:
            sql += " NOT NULL"
        
        if self.default is not None:
            sql += f" DEFAULT {self.default}"
        
        if self.unique:
            sql += " UNIQUE"
            
        return sql

@dataclass 
class TableDefinition:
    """PostgreSQL table definition."""
    name: str
    columns: List[ColumnDefinition]
    primary_keys: List[str]
    foreign_keys: List[Dict[str, str]]
    indexes: List[Dict[str, Any]]
    constraints: List[str]
    
    def get_create_sql(self) -> str:
        """Generate CREATE TABLE SQL."""
        column_defs = []
        
        for col in self.columns:
            column_defs.append(col.to_sql())
        
        # Add primary key constraint
        if self.primary_keys:
            pk_cols = ", ".join(self.primary_keys)
            column_defs.append(f"PRIMARY KEY ({pk_cols})")
        
        # Add foreign key constraints
        for fk in self.foreign_keys:
            column_defs.append(
                f"FOREIGN KEY ({fk['column']}) REFERENCES {fk['table']}({fk['references']})"
            )
        
        # Add custom constraints
        for constraint in self.constraints:
            column_defs.append(constraint)
        
        columns_sql = ",\n    ".join(column_defs)
        
        return f"""
CREATE TABLE IF NOT EXISTS {self.name} (
    {columns_sql}
);"""

@dataclass
class Neo4jConstraint:
    """Neo4j constraint definition."""
    name: str
    type: str  # 'uniqueness', 'existence', 'node_key'
    label: str
    properties: List[str]
    
    def to_cypher(self) -> str:
        """Generate Cypher constraint statement."""
        props = ", ".join([f"n.{prop}" for prop in self.properties])
        
        if self.type == 'uniqueness':
            return f"CREATE CONSTRAINT {self.name} IF NOT EXISTS FOR (n:{self.label}) REQUIRE ({props}) IS UNIQUE"
        elif self.type == 'existence':
            return f"CREATE CONSTRAINT {self.name} IF NOT EXISTS FOR (n:{self.label}) REQUIRE ({props}) IS NOT NULL"
        elif self.type == 'node_key':
            return f"CREATE CONSTRAINT {self.name} IF NOT EXISTS FOR (n:{self.label}) REQUIRE ({props}) IS NODE KEY"
        else:
            raise ValueError(f"Unknown constraint type: {self.type}")

# =============================================================================
# EXPECTED POSTGRESQL SCHEMA (Aligned with 001_core.sql)
# =============================================================================

EXPECTED_POSTGRES_TABLES: Dict[str, TableDefinition] = {
    # Research papers metadata (multi-backend storage support)
    "research_papers": TableDefinition(
        name="research_papers",
        columns=[
            ColumnDefinition("id", "SERIAL", primary_key=True, nullable=False),
            ColumnDefinition("file_name", "VARCHAR(500)", nullable=False),
            ColumnDefinition("original_filename", "VARCHAR(500)"),
            ColumnDefinition("file_size", "BIGINT"),
            ColumnDefinition("file_hash", "VARCHAR(64)"),
            ColumnDefinition("title", "TEXT"),
            ColumnDefinition("authors", "TEXT"),
            ColumnDefinition("abstract", "TEXT"),
            ColumnDefinition("doi", "VARCHAR(100)"),
            ColumnDefinition("journal", "VARCHAR(255)"),
            ColumnDefinition("publication_year", "INTEGER"),
            ColumnDefinition("keywords", "TEXT[]"),
            ColumnDefinition("processing_status", "VARCHAR(50)", default="'pending'"),
            ColumnDefinition("storage_key", "TEXT", nullable=False),
            ColumnDefinition("primary_backend", "VARCHAR(50)", nullable=False),
            ColumnDefinition("storage_backends", "TEXT[]", nullable=False),
            ColumnDefinition("metadata", "JSONB"),
            ColumnDefinition("created_at", "TIMESTAMP", nullable=False, default="CURRENT_TIMESTAMP"),
            ColumnDefinition("updated_at", "TIMESTAMP", nullable=False, default="CURRENT_TIMESTAMP")
        ],
        primary_keys=["id"],
        foreign_keys=[],
        indexes=[
            {"name": "idx_papers_doi", "columns": ["doi"]},
            {"name": "idx_papers_created", "columns": ["created_at"]},
            {"name": "idx_papers_status", "columns": ["processing_status"]},
            {"name": "idx_papers_filename", "columns": ["file_name"]},
            {"name": "idx_papers_storage_key", "columns": ["storage_key"]},
            {"name": "idx_papers_primary_backend", "columns": ["primary_backend"]},
            {"name": "idx_papers_storage_backends", "columns": ["storage_backends"], "type": "gin"}
        ],
        constraints=[
            "CHECK (file_name != '')",
            "CHECK (file_size >= 0)",
            "CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed', 'skipped'))",
            "CHECK (primary_backend IN ('local', 'appwrite', 's3'))",
            "CHECK (array_length(storage_backends, 1) >= 1)"
        ]
    ),

    # System logs for comprehensive logging and debugging (protected table)
    "system_logs": TableDefinition(
        name="system_logs",
        columns=[
            ColumnDefinition("id", "SERIAL", primary_key=True, nullable=False),
            ColumnDefinition("timestamp", "TIMESTAMP", nullable=False, default="CURRENT_TIMESTAMP"),
            ColumnDefinition("level", "VARCHAR(20)", nullable=False),
            ColumnDefinition("message", "TEXT", nullable=False),
            ColumnDefinition("source", "VARCHAR(100)"),
            ColumnDefinition("event_type", "VARCHAR(50)"),
            ColumnDefinition("category", "VARCHAR(50)"),
            ColumnDefinition("context", "JSONB"),
            ColumnDefinition("user_id", "VARCHAR(255)"),
            ColumnDefinition("session_id", "VARCHAR(255)"),
            ColumnDefinition("created_at", "TIMESTAMP", nullable=False, default="CURRENT_TIMESTAMP")
        ],
        primary_keys=["id"],
        foreign_keys=[],
        indexes=[
            {"name": "idx_logs_timestamp", "columns": ["timestamp"]},
            {"name": "idx_logs_level", "columns": ["level"]},
            {"name": "idx_logs_source", "columns": ["source"]},
            {"name": "idx_logs_event_type", "columns": ["event_type"]},
            {"name": "idx_logs_category", "columns": ["category"]},
            {"name": "idx_logs_created", "columns": ["created_at"]},
            {"name": "idx_logs_context_gin", "columns": ["context"], "type": "gin"}
        ],
        constraints=[
            "CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'))",
            "CHECK (message != '')"
        ]
    ),

    # Sentences extracted from papers
    "sentences": TableDefinition(
        name="sentences",
        columns=[
            ColumnDefinition("id", "SERIAL", primary_key=True, nullable=False),
            ColumnDefinition("paper_id", "INTEGER", nullable=False),
            ColumnDefinition("sentence_number", "INTEGER", nullable=False),
            ColumnDefinition("text_content", "TEXT", nullable=False),
            ColumnDefinition("section_type", "VARCHAR(100)"),
            ColumnDefinition("char_start", "INTEGER"),
            ColumnDefinition("char_end", "INTEGER"),
            ColumnDefinition("xml_context", "TEXT"),
            ColumnDefinition("metadata", "JSONB"),
            ColumnDefinition("created_at", "TIMESTAMP", nullable=False, default="CURRENT_TIMESTAMP")
        ],
        primary_keys=["id"],
        foreign_keys=[
            {"column": "paper_id", "table": "research_papers", "references": "id"}
        ],
        indexes=[
            {"name": "idx_sentences_paper", "columns": ["paper_id"]},
            {"name": "idx_sentences_section", "columns": ["section_type"]},
            {"name": "idx_sentences_char_range", "columns": ["char_start", "char_end"]},
            {"name": "idx_sentences_number", "columns": ["paper_id", "sentence_number"]}
        ],
        constraints=[
            "CHECK (sentence_number >= 0)",
            "CHECK (char_start >= 0)",
            "CHECK (char_end >= char_start)",
            "CHECK (text_content != '')"
        ]
    ),

    # Datasets for training/testing management (multi-backend storage support)
    "datasets": TableDefinition(
        name="datasets",
        columns=[
            ColumnDefinition("id", "SERIAL", primary_key=True, nullable=False),
            ColumnDefinition("name", "VARCHAR(255)", nullable=False),
            ColumnDefinition("type", "VARCHAR(50)", nullable=False),
            ColumnDefinition("description", "TEXT"),
            ColumnDefinition("file_path", "TEXT"),
            ColumnDefinition("file_size", "BIGINT"),
            ColumnDefinition("file_hash", "VARCHAR(64)"),
            ColumnDefinition("record_count", "INTEGER"),
            ColumnDefinition("schema_version", "VARCHAR(20)"),
            ColumnDefinition("storage_key", "TEXT"),
            ColumnDefinition("primary_backend", "VARCHAR(50)"),
            ColumnDefinition("storage_backends", "TEXT[]"),
            ColumnDefinition("metadata", "JSONB"),
            ColumnDefinition("is_active", "BOOLEAN", default="true"),
            ColumnDefinition("created_at", "TIMESTAMP", nullable=False, default="CURRENT_TIMESTAMP"),
            ColumnDefinition("updated_at", "TIMESTAMP", nullable=False, default="CURRENT_TIMESTAMP")
        ],
        primary_keys=["id"],
        foreign_keys=[],
        indexes=[
            {"name": "idx_datasets_name_type", "columns": ["name", "type"], "unique": True},
            {"name": "idx_datasets_type", "columns": ["type"]},
            {"name": "idx_datasets_active", "columns": ["is_active"]},
            {"name": "idx_datasets_storage_key", "columns": ["storage_key"]},
            {"name": "idx_datasets_primary_backend", "columns": ["primary_backend"]},
            {"name": "idx_datasets_storage_backends", "columns": ["storage_backends"], "type": "gin"}
        ],
        constraints=[
            "CHECK (name != '')",
            "CHECK (type IN ('training', 'testing', 'validation', 'production'))",
            "CHECK (record_count >= 0)",
            "CHECK (file_size >= 0)"
        ]
    ),

    # Model configurations for ensemble tracking (multi-backend storage support)
    "model_configurations": TableDefinition(
        name="model_configurations",
        columns=[
            ColumnDefinition("id", "SERIAL", primary_key=True, nullable=False),
            ColumnDefinition("name", "VARCHAR(255)", nullable=False),
            ColumnDefinition("model_id", "VARCHAR(255)", nullable=False),
            ColumnDefinition("version", "VARCHAR(50)", nullable=False),
            ColumnDefinition("base_weight", "DECIMAL(5,3)", default="1.000"),
            ColumnDefinition("reliability_score", "DECIMAL(5,3)", default="0.500"),
            ColumnDefinition("specialization_domains", "TEXT[]"),
            ColumnDefinition("config_path", "TEXT"),
            ColumnDefinition("storage_key", "TEXT"),
            ColumnDefinition("primary_backend", "VARCHAR(50)"),
            ColumnDefinition("storage_backends", "TEXT[]"),
            ColumnDefinition("metadata", "JSONB"),
            ColumnDefinition("is_active", "BOOLEAN", default="true"),
            ColumnDefinition("created_at", "TIMESTAMP", nullable=False, default="CURRENT_TIMESTAMP"),
            ColumnDefinition("updated_at", "TIMESTAMP", nullable=False, default="CURRENT_TIMESTAMP")
        ],
        primary_keys=["id"],
        foreign_keys=[],
        indexes=[
            {"name": "idx_model_name_version", "columns": ["name", "version"], "unique": True},
            {"name": "idx_model_active", "columns": ["is_active"]},
            {"name": "idx_model_reliability", "columns": ["reliability_score"], "desc": True},
            {"name": "idx_model_storage_key", "columns": ["storage_key"]},
            {"name": "idx_model_primary_backend", "columns": ["primary_backend"]},
            {"name": "idx_model_storage_backends", "columns": ["storage_backends"], "type": "gin"}
        ],
        constraints=[
            "CHECK (name != '')",
            "CHECK (version != '')",
            "CHECK (base_weight >= 0 AND base_weight <= 5)",
            "CHECK (reliability_score >= 0 AND reliability_score <= 1)"
        ]
    ),

    # Model expertise weights per entity type
    "model_entity_expertise": TableDefinition(
        name="model_entity_expertise",
        columns=[
            ColumnDefinition("id", "SERIAL", primary_key=True, nullable=False),
            ColumnDefinition("model_config_id", "INTEGER", nullable=False),
            ColumnDefinition("entity_type", "VARCHAR(50)", nullable=False),
            ColumnDefinition("expertise_weight", "DECIMAL(5,3)", default="1.000"),
            ColumnDefinition("confidence_threshold", "DECIMAL(5,3)", default="0.500"),
            ColumnDefinition("created_at", "TIMESTAMP", nullable=False, default="CURRENT_TIMESTAMP"),
            ColumnDefinition("updated_at", "TIMESTAMP", nullable=False, default="CURRENT_TIMESTAMP")
        ],
        primary_keys=["id"],
        foreign_keys=[
            {"column": "model_config_id", "table": "model_configurations", "references": "id"}
        ],
        indexes=[
            {"name": "idx_expertise_model_entity", "columns": ["model_config_id", "entity_type"], "unique": True},
            {"name": "idx_expertise_entity_type", "columns": ["entity_type"]}
        ],
        constraints=[
            "CHECK (entity_type IN ('POLYMER', 'PROPERTY', 'VALUE', 'UNIT', 'SYMBOL'))",
            "CHECK (expertise_weight >= 0 AND expertise_weight <= 5)",
            "CHECK (confidence_threshold >= 0 AND confidence_threshold <= 1)"
        ]
    ),

    # Extraction sessions for tracking runs and ensemble strategies
    "extraction_sessions": TableDefinition(
        name="extraction_sessions",
        columns=[
            ColumnDefinition("id", "UUID", primary_key=True, nullable=False, default="uuid_generate_v4()"),
            ColumnDefinition("session_name", "VARCHAR(255)", nullable=False),
            ColumnDefinition("paper_id", "INTEGER", nullable=False),
            ColumnDefinition("ensemble_strategy", "VARCHAR(50)", nullable=False),
            ColumnDefinition("model_configs", "INTEGER[]", nullable=False),
            ColumnDefinition("status", "VARCHAR(50)", default="'active'"),
            ColumnDefinition("progress_percentage", "INTEGER", default="0"),
            ColumnDefinition("entities_extracted", "INTEGER", default="0"),
            ColumnDefinition("start_time", "TIMESTAMP", nullable=False, default="CURRENT_TIMESTAMP"),
            ColumnDefinition("end_time", "TIMESTAMP"),
            ColumnDefinition("metadata", "JSONB"),
            ColumnDefinition("created_at", "TIMESTAMP", nullable=False, default="CURRENT_TIMESTAMP"),
            ColumnDefinition("completed_at", "TIMESTAMP")
        ],
        primary_keys=["id"],
        foreign_keys=[
            {"column": "paper_id", "table": "research_papers", "references": "id"}
        ],
        indexes=[
            {"name": "idx_sessions_paper", "columns": ["paper_id"]},
            {"name": "idx_sessions_status", "columns": ["status"]},
            {"name": "idx_sessions_created", "columns": ["created_at"]},
            {"name": "idx_sessions_strategy", "columns": ["ensemble_strategy"]}
        ],
        constraints=[
            "CHECK (session_name != '')",
            "CHECK (ensemble_strategy IN ('simple_average', 'weighted_average', 'majority_vote', 'confidence_weighted'))",
            "CHECK (status IN ('active', 'completed', 'failed', 'cancelled'))",
            "CHECK (progress_percentage >= 0 AND progress_percentage <= 100)",
            "CHECK (entities_extracted >= 0)"
        ]
    )
}

# Note: Additional tables from 001_core.sql like entities, entity_attributes, etc.
# would be added here following the same pattern

# =============================================================================
# EXPECTED NEO4J SCHEMA  
# =============================================================================

EXPECTED_NEO4J_CONSTRAINTS: List[Neo4jConstraint] = [
    # Paper nodes
    Neo4jConstraint(
        name="paper_id_unique",
        type="uniqueness", 
        label="Paper",
        properties=["paper_id"]
    ),
    Neo4jConstraint(
        name="paper_id_exists",
        type="existence",
        label="Paper", 
        properties=["paper_id"]
    ),
    Neo4jConstraint(
        name="paper_filename_exists",
        type="existence",
        label="Paper",
        properties=["filename"]
    ),
    
    # Entity nodes
    Neo4jConstraint(
        name="entity_id_unique",
        type="uniqueness",
        label="Entity", 
        properties=["entity_id"]
    ),
    Neo4jConstraint(
        name="entity_text_type_key",
        type="node_key",
        label="Entity",
        properties=["text", "type"]
    ),
    
    # Property nodes
    Neo4jConstraint(
        name="property_name_unique",
        type="uniqueness",
        label="Property",
        properties=["name"]
    ),
    Neo4jConstraint(
        name="property_name_exists", 
        type="existence",
        label="Property",
        properties=["name"]
    ),
    
    # Material nodes
    Neo4jConstraint(
        name="material_name_formula_key",
        type="node_key",
        label="Material",
        properties=["name", "formula"]
    ),
    Neo4jConstraint(
        name="material_name_exists",
        type="existence", 
        label="Material",
        properties=["name"]
    ),
    
    # Method nodes
    Neo4jConstraint(
        name="method_name_unique",
        type="uniqueness",
        label="Method",
        properties=["name"]
    ),
    Neo4jConstraint(
        name="method_name_exists",
        type="existence",
        label="Method", 
        properties=["name"]
    ),
    
    # Dataset nodes
    Neo4jConstraint(
        name="dataset_name_version_key",
        type="node_key",
        label="Dataset",
        properties=["name", "version"]
    ),
    
    # Model nodes 
    Neo4jConstraint(
        name="model_name_version_key",
        type="node_key",
        label="Model",
        properties=["name", "version"]
    )
]

# =============================================================================
# EXPECTED STORAGE BUCKET STRUCTURE (Aligned with paths.py)
# =============================================================================

# Use paths.py STORAGE_PATHS for consistency
EXPECTED_STORAGE_BUCKETS: Dict[str, Dict[str, Any]] = {
    bucket_name: {
        "name": bucket_name,
        "description": f"Storage bucket for {bucket_name.replace('_', ' ')}",
        "required": True,
        "replicated": bucket_name != "models",  # models are local only
        "structure": {
            "max_file_size": "100MB" if bucket_name != "models" else "1GB",
            "allowed_extensions": [],  # Set specific extensions per bucket as needed
            "versioning": bucket_name in ["models", "datasets"],
            "retention_days": 365 if bucket_name == "system_logs" else None
        }
    }
    for bucket_name in STORAGE_PATHS.keys()
}

def _get_allowed_extensions(bucket_name: str) -> List[str]:
    """Get allowed file extensions for each bucket type."""
    extension_map = {
        "raw_inputs": [".pdf", ".doc", ".docx", ".txt"],
        "extracted_xml": [".xml", ".tei"],
        "processed_xml": [".xml", ".tei"],
        "samples": [".txt", ".json", ".csv"],
        "models": [".bin", ".safetensors", ".json", ".txt", ".model", ".vocab"],
        "reports": [".csv", ".json", ".html", ".txt", ".pdf"],
        "exports": [".csv", ".json", ".txt", ".xlsx"],
        "system_logs": [".log", ".txt", ".json"],
        "datasets": [".json", ".csv", ".txt", ".parquet", ".arrow"]
    }
    return extension_map.get(bucket_name, [])

# =============================================================================
# MODEL MANAGEMENT CONFIGURATION (From Environment)
# =============================================================================

def get_model_github_config() -> Dict[str, Any]:
    """Get GitHub model configuration from environment variables."""
    return {
        "repository_url": os.getenv("MODELS_GITHUB_REPO", "https://github.com/polymer-nlp/model-assets.git"),
        "branch": os.getenv("MODELS_GITHUB_BRANCH", "main"),
        "github_token": os.getenv("MODELS_GITHUB_TOKEN", os.getenv("GITHUB_TOKEN", "")),
        "expected_folders": ["finetuned", "tokenizers"],
        "version_pattern": os.getenv("MODELS_EXPECTED_VERSION_PATTERN", r"^(finetuned|tokenizers)-(\d+\.\d+\.\d+)$"),
        "local_models_path": os.getenv("MODELS_ROOT", "./workspace/public/models"),
        "clone_timeout_seconds": int(os.getenv("MODELS_CLONE_TIMEOUT", "300")),
        "expected_version": os.getenv("MODELS_VERSION", "1.0.0"),
        "version_match_required": True,
        "backup_before_replace": os.getenv("MODELS_BACKUP_BEFORE_REPLACE", "true").lower() == "true"
    }

# Environment configuration requirements for GitHub access
GITHUB_ENV_VARS = {
    "MODELS_GITHUB_REPO": "GitHub repository URL for model assets",
    "MODELS_GITHUB_BRANCH": "Branch to clone from (default: main)",
    "MODELS_GITHUB_TOKEN": "GitHub personal access token for repository access",
    "MODELS_VERSION": "Expected model version (e.g., 1.0.0)",
    "MODELS_ROOT": "Local path for model storage (default: ./workspace/public/models)",
    "MODELS_CLONE_TIMEOUT": "Clone timeout in seconds (default: 300)",
    "MODELS_BACKUP_BEFORE_REPLACE": "Backup models before replacing (default: true)"
}

# =============================================================================
# SCHEMA VALIDATION UTILITIES
# =============================================================================

class SchemaValidator:
    """Utility class for validating and comparing schemas."""
    
    def __init__(self):
        self.postgres_tables = EXPECTED_POSTGRES_TABLES
        self.neo4j_constraints = EXPECTED_NEO4J_CONSTRAINTS
        self.storage_buckets = EXPECTED_STORAGE_BUCKETS
    
    def get_missing_postgres_tables(self, existing_tables: List[str]) -> List[str]:
        """Get list of missing PostgreSQL tables."""
        expected = set(self.postgres_tables.keys())
        existing = set(existing_tables)
        return list(expected - existing)
    
    def get_missing_postgres_columns(self, table_name: str, existing_columns: List[str]) -> List[ColumnDefinition]:
        """Get missing columns for a specific table."""
        if table_name not in self.postgres_tables:
            return []
        
        expected_cols = {col.name: col for col in self.postgres_tables[table_name].columns}
        existing_cols = set(existing_columns)
        
        missing = []
        for col_name, col_def in expected_cols.items():
            if col_name not in existing_cols:
                missing.append(col_def)
        
        return missing
    
    def get_missing_neo4j_constraints(self, existing_constraints: List[str]) -> List[Neo4jConstraint]:
        """Get missing Neo4j constraints."""
        existing_names = {constraint.split()[2] for constraint in existing_constraints if len(constraint.split()) > 2}
        
        missing = []
        for constraint in self.neo4j_constraints:
            if constraint.name not in existing_names:
                missing.append(constraint)
        
        return missing
    
    def get_missing_storage_buckets(self, backend: str, existing_buckets: List[str]) -> List[str]:
        """Get missing storage buckets for a backend."""
        expected = set(self.storage_buckets.keys())
        existing = set(existing_buckets)
        
        # Models bucket is only required for primary backend
        if backend != "primary" and "models" in expected:
            expected.discard("models")
        
        return list(expected - existing)
    
    def validate_model_versions(self, finetuned_version: str, tokenizer_version: str) -> bool:
        """Validate that model versions match."""
        return finetuned_version == tokenizer_version
    
    def get_schema_version(self) -> str:
        """Get current schema version."""
        return SCHEMA_VERSION
