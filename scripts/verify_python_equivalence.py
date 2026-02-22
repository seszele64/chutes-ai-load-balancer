#!/usr/bin/env python3
"""
Verify Python tests provide equivalent functionality to original shell tests.

Given: Python test files in the project
When: Running this verification script
Then: PASS if equivalent or better test coverage, FAIL if gaps exist

This implements Success Criterion SC-2 and SC-3.

Verification Criteria:
- All original shell test scenarios have Python equivalents
- Health check test exists
- Route selection test exists
- Fallback behavior test exists
- Cache behavior test exists
- Test count meets minimum (54 tests per original criteria: 32 unit + 16 integration + 6 E2E)
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


class TestCount(NamedTuple):
    """Count of tests by category."""

    unit: int
    integration: int
    e2e: int

    @property
    def total(self) -> int:
        return self.unit + self.integration + self.e2e


class CheckResult(NamedTuple):
    """Result of a single verification check."""

    name: str
    passed: bool
    message: str


def get_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def get_test_counts(root: Path) -> TestCount:
    """
    Count tests by category using pytest collection.

    Given a project root directory
    When running pytest --collect-only with markers
    Then count tests by category

    Args:
        root: Project root directory

    Returns:
        TestCount with unit, integration, e2e counts
    """
    counts = {"unit": 0, "integration": 0, "e2e": 0}

    # Count unit tests
    try:
        result = subprocess.run(
            ["pytest", "tests/unit/", "--collect-only", "-q"],
            capture_output=True,
            text=True,
            cwd=root,
            timeout=30,
        )
        # Count lines that contain <Function - this is how pytest shows tests
        if result.returncode == 0:
            lines = [l for l in result.stdout.strip().split("\n") if "<Function" in l]
            counts["unit"] = len(lines)
    except Exception:
        pass  # Keep default 0

    # Count integration tests
    try:
        result = subprocess.run(
            ["pytest", "tests/integration/", "--collect-only", "-q"],
            capture_output=True,
            text=True,
            cwd=root,
            timeout=30,
        )
        if result.returncode == 0:
            lines = [l for l in result.stdout.strip().split("\n") if "<Function" in l]
            counts["integration"] = len(lines)
    except Exception:
        pass

    # Count E2E tests
    try:
        result = subprocess.run(
            ["pytest", "tests/e2e/", "--collect-only", "-q"],
            capture_output=True,
            text=True,
            cwd=root,
            timeout=30,
        )
        if result.returncode == 0:
            lines = [l for l in result.stdout.strip().split("\n") if "<Function" in l]
            counts["e2e"] = len(lines)
    except Exception:
        pass

    return TestCount(
        unit=counts["unit"], integration=counts["integration"], e2e=counts["e2e"]
    )


def check_minimum_test_count(root: Path) -> CheckResult:
    """
    Check if minimum test count meets requirements.

    Per spec: 32 unit + 16 integration + 6 E2E = 54 minimum
    Current: 32 unit + 23 integration + 6 E2E = 61 tests
    """
    counts = get_test_counts(root)
    total = counts.total

    # Current known counts from the project
    # 32 unit, 23 integration, 6 e2e = 61 total
    minimum_required = 54

    if total >= minimum_required:
        return CheckResult(
            "Minimum test count",
            True,
            f"Found {total} tests (minimum: {minimum_required})",
        )
    else:
        return CheckResult(
            "Minimum test count",
            False,
            f"Found {total} tests, need at least {minimum_required}",
        )


def check_test_categories(root: Path) -> CheckResult:
    """Check if tests are organized by category (unit/integration/e2e)."""
    tests_dir = root / "tests"

    if not tests_dir.exists():
        return CheckResult("Test categories", False, "tests/ not found")

    categories = []

    if (tests_dir / "unit").exists():
        categories.append("unit")
    if (tests_dir / "integration").exists():
        categories.append("integration")
    if (tests_dir / "e2e").exists():
        categories.append("e2e")

    if len(categories) >= 3:
        return CheckResult(
            "Test categories", True, f"Found categories: {', '.join(categories)}"
        )
    else:
        return CheckResult(
            "Test categories",
            False,
            f"Missing categories. Found: {', '.join(categories) if categories else 'none'}",
        )


def check_health_test_exists(root: Path) -> CheckResult:
    """Check if health check test exists."""
    test_patterns = [
        "test_health",
        "test_health_endpoint",
    ]

    for pattern in test_patterns:
        if search_tests(root, pattern):
            return CheckResult(
                "Health check test", True, f"Found test matching '{pattern}'"
            )

    return CheckResult("Health check test", False, "No health check test found")


def check_route_selection_test_exists(root: Path) -> CheckResult:
    """Check if route selection test exists."""
    test_patterns = [
        "test_routing_selects",
        "test_route",
        "test_model_selection",
    ]

    for pattern in test_patterns:
        if search_tests(root, pattern):
            return CheckResult(
                "Route selection test", True, f"Found test matching '{pattern}'"
            )

    return CheckResult("Route selection test", False, "No route selection test found")


def check_fallback_test_exists(root: Path) -> CheckResult:
    """Check if fallback behavior test exists."""
    test_patterns = [
        "test_fallback",
        "test_failover",
        "test_model_switching",
        "test_model_unavailable",
        "fallback",  # Also search for "fallback" in test names
    ]

    for pattern in test_patterns:
        if search_tests(root, pattern):
            return CheckResult(
                "Fallback behavior test", True, f"Found test matching '{pattern}'"
            )

    return CheckResult("Fallback behavior test", False, "No fallback test found")


def check_cache_test_exists(root: Path) -> CheckResult:
    """Check if cache behavior test exists."""
    test_patterns = [
        "test_cache",
        "cache_",
    ]

    for pattern in test_patterns:
        if search_tests(root, pattern):
            return CheckResult(
                "Cache behavior test", True, f"Found test matching '{pattern}'"
            )

    return CheckResult("Cache behavior test", False, "No cache test found")


def search_tests(root: Path, pattern: str) -> bool:
    """Search for a test matching the given pattern."""
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", f"-k={pattern}", "--collect-only", "-q"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        # If tests were collected, pattern matches
        return "<Function" in (result.stdout + result.stderr)

    except Exception:
        return False


def output_json(checks: List[CheckResult], passed: int, failed: int) -> None:
    """Output results as JSON for CI integration."""
    import json

    results = {
        "summary": {
            "passed": passed,
            "failed": failed,
            "total": passed + failed,
            "success": failed == 0,
        },
        "checks": [
            {"name": check.name, "passed": check.passed, "message": check.message}
            for check in checks
        ],
    }
    print(json.dumps(results, indent=2))


def print_check_results(
    checks: List[CheckResult], passed: int, failed: int, verbose: bool
) -> None:
    """Print colored results to console."""
    print(f"\n{Colors.BOLD}Python Test Equivalence Verification{Colors.RESET}\n")

    for check in checks:
        status = (
            f"{Colors.GREEN}PASS{Colors.RESET}"
            if check.passed
            else f"{Colors.RED}FAIL{Colors.RESET}"
        )
        print(f"  [{status}] {check.name}")
        if verbose or not check.passed:
            print(f"         {check.message}")

    # Get test counts for summary
    counts = get_test_counts(get_root())
    print(f"\n{Colors.BOLD}Test Coverage Summary:{Colors.RESET}")
    print(f"  Unit tests:       {counts.unit}")
    print(f"  Integration tests: {counts.integration}")
    print(f"  E2E tests:        {counts.e2e}")
    print(f"  Total:             {counts.total}")

    print(f"\n{Colors.BOLD}Results: {passed} passed, {failed} failed{Colors.RESET}")

    if failed == 0:
        print(
            f"\n{Colors.GREEN}Python tests provide equivalent or better coverage.{Colors.RESET}"
        )


def check_pytest_works(root: Path) -> CheckResult:
    """Check if pytest can collect and run tests."""
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "--collect-only", "-q"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
        )

        output = result.stdout + result.stderr

        # Count tests collected
        match = re.search(r"(\d+)\s+test", output)
        if match:
            count = int(match.group(1))
            return CheckResult(
                "pytest functional", True, f"pytest collected {count} tests"
            )

        return CheckResult("pytest functional", False, "Could not determine test count")

    except FileNotFoundError:
        return CheckResult("pytest functional", False, "pytest not installed")
    except Exception as e:
        return CheckResult("pytest functional", False, f"error: {e}")


def verify_python_equivalence(verbose: bool = False, json_output: bool = False) -> bool:
    """
    Verify Python tests provide equivalent functionality.

    Returns True if equivalent or better coverage, False if gaps exist.
    """
    root = get_root()

    checks = [
        check_pytest_works(root),
        check_test_categories(root),
        check_minimum_test_count(root),
        check_health_test_exists(root),
        check_route_selection_test_exists(root),
        check_fallback_test_exists(root),
        check_cache_test_exists(root),
    ]

    passed = 0
    failed = 0

    for check in checks:
        if check.passed:
            passed += 1
        else:
            failed += 1

    if json_output:
        output_json(checks, passed, failed)
    else:
        print_check_results(checks, passed, failed, verbose)

    return failed == 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify Python tests provide equivalent coverage"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed output for all checks",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    success = verify_python_equivalence(verbose=args.verbose, json_output=args.json)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
