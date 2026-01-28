#!/bin/bash
# Quick lint check - run after every change using ruff
# Usage: ./utils/quick_lint.sh [--fix]

cd "$(dirname "$0")/.." || exit 1

echo "🔍 Running ruff linting..."
echo ""

if [[ "$1" == "--fix" ]]; then
    # Auto-fix issues with ruff
    echo "🔧 Running ruff check with auto-fix..."
    ruff check --fix custom_components/kidschores tests
    ruff_check_exit=$?

    echo ""
    echo "🔧 Running ruff format..."
    ruff format custom_components/kidschores tests
    ruff_format_exit=$?

    echo ""
    echo "🔍 Running mypy type checking..."
    mypy --explicit-package-bases custom_components/kidschores
    mypy_exit=$?

    echo ""
    echo "🏛️ Running architectural boundary checks..."
    python utils/check_boundaries.py
    boundary_exit=$?

    if [ $ruff_check_exit -eq 0 ] && [ $ruff_format_exit -eq 0 ] && [ $mypy_exit -eq 0 ] && [ $boundary_exit -eq 0 ]; then
        echo ""
        echo "✅ All auto-fixes applied! Verify changes and commit."
        exit 0
    else
        echo ""
        echo "⚠️ Some issues remain after auto-fix. Review output above."
        exit 1
    fi
else
    # Check only (no auto-fix)
    echo "Running ruff check (read-only)..."
    ruff check custom_components/kidschores tests
    ruff_check_exit=$?

    echo ""
    echo "Checking code formatting..."
    ruff format --check custom_components/kidschores tests
    ruff_format_exit=$?

    echo ""
    echo "🔍 Running mypy type checking..."
    mypy --explicit-package-bases custom_components/kidschores
    mypy_exit=$?

    echo ""
    echo "🏛️ Running architectural boundary checks..."
    python utils/check_boundaries.py
    boundary_exit=$?

    if [ $ruff_check_exit -eq 0 ] && [ $ruff_format_exit -eq 0 ] && [ $mypy_exit -eq 0 ] && [ $boundary_exit -eq 0 ]; then
        echo ""
        echo "✅ All checks passed! Ready to commit."
        exit 0
    else
        echo ""
        echo "❌ Linting issues found. Run with --fix to auto-correct:"
        echo "  ./utils/quick_lint.sh --fix"
        exit 1
    fi
fi
