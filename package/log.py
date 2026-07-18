"""
log.py — Structured CloudWatch logging with credential masking.

Emits single JSON log entries to stdout (captured by CloudWatch Logs).
Never logs the resolved values of DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD.
Swallows any internal logging exceptions so they never surface in API responses.
"""

import json
import os
import traceback as tb
from typing import Optional

# Environment variable names whose *values* must never appear in logs
_SENSITIVE_ENV_KEYS = {"DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"}


def _get_sensitive_values() -> set:
    """Collect the current resolved values of all sensitive env vars."""
    values = set()
    for key in _SENSITIVE_ENV_KEYS:
        val = os.environ.get(key, "")
        if val:
            values.add(val)
    return values


def _mask(text: str, sensitive_values: set) -> str:
    """Replace any sensitive value found in *text* with [REDACTED]."""
    for secret in sensitive_values:
        text = text.replace(secret, "[REDACTED]")
    return text


def log_error(
    message: str,
    exc: Optional[BaseException] = None,
    operation: Optional[str] = None,
) -> None:
    """
    Emit a structured JSON error log entry to stdout (CloudWatch).

    Parameters
    ----------
    message   : Human-readable description of what went wrong.
    exc       : The exception instance, if any.
    operation : The logical operation that failed (e.g. 'list_employees').
    """
    try:
        sensitive = _get_sensitive_values()

        entry: dict = {
            "level": "ERROR",
            "message": _mask(message, sensitive),
        }

        if operation:
            entry["operation"] = operation

        if exc is not None:
            entry["exception_type"] = type(exc).__name__
            entry["exception_message"] = _mask(str(exc), sensitive)
            entry["traceback"] = _mask(
                "".join(tb.format_exception(type(exc), exc, exc.__traceback__)),
                sensitive,
            )

        print(json.dumps(entry))

    except Exception:
        # Logging must never break the caller's control flow (Req 7.4).
        pass
