"""
db.py — Database connectivity and query execution.

Responsibilities:
  - Read and validate DB credentials via validation.validate_db_config()
  - Open a psycopg2 connection with a 5-second connect timeout
  - Retry connection up to 3 times with a 1-second interval (Req 3.5)
  - Enforce a 5-second statement timeout on every query (Req 2.7)
  - Execute parameterized SELECT queries only — never string interpolation
  - Return plain Python dicts so the caller has no psycopg2 dependency
"""

import time
from typing import Optional

import psycopg2
import psycopg2.extras

from log import log_error
from validation import DBConfig, validate_db_config

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3
_RETRY_INTERVAL_SECONDS = 1

# Enforced at the PostgreSQL server level; raises QueryCanceledError on breach.
_STATEMENT_TIMEOUT_MS = 5000

# Cap returned by GET /employees (Req 1.3, 1.6).
_LIST_HARD_CAP = 10_000


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def get_connection(config: Optional[DBConfig] = None) -> psycopg2.extensions.connection:
    """
    Open a psycopg2 connection using *config* (or os.environ when None).

    Retries up to _MAX_RETRIES times with _RETRY_INTERVAL_SECONDS between
    attempts. Raises psycopg2.OperationalError after all attempts are
    exhausted (caller is responsible for logging and converting to HTTP 500).

    Parameters
    ----------
    config : Pre-validated DBConfig. When None, validate_db_config() reads
             the credentials from os.environ.

    Returns
    -------
    psycopg2.extensions.connection : Open database connection.
    """
    if config is None:
        config = validate_db_config()  # raises ConfigError if env vars missing/invalid

    last_exc: Optional[Exception] = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            conn = psycopg2.connect(
                host=config.host,
                port=config.port,
                dbname=config.dbname,
                user=config.user,
                password=config.password,
                connect_timeout=5,
                # Enforce statement-level timeout so long-running queries are
                # cancelled by the DB server after _STATEMENT_TIMEOUT_MS ms.
                options=f"-c statement_timeout={_STATEMENT_TIMEOUT_MS}",
            )
            return conn
        except psycopg2.OperationalError as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_INTERVAL_SECONDS)

    # All retries exhausted — log and re-raise so the handler can return 500.
    log_error(
        f"DB connection failed after {_MAX_RETRIES} attempts",
        exc=last_exc,
        operation="get_connection",
    )
    raise last_exc


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------

def list_employees(conn: psycopg2.extensions.connection) -> tuple[list, bool]:
    """
    Fetch up to _LIST_HARD_CAP employees from the database.

    Uses LIMIT _LIST_HARD_CAP + 1 so we can detect truncation without a
    separate COUNT query (Req 1.6).

    Parameters
    ----------
    conn : Open psycopg2 connection.

    Returns
    -------
    (rows, truncated) where
      rows      : list of {"id": int, "name": str} dicts (≤ _LIST_HARD_CAP)
      truncated : True when the table contains more than _LIST_HARD_CAP rows
    """
    # Parameterized query — no user-supplied values, but uses the pattern
    # consistently (Req 4.1 / 4.2).
    sql = "SELECT id, name FROM employee ORDER BY id LIMIT %s"

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (_LIST_HARD_CAP + 1,))
        raw_rows = cur.fetchall()

    truncated = len(raw_rows) > _LIST_HARD_CAP
    rows = [{"id": row["id"], "name": row["name"]} for row in raw_rows[:_LIST_HARD_CAP]]
    return rows, truncated


def get_employee(conn: psycopg2.extensions.connection, employee_id: int) -> Optional[dict]:
    """
    Fetch a single employee by primary key.

    Parameters
    ----------
    conn        : Open psycopg2 connection.
    employee_id : Validated positive integer employee ID.

    Returns
    -------
    {"id": int, "name": str} if found, None otherwise.
    """
    # Parameterized query — employee_id is passed as a bound parameter (Req 4.2 / 4.3).
    sql = "SELECT id, name FROM employee WHERE id = %s"

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (employee_id,))
        row = cur.fetchone()

    if row is None:
        return None
    return {"id": row["id"], "name": row["name"]}
