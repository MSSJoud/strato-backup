#!/usr/bin/env bash
set -euo pipefail

mkdir -p /workspace/outputs
mkdir -p /tmp/matplotlib

exec "$@"

