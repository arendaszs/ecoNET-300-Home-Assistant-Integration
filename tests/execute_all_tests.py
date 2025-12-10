#!/usr/bin/env python3
"""Execute all tests step by step."""

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
print("Running All Tests Step by Step")
print(f"Reports: {REPORTS}")
print("=" * 80)

results = []
for i, (name, ttype) in enumerate(TESTS, 1):
    print(f"\n[{i}/{len(TESTS)}] {name} ({ttype})...")
    path = BASE / name
    if not path.exists():
        print("  ⚠️  NOT FOUND")
        results.append((name, "NOT_FOUND", -1))
        continue

    out_file = REPORTS / f"{path.stem}_output.txt"

    cmd = (
        [sys.executable, "-m", "pytest", str(path), "-v"]
        if ttype == "pytest"
        else [sys.executable, str(path)]
    )
    res = subprocess.run(
        cmd, check=False, capture_output=True, text=True, cwd=BASE.parent
    )

    txt = f"Test: {name}\nType: {ttype}\nTime: {datetime.now().isoformat()}\nExit: {res.returncode}\n\nSTDOUT:\n{res.stdout}\n\nSTDERR:\n{res.stderr}\n"
    out_file.write_text(txt, encoding="utf-8")

    status = "PASSED" if res.returncode == 0 else "FAILED"
    icon = "✅" if status == "PASSED" else "❌"
    print(f"  {icon} {status}")
    results.append((name, status, res.returncode))

# Summary
summary = f"Test Run Summary\n{'=' * 80}\nTime: {datetime.now().isoformat()}\n\n"
passed = sum(1 for _, s, _ in results if s == "PASSED")
failed = sum(1 for _, s, _ in results if s == "FAILED")
summary += f"Total: {len(results)}\n✅ Passed: {passed}\n❌ Failed: {failed}\n\n"
for name, status, code in results:
    summary += f"{'✅' if status == 'PASSED' else '❌'} {name} - {status} ({code})\n"

(REPORTS / "summary.txt").write_text(summary, encoding="utf-8")

print(f"\n{'=' * 80}")
print(f"✅ Passed: {passed}")
print(f"❌ Failed: {failed}")
print(f"📄 Summary: {REPORTS / 'summary.txt'}")
print("=" * 80)
