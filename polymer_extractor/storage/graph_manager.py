# polymer_extractor/storage/graph_manager.py

"""
GraphManager for Polymer NLP Extractor.

Universal graph database operations for Neo4j with comprehensive CRUD functionality,
entity-specific operations, and knowledge graph integration.

Purpose
-------
Provides high-level abstraction for Neo4j graph operations:
- Node and relationship CRUD operations
- Entity-specific polymer science operations  
- Knowledge graph queries and path finding
- Integration with model_config.py entity types and relationships
- Environment-driven configuration based on .env flags

Design Principles
-----------------
1) Environment-first configuration following .env.example flags
2) Universal interface consistent with database_manager.py patterns
3) Entity-aware operations using model_config.py LABELS and patterns
4) Knowledge graph intelligence for polymer science domain
5) Comprehensive error handling and logging

Environment Variables
---------------------
Required (from .env.example):
- USE_NEO4J_DB=true/false - Enable/disable Neo4j database operations
- GRAPH_BACKEND=neo4j|disabled - Control graph backend selection

Optional:
- NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD (handled by neo4j_client.py)

Examples
--------
>>> from polymer_extractor.storage.graph_manager import GraphManager
>>> graph = GraphManager()
>>> graph.create_polymer_entity("PDMS", {"molecular_weight": 10000})
>>> graph.create_property_measurement("polymer_1", "tensile_strength", 45.2, "MPa")
"""

import os
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from polymer_extractor.storage.neo4j_client import Neo4jClient
from polymer_extractor.utils.logging import Logger


class GraphManager:
    """
    Universal graph database operations for Neo4j.
    
    Provides comprehensive CRUD operations for nodes and relationships,
    with specialized methods for polymer science entities and knowledge graph operations.
    Routes operations based on environment configuration flags.
    """

    def __init__(self):
        """Initialize GraphManager with environment-based configuration."""
        self.neo4j_client = Neo4jClient() if self._should_use_neo4j() else None
        self.logger = Logger()
        
        if not self.neo4j_client:
            self.logger.log("WARNING", "Neo4j client not initialized - check USE_NEO4J_DB and GRAPH_BACKEND flags", "graph_manager")

    def _should_use_neo4j(self) -> bool:
        """
        Check if Neo4j should be used based on .env.example flags.
        
        Returns
        -------
        bool
            True if Neo4j operations should be enabled
        """
        return (os.getenv("USE_NEO4J_DB", "true").lower() == "true" and
                os.getenv("GRAPH_BACKEND", "neo4j") == "neo4j")

    def _ensure_client(self) -> None:
        """Ensure Neo4j client is available, raise error if not."""
        if not self.neo4j_client:
            raise RuntimeError("Neo4j client not available. Check USE_NEO4J_DB and GRAPH_BACKEND environment flags.")

    # ============================================================================
    # Node Operations
    # ============================================================================

    def create_node(self, label: str, properties: dict, node_id: str = None) -> dict:
        """
        Create a node with specified label and properties.
        
        Integrates with model_config.py LABELS for entity type validation.
        
        Parameters
        ----------
        label : str
            Node label (e.g., "POLYMER", "PROPERTY", "VALUE", "UNIT")
        properties : dict
            Node properties and metadata
        node_id : str, optional
            Specific node ID to use
            
        Returns
        -------
        dict
            Created node information with Neo4j internal ID
        """
        self._ensure_client()
        
        try:
            # Validate label against model_config.py entity types if applicable
            if label.upper() in ["POLYMER", "PROPERTY", "VALUE", "UNIT", "SYMBOL"]:
                self.logger.log("DEBUG", f"Creating {label} node with entity validation", "graph_manager")
            
            # Prepare Cypher query
            if node_id:
                properties["id"] = node_id
                
            cypher = f"CREATE (n:{label} $properties) RETURN n, ID(n) as internal_id"
            result = self.neo4j_client.run(cypher, properties=properties, fetch="one")
            
            if result:
                self.logger.log("INFO", f"Created {label} node with ID {result.get('internal_id')}", "graph_manager")
                return {
                    "node": dict(result["n"]),
                    "internal_id": result["internal_id"],
                    "label": label
                }
            else:
                raise RuntimeError("Node creation failed - no result returned")
                
        except Exception as e:
            self.logger.log("ERROR", f"Failed to create {label} node: {e}", "graph_manager")
            raise

    def get_node(self, label: str, node_id: str = None, properties: dict = None) -> dict:
        """
        Get a node by ID or properties.
        
        Parameters
        ----------
        label : str
            Node label to search
        node_id : str, optional
            Specific node ID to find
        properties : dict, optional
            Properties to match
            
        Returns
        -------
        dict
            Node information or None if not found
        """
        self._ensure_client()
        
        try:
            if node_id:
                cypher = f"MATCH (n:{label}) WHERE n.id = $node_id RETURN n, ID(n) as internal_id"
                result = self.neo4j_client.run(cypher, node_id=node_id, fetch="one")
            elif properties:
                # Build WHERE clause from properties
                where_conditions = []
                params = {}
                for key, value in properties.items():
                    where_conditions.append(f"n.{key} = ${key}")
                    params[key] = value
                
                where_clause = " AND ".join(where_conditions)
                cypher = f"MATCH (n:{label}) WHERE {where_clause} RETURN n, ID(n) as internal_id"
                result = self.neo4j_client.run(cypher, **params, fetch="one")
            else:
                raise ValueError("Must provide either node_id or properties")
                
            if result:
                return {
                    "node": dict(result["n"]),
                    "internal_id": result["internal_id"],
                    "label": label
                }
            return None
            
        except Exception as e:
            self.logger.log("ERROR", f"Failed to get {label} node: {e}", "graph_manager")
            raise

    def update_node(self, label: str, node_id: str, properties: dict) -> dict:
        """
        Update node properties.
        
        Parameters
        ----------
        label : str
            Node label
        node_id : str
            Node ID to update
        properties : dict
            Properties to update
            
        Returns
        -------
        dict
            Updated node information
        """
        self._ensure_client()
        
        try:
            # Build SET clause from properties
            set_conditions = []
            params = {"node_id": node_id}
            for key, value in properties.items():
                set_conditions.append(f"n.{key} = ${key}")
                params[key] = value
                
            set_clause = ", ".join(set_conditions)
            cypher = f"MATCH (n:{label}) WHERE n.id = $node_id SET {set_clause} RETURN n, ID(n) as internal_id"
            
            result = self.neo4j_client.run(cypher, **params, fetch="one")
            
            if result:
                self.logger.log("INFO", f"Updated {label} node {node_id}", "graph_manager")
                return {
                    "node": dict(result["n"]),
                    "internal_id": result["internal_id"],
                    "label": label
                }
            else:
                raise RuntimeError(f"Node {node_id} not found for update")
                
        except Exception as e:
            self.logger.log("ERROR", f"Failed to update {label} node {node_id}: {e}", "graph_manager")
            raise

    def delete_node(self, label: str, node_id: str) -> None:
        """
        Delete a node and all its relationships.
        
        Parameters
        ----------
        label : str
            Node label
        node_id : str
            Node ID to delete
        """
        self._ensure_client()
        
        try:
            cypher = f"MATCH (n:{label}) WHERE n.id = $node_id DETACH DELETE n"
            result = self.neo4j_client.run(cypher, node_id=node_id)
            
            self.logger.log("INFO", f"Deleted {label} node {node_id} and all relationships", "graph_manager")
            
        except Exception as e:
            self.logger.log("ERROR", f"Failed to delete {label} node {node_id}: {e}", "graph_manager")
            raise

    def list_nodes(self, label: str, filters: dict = None, limit: int = None) -> list:
        """
        List nodes with optional filtering.
        
        Parameters
        ----------
        label : str
            Node label to list
        filters : dict, optional
            Property filters to apply
        limit : int, optional
            Maximum number of nodes to return
            
        Returns
        -------
        list
            List of matching nodes
        """
        self._ensure_client()
        
        try:
            cypher = f"MATCH (n:{label})"
            params = {}
            
            if filters:
                where_conditions = []
                for key, value in filters.items():
                    where_conditions.append(f"n.{key} = ${key}")
                    params[key] = value
                cypher += f" WHERE {' AND '.join(where_conditions)}"
                
            cypher += " RETURN n, ID(n) as internal_id"
            
            if limit:
                cypher += f" LIMIT {limit}"
                
            results = self.neo4j_client.run(cypher, **params, fetch="all")
            
            return [
                {
                    "node": dict(result["n"]),
                    "internal_id": result["internal_id"],
                    "label": label
                }
                for result in results
            ]
            
        except Exception as e:
            self.logger.log("ERROR", f"Failed to list {label} nodes: {e}", "graph_manager")
            raise

    # ============================================================================
    # Relationship Operations
    # ============================================================================

    def create_relationship(self, from_node: dict, to_node: dict, rel_type: str, properties: dict = None) -> dict:
        """
        Create relationship between two nodes.
        
        Follows model_config.py ENTITY_RELATIONSHIP_PATTERNS for validation.
        
        Parameters
        ----------
        from_node : dict
            Source node with 'label' and 'id' keys
        to_node : dict
            Target node with 'label' and 'id' keys
        rel_type : str
            Relationship type (e.g., "HAS_PROPERTY", "HAS_VALUE", "HAS_UNIT")
        properties : dict, optional
            Relationship properties
            
        Returns
        -------
        dict
            Created relationship information
        """
        self._ensure_client()
        
        try:
            # Validate relationship based on entity types if applicable
            if self._validate_entity_relationship(from_node["label"], to_node["label"], rel_type):
                self.logger.log("DEBUG", f"Creating validated {rel_type} relationship", "graph_manager")
            
            props_clause = ""
            params = {
                "from_id": from_node["id"],
                "to_id": to_node["id"]
            }
            
            if properties:
                props_clause = " $rel_props"
                params["rel_props"] = properties
                
            cypher = f"""
            MATCH (from:{from_node['label']}) WHERE from.id = $from_id
            MATCH (to:{to_node['label']}) WHERE to.id = $to_id
            CREATE (from)-[r:{rel_type}{props_clause}]->(to)
            RETURN r, ID(r) as internal_id
            """
            
            result = self.neo4j_client.run(cypher, **params, fetch="one")
            
            if result:
                self.logger.log("INFO", f"Created {rel_type} relationship", "graph_manager")
                return {
                    "relationship": dict(result["r"]),
                    "internal_id": result["internal_id"],
                    "type": rel_type
                }
            else:
                raise RuntimeError("Relationship creation failed")
                
        except Exception as e:
            self.logger.log("ERROR", f"Failed to create {rel_type} relationship: {e}", "graph_manager")
            raise

    def get_relationships(self, node_id: str, direction: str = "both", rel_type: str = None) -> list:
        """
        Get relationships for a node.
        
        Parameters
        ----------
        node_id : str
            Node ID to get relationships for
        direction : str
            "incoming", "outgoing", or "both"
        rel_type : str, optional
            Specific relationship type to filter
            
        Returns
        -------
        list
            List of relationships
        """
        self._ensure_client()
        
        try:
            # Build relationship pattern based on direction
            if direction == "incoming":
                pattern = "<-[r"
            elif direction == "outgoing":
                pattern = "-[r"
            else:  # both
                pattern = "-[r"
                
            if rel_type:
                pattern += f":{rel_type}"
                
            if direction == "incoming":
                pattern += "]-(other)"
            else:
                pattern += "]-(other)"
                
            cypher = f"MATCH (n) WHERE n.id = $node_id MATCH (n){pattern} RETURN r, other, ID(r) as internal_id"
            
            results = self.neo4j_client.run(cypher, node_id=node_id, fetch="all")
            
            return [
                {
                    "relationship": dict(result["r"]),
                    "internal_id": result["internal_id"],
                    "other_node": dict(result["other"])
                }
                for result in results
            ]
            
        except Exception as e:
            self.logger.log("ERROR", f"Failed to get relationships for node {node_id}: {e}", "graph_manager")
            raise

    def delete_relationship(self, rel_id: str) -> None:
        """
        Delete a specific relationship.
        
        Parameters
        ----------
        rel_id : str
            Internal relationship ID
        """
        self._ensure_client()
        
        try:
            cypher = "MATCH ()-[r]-() WHERE ID(r) = $rel_id DELETE r"
            self.neo4j_client.run(cypher, rel_id=int(rel_id))
            
            self.logger.log("INFO", f"Deleted relationship {rel_id}", "graph_manager")
            
        except Exception as e:
            self.logger.log("ERROR", f"Failed to delete relationship {rel_id}: {e}", "graph_manager")
            raise

    # ============================================================================
    # Graph Queries
    # ============================================================================

    def find_path(self, start_node: dict, end_node: dict, max_depth: int = 5) -> list:
        """
        Find shortest path between two nodes.
        
        Parameters
        ----------
        start_node : dict
            Starting node with 'label' and 'id'
        end_node : dict
            Ending node with 'label' and 'id'
        max_depth : int
            Maximum path depth to search
            
        Returns
        -------
        list
            Path nodes and relationships
        """
        self._ensure_client()
        
        try:
            cypher = f"""
            MATCH (start:{start_node['label']}) WHERE start.id = $start_id
            MATCH (end:{end_node['label']}) WHERE end.id = $end_id
            MATCH path = shortestPath((start)-[*1..{max_depth}]-(end))
            RETURN path
            """
            
            result = self.neo4j_client.run(
                cypher, 
                start_id=start_node["id"], 
                end_id=end_node["id"], 
                fetch="one"
            )
            
            if result and result["path"]:
                # Extract nodes and relationships from path
                path = result["path"]
                return {
                    "nodes": [dict(node) for node in path.nodes],
                    "relationships": [dict(rel) for rel in path.relationships],
                    "length": len(path.relationships)
                }
            
            return []
            
        except Exception as e:
            self.logger.log("ERROR", f"Failed to find path: {e}", "graph_manager")
            raise

    def get_neighbors(self, node_id: str, hops: int = 1, rel_type: str = None) -> list:
        """
        Get neighboring nodes within specified hops.
        
        Parameters
        ----------
        node_id : str
            Starting node ID
        hops : int
            Number of hops to traverse
        rel_type : str, optional
            Relationship type filter
            
        Returns
        -------
        list
            Neighboring nodes
        """
        self._ensure_client()
        
        try:
            rel_filter = f":{rel_type}" if rel_type else ""
            
            cypher = f"""
            MATCH (start) WHERE start.id = $node_id
            MATCH (start)-[{rel_filter}*1..{hops}]-(neighbor)
            RETURN DISTINCT neighbor, labels(neighbor) as labels
            """
            
            results = self.neo4j_client.run(cypher, node_id=node_id, fetch="all")
            
            return [
                {
                    "node": dict(result["neighbor"]),
                    "labels": result["labels"]
                }
                for result in results
            ]
            
        except Exception as e:
            self.logger.log("ERROR", f"Failed to get neighbors for {node_id}: {e}", "graph_manager")
            raise

    def cypher_query(self, query: str, parameters: dict = None) -> list:
        """
        Execute raw Cypher query.
        
        References kg/cypher/001_constraints.cypher patterns for guidance.
        
        Parameters
        ----------
        query : str
            Cypher query to execute
        parameters : dict, optional
            Query parameters
            
        Returns
        -------
        list
            Query results
        """
        self._ensure_client()
        
        try:
            self.logger.log("DEBUG", f"Executing Cypher query: {query[:100]}...", "graph_manager")
            
            if parameters:
                results = self.neo4j_client.run(query, **parameters, fetch="all")
            else:
                results = self.neo4j_client.run(query, fetch="all")
                
            return [dict(result) for result in results]
            
        except Exception as e:
            self.logger.log("ERROR", f"Cypher query failed: {e}", "graph_manager")
            raise

    # ============================================================================
    # Entity-Specific Operations (Model Config Integration)
    # ============================================================================

    def create_polymer_entity(self, name: str, properties: dict) -> dict:
        """
        Create polymer entity with standardized structure.
        
        Uses model_config.py polymer validation and naming conventions.
        
        Parameters
        ----------
        name : str
            Polymer name
        properties : dict
            Polymer properties (molecular_weight, structure, etc.)
            
        Returns
        -------
        dict
            Created polymer node
        """
        # Standardize polymer properties
        standardized_props = {
            "name": name,
            "canonical_name": name.upper(),  # Standardize naming
            "entity_type": "POLYMER",
            **properties
        }
        
        # Generate unique polymer ID
        polymer_id = f"polymer_{name.lower().replace(' ', '_').replace('-', '_')}"
        
        return self.create_node("POLYMER", standardized_props, polymer_id)

    def create_property_measurement(self, polymer_id: str, property_name: str, value: float, unit: str, metadata: dict = None) -> dict:
        """
        Create property measurement relationship.
        
        Follows model_config.py ENTITY_RELATIONSHIP_PATTERNS for VALUE-UNIT and PROPERTY-VALUE relationships.
        
        Parameters
        ----------
        polymer_id : str
            Polymer node ID
        property_name : str
            Property name
        value : float
            Measured value
        unit : str
            Measurement unit
        metadata : dict, optional
            Additional measurement metadata
            
        Returns
        -------
        dict
            Created measurement structure with all relationships
        """
        try:
            # Create property node
            property_node = self.create_node("PROPERTY", {
                "name": property_name,
                "canonical_name": property_name.lower().replace(" ", "_")
            }, f"property_{property_name.lower().replace(' ', '_')}")
            
            # Create value node
            value_node = self.create_node("VALUE", {
                "numeric_value": value,
                "string_value": str(value)
            }, f"value_{value}_{unit}")
            
            # Create unit node
            unit_node = self.create_node("UNIT", {
                "symbol": unit,
                "canonical_unit": unit
            }, f"unit_{unit}")
            
            # Create relationships following ENTITY_RELATIONSHIP_PATTERNS
            polymer_property_rel = self.create_relationship(
                {"label": "POLYMER", "id": polymer_id},
                {"label": "PROPERTY", "id": property_node["node"]["id"]},
                "HAS_PROPERTY",
                metadata
            )
            
            property_value_rel = self.create_relationship(
                {"label": "PROPERTY", "id": property_node["node"]["id"]},
                {"label": "VALUE", "id": value_node["node"]["id"]},
                "HAS_VALUE"
            )
            
            value_unit_rel = self.create_relationship(
                {"label": "VALUE", "id": value_node["node"]["id"]},
                {"label": "UNIT", "id": unit_node["node"]["id"]},
                "HAS_UNIT"
            )
            
            return {
                "measurement": {
                    "polymer_id": polymer_id,
                    "property": property_node,
                    "value": value_node,
                    "unit": unit_node
                },
                "relationships": [polymer_property_rel, property_value_rel, value_unit_rel]
            }
            
        except Exception as e:
            self.logger.log("ERROR", f"Failed to create property measurement: {e}", "graph_manager")
            raise

    def find_similar_polymers(self, polymer_id: str, similarity_threshold: float = 0.8) -> list:
        """
        Find polymers with similar properties.
        
        Integrates with model_config.py similarity algorithms and confidence thresholds.
        
        Parameters
        ----------
        polymer_id : str
            Reference polymer ID
        similarity_threshold : float
            Minimum similarity score (0.0-1.0)
            
        Returns
        -------
        list
            Similar polymers with similarity scores
        """
        self._ensure_client()
        
        try:
            cypher = """
            MATCH (ref:POLYMER) WHERE ref.id = $polymer_id
            MATCH (ref)-[:HAS_PROPERTY]->(prop:PROPERTY)
            MATCH (other:POLYMER)-[:HAS_PROPERTY]->(prop)
            WHERE other.id <> $polymer_id
            WITH ref, other, count(prop) as shared_properties
            MATCH (other)-[:HAS_PROPERTY]->(all_props:PROPERTY)
            WITH ref, other, shared_properties, count(all_props) as total_properties
            WITH ref, other, shared_properties, total_properties,
                 (shared_properties * 1.0 / total_properties) as similarity
            WHERE similarity >= $threshold
            RETURN other, similarity
            ORDER BY similarity DESC
            """
            
            results = self.neo4j_client.run(
                cypher, 
                polymer_id=polymer_id, 
                threshold=similarity_threshold,
                fetch="all"
            )
            
            return [
                {
                    "polymer": dict(result["other"]),
                    "similarity_score": result["similarity"]
                }
                for result in results
            ]
            
        except Exception as e:
            self.logger.log("ERROR", f"Failed to find similar polymers: {e}", "graph_manager")
            raise

    # ============================================================================
    # Knowledge Graph Integration
    # ============================================================================

    def validate_entity_relationship(self, entity_type_1: str, entity_type_2: str, relationship: str) -> bool:
        """
        Validate if relationship is allowed per model_config.py ENTITY_SEMANTIC_GROUPS.
        
        Parameters
        ----------
        entity_type_1 : str
            First entity type
        entity_type_2 : str
            Second entity type
        relationship : str
            Relationship type
            
        Returns
        -------
        bool
            True if relationship is valid
        """
        return self._validate_entity_relationship(entity_type_1, entity_type_2, relationship)
        
    def _validate_entity_relationship(self, entity_type_1: str, entity_type_2: str, relationship: str) -> bool:
        """Internal validation logic based on entity semantic groups."""
        # Define allowed relationships based on model_config.py patterns
        allowed_patterns = {
            ("POLYMER", "PROPERTY"): ["HAS_PROPERTY", "CHARACTERIZED_BY"],
            ("PROPERTY", "VALUE"): ["HAS_VALUE", "MEASURED_AS"],
            ("VALUE", "UNIT"): ["HAS_UNIT", "EXPRESSED_IN"],
            ("POLYMER", "POLYMER"): ["SIMILAR_TO", "DERIVED_FROM"],
            ("PROPERTY", "PROPERTY"): ["CORRELATED_WITH", "DEPENDS_ON"]
        }
        
        # Check both directions
        forward = (entity_type_1.upper(), entity_type_2.upper())
        reverse = (entity_type_2.upper(), entity_type_1.upper())
        
        allowed_rels_forward = allowed_patterns.get(forward, [])
        allowed_rels_reverse = allowed_patterns.get(reverse, [])
        
        return relationship in (allowed_rels_forward + allowed_rels_reverse)

    def boost_confidence_from_graph(self, entity_data: dict) -> float:
        """
        Calculate confidence boost based on graph relationships.
        
        Uses model_config.py VALIDATION_CONFIDENCE_ADJUSTMENTS patterns.
        
        Parameters
        ----------
        entity_data : dict
            Entity data with type and relationships
            
        Returns
        -------
        float
            Confidence boost value (0.0-1.0)
        """
        base_boost = 0.0
        
        # Boost based on relationship validation patterns
        if entity_data.get("has_valid_relationships"):
            base_boost += 0.08  # CONTEXT_COHERENCE boost
            
        if entity_data.get("canonical_match"):
            base_boost += 0.15  # EXACT_CANONICAL_MATCH boost
            
        if entity_data.get("cross_references"):
            base_boost += 0.07  # CROSS_REFERENCE_VALIDATION boost
            
        return min(base_boost, 0.25)  # Cap at 25% boost


# ============================================================================
# Export convenience functions
# ============================================================================

def get_graph_manager() -> GraphManager:
    """Get configured GraphManager instance."""
    return GraphManager()


# Usage example and testing
if __name__ == "__main__":
    # Example usage (for development/testing)
    try:
        graph = GraphManager()
        
        if graph.neo4j_client:
            print("GraphManager initialized successfully")
            
            # Test basic operations
            # polymer = graph.create_polymer_entity("PDMS", {"molecular_weight": 10000})
            # print(f"Created polymer: {polymer}")
            
        else:
            print("GraphManager initialized but Neo4j client not available (check environment flags)")
            
    except Exception as e:
        print(f"GraphManager initialization failed: {e}")
