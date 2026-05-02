#!/usr/bin/env bash
# Validates kubesec scan output and errors if any items have valid==false

set -euo pipefail

# Read JSON from stdin
json=$(cat)

# Check if any items have valid==false using jq
invalid_count=$(echo "$json" | jq '[.[] | select(.valid == false)] | length')

if [ "$invalid_count" -gt 0 ]; then
  echo "Error: kubesec found $invalid_count invalid items:"
  echo "$json" | jq '.[] | select(.valid == false) | {object: .object, valid: .valid, message: .message}'
  exit 1
fi

# Output the original JSON for piping to next command
echo "$json"
