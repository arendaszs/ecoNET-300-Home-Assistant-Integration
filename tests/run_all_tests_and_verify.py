#!/usr/bin/env python3
"""Run all tests and verify outputs are saved."""

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
print(f"Reports Directory: {REPORTS}")
print("=" * 80)

results = []
for i, (name, ttype) in enumerate(TESTS, 1):
    print(f"\n[{i}/{len(TESTS)}] {name}...", end=" ")
    path = BASE / name
    if not path.exists():
        print("⚠️  NOT FOUND")
        results.append((name, "NOT_FOUND", -1, None))
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
    results.append((name, status, res.returncode, out_file.name))

# Create summary
summary_lines = [
    "Test Run Summary",
    "=" * 80,
    f"Timestamp: {datetime.now().isoformat()}",
    "",
    f"Total Tests: {len(results)}",
    f"✅ Passed: {sum(1 for _, s, _, _ in results if s == 'PASSED')}",
    f"❌ Failed: {sum(1 for _, s, _, _ in results if s == 'FAILED')}",
    f"⚠️  Not Found: {sum(1 for _, s, _, _ in results if s == 'NOT_FOUND')}",
    "",
    "=" * 80,
    "Detailed Results:",
    "-" * 80,
    "",
]

for name, status, code, out_file in results:
    icon = "✅" if status == "PASSED" else "❌" if status == "FAILED" else "⚠️"
    summary_lines.append(f"{icon} {name} - {status} (exit: {code})")
    if out_file:
        summary_lines.append(f"   Output: {out_file}")
    summary_lines.append("")

summary_file = REPORTS / "test_run_summary.txt"
summary_file.write_text("\n".join(summary_lines), encoding="utf-8")

# Verify files
all_files = sorted(REPORTS.glob("*.txt"))
print(f"\n{'=' * 80}")
print(f"✅ Passed: {sum(1 for _, s, _, _ in results if s == 'PASSED')}")
print(f"❌ Failed: {sum(1 for _, s, _, _ in results if s == 'FAILED')}")
print(f"📄 Summary: {summary_file.name}")
print(f"📁 Total files in reports: {len(all_files)}")
print("=" * 80)
