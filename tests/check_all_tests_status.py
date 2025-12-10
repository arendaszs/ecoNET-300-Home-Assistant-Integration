#!/usr/bin/env python3
"""Check status of all tests."""

from datetime import datetime
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).parent
REPORTS = BASE / "test_reports"
REPORTS.mkdir(parents=True, exist_ok=True)

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

print("=" * 80)
print("Running All Tests - Checking Integration Status")
print("=" * 80)

results = []
for i, (name, ttype) in enumerate(TESTS, 1):
    print(f"[{i}/{len(TESTS)}] {name}...", end=" ", flush=True)
    path = BASE / name
    if not path.exists():
        print("⚠️  NOT FOUND")
        results.append((name, "NOT_FOUND", -1))
        continue

    out_file = REPORTS / f"{path.stem}_output.txt"
    cmd = (
        [sys.executable, "-m", "pytest", str(path), "-v", "--tb=short"]
        if ttype == "pytest"
        else [sys.executable, str(path)]
    )

    res = subprocess.run(
        cmd, check=False, capture_output=True, text=True, cwd=BASE.parent
    )

    content = f"""Test: {name}
Type: {ttype}
Timestamp: {datetime.now().isoformat()}
Exit Code: {res.returncode}
{"=" * 80}

STDOUT:
{res.stdout}

STDERR:
{res.stderr}
"""
    out_file.write_text(content, encoding="utf-8")

    status = "PASSED" if res.returncode == 0 else "FAILED"
    icon = "✅" if status == "PASSED" else "❌"
    print(f"{icon} {status}")
    results.append((name, status, res.returncode))

# Create summary
passed = sum(1 for _, s, _ in results if s == "PASSED")
failed = sum(1 for _, s, _ in results if s == "FAILED")
not_found = sum(1 for _, s, _ in results if s == "NOT_FOUND")

summary = f"""Test Run Summary
{"=" * 80}
Timestamp: {datetime.now().isoformat()}

Total Tests: {len(results)}
✅ Passed: {passed}
❌ Failed: {failed}
⚠️  Not Found: {not_found}

{"=" * 80}
Detailed Results:
{"-" * 80}

"""
for name, status, code in results:
    icon = "✅" if status == "PASSED" else "❌" if status == "FAILED" else "⚠️"
    summary += f"{icon} {name} - {status} (exit: {code})\n"

summary_file = REPORTS / "test_run_summary.txt"
summary_file.write_text(summary, encoding="utf-8")

print(f"\n{'=' * 80}")
print("SUMMARY")
print(f"{'=' * 80}")
print(f"✅ Passed: {passed}")
print(f"❌ Failed: {failed}")
if not_found > 0:
    print(f"⚠️  Not Found: {not_found}")
print(f"\n📄 Summary saved to: {summary_file}")
print(f"{'=' * 80}")

if failed == 0:
    print("\n🎉 ALL TESTS PASSED! Integration is working correctly.")
    sys.exit(0)
else:
    print(f"\n⚠️  {failed} test(s) failed. Check individual output files for details.")
    sys.exit(1)
