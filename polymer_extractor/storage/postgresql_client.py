# polymer_extractor/storage/postgresql_client.py

"""
PostgreSQL Client for Polymer NLP Extractor.

Purpose
-------
A single, reliable entry point for connecting to and querying PostgreSQL with:
- Connection pooling
- Safe parameterized queries
- Health checks and structured diagnostics
- Transaction context manager
- Batched executions and bulk COPY support
- Optional pagination helpers
- Minimal retry logic for transient errors

Design Principles
-----------------
1) Environment-first configuration (dotenv) with clear validation.
2) Small, explicit API surface that services and repositories can depend on.
3) No ORM assumptions — works with raw SQL (ready for repository pattern).
4) Mirrors the docstring and logging style used in the storage layer for Appwrite,
   providing consistent developer ergonomics across storage clients.

Environment Variables
---------------------
The client reads either a DSN or individual parts. These are the supported keys:

Mandatory (one of the following)
- POSTGRES_DSN
  e.g., postgresql://polymer:polymer_password@localhost:5432/polymer_extractor

OR all of:
- POSTGRES_HOST
- POSTGRES_PORT
- POSTGRES_DB
- POSTGRES_USER
- POSTGRES_PASSWORD

Optional
- POSTGRES_MIN_CONN (default: 1)
- POSTGRES_MAX_CONN (default: 10)
- POSTGRES_CONNECT_TIMEOUT (seconds, default: 10)
- POSTGRES_APPLICATION_NAME (default: polymer-nlp-extractor)

Examples
--------
>>> from polymer_extractor.storage.postgresql_client import PostgresClient
>>> db = PostgresClient()
>>> db.health_check()
{'ok': True, 'details': {'server_version': '16.x', 'pool': {'min': 1, 'max': 10, 'in_use': 0}}}

>>> db.run("SELECT 1 AS ok;", fetch="one")
{'ok': 1}

>>> with db.transaction() as cur:
...     cur.execute("INSERT INTO papers (doi, title) VALUES (%s, %s) RETURNING id", ("10.1234/foo", "Title"))
...     new_id = cur.fetchone()[0]

Notes
-----
- Keep the client focused on connectivity, execution, and diagnostics.
- Higher-level data access (joins, domain logic) should live in repositories.

"""

from __future__ import annotations

import os
import time
import typing as t
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool
from dotenv import load_dotenv

from polymer_extractor.utils.logging import Logger

# === Load environment variables early (consistent with other storage clients) ===
# Mirrors `appwrite_client.py` approach.
# See: polymer_extractor/storage/appwrite_client.py
# (Consistent .env loading and validation)  # noqa: E501
load_dotenv()
logger = Logger()

# === Type aliases ===
Row = t.Dict[str, t.Any]
Rows = t.List[Row]


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    try:
        return int(val) if val is not None else default
    except ValueError:
        logger.warning(
            f"Invalid int for {name}='{val}', falling back to {default}",
            source="postgresql_client",
            event_type="config",
        )
        return default


def _build_dsn_from_parts() -> t.Optional[str]:
    """
    Construct a DSN from discrete environment variables if POSTGRES_DSN is not set.

    Returns
    -------
    Optional[str]
        A PostgreSQL DSN string or None if required parts are missing.
    """
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT")
    db = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")

    if all([host, port, db, user, password]):
        # Optional knobs
        app_name = os.getenv("POSTGRES_APPLICATION_NAME", "polymer-nlp-extractor")
        timeout = _env_int("POSTGRES_CONNECT_TIMEOUT", 10)
        return (
            f"postgresql://{user}:{password}@{host}:{port}/{db}"
            f"?application_name={app_name}&connect_timeout={timeout}"
        )
    return None


class PostgresClient:
    """
    PostgreSQL pooled client.

    Responsibilities
    ----------------
    - Validate configuration and create a connection pool.
    - Provide simple, safe query/execute helpers.
    - Offer a transaction context manager with automatic commit/rollback.
    - Provide health checks and structured error logging.

    Non-Responsibilities
    --------------------
    - No ORM, no schema migrations (provide helpers only).
    - No domain-level joins/logic (use repositories for that).
    """

    def __init__(
        self,
        dsn: t.Optional[str] = None,
        min_conn: t.Optional[int] = None,
        max_conn: t.Optional[int] = None,
    ) -> None:
        """
        Initialize the PostgreSQL connection pool.

        Parameters
        ----------
        dsn : Optional[str]
            PostgreSQL DSN. If None, it is resolved from environment variables.
        min_conn : Optional[int]
            Minimum connections in the pool (defaults to POSTGRES_MIN_CONN or 1).
        max_conn : Optional[int]
            Maximum connections in the pool (defaults to POSTGRES_MAX_CONN or 10).

        Raises
        ------
        EnvironmentError
            If configuration is insufficient to build a DSN.
        psycopg2.Error
            If pool initialization fails.
        """
        self._dsn = dsn or os.getenv("POSTGRES_DSN") or _build_dsn_from_parts()
        if not self._dsn:
            # Align with environment validation used in other storage clients.
            # See appwrite_client.py for similar pattern.
            raise EnvironmentError(
                "[Postgres Client ERROR] Missing PostgreSQL configuration. "
                "Provide POSTGRES_DSN or all of POSTGRES_HOST/PORT/DB/USER/PASSWORD."
            )

        self._min = min_conn or _env_int("POSTGRES_MIN_CONN", 1)
        self._max = max_conn or _env_int("POSTGRES_MAX_CONN", 10)

        # RealDictCursor returns rows as dictionaries keyed by column name
        self._cursor_factory = psycopg2.extras.RealDictCursor

        try:
            self._pool: SimpleConnectionPool = SimpleConnectionPool(
                minconn=self._min, maxconn=self._max, dsn=self._dsn
            )
            logger.info(
                "PostgreSQL pool initialized.",
                source="postgresql_client",
                event_type="startup",
                extra={"min_conn": self._min, "max_conn": self._max},
            )
        except Exception as e:
            logger.critical(
                "Failed to initialize PostgreSQL pool.",
                source="postgresql_client",
                error=e,
                event_type="startup",
            )
            raise

    # --------------------------------------------------------------------- #
    # Core helpers
    # --------------------------------------------------------------------- #
    def _get_conn(self) -> psycopg2.extensions.connection:
        return self._pool.getconn()

    def _put_conn(self, conn: psycopg2.extensions.connection) -> None:
        self._pool.putconn(conn)

    def close(self) -> None:
        """Close all connections in the pool."""
        try:
            self._pool.closeall()
            logger.info(
                "PostgreSQL pool closed.",
                source="postgresql_client",
                event_type="shutdown",
            )
        except Exception as e:
            logger.warning(
                "Error while closing PostgreSQL pool.",
                source="postgresql_client",
                error=e,
                event_type="shutdown",
            )

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
              "details": {
                  "server_version": str|None,
                  "pool": {"min": int, "max": int, "in_use": int}
              },
              "error": str|None
            }
        """
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor(self._cursor_factory) as cur:
                cur.execute("SHOW server_version;")
                ver = cur.fetchone().get("server_version")

            in_use = self._pool._used # type: ignore[attr-defined]
            payload: Row = {
                "ok": True,
                "details": {
                    "server_version": ver,
                    "pool": {"min": self._min, "max": self._max, "in_use": len(in_use)},
                },
                "error": None,
            }
            logger.debug(
                "Health check OK.",
                source="postgresql_client",
                event_type="health_check",
                extra=payload,
            )
            return payload
        except Exception as e:
            logger.error(
                "Health check failed.",
                source="postgresql_client",
                error=e,
                event_type="health_check",
            )
            return {"ok": False, "details": None, "error": str(e)}
        finally:
            if conn:
                self._put_conn(conn)

    # --------------------------------------------------------------------- #
    # Query execution
    # --------------------------------------------------------------------- #
    def run(
        self,
        sql: str,
        params: t.Optional[t.Union[t.Sequence[t.Any], t.Mapping[str, t.Any]]] = None,
        *,
        fetch: t.Literal["none", "one", "all"] = "none",
        page: t.Optional[int] = None,
        page_size: t.Optional[int] = None,
        retries: int = 1,
        retry_backoff: float = 0.25,
    ) -> t.Union[None, Row, Rows]:
        """
        Execute a single SQL statement with optional fetching and pagination.

        Parameters
        ----------
        sql : str
            The SQL statement to execute. Use %s placeholders for parameters.
        params : Optional[Sequence|Mapping]
            Positional or named parameters to bind safely.
        fetch : {'none','one','all'}, default 'none'
            Fetch mode:
            - 'none' : return None
            - 'one'  : return a single row as dict or None
            - 'all'  : return a list of dict rows (possibly empty)
        page : Optional[int]
            1-based page number for pagination (requires page_size).
        page_size : Optional[int]
            Page size for pagination (requires page).
        retries : int, default 1
            Number of transient retries on failure.
        retry_backoff : float, default 0.25
            Initial backoff (seconds), doubles each retry.

        Returns
        -------
        None | dict | list[dict]

        Raises
        ------
        psycopg2.Error
            When execution fails after all retries.
        """
        # Apply LIMIT/OFFSET if paging is requested
        if page is not None and page_size is not None:
            offset = max(0, (page - 1) * page_size)
            sql = f"{sql.strip()} LIMIT %s OFFSET %s"
            # Ensure params is a list to append limit/offset deterministically
            if params is None:
                params = [page_size, offset]
            elif isinstance(params, (list, tuple)):
                params = list(params) + [page_size, offset]
            elif isinstance(params, dict):
                # For named params, we add positional tail params
                params = list(params.values()) + [page_size, offset]
            else:
                params = [params, page_size, offset]

        attempt = 0
        while True:
            attempt += 1
            conn = None
            try:
                conn = self._get_conn()
                with conn, conn.cursor(self._cursor_factory) as cur:
                    cur.execute(sql, params)
                    if fetch == "none":
                        return None
                    if fetch == "one":
                        row = cur.fetchone()
                        return row if row is not None else None
                    if fetch == "all":
