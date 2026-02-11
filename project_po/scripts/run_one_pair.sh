#!/usr/bin/env bash
set -euo pipefail

MISSION="$1"          # ERS | ENV | ALOS | S1
PAIRS_CSV="$2"        # pairs/pairs_<MISSION>.csv
IDX="$3"              # 1-based line index in csv (skip header)

PAIR_LINE=$(awk -F',' -v i="$IDX" 'NR==i+1{print $0}' "$PAIRS_CSV")
REF=$(echo "$PAIR_LINE" | cut -d',' -f1)
SEC=$(echo "$PAIR_LINE" | cut -d',' -f2)

OUTDIR="work/ISCE2/${MISSION}/IFG_${REF}_${SEC}"
mkdir -p "$OUTDIR"
cd "$OUTDIR"

echo "[INFO] MISSION=$MISSION REF=$REF SEC=$SEC OUTDIR=$OUTDIR"

# -------------------------------------------------------------------
# TODO: Put the mission-specific ISCE2 commands here.
# You will typically:
#  - link/copy SLCs into this folder
#  - run a mission-specific ISCE2 recipe
#  - produce: unwrapped phase + coherence
# -------------------------------------------------------------------

# Example placeholders:
echo "RUN ISCE2 HERE for $MISSION (REF=$REF SEC=$SEC)" | tee run.log

# touch expected outputs (placeholders)
# touch unw_phase.tif coherence.tif
