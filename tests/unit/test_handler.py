"""
test_handler.py — Unit tests for handler.py

All DB calls are mocked so no real PostgreSQL connection is needed.
Covers routing, method validation, happy paths, and all error paths.
"""

import json
import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

import handler


# ---------------------------------------------------------------------------
# Event factories
# ---------------------------------------------------------------------------

def _list_event(method: str = "GET") -> dict:
    return {
        "httpMethod": method,
        "resource": "/employees",
        "pathParameters": None,
    }


def _detail_event(employee_id: str = "1", method: str = "GET") -> dict:
    return {
        "httpMethod": method,
        "resource": "/employees/{id}",
        "pathParameters": {"id": employee_id},
    }


# ---------------------------------------------------------------------------
# Method validation
# ---------------------------------------------------------------------------

class TestMethodValidation:

    def test_post_to_list_returns_405(self):
        r = handler.lambda_handler(_list_event("POST"), None)
        assert r["statusCode"] == 405

    def test_put_to_detail_returns_405(self):
        r = handler.lambda_handler(_detail_event("1", "PUT"), None)
        assert r["statusCode"] == 405

    def test_delete_returns_405(self):
        r = handler.lambda_handler(_detail_event("1", "DELETE"), None)
        assert r["statusCode"] == 405

    def test_405_has_allow_header(self):
        r = handler.lambda_handler(_list_event("POST"), None)
        assert r["headers"].get("Allow") == "GET"


# ---------------------------------------------------------------------------
# GET /employees
# ---------------------------------------------------------------------------

class TestListEmployees:

    @patch("handler.db.get_connection")
    @patch("handler.db.list_employees")
    def test_happy_path_200(self, mock_list, mock_conn):
        rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        mock_list.return_value = (rows, False)
        mock_conn.return_value = MagicMock()

        r = handler.lambda_handler(_list_event(), None)

        assert r["statusCode"] == 200
        assert json.loads(r["body"]) == rows

    @patch("handler.db.get_connection")
    @patch("handler.db.list_employees")
    def test_empty_list_returns_200_empty_array(self, mock_list, mock_conn):
        mock_list.return_value = ([], False)
        mock_conn.return_value = MagicMock()

        r = handler.lambda_handler(_list_event(), None)

        assert r["statusCode"] == 200
        assert json.loads(r["body"]) == []

    @patch("handler.db.get_connection")
    @patch("handler.db.list_employees")
    def test_truncated_sets_header(self, mock_list, mock_conn):
        rows = [{"id": i, "name": f"Emp{i}"} for i in range(1, 10001)]
        mock_list.return_value = (rows, True)
        mock_conn.return_value = MagicMock()

        r = handler.lambda_handler(_list_event(), None)

        assert r["statusCode"] == 200
        assert r["headers"].get("X-Result-Truncated") == "true"

    @patch("handler.db.get_connection")
    def test_db_connection_error_returns_500(self, mock_conn):
        import psycopg2
        mock_conn.side_effect = psycopg2.OperationalError("connection refused")

        r = handler.lambda_handler(_list_event(), None)

        assert r["statusCode"] == 500

    @patch("handler.db.get_connection")
    def test_config_error_returns_500(self, mock_conn):
        from validation import ConfigError
        mock_conn.side_effect = ConfigError("DB_HOST missing")

        r = handler.lambda_handler(_list_event(), None)

        assert r["statusCode"] == 500

    @patch("handler.db.get_connection")
    @patch("handler.db.list_employees")
    def test_connection_closed_after_success(self, mock_list, mock_conn):
        mock_conn_obj = MagicMock()
        mock_conn.return_value = mock_conn_obj
        mock_list.return_value = ([], False)

        handler.lambda_handler(_list_event(), None)

        mock_conn_obj.close.assert_called_once()

    @patch("handler.db.get_connection")
    @patch("handler.db.list_employees")
    def test_connection_closed_after_db_error(self, mock_list, mock_conn):
        import psycopg2
        mock_conn_obj = MagicMock()
        mock_conn.return_value = mock_conn_obj
        mock_list.side_effect = psycopg2.DatabaseError("query failed")

        handler.lambda_handler(_list_event(), None)

        mock_conn_obj.close.assert_called_once()


# ---------------------------------------------------------------------------
# GET /employees/{id}
# ---------------------------------------------------------------------------

class TestGetEmployee:

    @patch("handler.db.get_connection")
    @patch("handler.db.get_employee")
    def test_found_returns_200(self, mock_get, mock_conn):
        record = {"id": 3, "name": "Charlie"}
        mock_get.return_value = record
        mock_conn.return_value = MagicMock()

        r = handler.lambda_handler(_detail_event("3"), None)

        assert r["statusCode"] == 200
        assert json.loads(r["body"]) == record

    @patch("handler.db.get_connection")
    @patch("handler.db.get_employee")
    def test_not_found_returns_404(self, mock_get, mock_conn):
        mock_get.return_value = None
        mock_conn.return_value = MagicMock()

        r = handler.lambda_handler(_detail_event("999"), None)

        assert r["statusCode"] == 404
        body = json.loads(r["body"])
        assert "message" in body

    def test_invalid_id_non_numeric_returns_400(self):
        r = handler.lambda_handler(_detail_event("abc"), None)
        assert r["statusCode"] == 400

    def test_invalid_id_zero_returns_400(self):
        r = handler.lambda_handler(_detail_event("0"), None)
        assert r["statusCode"] == 400

    def test_invalid_id_negative_returns_400(self):
        r = handler.lambda_handler(_detail_event("-5"), None)
        assert r["statusCode"] == 400

    def test_invalid_id_too_large_returns_400(self):
        r = handler.lambda_handler(_detail_event("1000000000"), None)
        assert r["statusCode"] == 400

    def test_missing_path_parameters_returns_400(self):
        event = {
            "httpMethod": "GET",
            "resource": "/employees/{id}",
            "pathParameters": None,
        }
        r = handler.lambda_handler(event, None)
        assert r["statusCode"] == 400

    @patch("handler.db.get_connection")
    def test_db_error_returns_500(self, mock_conn):
        import psycopg2
        mock_conn.side_effect = psycopg2.OperationalError("timeout")

        r = handler.lambda_handler(_detail_event("1"), None)

        assert r["statusCode"] == 500

    @patch("handler.db.get_connection")
    @patch("handler.db.get_employee")
    def test_connection_closed_after_success(self, mock_get, mock_conn):
        mock_conn_obj = MagicMock()
        mock_conn.return_value = mock_conn_obj
        mock_get.return_value = {"id": 1, "name": "Alice"}

        handler.lambda_handler(_detail_event("1"), None)

        mock_conn_obj.close.assert_called_once()

    @patch("handler.db.get_connection")
    @patch("handler.db.get_employee")
    def test_connection_closed_after_not_found(self, mock_get, mock_conn):
        mock_conn_obj = MagicMock()
        mock_conn.return_value = mock_conn_obj
        mock_get.return_value = None

        handler.lambda_handler(_detail_event("999"), None)

        mock_conn_obj.close.assert_called_once()


# ---------------------------------------------------------------------------
# Response contract — all paths must return valid proxy integration shape
# ---------------------------------------------------------------------------

class TestResponseContract:

    def _assert_contract(self, r: dict):
        assert "statusCode" in r
        assert "headers" in r
        assert "body" in r
        assert r["headers"].get("Content-Type") == "application/json"
        json.loads(r["body"])  # must be valid JSON

    @patch("handler.db.get_connection")
    @patch("handler.db.list_employees")
    def test_list_success_contract(self, mock_list, mock_conn):
        mock_list.return_value = ([], False)
        mock_conn.return_value = MagicMock()
        self._assert_contract(handler.lambda_handler(_list_event(), None))

    def test_400_contract(self):
        self._assert_contract(handler.lambda_handler(_detail_event("bad"), None))

    @patch("handler.db.get_connection")
    @patch("handler.db.get_employee")
    def test_404_contract(self, mock_get, mock_conn):
        mock_get.return_value = None
        mock_conn.return_value = MagicMock()
        self._assert_contract(handler.lambda_handler(_detail_event("9999"), None))

    def test_405_contract(self):
        self._assert_contract(handler.lambda_handler(_list_event("DELETE"), None))

    @patch("handler.db.get_connection")
    def test_500_contract(self, mock_conn):
        import psycopg2
        mock_conn.side_effect = psycopg2.OperationalError("fail")
        self._assert_contract(handler.lambda_handler(_list_event(), None))
