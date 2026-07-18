"""
validation.py — Input and configuration validation.

Pure functions — no I/O, no side effects.

Raises
------
ValidationError : invalid path parameter supplied by a client (→ HTTP 400)
ConfigError     : missing/invalid Lambda environment variable (→ HTTP 500)
"""

import os
from typing import NamedTuple, Optional

# ---------------------------------------------------------------------------
# Custom exception types
# ---------------------------------------------------------------------------

class ValidationError(ValueError):
    """Raised when a client-supplied value fails validation."""


class ConfigError(RuntimeError):
    """Raised when a required environment variable is missing or invalid."""


# ---------------------------------------------------------------------------
# Internal config model
# ---------------------------------------------------------------------------

class DBConfig(NamedTuple):
    host: str
    port: int       # validated: 1–65535
    dbname: str
    user: str
    password: str


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

_EMPLOYEE_ID_MAX = 999_999_999


def validate_employee_id(raw_id: Optional[str]) -> int:
    """
    Parse and validate an employee ID from a path parameter string.

    Valid: a decimal string representing a positive integer in [1, 999_999_999].

    Parameters
    ----------
    raw_id : The raw string from the URL path parameter (may be None).

    Returns
    -------
    int : The validated employee ID.

    Raises
    ------
    ValidationError : if raw_id is None, empty, non-numeric, zero, negative,
                      or greater than 999_999_999.
    """
    if not raw_id:
        raise ValidationError("Employee ID is required")

    try:
        employee_id = int(raw_id)
    except ValueError:
        raise ValidationError(f"Employee ID must be a numeric value, got: {raw_id!r}")

    if employee_id <= 0:
        raise ValidationError(f"Employee ID must be a positive integer, got: {employee_id}")

    if employee_id > _EMPLOYEE_ID_MAX:
        raise ValidationError(
            f"Employee ID must not exceed {_EMPLOYEE_ID_MAX}, got: {employee_id}"
        )

    return employee_id


_REQUIRED_DB_VARS = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")


def validate_db_config(env: Optional[dict] = None) -> DBConfig:
    """
    Read and validate all required DB credentials from environment variables.

    Parameters
    ----------
    env : Mapping of environment variable names to values.
          Defaults to os.environ when None (production path).

    Returns
    -------
    DBConfig : Validated connection parameters.

    Raises
    ------
    ConfigError : listing every missing or invalid variable name.
    """
    if env is None:
        env = os.environ

    errors = []

    # Check for missing or empty variables
    missing = [k for k in _REQUIRED_DB_VARS if not env.get(k, "").strip()]
    if missing:
        errors.append(f"Missing or empty environment variables: {', '.join(missing)}")

    if errors:
        raise ConfigError("; ".join(errors))

    # Validate DB_PORT separately so we can give a precise error
    raw_port = env["DB_PORT"].strip()
    try:
        port = int(raw_port)
        if not (1 <= port <= 65535):
            raise ValueError
    except ValueError:
        raise ConfigError(
            f"DB_PORT must be an integer between 1 and 65535, got: {raw_port!r}"
        )

    return DBConfig(
        host=env["DB_HOST"].strip(),
        port=port,
        dbname=env["DB_NAME"].strip(),
        user=env["DB_USER"].strip(),
        password=env["DB_PASSWORD"].strip(),
    )
