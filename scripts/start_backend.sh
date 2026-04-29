#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_exe=""

if [[ -x "${repo_root}/.venv/bin/python" ]]; then
    python_exe="${repo_root}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    python_exe="$(command -v python3)"
else
    echo "Python 3 not found. Install python3 or create ${repo_root}/.venv first." >&2
    exit 1
fi

cd "${repo_root}"
echo "Starting backend with ${python_exe}"
exec "${python_exe}" backend/main.py
