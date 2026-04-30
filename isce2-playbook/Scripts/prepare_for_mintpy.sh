#!/bin/bash
# prepare_for_mintpy.sh
# Bridge script: Prepare ISCE2 topsStack outputs for MintPy time-series analysis
#
# Usage:
#   ./Scripts/prepare_for_mintpy.sh <isce2_stack_dir> <mintpy_input_dir>
#
# Example:
#   ./Scripts/prepare_for_mintpy.sh ./merged ../mintpy-playbook/input_data
#
# What it does:
# 1. Organizes ISCE2 outputs into MintPy expected structure
# 2. Creates file lists for MintPy loading
# 3. Copies geometry files (lat, lon, los, height)
# 4. Copies interferogram stack (unwrapped phase, coherence)

set -e  # Exit on error

if [ $# -ne 2 ]; then
    echo "Usage: $0 <isce2_stack_dir> <mintpy_input_dir>"
    echo ""
    echo "Arguments:"
    echo "  isce2_stack_dir    : Directory with ISCE2 topsStack outputs (merged/)"
    echo "  mintpy_input_dir   : Target directory for MintPy (will be created)"
    echo ""
    echo "Example:"
    echo "  $0 ./merged ../mintpy-playbook/input_data"
    exit 1
fi

ISCE2_DIR="$1"
MINTPY_DIR="$2"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "ISCE2 → MintPy Bridge: Preparing Data"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check ISCE2 directory exists
if [ ! -d "$ISCE2_DIR" ]; then
    echo "❌ ERROR: ISCE2 directory not found: $ISCE2_DIR"
    exit 1
fi

# Create MintPy directory structure
echo "📁 Creating MintPy input directory: $MINTPY_DIR"
mkdir -p "$MINTPY_DIR"/{interferograms,geometry}

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1: Copy Geometry Files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Copy geometry files (lat, lon, height, los)
GEOM_FILES=("lat.rdr" "lon.rdr" "hgt.rdr" "los.rdr" "shadowMask.rdr" "incLocal.rdr")

for geom_file in "${GEOM_FILES[@]}"; do
    if [ -f "$ISCE2_DIR/geom_reference/$geom_file" ]; then
        echo "  ✓ Copying $geom_file"
        cp "$ISCE2_DIR/geom_reference/$geom_file" "$MINTPY_DIR/geometry/"
    else
        echo "  ⚠ Warning: $geom_file not found (optional)"
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2: Organize Interferograms"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Find all interferogram directories
IFG_COUNT=0
for ifg_dir in "$ISCE2_DIR"/interferograms/*/; do
    if [ -d "$ifg_dir" ]; then
        ifg_name=$(basename "$ifg_dir")
        echo "  Processing: $ifg_name"
        
        # Create interferogram subdirectory
        mkdir -p "$MINTPY_DIR/interferograms/$ifg_name"
        
        # Copy essential files
        if [ -f "$ifg_dir/filt_topophase.unw.geo" ]; then
            cp "$ifg_dir/filt_topophase.unw.geo" "$MINTPY_DIR/interferograms/$ifg_name/"
            echo "    ✓ unwrapped phase"
        fi
        
        if [ -f "$ifg_dir/filt_topophase.unw.geo.cor" ]; then
            cp "$ifg_dir/filt_topophase.unw.geo.cor" "$MINTPY_DIR/interferograms/$ifg_name/"
            echo "    ✓ coherence"
        fi
        
        if [ -f "$ifg_dir/filt_topophase.unw.conncomp" ]; then
            cp "$ifg_dir/filt_topophase.unw.conncomp" "$MINTPY_DIR/interferograms/$ifg_name/"
            echo "    ✓ connected components"
        fi
        
        IFG_COUNT=$((IFG_COUNT + 1))
    fi
done

echo ""
echo "  Total interferograms processed: $IFG_COUNT"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3: Create MintPy File List"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Generate file list for MintPy loading
cat > "$MINTPY_DIR/file_list.txt" << EOF
# MintPy Input File List
# Generated from ISCE2 topsStack outputs
#
# Geometry files
geometry/lat.rdr
geometry/lon.rdr
geometry/hgt.rdr
geometry/los.rdr

# Interferograms (unwrapped phase + coherence)
EOF

for ifg_dir in "$MINTPY_DIR"/interferograms/*/; do
    if [ -d "$ifg_dir" ]; then
        ifg_name=$(basename "$ifg_dir")
        echo "interferograms/$ifg_name/filt_topophase.unw.geo" >> "$MINTPY_DIR/file_list.txt"
        echo "interferograms/$ifg_name/filt_topophase.unw.geo.cor" >> "$MINTPY_DIR/file_list.txt"
    fi
done

echo "  ✓ Created file_list.txt with $IFG_COUNT interferograms"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ COMPLETE: Data prepared for MintPy"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📂 Output directory: $MINTPY_DIR"
echo "📊 Interferograms: $IFG_COUNT pairs"
echo ""
echo "Next steps:"
echo "  1. cd ../mintpy-playbook"
echo "  2. Edit mintpy config to point to: $MINTPY_DIR"
echo "  3. Run: docker compose run --rm mintpy smallbaselineApp.py <config>"
echo ""
echo "Or use the bridge script:"
echo "  python3 Scripts/ts_analysis_mintpy.py --data_dir $MINTPY_DIR --work_dir ./mintpy_output"
echo ""
