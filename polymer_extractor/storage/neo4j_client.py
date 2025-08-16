# polymer_extractor/storage/neo4j_client.py

"""
Neo4j Client for Polymer NLP Extractor.

Purpose
-------
A single, reliable entry point for connecting to and querying Neo4j with:
- Managed driver lifecycle
- Safe, parameterized Cypher execution
- Health checks and structured diagnostics
- Transaction context manager (read/write)
- Minimal retry logic for transient routing/connection errors
- Convenience helpers for common tasks (constraints, upsert)

Design Principles
-----------------
1) Environment-first configuration (dotenv) with clear validation.
2) Small, explicit API surface that services and KG modules can depend on.
3) No schema assumptions — works with raw Cypher (ready for KG repository/pipeline).
4) Assumes database and user already exist - only manages constraints and schemas.

Environment Variables
---------------------
Required
- NEO4J_URI            e.g., bolt://localhost:7687 or neo4j+s://<host>:7687
- NEO4J_USER
- NEO4J_PASSWORD

Optional
- NEO4J_DATABASE       (default: neo4j)
- NEO4J_MAX_POOL_SIZE  (default: 50)
- NEO4J_ENCRYPTION     (true|false; default: auto from URI scheme)
- NEO4J_TRUST_ALL      (true|false; only for development; default: false)

Examples
--------
>>> from polymer_extractor.storage.neo4j_client import Neo4jClient
>>> kg = Neo4jClient()
>>> kg.health_check()
{'ok': True, 'details': {'edition': 'community', 'version': '5.x', 'database': 'neo4j'}}

>>> kg.run("RETURN 1 AS ok", fetch="one")
{'ok': 1}

>>> with kg.transaction(access_mode="write") as tx:
...     tx.run("MERGE (p:Paper {doi:$doi})", doi="10.1234/foo")

Notes
-----
- Keep the client focused on connectivity, execution, and diagnostics.
- Higher-level KG logic (canonicalization, validation, boosting) should live in
  knowledge_graph/* modules and call into this client.
- Database and user must exist before initializing the client.
"""

from __future__ import annotations
import os
import time
import traceback
import typing as t
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

from dotenv import load_dotenv
from neo4j import GraphDatabase, basic_auth
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired

from polymer_extractor.utils.logging import Logger

# === Load environment variables early (consistent with other storage clients) ===
load_dotenv()
logger = Logger()

# === Type aliases ===
Row = t.Dict[str, t.Any]
Rows = t.List[Row]

# Access mode mapping for readability
_READ = "READ"
_WRITE = "WRITE"


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    try:
        return int(val) if val is not None else default
    except ValueError:
        logger.warning(
            f"Invalid int for {name}='{val}', falling back to {default}",
            source="neo4j_client",
            event_type="config",
        )
        return default


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}


def _record_to_dict(rec) -> Row:
    # neo4j.Record -> dict
    return dict(rec.items())


class Neo4jClient:
    """
    Neo4j pooled driver wrapper.

    Responsibilities
    ----------------
    - Validate configuration and create a driver with sane defaults.
    - Provide simple, safe Cypher execution helpers (read/write).
    - Offer a transaction context manager with automatic commit/rollback.
    - Provide health checks and structured error logging.

    Non-Responsibilities
    --------------------
    - No Cypher generation for domain logic (done in KG modules).
    - No schema migrations (helpers available but not opinionated).
    - No database creation (databases and users must exist).
    """

    def __init__(
        self,
        uri: t.Optional[str] = None,
        user: t.Optional[str] = None,
        password: t.Optional[str] = None,
        database: t.Optional[str] = None,
        max_pool_size: t.Optional[int] = None,
        encrypted: t.Optional[bool] = None,
        trust_all: t.Optional[bool] = None,
    ) -> None:
        """
        Initialize Neo4j client.
        
        Assumes the database already exists with proper permissions.
        Will only create constraints and schemas as needed.
        
        Parameters
        ----------
        uri : str, optional
            Neo4j URI (default: from NEO4J_URI env var)
        user : str, optional
            Neo4j user (default: from NEO4J_USER env var)
        password : str, optional
            Neo4j password (default: from NEO4J_PASSWORD env var)
        database : str, optional
            Neo4j database (default: from NEO4J_DATABASE env var or 'neo4j')
        max_pool_size : int, optional
            Max connections (default: from NEO4J_MAX_POOL_SIZE env var or 50)
        encrypted : bool, optional
            Use encryption (default: auto from URI scheme)
        trust_all : bool, optional
            Trust all certificates - DEVELOPMENT ONLY (default: False)
        """
        self.logger = logger
        
        # Resolve config from env if not provided
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        
        if not self.password:
            raise ValueError("Neo4j password is required. Set NEO4J_PASSWORD or provide password parameter.")
        
        # Driver settings
        max_pool = max_pool_size or _env_int("NEO4J_MAX_POOL_SIZE", 50)
        
        # Encryption handling
        if encrypted is None:
            encrypted = self.uri.startswith(("neo4j+s://", "neo4j+ssc://", "bolt+s://", "bolt+ssc://"))
        
        trust_all = trust_all or _env_bool("NEO4J_TRUST_ALL", False)
        
        # Convert trust_all boolean to Neo4j trust enum value
        if trust_all:
            trust_config = "TRUST_ALL_CERTIFICATES"
        else:
            trust_config = "TRUST_SYSTEM_CA_SIGNED_CERTIFICATES"
        
        # Create driver
        try:
            auth = basic_auth(self.user, self.password)
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=auth,
                max_connection_pool_size=max_pool,
                encrypted=encrypted,
                trust=trust_config,
            )
            
            self.logger.info(
                f"Neo4j client initialized: {self.uri} (database: {self.database})",
                source="neo4j_client",
                event_type="initialization",
            )
            
            # Database existence check is deferred to prevent handshake issues during initialization
            self.logger.info("Neo4j driver created successfully. Database validation deferred to first operation.",
                           source="neo4j_client", event_type="driver_ready")
                
        except Exception as e:
            self.logger.critical(
                f"Failed to initialize Neo4j driver.\nStack trace:\n{traceback.format_exc()}",
                source="neo4j_client",
                event_type="initialization_error",
            )
            raise

    # --------------------------------------------------------------------- #
    # Diagnostics
    # --------------------------------------------------------------------- #
    def health_check(self) -> Row:
        """
        Perform a health check on the Neo4j connection.

        Returns
        -------
        Row
            Health status and server details.
        """
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("CALL dbms.components() YIELD name, versions, edition")
                components = list(result)

                if components:
                    kernel = components[0]
                    return {
                        "ok": True,
                        "details": {
                            "name": kernel["name"],
                            "version": kernel["versions"][0],
                            "edition": kernel["edition"],
                            "database": self.database,
                        },
                    }
                else:
                    # Fallback if dbms.components() is not available
                    result = session.run("RETURN 1 AS status")
                    result.consume()
                    return {
                        "ok": True,
                        "details": {
                            "database": self.database,
                            "status": "connected",
                        },
                    }

        except Exception as e:
            self.logger.error(
                "Neo4j health check failed",
                source="neo4j_client",
                error=e,
                event_type="health_check",
            )
            return {
                "ok": False,
                "error": str(e),
            }

    def check_database_exists(self) -> t.Dict[str, t.Any]:
        """
        Check if the target database exists and is accessible.
        
        Returns
        -------
        Dict[str, Any]
            Database existence status and details
        """
        result = {
            "exists": False,
            "accessible": False,
            "database_name": self.database,
            "error": None,
            "timestamp": datetime.now().isoformat() + "Z"
        }
        
        try:
            with self.driver.session() as session:
                # Check if we can access system database to list databases
                try:
                    db_result = session.run("SHOW DATABASES")
                    databases = [record["name"] for record in db_result]
                    
                    if self.database in databases:
                        result["exists"] = True
                        
                        # Try to access the target database
                        try:
                            with self.driver.session(database=self.database) as db_session:
                                db_session.run("RETURN 1 as test")
                                result["accessible"] = True
                                self.logger.info(f"Database '{self.database}' exists and is accessible", 
                                               source="neo4j_client", event_type="database_check")
                        except Exception as access_error:
                            result["error"] = f"Database exists but not accessible: {access_error}"
                    else:
                        result["error"] = f"Database '{self.database}' not found. Available: {databases}"
                        
                except Exception as show_error:
                    # Fallback: try to connect directly to the database
                    try:
                        with self.driver.session(database=self.database) as db_session:
                            db_session.run("RETURN 1 as test")
                            result["exists"] = True
                            result["accessible"] = True
                            self.logger.info(f"Database '{self.database}' is accessible (direct test)", 
                                           source="neo4j_client", event_type="database_check")
                    except Exception as direct_error:
                        result["error"] = f"Cannot access database: {direct_error}"
                        
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"Database existence check failed: {e}", 
                            source="neo4j_client", event_type="database_check")
        
        return result

    # --------------------------------------------------------------------- #
    # Query execution
    # --------------------------------------------------------------------- #
    def run(
        self,
        cypher: str,
        params: t.Optional[t.Mapping[str, t.Any]] = None,
        *,
        db: t.Optional[str] = None,
        fetch: t.Literal["none", "one", "all"] = "none",
        access_mode: t.Literal["read", "write"] = "write",
        retries: int = 1,
        retry_backoff: float = 0.25,
    ) -> t.Union[None, Row, Rows]:
        """
        Execute a Cypher query.

        Parameters
        ----------
        cypher : str
            Cypher query to execute.
        params : Optional[Mapping[str, Any]]
            Parameters for the Cypher query.
        db : Optional[str]
            Database to run against (default: self.database).
        fetch : Literal["none", "one", "all"]
            How to fetch results: "none" (no fetch), "one" (single record), "all" (all records).
        access_mode : Literal["read", "write"]
            Transaction access mode.
        retries : int
            Number of retry attempts for transient errors.
        retry_backoff : float
            Backoff multiplier for retries.

        Returns
        -------
        Union[None, Row, Rows]
            Query results based on fetch parameter.
        """
        database = db or self.database
        mode = _WRITE if access_mode == "write" else _READ

        for attempt in range(1, retries + 1):
            try:
                with self.driver.session(database=database, default_access_mode=mode) as session:
                    result = session.run(cypher, params or {})

                    if fetch == "none":
                        result.consume()
                        return None
                    elif fetch == "one":
                        record = result.single()
                        return _record_to_dict(record) if record else None
                    elif fetch == "all":
                        records = list(result)
                        return [_record_to_dict(record) for record in records]

            except (ServiceUnavailable, SessionExpired) as e:
                # Transient errors that might benefit from retry
                self.logger.warning(
                    f"Neo4j transient error (attempt {attempt}/{retries})",
                    source="neo4j_client",
                    error=e,
                    event_type="query_retry",
                )
                if attempt >= retries:
                    raise
                # Exponential backoff
                time.sleep(retry_backoff * (2 ** (attempt - 1)))

            except Exception as e:
                # Non-transient errors
                self.logger.error(
                    f"Neo4j query failed: {cypher[:100]}...",
                    source="neo4j_client",
                    error=e,
                    event_type="query_error",
                )
                raise

    # --------------------------------------------------------------------- #
    # Transactions
    # --------------------------------------------------------------------- #
    @contextmanager
    def transaction(
        self,
        *,
        db: t.Optional[str] = None,
        access_mode: t.Literal["read", "write"] = "write",
    ):
        """
        Context manager for Neo4j transactions.

        Parameters
        ----------
        db : Optional[str]
            Database to run against (default: self.database).
        access_mode : Literal["read", "write"]
            Transaction access mode.

        Yields
        ------
        neo4j.Transaction
            Neo4j transaction object.

        Examples
        --------
        >>> with kg.transaction(access_mode="write") as tx:
        ...     tx.run("MERGE (p:Paper {doi: $doi})", doi="10.1234/test")
        """
        database = db or self.database
        mode = _WRITE if access_mode == "write" else _READ

        with self.driver.session(database=database, default_access_mode=mode) as session:
            with session.begin_transaction() as tx:
                try:
                    yield tx
                except Exception as e:
                    self.logger.error(
                        "Neo4j transaction failed and was rolled back",
                        source="neo4j_client",
                        error=e,
                        event_type="transaction_error",
                    )
                    raise

    # --------------------------------------------------------------------- #
    # Schema helpers (optional, safe to use at boot)
    # --------------------------------------------------------------------- #
    def create_unique_constraint(self, label: str, property_name: str) -> None:
        """
        Create a unique constraint on a label and property.

        Parameters
        ----------
        label : str
            Node label.
        property_name : str
            Property name.
        """
        constraint_name = f"unique_{label}_{property_name}".lower()
        cypher = f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{property_name} IS UNIQUE"
        self.run(cypher)
        self.logger.info(
            f"Created unique constraint: {label}.{property_name}",
            source="neo4j_client",
            event_type="constraint_creation",
        )

    def create_exists_constraint(self, label: str, property_name: str) -> None:
        """
        Create an existence constraint on a label and property.

        Parameters
        ----------
        label : str
            Node label.
        property_name : str
            Property name.
        """
        constraint_name = f"exists_{label}_{property_name}".lower()
        cypher = f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{property_name} IS NOT NULL"
        self.run(cypher)
        self.logger.info(
            f"Created existence constraint: {label}.{property_name}",
            source="neo4j_client",
            event_type="constraint_creation",
        )

    # --------------------------------------------------------------------- #
    # Convenience upsert (MERGE) helpers — thin, intentionally generic
    # --------------------------------------------------------------------- #
    def upsert_node(
        self,
        *,
        label: str,
        match: t.Mapping[str, t.Any],
        on_create: t.Optional[t.Mapping[str, t.Any]] = None,
        on_match: t.Optional[t.Mapping[str, t.Any]] = None,
        db: t.Optional[str] = None,
    ) -> None:
        """
        Upsert (MERGE) a node with conditional property setting.

        Parameters
        ----------
        label : str
            Node label.
        match : Mapping[str, Any]
            Properties to match on.
        on_create : Optional[Mapping[str, Any]]
            Properties to set only when creating.
        on_match : Optional[Mapping[str, Any]]
            Properties to set only when matching existing node.
        db : Optional[str]
            Database to run against.
        """
        # Build MERGE clause
        match_props = ", ".join(f"{k}: ${k}" for k in match.keys())
        cypher = f"MERGE (n:{label} {{{match_props}}})"

        params = dict(match)

        # Add ON CREATE clause if needed
        if on_create:
            create_props = ", ".join(f"n.{k} = $create_{k}" for k in on_create.keys())
            cypher += f" ON CREATE SET {create_props}"
            params.update({f"create_{k}": v for k, v in on_create.items()})

        # Add ON MATCH clause if needed
        if on_match:
            match_props = ", ".join(f"n.{k} = $match_{k}" for k in on_match.keys())
            cypher += f" ON MATCH SET {match_props}"
            params.update({f"match_{k}": v for k, v in on_match.items()})

        self.run(cypher, params, db=db)

    # --------------------------------------------------------------------- #
    # Schema Management
    # --------------------------------------------------------------------- #
    def deploy_constraints(self, constraint_file: str = None) -> t.Dict[str, t.Any]:
        """
        Deploy Neo4j constraints from Cypher file.
        
        Parameters
        ----------
        constraint_file : str, optional
            Path to Cypher constraints file
            
        Returns
        -------
        Dict[str, Any]
            Deployment result with status and details
        """
        result = {
            "success": False,
            "operation": "deploy_constraints",
            "file_path": constraint_file,
            "constraints_created": [],
            "error": None
        }
        
        try:
            if constraint_file:
                constraints_path = Path(constraint_file)
            else:
                # Default constraint file location
                constraints_path = Path("kg/cypher/001_constraints.cypher")
            
            if not constraints_path.exists():
                result["error"] = f"Constraints file not found: {constraints_path}"
                return result
            
            constraints_cypher = constraints_path.read_text()
            
            # Split into individual statements and execute
            statements = [stmt.strip() for stmt in constraints_cypher.split(';') if stmt.strip()]
            
            for statement in statements:
                if statement.upper().startswith('CREATE CONSTRAINT'):
                    self.run(statement)
                    result["constraints_created"].append(statement[:50] + "...")
                    
            result["success"] = True
            
            self.logger.info(
                f"Neo4j constraints deployed successfully from {constraints_path}",
                source="neo4j_client",
                event_type="constraint_deployment"
            )
            
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(
                f"Failed to deploy constraints from {constraint_file}",
                source="neo4j_client",
                error=e,
                event_type="constraint_deployment"
            )
            
        return result

    def reset_database(self, confirm: bool = False) -> t.Dict[str, t.Any]:
        """
        Reset database by removing all nodes and relationships (not the database itself).
        
        Parameters
        ----------
        confirm : bool
            Must be True to actually perform the reset (safety check)
            
        Returns
        -------
        Dict[str, Any]
            Reset result with status and details
        """
        result = {
            "success": False,
            "operation": "reset_database",
            "nodes_deleted": 0,
            "relationships_deleted": 0,
            "error": None
        }
        
        if not confirm:
            result["error"] = "Reset not confirmed. Set confirm=True to proceed."
            return result
        
        try:
            # Count nodes and relationships before deletion
            node_count = self.run("MATCH (n) RETURN count(n) AS count", fetch="one")["count"]
            rel_count = self.run("MATCH ()-[r]->() RETURN count(r) AS count", fetch="one")["count"]
            
            # Delete all relationships first, then nodes
            self.run("MATCH ()-[r]->() DELETE r")
            self.run("MATCH (n) DELETE n")
            
            result["nodes_deleted"] = node_count
            result["relationships_deleted"] = rel_count
            result["success"] = True
            
            self.logger.info(
                f"Neo4j database reset completed. Deleted {node_count} nodes and {rel_count} relationships",
                source="neo4j_client",
                event_type="database_reset"
            )
            
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(
                "Failed to reset Neo4j database",
                source="neo4j_client",
                error=e,
                event_type="database_reset"
            )
            
        return result

    # --------------------------------------------------------------------- #
    # Utilities
    # --------------------------------------------------------------------- #
    def close(self) -> None:
        """Close the Neo4j driver."""
        try:
            self.driver.close()
            self.logger.info(
                "Neo4j driver closed",
                source="neo4j_client",
                event_type="cleanup",
            )
        except Exception as e:
            self.logger.warning(
                "Error closing Neo4j driver",
                source="neo4j_client",
                error=e,
                event_type="cleanup",
            )

    def driver_info(self) -> Row:
        """
        Get driver configuration information.

        Returns
        -------
        Row
            Driver configuration details.
        """
        return {
            "uri": self.uri,
            "database": self.database,
            "user": self.user,
            # Note: Don't include password in info response
        }

    def service_status(self) -> t.Dict[str, t.Any]:
        """
        Get Neo4j service status.
        
        Returns
        -------
        t.Dict[str, t.Any]
            Service status information with 'status' key ('healthy', 'error', 'unavailable')
        """
        try:
            # Check if we can connect and verify the connection
            with self.driver.session() as session:
                result = session.run("RETURN 1 as test")
                result.consume()
            
            return {
                "status": "healthy",
                "service": "neo4j",
                "uri": self.uri,
                "database": self.database,
                "message": "Neo4j is accessible and responding"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "service": "neo4j",
                "error": str(e),
                "message": f"Neo4j connection failed: {e}"
            }

    def validate_database_on_demand(self) -> t.Dict[str, t.Any]:
        """
        Validate database existence and accessibility when explicitly requested.
        This method should be called after initialization to verify database setup.
        
        Returns
        -------
        t.Dict[str, t.Any]
            Database validation results
        """
        try:
            db_check = self.check_database_exists()
            if not db_check["exists"] or not db_check["accessible"]:
                self.logger.warning(f"Database validation issue: {db_check.get('error', 'Database not accessible')}", 
                                  source="neo4j_client", event_type="database_validation")
            else:
                self.logger.info(f"Database '{self.database}' validated successfully", 
                               source="neo4j_client", event_type="database_validation")
            return db_check
        except Exception as e:
            error_msg = f"Database validation failed: {e}"
            self.logger.error(error_msg, source="neo4j_client", event_type="database_validation")
            return {
                "exists": False,
                "accessible": False,
                "database_name": self.database,
                "error": error_msg,
                "timestamp": datetime.now().isoformat() + "Z"
            }


__all__ = ["Neo4jClient", "Row", "Rows"]
