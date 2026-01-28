#!/usr/bin/env python3
"""Architectural boundary validation for KidsChores.

This script enforces structural rules from:
- CODE_REVIEW_GUIDE.md § Phase 0: Boundary Check
- QUALITY_REFERENCE.md § Quality Compliance Checklist

Run standalone: python utils/check_boundaries.py
Exit code 0 = all checks pass, 1 = violations found

Checks:
1. Purity Boundary - No homeassistant.* imports in pure modules
2. Lexicon Standards - Item vs Entity terminology
3. CRUD Ownership - Single Write Path enforcement
4. Code Quality - Logging, type syntax, exceptions
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NamedTuple

# Base paths
REPO_ROOT = Path(__file__).parent.parent
COMPONENT_PATH = REPO_ROOT / "custom_components" / "kidschores"

# Pure modules that must not import homeassistant
PURE_MODULE_PATHS = [
    COMPONENT_PATH / "utils",
    COMPONENT_PATH / "engines",
    COMPONENT_PATH / "data_builders.py",
]

# Files that must not write to storage
NO_WRITE_FILES = [
    COMPONENT_PATH / "options_flow.py",
    COMPONENT_PATH / "services.py",
]

# Allow-list for bare exceptions (config flows need robustness, background tasks need isolation)
# Per AGENTS.md: "✅ Allowed in config flows" and "✅ Allowed in functions/methods that run in background tasks"
BARE_EXCEPTION_ALLOWLIST = [
    "config_flow.py",
    "options_flow.py",
    # Background task and fallback logic files - bare exceptions prevent cascade failures
    "gamification_manager.py",  # Kid evaluation loop - one kid's error shouldn't stop others
    "chore_manager.py",  # Undo operations - point reclaim failure shouldn't fail undo
    "chore_engine.py",  # Streak calculation fallback - any failure safely resets streak
]


class Violation(NamedTuple):
    """A boundary violation with context."""

    category: str
    file_path: Path
    line_number: int
    line_content: str
    message: str
    doc_reference: str


def find_ha_imports_in_pure_modules() -> list[Violation]:
    """Check Audit Step A: No homeassistant imports in pure modules."""
    violations = []
    patterns = [
        re.compile(r"^\s*from\s+homeassistant"),
        re.compile(r"^\s*import\s+homeassistant"),
    ]

    for module_path in PURE_MODULE_PATHS:
        if module_path.is_file():
            files_to_check = [module_path]
        elif module_path.is_dir():
            files_to_check = list(module_path.rglob("*.py"))
        else:
            continue

        for file_path in files_to_check:
            try:
                with open(file_path, encoding="utf-8") as f:
                    for line_num, line in enumerate(f, start=1):
                        for pattern in patterns:
                            if pattern.search(line):
                                violations.append(
                                    Violation(
                                        category="PURITY",
                                        file_path=file_path,
                                        line_number=line_num,
                                        line_content=line.strip(),
                                        message=f"Homeassistant import in pure module",
                                        doc_reference="CODE_REVIEW_GUIDE.md § Audit Step A",
                                    )
                                )
            except Exception as e:
                print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)

    return violations


def find_ambiguous_entity_terminology() -> list[Violation]:
    """Check Audit Step B: Item vs Entity lexicon."""
    violations = []
    # Look for "Chore Entity", "Kid Entity", etc. in comments and docstrings
    pattern = re.compile(
        r'(Chore\s+Entity|Kid\s+Entity|Badge\s+Entity|Reward\s+Entity|Parent\s+Entity|Penalty\s+Entity|Bonus\s+Entity|Achievement\s+Entity|Challenge\s+Entity)',
        re.IGNORECASE
    )

    files_to_check = [
        COMPONENT_PATH / "data_builders.py",
        COMPONENT_PATH / "managers",
    ]

    for path in files_to_check:
        if path.is_file():
            file_list = [path]
        elif path.is_dir():
            file_list = list(path.rglob("*.py"))
        else:
            continue

        for file_path in file_list:
            try:
                with open(file_path, encoding="utf-8") as f:
                    for line_num, line in enumerate(f, start=1):
                        match = pattern.search(line)
                        if match:
                            # Check if it's in a comment or docstring
                            if "#" in line or '"""' in line or "'''" in line:
                                violations.append(
                                    Violation(
                                        category="LEXICON",
                                        file_path=file_path,
                                        line_number=line_num,
                                        line_content=line.strip(),
                                        message=f'Use "Item" or "Record" instead of "{match.group(1)}"',
                                        doc_reference="ARCHITECTURE.md § Lexicon Standards",
                                    )
                                )
            except Exception as e:
                print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)

    return violations


def find_storage_writes_in_ui_layer() -> list[Violation]:
    """Check Audit Step C: No storage writes outside Managers."""
    violations = []

    # Match actual storage writes, not just any const.DATA_ access
    write_patterns = [
        # Direct assignment to coordinator._data
        re.compile(r"coordinator\._data\[.*\]\s*="),
        re.compile(r"self\._data\[.*\]\s*="),
        # .update() calls on coordinator._data
        re.compile(r"coordinator\._data\[.*\]\.update\("),
        re.compile(r"self\._data\[.*\]\.update\("),
        # Persistence calls
        re.compile(r"coordinator\._persist\(\)"),
        re.compile(r"self\._persist\(\)"),
    ]

    for file_path in NO_WRITE_FILES:
        if not file_path.exists():
            continue

        try:
            with open(file_path, encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    for pattern in write_patterns:
                        if pattern.search(line):
                            violations.append(
                                Violation(
                                    category="CRUD",
                                    file_path=file_path,
                                    line_number=line_num,
                                    line_content=line.strip(),
                                    message="Direct storage write in UI/Service layer - must delegate to Manager",
                                    doc_reference="DEVELOPMENT_STANDARDS.md § 4. Data Write Standards",
                                )
                            )
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)

    return violations


def find_hardcoded_translation_keys() -> list[Violation]:
    """Check: translation_key must use const.TRANS_KEY_* constants."""
    violations = []
    # Match translation_key="literal" or translation_domain="literal"
    patterns = [
        re.compile(r'translation_key\s*=\s*["\']([^"\']+)["\']'),
        re.compile(r'translation_domain\s*=\s*["\'](?!kidschores)([^"\']+)["\']'),
    ]

    for file_path in COMPONENT_PATH.rglob("*.py"):
        try:
            with open(file_path, encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    for pattern in patterns:
                        match = pattern.search(line)
                        if match:
                            # Check if it references const.TRANS_KEY_ or const.DOMAIN
                            if "const.TRANS_KEY_" not in line and "const.DOMAIN" not in line:
                                violations.append(
                                    Violation(
                                        category="TRANSLATION",
                                        file_path=file_path,
                                        line_number=line_num,
                                        line_content=line.strip(),
                                        message="Use const.TRANS_KEY_* for translation_key, const.DOMAIN for translation_domain",
                                        doc_reference="DEVELOPMENT_STANDARDS.md § 3. Constant Naming Standards",
                                    )
                                )
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)

    return violations


def find_fstrings_in_logging() -> list[Violation]:
    """Check: No f-strings in logging statements."""
    violations = []
    # Match logger calls with f-strings
    pattern = re.compile(r'(LOGGER|const\.LOGGER)\.(debug|info|warning|error|exception)\s*\(\s*f["\']')

    for file_path in COMPONENT_PATH.rglob("*.py"):
        try:
            with open(file_path, encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    if pattern.search(line):
                        violations.append(
                            Violation(
                                category="LOGGING",
                                file_path=file_path,
                                line_number=line_num,
                                line_content=line.strip(),
                                message='Use lazy logging: logger.debug("msg: %s", var) not f"msg: {var}"',
                                doc_reference="DEVELOPMENT_STANDARDS.md § 5. Lazy Logging",
                            )
                        )
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)

    return violations


def find_old_typing_syntax() -> list[Violation]:
    """Check: Modern type syntax (str | None, not Optional[str])."""
    violations = []
    pattern = re.compile(r'\bOptional\[')

    for file_path in COMPONENT_PATH.rglob("*.py"):
        try:
            with open(file_path, encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    if pattern.search(line):
                        violations.append(
                            Violation(
                                category="TYPE_SYNTAX",
                                file_path=file_path,
                                line_number=line_num,
                                line_content=line.strip(),
                                message='Use modern syntax: "str | None" instead of "Optional[str]"',
                                doc_reference="DEVELOPMENT_STANDARDS.md § 4. Type Hints",
                            )
                        )
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)

    return violations


def find_bare_exceptions() -> list[Violation]:
    """Check: No bare Exception catches (except in config flows)."""
    violations = []
    pattern = re.compile(r'^\s*except\s+(Exception|BaseException)\s*:')

    for file_path in COMPONENT_PATH.rglob("*.py"):
        # Skip files in allow-list
        if any(allowed in str(file_path) for allowed in BARE_EXCEPTION_ALLOWLIST):
            continue

        try:
            with open(file_path, encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    if pattern.search(line):
                        violations.append(
                            Violation(
                                category="EXCEPTION",
                                file_path=file_path,
                                line_number=line_num,
                                line_content=line.strip(),
                                message="Use specific exception types, not bare Exception (unless in config flow)",
                                doc_reference="DEVELOPMENT_STANDARDS.md § Error Handling",
                            )
                        )
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)

    return violations


def format_violations(violations: list[Violation]) -> str:
    """Format violations for display."""
    if not violations:
        return ""

    # Group by category
    by_category: dict[str, list[Violation]] = {}
    for v in violations:
        by_category.setdefault(v.category, []).append(v)

    output = []
    for category, items in sorted(by_category.items()):
        output.append(f"\n{'='*80}")
        output.append(f"❌ {category} VIOLATIONS ({len(items)} found)")
        output.append(f"{'='*80}")

        for v in items:
            rel_path = v.file_path.relative_to(REPO_ROOT)
            output.append(f"\n📁 {rel_path}:{v.line_number}")
            output.append(f"   {v.line_content}")
            output.append(f"   ⚠️  {v.message}")
            output.append(f"   📖 See: {v.doc_reference}")

    return "\n".join(output)


def main() -> int:
    """Run all boundary checks."""
    print("🔍 Running architectural boundary checks...")
    print(f"   Checking: {COMPONENT_PATH.relative_to(REPO_ROOT)}\n")

    all_violations = []

    # Run all checks
    checks = [
        ("Purity Boundary", find_ha_imports_in_pure_modules),
        ("Lexicon Standards", find_ambiguous_entity_terminology),
        ("CRUD Ownership", find_storage_writes_in_ui_layer),
        ("Translation Constants", find_hardcoded_translation_keys),
        ("Logging Quality", find_fstrings_in_logging),
        ("Type Syntax", find_old_typing_syntax),
        ("Exception Handling", find_bare_exceptions),
    ]

    for check_name, check_func in checks:
        print(f"   ⏳ Checking {check_name}...", end=" ")
        violations = check_func()
        if violations:
            print(f"❌ {len(violations)} violation(s)")
            all_violations.extend(violations)
        else:
            print("✅")

    # Report results
    if all_violations:
        print(format_violations(all_violations))
        print(f"\n{'='*80}")
        print(f"❌ FAILED: {len(all_violations)} boundary violation(s) found")
        print(f"{'='*80}")
        print("\n💡 Fix these violations to maintain Platinum quality standards.")
        print("   See CODE_REVIEW_GUIDE.md and QUALITY_REFERENCE.md for details.\n")
        return 1

    print("\n" + "="*80)
    print("✅ SUCCESS: All architectural boundaries validated")
    print("="*80)
    print("\n🎯 Platinum quality standards maintained!\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
