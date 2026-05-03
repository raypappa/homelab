#!/usr/bin/env bash
# Validates kubesec scan output and errors if any items have valid==false

set -euo pipefail

# Read JSON from stdin
json=$(cat)

# Filter out valid==false and unsupported resource kinds
filtered=$(echo "$json" | jq '[.[] | select(.valid != false and .message != "This resource kind is not supported by kubesec")]')

# Check if any items remain after filtering
invalid_count=$(echo "$filtered" | jq '[.[] | select(.valid == false)] | length')

if [ "$invalid_count" -gt 0 ]; then
  echo "Error: kubesec found $invalid_count invalid items:"
  echo "$filtered" | jq '.[] | select(.valid == false) | {object: .object, valid: .valid, message: .message}'
  exit 1
fi

# Output the filtered JSON for piping to next command
echo "$filtered"
