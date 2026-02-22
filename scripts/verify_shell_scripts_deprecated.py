#!/usr/bin/env python3
"""
Verify shell-based testing is deprecated in favor of Python tests.

Given: Shell scripts in the project
When: Running this verification script
Then: PASS if shell tests properly deprecated, FAIL otherwise

This implements Success Criterion SC-4: Shell-based testing is deprecated.

Verification Criteria:
- scripts/test-proxy.sh exists but has deprecation warning
- scripts/run-proxy.sh still functional (needed for running proxy)
- README or documentation mentions pytest as preferred test method
- pyproject.toml has pytest configuration
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, NamedTuple


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


class CheckResult(NamedTuple):
    """Result of a single verification check."""

    name: str
    passed: bool
    message: str


def get_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def check_test_proxy_deprecated(root: Path) -> CheckResult:
    """Check if test-proxy.sh has proper deprecation warning."""
    test_script = root / "scripts/test-proxy.sh"

    if not test_script.exists():
        return CheckResult("test-proxy.sh exists", False, "file not found")

    try:
        content = test_script.read_text(encoding="utf-8").lower()

        # Look for explicit deprecation markers
        deprecation_markers = [
            "deprecated",
            "deprecation warning",
            "no longer maintained",
            "use pytest instead",
            "use python -m pytest",
            "migrated to pytest",
        ]

        found_markers = [m for m in deprecation_markers if m in content]

        if found_markers:
            return CheckResult(
                "test-proxy.sh deprecated",
                True,
                f"found deprecation markers: {', '.join(found_markers)}",
            )
        else:
            return CheckResult(
                "test-proxy.sh deprecated", False, "no clear deprecation warning found"
            )

    except Exception as e:
        return CheckResult("test-proxy.sh deprecated", False, f"error: {e}")


def check_run_proxy_exists(root: Path) -> CheckResult:
    """Check if run-proxy.sh still exists (needed for running proxy)."""
    run_script = root / "scripts/run-proxy.sh"

    if run_script.exists():
        return CheckResult("run-proxy.sh exists", True, "file found")
    else:
        return CheckResult("run-proxy.sh exists", False, "file not found")


def check_pytest_configured(root: Path) -> CheckResult:
    """Check if pyproject.toml has pytest configuration."""
    pyproject = root / "pyproject.toml"

    if not pyproject.exists():
        return CheckResult("pytest configuration", False, "pyproject.toml not found")

    try:
        content = pyproject.read_text()

        if "[tool.pytest.ini_options]" in content:
            return CheckResult(
                "pytest configuration", True, "pytest config found in pyproject.toml"
            )
        else:
            return CheckResult(
                "pytest configuration", False, "no pytest config in pyproject.toml"
            )

    except Exception as e:
        return CheckResult("pytest configuration", False, f"error: {e}")


def check_readme_mentions_pytest(root: Path) -> CheckResult:
    """Check if README mentions pytest as preferred test method."""
    readme_files = [
        root / "README.md",
        root / "RUNNING-PROXY.md",
        root / "AGENTS.md",
    ]

    for readme_path in readme_files:
        if not readme_path.exists():
            continue

        try:
            content = readme_path.read_text()

            # Check for pytest mentions
            if re.search(r"\bpytest\b", content, re.IGNORECASE):
                return CheckResult(
                    "README mentions pytest",
                    True,
                    f"pytest mentioned in {readme_path.name}",
                )

        except Exception:
            continue

    return CheckResult(
        "README mentions pytest", False, "no mention of pytest in README files"
    )


def check_tests_directory_no_shell(root: Path) -> CheckResult:
    """Check that tests/ directory has no shell scripts."""
    tests_dir = root / "tests"

    if not tests_dir.exists():
        return CheckResult("tests/ no shell scripts", False, "tests/ not found")

    shell_scripts = list(tests_dir.glob("*.sh"))
    shell_scripts.extend(list(tests_dir.glob("**/*.sh")))

    if shell_scripts:
        return CheckResult(
            "tests/ no shell scripts",
            False,
            f"found {len(shell_scripts)} shell scripts: {[s.name for s in shell_scripts]}",
        )

    return CheckResult("tests/ no shell scripts", True, "no shell scripts in tests/")


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
    print(f"\n{Colors.BOLD}Shell Script Deprecation Verification{Colors.RESET}\n")

    for check in checks:
        status = (
            f"{Colors.GREEN}PASS{Colors.RESET}"
            if check.passed
            else f"{Colors.RED}FAIL{Colors.RESET}"
        )
        print(f"  [{status}] {check.name}")
        if verbose or not check.passed:
            print(f"         {check.message}")

    print(f"\n{Colors.BOLD}Results: {passed} passed, {failed} failed{Colors.RESET}")

    # Special message based on overall status
    if failed == 0:
        print(
            f"\n{Colors.GREEN}Shell-based testing is properly deprecated.{Colors.RESET}"
        )
        print("Use Python/pytest for testing.")


def verify_shell_scripts_deprecated(
    verbose: bool = False, json_output: bool = False
) -> bool:
    """
    Verify shell scripts are properly deprecated.

    Returns True if all deprecation checks pass, False otherwise.
    """
    root = get_root()

    checks = [
        check_test_proxy_deprecated(root),
        check_run_proxy_exists(root),
        check_pytest_configured(root),
        check_readme_mentions_pytest(root),
        check_tests_directory_no_shell(root),
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
    parser = argparse.ArgumentParser(description="Verify shell scripts are deprecated")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed output for all checks",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    success = verify_shell_scripts_deprecated(
        verbose=args.verbose, json_output=args.json
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
