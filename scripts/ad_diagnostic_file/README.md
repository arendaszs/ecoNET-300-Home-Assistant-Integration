# Diagnostic Files Drop Folder

Drop your Home Assistant ecoNET300 diagnostic files here.

## How to Get Diagnostic Files

1. Open **Home Assistant**
2. Go to **Settings → Devices & Services**
3. Find the **ecoNET300** integration
4. Click on it to open
5. Click the **⋮ menu** (three dots) → **Download diagnostics**
6. Copy the downloaded `config_entry-econet300-*.json` file here

## Usage

After placing your file(s) here, run:

```bash
python scripts/create_fixture_from_diagnostics.py
```

The script will:
1. Auto-detect the device name from the diagnostic file
2. Create a fixture folder in `tests/fixtures/{device_name}/`
3. Extract and save all relevant data files
4. **Delete the source diagnostic file** after successful processing

## Options

```bash
# Preview only (don't create files)
python scripts/create_fixture_from_diagnostics.py --dry-run

# Keep the diagnostic file after processing
python scripts/create_fixture_from_diagnostics.py --keep-file

# Override device name
python scripts/create_fixture_from_diagnostics.py --device-name "ecoMAX920i2"
```

## Notes

- Only **ecoNET300** diagnostic files are processed
- HACS or other integration diagnostics will be skipped
- Files are automatically deleted after successful processing (use `--keep-file` to prevent)
