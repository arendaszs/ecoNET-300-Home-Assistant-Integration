"""Test switch exception handling symmetry."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError
import pytest

from custom_components.econet300.switch import BoilerControlError, EconetSwitch


class TestSwitchExceptionHandling:
    """Test that both async_turn_on and async_turn_off handle exceptions symmetrically."""

    @pytest.fixture
    def mock_switch(self):
        """Create a mock switch entity."""
        mock_coordinator = MagicMock()
        mock_api = MagicMock()
        entity_description = MagicMock()
        entity_description.key = "boiler_control"
        entity_description.name = "Boiler Control"

        switch = EconetSwitch(entity_description, mock_coordinator, mock_api)
        # Mock hass and async_write_ha_state to avoid runtime errors
        switch.hass = MagicMock()
        switch.async_write_ha_state = AsyncMock()
        return switch

    @pytest.mark.asyncio
    async def test_async_turn_on_catches_all_exceptions(self, mock_switch):
        """Test that async_turn_on catches all exceptions."""
        # Mock API to raise ClientError
        mock_switch.api.set_param = AsyncMock(side_effect=ClientError("Network error"))
        mock_switch._attr_is_on = False  # noqa: SLF001

        # Should catch the exception and re-raise it
        with pytest.raises(ClientError):
            await mock_switch.async_turn_on()

        # State should not have changed
        assert mock_switch._attr_is_on is False  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_async_turn_off_catches_all_exceptions(self, mock_switch):
        """Test that async_turn_off catches all exceptions."""
        # Mock API to raise ClientError
        mock_switch.api.set_param = AsyncMock(side_effect=ClientError("Network error"))
        mock_switch._attr_is_on = True  # noqa: SLF001

        # Should catch the exception and re-raise it
        with pytest.raises(ClientError):
            await mock_switch.async_turn_off()

        # State should not have changed
        assert mock_switch._attr_is_on is True  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_async_turn_off_catches_oserror_and_converts_to_boiler_error(
        self, mock_switch
    ):
        """Test that async_turn_off catches OSError and converts to BoilerControlError."""
        # Mock API to raise OSError
        mock_switch.api.set_param = AsyncMock(side_effect=OSError("Connection failed"))
        mock_switch._attr_is_on = True  # noqa: SLF001

        # Should catch OSError and convert to BoilerControlError
        with pytest.raises(BoilerControlError) as exc_info:
            await mock_switch.async_turn_off()

        # BoilerControlError now uses translation keys
        assert exc_info.value.translation_key == "boiler_control_failed"
        placeholders = exc_info.value.translation_placeholders or {}
        assert "Connection failed" in placeholders.get("error", "")
        # State should not have changed
        assert mock_switch._attr_is_on is True  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_async_turn_off_catches_timeout_and_converts_to_boiler_error(
        self, mock_switch
    ):
        """Test that async_turn_off catches TimeoutError and converts to BoilerControlError."""
        # Mock API to raise TimeoutError
        mock_switch.api.set_param = AsyncMock(
            side_effect=asyncio.TimeoutError("Request timeout")
        )
        mock_switch._attr_is_on = True  # noqa: SLF001

        # Should catch TimeoutError and convert to BoilerControlError
        with pytest.raises(BoilerControlError) as exc_info:
            await mock_switch.async_turn_off()

        # BoilerControlError now uses translation keys
        assert exc_info.value.translation_key == "boiler_control_failed"
        # State should not have changed
        assert mock_switch._attr_is_on is True  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_async_turn_off_catches_boiler_control_error_and_re_raises(
        self, mock_switch
    ):
        """Test that async_turn_off catches BoilerControlError and re-raises it."""
        # Mock API to raise BoilerControlError
        mock_switch.api.set_param = AsyncMock(
            side_effect=BoilerControlError("API failure")
        )
        mock_switch._attr_is_on = True  # noqa: SLF001

        # Should catch and re-raise BoilerControlError
        with pytest.raises(BoilerControlError) as exc_info:
            await mock_switch.async_turn_off()

        # BoilerControlError uses translation keys, check it's re-raised properly
        assert exc_info.value.translation_key == "boiler_control_failed"
        # State should not have changed
        assert mock_switch._attr_is_on is True  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_async_turn_off_handles_value_error_gracefully(self, mock_switch):
        """Test that async_turn_off catches ValueError and re-raises it."""
        # Mock API to raise ValueError
        mock_switch.api.set_param = AsyncMock(side_effect=ValueError("Invalid value"))
        mock_switch._attr_is_on = True  # noqa: SLF001

        # Should catch ValueError and re-raise it
        with pytest.raises(ValueError):
            await mock_switch.async_turn_off()

        # State should not have changed
        assert mock_switch._attr_is_on is True  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_async_turn_off_successful_operation(self, mock_switch):
        """Test that async_turn_off works correctly on successful operation."""
        # Mock API to succeed
        mock_switch.api.set_param = AsyncMock(return_value=True)
        mock_switch._attr_is_on = True  # noqa: SLF001

        await mock_switch.async_turn_off()

        # Should have called set_param with correct parameters
        mock_switch.api.set_param.assert_called_once_with("BOILER_CONTROL", 0)
        # State should be updated
        assert mock_switch._attr_is_on is False  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_async_turn_off_handles_false_return_value(self, mock_switch):
        """Test that async_turn_off handles API returning False correctly."""
        # Mock API to return False (operation failed)
        mock_switch.api.set_param = AsyncMock(return_value=False)
        mock_switch._attr_is_on = True  # noqa: SLF001

        # Should raise BoilerControlError
        with pytest.raises(BoilerControlError) as exc_info:
            await mock_switch.async_turn_off()

        # BoilerControlError now uses translation keys
        assert exc_info.value.translation_key == "boiler_control_failed"
        placeholders = exc_info.value.translation_placeholders or {}
        assert "Failed to turn boiler OFF" in placeholders.get("error", "")
        # State should not have changed
        assert mock_switch._attr_is_on is True  # noqa: SLF001
