"""
response.py — Response builder for API Gateway Lambda Proxy Integration.

Every function returns a dict with the three required fields:
  statusCode : int
  headers    : dict  (always includes Content-Type: application/json)
  body       : str   (non-empty, valid JSON)

No function ever leaks exception details into the response body.
"""

import json
from typing import Union

_JSON_HEADERS = {"Content-Type": "application/json"}


def _build(status_code: int, body: Union[dict, list], extra_headers: dict = None) -> dict:
    """Internal helper — serialises body and assembles the proxy response."""
    headers = dict(_JSON_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(body),
    }


# ---------------------------------------------------------------------------
# Success responses
# ---------------------------------------------------------------------------

def success(record: dict) -> dict:
    """HTTP 200 — single employee record."""
    return _build(200, record)


def success_list(rows: list, truncated: bool = False) -> dict:
    """
    HTTP 200 — list of employee records.

    If *truncated* is True an X-Result-Truncated: true header is added to
    signal that the result set was capped at 10 000 records (Req 1.6).
    """
    extra = {"X-Result-Truncated": "true"} if truncated else None
    return _build(200, rows, extra_headers=extra)


# ---------------------------------------------------------------------------
# Client-error responses
# ---------------------------------------------------------------------------

def not_found() -> dict:
    """HTTP 404 — employee not found (Req 2.4)."""
    return _build(404, {"message": "Employee not found"})


def bad_request(detail: str = "Invalid request") -> dict:
    """HTTP 400 — invalid path parameter (Req 2.5, 5.4)."""
    return _build(400, {"message": detail})


def method_not_allowed(allowed: str = "GET") -> dict:
    """HTTP 405 — HTTP method other than GET used on a defined path (Req 5.7)."""
    return _build(405, {"message": "Method not allowed"}, extra_headers={"Allow": allowed})


# ---------------------------------------------------------------------------
# Server-error responses
# ---------------------------------------------------------------------------

def internal_error() -> dict:
    """
    HTTP 500 — generic server/infrastructure error (Req 5.5).

    Deliberately vague — never exposes exception details.
    """
    return _build(500, {"message": "Internal server error"})
