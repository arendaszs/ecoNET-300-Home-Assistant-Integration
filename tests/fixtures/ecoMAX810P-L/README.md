# 🔄 RM Endpoints Merged Data Structure

## 📋 Overview

This directory contains test fixtures demonstrating how the `rm...` endpoint data merges together in the ecoNET300 Home Assistant integration.

## 📁 Files

### **📊 Comprehensive Merged Data**

- **`rmParamsComplete.json`** - **Complete merged data** with all 165+ parameters from real endpoint data
  - **Size**: 3,965 lines (vs 179 lines in example version)
  - **Parameters**: 165 total parameters with complete data
  - **Structure**: 216 structure entries, 31 enum types, 9 unit types
  - **Generated**: Using real test fixture data, not mock examples

### **Individual Endpoint Files**

- `rmParamsData.json` - Parameter metadata (values, min/max, units, edit flags)
- `rmParamsNames.json` - Human-readable parameter names
- `rmParamsDescs.json` - Parameter descriptions
- `rmStructure.json` - Menu structure and navigation
- `rmParamsEnums.json` - Enumeration values
- `rmLangs.json` - Available languages
- `rmLocksNames.json` - Lock/restriction messages
- `rmAlarmsNames.json` - Alarm names

### **Merged Data Files**

- `rmParamsComplete.json` - **Complete merged structure** showing how all endpoints combine
- `rmParamsComplete_generated.json` - **Generated example** from the test script

## 🔢 Parameter Number Mapping

The `number` field in each parameter represents the **actual parameter ID** from the ecoNET system, derived from the `rmStructure` endpoint:

### **How It Works**

1. **Structure Analysis**: The system extracts all entries with `type: 1` (parameter type) from `rmStructure`
2. **Index Mapping**: Each parameter in the array gets mapped to its corresponding structure entry
3. **Number Assignment**: The `index` field from the structure entry becomes the parameter's `number`

### **Example Mapping**

```json
// Parameter array (rmParamsData)
[
  {"value": 60, "index": 0},  // First parameter
  {"value": 5, "index": 1},   // Second parameter
  {"value": 10, "index": 2}    // Third parameter
]

// Structure entries (rmStructure) - type: 1 only
[
  {"index": 46, "type": 1},   // Maps to parameter 0
  {"index": 111, "type": 1},  // Maps to parameter 1
  {"index": 112, "type": 1}   // Maps to parameter 2
]

// Result: Merged parameters with numbers
[
  {"value": 60, "index": 0, "number": 46},
  {"value": 5, "index": 1, "number": 111},
  {"value": 10, "index": 2, "number": 112}
]
```

### **Why This Matters**

- **`index`**: Array position (0, 1, 2, ...) - used for internal processing
- **`number`**: Actual ecoNET parameter ID (46, 111, 112, ...) - used for API calls and system integration

This mapping ensures that the parameter numbers match exactly with the ecoNET system's internal parameter IDs, enabling proper integration with the heating controller's API.

## 🔧 Units Mapping

The `unit_name` field in each parameter represents the **actual unit symbol** from the ecoNET system, derived from the `rmParamsUnitsNames` endpoint:

### **How Units Work**

1. **Unit Index**: Each parameter has a `unit` field (e.g., `"unit": 5`)
2. **Units Array**: The `rmParamsUnitsNames` endpoint provides an array of unit symbols
3. **Unit Resolution**: The unit index maps to the corresponding unit symbol in the array

### **Example Units Mapping**

```json
// Units array (rmParamsUnitsNames)
["", "°C", "sek.", "min.", "h.", "%", "kg", "kW", "r/min"]

// Parameter data
{"value": 60, "unit": 5}  // unit index 5

// Result: Merged parameter with unit name
{"value": 60, "unit": 5, "unit_name": "%"}  // unit index 5 → "%"
```

### **Why Units Matter**

- **`unit`**: Index into the units array (5) - used for internal processing
- **`unit_name`**: Actual unit symbol ("%") - used for display and user interface

This mapping ensures that parameters display with the correct unit symbols, providing a better user experience in the Home Assistant interface.

## 🔧 Merging Process

### **Step 1: Foundation (`rmParamsData` + `rmParamsNames`)**

```json
{
  "parameters": [
    {
      "value": 60,
      "maxv": 100,
      "minv": 15,
      "edit": true,
      "unit": 5,
      "name": "100% Blow-in output",
      "index": 0
    }
  ]
}
```

### **Step 2: Add Descriptions (`+ rmParamsDescs`)**

```json
{
  "parameters": [
    {
      "value": 60,
      "maxv": 100,
      "minv": 15,
      "edit": true,
      "unit": 5,
      "name": "100% Blow-in output",
      "description": "Blow-in output when the burner runs at maximum output.",
      "index": 0
    }
  ]
}
```

### **Step 3: Complete Structure (`+ rmStructure + rmParamsEnums`)**

```json
{
  "parameters": [
    {
      "value": 60,
      "maxv": 100,
      "minv": 15,
      "edit": true,
      "unit": 5,
      "name": "100% Blow-in output",
      "description": "Blow-in output when the burner runs at maximum output.",
      "index": 0,
      "number": 46,
      "unit_name": "%"
    }
  ],
  "structure": [{ "pass_index": 0, "index": 1, "type": 7, "lock": false }],
  "enums": [
    { "0": ["off", "on"] },
    { "1": ["off", "priority", "no_priority", "summer_mode"] }
  ]
}
```

## 🚀 API Methods

The merging is implemented through these step-by-step methods:

### **1. `fetch_merged_rm_data_with_names()`**

- **Merges**: `rmParamsData` + `rmParamsNames`
- **Result**: Parameters with metadata and human-readable names
- **Version**: `1.0-names`

### **2. `fetch_merged_rm_data_with_names_and_descs()`**

- **Merges**: Previous + `rmParamsDescs`
- **Result**: Parameters with names and descriptions
- **Version**: `1.0-names-descs`

### **3. `fetch_merged_rm_data_with_names_descs_and_structure()`**

- **Merges**: Previous + `rmStructure` + `rmParamsEnums` + `rmParamsUnitsNames`
- **Result**: Complete unified data structure with parameter numbers and units
- **Version**: `1.0-names-descs-structure-units`

## 🔄 Data Generation

### **Comprehensive Data Generation**

The comprehensive `rmParamsComplete.json` file is generated using real endpoint data:

```bash
# Generate comprehensive merged data (165+ parameters)
python scripts/generate_comprehensive_rm_data.py
```

**Generated Data Statistics:**

- **Total Parameters**: 165 (vs 5 in example)
- **Named Parameters**: 165 (100% coverage)
- **Described Parameters**: 165 (100% coverage)
- **Editable Parameters**: 165 (100% coverage)
- **Structure Entries**: 216
- **Enum Types**: 31
- **Unit Types**: 9
- **Parameter Numbers**: 115 (mapped from structure)

### **Example vs Comprehensive**

| Aspect          | Example Version     | Comprehensive Version  |
| --------------- | ------------------- | ---------------------- |
| **Parameters**  | 5                   | 165                    |
| **File Size**   | 179 lines           | 3,965 lines            |
| **Data Source** | Mock/test data      | Real endpoint fixtures |
| **Coverage**    | Partial             | Complete               |
| **Use Case**    | Testing/development | Production/analysis    |

## 🧪 Testing

Run the test script to see the merging process in action:

```bash
python scripts/test_rm_merging.py
```

This will:

1. Demonstrate each step of the merging process
2. Show the progressive data structure
3. Generate a complete merged JSON file
4. Display statistics about the merged data

## 📊 Data Structure Benefits

### **Performance**

- **Single API call** instead of multiple separate calls
- **Parallel processing** of all endpoints
- **Reduced network overhead**

### **Usability**

- **Unified data structure** for all parameter information
- **Easy access** to names, descriptions, values, and metadata
- **Consistent format** across all parameters

### **Maintenance**

- **Single method** to maintain instead of multiple
- **Consistent error handling**
- **Easier testing and debugging**

## 🔍 Example Usage

```python
# Get complete merged data
api = Econet300Api(...)
complete_data = await api.fetch_merged_rm_data_with_names_descs_and_structure("en")

# Access parameter information
for param in complete_data["parameters"]:
    print(f"Name: {param['name']}")
    print(f"Description: {param['description']}")
    print(f"Value: {param['value']}")
    print(f"Range: {param['minv']} - {param['maxv']}")
    print(f"Editable: {param['edit']}")
    print(f"Number: {param['number']}")
    print("---")

# Access structure
structure = complete_data["structure"]
for item in structure:
    print(f"Menu item: {item['index']} (type: {item['type']})")

# Access enums
enums = complete_data["enums"]
for enum_type, values in enums.items():
    print(f"Enum {enum_type}: {values}")
```

## 🎯 Key Features

- **Progressive Merging**: Each step builds on the previous one
- **Error Handling**: Graceful handling of failed endpoint calls
- **Type Safety**: Proper type annotations and validation
- **Debugging**: Clear logging of each merging step
- **Flexibility**: Can stop at any step depending on needs

This merged approach provides a much cleaner and more efficient way to work with the RM endpoint data, matching exactly how the ecoNET24 web interface processes the information.
