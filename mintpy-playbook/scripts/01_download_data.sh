#!/bin/bash
# =============================================================================
# MintPy Docker Playbook — Step 1: Download Sample Data
# =============================================================================
# Downloads the Fernandina Volcano (Galápagos) Sentinel-1 interferogram stack
# from Zenodo. This is the canonical MintPy example dataset.
#
# Dataset details:
#   Area:   Fernandina volcano, Galápagos Islands, Ecuador
#   Sensor: Sentinel-1 A/B, descending track 128
#   Period: December 2014 – June 2018 (98 acquisitions)
#   Source: Pre-processed with ISCE2/topsStack
#   Size:   ~700 MB compressed, ~1.5 GB extracted
# =============================================================================
set -euo pipefail

# Configuration
DATASET="${DATASET:-FernandinaSenDT128}"
DATA_DIR="/data"
ARCHIVE="${DATASET}.tar.xz"

# Zenodo URLs for available datasets
declare -A ZENODO_URLS
ZENODO_URLS["FernandinaSenDT128"]="https://zenodo.org/record/3952953/files/FernandinaSenDT128.tar.xz"
ZENODO_URLS["SanFranSenDT42"]="https://zenodo.org/record/4265413/files/SanFranSenDT42.tar.xz"
ZENODO_URLS["WellsEnvD2T399"]="https://zenodo.org/record/3952950/files/WellsEnvD2T399.tar.xz"
ZENODO_URLS["KujuAlosAT422F650"]="https://zenodo.org/record/3952917/files/KujuAlosAT422F650.tar.xz"

URL="${ZENODO_URLS[$DATASET]}"

echo "══════════════════════════════════════════════════════════════"
echo "  Step 1: Download Sample Data"
echo "  Dataset: ${DATASET}"
echo "  Source:  Zenodo"
echo "══════════════════════════════════════════════════════════════"

cd "$DATA_DIR"

# Check if data already exists
if [ -d "${DATA_DIR}/${DATASET}" ]; then
    echo "✓ Dataset directory already exists: ${DATA_DIR}/${DATASET}"
    echo "  Skipping download. Delete the directory to re-download."
    exit 0
fi

# Download archive if not present
if [ ! -f "${DATA_DIR}/${ARCHIVE}" ]; then
    echo "⬇ Downloading ${ARCHIVE} from Zenodo..."
    echo "  URL: ${URL}"
    echo "  This may take several minutes depending on your connection."
    echo ""
    wget --progress=bar:force:noscroll -O "${ARCHIVE}" "${URL}"
    echo ""
    echo "✓ Download complete: $(du -h ${ARCHIVE} | cut -f1)"
else
    echo "✓ Archive already exists: ${ARCHIVE}"
fi

# Extract archive
echo "📦 Extracting ${ARCHIVE}..."
tar -xvJf "${ARCHIVE}" 2>&1 | tail -1
echo "✓ Extraction complete"

# Create MintPy working directory if it doesn't exist
MINTPY_DIR="${DATA_DIR}/${DATASET}/mintpy"
mkdir -p "$MINTPY_DIR"

# Verify directory structure
echo ""
echo "── Directory Structure ──────────────────────────────────────"
echo "Data root: ${DATA_DIR}/${DATASET}/"
ls -la "${DATA_DIR}/${DATASET}/" 2>/dev/null || true
echo ""
if [ -d "${DATA_DIR}/${DATASET}/merged" ]; then
    echo "Interferograms:"
    ls "${DATA_DIR}/${DATASET}/merged/interferograms/" 2>/dev/null | head -5
    NIFG=$(ls -d "${DATA_DIR}/${DATASET}/merged/interferograms/"*/ 2>/dev/null | wc -l)
    echo "  ... (${NIFG} interferogram pairs total)"
fi
echo "────────────────────────────────────────────────────────────"

# Optionally clean up archive to save space
# Uncomment the next line if disk space is tight:
# rm -f "${DATA_DIR}/${ARCHIVE}" && echo "🗑 Removed archive to save space"

echo ""
echo "✅ Step 1 complete — data ready at ${DATA_DIR}/${DATASET}/"
