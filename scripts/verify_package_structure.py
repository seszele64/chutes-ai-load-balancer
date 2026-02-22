#!/usr/bin/env python3
"""
Verify package structure is correct for the modular litellm_proxy package.

Given: Project root directory with expected structure
When: Running this verification script
Then: PASS if all required files/directories exist, FAIL otherwise

Verification Criteria:
- src/litellm_proxy/ directory exists
- src/litellm_proxy/__init__.py exists and exports all modules
- src/litellm_proxy/routing/strategy.py exists with ChutesUtilizationRouting class
- src/litellm_proxy/cache/store.py exists with UtilizationCache class
- src/litellm_proxy/api/client.py exists with ChutesAPIClient class
- src/litellm_proxy/config/loader.py exists with ConfigLoader class
- src/litellm_proxy/exceptions.py exists with 7 custom exceptions
- Backwards compatibility: chutes_routing.py re-exports from new modules
"""

import argparse
import ast
import sys
from pathlib import Path
from typing import List, NamedTuple


class CheckResult(NamedTuple):
    """Result of a single verification check."""

    name: str
    passed: bool
    message: str


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def get_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def check_directory_exists(root: Path, rel_path: str) -> CheckResult:
    """Check if a directory exists."""
    path = root / rel_path
    if path.exists() and path.is_dir():
        return CheckResult(f"Directory: {rel_path}", True, "exists")
    return CheckResult(f"Directory: {rel_path}", False, f"not found at {path}")


def check_file_exists(root: Path, rel_path: str) -> CheckResult:
    """Check if a file exists."""
    path = root / rel_path
    if path.exists() and path.is_file():
        return CheckResult(f"File: {rel_path}", True, "exists")
    return CheckResult(f"File: {rel_path}", False, f"not found at {path}")


def check_class_exists(root: Path, rel_path: str, class_name: str) -> CheckResult:
    """
    Check if a class exists in a Python file using AST parsing.

    Given a Python file path and class name
    When parsing the file with AST
    Then verify the class definition exists

    Args:
        root: Project root directory
        rel_path: Relative path to Python file
        class_name: Name of class to find

    Returns:
        CheckResult indicating success/failure
    """
    path = root / rel_path
    if not path.exists():
        return CheckResult(f"Class {class_name}", False, f"file {rel_path} not found")

    try:
        content = path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return CheckResult(f"Class {class_name} in {rel_path}", True, "found")

        return CheckResult(
            f"Class {class_name} in {rel_path}", False, "class not found"
        )
    except SyntaxError as e:
        return CheckResult(
            f"Class {class_name} in {rel_path}", False, f"syntax error: {e}"
        )
    except Exception as e:
        return CheckResult(f"Class {class_name} in {rel_path}", False, f"error: {e}")


def check_init_exports(root: Path) -> CheckResult:
    """Check if __init__.py exports all required modules."""
    init_path = root / "src/litellm_proxy/__init__.py"

    if not init_path.exists():
        return CheckResult("__init__.py exports", False, "file not found")

    try:
        content = init_path.read_text()

        required_exports = [
            "ChutesUtilizationRouting",
            "UtilizationCache",
            "ChutesAPIClient",
            "ConfigLoader",
        ]

        missing = [exp for exp in required_exports if exp not in content]

        if missing:
            return CheckResult(
                "__init__.py exports", False, f"missing exports: {', '.join(missing)}"
            )

        return CheckResult("__init__.py exports", True, "all required exports found")

    except Exception as e:
        return CheckResult("__init__.py exports", False, f"error: {e}")


def check_exceptions_count(root: Path) -> CheckResult:
    """Count exception classes using AST parsing."""
    exc_path = root / "src/litellm_proxy/exceptions.py"

    if not exc_path.exists():
        return CheckResult("exceptions.py count", False, "file not found")

    try:
        content = exc_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        exceptions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if it inherits from Exception or another Error class
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id.endswith(
                        ("Error", "Exception")
                    ):
                        exceptions.append(node.name)
                        break

        if len(exceptions) >= 7:
            return CheckResult(
                "exceptions.py count", True, f"found {len(exceptions)} exceptions"
            )
        else:
            return CheckResult(
                "exceptions.py count",
                False,
                f"found {len(exceptions)}, expected at least 7",
            )

    except Exception as e:
        return CheckResult("exceptions.py count", False, f"error: {e}")


def check_backwards_compatibility(root: Path) -> CheckResult:
    """Check if chutes_routing.py re-exports from new modules."""
    routing_path = root / "chutes_routing.py"

    if not routing_path.exists():
        return CheckResult(
            "Backwards compatibility", False, "chutes_routing.py not found"
        )

    try:
        content = routing_path.read_text()

        # Check for re-exports from litellm_proxy
        if "from litellm_proxy" in content:
            return CheckResult(
                "Backwards compatibility", True, "re-exports from litellm_proxy"
            )
        else:
            return CheckResult(
                "Backwards compatibility", False, "does not re-export from new modules"
            )

    except Exception as e:
        return CheckResult("Backwards compatibility", False, f"error: {e}")


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
    print(f"\n{Colors.BOLD}Package Structure Verification{Colors.RESET}\n")

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


def verify_package_structure(verbose: bool = False, json_output: bool = False) -> bool:
    """
    Verify the package structure is correct.

    Returns True if all checks pass, False otherwise.
    """
    root = get_root()

    checks = [
        # Directory structure
        check_directory_exists(root, "src"),
        check_directory_exists(root, "src/litellm_proxy"),
        check_directory_exists(root, "src/litellm_proxy/routing"),
        check_directory_exists(root, "src/litellm_proxy/cache"),
        check_directory_exists(root, "src/litellm_proxy/api"),
        check_directory_exists(root, "src/litellm_proxy/config"),
        # Required files
        check_file_exists(root, "src/litellm_proxy/__init__.py"),
        check_file_exists(root, "src/litellm_proxy/exceptions.py"),
        check_file_exists(root, "src/litellm_proxy/routing/strategy.py"),
        check_file_exists(root, "src/litellm_proxy/cache/store.py"),
        check_file_exists(root, "src/litellm_proxy/api/client.py"),
        check_file_exists(root, "src/litellm_proxy/config/loader.py"),
        check_file_exists(root, "chutes_routing.py"),
        # Class existence
        check_class_exists(
            root, "src/litellm_proxy/routing/strategy.py", "ChutesUtilizationRouting"
        ),
        check_class_exists(
            root, "src/litellm_proxy/cache/store.py", "UtilizationCache"
        ),
        check_class_exists(root, "src/litellm_proxy/api/client.py", "ChutesAPIClient"),
        check_class_exists(root, "src/litellm_proxy/config/loader.py", "ConfigLoader"),
        # __init__.py exports
        check_init_exports(root),
        # Exceptions count
        check_exceptions_count(root),
        # Backwards compatibility
        check_backwards_compatibility(root),
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
        description="Verify package structure for litellm_proxy"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed output for all checks",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    success = verify_package_structure(verbose=args.verbose, json_output=args.json)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
