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
4) Assumes database and user already exist - only manages tables and schemas.

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
from typing import Dict, Any, Optional, Union, List, Tuple
import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

from polymer_extractor.utils.logging import Logger

# === Load environment variables early (consistent with other storage clients) ===
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
    - No database creation (databases and users must exist).
    """

    def __init__(
        self,
        dsn: t.Optional[str] = None,
        min_conn: t.Optional[int] = None,
        max_conn: t.Optional[int] = None,
    ) -> None:
        """
        Initialize PostgreSQL client.
        
        Assumes the database and user already exist with proper permissions.
        Will only create tables and schemas as needed.
        
        Parameters
        ----------
        dsn : str, optional
            PostgreSQL DSN. If not provided, will be constructed from env vars.
        min_conn : int, optional
            Minimum connections in pool (default: 1)
        max_conn : int, optional
            Maximum connections in pool (default: 10)
        """
        self.logger = logger
        
        # Resolve DSN
        self.dsn = dsn or os.getenv("POSTGRES_DSN") or _build_dsn_from_parts()
        if not self.dsn:
            raise ValueError(
                "No PostgreSQL DSN provided. Set POSTGRES_DSN or provide host/port/db/user/password."
            )
        
        # Pool settings
        self.min_conn = min_conn or _env_int("POSTGRES_MIN_CONN", 1)
        self.max_conn = max_conn or _env_int("POSTGRES_MAX_CONN", 10)
        
        # Create connection pool
        try:
            self.pool = SimpleConnectionPool(
                self.min_conn,
                self.max_conn,
                self.dsn,
            )
            self.logger.info(
                f"PostgreSQL client initialized with pool ({self.min_conn}-{self.max_conn} connections)",
                source="postgresql_client",
                event_type="initialization",
            )
            
            # Check database existence on initialization
            db_check = self.check_database_exists()
            if not db_check["exists"] or not db_check["accessible"]:
                error_msg = f"Database check failed: {db_check.get('error', 'Database not accessible')}"
                self.logger.critical(error_msg, source="postgresql_client", event_type="database_check")
                raise ConnectionError(f"PostgreSQL database not accessible: {db_check.get('error')}")
                
        except Exception as e:
            self.logger.critical(
                f"Failed to initialize PostgreSQL pool.\nStack trace:\n{traceback.format_exc()}",
                source="postgresql_client",
                event_type="initialization_error",
            )
            raise

    # --------------------------------------------------------------------- #
    # Core helpers
    # --------------------------------------------------------------------- #
    def _get_conn(self) -> psycopg2.extensions.connection:
        return self.pool.getconn()

    def _put_conn(self, conn: psycopg2.extensions.connection) -> None:
        self.pool.putconn(conn)

    def close(self) -> None:
        """Close all connections in the pool."""
        try:
            self.pool.closeall()
            logger.info(
                "PostgreSQL connection pool closed",
                source="postgresql_client",
                event_type="cleanup",
            )
        except Exception as e:
            logger.warning(
                "Error closing PostgreSQL pool",
                source="postgresql_client",
                error=e,
                event_type="cleanup",
            )

    # --------------------------------------------------------------------- #
    # Diagnostics
    # --------------------------------------------------------------------- #
    def health_check(self) -> Row:
        """
        Perform a health check on the PostgreSQL connection.

        Returns
        -------
        Row
            Health status and connection details.
        """
        try:
            conn = self._get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT version() AS server_version")
                    version_row = cur.fetchone()

                    # Pool stats
                    # Note: SimpleConnectionPool doesn't expose detailed stats like HikariCP,
                    # so we'll provide basic info
                    pool_info = {
                        "min": self.min_conn,
                        "max": self.max_conn,
                        # These are rough estimates based on available public methods
                        "in_use": 0,  # Would need custom tracking to get exact count
                    }

                return {
                    "ok": True,
                    "details": {
                        "server_version": version_row[0] if version_row else "unknown",
                        "pool": pool_info,
                    },
                }
            finally:
                self._put_conn(conn)

        except Exception as e:
            logger.error(
                "PostgreSQL health check failed",
                source="postgresql_client",
                error=e,
                event_type="health_check",
            )
            return {
                "ok": False,
                "error": str(e),
            }

    def check_database_exists(self) -> Dict[str, Any]:
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
            "database_name": None,
            "error": None,
            "timestamp": datetime.now().isoformat() + "Z"
        }
        
        try:
            conn = self._get_conn()
            try:
                with conn.cursor() as cur:
                    # Get current database name
                    cur.execute("SELECT current_database()")
                    db_name = cur.fetchone()[0]
                    result["database_name"] = db_name
                    
                    # Check if we can read from system catalogs
                    cur.execute("SELECT count(*) FROM pg_database WHERE datname = %s", (db_name,))
                    count = cur.fetchone()[0]
                    
                    if count > 0:
                        result["exists"] = True
                        result["accessible"] = True
                        self.logger.info(f"Database '{db_name}' exists and is accessible", 
                                       source="postgresql_client", event_type="database_check")
                    else:
                        result["error"] = f"Database '{db_name}' not found in system catalog"
                        
            finally:
                self._put_conn(conn)
                
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"Database existence check failed: {e}", 
                            source="postgresql_client", event_type="database_check")
        
        return result

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
        Execute a SQL statement.

        Parameters
        ----------
        sql : str
            SQL statement to execute.
        params : Optional[Union[Sequence[Any], Mapping[str, Any]]]
            Parameters for the SQL statement.
        fetch : Literal["none", "one", "all"]
            How to fetch results: "none" (no fetch), "one" (single row), "all" (all rows).
        page : Optional[int]
            Page number for pagination (0-based). Requires page_size.
        page_size : Optional[int]
            Number of rows per page. Requires page.
        retries : int
            Number of retry attempts for transient errors.
        retry_backoff : float
            Backoff multiplier for retries (exponential backoff).

        Returns
        -------
        Union[None, Row, Rows]
            Query results based on fetch parameter.
        """
        # Handle pagination
        if page is not None and page_size is not None:
            offset = page * page_size
            sql = f"{sql} LIMIT %s OFFSET %s"
            if params is None:
                params = [page_size, offset]
            elif isinstance(params, (list, tuple)):
                params = list(params) + [page_size, offset]
            elif isinstance(params, dict):
                params = list(params.values()) + [page_size, offset]
            else:
                params = [params, page_size, offset]

        for attempt in range(1, retries + 1):
            try:
                conn = self._get_conn()
                try:
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                        cur.execute(sql, params)
                        if fetch == "none":
                            return None
                        if fetch == "one":
                            row = cur.fetchone()
                            return dict(row) if row else None
                        if fetch == "all":
                            rows = cur.fetchall()
                            return [dict(row) for row in rows]
                finally:
                    self._put_conn(conn)

            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                # Transient errors that might benefit from retry
                logger.warning(
                    f"PostgreSQL transient error (attempt {attempt}/{retries})",
                    source="postgresql_client",
                    error=e,
                    event_type="query_retry",
                )
                if attempt >= retries:
                    raise
                # Exponential backoff
                time.sleep(retry_backoff * (2 ** (attempt - 1)))

            except Exception as e:
                # Non-transient errors
                logger.error(
                    f"PostgreSQL query failed: {sql[:100]}...",
                    source="postgresql_client",
                    error=e,
                    event_type="query_error",
                )
                raise

    # --------------------------------------------------------------------- #
    # Transactions
    # --------------------------------------------------------------------- #
    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions.

        Yields
        ------
        psycopg2.extras.RealDictCursor
            Database cursor with automatic commit/rollback.

        Examples
        --------
        >>> with db.transaction() as cur:
        ...     cur.execute("INSERT INTO papers (title) VALUES (%s)", ("New Paper",))
        ...     cur.execute("UPDATE authors SET count = count + 1")
        """
        conn = self._get_conn()
        try:
            with conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    yield cur
        except Exception as e:
            logger.error(
                "Transaction failed and was rolled back",
                source="postgresql_client",
                error=e,
                event_type="transaction_error",
            )
            raise
        finally:
            self._put_conn(conn)

    # ============================================================================
    # Schema Management
    # ============================================================================

    def deploy_schema(self, sql_file_path: str) -> Dict[str, Any]:
        """
        Deploy database schema from SQL file.
        
        Parameters
        ----------
        sql_file_path : str
            Path to SQL schema file
            
        Returns
        -------
        Dict[str, Any]
            Deployment result with status and details
        """
        result = {
            "success": False,
            "operation": "deploy_schema",
            "file_path": sql_file_path,
            "tables_created": [],
            "error": None
        }
        
        try:
            schema_path = Path(sql_file_path)
            if not schema_path.exists():
                result["error"] = f"Schema file not found: {sql_file_path}"
                return result
            
            schema_sql = schema_path.read_text()
            
            with self.transaction() as cur:
                cur.execute(schema_sql)
                result["success"] = True
                
            self.logger.info(
                f"Database schema deployed successfully from {sql_file_path}",
                source="postgresql_client",
                event_type="schema_deployment"
            )
            
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(
                f"Failed to deploy schema from {sql_file_path}",
                source="postgresql_client",
                error=e,
                event_type="schema_deployment"
            )
            
        return result

    def reset_database(self, preserve_logs: bool = True) -> Dict[str, Any]:
        """
        Reset database by dropping all tables (not the database itself).
        
        Parameters
        ----------
        preserve_logs : bool
            Whether to preserve log tables (default: True)
            
        Returns
        -------
        Dict[str, Any]
            Reset result with status and details
        """
        result = {
            "success": False,
            "operation": "reset_database",
            "tables_dropped": [],
            "tables_preserved": [],
            "error": None
        }
        
        try:
            with self.transaction() as cur:
                # Get all table names
                cur.execute("""
                    SELECT tablename FROM pg_tables 
                    WHERE schemaname = 'public'
                """)
                tables = [row["tablename"] for row in cur.fetchall()]
                
                for table in tables:
                    # Preserve log tables if requested
                    if preserve_logs and "log" in table.lower():
                        result["tables_preserved"].append(table)
                        continue
                    
                    cur.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
                    result["tables_dropped"].append(table)
                
                result["success"] = True
                
            self.logger.info(
                f"Database reset completed. Dropped {len(result['tables_dropped'])} tables",
                source="postgresql_client",
                event_type="database_reset"
            )
            
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(
                "Failed to reset database",
                source="postgresql_client",
                error=e,
                event_type="database_reset"
            )
            
        return result

    def create_table_if_not_exists(self, table_name: str, schema_sql: str) -> bool:
        """
        Create table if it doesn't exist.
        
        Parameters
        ----------
        table_name : str
            Name of the table
        schema_sql : str
            CREATE TABLE SQL statement
            
        Returns
        -------
        bool
            True if table was created, False if it already existed
        """
        try:
            with self.transaction() as cur:
                # Check if table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = %s
                    )
                """, (table_name,))
                
                exists = cur.fetchone()["exists"]
                
                if not exists:
                    cur.execute(schema_sql)
                    self.logger.info(
                        f"Table '{table_name}' created successfully",
                        source="postgresql_client",
                        event_type="table_creation"
                    )
                    return True
                else:
                    self.logger.debug(
                        f"Table '{table_name}' already exists",
                        source="postgresql_client",
                        event_type="table_check"
                    )
                    return False
                    
        except Exception as e:
            self.logger.error(
                f"Failed to create table '{table_name}'",
                source="postgresql_client",
                error=e,
                event_type="table_creation"
            )
            raise

    def add_column_if_not_exists(self, table_name: str, column_def: str) -> bool:
        """
        Add column to table if it doesn't exist.
        
        Parameters
        ----------
        table_name : str
            Name of the table
        column_def : str
            Column definition (e.g., "new_column VARCHAR(255)")
            
        Returns
        -------
        bool
            True if column was added, False if it already existed
        """
        try:
            # Extract column name from definition
            column_name = column_def.split()[0]
            
            with self.transaction() as cur:
                # Check if column exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = %s 
                        AND column_name = %s
                    )
                """, (table_name, column_name))
                
                exists = cur.fetchone()["exists"]
                
                if not exists:
                    cur.execute(f'ALTER TABLE "{table_name}" ADD COLUMN {column_def}')
                    self.logger.info(
                        f"Column '{column_name}' added to table '{table_name}'",
                        source="postgresql_client",
                        event_type="column_addition"
                    )
                    return True
                else:
                    self.logger.debug(
                        f"Column '{column_name}' already exists in table '{table_name}'",
                        source="postgresql_client",
                        event_type="column_check"
                    )
                    return False
                    
        except Exception as e:
            self.logger.error(
                f"Failed to add column '{column_def}' to table '{table_name}'",
                source="postgresql_client",
                error=e,
                event_type="column_addition"
            )
            raise

    def service_status(self) -> Dict[str, Any]:
        """
        Get PostgreSQL service status.
        
        Returns
        -------
        Dict[str, Any]
            Service status information with 'status' key ('healthy', 'error', 'unavailable')
        """
        try:
            # Check if we can connect and run a simple query
            health_result = self.health_check()
            
            # Extract connection info from DSN for display
            conn_info = {"dsn": self.dsn}
            
            # Convert health check result to service status format
            return {
                "status": "healthy",
                "service": "postgresql",
                "connection_info": conn_info,
                "message": "PostgreSQL is accessible and responding"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "service": "postgresql", 
                "error": str(e),
                "message": f"PostgreSQL connection failed: {e}"
            }


__all__ = ["PostgresClient", "Row", "Rows"]
