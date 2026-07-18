"""
handler.py — AWS Lambda entry point for the Employee Lookup API.

Routing table
-------------
GET /employees        → list_employees()
GET /employees/{id}   → get_employee_by_id()
<any other method>    → 405 Method Not Allowed

API Gateway Lambda Proxy Integration contract (Req 6.2 / 6.3):
  Input  : event dict with keys httpMethod, resource, pathParameters, …
  Output : {"statusCode": int, "headers": dict, "body": str}
"""

import psycopg2

import db
import response as resp
from log import log_error
from validation import ConfigError, ValidationError, validate_employee_id

# ---------------------------------------------------------------------------
# Route constants — must match the API Gateway resource paths exactly
# ---------------------------------------------------------------------------
_ROUTE_LIST = "/employees"
_ROUTE_DETAIL = "/employees/{id}"


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

def _handle_list_employees() -> dict:
    """Handle GET /employees — returns all employees (capped at 10 000)."""
    conn = None
    try:
        conn = db.get_connection()
        rows, truncated = db.list_employees(conn)
        return resp.success_list(rows, truncated=truncated)

    except (psycopg2.OperationalError, psycopg2.DatabaseError) as exc:
        log_error("Database error during list_employees", exc=exc, operation="list_employees")
        return resp.internal_error()

    except ConfigError as exc:
        log_error("Configuration error during list_employees", exc=exc, operation="list_employees")
        return resp.internal_error()

    except Exception as exc:
        log_error("Unexpected error during list_employees", exc=exc, operation="list_employees")
        return resp.internal_error()

    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _handle_get_employee(path_parameters: dict) -> dict:
    """Handle GET /employees/{id} — returns a single employee or 404."""
    # Validate the path parameter before touching the DB (Req 2.5)
    raw_id = (path_parameters or {}).get("id")
    try:
        employee_id = validate_employee_id(raw_id)
    except ValidationError as exc:
        return resp.bad_request(str(exc))

    conn = None
    try:
        conn = db.get_connection()
        employee = db.get_employee(conn, employee_id)

        if employee is None:
            return resp.not_found()

        return resp.success(employee)

    except (psycopg2.OperationalError, psycopg2.DatabaseError) as exc:
        log_error("Database error during get_employee", exc=exc, operation="get_employee")
        return resp.internal_error()

    except ConfigError as exc:
        log_error("Configuration error during get_employee", exc=exc, operation="get_employee")
        return resp.internal_error()

    except Exception as exc:
        log_error("Unexpected error during get_employee", exc=exc, operation="get_employee")
        return resp.internal_error()

    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------

def lambda_handler(event: dict, context: object) -> dict:
    """
    Main Lambda handler — satisfies the API Gateway Lambda Proxy Integration
    contract.

    Parameters
    ----------
    event   : API Gateway proxy event dict.
    context : Lambda context object (unused).

    Returns
    -------
    dict with keys statusCode (int), headers (dict), body (str).
    """
    try:
        http_method = event.get("httpMethod", "").upper()
        resource = event.get("resource", "")
        path_parameters = event.get("pathParameters") or {}

        # Enforce GET-only on all defined routes (Req 5.7)
        if http_method != "GET":
            return resp.method_not_allowed(allowed="GET")

        if resource == _ROUTE_LIST:
            return _handle_list_employees()

        if resource == _ROUTE_DETAIL:
            return _handle_get_employee(path_parameters)

        # Fallback — should not be reached when API Gateway is configured
        # correctly, but guards against misconfiguration.
        return resp.internal_error()

    except Exception as exc:
        # Outermost catch-all: log and return 500 (Req 7.1)
        log_error("Unhandled exception in lambda_handler", exc=exc, operation="lambda_handler")
        return resp.internal_error()
