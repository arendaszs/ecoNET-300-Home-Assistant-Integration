"""Tests for parameter validation functions in common_functions.py."""

import pytest

from custom_components.econet300.common_functions import (
    get_lock_reason,
    is_binary_enum,
    is_parameter_locked,
    should_be_select_entity,
    should_be_switch_entity,
    validate_parameter_data,
)


class TestValidateParameterData:
    """Tests for validate_parameter_data function."""

    def test_valid_parameter_with_all_fields(self):
        """Test validation passes for a complete valid parameter."""
        param = {
            "key": "tempCOSet",
            "name": "Boiler Temperature Setpoint",
            "edit": True,
            "unit_name": "°C",
            "minv": 30,
            "maxv": 80,
        }
        is_valid, error = validate_parameter_data(param)
        assert is_valid is True
        assert error == ""

    def test_missing_key(self):
        """Test validation fails when key is missing."""
        param = {
            "name": "Test Parameter",
            "edit": True,
        }
        is_valid, error = validate_parameter_data(param)
        assert is_valid is False
        assert "Missing parameter key" in error

    def test_missing_name(self):
        """Test validation fails when name is missing."""
        param = {
            "key": "test_key",
            "edit": True,
        }
        is_valid, error = validate_parameter_data(param)
        assert is_valid is False
        assert "Missing parameter name" in error

    def test_editable_number_missing_min_max(self):
        """Test validation fails for editable number without min/max."""
        param = {
            "key": "test_key",
            "name": "Test Parameter",
            "edit": True,
            "unit_name": "°C",
            # Missing minv and maxv
        }
        is_valid, error = validate_parameter_data(param)
        assert is_valid is False
        assert "Missing min/max" in error

    def test_editable_number_invalid_range(self):
        """Test validation fails when min >= max."""
        param = {
            "key": "test_key",
            "name": "Test Parameter",
            "edit": True,
            "unit_name": "°C",
            "minv": 80,
            "maxv": 30,  # Invalid: max < min
        }
        is_valid, error = validate_parameter_data(param)
        assert is_valid is False
        assert "Invalid min/max range" in error

    def test_editable_number_equal_range(self):
        """Test validation fails when min == max."""
        param = {
            "key": "test_key",
            "name": "Test Parameter",
            "edit": True,
            "unit_name": "°C",
            "minv": 50,
            "maxv": 50,  # Invalid: max == min
        }
        is_valid, error = validate_parameter_data(param)
        assert is_valid is False
        assert "Invalid min/max range" in error

    def test_non_editable_parameter_no_range_check(self):
        """Test validation passes for non-editable params without min/max."""
        param = {
            "key": "test_key",
            "name": "Test Parameter",
            "edit": False,  # Not editable, so no range check needed
            "unit_name": "°C",
        }
        is_valid, error = validate_parameter_data(param)
        assert is_valid is True
        assert error == ""

    def test_valid_enum_parameter(self):
        """Test validation passes for valid enum parameter."""
        param = {
            "key": "test_key",
            "name": "Test Parameter",
            "edit": True,
            "enum": {
                "values": ["OFF", "ON"],
                "first": 0,
            },
        }
        is_valid, error = validate_parameter_data(param)
        assert is_valid is True
        assert error == ""

    def test_invalid_enum_structure(self):
        """Test validation fails for invalid enum structure."""
        param = {
            "key": "test_key",
            "name": "Test Parameter",
            "edit": True,
            "enum": "not_a_dict",  # Invalid enum structure
        }
        is_valid, error = validate_parameter_data(param)
        assert is_valid is False
        assert "Invalid enum structure" in error

    def test_empty_enum_values(self):
        """Test validation fails for empty enum values."""
        param = {
            "key": "test_key",
            "name": "Test Parameter",
            "edit": True,
            "enum": {
                "values": [],  # Empty values
                "first": 0,
            },
        }
        is_valid, error = validate_parameter_data(param)
        assert is_valid is False
        assert "Empty enum values" in error


class TestIsParameterLocked:
    """Tests for is_parameter_locked function."""

    def test_locked_parameter(self):
        """Test returns True for locked parameter."""
        param = {"locked": True}
        assert is_parameter_locked(param) is True

    def test_unlocked_parameter(self):
        """Test returns False for unlocked parameter."""
        param = {"locked": False}
        assert is_parameter_locked(param) is False

    def test_missing_locked_field(self):
        """Test returns False when locked field is missing."""
        param = {}
        assert is_parameter_locked(param) is False

    def test_locked_with_reason(self):
        """Test returns True for locked parameter with reason."""
        param = {
            "locked": True,
            "lock_reason": "Weather control enabled.",
        }
        assert is_parameter_locked(param) is True


class TestGetLockReason:
    """Tests for get_lock_reason function."""

    def test_get_lock_reason_present(self):
        """Test returns lock reason when present."""
        param = {"lock_reason": "Requires turn off the controller."}
        assert get_lock_reason(param) == "Requires turn off the controller."

    def test_get_lock_reason_missing(self):
        """Test returns None when lock_reason is missing."""
        param = {}
        assert get_lock_reason(param) is None

    def test_get_lock_reason_none(self):
        """Test returns None when lock_reason is None."""
        param = {"lock_reason": None}
        assert get_lock_reason(param) is None

    def test_get_lock_reason_empty_string(self):
        """Test returns empty string when lock_reason is empty."""
        param = {"lock_reason": ""}
        assert get_lock_reason(param) == ""


class TestLockReasonsFromFixture:
    """Tests using lock reasons from fixture data."""

    @pytest.fixture
    def lock_reasons(self):
        """Load lock reasons from fixture."""
        return [
            "",
            "Requires turn off the controller.",
            "Weather control enabled.",
            "HUW mode off.",
            "Function unavailable.",
            "Lambda sensor calibration in progress",
            "",
        ]

    def test_lock_reason_weather_control(self, lock_reasons):
        """Test weather control lock reason."""
        param = {"lock_reason": lock_reasons[2]}
        assert get_lock_reason(param) == "Weather control enabled."

    def test_lock_reason_controller_off(self, lock_reasons):
        """Test controller off lock reason."""
        param = {"lock_reason": lock_reasons[1]}
        assert get_lock_reason(param) == "Requires turn off the controller."

    def test_lock_reason_huw_mode(self, lock_reasons):
        """Test HUW mode lock reason."""
        param = {"lock_reason": lock_reasons[3]}
        assert get_lock_reason(param) == "HUW mode off."

    def test_lock_reason_lambda_calibration(self, lock_reasons):
        """Test lambda calibration lock reason."""
        param = {"lock_reason": lock_reasons[5]}
        assert get_lock_reason(param) == "Lambda sensor calibration in progress"


class TestIsBinaryEnum:
    """Tests for is_binary_enum function."""

    def test_binary_on_off(self):
        """Test binary enum with OFF/ON values."""
        assert is_binary_enum(["OFF", "ON"]) is True

    def test_binary_yes_no(self):
        """Test binary enum with NO/YES values."""
        assert is_binary_enum(["NO", "YES"]) is True

    def test_binary_enabled_disabled(self):
        """Test binary enum with DISABLED/ENABLED values."""
        assert is_binary_enum(["DISABLED", "ENABLED"]) is True

    def test_non_binary_three_options(self):
        """Test non-binary enum with 3 options - only checks first 2."""
        # Note: is_binary_enum only checks first 2 values by design
        # This returns True because first 2 match binary pattern
        assert is_binary_enum(["OFF", "ON", "AUTO"]) is True

    def test_non_binary_pattern(self):
        """Test non-binary enum that doesn't match patterns."""
        assert is_binary_enum(["LOW", "MEDIUM", "HIGH"]) is False

    def test_empty_enum(self):
        """Test empty enum."""
        assert is_binary_enum([]) is False

    def test_single_value(self):
        """Test single value enum."""
        assert is_binary_enum(["ON"]) is False


class TestShouldBeSwitchEntity:
    """Tests for should_be_switch_entity function."""

    def test_binary_switch_with_min_max(self):
        """Test binary enum with min/max indicating 2 options."""
        param = {
            "edit": True,
            "enum": {"values": ["OFF", "ON"]},
            "minv": 0,
            "maxv": 1,
        }
        assert should_be_switch_entity(param) is True

    def test_three_option_enum_with_min_max_not_switch(self):
        """Test 3-option enum with min/max should NOT be switch."""
        param = {
            "edit": True,
            "enum": {"values": ["OFF", "ON", "AUTO"]},
            "minv": 0,
            "maxv": 2,
        }
        assert should_be_switch_entity(param) is False

    def test_three_option_enum_no_min_max_not_switch(self):
        """Test 3-option enum without min/max should NOT be switch.

        This is the key bug fix test - previously this would incorrectly
        return True because is_binary_enum only checks first 2 values.
        """
        param = {
            "edit": True,
            "enum": {"values": ["OFF", "ON", "AUTO"]},
            # No minv/maxv
        }
        assert should_be_switch_entity(param) is False

    def test_binary_switch_no_min_max(self):
        """Test binary enum without min/max still works as switch."""
        param = {
            "edit": True,
            "enum": {"values": ["OFF", "ON"]},
            # No minv/maxv - fallback to enum length check
        }
        assert should_be_switch_entity(param) is True

    def test_non_editable_not_switch(self):
        """Test non-editable param is not a switch."""
        param = {
            "edit": False,
            "enum": {"values": ["OFF", "ON"]},
            "minv": 0,
            "maxv": 1,
        }
        assert should_be_switch_entity(param) is False

    def test_locked_param_not_switch(self):
        """Test locked param is not a switch."""
        param = {
            "edit": True,
            "locked": True,
            "enum": {"values": ["OFF", "ON"]},
            "minv": 0,
            "maxv": 1,
        }
        assert should_be_switch_entity(param) is False

    def test_no_enum_not_switch(self):
        """Test param without enum is not a switch."""
        param = {
            "edit": True,
            "minv": 0,
            "maxv": 100,
        }
        assert should_be_switch_entity(param) is False


class TestShouldBeSelectEntity:
    """Tests for should_be_select_entity function."""

    def test_three_option_select_with_min_max(self):
        """Test 3-option enum with min/max is select."""
        param = {
            "edit": True,
            "enum": {"values": ["OFF", "ON", "AUTO"]},
            "minv": 0,
            "maxv": 2,
        }
        assert should_be_select_entity(param) is True

    def test_three_option_select_no_min_max(self):
        """Test 3-option enum without min/max is select.

        This is the key bug fix test - previously this would incorrectly
        return False because is_binary_enum returns True for first 2 values.
        """
        param = {
            "edit": True,
            "enum": {"values": ["OFF", "ON", "AUTO"]},
            # No minv/maxv
        }
        assert should_be_select_entity(param) is True

    def test_binary_enum_not_select(self):
        """Test binary enum with min/max indicating 2 options is not select."""
        param = {
            "edit": True,
            "enum": {"values": ["OFF", "ON"]},
            "minv": 0,
            "maxv": 1,
        }
        assert should_be_select_entity(param) is False

    def test_binary_enum_no_min_max_not_select(self):
        """Test binary enum without min/max is not select."""
        param = {
            "edit": True,
            "enum": {"values": ["OFF", "ON"]},
            # No minv/maxv
        }
        assert should_be_select_entity(param) is False

    def test_non_editable_not_select(self):
        """Test non-editable param is not a select."""
        param = {
            "edit": False,
            "enum": {"values": ["OFF", "ON", "AUTO"]},
            "minv": 0,
            "maxv": 2,
        }
        assert should_be_select_entity(param) is False

    def test_locked_param_not_select(self):
        """Test locked param is not a select."""
        param = {
            "edit": True,
            "locked": True,
            "enum": {"values": ["OFF", "ON", "AUTO"]},
            "minv": 0,
            "maxv": 2,
        }
        assert should_be_select_entity(param) is False

    def test_no_enum_not_select(self):
        """Test param without enum is not a select."""
        param = {
            "edit": True,
            "minv": 0,
            "maxv": 100,
        }
        assert should_be_select_entity(param) is False

    def test_many_options_select(self):
        """Test enum with many options is select."""
        param = {
            "edit": True,
            "enum": {"values": ["A", "B", "C", "D", "E"]},
            "minv": 0,
            "maxv": 4,
        }
        assert should_be_select_entity(param) is True


class TestSwitchSelectMutualExclusion:
    """Tests to ensure switch and select detection are mutually exclusive."""

    def test_binary_enum_switch_not_select(self):
        """Test binary enum is switch, not select."""
        param = {
            "edit": True,
            "enum": {"values": ["OFF", "ON"]},
            "minv": 0,
            "maxv": 1,
        }
        assert should_be_switch_entity(param) is True
        assert should_be_select_entity(param) is False

    def test_three_option_select_not_switch(self):
        """Test 3-option enum is select, not switch."""
        param = {
            "edit": True,
            "enum": {"values": ["OFF", "ON", "AUTO"]},
            "minv": 0,
            "maxv": 2,
        }
        assert should_be_switch_entity(param) is False
        assert should_be_select_entity(param) is True

    def test_three_option_no_min_max_select_not_switch(self):
        """Test 3-option enum without min/max is select, not switch.

        Critical test for the bug fix - ensures mutual exclusion
        when min/max are unavailable.
        """
        param = {
            "edit": True,
            "enum": {"values": ["OFF", "ON", "AUTO"]},
            # No minv/maxv
        }
        assert should_be_switch_entity(param) is False
        assert should_be_select_entity(param) is True

    def test_binary_no_min_max_switch_not_select(self):
        """Test binary enum without min/max is switch, not select."""
        param = {
            "edit": True,
            "enum": {"values": ["OFF", "ON"]},
            # No minv/maxv
        }
        assert should_be_switch_entity(param) is True
        assert should_be_select_entity(param) is False

