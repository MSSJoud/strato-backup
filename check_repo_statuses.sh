#!/usr/bin/env bash

set -euo pipefail

repos=(
  "/home/ubuntu/work"
  "/home/ubuntu/work/ait/LLMgeoChat"
  "/home/ubuntu/work/hydroinsar-qgis"
  "/home/ubuntu/work/w3ra-hydroinsar-qgis"
  "/home/ubuntu/work/w3raexplorer_v01"
)

for repo in "${repos[@]}"; do
  echo "==> $repo"
  git -C "$repo" status --short --branch
  echo "remote:"
  git -C "$repo" remote -v | sed -n '1,2p'
  echo
done
