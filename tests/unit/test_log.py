"""
test_log.py — Unit tests for log.py

Covers:
  - Structured JSON output with required fields
  - Credential masking for all sensitive env vars
  - Graceful handling when logging itself raises
"""

import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

import log


def _capture_log(capsys, message, exc=None, operation=None, env_overrides=None):
    """Helper — calls log_error with optional env var overrides, captures stdout."""
    original = {}
    try:
        if env_overrides:
            for k, v in env_overrides.items():
                original[k] = os.environ.get(k)
                os.environ[k] = v
        log.log_error(message, exc=exc, operation=operation)
        captured = capsys.readouterr()
        return json.loads(captured.out.strip())
    finally:
        for k, v in original.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class TestLogError:

    def test_emits_json(self, capsys):
        log.log_error("something broke")
        out = capsys.readouterr().out.strip()
        data = json.loads(out)  # must not raise
        assert isinstance(data, dict)

    def test_level_is_error(self, capsys):
        entry = _capture_log(capsys, "oops")
        assert entry["level"] == "ERROR"

    def test_message_present(self, capsys):
        entry = _capture_log(capsys, "test message")
        assert entry["message"] == "test message"

    def test_operation_present_when_supplied(self, capsys):
        entry = _capture_log(capsys, "fail", operation="list_employees")
        assert entry["operation"] == "list_employees"

    def test_operation_absent_when_not_supplied(self, capsys):
        entry = _capture_log(capsys, "fail")
        assert "operation" not in entry

    def test_exception_fields_present(self, capsys):
        try:
            raise ValueError("bad value")
        except ValueError as e:
            entry = _capture_log(capsys, "caught", exc=e)

        assert "exception_type" in entry
        assert "exception_message" in entry
        assert "traceback" in entry

    def test_exception_type_name(self, capsys):
        try:
            raise RuntimeError("boom")
        except RuntimeError as e:
            entry = _capture_log(capsys, "err", exc=e)

        assert entry["exception_type"] == "RuntimeError"

    def test_no_exception_fields_when_none(self, capsys):
        entry = _capture_log(capsys, "info only")
        assert "exception_type" not in entry
        assert "exception_message" not in entry
        assert "traceback" not in entry


class TestCredentialMasking:

    _SENSITIVE_KEYS = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]

    def test_db_host_masked_in_message(self, capsys):
        env = {"DB_HOST": "super-secret-host.rds.amazonaws.com"}
        entry = _capture_log(capsys, "host is super-secret-host.rds.amazonaws.com", env_overrides=env)
        assert "super-secret-host.rds.amazonaws.com" not in entry["message"]
        assert "[REDACTED]" in entry["message"]

    def test_db_password_masked_in_exception_message(self, capsys):
        secret = "p@ssw0rd123"
        env = {"DB_PASSWORD": secret}
        try:
            raise Exception(f"auth failed for password {secret}")
        except Exception as e:
            entry = _capture_log(capsys, "db error", exc=e, env_overrides=env)

        assert secret not in entry.get("exception_message", "")

    def test_db_user_masked_in_traceback(self, capsys):
        username = "db_admin_user"
        env = {"DB_USER": username}
        try:
            raise Exception(f"user {username} not found")
        except Exception as e:
            entry = _capture_log(capsys, "auth error", exc=e, env_overrides=env)

        tb_text = entry.get("traceback", "")
        assert username not in tb_text

    def test_non_sensitive_value_not_masked(self, capsys):
        entry = _capture_log(capsys, "ordinary message with no secrets")
        assert "ordinary message with no secrets" in entry["message"]

    def test_all_sensitive_keys_masked(self, capsys):
        """Each sensitive value, when present in the message, is replaced."""
        secrets = {
            "DB_HOST": "myhost",
            "DB_PORT": "9999",
            "DB_NAME": "mydb",
            "DB_USER": "myuser",
            "DB_PASSWORD": "mypassword",
        }
        message = " ".join(secrets.values())
        entry = _capture_log(capsys, message, env_overrides=secrets)
        for secret_value in secrets.values():
            assert secret_value not in entry["message"]


class TestLoggingFailureSilenced:

    def test_internal_error_does_not_propagate(self, monkeypatch):
        """If json.dumps raises, log_error must not raise (Req 7.4)."""
        import log as log_module

        original_dumps = json.dumps

        def broken_dumps(*args, **kwargs):
            raise RuntimeError("json broken")

        monkeypatch.setattr("log.json.dumps", broken_dumps)

        # Must not raise
        log_module.log_error("test", operation="test_op")
