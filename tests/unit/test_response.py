"""
test_response.py — Unit tests for response.py

Verifies that every builder function:
  - Returns statusCode, headers, body
  - Sets Content-Type: application/json
  - Returns a non-empty, valid-JSON body
  - Uses the correct HTTP status code
  - Handles list truncation header correctly
"""

import json
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

import response as resp


def _parse_body(r: dict):
    """Helper — deserialise the body string and return the Python object."""
    return json.loads(r["body"])


def _assert_base_contract(r: dict):
    """Every response must satisfy the Lambda Proxy Integration contract."""
    assert "statusCode" in r
    assert "headers" in r
    assert "body" in r
    assert isinstance(r["statusCode"], int)
    assert isinstance(r["headers"], dict)
    assert isinstance(r["body"], str)
    assert len(r["body"]) > 0
    assert r["headers"].get("Content-Type") == "application/json"
    # body must be valid JSON
    json.loads(r["body"])


# ---------------------------------------------------------------------------
# success()
# ---------------------------------------------------------------------------

class TestSuccess:

    def test_status_200(self):
        r = resp.success({"id": 1, "name": "Alice"})
        assert r["statusCode"] == 200

    def test_body_equals_record(self):
        record = {"id": 7, "name": "Bob"}
        r = resp.success(record)
        assert _parse_body(r) == record

    def test_contract(self):
        _assert_base_contract(resp.success({"id": 1, "name": "X"}))


# ---------------------------------------------------------------------------
# success_list()
# ---------------------------------------------------------------------------

class TestSuccessList:

    def test_status_200(self):
        r = resp.success_list([])
        assert r["statusCode"] == 200

    def test_empty_list(self):
        r = resp.success_list([])
        assert _parse_body(r) == []

    def test_rows_preserved(self):
        rows = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
        r = resp.success_list(rows)
        assert _parse_body(r) == rows

    def test_no_truncation_header_by_default(self):
        r = resp.success_list([{"id": 1, "name": "A"}])
        assert "X-Result-Truncated" not in r["headers"]

    def test_truncation_header_present_when_true(self):
        r = resp.success_list([{"id": 1, "name": "A"}], truncated=True)
        assert r["headers"].get("X-Result-Truncated") == "true"

    def test_no_truncation_header_when_false(self):
        r = resp.success_list([{"id": 1, "name": "A"}], truncated=False)
        assert "X-Result-Truncated" not in r["headers"]

    def test_contract(self):
        _assert_base_contract(resp.success_list([{"id": 1, "name": "Z"}]))


# ---------------------------------------------------------------------------
# not_found()
# ---------------------------------------------------------------------------

class TestNotFound:

    def test_status_404(self):
        assert resp.not_found()["statusCode"] == 404

    def test_body_has_message(self):
        body = _parse_body(resp.not_found())
        assert "message" in body
        assert len(body["message"]) > 0

    def test_message_content(self):
        body = _parse_body(resp.not_found())
        assert "not found" in body["message"].lower()

    def test_contract(self):
        _assert_base_contract(resp.not_found())


# ---------------------------------------------------------------------------
# bad_request()
# ---------------------------------------------------------------------------

class TestBadRequest:

    def test_status_400(self):
        assert resp.bad_request("bad id")["statusCode"] == 400

    def test_body_has_message(self):
        body = _parse_body(resp.bad_request("oops"))
        assert "message" in body

    def test_detail_in_body(self):
        body = _parse_body(resp.bad_request("custom detail"))
        assert "custom detail" in body["message"]

    def test_contract(self):
        _assert_base_contract(resp.bad_request("x"))


# ---------------------------------------------------------------------------
# method_not_allowed()
# ---------------------------------------------------------------------------

class TestMethodNotAllowed:

    def test_status_405(self):
        assert resp.method_not_allowed()["statusCode"] == 405

    def test_allow_header_default(self):
        r = resp.method_not_allowed()
        assert r["headers"].get("Allow") == "GET"

    def test_allow_header_custom(self):
        r = resp.method_not_allowed(allowed="GET, HEAD")
        assert r["headers"].get("Allow") == "GET, HEAD"

    def test_body_has_message(self):
        body = _parse_body(resp.method_not_allowed())
        assert "message" in body

    def test_contract(self):
        _assert_base_contract(resp.method_not_allowed())


# ---------------------------------------------------------------------------
# internal_error()
# ---------------------------------------------------------------------------

class TestInternalError:

    def test_status_500(self):
        assert resp.internal_error()["statusCode"] == 500

    def test_body_has_message(self):
        body = _parse_body(resp.internal_error())
        assert "message" in body
        assert len(body["message"]) > 0

    def test_body_does_not_expose_internals(self):
        # The generic message must not contain stack-trace keywords
        body_str = resp.internal_error()["body"]
        for forbidden in ("Traceback", "Exception", "Error", "psycopg2"):
            assert forbidden not in body_str

    def test_contract(self):
        _assert_base_contract(resp.internal_error())
