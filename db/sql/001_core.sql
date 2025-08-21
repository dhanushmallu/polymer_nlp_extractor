-- ================================================================
-- PostgreSQL Schema for Polymer NLP Extractor
-- Version: 2.0 - Multi-Backend Storage Support
-- Created: 2025-08-20
-- Purpose: Core database schema supporting multiple concurrent storage backends
-- Notes: Supports local, Appwrite, and S3 storage with flexible strategies
-- ================================================================

-- Drop existing tables if they exist (for clean migrations)
DROP TABLE IF EXISTS performance_metrics CASCADE;
DROP TABLE IF EXISTS validation_logs CASCADE;
DROP TABLE IF EXISTS kg_relationship_cache CASCADE;
DROP TABLE IF EXISTS property_measurements CASCADE;
DROP TABLE IF EXISTS value_unit_pairs CASCADE;
DROP TABLE IF EXISTS entity_relationships CASCADE;
DROP TABLE IF EXISTS entity_attributes CASCADE;
DROP TABLE IF EXISTS entities CASCADE;
DROP TABLE IF EXISTS model_entity_expertise CASCADE;
DROP TABLE IF EXISTS model_configurations CASCADE;
DROP TABLE IF EXISTS extraction_sessions CASCADE;
DROP TABLE IF EXISTS sentences CASCADE;
DROP TABLE IF EXISTS datasets CASCADE;
DROP TABLE IF EXISTS research_papers CASCADE;
DROP TABLE IF EXISTS system_logs CASCADE;

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ================================================================
-- 1. CORE METADATA TABLES
-- ================================================================

-- Research papers metadata (multi-backend storage support)
CREATE TABLE research_papers (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(255) UNIQUE NOT NULL,
    doi VARCHAR(255),
    title TEXT,
    authors TEXT NOT NULL,
    journal VARCHAR(255),
    publication_date DATE,
    abstract TEXT,
    grobid_version VARCHAR(50),
    -- Multi-backend storage references
    storage_key VARCHAR(500), -- Primary storage reference (used by StorageManager)
    local_path VARCHAR(500), -- Local storage path (when local backend active)
    appwrite_file_id VARCHAR(255), -- Appwrite storage ID (when appwrite backend active)
    s3_key VARCHAR(500), -- S3 object key (when s3 backend active)
    storage_backends TEXT[], -- Array of active backends for this file ['local', 'appwrite', 's3']
    primary_backend VARCHAR(20), -- Primary backend used for this file
    file_size BIGINT,
    processing_status VARCHAR(20) DEFAULT 'pending' CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_papers_doi ON research_papers(doi);
CREATE INDEX idx_papers_created ON research_papers(created_at);
CREATE INDEX idx_papers_status ON research_papers(processing_status);
CREATE INDEX idx_papers_filename ON research_papers(file_name);
CREATE INDEX idx_papers_storage_key ON research_papers(storage_key);
CREATE INDEX idx_papers_primary_backend ON research_papers(primary_backend);
CREATE INDEX idx_papers_storage_backends ON research_papers USING GIN(storage_backends);

-- System logs for comprehensive logging and debugging
CREATE TABLE system_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level VARCHAR(20) NOT NULL CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    message TEXT NOT NULL,
    source VARCHAR(255),
    event_type VARCHAR(100) DEFAULT 'general',
    user_action BOOLEAN DEFAULT false,
    context JSONB,
    stack_trace TEXT,
    file_name VARCHAR(255),
    line_number INTEGER,
    category VARCHAR(50) DEFAULT 'system',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_logs_timestamp ON system_logs(timestamp);
CREATE INDEX idx_logs_level ON system_logs(level);
CREATE INDEX idx_logs_source ON system_logs(source);
CREATE INDEX idx_logs_event_type ON system_logs(event_type);
CREATE INDEX idx_logs_category ON system_logs(category);
CREATE INDEX idx_logs_created ON system_logs(created_at);
CREATE INDEX idx_logs_context_gin ON system_logs USING GIN(context);

-- Sentences extracted from papers
CREATE TABLE sentences (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER REFERENCES research_papers(id) ON DELETE CASCADE,
    sentence_number INTEGER NOT NULL,
    text_content TEXT NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    token_count INTEGER,
    section_type VARCHAR(100),
    section_header TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sentences_paper ON sentences(paper_id);
CREATE INDEX idx_sentences_section ON sentences(section_type);
CREATE INDEX idx_sentences_char_range ON sentences(char_start, char_end);
CREATE INDEX idx_sentences_number ON sentences(paper_id, sentence_number);

-- Datasets for training/testing management (multi-backend storage support)
CREATE TABLE datasets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(20) CHECK (type IN ('training', 'testing', 'validation')) NOT NULL,
    source_file VARCHAR(255),
    -- Multi-backend storage references
    storage_key VARCHAR(500), -- Primary storage reference (used by StorageManager)
    local_path VARCHAR(500), -- Local storage path (when local backend active)
    appwrite_file_id VARCHAR(255), -- Appwrite storage ID (when appwrite backend active)
    s3_key VARCHAR(500), -- S3 object key (when s3 backend active)
    storage_backends TEXT[], -- Array of active backends for this dataset ['local', 'appwrite', 's3']
    primary_backend VARCHAR(20), -- Primary backend used for this dataset
    total_entities INTEGER DEFAULT 0,
    total_sentences INTEGER DEFAULT 0,
    annotation_format VARCHAR(50),
    quality_score DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

CREATE UNIQUE INDEX idx_datasets_name_type ON datasets(name, type);
CREATE INDEX idx_datasets_type ON datasets(type);
CREATE INDEX idx_datasets_active ON datasets(is_active);
CREATE INDEX idx_datasets_storage_key ON datasets(storage_key);
CREATE INDEX idx_datasets_primary_backend ON datasets(primary_backend);
CREATE INDEX idx_datasets_storage_backends ON datasets USING GIN(storage_backends);

-- ================================================================
-- 2. MODEL CONFIGURATION TABLES
-- ================================================================

-- Model configurations for ensemble tracking
CREATE TABLE model_configurations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    model_id VARCHAR(255) NOT NULL,
    version VARCHAR(50) DEFAULT 'v1.0',
    base_weight DECIMAL(4,2) DEFAULT 1.00 CHECK (base_weight >= 0.00 AND base_weight <= 2.00),
    reliability_score DECIMAL(3,2) DEFAULT 0.50 CHECK (reliability_score >= 0.00 AND reliability_score <= 1.00),
    specialization_domains TEXT[],
    tokenizer_config JSONB,
    model_parameters JSONB,
    training_details JSONB,
    -- Multi-backend storage references for model files
    storage_key VARCHAR(500), -- Primary storage reference (used by StorageManager)
    local_path VARCHAR(500), -- Local storage path (when local backend active)
    appwrite_file_id VARCHAR(255), -- Appwrite storage ID (when appwrite backend active)
    s3_key VARCHAR(500), -- S3 object key (when s3 backend active)
    storage_backends TEXT[], -- Array of active backends for this model ['local', 'appwrite', 's3']
    primary_backend VARCHAR(20), -- Primary backend used for this model
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_model_name_version ON model_configurations(name, version);
CREATE INDEX idx_model_active ON model_configurations(is_active);
CREATE INDEX idx_model_reliability ON model_configurations(reliability_score DESC);
CREATE INDEX idx_model_storage_key ON model_configurations(storage_key);
CREATE INDEX idx_model_primary_backend ON model_configurations(primary_backend);
CREATE INDEX idx_model_storage_backends ON model_configurations USING GIN(storage_backends);

-- Model expertise weights per entity type
CREATE TABLE model_entity_expertise (
    id SERIAL PRIMARY KEY,
    model_config_id INTEGER REFERENCES model_configurations(id) ON DELETE CASCADE,
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('POLYMER', 'PROPERTY', 'VALUE', 'UNIT', 'SYMBOL')),
    expertise_weight DECIMAL(4,2) DEFAULT 1.00 CHECK (expertise_weight >= 0.00 AND expertise_weight <= 2.00),
    confidence_threshold DECIMAL(3,2) DEFAULT 0.50 CHECK (confidence_threshold >= 0.00 AND confidence_threshold <= 1.00),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_expertise_model_entity ON model_entity_expertise(model_config_id, entity_type);
CREATE INDEX idx_expertise_entity_type ON model_entity_expertise(entity_type);

-- ================================================================
-- 3. EXTRACTION SESSION MANAGEMENT
-- ================================================================

-- Extraction sessions for tracking runs and ensemble strategies
CREATE TABLE extraction_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_name VARCHAR(255) NOT NULL,
    paper_id INTEGER REFERENCES research_papers(id) ON DELETE CASCADE,
    model_ids INTEGER[],
    ensemble_strategy VARCHAR(50) DEFAULT 'weighted_voting' CHECK (ensemble_strategy IN ('weighted_voting', 'max_confidence', 'unanimous', 'majority')),
    confidence_threshold DECIMAL(3,2) DEFAULT 0.50,
    total_entities INTEGER DEFAULT 0,
    total_processed_sentences INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    error_message TEXT,
    processing_time_ms BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_sessions_paper ON extraction_sessions(paper_id);
CREATE INDEX idx_sessions_status ON extraction_sessions(status);
CREATE INDEX idx_sessions_created ON extraction_sessions(created_at);
CREATE INDEX idx_sessions_strategy ON extraction_sessions(ensemble_strategy);

-- ================================================================
-- 4. UNIFIED ENTITY STORAGE
-- ================================================================

-- Unified entity structure for all entity types
CREATE TABLE entities (
    id SERIAL PRIMARY KEY,
    sentence_id INTEGER REFERENCES sentences(id) ON DELETE CASCADE,
    session_id UUID REFERENCES extraction_sessions(id) ON DELETE CASCADE,
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('POLYMER', 'PROPERTY', 'VALUE', 'UNIT', 'SYMBOL')),
    text_content TEXT NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    confidence_score DECIMAL(6,4) NOT NULL,
    model_source VARCHAR(100) NOT NULL,
    model_weight DECIMAL(4,2),
    data_type VARCHAR(20) DEFAULT 'extracted' CHECK (data_type IN ('training', 'testing', 'extracted')) NOT NULL,
    dataset_id INTEGER REFERENCES datasets(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance indexes for entities (proper ordering after table creation)
CREATE INDEX idx_entities_sentence ON entities(sentence_id);
CREATE INDEX idx_entities_session ON entities(session_id);
CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_confidence ON entities(confidence_score DESC);
CREATE INDEX idx_entities_data_type ON entities(data_type);
CREATE INDEX idx_entities_char_range ON entities(char_start, char_end);
CREATE INDEX idx_entities_text ON entities(text_content);

-- Enhanced full-text search indexes
CREATE INDEX idx_entities_text_gin ON entities USING GIN(to_tsvector('english', text_content));
CREATE INDEX idx_entities_text_trigram ON entities USING GIN(text_content gin_trgm_ops);
CREATE INDEX idx_entities_text_lower ON entities(LOWER(text_content));
CREATE INDEX idx_entities_text_length ON entities(LENGTH(text_content));

-- Composite indexes for common queries
CREATE INDEX idx_entities_type_confidence ON entities(entity_type, confidence_score DESC);
CREATE INDEX idx_entities_session_type ON entities(session_id, entity_type);
CREATE INDEX idx_entities_sentence_type ON entities(sentence_id, entity_type);

-- ================================================================
-- 5. ENTITY ENHANCEMENT TABLES
-- ================================================================

-- Entity attributes for normalization and KG enhancement
CREATE TABLE entity_attributes (
    id SERIAL PRIMARY KEY,
    entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    canonical_form TEXT,
    synonyms TEXT[],
    confidence_boost DECIMAL(4,3) DEFAULT 0.000,
    validation_status VARCHAR(20) DEFAULT 'pending' CHECK (validation_status IN ('pending', 'validated', 'corrected', 'rejected')),
    validation_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_attributes_entity ON entity_attributes(entity_id);
CREATE INDEX idx_attributes_canonical ON entity_attributes(canonical_form);
CREATE INDEX idx_attributes_status ON entity_attributes(validation_status);

-- ================================================================
-- 6. SEMANTIC RELATIONSHIP TABLES
-- ================================================================

-- Generic entity relationships for complex semantic modeling
CREATE TABLE entity_relationships (
    id SERIAL PRIMARY KEY,
    entity1_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    entity2_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL,
    relationship_confidence DECIMAL(6,4) NOT NULL,
    distance_tokens INTEGER,
    context_window TEXT,
    sentence_id INTEGER REFERENCES sentences(id) ON DELETE CASCADE,
    session_id UUID REFERENCES extraction_sessions(id) ON DELETE CASCADE,
    validation_status VARCHAR(20) DEFAULT 'pending' CHECK (validation_status IN ('pending', 'validated', 'rejected')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_entity_rel_entity1 ON entity_relationships(entity1_id);
CREATE INDEX idx_entity_rel_entity2 ON entity_relationships(entity2_id);
CREATE INDEX idx_entity_rel_type ON entity_relationships(relationship_type);
CREATE INDEX idx_entity_rel_confidence ON entity_relationships(relationship_confidence DESC);
CREATE INDEX idx_entity_rel_sentence ON entity_relationships(sentence_id);
CREATE INDEX idx_entity_rel_session ON entity_relationships(session_id);
CREATE INDEX idx_entity_rel_validation ON entity_relationships(validation_status);
CREATE UNIQUE INDEX idx_entity_rel_unique ON entity_relationships(entity1_id, entity2_id, relationship_type);

-- Value-Unit relationships (most common semantic pair)
CREATE TABLE value_unit_pairs (
    id SERIAL PRIMARY KEY,
    value_entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    unit_entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    numerical_value DECIMAL(15,6),
    unit_canonical TEXT,
    relationship_confidence DECIMAL(6,4) NOT NULL,
    distance_tokens INTEGER,
    sentence_id INTEGER REFERENCES sentences(id) ON DELETE CASCADE,
    session_id UUID REFERENCES extraction_sessions(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_value_unit_unique ON value_unit_pairs(value_entity_id, unit_entity_id);
CREATE INDEX idx_value_unit_sentence ON value_unit_pairs(sentence_id);
CREATE INDEX idx_value_unit_session ON value_unit_pairs(session_id);
CREATE INDEX idx_value_unit_confidence ON value_unit_pairs(relationship_confidence DESC);

-- Property-Value-Unit semantic triples
CREATE TABLE property_measurements (
    id SERIAL PRIMARY KEY,
    property_entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    value_entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    unit_entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    measurement_type VARCHAR(50),
    measurement_confidence DECIMAL(6,4) NOT NULL,
    context_sentence_id INTEGER REFERENCES sentences(id) ON DELETE CASCADE,
    session_id UUID REFERENCES extraction_sessions(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_prop_measurements_property ON property_measurements(property_entity_id);
CREATE INDEX idx_prop_measurements_value ON property_measurements(value_entity_id);
CREATE INDEX idx_prop_measurements_unit ON property_measurements(unit_entity_id);
CREATE INDEX idx_prop_measurements_sentence ON property_measurements(context_sentence_id);
CREATE INDEX idx_prop_measurements_session ON property_measurements(session_id);

-- ================================================================
-- 7. VALIDATION AND PERFORMANCE TRACKING
-- ================================================================

-- Validation logs for quality assurance
CREATE TABLE validation_logs (
    id SERIAL PRIMARY KEY,
    entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    session_id UUID REFERENCES extraction_sessions(id) ON DELETE CASCADE,
    validation_type VARCHAR(100) NOT NULL,
    validation_passed BOOLEAN NOT NULL,
    confidence_adjustment DECIMAL(4,3) DEFAULT 0.000,
    validation_details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_validation_entity ON validation_logs(entity_id);
CREATE INDEX idx_validation_session ON validation_logs(session_id);
CREATE INDEX idx_validation_type ON validation_logs(validation_type);
CREATE INDEX idx_validation_passed ON validation_logs(validation_passed);

-- Performance metrics tracking
CREATE TABLE performance_metrics (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES extraction_sessions(id) ON DELETE CASCADE,
    entity_type VARCHAR(20),
    model_name VARCHAR(100),
    metric_name VARCHAR(50) NOT NULL,
    metric_value DECIMAL(6,4) NOT NULL,
    sample_size INTEGER,
    threshold_used DECIMAL(4,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_metrics_session ON performance_metrics(session_id);
CREATE INDEX idx_metrics_type ON performance_metrics(entity_type);
CREATE INDEX idx_metrics_model ON performance_metrics(model_name);
CREATE INDEX idx_metrics_name ON performance_metrics(metric_name);
CREATE INDEX idx_metrics_created ON performance_metrics(created_at);

-- ================================================================
-- 8. KNOWLEDGE GRAPH SUPPORT TABLES
-- ================================================================

-- Knowledge graph relationship cache for performance
CREATE TABLE kg_relationship_cache (
    id SERIAL PRIMARY KEY,
    entity1_canonical TEXT NOT NULL,
    entity2_canonical TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    confidence_score DECIMAL(5,3) NOT NULL,
    confidence_boost DECIMAL(3,2) DEFAULT 0.00,
    context_requirements JSONB,
    validation_rules JSONB,
    distance_threshold INTEGER,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cache_hits INTEGER DEFAULT 0
);

CREATE INDEX idx_kg_cache_entities ON kg_relationship_cache(entity1_canonical, entity2_canonical);
CREATE INDEX idx_kg_cache_type ON kg_relationship_cache(relationship_type);
CREATE INDEX idx_kg_cache_updated ON kg_relationship_cache(last_updated);

-- ================================================================
-- 9. USEFUL VIEWS FOR COMMON QUERIES
-- ================================================================

-- View for complete entity information with session context
CREATE VIEW entity_details AS
SELECT 
    e.id,
    e.text_content,
    e.entity_type,
    e.confidence_score,
    e.model_source,
    e.char_start,
    e.char_end,
    s.text_content as sentence_text,
    s.sentence_number,
    rp.title as paper_title,
    rp.doi,
    es.session_name,
    es.ensemble_strategy,
    ea.canonical_form,
    ea.validation_status
FROM entities e
JOIN sentences s ON e.sentence_id = s.id
JOIN research_papers rp ON s.paper_id = rp.id
JOIN extraction_sessions es ON e.session_id = es.id
LEFT JOIN entity_attributes ea ON e.id = ea.entity_id;

-- View for semantic relationships summary
CREATE VIEW semantic_relationships AS
SELECT 
    'VALUE_UNIT' as relationship_type,
    vup.id as relationship_id,
    ve.text_content as entity1_text,
    ue.text_content as entity2_text,
    vup.numerical_value,
    vup.unit_canonical,
    vup.relationship_confidence,
    s.text_content as sentence_text,
    es.session_name
FROM value_unit_pairs vup
JOIN entities ve ON vup.value_entity_id = ve.id
JOIN entities ue ON vup.unit_entity_id = ue.id
JOIN sentences s ON vup.sentence_id = s.id
JOIN extraction_sessions es ON vup.session_id = es.id

UNION ALL

SELECT 
    'PROPERTY_MEASUREMENT' as relationship_type,
    pm.id as relationship_id,
    pe.text_content as entity1_text,
    ve.text_content || ' ' || ue.text_content as entity2_text,
    NULL as numerical_value,
    pm.measurement_type as unit_canonical,
    pm.measurement_confidence,
    s.text_content as sentence_text,
    es.session_name
FROM property_measurements pm
JOIN entities pe ON pm.property_entity_id = pe.id
JOIN entities ve ON pm.value_entity_id = ve.id
JOIN entities ue ON pm.unit_entity_id = ue.id
JOIN sentences s ON pm.context_sentence_id = s.id
JOIN extraction_sessions es ON pm.session_id = es.id;

-- ================================================================
-- 10. INITIAL DATA SETUP
-- ================================================================

-- Insert default model configurations
INSERT INTO model_configurations (name, model_id, version, base_weight, reliability_score, specialization_domains, is_active) VALUES
('bert-base-uncased', 'bert-base-uncased', 'v1.0', 1.00, 0.85, ARRAY['general'], true),
('distilbert-base-uncased', 'distilbert-base-uncased', 'v1.0', 0.90, 0.80, ARRAY['efficiency'], true),
('scibert-scivocab-uncased', 'allenai/scibert_scivocab_uncased', 'v1.0', 1.10, 0.90, ARRAY['scientific'], true);

-- Insert default model expertise weights
INSERT INTO model_entity_expertise (model_config_id, entity_type, expertise_weight, confidence_threshold)
SELECT 
    mc.id,
    entity_type,
    CASE 
        WHEN mc.name = 'scibert-scivocab-uncased' AND entity_type IN ('POLYMER', 'PROPERTY') THEN 1.20
        WHEN mc.name = 'scibert-scivocab-uncased' AND entity_type IN ('VALUE', 'UNIT') THEN 1.10
        WHEN mc.name = 'scibert-scivocab-uncased' AND entity_type = 'SYMBOL' THEN 0.95
        ELSE 1.00
    END as expertise_weight,
    CASE 
        WHEN entity_type = 'VALUE' THEN 0.60
        WHEN entity_type = 'UNIT' THEN 0.65
        WHEN entity_type = 'SYMBOL' THEN 0.70
        ELSE 0.50
    END as confidence_threshold
FROM model_configurations mc
CROSS JOIN (VALUES ('POLYMER'), ('PROPERTY'), ('VALUE'), ('UNIT'), ('SYMBOL')) AS types(entity_type)
WHERE mc.is_active = true;

-- ================================================================
-- SCHEMA CREATION COMPLETE
-- ================================================================

SELECT 'PostgreSQL schema deployment successful!' as status,
       'Storage migration: Appwrite fields removed' as migration_status,
       'Database configuration loaded from .env' as credentials;
