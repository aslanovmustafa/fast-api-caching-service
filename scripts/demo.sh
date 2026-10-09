#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
api_url="${1:-http://127.0.0.1:8000}"

echo "Create and read the same payload twice"
python -m app.cli --host "$api_url" --input examples/input.json --repeat 2

echo "Read input from stdin"
python -m app.cli --host "$api_url" --input - < examples/input.json

echo "An unknown field should return 422"
curl --silent --show-error --write-out '\nHTTP %{http_code}\n' \
  "$api_url/payload" \
  -H 'Content-Type: application/json' \
  -d '{"list_1":[],"list_2":[],"typo":true}'

echo "An unknown endpoint should return 404"
curl --silent --show-error --write-out '\nHTTP %{http_code}\n' "$api_url/not-an-endpoint"
