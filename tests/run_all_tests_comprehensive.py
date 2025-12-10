#!/usr/bin/env python3
"""Comprehensive test runner - runs all tests and saves outputs."""

from datetime import datetime
from pathlib import Path
import subprocess
import sys

BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "test_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# All test files
TESTS = [
    ("test_init.py", "pytest"),
    ("test_sensor_basic.py", "pytest"),
    ("test_diagnostics.py", "pytest"),
    ("test_entity_safety_checks_simple.py", "pytest"),
    ("test_icon_translations.py", "pytest"),
    ("test_translations_comprehensive.py", "pytest"),
    ("test_dynamic_number_entities.py", "pytest"),
    ("test_service_parameter_detection.py", "pytest"),
    ("test_cons_check_key.py", "script"),
]


def run_and_save(test_name, test_type):
    """Run a test and save output."""
    test_path = BASE_DIR / test_name
    if not test_path.exists():
        return {"name": test_name, "status": "NOT_FOUND", "exit": -1}

    output_file = REPORTS_DIR / f"{test_path.stem}_output.txt"

    if test_type == "pytest":
        cmd = [sys.executable, "-m", "pytest", str(test_path), "-v", "--tb=short"]
    else:
        cmd = [sys.executable, str(test_path)]

    result = subprocess.run(
        cmd, check=False, capture_output=True, text=True, cwd=BASE_DIR.parent
    )

    content = f"""Test: {test_name}
Type: {test_type}
Timestamp: {datetime.now().isoformat()}
Exit Code: {result.returncode}
{"=" * 80}

STDOUT:
{result.stdout}

STDERR:
{result.stderr}
"""
    output_file.write_text(content, encoding="utf-8")

    return {
        "name": test_name,
        "status": "PASSED" if result.returncode == 0 else "FAILED",
        "exit": result.returncode,
        "file": output_file.name,
    }


# Run all tests
print("Running all tests...")
results = []
for i, (test_name, test_type) in enumerate(TESTS, 1):
    print(f"[{i}/{len(TESTS)}] {test_name}...", end=" ")
    result = run_and_save(test_name, test_type)
    results.append(result)
    status_icon = (
        "✅"
        if result["status"] == "PASSED"
        else "❌"
        if result["status"] == "FAILED"
        else "⚠️"
    )
    print(f"{status_icon} {result['status']}")

# Create summary
summary_content = f"""Test Run Summary
{"=" * 80}
Timestamp: {datetime.now().isoformat()}

Total Tests: {len(results)}
✅ Passed: {sum(1 for r in results if r["status"] == "PASSED")}
❌ Failed: {sum(1 for r in results if r["status"] == "FAILED")}
⚠️  Not Found: {sum(1 for r in results if r["status"] == "NOT_FOUND")}

{"=" * 80}
Detailed Results:
{"-" * 80}
"""
for r in results:
    icon = "✅" if r["status"] == "PASSED" else "❌" if r["status"] == "FAILED" else "⚠️"
    summary_content += f"{icon} {r['name']} - {r['status']} (exit: {r['exit']})\n"
    if "file" in r:
        summary_content += f"   Output: {r['file']}\n"
    summary_content += "\n"

summary_file = REPORTS_DIR / "test_run_summary.txt"
summary_file.write_text(summary_content, encoding="utf-8")

print(f"\n{'=' * 80}")
print(f"Summary saved to: {summary_file.name}")
print(f"All outputs saved to: {REPORTS_DIR}")
print(f"{'=' * 80}")

# Verify files were created
files = list(REPORTS_DIR.glob("*_output.txt"))
print(f"\nCreated {len(files)} output files:")
for f in sorted(files):
    print(f"  - {f.name}")

sys.exit(0)
