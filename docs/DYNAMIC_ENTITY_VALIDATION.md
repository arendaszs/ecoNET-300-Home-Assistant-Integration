# Dynamic Entity Validation Layer

> **Last Updated**: December 2024
> **Status**: Active
> **Affects**: `number.py`, `switch.py`, `select.py`, `sensor.py`, `common_functions.py`

This document describes the validation and locking layer for dynamic entities created from the `mergedData` API endpoint.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Schema](#architecture-schema)
3. [Validation Functions](#validation-functions)
4. [Locking Mechanism](#locking-mechanism)
5. [Entity Type Detection](#entity-type-detection)
6. [Entity Availability](#entity-availability)
7. [API Data Structure](#api-data-structure)
8. [Configuration Options](#configuration-options)
9. [Developer Guidelines](#developer-guidelines)
10. [Troubleshooting](#troubleshooting)

---

## Overview

Dynamic entities are created from parameters discovered at runtime via the `mergedData` API endpoint. Unlike legacy entities (defined in `const.py` mappings), dynamic entities are generated based on device capabilities.

### Key Features

- **Parameter Validation**: Ensures data integrity before entity creation
- **Lock State Handling**: Respects device-side parameter locks
- **Entity Type Detection**: Automatically determines correct entity type (number, switch, select, sensor)
- **Dynamic Availability**: Entities become unavailable when locked

---

## Architecture Schema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           API RESPONSE (mergedData)                         │
│                                                                             │
│  {                                                                          │
│    "parameters": {                                                          │
│      "1234": {                                                              │
│        "key": "1234",                                                       │
│        "name": "Boiler Temperature",                                        │
│        "value": 65,                                                         │
│        "edit": true,                                                        │
│        "unit_name": "°C",                                                   │
│        "minv": 30,                                                          │
│        "maxv": 85,                                                          │
│        "locked": true,                      ◄── Lock status from device     │
│        "lock_reason": "Weather control",   ◄── Human-readable reason        │
│        "enum": null,                                                        │
│        "category_index": 5,                                                 │
│        "category_name": "Boiler"                                            │
│      }                                                                      │
│    }                                                                        │
│  }                                                                          │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         VALIDATION LAYER                                    │
│                      (common_functions.py)                                  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  validate_parameter_data(param)                                      │   │
│  │  ├── Check: key exists and not empty                                 │   │
│  │  ├── Check: name exists and not empty                                │   │
│  │  ├── Check: if editable number → valid min/max range                 │   │
│  │  └── Check: if enum → values not empty                               │   │
│  │                                                                       │   │
│  │  Returns: (is_valid: bool, error_message: str)                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                         │
│                     ┌─────────────┴─────────────┐                           │
│                     │                           │                           │
│                ❌ Invalid                   ✅ Valid                        │
│                     │                           │                           │
│              Skip + Log                         ▼                           │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  LOCK CHECK                                                          │   │
│  │  is_parameter_locked(param) → bool                                   │   │
│  │  get_lock_reason(param) → str | None                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                         │
│                     ┌─────────────┴─────────────┐                           │
│                     │                           │                           │
│              🔒 Locked                    🔓 Unlocked                       │
│                     │                           │                           │
│                     ▼                           ▼                           │
│  ┌─────────────────────────┐    ┌─────────────────────────────────────┐    │
│  │ show_locked_as_sensors  │    │  ENTITY TYPE DETECTION              │    │
│  │ option enabled?         │    │                                     │    │
│  │                         │    │  should_be_number_entity(param)     │    │
│  │ YES → Create Sensor     │    │  should_be_switch_entity(param)     │    │
│  │ NO  → Skip parameter    │    │  should_be_select_entity(param)     │    │
│  └─────────────────────────┘    │  should_be_read_only_sensor(param)  │    │
│                                 └─────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ENTITY CREATION                                     │
│                                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌─────────────┐  │
│  │    NUMBER     │  │    SWITCH     │  │    SELECT     │  │   SENSOR    │  │
│  │   (number.py) │  │  (switch.py)  │  │  (select.py)  │  │ (sensor.py) │  │
│  │               │  │               │  │               │  │             │  │
│  │ • Editable    │  │ • 2 options   │  │ • 3+ options  │  │ • Read-only │  │
│  │ • Has unit    │  │ • Binary      │  │ • Has enum    │  │ • Info only │  │
│  │ • Min/Max     │  │   pattern     │  │               │  │ • Locked    │  │
│  │               │  │   (on/off)    │  │               │  │   params    │  │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘  └──────┬──────┘  │
│          │                  │                  │                 │         │
│          └──────────────────┴──────────────────┴─────────────────┘         │
│                                      │                                      │
└──────────────────────────────────────┼──────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RUNTIME BEHAVIOR                                    │
│                                                                             │
│  Each coordinator update:                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  _handle_coordinator_update()                                        │   │
│  │  │                                                                   │   │
│  │  ├── Update value from mergedData                                    │   │
│  │  ├── Update lock state (self._locked / _is_parameter_locked())       │   │
│  │  └── Trigger async_write_ha_state()                                  │   │
│  │                                                                       │   │
│  │  available property:                                                  │   │
│  │  │                                                                   │   │
│  │  ├── Check super().available (coordinator connected?)                │   │
│  │  └── Check NOT locked → Entity grayed out if locked                  │   │
│  │                                                                       │   │
│  │  When user attempts to change value:                                  │   │
│  │  │                                                                   │   │
│  │  └── if locked → Raise HomeAssistantError with lock_reason           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Validation Functions

Located in `custom_components/econet300/common_functions.py`:

### `validate_parameter_data(param: dict) -> tuple[bool, str]`

Validates parameter completeness before entity creation.

```python
def validate_parameter_data(param: dict) -> tuple[bool, str]:
    """Validate parameter from mergedData before entity creation.
    
    Args:
        param: Parameter dictionary from mergedData
        
    Returns:
        Tuple of (is_valid, error_message)
        - (True, "") if valid
        - (False, "reason") if invalid
    """
```

**Validation Rules:**

| Rule | Condition | Error Message |
|------|-----------|---------------|
| Key exists | `param.get("key")` is truthy | "Missing key or name" |
| Name exists | `param.get("name")` is truthy | "Missing key or name" |
| Number range | If `edit=True` and `unit_name` set | "Missing min/max for number" |
| Range validity | `minv < maxv` | "Invalid min/max range" |
| Numeric values | `minv` and `maxv` are numeric | "Non-numeric min/max values" |
| Enum values | If `enum` set, `values` not empty | "Empty enum values" |

### `is_parameter_locked(param: dict) -> bool`

Checks if a parameter is locked by the device.

```python
def is_parameter_locked(param: dict) -> bool:
    """Check if parameter is locked using existing mergedData field."""
    return param.get("locked", False)
```

### `get_lock_reason(param: dict) -> str | None`

Gets the human-readable lock reason.

```python
def get_lock_reason(param: dict) -> str | None:
    """Get human-readable lock reason from mergedData."""
    return param.get("lock_reason")
```

---

## Locking Mechanism

### Lock Sources

Locks originate from the ecoNET device and are included in the `mergedData` response. Common lock reasons:

| Lock Reason | Description | Endpoint Source |
|-------------|-------------|-----------------|
| Weather control enabled | Parameter controlled by weather module | `rmLocksNames` |
| Controller is off | Parameter unavailable when controller off | `rmLocksNames` |
| HUW mode set to schedule | Hot water controlled by schedule | `rmLocksNames` |
| Lambda calibration active | During probe calibration | `rmLocksNames` |

### Lock Handling Flow

```
Parameter locked?
       │
       ├── YES ──► show_locked_as_sensors option?
       │                    │
       │                    ├── YES ──► Create read-only sensor
       │                    │           with lock icon
       │                    │
       │                    └── NO  ──► Skip parameter entirely
       │
       └── NO  ──► Create appropriate entity type
                   (number, switch, select)
```

### Runtime Lock Changes

When a lock status changes during runtime:

1. **Coordinator fetches new data** from `mergedData`
2. **`_handle_coordinator_update()`** updates `self._locked`
3. **`available` property** returns `False` if locked
4. **Home Assistant UI** shows entity as grayed out (unavailable)
5. **User interaction blocked** with informative error message

---

## Entity Type Detection

Located in `custom_components/econet300/common_functions.py`:

### Decision Matrix

```
┌─────────────────────────────────────────────────────────────────┐
│                    ENTITY TYPE DECISION TREE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Parameter has edit=True?                                        │
│       │                                                          │
│       ├── NO ──────────────────────────────────► SENSOR         │
│       │                                                          │
│       └── YES ──► Has enum?                                      │
│                       │                                          │
│                       ├── NO ──► Has unit_name?                  │
│                       │              │                           │
│                       │              ├── YES ──► Valid min/max?  │
│                       │              │              │            │
│                       │              │              ├── YES ──► NUMBER
│                       │              │              │            │
│                       │              │              └── NO ───► SENSOR
│                       │              │                           │
│                       │              └── NO ───────────────────► SENSOR
│                       │                                          │
│                       └── YES ──► enum.count?                    │
│                                       │                          │
│                                       ├── == 2 ──► Binary pattern?
│                                       │              │           │
│                                       │              ├── YES ──► SWITCH
│                                       │              │           │
│                                       │              └── NO ───► SELECT
│                                       │                          │
│                                       └── >= 3 ─────────────────► SELECT
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Detection Functions

#### `should_be_number_entity(param: dict) -> bool`

```python
# Criteria for NUMBER entity:
# 1. edit = True (editable)
# 2. unit_name is set (has measurement unit)
# 3. No enum (not a selection)
# 4. Valid minv/maxv range (minv < maxv)
```

#### `should_be_switch_entity(param: dict) -> bool`

```python
# Criteria for SWITCH entity:
# 1. edit = True (editable)
# 2. Has enum with exactly 2 options
# 3. Options match binary pattern (on/off, yes/no, etc.)
```

**Binary Patterns Recognized:**

- `on` / `off`
- `yes` / `no`
- `enable` / `disable`
- `enabled` / `disabled`
- `active` / `inactive`
- `start` / `stop`
- `open` / `close`
- `true` / `false`
- `1` / `0`
- `tak` / `nie` (Polish)
- `wł` / `wył` (Polish)
- `włączony` / `wyłączony` (Polish)

#### `should_be_select_entity(param: dict) -> bool`

```python
# Criteria for SELECT entity:
# 1. edit = True (editable)
# 2. Has enum with 3+ options
# 3. Options are valid strings
# 4. NOT a binary pattern (handled by switch)
```

#### `should_be_read_only_sensor(param: dict, category_name: str | None) -> bool`

```python
# Criteria for read-only SENSOR:
# 1. edit = False (not editable), OR
# 2. locked = True (device-locked), OR
# 3. category_name = "Information" (info-only category)
```

---

## Entity Availability

### Implementation

Each editable entity type implements the `available` property:

```python
@property
def available(self) -> bool:
    """Return True if entity is available (not locked).

    When a parameter is locked by the device (e.g., "Weather control enabled"),
    the entity becomes unavailable in Home Assistant, preventing user interaction.
    """
    # Base availability check (coordinator connected, etc.)
    if not super().available:
        return False
    # Check if parameter is locked
    return not self._is_parameter_locked()  # or not self._locked
```

### Entity Classes with Lock Support

| Entity Class | File | Lock Check Method |
|--------------|------|-------------------|
| `EconetNumber` | `number.py` | `_is_parameter_locked()` |
| `MixerNumber` | `number.py` | `_is_parameter_locked()` |
| `MixerDynamicNumber` | `number.py` | `_is_parameter_locked()` |
| `MenuCategorySwitch` | `switch.py` | `self._locked` |
| `MenuCategorySelect` | `select.py` | `self._locked` |

### Visual Indicators

When a parameter is locked:

1. **Entity unavailable** (grayed out in UI)
2. **Lock icon** (`mdi:lock`) displayed
3. **Extra attributes** show `locked: true` and `lock_reason`
4. **Error on interaction** with descriptive message

---

## API Data Structure

### mergedData Response

```json
{
  "parameters": {
    "1234": {
      "key": "1234",
      "name": "Parameter Name",
      "value": 65,
      "edit": true,
      "unit_name": "°C",
      "minv": 30,
      "maxv": 85,
      "locked": false,
      "lock_reason": null,
      "enum": null,
      "category_index": 5,
      "category_name": "Boiler"
    },
    "1235": {
      "key": "1235",
      "name": "Operation Mode",
      "value": 1,
      "edit": true,
      "unit_name": null,
      "minv": null,
      "maxv": null,
      "locked": true,
      "lock_reason": "Weather control enabled",
      "enum": {
        "values": ["Manual", "Auto", "Schedule"],
        "first": 0
      },
      "category_index": 5,
      "category_name": "Boiler"
    }
  }
}
```

### Required Fields for Entity Creation

| Field | Required | Used For |
|-------|----------|----------|
| `key` | ✅ Yes | Entity unique_id |
| `name` | ✅ Yes | Entity name |
| `value` | ✅ Yes | Current state |
| `edit` | ✅ Yes | Editable vs read-only |
| `unit_name` | For numbers | Unit of measurement |
| `minv` | For numbers | Minimum value |
| `maxv` | For numbers | Maximum value |
| `locked` | Optional | Lock state (default: false) |
| `lock_reason` | Optional | Human-readable lock reason |
| `enum` | For switch/select | Available options |
| `category_index` | Optional | Device grouping |
| `category_name` | Optional | Device grouping |

---

## Configuration Options

In `config_flow.py` (Options Flow):

| Option | Default | Description |
|--------|---------|-------------|
| `show_locked_as_sensors` | `True` | Create read-only sensors for locked editable parameters |
| `include_lock_reasons` | `True` | Include lock_reason in entity attributes |

### Translation Keys

```json
{
  "options": {
    "step": {
      "init": {
        "data": {
          "show_locked_as_sensors": "Show locked parameters as read-only sensors",
          "include_lock_reasons": "Include lock reasons in entity attributes"
        }
      }
    }
  }
}
```

---

## Developer Guidelines

### Adding New Validation Rules

1. Add validation logic to `validate_parameter_data()` in `common_functions.py`
2. Return `(False, "descriptive error message")` for invalid parameters
3. Update this documentation

### Adding New Entity Types

1. Create entity type detection function in `common_functions.py`
2. Add lock handling (`_is_parameter_locked()` or `self._locked`)
3. Implement `available` property
4. Handle lock in action methods (raise `HomeAssistantError`)
5. Update this documentation

### Adding New Lock Reasons

Lock reasons come from the device via `rmLocksNames` endpoint. No code changes needed - they're automatically passed through `mergedData`.

### Testing

Run validation tests:

```bash
pytest tests/test_validation_functions.py -v
```

Test cases cover:

- Parameter validation (valid/invalid)
- Lock detection
- Lock reason retrieval
- Read-only sensor detection
- Real lock reasons from fixtures

---

## Troubleshooting

### Entity Not Created

**Check logs for:**

```
DEBUG: Skipping invalid parameter 1234: Missing key or name
DEBUG: Skipping locked parameter: Parameter Name
```

**Common causes:**

- Missing required fields (`key`, `name`)
- Invalid min/max range for numbers
- Empty enum values
- Parameter locked (if `show_locked_as_sensors` is disabled)

### Entity Shows as Unavailable

**Expected behavior when:**

- Parameter is locked by device
- Coordinator is not connected
- Device is offline

**Check attributes for:**

```yaml
locked: true
lock_reason: "Weather control enabled"
```

### Cannot Change Value

**Error message format:**

```
Parameter 'Boiler Temperature' is locked and cannot be modified
Cannot turn ON: Weather control enabled
Cannot change option: Controller is off
```

**Resolution:**

1. Check device/controller settings
2. Disable weather control or other automatic modes
3. Wait for device to release lock

---

## Changelog

| Date | Change |
|------|--------|
| Dec 2024 | Initial validation layer implementation |
| Dec 2024 | Added `available` property for dynamic lock handling |
| Dec 2024 | Added configuration options for lock behavior |

---

## Related Documentation

- [API V1 Documentation](API_V1_DOCUMENTATION.md)
- [API Construction Guide](API_CONSTRUCTION_GUIDE.md)
- [Cloud Translations](cloud_translations/README.md)
- [Developer Tools Guide](DEVELOPER_TOOLS_GUIDE.md)

