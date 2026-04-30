#!/bin/bash
# =============================================================================
# MintPy Docker Playbook — Step 2: Run smallbaselineApp Pipeline
# =============================================================================
# Runs the complete MintPy routine time-series analysis workflow.
#
# This is the core of MintPy — it executes all 17 processing steps:
#   1.  load_data           → Load interferograms into HDF5
#   2.  modify_network      → Filter interferogram network
#   3.  reference_point     → Select spatial reference pixel
#   4.  quick_overview      → Quick velocity/coherence assessment
#   5.  correct_unwrap_error → Fix phase unwrapping errors
#   6.  invert_network      → Invert network → displacement time-series
#   7.  correct_LOD         → Local oscillator drift (Envisat only)
#   8.  correct_SET         → Solid Earth tides
#   9.  correct_troposphere → Tropospheric delay correction
#   10. deramp              → Remove orbital ramps
#   11. correct_topography  → DEM error correction
#   12. residual_RMS        → Quality assessment
#   13. reference_date      → Select reference date
#   14. velocity            → Estimate displacement velocity
#   15. geocode             → Radar → geographic coordinates
#   16. google_earth        → Generate KMZ files
#   17. hdfeos5             → Export to HDF-EOS5 format
# =============================================================================
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/mnt/data/sbas_vs_ps_test_bologna}"
STACK_TYPE="${STACK_TYPE:-sbas}"
TEMPLATE="${TEMPLATE:-${PROJECT_DIR}/mintpy_config_${STACK_TYPE}.cfg}"
WORK_DIR="${WORK_DIR:-${PROJECT_DIR}/mintpy_work/${STACK_TYPE}}"

echo "══════════════════════════════════════════════════════════════"
echo "  Step 2: Run MintPy smallbaselineApp Pipeline"
echo "  Project:   ${PROJECT_DIR}"
echo "  Stack:     ${STACK_TYPE}"
echo "  Template:  ${TEMPLATE}"
echo "  Work Dir:  ${WORK_DIR}"
echo "══════════════════════════════════════════════════════════════"

# Validate prerequisites
if [ ! -d "${PROJECT_DIR}" ]; then
    echo "✗ ERROR: Project directory not found at ${PROJECT_DIR}"
    echo "  Check docker volume mounts and PROJECT_DIR."
    exit 1
fi

if [ ! -f "${TEMPLATE}" ]; then
    echo "✗ ERROR: Template file not found: ${TEMPLATE}"
    exit 1
fi

# Create and move to working directory
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

echo ""
echo "── Starting Pipeline ─────────────────────────────────────────"
echo "  Start time: $(date)"
echo ""

# Run the complete workflow
# The --plot flag generates figures in the ./pic/ directory
START_TIME=$SECONDS

smallbaselineApp.py "${TEMPLATE}" --plot 2>&1 | tee pipeline.log

ELAPSED=$(( SECONDS - START_TIME ))
MINUTES=$(( ELAPSED / 60 ))
SECONDS_REMAINING=$(( ELAPSED % 60 ))

echo ""
echo "────────────────────────────────────────────────────────────"
echo "  End time:  $(date)"
echo "  Duration:  ${MINUTES}m ${SECONDS_REMAINING}s"
echo "────────────────────────────────────────────────────────────"

# Verify key outputs
echo ""
echo "── Output Verification ───────────────────────────────────────"

check_file() {
    if [ -f "$1" ]; then
        SIZE=$(du -h "$1" | cut -f1)
        echo "  ✓ $(basename $1) (${SIZE})"
    else
        echo "  ✗ $(basename $1) — MISSING"
    fi
}

echo "Core HDF5 files:"
check_file "${WORK_DIR}/inputs/ifgramStack.h5"
check_file "${WORK_DIR}/inputs/geometryRadar.h5"
check_file "${WORK_DIR}/timeseries.h5"
check_file "${WORK_DIR}/temporalCoherence.h5"
check_file "${WORK_DIR}/velocity.h5"

echo ""
echo "Corrected time-series:"
for f in "${WORK_DIR}"/timeseries_*.h5; do
    [ -f "$f" ] && check_file "$f"
done

echo ""
echo "Figures:"
if [ -d "${WORK_DIR}/pic" ]; then
    NFIGS=$(ls "${WORK_DIR}/pic/"*.png 2>/dev/null | wc -l)
    echo "  ✓ ${NFIGS} figures generated in ./pic/"
else
    echo "  ✗ No figures directory found"
fi

echo "────────────────────────────────────────────────────────────"
echo ""
echo "✅ Step 2 complete — MintPy pipeline finished!"
echo "   Results in: ${WORK_DIR}/"
echo "   Figures in: ${WORK_DIR}/pic/"
echo "   Log file:   ${WORK_DIR}/pipeline.log"
