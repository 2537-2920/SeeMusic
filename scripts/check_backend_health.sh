#!/usr/bin/env bash

set -euo pipefail

base_url="${1:-http://127.0.0.1:8000}"

for path in "/health" "/api/v1/health"; do
    echo "Checking ${base_url}${path}"
    curl --fail --silent --show-error "${base_url}${path}"
    echo
done
