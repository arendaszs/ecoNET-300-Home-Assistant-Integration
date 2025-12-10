#!/usr/bin/env python3
"""Verify test_reports directory and run all tests."""

from datetime import datetime
from pathlib import Path
import subprocess
import sys

BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "test_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Verify directory exists
test_file = REPORTS_DIR / "verification.txt"
with test_file.open("w", encoding="utf-8") as f:
    f.write(f"Verification test - {datetime.now().isoformat()}\n")
    f.write(f"Reports directory: {REPORTS_DIR}\n")
    f.write("Directory created successfully!\n")

print(f"✅ Verification file created: {test_file}")
print(f"📁 Reports directory: {REPORTS_DIR}")

# Test files
tests = [
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

print(f"\nRunning {len(tests)} tests...\n")

results = []
for i, (test_file, test_type) in enumerate(tests, 1):
    print(f"[{i}/{len(tests)}] Running {test_file}...", end=" ")

    test_path = BASE_DIR / test_file
    if not test_path.exists():
        print("❌ NOT FOUND")
        results.append((test_file, "NOT_FOUND", -1))
        continue

    output_file = REPORTS_DIR / f"{test_path.stem}_output.txt"

    if test_type == "pytest":
        cmd = [sys.executable, "-m", "pytest", str(test_path), "-v", "--tb=short"]
    else:
        cmd = [sys.executable, str(test_path)]

    result = subprocess.run(
        cmd, check=False, capture_output=True, text=True, cwd=BASE_DIR.parent
    )

    with output_file.open("w", encoding="utf-8") as f:
        f.write(f"Test: {test_file}\nType: {test_type}\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write("=" * 80 + "\n\n")
        f.write("STDOUT:\n" + result.stdout + "\n\n")
        f.write("STDERR:\n" + result.stderr + "\n\n")
        f.write(f"Exit code: {result.returncode}\n")

    status = "✅ PASSED" if result.returncode == 0 else "❌ FAILED"
    print(status)
    results.append(
        (test_file, "PASSED" if result.returncode == 0 else "FAILED", result.returncode)
    )

# Create summary
summary_file = REPORTS_DIR / "test_run_summary.txt"
with summary_file.open("w", encoding="utf-8") as f:
    f.write("Test Run Summary\n" + "=" * 80 + "\n")
    f.write(f"Timestamp: {datetime.now().isoformat()}\n\n")

    passed = sum(1 for _, s, _ in results if s == "PASSED")
    failed = sum(1 for _, s, _ in results if s == "FAILED")
    not_found = sum(1 for _, s, _ in results if s == "NOT_FOUND")

    f.write(f"Total: {len(results)}\n")
    f.write(f"✅ Passed: {passed}\n")
    f.write(f"❌ Failed: {failed}\n")
    if not_found > 0:
        f.write(f"⚠️  Not found: {not_found}\n")
    f.write("\n" + "-" * 80 + "\n\n")

    for test_file, status, exit_code in results:
        icon = "✅" if status == "PASSED" else "❌" if status == "FAILED" else "⚠️"
        f.write(f"{icon} {test_file} - {status} (exit: {exit_code})\n")

print(f"\n{'=' * 80}")
print(f"✅ Passed: {passed}")
print(f"❌ Failed: {failed}")
print(f"📄 Summary: {summary_file.name}")
print(f"{'=' * 80}")

sys.exit(0 if failed == 0 else 1)
