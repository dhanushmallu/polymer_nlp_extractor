-- ================================================================
-- PostgreSQL Schema for Polymer NLP Extractor
-- Version: 1.0
-- Created: 2025-08-13
-- Purpose: Core database schema for dual-database architecture
-- ================================================================

-- Drop existing tables if they exist (for clean migrations)
DROP TABLE IF EXISTS performance_metrics CASCADE;
DROP TABLE IF EXISTS validation_logs CASCADE;
DROP TABLE IF EXISTS kg_relationship_cache CASCADE;
DROP TABLE IF EXISTS property_measurements CASCADE;
DROP TABLE IF EXISTS value_unit_pairs CASCADE;
DROP TABLE IF EXISTS entity_attributes CASCADE;
DROP TABLE IF EXISTS entities CASCADE;
DROP TABLE IF EXISTS model_entity_expertise CASCADE;
DROP TABLE IF EXISTS model_configurations CASCADE;
DROP TABLE IF EXISTS extraction_sessions CASCADE;
DROP TABLE IF EXISTS sentences CASCADE;
DROP TABLE IF EXISTS datasets CASCADE;
DROP TABLE IF EXISTS research_papers CASCADE;

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- ================================================================
-- 1. CORE METADATA TABLES
-- ================================================================

-- Research papers metadata
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
    appwrite_file_id VARCHAR(255), -- Link to Appwrite storage
    file_size BIGINT,
    processing_status VARCHAR(20) DEFAULT 'pending' CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for research_papers
CREATE INDEX idx_papers_doi ON research_papers(doi);
CREATE INDEX idx_papers_created ON research_papers(created_at);
CREATE INDEX idx_papers_status ON research_papers(processing_status);
CREATE INDEX idx_papers_filename ON research_papers(file_name);

-- Sentences extracted from papers (character-level precision)
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

-- Indexes for sentences
CREATE INDEX idx_sentences_paper ON sentences(paper_id);
CREATE INDEX idx_sentences_section ON sentences(section_type);
CREATE INDEX idx_sentences_char_range ON sentences(char_start, char_end);
CREATE INDEX idx_sentences_number ON sentences(paper_id, sentence_number);

-- Datasets for training/testing management
CREATE TABLE datasets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(20) CHECK (type IN ('training', 'testing', 'validation')) NOT NULL,
    source_file VARCHAR(255),
    appwrite_file_id VARCHAR(255),
    total_entities INTEGER DEFAULT 0,
    total_sentences INTEGER DEFAULT 0,
    annotation_format VARCHAR(50), -- BIO, BILOU, etc.
    quality_score DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- Indexes for datasets
CREATE UNIQUE INDEX idx_datasets_name_type ON datasets(name, type);
CREATE INDEX idx_datasets_type ON datasets(type);
CREATE INDEX idx_datasets_active ON datasets(is_active);

-- ================================================================
-- 2. MODEL CONFIGURATION TABLES
-- ================================================================

-- Model configurations for ensemble tracking
CREATE TABLE model_configurations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    model_id VARCHAR(255) NOT NULL, -- HuggingFace ID
    version VARCHAR(50) NOT NULL,
    base_weight DECIMAL(4,2) DEFAULT 1.00,
    reliability_score DECIMAL(4,2) DEFAULT 1.00,
    specialization_domains TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- Indexes for model_configurations
CREATE UNIQUE INDEX idx_models_name_version ON model_configurations(name, version);
CREATE INDEX idx_models_name ON model_configurations(name);
CREATE INDEX idx_models_active ON model_configurations(is_active);

-- Model expertise per entity type
CREATE TABLE model_entity_expertise (
    id SERIAL PRIMARY KEY,
    model_config_id INTEGER REFERENCES model_configurations(id) ON DELETE CASCADE,
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('POLYMER', 'PROPERTY', 'VALUE', 'UNIT', 'SYMBOL')),
    expertise_weight DECIMAL(4,2) NOT NULL DEFAULT 1.00,
    confidence_threshold DECIMAL(4,2) DEFAULT 0.50
);

-- Indexes for model_entity_expertise
CREATE UNIQUE INDEX idx_expertise_model_entity ON model_entity_expertise(model_config_id, entity_type);
CREATE INDEX idx_expertise_entity ON model_entity_expertise(entity_type);

-- ================================================================
-- 3. EXTRACTION SESSION TRACKING
-- ================================================================

-- Processing sessions with comprehensive metadata
CREATE TABLE extraction_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_name VARCHAR(255),
    paper_id INTEGER REFERENCES research_papers(id),
    ensemble_strategy VARCHAR(50) DEFAULT 'weighted_confidence' CHECK (ensemble_strategy IN (
        'weighted_confidence', 'expert_consensus', 'dynamic_threshold', 
        'semantic_aware', 'adaptive_voting'
    )),
    models_used TEXT[], -- Array of model names used
    total_entities INTEGER DEFAULT 0,
    average_confidence DECIMAL(6,4),
    consensus_rate DECIMAL(5,4),
    processing_time_seconds INTEGER,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    processing_notes TEXT,
    kg_inference_enabled BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Indexes for extraction_sessions
CREATE INDEX idx_sessions_paper ON extraction_sessions(paper_id);
CREATE INDEX idx_sessions_status ON extraction_sessions(status);
CREATE INDEX idx_sessions_created ON extraction_sessions(created_at);
CREATE INDEX idx_sessions_strategy ON extraction_sessions(ensemble_strategy);

-- ================================================================
-- 4. UNIFIED ENTITY STORAGE
-- ================================================================

-- Unified entity structure for all entity types (NO MATERIAL label)
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
    model_weight DECIMAL(4,2), -- Applied weight during ensemble
    data_type VARCHAR(20) DEFAULT 'extracted' CHECK (data_type IN ('training', 'testing', 'extracted')) NOT NULL,
    dataset_id INTEGER REFERENCES datasets(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance indexes for entities
CREATE INDEX idx_entities_sentence ON entities(sentence_id);
CREATE INDEX idx_entities_session ON entities(session_id);
CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_confidence ON entities(confidence_score DESC);
CREATE INDEX idx_entities_data_type ON entities(data_type);
CREATE INDEX idx_entities_char_range ON entities(char_start, char_end);
CREATE INDEX idx_entities_text ON entities(text_content);

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

-- Indexes for entity_attributes
CREATE UNIQUE INDEX idx_attributes_entity ON entity_attributes(entity_id);
CREATE INDEX idx_attributes_canonical ON entity_attributes(canonical_form);
CREATE INDEX idx_attributes_status ON entity_attributes(validation_status);

-- ================================================================
-- 6. SEMANTIC RELATIONSHIP TABLES
-- ================================================================

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

-- Indexes for value_unit_pairs
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

-- Indexes for property_measurements
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

-- Indexes for validation_logs
CREATE INDEX idx_validation_entity ON validation_logs(entity_id);
CREATE INDEX idx_validation_session ON validation_logs(session_id);
CREATE INDEX idx_validation_type ON validation_logs(validation_type);
CREATE INDEX idx_validation_passed ON validation_logs(validation_passed);

-- Performance metrics tracking
CREATE TABLE performance_metrics (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES extraction_sessions(id) ON DELETE CASCADE,
    entity_type VARCHAR(20), -- NULL for global metrics
    model_name VARCHAR(100), -- NULL for ensemble metrics
    metric_name VARCHAR(50) NOT NULL, -- precision, recall, f1_score, etc.
    metric_value DECIMAL(6,4) NOT NULL,
    sample_size INTEGER,
    threshold_used DECIMAL(4,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance_metrics
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

-- Indexes for kg_relationship_cache
CREATE INDEX idx_kg_cache_entities ON kg_relationship_cache(entity1_canonical, entity2_canonical);
CREATE INDEX idx_kg_cache_type ON kg_relationship_cache(relationship_type);
CREATE INDEX idx_kg_cache_updated ON kg_relationship_cache(last_updated);

-- ================================================================
-- 9. TRIGGERS FOR AUTOMATIC UPDATES
-- ================================================================

-- Function to update timestamps automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply timestamp triggers
CREATE TRIGGER update_research_papers_updated_at BEFORE UPDATE ON research_papers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_entity_attributes_updated_at BEFORE UPDATE ON entity_attributes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to update entity counts in sessions
CREATE OR REPLACE FUNCTION update_session_entity_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE extraction_sessions 
        SET total_entities = (
            SELECT COUNT(*) FROM entities WHERE session_id = NEW.session_id
        )
        WHERE id = NEW.session_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE extraction_sessions 
        SET total_entities = (
            SELECT COUNT(*) FROM entities WHERE session_id = OLD.session_id
        )
        WHERE id = OLD.session_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ language 'plpgsql';

-- Apply entity count triggers
CREATE TRIGGER update_entity_count_on_insert AFTER INSERT ON entities
    FOR EACH ROW EXECUTE FUNCTION update_session_entity_count();

CREATE TRIGGER update_entity_count_on_delete AFTER DELETE ON entities
    FOR EACH ROW EXECUTE FUNCTION update_session_entity_count();

-- ================================================================
-- 10. USEFUL VIEWS FOR COMMON QUERIES
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
-- 11. INITIAL DATA SETUP
-- ================================================================

-- Insert default model configurations
INSERT INTO model_configurations (name, model_id, version, base_weight, reliability_score, specialization_domains, is_active) VALUES
('bert-base-uncased', 'bert-base-uncased', 'v1.0', 1.00, 0.85, ARRAY['general'], true),
('distilbert-base-uncased', 'distilbert-base-uncased', 'v1.0', 0.90, 0.80, ARRAY['efficiency'], true),
('scibert-scivocab-uncased', 'allenai/scibert_scivocab_uncased', 'v1.0', 1.10, 0.90, ARRAY['scientific'], true);

-- Insert default model expertise weights (removing MATERIAL label)
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

-- Grant necessary permissions (adjust as needed for your user)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO polymer_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO polymer_user;

-- Output completion message
SELECT 'PostgreSQL schema 001_core.sql created successfully!' as status,
       'Tables: ' || COUNT(*) || ' created' as summary
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN (
    'research_papers', 'sentences', 'datasets', 'model_configurations', 
    'model_entity_expertise', 'extraction_sessions', 'entities', 
    'entity_attributes', 'value_unit_pairs', 'property_measurements',
    'validation_logs', 'performance_metrics', 'kg_relationship_cache'
  );
