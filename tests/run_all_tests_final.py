#!/usr/bin/env python3
"""Final comprehensive test runner."""

from datetime import datetime
from pathlib import Path
import subprocess
import sys

BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "test_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

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

results = []
for test_name, test_type in TESTS:
    test_path = BASE_DIR / test_name
    if not test_path.exists():
        results.append({"name": test_name, "status": "NOT_FOUND", "exit": -1})
        continue

    output_file = REPORTS_DIR / f"{test_path.stem}_output.txt"

    if test_type == "pytest":
        cmd = [sys.executable, "-m", "pytest", str(test_path), "-v", "--tb=short"]
    else:
        cmd = [sys.executable, str(test_path)]

    result = subprocess.run(
        cmd, check=False, capture_output=True, text=True, cwd=BASE_DIR.parent
    )

    content = f"Test: {test_name}\nType: {test_type}\nTimestamp: {datetime.now().isoformat()}\nExit: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n"
    output_file.write_text(content, encoding="utf-8")

    results.append(
        {
            "name": test_name,
            "status": "PASSED" if result.returncode == 0 else "FAILED",
            "exit": result.returncode,
            "file": output_file.name,
        }
    )

# Create summary
summary = f"""Test Run Summary
{"=" * 80}
Timestamp: {datetime.now().isoformat()}

Total: {len(results)}
✅ Passed: {sum(1 for r in results if r["status"] == "PASSED")}
❌ Failed: {sum(1 for r in results if r["status"] == "FAILED")}
⚠️  Not Found: {sum(1 for r in results if r["status"] == "NOT_FOUND")}

{"=" * 80}
Results:
{"-" * 80}
"""
for r in results:
    icon = "✅" if r["status"] == "PASSED" else "❌" if r["status"] == "FAILED" else "⚠️"
    summary += f"{icon} {r['name']} - {r['status']} (exit: {r['exit']})\n"
    if "file" in r:
        summary += f"   Output: {r['file']}\n"
    summary += "\n"

(REPORTS_DIR / "test_run_summary.txt").write_text(summary, encoding="utf-8")

# List all files
all_files = sorted(REPORTS_DIR.glob("*.txt"))
file_list = f"\nFiles in {REPORTS_DIR}:\n"
for f in all_files:
    file_list += f"  - {f.name} ({f.stat().st_size} bytes)\n"

(REPORTS_DIR / "file_list.txt").write_text(file_list, encoding="utf-8")

print("All tests completed!")
print(f"Summary: {REPORTS_DIR / 'test_run_summary.txt'}")
print(f"File list: {REPORTS_DIR / 'file_list.txt'}")
