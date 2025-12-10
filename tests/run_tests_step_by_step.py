#!/usr/bin/env python3
"""Run all tests step by step and save outputs to test_reports directory."""

from datetime import datetime
from pathlib import Path
import subprocess
import sys

# Define paths
BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "test_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Test files to run in order
TEST_FILES = [
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

SUMMARY_FILE = REPORTS_DIR / "test_run_summary.txt"


def run_test(test_file: str, test_type: str) -> dict:
    """Run a single test file."""
    test_path = BASE_DIR / test_file
    if not test_path.exists():
        return {
            "file": test_file,
            "status": "NOT_FOUND",
            "exit_code": -1,
        }

    output_file = REPORTS_DIR / f"{test_path.stem}_output.txt"

    if test_type == "pytest":
        cmd = [sys.executable, "-m", "pytest", str(test_path), "-v", "--tb=short"]
    else:
        cmd = [sys.executable, str(test_path)]

    print(f"\n{'=' * 80}")
    print(f"Running: {test_file} ({test_type})")
    print(f"{'=' * 80}")

    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        cwd=BASE_DIR.parent,
    )

    # Save output
    with output_file.open("w", encoding="utf-8") as f:
        f.write(f"Test: {test_file}\n")
        f.write(f"Type: {test_type}\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write("=" * 80 + "\n\n")
        f.write("STDOUT:\n")
        f.write(result.stdout)
        f.write("\n\nSTDERR:\n")
        f.write(result.stderr)
        f.write(f"\n\nExit code: {result.returncode}\n")

    status = "PASSED" if result.returncode == 0 else "FAILED"
    print(f"Status: {'✅ PASSED' if result.returncode == 0 else '❌ FAILED'}")
    print(f"Output saved to: {output_file.name}")

    return {
        "file": test_file,
        "type": test_type,
        "status": status,
        "exit_code": result.returncode,
        "output_file": output_file.name,
    }


def main():
    """Run all tests step by step."""
    print("=" * 80)
    print("Running All Tests Step by Step")
    print(f"Reports directory: {REPORTS_DIR}")
    print("=" * 80)

    results = []

    for test_file, test_type in TEST_FILES:
        result = run_test(test_file, test_type)
        results.append(result)

    # Generate summary
    with SUMMARY_FILE.open("w", encoding="utf-8") as f:
        f.write("Test Run Summary\n")
        f.write("=" * 80 + "\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n\n")

        passed = sum(1 for r in results if r["status"] == "PASSED")
        failed = sum(1 for r in results if r["status"] == "FAILED")
        not_found = sum(1 for r in results if r["status"] == "NOT_FOUND")

        f.write(f"Total tests: {len(results)}\n")
        f.write(f"✅ Passed: {passed}\n")
        f.write(f"❌ Failed: {failed}\n")
        if not_found > 0:
            f.write(f"⚠️  Not found: {not_found}\n")
        f.write("\n" + "-" * 80 + "\n\n")

        for result in results:
            status_icon = (
                "✅"
                if result["status"] == "PASSED"
                else "❌"
                if result["status"] == "FAILED"
                else "⚠️"
            )
            f.write(
                f"{status_icon} {result['file']} ({result.get('type', 'unknown')})\n"
            )
            f.write(f"   Exit code: {result['exit_code']}\n")
            if "output_file" in result:
                f.write(f"   Output: {result['output_file']}\n")
            f.write("\n")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    passed = sum(1 for r in results if r["status"] == "PASSED")
    failed = sum(1 for r in results if r["status"] == "FAILED")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📄 Summary: {SUMMARY_FILE.name}")
    print("=" * 80)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
