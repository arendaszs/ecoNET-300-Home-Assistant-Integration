#!/usr/bin/env python3
"""Run all tests and generate comprehensive report."""

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
print("ECO.NET300 INTEGRATION TEST SUITE")
print("=" * 80)
print(f"Running {len(TESTS)} test files...")
print(f"Reports will be saved to: {REPORTS}")
print("=" * 80)

results = []
for i, (name, ttype) in enumerate(TESTS, 1):
    print(f"\n[{i}/{len(TESTS)}] {name} ({ttype})...", end=" ", flush=True)
    path = BASE / name
    if not path.exists():
        print("⚠️  NOT FOUND")
        results.append({"name": name, "status": "NOT_FOUND", "exit": -1})
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
    results.append(
        {"name": name, "status": status, "exit": res.returncode, "file": out_file.name}
    )

# Generate summary
passed = sum(1 for r in results if r["status"] == "PASSED")
failed = sum(1 for r in results if r["status"] == "FAILED")
not_found = sum(1 for r in results if r["status"] == "NOT_FOUND")

summary = f"""ECO.NET300 INTEGRATION TEST REPORT
{"=" * 80}
Generated: {datetime.now().isoformat()}

OVERALL STATUS: {"✅ ALL TESTS PASSED" if failed == 0 else f"❌ {failed} TEST(S) FAILED"}

SUMMARY:
  Total Tests: {len(results)}
  ✅ Passed: {passed}
  ❌ Failed: {failed}
  ⚠️  Not Found: {not_found}

{"=" * 80}
DETAILED RESULTS:
{"-" * 80}

"""
for r in results:
    icon = "✅" if r["status"] == "PASSED" else "❌" if r["status"] == "FAILED" else "⚠️"
    summary += f"{icon} {r['name']} - {r['status']} (exit: {r['exit']})\n"
    if "file" in r:
        summary += f"   Output: {r['file']}\n"
    summary += "\n"

summary += f"""
{"=" * 80}
CONCLUSION:
"""
if failed == 0:
    summary += "✅ Integration passes all tests! The software is working correctly.\n"
else:
    summary += f"❌ Integration has {failed} failing test(s). Check output files for details.\n"

summary_file = REPORTS / "INTEGRATION_STATUS_REPORT.txt"
summary_file.write_text(summary, encoding="utf-8")

print(f"\n{'=' * 80}")
print("FINAL SUMMARY")
print(f"{'=' * 80}")
print(f"✅ Passed: {passed}")
print(f"❌ Failed: {failed}")
if not_found > 0:
    print(f"⚠️  Not Found: {not_found}")
print(f"\n📄 Full report: {summary_file}")
print(f"📁 All outputs: {REPORTS}")
print(f"{'=' * 80}")

if failed == 0:
    print("\n🎉 SUCCESS: All tests passed! Integration is working correctly.")
else:
    print(f"\n⚠️  WARNING: {failed} test(s) failed. Check output files for details.")

sys.exit(0 if failed == 0 else 1)
