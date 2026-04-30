# 🌋 MintPy Docker Playbook

**A complete, reproducible InSAR time-series analysis workflow using MintPy in Docker.**

This project packages everything you need to run a full MintPy (Miami InSAR Time-series software in Python) analysis — from downloading sample interferogram data to producing velocity maps and time-series visualizations — inside a Docker container with zero local dependency management.

## What This Does

The playbook runs the **Fernandina Volcano (Galápagos, Ecuador)** sample dataset through MintPy's complete `smallbaselineApp.py` pipeline, which includes 17 processing steps:

| # | Step | Description |
|---|------|-------------|
| 1 | `load_data` | Load interferogram stack into HDF5 format |
| 2 | `modify_network` | Remove unwanted interferograms based on temporal/spatial baseline |
| 3 | `reference_point` | Select reference pixel with highest spatial coherence |
| 4 | `quick_overview` | Generate quick assessment of average velocity and temporal coherence |
| 5 | `correct_unwrap_error` | Detect and correct phase unwrapping errors |
| 6 | `invert_network` | Invert interferogram network → displacement time-series |
| 7 | `correct_LOD` | Correct local oscillator drift (Envisat only) |
| 8 | `correct_SET` | Correct solid Earth tides |
| 9 | `correct_troposphere` | Correct tropospheric delay (ERA5 atmospheric model) |
| 10 | `deramp` | Remove phase ramps (orbital errors) |
| 11 | `correct_topography` | Correct DEM errors |
| 12 | `residual_RMS` | Compute residual RMS for quality assessment |
| 13 | `reference_date` | Select reference date for time-series |
| 14 | `velocity` | Estimate linear displacement velocity |
| 15 | `geocode` | Geocode results from radar to geographic coordinates |
| 16 | `google_earth` | Generate Google Earth KMZ files |
| 17 | `hdfeos5` | Export results to HDF-EOS5 format |

After the main pipeline, additional scripts run post-processing analysis and generate publication-quality figures.

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed and running
- ~5 GB free disk space (sample data + processing outputs)
- Internet connection (for downloading sample data)

### One-Command Run

```bash
git clone <this-repo>
cd mintpy-docker-playbook
make run
```

Or without `make`:

```bash
docker compose up --build
```

### Step-by-Step Run

```bash
# 1. Build the Docker image
docker compose build

# 2. Download sample data only
docker compose run --rm mintpy bash /workspace/scripts/01_download_data.sh

# 3. Run full pipeline
docker compose run --rm mintpy bash /workspace/scripts/02_run_pipeline.sh

# 4. Run post-processing analysis
docker compose run --rm mintpy bash /workspace/scripts/03_post_analysis.sh

# 5. Generate figures
docker compose run --rm mintpy python /workspace/scripts/04_generate_figures.py
```

### Bologna Subset Run (SBAS/PS on /mnt/data)

These scripts now support Bologna paths directly.

```bash
# SBAS MintPy run
docker compose run --rm -e PROJECT_DIR=/mnt/data/sbas_vs_ps_test_bologna -e STACK_TYPE=sbas mintpy \
    bash /workspace/scripts/02_run_pipeline.sh

# PS MintPy run
docker compose run --rm -e PROJECT_DIR=/mnt/data/sbas_vs_ps_test_bologna -e STACK_TYPE=ps mintpy \
    bash /workspace/scripts/02_run_pipeline.sh

# Post-analysis for SBAS/PS
docker compose run --rm -e PROJECT_DIR=/mnt/data/sbas_vs_ps_test_bologna -e STACK_TYPE=sbas mintpy \
    bash /workspace/scripts/03_post_analysis.sh
docker compose run --rm -e PROJECT_DIR=/mnt/data/sbas_vs_ps_test_bologna -e STACK_TYPE=ps mintpy \
    bash /workspace/scripts/03_post_analysis.sh
```

### Interactive Mode (Jupyter)

```bash
docker compose up jupyter
# Open http://localhost:8888 in your browser
```

### Interactive Shell

```bash
docker compose run --rm mintpy bash
# Now you're inside the container with MintPy ready to use
```

---

## Project Structure

```
mintpy-docker-playbook/
├── README.md                          # This file
├── Dockerfile                         # Custom image extending official MintPy
├── docker-compose.yml                 # Service definitions
├── Makefile                           # Convenience commands
├── .env                               # Environment variables
├── config/
│   └── FernandinaSenDT128.txt         # MintPy template for sample dataset
├── scripts/
│   ├── 01_download_data.sh            # Download Fernandina sample data from Zenodo
│   ├── 02_run_pipeline.sh             # Run complete smallbaselineApp pipeline
│   ├── 03_post_analysis.sh            # Post-processing: info, view, tsview, etc.
│   ├── 04_generate_figures.py         # Python script for publication figures
│   ├── 05_step_by_step_pipeline.sh    # Run each step individually with logging
│   └── entrypoint.sh                  # Docker entrypoint
├── notebooks/
│   └── mintpy_interactive_analysis.ipynb  # Jupyter notebook for interactive work
└── docs/
    └── WORKFLOW_GUIDE.md              # Detailed explanation of every step
```

---

## Output Structure

After a successful run, the `data/` directory (mounted volume) will contain:

```
data/FernandinaSenDT128/mintpy/
├── inputs/                   # Loaded HDF5 data
│   ├── ifgramStack.h5        # Interferogram stack
│   ├── geometryRadar.h5      # Geometry in radar coordinates
│   └── geometryGeo.h5        # Geometry in geographic coordinates
├── timeseries.h5             # Raw displacement time-series
├── timeseries_*.h5           # Corrected time-series (various corrections)
├── temporalCoherence.h5      # Temporal coherence map
├── velocity.h5               # Estimated velocity map
├── geo/                      # Geocoded results
├── pic/                      # Generated figures (PNG)
├── Google Earth/              # KMZ files
└── S1_IW12_128_0593_0597_*   # HDF-EOS5 file
```

---

## Customization

### Using Your Own Data

1. Place your interferogram stack in the `data/` directory
2. Copy and edit the template file in `config/`:
   ```bash
   cp config/FernandinaSenDT128.txt config/MyDataset.txt
   # Edit paths and parameters in MyDataset.txt
   ```
3. Run: `docker compose run --rm mintpy smallbaselineApp.py /workspace/config/MyDataset.txt`

### Available Sample Datasets

| Dataset | Area | Sensor | Zenodo Record |
|---------|------|--------|---------------|
| FernandinaSenDT128 | Galápagos, Ecuador | Sentinel-1 | [3952953](https://zenodo.org/record/3952953) |
| SanFranSenDT42 | San Francisco, USA | Sentinel-1 | [4265413](https://zenodo.org/record/4265413) |
| WellsEnvD2T399 | Wells, Nevada | Envisat | [3952950](https://zenodo.org/record/3952950) |
| KujuAlosAT422F650 | Kuju, Japan | ALOS | [3952917](https://zenodo.org/record/3952917) |

Edit `.env` to switch datasets.

---

## References

- Yunjun, Z., Fattahi, H., and Amelung, F. (2019), Small baseline InSAR time series analysis: Unwrapping error correction and noise reduction, *Computers & Geosciences*, 133, 104331.
- MintPy Documentation: https://mintpy.readthedocs.io
- MintPy GitHub: https://github.com/insarlab/MintPy

---

## License

This playbook is MIT licensed. MintPy itself is licensed under its own terms — see the [MintPy repository](https://github.com/insarlab/MintPy/blob/main/LICENSE).
