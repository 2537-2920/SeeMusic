#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

find "$ROOT_DIR" -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".mypy_cache" -o -name ".ruff_cache" -o -name "htmlcov" \) -prune -exec rm -rf {} +
find "$ROOT_DIR" -type f \( -name "*.pyc" -o -name "*.pyo" -o -name ".coverage" -o -name "coverage.xml" \) -delete

printf 'Python cache artifacts cleaned in %s\n' "$ROOT_DIR"

