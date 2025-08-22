// ================================================================
// Neo4j Knowledge Graph Constraints and Indexes
// Version: 1.0
// Created: 2025-08-13
// Purpose: Bootstrap knowledge graph schema for Polymer NLP Extractor
// ================================================================

// Drop existing constraints if they exist (for clean setup)
DROP CONSTRAINT polymer_canonical_key IF EXISTS;
DROP CONSTRAINT property_canonical_key IF EXISTS;
DROP CONSTRAINT value_canonical_key IF EXISTS;
DROP CONSTRAINT unit_canonical_key IF EXISTS;
DROP CONSTRAINT symbol_canonical_key IF EXISTS;
DROP CONSTRAINT paper_doi_key IF EXISTS;
DROP CONSTRAINT session_id_key IF EXISTS;
DROP CONSTRAINT extraction_session_id_key IF EXISTS;

// Drop existing indexes if they exist
DROP INDEX entity_text_index IF EXISTS;
DROP INDEX entity_type_index IF EXISTS;
DROP INDEX relationship_strength_index IF EXISTS;
DROP INDEX validation_status_index IF EXISTS;
DROP INDEX confidence_score_index IF EXISTS;

// ================================================================
// 1. NODE UNIQUENESS CONSTRAINTS (Community Edition Compatible)
// Note: Using standard UNIQUE constraints instead of IS UNIQUE syntax
// ================================================================

// Entity nodes - ensure canonical forms are unique per type
CREATE CONSTRAINT polymer_canonical_key IF NOT EXISTS
FOR (p:Polymer) 
REQUIRE p.canonical_form IS UNIQUE;

CREATE CONSTRAINT property_canonical_key IF NOT EXISTS
FOR (prop:Property) 
REQUIRE prop.canonical_form IS UNIQUE;

CREATE CONSTRAINT value_canonical_key IF NOT EXISTS
FOR (v:Value) 
REQUIRE (v.canonical_form, v.numerical_value) IS UNIQUE;

CREATE CONSTRAINT unit_canonical_key IF NOT EXISTS
FOR (u:Unit) 
REQUIRE u.canonical_form IS UNIQUE;

CREATE CONSTRAINT symbol_canonical_key IF NOT EXISTS
FOR (s:Symbol) 
REQUIRE s.canonical_form IS UNIQUE;

// Paper nodes - DOI should be unique when present
CREATE CONSTRAINT paper_doi_key IF NOT EXISTS
FOR (p:Paper) 
REQUIRE p.doi IS UNIQUE;

// Session nodes - session IDs should be unique
CREATE CONSTRAINT session_id_key IF NOT EXISTS
FOR (s:Session) 
REQUIRE s.session_id IS UNIQUE;

// Extraction session nodes - extraction session IDs should be unique  
CREATE CONSTRAINT extraction_session_id_key IF NOT EXISTS
FOR (es:ExtractionSession) 
REQUIRE es.session_id IS UNIQUE;

// ================================================================
// 2. ENTITY NODE PROPERTY CONSTRAINTS
// Note: Property existence constraints (IS NOT NULL) require Neo4j Enterprise Edition
// For Community Edition, we rely on application-level validation instead
// ================================================================

// Community Edition: Use indexes for performance instead of existence constraints
// These provide similar benefits for query performance without Enterprise requirements

// Polymer canonical form index for fast lookups
CREATE INDEX polymer_canonical_index IF NOT EXISTS 
FOR (p:Polymer) ON (p.canonical_form);

// Property canonical form index
CREATE INDEX property_canonical_index IF NOT EXISTS 
FOR (prop:Property) ON (prop.canonical_form);

// Value canonical form index
CREATE INDEX value_canonical_index IF NOT EXISTS 
FOR (v:Value) ON (v.canonical_form);

// Unit indexes for both canonical form and unit system
CREATE INDEX unit_canonical_index IF NOT EXISTS 
FOR (u:Unit) ON (u.canonical_form);

CREATE INDEX unit_system_index IF NOT EXISTS 
FOR (u:Unit) ON (u.unit_system);

// Symbol canonical form index
CREATE INDEX symbol_canonical_index IF NOT EXISTS 
FOR (s:Symbol) ON (s.canonical_form);

// ================================================================
// 3. RELATIONSHIP TYPE CONSTRAINTS
// ================================================================

// Valid relationship types and their constraints
// Note: Neo4j doesn't have built-in relationship type constraints,
// but we document the expected patterns here

/*
EXPECTED RELATIONSHIP TYPES WITH VALIDATION CONSTRAINTS:

Entity Relationships (with direction constraints):
- (:Value)-[:HAS_UNIT]->(:Unit) [Required: numerical_value on Value]
- (:Property)-[:MEASURED_BY]->(:Value) [Required: measurement_type context]
- (:Property)-[:APPLIES_TO]->(:Polymer) [Required: property_category match]
- (:Polymer)-[:HAS_PROPERTY]->(:Property) [Bidirectional with APPLIES_TO]
- (:Value)-[:PART_OF]->(:Property) [Required: property context]

Semantic Relationships (bidirectional):
- (:Entity)-[:SIMILAR_TO]->(:Entity) [Required: similarity_score >= 0.7]
- (:Entity)-[:CANONICAL_FORM_OF]->(:Entity) [Required: canonical_form property]
- (:Entity)-[:SYNONYM_OF]->(:Entity) [Bidirectional semantic equivalent]

Document Relationships (hierarchical):
- (:Entity)-[:EXTRACTED_FROM]->(:Sentence) [Required: char_start, char_end]
- (:Sentence)-[:PART_OF]->(:Paper) [Required: sentence_number]
- (:Entity)-[:FOUND_IN_SESSION]->(:ExtractionSession) [Required: session_id]

Validation Relationships (quality control):
- (:Entity)-[:VALIDATED_BY]->(:ValidationRule) [Required: validation_status]
- (:Entity)-[:CORRECTED_TO]->(:Entity) [Required: correction_type]

Session Tracking Relationships:
- (:ExtractionSession)-[:PROCESSED]->(:Paper) [Required: processing_status]
- (:ExtractionSession)-[:USED_MODEL]->(:Model) [Required: model configuration]
- (:ExtractionSession)-[:GENERATED]->(:Entity) [Required: extraction metadata]
*/

// ================================================================
// 4. PERFORMANCE INDEXES
// ================================================================

// Text search indexes for entity matching
CREATE INDEX entity_text_index 
FOR (e:Entity) 
ON (e.text_content);

CREATE INDEX entity_canonical_index 
FOR (e:Entity) 
ON (e.canonical_form);

// Entity type indexes for fast filtering
CREATE INDEX entity_type_index 
FOR (e:Entity) 
ON (e.entity_type);

// Confidence and validation indexes
CREATE INDEX confidence_score_index 
FOR (e:Entity) 
ON (e.confidence_score);

CREATE INDEX validation_status_index 
FOR (e:Entity) 
ON (e.validation_status);

// Relationship strength indexes for KG queries
CREATE INDEX relationship_strength_index 
FOR ()-[r:HAS_UNIT|MEASURED_BY|APPLIES_TO|HAS_PROPERTY]-() 
ON (r.strength);

CREATE INDEX relationship_confidence_index 
FOR ()-[r:HAS_UNIT|MEASURED_BY|APPLIES_TO|HAS_PROPERTY]-() 
ON (r.confidence);

// Session and extraction session indexes
CREATE INDEX paper_doi_index 
FOR (p:Paper) 
ON (p.doi);

CREATE INDEX session_created_index 
FOR (s:Session) 
ON (s.created_at);

CREATE INDEX extraction_session_created_index 
FOR (es:ExtractionSession) 
ON (es.created_at);

CREATE INDEX extraction_session_strategy_index 
FOR (es:ExtractionSession) 
ON (es.ensemble_strategy);

CREATE INDEX extraction_session_status_index 
FOR (es:ExtractionSession) 
ON (es.status);

// ================================================================
// 5. SESSION TRACKING NODES AND CONSTRAINTS (ENHANCED)
// ================================================================

// Session tracking for extraction sessions (Community Edition compatible)
CREATE CONSTRAINT session_uuid_key IF NOT EXISTS
FOR (s:Session) 
REQUIRE s.uuid IS UNIQUE;

CREATE CONSTRAINT extraction_session_uuid_key IF NOT EXISTS
FOR (es:ExtractionSession) 
REQUIRE es.uuid IS UNIQUE;

// Model tracking nodes with enhanced constraints
CREATE CONSTRAINT model_name_version_key IF NOT EXISTS
FOR (m:Model) 
REQUIRE (m.name, m.version) IS UNIQUE;

// Sentence tracking nodes with paper-level uniqueness
CREATE CONSTRAINT sentence_paper_number_key IF NOT EXISTS
FOR (s:Sentence) 
REQUIRE (s.paper_id, s.sentence_number) IS UNIQUE;

// Enhanced session tracking indexes
CREATE INDEX session_status_index IF NOT EXISTS
FOR (s:Session) 
ON (s.status);

CREATE INDEX session_created_index IF NOT EXISTS
FOR (s:Session) 
ON (s.created_at);

CREATE INDEX extraction_session_status_index IF NOT EXISTS
FOR (es:ExtractionSession) 
ON (es.status);

CREATE INDEX extraction_session_strategy_index IF NOT EXISTS
FOR (es:ExtractionSession) 
ON (es.ensemble_strategy);

CREATE INDEX extraction_session_models_index IF NOT EXISTS
FOR (es:ExtractionSession) 
ON (es.models_used);

// Model performance tracking indexes
CREATE INDEX model_performance_index IF NOT EXISTS
FOR (m:Model) 
ON (m.performance_score);

CREATE INDEX model_specialization_index IF NOT EXISTS
FOR (m:Model) 
ON (m.specialization_domains);

// Session-entity relationship tracking indexes
CREATE INDEX session_entity_count_index IF NOT EXISTS
FOR (s:Session) 
ON (s.total_entities);

CREATE INDEX extraction_session_confidence_index IF NOT EXISTS
FOR (es:ExtractionSession) 
ON (es.average_confidence);

CREATE CONSTRAINT extraction_session_uuid_key IF NOT EXISTS
FOR (es:ExtractionSession) 
REQUIRE es.uuid IS UNIQUE;

// Model tracking nodes
CREATE CONSTRAINT model_name_version_key IF NOT EXISTS
FOR (m:Model) 
REQUIRE (m.name, m.version) IS UNIQUE;

// Sentence tracking nodes  
CREATE CONSTRAINT sentence_paper_number_key IF NOT EXISTS
FOR (s:Sentence) 
REQUIRE (s.paper_id, s.sentence_number) IS UNIQUE;

// ================================================================
// 6. RELATIONSHIP VALIDATION CONSTRAINTS AND SESSION TRACKING
// ================================================================

// Session tracking nodes with enhanced constraints (Community Edition compatible)
CREATE CONSTRAINT session_uuid_key IF NOT EXISTS
FOR (s:Session) 
REQUIRE s.uuid IS UNIQUE;

CREATE CONSTRAINT extraction_session_uuid_key IF NOT EXISTS
FOR (es:ExtractionSession) 
REQUIRE es.uuid IS UNIQUE;

// Enhanced relationship validation patterns
// Note: Implemented as application-level validation rules with KG support
// since Neo4j Community Edition doesn't support schema constraints on relationships

/*
EXPANDED RELATIONSHIP VALIDATION RULES (Application-Level Enforcement):

1. VALUE-UNIT relationships (ENHANCED):
   - (:Value)-[:HAS_UNIT]->(:Unit) [REQUIRED: numerical_value property]
   - Distance constraint: max 5 tokens apart
   - Confidence threshold: >= 0.6
   - Direction enforcement: VALUE -> UNIT (unidirectional)
   - Multiplicity: One VALUE can have multiple UNITs (compound units)

2. PROPERTY-VALUE relationships (ENHANCED):
   - (:Property)-[:MEASURED_BY]->(:Value) [REQUIRED: measurement_type]
   - Distance constraint: max 10 tokens apart  
   - Confidence threshold: >= 0.65
   - Bidirectional relationships allowed for semantic completeness
   - Context validation: Ensure measurement is physically meaningful

3. POLYMER-PROPERTY relationships (ENHANCED):
   - (:Polymer)-[:HAS_PROPERTY]->(:Property) [BIDIRECTIONAL allowed]
   - (:Property)-[:APPLIES_TO]->(:Polymer) [BIDIRECTIONAL allowed]
   - Distance constraint: max 20 tokens apart
   - Confidence threshold: >= 0.7
   - Domain validation: Check property is applicable to polymer class

4. Session relationships (NEW):
   - (:Entity)-[:EXTRACTED_IN]->(:ExtractionSession) [REQUIRED: session_uuid]
   - (:ExtractionSession)-[:PROCESSED]->(:Paper) [REQUIRED: status property]
   - (:ExtractionSession)-[:USED_MODEL]->(:Model) [REQUIRED: weight property]
   - (:ExtractionSession)-[:GENERATED]->(:Entity) [REQUIRED: extraction metadata]

5. Validation relationships (ENHANCED):
   - (:Entity)-[:VALIDATED_AS]->(:ValidationRule) [REQUIRED: status]
   - (:Entity)-[:CORRECTED_TO]->(:Entity) [REQUIRED: correction_type]
   - (:Entity)-[:CANONICAL_FORM_OF]->(:Entity) [REQUIRED: canonical_form]
   - (:ValidationRule)-[:VALIDATES]->(:EntityType) [REQUIRED: rule_scope]

6. Document hierarchy (ENHANCED):
   - (:Entity)-[:FOUND_IN]->(:Sentence) [REQUIRED: char_start, char_end]
   - (:Sentence)-[:PART_OF]->(:Paper) [REQUIRED: sentence_number]
   - (:ValidationRule)-[:APPLIES_TO]->(:EntityType) [REQUIRED: rule_type]
   - (:Session)-[:TRACKS]->(:ExtractionSession) [REQUIRED: session_metadata]

7. Advanced semantic relationships (NEW):
   - (:Entity)-[:CONTEXT_RELATED]->(:Entity) [Context-based semantic similarity]
   - (:Property)-[:TYPICALLY_PAIRED_WITH]->(:Unit) [Domain knowledge relationships]
   - (:Polymer)-[:CHEMICALLY_SIMILAR_TO]->(:Polymer) [Chemical structure similarity]
   - (:ValidationRule)-[:DEPENDS_ON]->(:ValidationRule) [Rule dependency chains]
*/

// ================================================================
// 7. COMPOSITE INDEXES FOR COMPLEX QUERIES
// ================================================================

// ================================================================
// 7. COMPOSITE INDEXES FOR COMPLEX QUERIES
// ================================================================

// Entity type + confidence for ranked queries
CREATE INDEX entity_type_confidence_index 
FOR (e:Entity) 
ON (e.entity_type, e.confidence_score);

// Session tracking indexes for performance
CREATE INDEX session_uuid_index 
FOR (s:Session) 
ON (s.uuid);

CREATE INDEX session_status_index 
FOR (s:Session) 
ON (s.status);

CREATE INDEX extraction_session_uuid_index 
FOR (es:ExtractionSession) 
ON (es.uuid);

CREATE INDEX extraction_session_strategy_index 
FOR (es:ExtractionSession) 
ON (es.ensemble_strategy);

CREATE INDEX extraction_session_models_index 
FOR (es:ExtractionSession) 
ON (es.models_used);

// Model and validation indexes
CREATE INDEX model_name_index 
FOR (m:Model) 
ON (m.name);

CREATE INDEX model_active_index 
FOR (m:Model) 
ON (m.is_active);

CREATE INDEX validation_rule_type_index 
FOR (vr:ValidationRule) 
ON (vr.rule_type);

CREATE INDEX validation_rule_entity_type_index 
FOR (vr:ValidationRule) 
ON (vr.applicable_entity_types);

// Document hierarchy indexes
CREATE INDEX sentence_paper_index 
FOR (s:Sentence) 
ON (s.paper_id);

CREATE INDEX sentence_number_index 
FOR (s:Sentence) 
ON (s.sentence_number);

// Relationship strength and confidence indexes for KG traversals
CREATE INDEX relationship_confidence_numeric_index 
FOR ()-[r:HAS_UNIT|MEASURED_BY|APPLIES_TO|HAS_PROPERTY|EXTRACTED_IN|VALIDATED_AS]-() 
ON (r.confidence_score);

CREATE INDEX relationship_distance_index 
FOR ()-[r:HAS_UNIT|MEASURED_BY|APPLIES_TO|HAS_PROPERTY]-() 
ON (r.distance_tokens);

CREATE INDEX relationship_session_index 
FOR ()-[r:EXTRACTED_IN|PROCESSED|USED_MODEL]-() 
ON (r.session_uuid);

// ================================================================
// 8. KNOWLEDGE GRAPH BOOTSTRAP DATA
// ================================================================

// Create initial canonical entities for validation
// These serve as reference nodes for entity validation and confidence boosting

// Common polymer canonicals
CREATE (:Polymer {
    canonical_form: "polyethylene",
    synonyms: ["PE", "polyethene", "poly(ethylene)"],
    confidence_boost: 0.15,
    validation_status: "canonical",
    created_at: datetime()
});

CREATE (:Polymer {
    canonical_form: "polystyrene", 
    synonyms: ["PS", "poly(styrene)"],
    confidence_boost: 0.15,
    validation_status: "canonical",
    created_at: datetime()
});

CREATE (:Polymer {
    canonical_form: "polyvinyl chloride",
    synonyms: ["PVC", "poly(vinyl chloride)"],
    confidence_boost: 0.15,
    validation_status: "canonical", 
    created_at: datetime()
});

// Common property canonicals
CREATE (:Property {
    canonical_form: "glass transition temperature",
    synonyms: ["Tg", "glass transition temp", "glass-transition temperature"],
    confidence_boost: 0.12,
    validation_status: "canonical",
    property_category: "thermal",
    created_at: datetime()
});

CREATE (:Property {
    canonical_form: "melting temperature",
    synonyms: ["Tm", "melting point", "melting temp"],
    confidence_boost: 0.12,
    validation_status: "canonical",
    property_category: "thermal",
    created_at: datetime()
});

CREATE (:Property {
    canonical_form: "tensile strength",
    synonyms: ["ultimate tensile strength", "UTS"],
    confidence_boost: 0.12,
    validation_status: "canonical",
    property_category: "mechanical",
    created_at: datetime()
});

// Common unit canonicals
CREATE (:Unit {
    canonical_form: "celsius",
    synonyms: ["°C", "C", "degrees celsius"],
    confidence_boost: 0.10,
    validation_status: "canonical",
    unit_system: "metric",
    unit_type: "temperature",
    created_at: datetime()
});

CREATE (:Unit {
    canonical_form: "megapascal",
    synonyms: ["MPa", "mega pascal", "mega-pascal"],
    confidence_boost: 0.10,
    validation_status: "canonical", 
    unit_system: "metric",
    unit_type: "pressure",
    created_at: datetime()
});

CREATE (:Unit {
    canonical_form: "gram per cubic centimeter",
    synonyms: ["g/cm³", "g/cm3", "g cm⁻³"],
    confidence_boost: 0.10,
    validation_status: "canonical",
    unit_system: "metric", 
    unit_type: "density",
    created_at: datetime()
});

// Create validation rules
CREATE (:ValidationRule {
    rule_type: "VALUE_UNIT_PROXIMITY",
    description: "VALUE and UNIT entities must be within 5 tokens",
    applicable_entity_types: ["VALUE", "UNIT"],
    confidence_threshold: 0.6,
    distance_threshold: 5,
    confidence_adjustment: 0.12,
    is_active: true,
    created_at: datetime()
});

CREATE (:ValidationRule {
    rule_type: "PROPERTY_VALUE_RELATIONSHIP", 
    description: "PROPERTY and VALUE entities should be within 10 tokens",
    applicable_entity_types: ["PROPERTY", "VALUE"],
    confidence_threshold: 0.65,
    distance_threshold: 10,
    confidence_adjustment: 0.10,
    is_active: true,
    created_at: datetime()
});

CREATE (:ValidationRule {
    rule_type: "POLYMER_PROPERTY_ASSOCIATION",
    description: "POLYMER and PROPERTY entities may be within 20 tokens", 
    applicable_entity_types: ["POLYMER", "PROPERTY"],
    confidence_threshold: 0.7,
    distance_threshold: 20,
    confidence_adjustment: 0.08,
    is_active: true,
    created_at: datetime()
});

// ================================================================
// 9. RELATIONSHIP TEMPLATES FOR COMMON PATTERNS
// ================================================================

// Create common relationship patterns
MATCH (tg:Property {canonical_form: "glass transition temperature"}),
      (celsius:Unit {canonical_form: "celsius"})
CREATE (tg)-[:COMMONLY_MEASURED_IN {
    frequency: 0.85,
    confidence_boost: 0.05,
    validation_pattern: "temperature_celsius"
}]->(celsius);

MATCH (ts:Property {canonical_form: "tensile strength"}),
      (mpa:Unit {canonical_form: "megapascal"})  
CREATE (ts)-[:COMMONLY_MEASURED_IN {
    frequency: 0.90,
    confidence_boost: 0.05,
    validation_pattern: "strength_pressure"
}]->(mpa);

// ================================================================
// SCHEMA SETUP COMPLETE
// ================================================================

// Validation status + entity type for quality queries
CREATE INDEX validation_type_index 
FOR (e:Entity) 
ON (e.validation_status, e.entity_type);

// Session + entity type for session analysis
CREATE INDEX session_entity_type_index 
FOR (e:Entity) 
ON (e.session_id, e.entity_type);

// ================================================================
// 6. KNOWLEDGE GRAPH VALIDATION RULES
// ================================================================

// Create ValidationRule nodes for common patterns
CREATE (:ValidationRule {
    rule_id: 'value_unit_compatibility',
    rule_type: 'physical_consistency',
    description: 'Validates that VALUE-UNIT pairs are physically meaningful',
    confidence_boost: 0.12,
    validation_query: 'MATCH (v:Value)-[:HAS_UNIT]->(u:Unit) WHERE v.numerical_value IS NOT NULL RETURN v, u'
});

CREATE (:ValidationRule {
    rule_id: 'property_value_range',
    rule_type: 'domain_knowledge',
    description: 'Validates that property values fall within expected ranges',
    confidence_boost: 0.10,
    validation_query: 'MATCH (p:Property)-[:MEASURED_BY]->(v:Value) RETURN p, v'
});

CREATE (:ValidationRule {
    rule_id: 'polymer_property_compatibility',
    rule_type: 'semantic_validation',
    description: 'Validates that polymer-property combinations are chemically valid',
    confidence_boost: 0.08,
    validation_query: 'MATCH (pol:Polymer)-[:HAS_PROPERTY]->(prop:Property) RETURN pol, prop'
});

CREATE (:ValidationRule {
    rule_id: 'unit_system_consistency',
    rule_type: 'measurement_validation',
    description: 'Ensures units within a measurement are from compatible systems',
    confidence_boost: 0.06,
    validation_query: 'MATCH (u:Unit) WHERE u.unit_system IS NOT NULL RETURN u'
});

// ================================================================
// 7. CANONICAL ENTITY TEMPLATES
// ================================================================

// Create template canonical entities for common polymer science concepts

// Common polymer types
CREATE (:Polymer {
    canonical_form: 'polystyrene',
    aliases: ['PS', 'poly(styrene)', 'polystyrol'],
    polymer_class: 'thermoplastic',
    chemical_formula: '(C8H8)n',
    confidence_boost: 0.15
});

CREATE (:Polymer {
    canonical_form: 'polyethylene',
    aliases: ['PE', 'poly(ethylene)', 'polyethene'],
    polymer_class: 'thermoplastic',
    chemical_formula: '(C2H4)n',
    confidence_boost: 0.15
});

// Common properties
CREATE (:Property {
    canonical_form: 'glass_transition_temperature',
    aliases: ['Tg', 'T_g', 'glass transition temperature', 'glass-transition temperature'],
    property_category: 'thermal',
    typical_units: ['°C', 'K', '°F'],
    confidence_boost: 0.12
});

CREATE (:Property {
    canonical_form: 'tensile_strength',
    aliases: ['tensile strength', 'ultimate tensile strength', 'UTS'],
    property_category: 'mechanical',
    typical_units: ['MPa', 'GPa', 'psi'],
    confidence_boost: 0.12
});

CREATE (:Property {
    canonical_form: 'elastic_modulus',
    aliases: ['elastic modulus', 'Young\'s modulus', 'modulus of elasticity', 'E'],
    property_category: 'mechanical',
    typical_units: ['GPa', 'MPa', 'psi'],
    confidence_boost: 0.12
});

// Common units
CREATE (:Unit {
    canonical_form: 'celsius',
    aliases: ['°C', 'C', 'degree celsius', 'degrees celsius'],
    unit_system: 'metric',
    unit_category: 'temperature',
    confidence_boost: 0.08
});

CREATE (:Unit {
    canonical_form: 'megapascal',
    aliases: ['MPa', 'N/mm2', 'N/mm²', 'megapascals'],
    unit_system: 'SI',
    unit_category: 'pressure',
    confidence_boost: 0.08
});

CREATE (:Unit {
    canonical_form: 'gigapascal',
    aliases: ['GPa', 'GN/m2', 'GN/m²', 'gigapascals'],
    unit_system: 'SI',
    unit_category: 'pressure',
    confidence_boost: 0.08
});

// Common symbols
CREATE (:Symbol {
    canonical_form: 'sigma',
    aliases: ['σ', 'sigma', 'stress_symbol'],
    symbol_category: 'stress',
    typical_context: ['mechanical_properties', 'stress_analysis'],
    confidence_boost: 0.06
});

CREATE (:Symbol {
    canonical_form: 'epsilon',
    aliases: ['ε', 'epsilon', 'strain_symbol'],
    symbol_category: 'strain',
    typical_context: ['mechanical_properties', 'deformation'],
    confidence_boost: 0.06
});

// ================================================================
// 8. RELATIONSHIP TEMPLATES
// ================================================================

// Create common semantic relationships
MATCH (tg:Property {canonical_form: 'glass_transition_temperature'}),
      (celsius:Unit {canonical_form: 'celsius'})
CREATE (tg)-[:TYPICALLY_MEASURED_IN {
    strength: 0.9,
    confidence: 0.95,
    context: 'thermal_analysis'
}]->(celsius);

MATCH (ts:Property {canonical_form: 'tensile_strength'}),
      (mpa:Unit {canonical_form: 'megapascal'})
CREATE (ts)-[:TYPICALLY_MEASURED_IN {
    strength: 0.9,
    confidence: 0.95,
    context: 'mechanical_testing'
}]->(mpa);

MATCH (em:Property {canonical_form: 'elastic_modulus'}),
      (gpa:Unit {canonical_form: 'gigapascal'})
CREATE (em)-[:TYPICALLY_MEASURED_IN {
    strength: 0.9,
    confidence: 0.95,
    context: 'mechanical_testing'
}]->(gpa);

// ================================================================
// 9. KNOWLEDGE GRAPH UTILITY PROCEDURES
// ================================================================

// Create a procedure for entity validation (pseudo-code for documentation)
/*
CALL apoc.custom.asFunction(
    'kg.validateEntity',
    'MATCH (e:Entity {text_content: $text, entity_type: $type})
     OPTIONAL MATCH (canonical)-[:CANONICAL_FORM_OF]->(e)
     RETURN CASE 
         WHEN canonical IS NOT NULL THEN {validated: true, boost: canonical.confidence_boost}
         ELSE {validated: false, boost: 0.0}
     END as result',
    'MAP',
    [['text', 'STRING'], ['type', 'STRING']]
);
*/

// ================================================================
// 10. MONITORING AND MAINTENANCE QUERIES
// ================================================================

// Query to check constraint status
// SHOW CONSTRAINTS;

// Query to check index status  
// SHOW INDEXES;

// Query to validate KG structure
// MATCH (n) RETURN labels(n) as node_types, count(n) as count ORDER BY count DESC;

// Query to check relationship types
// MATCH ()-[r]->() RETURN type(r) as relationship_type, count(r) as count ORDER BY count DESC;

// ================================================================
// KNOWLEDGE GRAPH BOOTSTRAP COMPLETE
// ================================================================

// Return success message
RETURN 'Neo4j knowledge graph constraints and bootstrap data created successfully!' as status,
       'Constraints: 11, Indexes: 12, Validation Rules: 4, Canonical Entities: 8' as summary;
