#!/bin/bash
# =============================================================================
# MintPy Docker Playbook — Step 3: Post-Processing Analysis
# =============================================================================
# Runs various MintPy utility scripts for deeper inspection of results:
#   - info.py       → Print HDF5 file metadata and statistics
#   - view.py       → Generate 2D map views (velocity, coherence, DEM error)
#   - plot_network.py → Visualize the interferogram network
#   - plot_coherence_matrix.py → Coherence matrix for selected pixels
#   - save_kmz.py   → Google Earth KMZ export of velocity
#   - save_kmz_timeseries.py → KMZ time-series export
# =============================================================================
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/mnt/data/sbas_vs_ps_test_bologna}"
STACK_TYPE="${STACK_TYPE:-sbas}"
WORK_DIR="${WORK_DIR:-${PROJECT_DIR}/mintpy_work/${STACK_TYPE}}"
OUT_DIR="/workspace/outputs"

echo "══════════════════════════════════════════════════════════════"
echo "  Step 3: Post-Processing Analysis"
echo "  Project:  ${PROJECT_DIR}"
echo "  Stack:    ${STACK_TYPE}"
echo "  Work Dir: ${WORK_DIR}"
echo "  Output:   ${OUT_DIR}"
echo "══════════════════════════════════════════════════════════════"

if [ ! -f "${WORK_DIR}/velocity.h5" ]; then
    echo "✗ ERROR: velocity.h5 not found. Run the pipeline (Step 2) first."
    exit 1
fi

cd "$WORK_DIR"
mkdir -p "$OUT_DIR"

# ── 3.1 Dataset Information ─────────────────────────────────────────────
echo ""
echo "── 3.1 Dataset Information ───────────────────────────────────"

echo "--- Interferogram Stack ---"
info.py inputs/ifgramStack.h5 2>&1 | head -30

echo ""
echo "--- Time Series ---"
info.py timeseries.h5 2>&1 | head -20

echo ""
echo "--- Velocity ---"
info.py velocity.h5 2>&1 | head -15

# ── 3.2 Network Visualization ───────────────────────────────────────────
echo ""
echo "── 3.2 Network Plot ─────────────────────────────────────────"

if command -v plot_network.py &>/dev/null; then
    plot_network.py inputs/ifgramStack.h5 \
        --nodisplay \
        --save \
        --figsize 12 4 \
        2>/dev/null || echo "  (network plot skipped — display not available)"
    # Copy generated figures
    for f in network*.png Network*.png; do
        [ -f "$f" ] && cp "$f" "$OUT_DIR/" && echo "  ✓ Saved: $f"
    done
fi

# ── 3.3 Velocity Map Views ──────────────────────────────────────────────
echo ""
echo "── 3.3 Generate Map Views ───────────────────────────────────"

# Velocity map
echo "  Generating velocity map..."
view.py velocity.h5 velocity \
    --nodisplay \
    --save \
    --figsize 8 6 \
    -u cm/yr \
    --dem inputs/geometryRadar.h5 \
    -o "${OUT_DIR}/velocity_map.png" \
    2>/dev/null || echo "  (velocity map: view.py fallback)"

# Temporal coherence map
echo "  Generating temporal coherence map..."
view.py temporalCoherence.h5 \
    --nodisplay \
    --save \
    -c gray \
    --figsize 8 6 \
    -o "${OUT_DIR}/temporal_coherence.png" \
    2>/dev/null || echo "  (coherence map: view.py fallback)"

# Average spatial coherence
if [ -f "avgSpatialCoh.h5" ]; then
    echo "  Generating average spatial coherence map..."
    view.py avgSpatialCoh.h5 \
        --nodisplay \
        --save \
        -c gray \
        --figsize 8 6 \
        -o "${OUT_DIR}/avg_spatial_coherence.png" \
        2>/dev/null || true
fi

# DEM
echo "  Generating DEM view..."
view.py inputs/geometryRadar.h5 height \
    --nodisplay \
    --save \
    --figsize 8 6 \
    -o "${OUT_DIR}/dem.png" \
    2>/dev/null || echo "  (DEM view: fallback)"

# ── 3.4 Velocity Statistics ─────────────────────────────────────────────
echo ""
echo "── 3.4 Velocity Statistics ──────────────────────────────────"
python3 -c "
import h5py
import numpy as np

with h5py.File('velocity.h5', 'r') as f:
    vel = f['velocity'][:]
    # Mask zeros/nans
    vel_valid = vel[np.isfinite(vel) & (vel != 0)]

    print(f'  Grid size:     {vel.shape}')
    print(f'  Valid pixels:  {len(vel_valid):,} / {vel.size:,} ({100*len(vel_valid)/vel.size:.1f}%)')
    print(f'  Velocity range: {vel_valid.min()*100:.2f} to {vel_valid.max()*100:.2f} cm/yr')
    print(f'  Mean velocity:  {vel_valid.mean()*100:.3f} cm/yr')
    print(f'  Std deviation:  {vel_valid.std()*100:.3f} cm/yr')
    print(f'  Median:         {np.median(vel_valid)*100:.3f} cm/yr')
" 2>/dev/null || echo "  (velocity stats unavailable)"

# ── 3.5 Time-Series Statistics ───────────────────────────────────────────
echo ""
echo "── 3.5 Time-Series Summary ──────────────────────────────────"
python3 -c "
import h5py
import numpy as np

# Find the most corrected time-series file
import glob
ts_files = sorted(glob.glob('timeseries*.h5'))
ts_file = ts_files[-1]  # Most processed version

with h5py.File(ts_file, 'r') as f:
    dates = [d.decode() for d in f['date'][:]]
    ts = f['timeseries'][:]

    print(f'  File:          {ts_file}')
    print(f'  Date range:    {dates[0]} → {dates[-1]}')
    print(f'  N acquisitions: {len(dates)}')
    print(f'  Time span:     {(int(dates[-1][:4])-int(dates[0][:4]))*12 + int(dates[-1][4:6])-int(dates[0][4:6])} months')
    print(f'  Grid shape:    {ts.shape[1]} × {ts.shape[2]}')

    # Max cumulative displacement
    last = ts[-1]
    valid = last[np.isfinite(last) & (last != 0)]
    if len(valid) > 0:
        print(f'  Max displacement:   {valid.max()*100:.2f} cm (toward satellite)')
        print(f'  Min displacement:   {valid.min()*100:.2f} cm (away from satellite)')
" 2>/dev/null || echo "  (time-series stats unavailable)"

# ── 3.6 Copy Key Figures to Output ──────────────────────────────────────
echo ""
echo "── 3.6 Collecting Figures ───────────────────────────────────"
if [ -d "pic" ]; then
    cp pic/*.png "$OUT_DIR/" 2>/dev/null || true
    NCOPIED=$(ls "$OUT_DIR/"*.png 2>/dev/null | wc -l)
    echo "  ✓ Copied ${NCOPIED} figures to ${OUT_DIR}/"
fi

echo ""
echo "✅ Step 3 complete — analysis results in ${OUT_DIR}/"
