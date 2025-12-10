#!/usr/bin/env python3
"""Generate comprehensive test status report."""

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

results = []
for name, ttype in TESTS:
    path = BASE / name
    if not path.exists():
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

    content = f"Test: {name}\nType: {ttype}\nTime: {datetime.now().isoformat()}\nExit: {res.returncode}\n\nSTDOUT:\n{res.stdout}\n\nSTDERR:\n{res.stderr}\n"
    out_file.write_text(content, encoding="utf-8")

    results.append(
        {
            "name": name,
            "status": "PASSED" if res.returncode == 0 else "FAILED",
            "exit": res.returncode,
            "file": out_file.name,
        }
    )

# Generate report
passed = sum(1 for r in results if r["status"] == "PASSED")
failed = sum(1 for r in results if r["status"] == "FAILED")
not_found = sum(1 for r in results if r["status"] == "NOT_FOUND")

report = f"""INTEGRATION TEST STATUS REPORT
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
    report += f"{icon} {r['name']} - {r['status']} (exit code: {r['exit']})\n"
    if "file" in r:
        report += f"   Output file: {r['file']}\n"
    report += "\n"

report += f"""
{"=" * 80}
CONCLUSION:
"""
if failed == 0:
    report += "✅ Integration passes all tests! The software is working correctly.\n"
else:
    report += f"❌ Integration has {failed} failing test(s). Please check the output files for details.\n"

report_file = REPORTS / "INTEGRATION_STATUS_REPORT.txt"
report_file.write_text(report, encoding="utf-8")

print(report)
print(f"\n📄 Full report saved to: {report_file}")

sys.exit(0 if failed == 0 else 1)
