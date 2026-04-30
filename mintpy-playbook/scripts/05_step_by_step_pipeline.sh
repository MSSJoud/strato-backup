#!/bin/bash
# =============================================================================
# MintPy Docker Playbook — Step 5: Step-by-Step Pipeline (with individual logs)
# =============================================================================
# Runs each of the 17 smallbaselineApp steps individually, capturing
# stdout/stderr and timing for each step. Useful for debugging and
# understanding what each step does.
# =============================================================================
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/mnt/data/sbas_vs_ps_test_bologna}"
STACK_TYPE="${STACK_TYPE:-sbas}"
TEMPLATE="${TEMPLATE:-${PROJECT_DIR}/mintpy_config_${STACK_TYPE}.cfg}"
WORK_DIR="${WORK_DIR:-${PROJECT_DIR}/mintpy_work/${STACK_TYPE}}"
LOG_DIR="${WORK_DIR}/logs"

echo "══════════════════════════════════════════════════════════════"
echo "  Step-by-Step Pipeline Runner"
echo "  Project:   ${PROJECT_DIR}"
echo "  Stack:     ${STACK_TYPE}"
echo "  Template:  ${TEMPLATE}"
echo "  Logs:      ${LOG_DIR}/"
echo "══════════════════════════════════════════════════════════════"

mkdir -p "$WORK_DIR" "$LOG_DIR"
cd "$WORK_DIR"

# Define all steps in order
STEPS=(
    "load_data"
    "modify_network"
    "reference_point"
    "quick_overview"
    "correct_unwrap_error"
    "invert_network"
    "correct_LOD"
    "correct_SET"
    "correct_troposphere"
    "deramp"
    "correct_topography"
    "residual_RMS"
    "reference_date"
    "velocity"
    "geocode"
    "google_earth"
    "hdfeos5"
)

# Step descriptions
declare -A DESCRIPTIONS
DESCRIPTIONS["load_data"]="Load interferogram stack into HDF5 format"
DESCRIPTIONS["modify_network"]="Remove low-quality interferograms from network"
DESCRIPTIONS["reference_point"]="Select reference pixel (highest coherence)"
DESCRIPTIONS["quick_overview"]="Quick velocity and coherence assessment"
DESCRIPTIONS["correct_unwrap_error"]="Detect and correct phase unwrapping errors"
DESCRIPTIONS["invert_network"]="Invert interferogram network → time-series"
DESCRIPTIONS["correct_LOD"]="Correct local oscillator drift (Envisat only)"
DESCRIPTIONS["correct_SET"]="Correct solid Earth tides"
DESCRIPTIONS["correct_troposphere"]="Correct tropospheric delay (ERA5 model)"
DESCRIPTIONS["deramp"]="Remove orbital phase ramps"
DESCRIPTIONS["correct_topography"]="Correct DEM errors"
DESCRIPTIONS["residual_RMS"]="Compute residual RMS for quality assessment"
DESCRIPTIONS["reference_date"]="Select reference date for time-series"
DESCRIPTIONS["velocity"]="Estimate linear displacement velocity"
DESCRIPTIONS["geocode"]="Convert from radar to geographic coordinates"
DESCRIPTIONS["google_earth"]="Generate Google Earth KMZ visualization"
DESCRIPTIONS["hdfeos5"]="Export to HDF-EOS5 format"

# Summary table header
echo ""
printf "%-3s %-25s %-50s %-8s %-8s\n" "#" "Step" "Description" "Time" "Status"
printf "%-3s %-25s %-50s %-8s %-8s\n" "---" "-------------------------" "--------------------------------------------------" "--------" "--------"

TOTAL_START=$SECONDS

for i in "${!STEPS[@]}"; do
    STEP="${STEPS[$i]}"
    STEP_NUM=$((i + 1))
    DESC="${DESCRIPTIONS[$STEP]}"
    LOG_FILE="${LOG_DIR}/${STEP_NUM}_${STEP}.log"

    STEP_START=$SECONDS

    # Run the step
    if smallbaselineApp.py "${TEMPLATE}" --dostep "${STEP}" > "${LOG_FILE}" 2>&1; then
        STATUS="✓ OK"
    else
        STATUS="✗ FAIL"
    fi

    STEP_ELAPSED=$(( SECONDS - STEP_START ))
    STEP_TIME="${STEP_ELAPSED}s"

    printf "%-3s %-25s %-50s %-8s %-8s\n" \
        "${STEP_NUM}" "${STEP}" "${DESC}" "${STEP_TIME}" "${STATUS}"
done

TOTAL_ELAPSED=$(( SECONDS - TOTAL_START ))
TOTAL_MINUTES=$(( TOTAL_ELAPSED / 60 ))
TOTAL_SECONDS=$(( TOTAL_ELAPSED % 60 ))

echo ""
echo "────────────────────────────────────────────────────────────"
echo "  Total time: ${TOTAL_MINUTES}m ${TOTAL_SECONDS}s"
echo "  Logs saved: ${LOG_DIR}/"
echo "────────────────────────────────────────────────────────────"

# Generate figures after pipeline
echo ""
echo "Generating final plots..."
smallbaselineApp.py "${TEMPLATE}" --plot >> "${LOG_DIR}/plot.log" 2>&1 || true

echo ""
echo "✅ Step-by-step pipeline complete!"
echo "   Review individual logs in: ${LOG_DIR}/"
echo "   Example: cat ${LOG_DIR}/6_invert_network.log"
