"""Test configuration for ecoNET300 integration tests.

This module provides pytest fixtures and configuration for testing the
ecoNET300 Home Assistant integration.
"""

import json
from pathlib import Path
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import pytest
import pytest_asyncio

# Add the project root to the Python path so tests can import custom_components
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================================================
# Home Assistant Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def hass():
    """Create a Home Assistant instance for testing.

    This creates a minimal HA instance suitable for integration tests.
    For unit tests, prefer using mock_hass fixture instead.
    """
    hass_instance = HomeAssistant("test")

    # Mock the config_entries to avoid initialization issues
    mock_config_entries = MagicMock()
    mock_config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    mock_config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass_instance.config_entries = mock_config_entries

    await hass_instance.async_start()
    yield hass_instance
    await hass_instance.async_stop()


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance for unit tests.

    This is lighter weight than the full hass fixture and suitable
    for unit tests that don't need actual HA functionality.
    """
    mock = MagicMock(spec=HomeAssistant)
    mock.data = {}
    mock.config_entries = MagicMock()
    mock.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    mock.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    return mock


# ============================================================================
# Config Entry Fixtures
# ============================================================================


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry for testing."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.data = {
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_password",
    }
    entry.options = {
        "enable_dynamic_entities": True,
        "show_service_parameters": True,
    }
    return entry


@pytest.fixture
def mock_config_entry_minimal():
    """Create a minimal mock config entry without options."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.data = {
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_password",
    }
    entry.options = {}
    return entry


# ============================================================================
# API Fixtures
# ============================================================================


@pytest.fixture
def mock_api():
    """Create a mock Econet300Api for testing."""
    from custom_components.econet300.api import Econet300Api

    api = MagicMock(spec=Econet300Api)
    api.uid = "test-device-uid"
    api.model_id = "ecoMAX810P-L"
    api.host = "http://192.168.1.100"
    api.sw_rev = "1.0.0"
    return api


@pytest.fixture
def mock_coordinator():
    """Create a mock EconetDataCoordinator for testing."""
    from custom_components.econet300.common import EconetDataCoordinator

    coordinator = MagicMock(spec=EconetDataCoordinator)
    coordinator.data = {
        "sysParams": {"controllerID": "ecoMAX810P-L"},
        "regParams": {},
        "paramsEdits": {},
    }
    coordinator.has_reg_data = MagicMock(return_value=True)
    return coordinator


# ============================================================================
# Fixture Data Fixtures
# ============================================================================


@pytest.fixture
def fixtures_dir():
    """Return the path to the fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    """Return a function to load fixture files."""

    def _load_fixture(device: str, filename: str) -> dict[str, Any]:
        """Load a fixture file.

        Args:
            device: Device folder name (e.g., "ecoMAX810P-L")
            filename: File name (e.g., "regParams.json")

        Returns:
            Parsed JSON content

        """
        fixtures_dir = Path(__file__).parent / "fixtures"
        file_path = fixtures_dir / device / filename
        if not file_path.exists():
            return {}
        with file_path.open(encoding="utf-8") as f:
            return json.load(f)

    return _load_fixture


@pytest.fixture
def ecomax810p_reg_params(load_fixture):
    """Load ecoMAX810P-L regParams fixture."""
    return load_fixture("ecoMAX810P-L", "regParams.json")


@pytest.fixture
def ecomax810p_sys_params(load_fixture):
    """Load ecoMAX810P-L sysParams fixture."""
    return load_fixture("ecoMAX810P-L", "sysParams.json")


@pytest.fixture
def ecomax810p_merged_data(load_fixture):
    """Load ecoMAX810P-L mergedData fixture."""
    return load_fixture("ecoMAX810P-L", "mergedData.json")


# ============================================================================
# Integration Setup Fixtures
# ============================================================================


@pytest.fixture
def mock_integration_setup(mock_hass, mock_config_entry, mock_api, mock_coordinator):
    """Set up a mock integration environment."""
    from custom_components.econet300 import DOMAIN

    mock_hass.data[DOMAIN] = {
        mock_config_entry.entry_id: {
            "api": mock_api,
            "coordinator": mock_coordinator,
        }
    }
    return {
        "hass": mock_hass,
        "config_entry": mock_config_entry,
        "api": mock_api,
        "coordinator": mock_coordinator,
    }
