"""
test_validation.py — Unit tests for validation.py

Covers:
  - validate_employee_id: valid values, all invalid edge cases
  - validate_db_config: all-present success, missing vars, invalid DB_PORT
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from validation import (
    ConfigError,
    ValidationError,
    validate_db_config,
    validate_employee_id,
)

# ---------------------------------------------------------------------------
# validate_employee_id
# ---------------------------------------------------------------------------

class TestValidateEmployeeId:

    def test_valid_id_returns_integer(self):
        assert validate_employee_id("1") == 1

    def test_valid_large_id(self):
        assert validate_employee_id("999999999") == 999_999_999

    def test_valid_mid_range(self):
        assert validate_employee_id("42") == 42

    def test_none_raises(self):
        with pytest.raises(ValidationError):
            validate_employee_id(None)

    def test_empty_string_raises(self):
        with pytest.raises(ValidationError):
            validate_employee_id("")

    def test_non_numeric_raises(self):
        with pytest.raises(ValidationError):
            validate_employee_id("abc")

    def test_float_string_raises(self):
        with pytest.raises(ValidationError):
            validate_employee_id("1.5")

    def test_zero_raises(self):
        with pytest.raises(ValidationError):
            validate_employee_id("0")

    def test_negative_raises(self):
        with pytest.raises(ValidationError):
            validate_employee_id("-1")

    def test_exceeds_max_raises(self):
        with pytest.raises(ValidationError):
            validate_employee_id("1000000000")

    def test_sql_injection_string_raises(self):
        with pytest.raises(ValidationError):
            validate_employee_id("1 OR 1=1")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValidationError):
            validate_employee_id("   ")


# ---------------------------------------------------------------------------
# validate_db_config
# ---------------------------------------------------------------------------

_VALID_ENV = {
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_NAME": "employees",
    "DB_USER": "admin",
    "DB_PASSWORD": "secret",
}


class TestValidateDbConfig:

    def test_all_valid_returns_db_config(self):
        cfg = validate_db_config(_VALID_ENV)
        assert cfg.host == "localhost"
        assert cfg.port == 5432
        assert cfg.dbname == "employees"
        assert cfg.user == "admin"
        assert cfg.password == "secret"

    def test_port_is_integer(self):
        cfg = validate_db_config(_VALID_ENV)
        assert isinstance(cfg.port, int)

    def test_missing_single_var_raises(self):
        env = {**_VALID_ENV}
        del env["DB_HOST"]
        with pytest.raises(ConfigError):
            validate_db_config(env)

    def test_missing_multiple_vars_raises(self):
        env = {**_VALID_ENV}
        del env["DB_HOST"]
        del env["DB_PASSWORD"]
        with pytest.raises(ConfigError):
            validate_db_config(env)

    def test_empty_var_raises(self):
        env = {**_VALID_ENV, "DB_NAME": ""}
        with pytest.raises(ConfigError):
            validate_db_config(env)

    def test_whitespace_var_raises(self):
        env = {**_VALID_ENV, "DB_USER": "   "}
        with pytest.raises(ConfigError):
            validate_db_config(env)

    def test_port_zero_raises(self):
        env = {**_VALID_ENV, "DB_PORT": "0"}
        with pytest.raises(ConfigError):
            validate_db_config(env)

    def test_port_too_high_raises(self):
        env = {**_VALID_ENV, "DB_PORT": "65536"}
        with pytest.raises(ConfigError):
            validate_db_config(env)

    def test_port_non_numeric_raises(self):
        env = {**_VALID_ENV, "DB_PORT": "abc"}
        with pytest.raises(ConfigError):
            validate_db_config(env)

    def test_port_negative_raises(self):
        env = {**_VALID_ENV, "DB_PORT": "-1"}
        with pytest.raises(ConfigError):
            validate_db_config(env)

    def test_port_boundary_low(self):
        env = {**_VALID_ENV, "DB_PORT": "1"}
        cfg = validate_db_config(env)
        assert cfg.port == 1

    def test_port_boundary_high(self):
        env = {**_VALID_ENV, "DB_PORT": "65535"}
        cfg = validate_db_config(env)
        assert cfg.port == 65535

    def test_error_message_names_missing_var(self):
        env = {**_VALID_ENV}
        del env["DB_PASSWORD"]
        with pytest.raises(ConfigError) as exc_info:
            validate_db_config(env)
        assert "DB_PASSWORD" in str(exc_info.value)
