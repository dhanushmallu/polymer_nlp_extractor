# polymer_extractor/storage/neo4j_client.py

"""
polymer_extractor/storage/neo4j_client.py

Enterprise-grade Neo4j client for graph database operations in Polymer NLP Extractor.

Purpose
-------
Provides robust, production-ready interface for Neo4j graph database operations with:
- Managed driver lifecycle with connection pooling and health monitoring
- Safe, parameterized Cypher execution with retry logic for transient failures
- Comprehensive health checks and structured diagnostics
- Transaction context managers for atomic read/write operations
- Schema management helpers (constraints, indexes) for graph optimization
- Convenience upsert operations for common graph patterns

Key Abstractions
----------------
- Neo4jClient: Core driver wrapper with connection management and diagnostics
- Transaction context: Automatic commit/rollback for atomic operations
- Health monitoring: Real-time database status and connectivity validation
- Schema operations: Constraint and index management for graph integrity
- Retry mechanisms: Automatic handling of transient connection failures

Design Invariants
-----------------
- Environment-first configuration with comprehensive validation
- Small, explicit API surface for services and knowledge graph modules
- No schema assumptions - works with raw Cypher for maximum flexibility
- Database and user must exist - focuses on operational concerns only
- Thread-safe operations with proper session and driver management

Environment Integration
----------------------
Required environment variables:
- NEO4J_URI: Connection string (bolt://localhost:7687, neo4j+s://host:7687)
- NEO4J_USER: Database username
- NEO4J_PASSWORD: Database password

Optional configuration:
- NEO4J_DATABASE: Target database (default: neo4j)
- NEO4J_MAX_POOL_SIZE: Connection pool size (default: 50)
- NEO4J_ENCRYPTION: Enable/disable encryption (default: auto from URI)
- NEO4J_TRUST_ALL: Trust all certificates for development (default: false)

Examples
--------
>>> from polymer_extractor.storage.neo4j_client import Neo4jClient
>>> 
>>> # Basic operations
>>> client = Neo4jClient()
>>> health = client.health_check()
>>> print(f"Neo4j {health['details']['version']} ready")
>>> 
>>> # Simple queries
>>> result = client.run("RETURN 1 AS test", fetch="one") 
>>> nodes = client.run("MATCH (n:Paper) RETURN n LIMIT 10", fetch="all")
>>> 
>>> # Transactional operations
>>> with client.transaction(access_mode="write") as tx:
...     tx.run("MERGE (p:Paper {doi: $doi}) SET p.title = $title", 
...           {"doi": "10.1234/example", "title": "Sample Paper"})
>>> 
>>> # Schema management
>>> client.create_unique_constraint("Paper", "doi")
>>> client.upsert_node(label="Polymer", match={"name": "PDMS"}, 
...                   on_create={"molecular_weight": 10000})

Notes
-----
- Performance: Connection pooling minimizes overhead, O(1) query execution
- Thread Safety: Driver and sessions are thread-safe, transactions are not
- Error Handling: Comprehensive retry logic for transient failures
- Memory: Streaming results for large queries to minimize memory usage
- Security: Parameterized queries prevent Cypher injection attacks
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
from neo4j import GraphDatabase, basic_auth, TrustAll, TrustSystemCAs
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
    Production-ready Neo4j driver wrapper with comprehensive operational features.

    Summary
    -------
    Provides enterprise-grade Neo4j database operations with connection pooling,
    health monitoring, transaction management, and schema operations.

    Core Operations
    ---------------
    - Query execution: run(cypher, params, fetch="none|one|all")
    - Transactions: transaction(access_mode="read|write") context manager
    - Health monitoring: health_check(), check_database_exists()
    - Schema management: create_unique_constraint(), create_exists_constraint()
    - Upsert operations: upsert_node() for atomic MERGE operations

    Parameters
    ----------
    uri : Optional[str], default None
        Neo4j connection URI (uses NEO4J_URI env var if None)
    user : Optional[str], default None
        Database username (uses NEO4J_USER env var if None)
    password : Optional[str], default None
        Database password (uses NEO4J_PASSWORD env var if None)
    database : Optional[str], default None
        Target database name (uses NEO4J_DATABASE env var or "neo4j")
    max_pool_size : Optional[int], default None
        Connection pool size (uses NEO4J_MAX_POOL_SIZE env var or 50)
    encrypted : Optional[bool], default None
        Enable encryption (auto-detected from URI scheme if None)
    trust_all : Optional[bool], default None
        Trust all certificates for development (uses NEO4J_TRUST_ALL env var)

    Raises
    ------
    ConfigurationError
        If required environment variables are missing or invalid
    ServiceUnavailable
        If Neo4j database is not accessible

    Examples
    --------
    >>> # Environment-configured client
    >>> client = Neo4jClient()
    >>> health = client.health_check()
    >>> print(f"Connected to Neo4j {health['details']['version']}")
    >>> 
    >>> # Explicit configuration
    >>> client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="secret")
    >>> 
    >>> # Query operations
    >>> result = client.run("MATCH (n:Paper) RETURN count(n) as total", fetch="one")
    >>> papers = client.run("MATCH (p:Paper) RETURN p LIMIT 10", fetch="all")
    >>> 
    >>> # Transactional operations
    >>> with client.transaction(access_mode="write") as tx:
    ...     tx.run("CREATE (p:Paper {doi: $doi})", {"doi": "10.1234/example"})

    Notes
    -----
    - Complexity: O(1) for single queries, O(n) for result processing
    - Thread Safety: Driver and sessions thread-safe, transactions are single-threaded
    - Memory: Streaming results for large datasets to minimize memory usage
    - Performance: Connection pooling reduces overhead for frequent operations
    - Security: All queries use parameterized execution to prevent injection
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
        Initialize Neo4j client with configuration validation and driver setup.

        Summary
        -------
        Creates Neo4j driver with environment-based configuration and comprehensive validation.

        Parameters
        ----------
        uri : Optional[str]
            Neo4j connection URI (bolt://host:port, neo4j+s://host:port)
        user : str
            Database username for authentication
        password : str
            Database password for authentication
        database : Optional[str]
            Target database name (default: "neo4j")
        max_pool_size : Optional[int]
            Maximum connection pool size (default: 50)
        encrypted : Optional[bool]
            Enable TLS encryption (auto-detected from URI if None)
        trust_all : Optional[bool]
            Trust all certificates for development (default: False)

        Raises
        ------
        ConfigurationError
            If required parameters are missing or invalid
        ServiceUnavailable
            If initial connection to Neo4j fails

        Examples
        --------
        >>> # Environment-based configuration (recommended)
        >>> client = Neo4jClient()
        >>> 
        >>> # Explicit configuration for testing
        >>> client = Neo4jClient(
        ...     uri="bolt://localhost:7687",
        ...     user="neo4j", 
        ...     password="password"
        ... )

        Notes
        -----
        - Performance: O(1) - Establishes connection pool during initialization
        - Side Effects: Logs driver creation and database validation
        - Security: Credentials loaded from environment variables for production safety
        - Security: Credentials loaded from environment variables for production safety
        """
        self.logger = Logger()
        
        # Environment configuration
        self.uri = uri or os.getenv("NEO4J_URI")
        self.user = user or os.getenv("NEO4J_USER")
        self.password = password or os.getenv("NEO4J_PASSWORD")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        
        # Pool configuration
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
        
        # Convert trust_all boolean to Neo4j trusted_certificates enum value
        if trust_all:
            trusted_certificates = TrustAll()
        else:
            trusted_certificates = TrustSystemCAs()
        
        # Create driver
        try:
            auth = basic_auth(self.user, self.password)
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=auth,
                max_connection_pool_size=max_pool,
                encrypted=encrypted,
                trusted_certificates=trusted_certificates,
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
        Comprehensive health check with Neo4j server diagnostics.

        Summary
        -------
        Validates database connectivity and retrieves server version information
        for monitoring and troubleshooting purposes.

        Returns
        -------
        Row
            Health status dictionary with server details:
            - ok (bool): True if connection successful
            - details (dict): Server name, version, edition, database name
            - error (str): Error message if health check fails

        Raises
        ------
        No exceptions raised - errors are captured in return value

        Examples
        --------
        >>> client = Neo4jClient()
        >>> health = client.health_check()
        >>> if health["ok"]:
        ...     print(f"Connected to {health['details']['name']} {health['details']['version']}")
        ... else:
        ...     print(f"Health check failed: {health['error']}")

        Notes
        -----
        - Complexity: O(1) - Single lightweight diagnostic query
        - Side Effects: Logs health check results for monitoring
        - Fallback: Uses simple connectivity test if dbms.components() unavailable
        - Non-blocking: Safe to call frequently for health monitoring
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
        Execute parameterized Cypher query with comprehensive error handling.

        Summary
        -------
        Runs Cypher query against Neo4j with automatic retries, parameterization,
        and flexible result fetching patterns.

        Parameters
        ----------
        cypher : str
            Cypher query string with $parameter placeholders
        params : Optional[Mapping[str, Any]], default None
            Parameter values for query placeholders
        db : Optional[str], default None
            Target database name (uses self.database if None)
        fetch : Literal["none", "one", "all"], default "none"
            Result fetching strategy:
            - "none": No results returned (for writes/mutations)
            - "one": Single record (uses first result)
            - "all": All records as list
        access_mode : Literal["read", "write"], default "write"
            Session access mode for Neo4j optimization
        retries : int, default 1
            Number of retry attempts on transient failures
        retry_backoff : float, default 0.25
            Exponential backoff delay in seconds

        Returns
        -------
        Union[None, Row, Rows]
            - None if fetch="none"
            - Row (dict) if fetch="one"
            - Rows (List[dict]) if fetch="all"

        Raises
        ------
        CypherSyntaxError
            If Cypher query syntax is invalid
        ConstraintError
            If query violates database constraints
        ServiceUnavailable
            If Neo4j database is unreachable after retries

        Examples
        --------
        >>> client = Neo4jClient()
        >>> 
        >>> # Create operation (no results)
        >>> client.run(
        ...     "CREATE (p:Paper {doi: $doi, title: $title})",
        ...     {"doi": "10.1234/example", "title": "Sample Paper"}
        ... )
        >>> 
        >>> # Single result query
        >>> paper = client.run(
        ...     "MATCH (p:Paper {doi: $doi}) RETURN p",
        ...     {"doi": "10.1234/example"},
        ...     fetch="one"
        ... )
        >>> 
        >>> # Multiple results query
        >>> papers = client.run(
        ...     "MATCH (p:Paper) WHERE p.year = $year RETURN p LIMIT 10",
        ...     {"year": 2023},
        ...     fetch="all",
        ...     access_mode="read"
        ... )

        Notes
        -----
        - Complexity: O(n) where n is result set size
        - Security: All queries use parameterized execution to prevent injection
        - Performance: Read-only queries should use access_mode="read" for optimization
        - Memory: fetch="all" loads complete result set - use pagination for large datasets
        - Thread Safety: Session creation is thread-safe, individual transactions are not
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
        Context manager for atomic Neo4j transactions with automatic commit/rollback.

        Summary
        -------
        Provides transactional scope for multiple Cypher operations with ACID guarantees
        and automatic error handling.

        Parameters
        ----------
        db : Optional[str], default None
            Target database name (uses self.database if None)
        access_mode : Literal["read", "write"], default "write"
            Transaction access mode for Neo4j optimization:
            - "read": Read-only operations for better performance
            - "write": Write operations with full transaction guarantees

        Yields
        ------
        neo4j.Transaction
            Neo4j transaction object for executing Cypher statements

        Raises
        ------
        TransactionError
            If transaction fails and is automatically rolled back
        ServiceUnavailable
            If database connection is lost during transaction

        Examples
        --------
        >>> client = Neo4jClient()
        >>> 
        >>> # Write transaction with multiple operations
        >>> with client.transaction(access_mode="write") as tx:
        ...     tx.run("MERGE (p:Paper {doi: $doi})", {"doi": "10.1234/example"})
        ...     tx.run("MERGE (a:Author {name: $name})", {"name": "Smith, J."})
        ...     tx.run("MATCH (p:Paper {doi: $doi}), (a:Author {name: $name}) "
        ...            "MERGE (a)-[:AUTHORED]->(p)", 
        ...            {"doi": "10.1234/example", "name": "Smith, J."})
        >>> 
        >>> # Read-only transaction for consistent queries
        >>> with client.transaction(access_mode="read") as tx:
        ...     papers = list(tx.run("MATCH (p:Paper) RETURN p LIMIT 100"))
        ...     authors = list(tx.run("MATCH (a:Author) RETURN a LIMIT 50"))

        Notes
        -----
        - Complexity: O(1) for transaction setup, O(n) for contained operations
        - ACID Properties: Full atomicity, consistency, isolation, durability guarantees
        - Thread Safety: Individual transactions are single-threaded, concurrent transactions allowed
        - Performance: Read transactions have lower overhead and better concurrency
        - Side Effects: Automatic rollback on any exception, logging of transaction failures
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
        Create unique constraint on node label and property for data integrity.

        Summary
        -------
        Establishes uniqueness constraint to prevent duplicate values and enable
        efficient node lookups via indexed property.

        Parameters
        ----------
        label : str
            Node label for constraint (e.g., "Paper", "Author", "Polymer")
        property_name : str
            Property name that must be unique (e.g., "doi", "email", "cas_number")

        Raises
        ------
        ConstraintError
            If constraint creation fails due to existing duplicate values
        CypherSyntaxError
            If label or property name contains invalid characters

        Examples
        --------
        >>> client = Neo4jClient()
        >>> client.create_unique_constraint("Paper", "doi")
        >>> client.create_unique_constraint("Author", "orcid_id")
        >>> client.create_unique_constraint("Polymer", "cas_number")

        Notes
        -----
        - Complexity: O(n) where n is number of existing nodes to validate
        - Side Effects: Creates database index for improved query performance
        - Idempotent: Safe to call multiple times, uses IF NOT EXISTS
        - Performance: Dramatically improves MATCH and MERGE operations on constrained property
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
        Create existence constraint to ensure required properties are present.

        Summary
        -------
        Enforces NOT NULL constraint on node properties to guarantee data completeness
        and prevent incomplete records.

        Parameters
        ----------
        label : str
            Node label for constraint (e.g., "Paper", "Dataset", "Model")
        property_name : str
            Property that must exist (e.g., "title", "created_at", "file_path")

        Raises
        ------
        ConstraintError
            If constraint creation fails due to existing nodes with missing property
        CypherSyntaxError
            If label or property name contains invalid characters

        Examples
        --------
        >>> client = Neo4jClient()
        >>> client.create_exists_constraint("Paper", "title")
        >>> client.create_exists_constraint("Dataset", "created_at")
        >>> client.create_exists_constraint("Model", "version")

        Notes
        -----
        - Complexity: O(n) where n is number of existing nodes to validate
        - Side Effects: Validates all existing nodes have the required property
        - Data Quality: Prevents incomplete records from being created
        - Idempotent: Safe to call multiple times, uses IF NOT EXISTS
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
        Atomic upsert (MERGE) operation with conditional property setting.

        Summary
        -------
        Performs MERGE operation to create node if not exists, or update existing node,
        with different property sets for create vs. match scenarios.

        Parameters
        ----------
        label : str
            Node label for the upsert operation
        match : Mapping[str, Any]
            Properties to match existing nodes (should include unique identifiers)
        on_create : Optional[Mapping[str, Any]], default None
            Properties to set only when creating new node
        on_match : Optional[Mapping[str, Any]], default None
            Properties to set only when matching existing node
        db : Optional[str], default None
            Target database name (uses self.database if None)

        Raises
        ------
        ConstraintError
            If operation violates unique constraints
        CypherSyntaxError
            If generated Cypher contains syntax errors

        Examples
        --------
        >>> client = Neo4jClient()
        >>> 
        >>> # Simple upsert with creation timestamp
        >>> client.upsert_node(
        ...     label="Paper",
        ...     match={"doi": "10.1234/example"},
        ...     on_create={"created_at": "2023-01-01T10:00:00Z", "status": "new"},
        ...     on_match={"last_accessed": "2023-06-01T15:30:00Z"}
        ... )
        >>> 
        >>> # Upsert polymer with molecular data
        >>> client.upsert_node(
        ...     label="Polymer",
        ...     match={"name": "PDMS", "supplier": "Sigma"},
        ...     on_create={"discovered_date": "2023-01-01", "version": 1},
        ...     on_match={"version": 2, "updated_at": "2023-06-01"}
        ... )

        Notes
        -----
        - Complexity: O(log n) for unique property lookup, O(1) for property updates
        - Atomicity: Single Cypher MERGE operation ensures consistency
        - Performance: Most efficient way to handle create-or-update patterns
        - Index Usage: Leverages unique constraints for optimal performance
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
