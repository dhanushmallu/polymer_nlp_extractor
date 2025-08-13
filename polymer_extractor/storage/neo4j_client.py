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
4) Mirrors the docstring and logging style used in the storage layer.

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
"""

from __future__ import annotations

import os
import time
import typing as t
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
        Initialize the Neo4j driver.

        Parameters
        ----------
        uri : Optional[str]
            Bolt/Neo4j URI. If None, read from NEO4J_URI.
        user : Optional[str]
            Username. If None, read from NEO4J_USER.
        password : Optional[str]
            Password. If None, read from NEO4J_PASSWORD.
        database : Optional[str]
            Target database. Defaults to env NEO4J_DATABASE or 'neo4j'.
        max_pool_size : Optional[int]
            Maximum pooled connections. Defaults to env NEO4J_MAX_POOL_SIZE or 50.
        encrypted : Optional[bool]
            Force encryption toggle (usually inferred from URI). If None, inferred.
        trust_all : Optional[bool]
            Trust all certificates (dev only). Defaults to env NEO4J_TRUST_ALL or False.

        Raises
        ------
        EnvironmentError
            If configuration is insufficient.
        Neo4jError
            If driver initialization fails.
        """
        self._uri = uri or os.getenv("NEO4J_URI")
        self._user = user or os.getenv("NEO4J_USER")
        self._password = password or os.getenv("NEO4J_PASSWORD")
        self._db = database or os.getenv("NEO4J_DATABASE") or "neo4j"
        self._max_pool_size = max_pool_size or _env_int("NEO4J_MAX_POOL_SIZE", 50)

        if not (self._uri and self._user and self._password):
            raise EnvironmentError(
                "[Neo4j Client ERROR] Missing NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD."
            )

        # Encryption and trust settings
        # In most cases, encryption is inferred from the scheme:
        #   - neo4j+s / bolt+s : encrypted and verified
        #   - neo4j+ssc / bolt+ssc : encrypted, self-signed (dev)
        # For bolt://, encryption=False unless forced.
        self._encrypted = (
            encrypted if encrypted is not None else self._uri.startswith(("neo4j+s", "bolt+s", "neo4j+ssc", "bolt+ssc"))
        )
        self._trust_all = trust_all if trust_all is not None else _env_bool("NEO4J_TRUST_ALL", False)

        # Build auth and config
        auth = basic_auth(self._user, self._password)
        config: dict = {
            "max_connection_pool_size": self._max_pool_size,
            # driver 5.x ignores 'encrypted' for neo4j+s/bolt+s (always encrypted),
            # but this remains useful for bolt:// in secure networks.
            "encrypted": self._encrypted,
        }
        if self._trust_all:
            # NOTE: trust_all_certificates is not a top-level driver kwarg anymore;
            # with neo4j+s/bolt+ssc, certificates are accepted without verification.
            logger.warning(
                "NEO4J_TRUST_ALL=true: accepting self-signed/unverified certificates (development only).",
                source="neo4j_client",
                event_type="startup",
            )

        try:
            self._driver = GraphDatabase.driver(self._uri, auth=auth, **config)
            # quick connectivity check to fail fast at boot
            self._driver.verify_connectivity()
            logger.info(
                "Neo4j driver initialized.",
                source="neo4j_client",
                event_type="startup",
                extra={"uri": self._uri, "database": self._db, "max_pool_size": self._max_pool_size},
            )
        except Exception as e:
            logger.critical(
                "Failed to initialize Neo4j driver.",
                source="neo4j_client",
                error=e,
                event_type="startup",
            )
            raise

    # --------------------------------------------------------------------- #
    # Diagnostics
    # --------------------------------------------------------------------- #
    def health_check(self) -> Row:
        """
        Perform a basic health check.

        Returns
        -------
        dict
            JSON-serializable status payload:
            {
              "ok": bool,
              "details": {"version": str|None, "edition": str|None, "database": str},
              "error": str|None
            }
        """
        try:
            self._driver.verify_connectivity()
            # Try to fetch version/edition; works on 4.x/5.x
            rows = self.run(
                "CALL dbms.components() YIELD name, versions, edition "
                "RETURN versions[0] AS version, edition",
                fetch="one",
                access_mode="read",
            )
            version = rows.get("version") if rows else None
            edition = rows.get("edition") if rows else None
            payload: Row = {"ok": True, "details": {"version": version, "edition": edition, "database": self._db}, "error": None}
            logger.debug("Health check OK.", source="neo4j_client", event_type="health_check", extra=payload)
            return payload
        except Exception as e:
            logger.error("Health check failed.", source="neo4j_client", error=e, event_type="health_check")
            return {"ok": False, "details": None, "error": str(e)}

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
        Execute a single Cypher statement with optional fetching.

        Parameters
        ----------
        cypher : str
            Cypher statement to execute.
        params : Optional[Mapping[str, Any]]
            Query parameters. Values are safely transmitted.
        db : Optional[str]
            Target database. Defaults to configured default.
        fetch : {'none','one','all'}, default 'none'
            Fetch mode:
            - 'none' : return None
            - 'one'  : return a single row as dict or None
            - 'all'  : return a list of dict rows (possibly empty)
        access_mode : {'read','write'}, default 'write'
            Route to read or write servers in a cluster.
        retries : int, default 1
            Number of transient retries on failure (e.g., routing, session expired).
        retry_backoff : float, default 0.25
            Initial backoff (seconds), doubles each retry.

        Returns
        -------
        None | dict | list[dict]

        Raises
        ------
        Neo4jError
            When execution fails after all retries.
        """
        database = db or self._db
        mode = _READ if access_mode.lower() == "read" else _WRITE
        attempt = 0

        while True:
            attempt += 1
            try:
                with self._driver.session(database=database, default_access_mode=mode) as session:
                    result = session.run(cypher, **(params or {}))
                    if fetch == "none":
                        # Consume summary for consistency; no result rows needed.
                        result.consume()
                        return None
                    elif fetch == "one":
                        rec = result.single()
                        return _record_to_dict(rec) if rec is not None else None
                    elif fetch == "all":
                        return [_record_to_dict(r) for r in result]
                    return None
            except (ServiceUnavailable, SessionExpired) as e:
                logger.warning(
                    "Transient Neo4j error; will retry.",
                    source="neo4j_client",
                    error=e,
                    event_type="query",
                    extra={"attempt": attempt, "cypher_preview": cypher[:200]},
                )
                if attempt <= retries:
                    time.sleep(retry_backoff)
                    retry_backoff *= 2
                    continue
                raise
            except Neo4jError as e:
                logger.error(
                    "Neo4j query failed.",
                    source="neo4j_client",
                    error=e,
                    event_type="query",
                    extra={"attempt": attempt, "cypher_preview": cypher[:200]},
                )
                raise
            except Exception as e:
                logger.error(
                    "Unexpected error during Neo4j query.",
                    source="neo4j_client",
                    error=e,
                    event_type="query",
                    extra={"attempt": attempt},
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
        Transaction context manager.

        Usage
        -----
        >>> with kg.transaction(access_mode="write") as tx:
        ...     tx.run("MERGE (p:Paper {doi:$d})", d="10.1234/foo")
        ...     # commit happens automatically on successful exit

        Yields
        ------
        neo4j.Transaction
            A transaction bound to a dedicated session.

        Notes
        -----
        - Commit on success; rollback on exception.
        - Always closes the underlying session.
        """
        database = db or self._db
        mode = _READ if access_mode.lower() == "read" else _WRITE
        session = self._driver.session(database=database, default_access_mode=mode)
        tx = session.begin_transaction()
        try:
            yield tx
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            session.close()

    # --------------------------------------------------------------------- #
    # Schema helpers (optional, safe to use at boot)
    # --------------------------------------------------------------------- #
    def create_unique_constraint(self, label: str, property_name: str) -> None:
        """
        Create a uniqueness constraint if it doesn't already exist.

        Parameters
        ----------
        label : str
            Node label, e.g., 'Paper' or 'Canonical'.
        property_name : str
            Property to enforce uniqueness on, e.g., 'doi' or 'name'.
        """
        cypher = f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:`{label}`) REQUIRE n.`{property_name}` IS UNIQUE"
        self.run(cypher, access_mode="write")

    def create_exists_constraint(self, label: str, property_name: str) -> None:
        """
        Create an existence constraint if it doesn't already exist (Neo4j 5+).

        Parameters
        ----------
        label : str
            Node label.
        property_name : str
            Property that must exist on the node.
        """
        cypher = f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:`{label}`) REQUIRE n.`{property_name}` IS NOT NULL"
        self.run(cypher, access_mode="write")

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
        Upsert (MERGE) a node by a set of match keys, optionally setting properties.

        Parameters
        ----------
        label : str
            Node label to MERGE.
        match : Mapping[str, Any]
            Key-value pairs used in MERGE pattern, e.g., {'doi': '10.1234/foo'}.
        on_create : Optional[Mapping[str, Any]]
            Properties to set only when node is created.
        on_match : Optional[Mapping[str, Any]]
            Properties to set only when node matches an existing node.
        db : Optional[str]
            Database override.
        """
        if not match:
            raise ValueError("upsert_node requires at least one match key.")

        # Build MERGE pattern and SET clauses
        m_keys = ", ".join([f"{k}: ${k}" for k in match.keys()])
        set_create = ", ".join([f"n.{k} = $__create_{k}" for k in (on_create or {}).keys()]) or None
        set_match = ", ".join([f"n.{k} = $.__match_{k}" for k in (on_match or {}).keys()]) or None

        cypher = [f"MERGE (n:`{label}` {{ {m_keys} }})"]
        if set_create:
            cypher.append(f"ON CREATE SET {set_create}")
        if set_match:
            cypher.append(f"ON MATCH SET {set_match}")
        cypher.append("RETURN id(n) as id")
        query = "\n".join(cypher)

        params: dict = {}
        params.update(match)
        for k, v in (on_create or {}).items():
            params[f"__create_{k}"] = v
        for k, v in (on_match or {}).items():
            params[f".__match_{k}"] = v  # dot prefix to avoid collision with user keys

        self.run(query, params, db=db, fetch="one", access_mode="write")

    # --------------------------------------------------------------------- #
    # Utilities
    # --------------------------------------------------------------------- #
    def close(self) -> None:
        """Close the underlying driver and free pooled connections."""
        try:
            self._driver.close()
            logger.info("Neo4j driver closed.", source="neo4j_client", event_type="shutdown")
        except Exception as e:
            logger.warning("Error while closing Neo4j driver.", source="neo4j_client", error=e, event_type="shutdown")

    def driver_info(self) -> Row:
        """Return basic driver configuration for diagnostics."""
        return {
            "uri": self._uri,
            "database": self._db,
            "max_pool_size": self._max_pool_size,
            "encrypted": self._encrypted,
            "trust_all": self._trust_all,
        }


__all__ = ["Neo4jClient", "Row", "Rows"]
