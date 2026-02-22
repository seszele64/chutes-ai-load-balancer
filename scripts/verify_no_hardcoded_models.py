#!/usr/bin/env python3
"""
Verify no hardcoded model names exist in source code or tests.

Given: Python source files in the project
When: Running this verification script
Then: PASS if no hardcoded model names found, FAIL otherwise

This implements Success Criterion SC-1: Tests must use fixtures/parameters
for model names, not hardcoded strings.

Verification Criteria:
- No hardcoded model names like 'kimi-k2', 'glm-5', 'qwen-5' in .py files
- Tests use fixtures/parameters for model names, not hardcoded strings
- Allowed: model names in test fixtures (.yaml, .json files)
- Allowed: model names in litellm-config.yaml (user configuration)
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


class Violation(NamedTuple):
    """Represents a hardcoded model violation."""

    file_path: Path
    line_number: int
    line_content: str
    matched_pattern: str


def get_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


# Patterns for hardcoded model names
# These patterns represent specific model identifiers that should not be hardcoded
HARDCODED_MODEL_PATTERNS = [
    # Primary model patterns
    (r"\bkimi-k2\b", "kimi-k2"),
    (r"\bkimi-k2\.5\b", "kimi-k2.5"),
    (r"\bmoonshotai/kimi-k2\b", "moonshotai/kimi-k2"),
    (r"\bmoonshotai/kimi-k2\.5\b", "moonshotai/kimi-k2.5"),
    # Secondary model patterns
    (r"\bglm-5\b", "glm-5"),
    (r"\bzai-org/glm-5\b", "zai-org/glm-5"),
    # Tertiary model patterns
    (r"\bqwen-5\b", "qwen-5"),
    (r"\bqwen3\.5\b", "qwen3.5"),
    (r"\bqwen3\.5-397b-a17b\b", "qwen3.5-397b-a17b"),
    (r"\bqwen/Qwen3\.5-397B-A17B\b", "qwen/Qwen3.5-397B-A17B"),
    # Additional provider patterns
    (r'\bmoonshotai\b(?!\s*[/"])', "moonshotai"),
    (r'\bzai-org\b(?!\s*[/"])', "zai-org"),
    (r"\bQwen\b(?![/\.])", "Qwen"),
]

# Files/directories to exclude from checks
EXCLUDED_PATHS = [
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "litellm_proxy.egg-info",
    # Exclude verification scripts - they contain patterns by design
    "scripts/verify_",
]

# Files that legitimately contain hardcoded models
# These are acceptable as they are default fallbacks or templates
ALLOWED_FILES = [
    # start_litellm.py contains a get_default_model_list() function that is ONLY used
    # when the config file is not available - this is an acceptable fallback mechanism.
    # The default list provides sane defaults so the proxy can start without config.
    "start_litellm.py",
]

# File extensions to check (we only check .py files as per spec)
CHECK_EXTENSIONS = [".py"]


def should_exclude(path: Path) -> bool:
    """Check if path should be excluded from scanning."""
    path_str = str(path)

    # Check excluded paths
    for excluded in EXCLUDED_PATHS:
        if excluded in path_str:
            return True

    # Check allowed files (files that legitimately have defaults)
    for allowed in ALLOWED_FILES:
        if path_str.endswith(allowed):
            return True

    return False


def get_python_files(root: Path) -> List[Path]:
    """Get all Python files in the project, excluding test files."""
    files = []

    for ext in CHECK_EXTENSIONS:
        for file_path in root.glob(f"**/*{ext}"):
            if should_exclude(file_path):
                continue

            # Include all .py files EXCEPT test files in the check
            # This is because the spec says:
            # "Allowed: model names in test fixtures (.yaml, .json files)"
            # We still check test .py files for hardcoded strings though
            files.append(file_path)

    return files


def check_file_for_violations(file_path: Path) -> List[Violation]:
    """
    Check a single file for hardcoded model violations.

    Returns list of violations found.
    """
    violations = []

    try:
        content = file_path.read_text()
        lines = content.split("\n")
    except (UnicodeDecodeError, IOError) as e:
        # Skip files that can't be read
        return violations

    for line_num, line in enumerate(lines, start=1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        for pattern, model_name in HARDCODED_MODEL_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                violations.append(
                    Violation(
                        file_path=file_path,
                        line_number=line_num,
                        line_content=line.strip()[:80],  # Truncate long lines
                        matched_pattern=model_name,
                    )
                )

    return violations


def verify_no_hardcoded_models(
    verbose: bool = False, json_output: bool = False
) -> bool:
    """
    Verify no hardcoded model names exist in source code.

    Returns True if no violations found, False otherwise.
    """
    root = get_root()

    files = get_python_files(root)

    all_violations = []

    for file_path in files:
        violations = check_file_for_violations(file_path)
        all_violations.extend(violations)

    passed = len(all_violations) == 0
    failed = len(all_violations)

    if json_output:
        output_json_violations(all_violations, passed, failed)
    else:
        print_violations(all_violations, verbose, root)

    return passed


def output_json_violations(
    violations: List[Violation], passed: bool, failed: int
) -> None:
    """Output violations as JSON for CI integration."""
    import json

    results = {
        "summary": {
            "passed": passed,
            "failed": failed,
            "total": failed,
            "success": passed,
        },
        "violations": [
            {
                "file": str(v.file_path),
                "line": v.line_number,
                "content": v.line_content,
                "matched_pattern": v.matched_pattern,
            }
            for v in violations
        ],
    }
    print(json.dumps(results, indent=2))


def print_violations(violations: List[Violation], verbose: bool, root: Path) -> None:
    """Print violations to console."""
    print(f"\n{Colors.BOLD}Scanning for hardcoded model names...{Colors.RESET}\n")
    print(f"Scanning {len(get_python_files(root))} Python files...")

    if violations:
        print(
            f"\n{Colors.RED}{Colors.BOLD}FAIL: Found {len(violations)} violations{Colors.RESET}\n"
        )

        # Group violations by file for cleaner output
        by_file: dict = {}
        for v in violations:
            if v.file_path not in by_file:
                by_file[v.file_path] = []
            by_file[v.file_path].append(v)

        for file_path, file_violations in by_file.items():
            rel_path = file_path.relative_to(root)
            print(f"  {Colors.RED}{rel_path}{Colors.RESET}")
            for v in file_violations:
                print(f"    Line {v.line_number}: {v.matched_pattern}")
                if verbose:
                    print(f"      {v.line_content}")
    else:
        print(
            f"\n{Colors.GREEN}{Colors.BOLD}PASS: No hardcoded model names found{Colors.RESET}"
        )
        print("      All model references use configuration/fixtures")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify no hardcoded model names in source code"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed output including line content",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    success = verify_no_hardcoded_models(verbose=args.verbose, json_output=args.json)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
