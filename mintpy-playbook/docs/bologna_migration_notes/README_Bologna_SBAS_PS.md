# Bologna SBAS vs PS Comparison Test

## Objective
Compare **SBAS** (Small Baseline Subset) versus **PS** (Persistent Scatterer) InSAR time-series methods using the same dataset from Bologna, Italy.

## Test Area: Bologna, Italy
- **Location:** 44.3-44.7°N, 11.1-11.6°E
- **Coverage:** ~45 km × 45 km (~2,000 km²)
- **Characteristics:** 
  - Urban area (excellent PS targets: buildings, infrastructure)
  - Known subsidence issues (groundwater extraction)
  - Moderate topography (Po Valley, Apennines foothills)
- **Why Bologna:** Ideal for testing both methods due to urban + natural scatterers

## Directory Structure

### Storage Directory: /mnt/data/sbas_vs_ps_test_bologna/
**Purpose:** Raw data downloads and processed interferogram outputs (large files)

```
/mnt/data/sbas_vs_ps_test_bologna/
├── bologna_config.txt           # Configuration parameters
├── download_slcs.py              # SLC download script
├── README.md                     # This file
│
├── data/                         # Raw input data (~50-70 GB)
│   ├── safe/                     # Sentinel-1 SLC files (.SAFE)
│   ├── orbit/                    # Orbit files (POEORB/RESORB)
│   └── aux/                      # Auxiliary data (calibration, etc.)
│
├── configs/                      # Processing configurations
│   ├── sbas/                     # SBAS pair selection & ISCE2 XMLs
│   │   └── pairs_sbas.csv        # SBAS pairs (Δt≤48d, B⊥≤100m)
│   └── ps/                       # PS pair selection & ISCE2 XMLs
│       └── pairs_ps.csv          # PS pairs (Δt≤180d, B⊥≤250m)
│
├── outputs/                      # Processed interferograms (~100-200 GB)
│   ├── sbas/                     # SBAS interferogram stack
│   │   └── merged/               # ISCE2 outputs (unwrapped, coherence, geom)
│   └── ps/                       # PS interferogram stack
│       └── merged/               # ISCE2 outputs (unwrapped, coherence, geom)
│
└── mintpy_input/                 # MintPy input data (organized from ISCE2)
    ├── sbas/                     # SBAS stack prepared for MintPy
    └── ps/                       # PS stack prepared for MintPy
```

### Working Directory: /home/ubuntu/work/mintpy-playbook/
**Purpose:** MintPy processing workspace (configs, temporary files, analysis outputs)

```
/home/ubuntu/work/mintpy-playbook/
├── docker-compose.yml            # MintPy container config
├── configs/
│   ├── bologna_sbas_mintpy.cfg  # SBAS processing config
│   └── bologna_ps_mintpy.cfg    # PS processing config
│
└── work/                         # MintPy working directories
    ├── bologna_sbas/             # SBAS time-series analysis
    │   ├── inputs/ → /mnt/data/.../mintpy_input/sbas/  (symlink)
    │   ├── ifgramStack.h5        # Loaded interferograms
    │   ├── timeseries*.h5        # Time-series products
    │   ├── velocity.h5           # Velocity map
    │   └── pic/                  # Figures
    └── bologna_ps/               # PS time-series analysis
        ├── inputs/ → /mnt/data/.../mintpy_input/ps/  (symlink)
        ├── ifgramStack.h5
        ├── timeseries*.h5
        ├── velocity.h5
        └── pic/
```

## Workflow

### Phase 1: Data Acquisition (1-4 hours)

```bash
# 1. Download SLCs
cd /mnt/data/sbas_vs_ps_test_bologna
python3 download_slcs.py

# Expected: ~30 SLCs (2023 data)
# Size: ~50-70 GB
# Time: 2-4 hours (depends on bandwidth)
```

### Phase 2: Pair Selection (5 minutes)

```bash
# 2a. SBAS pair selection
cd /home/ubuntu/work
python3 select_s1_pairs_from_postgres.py \
  --db_name bologna_slcs \
  --bmax 100 \
  --tmax 48 \
  --output /mnt/data/sbas_vs_ps_test_bologna/configs/sbas/pairs_sbas.csv

# Expected: ~150-250 pairs

# 2b. PS pair selection
python3 select_s1_pairs_from_postgres.py \
  --db_name bologna_slcs \
  --bmax 250 \
  --tmax 180 \
  --output /mnt/data/sbas_vs_ps_test_bologna/configs/ps/pairs_ps.csv

# Expected: ~80-120 pairs
```

### Phase 3: ISCE2 Processing (1-3 days)

```bash
# 3a. Process SBAS stack
python3 generate_topsApp_batch.py \
  --db_name bologna_slcs \
  --data_path /mnt/data/sbas_vs_ps_test_bologna/data/safe \
  --output_dir /mnt/data/sbas_vs_ps_test_bologna/configs/sbas \
  --bmax 100 \
  --tmax 48

# Process all pairs (parallel recommended)
for xml in /mnt/data/sbas_vs_ps_test_bologna/configs/sbas/*/topsApp.xml; do
  docker compose run --rm isce2-insar topsApp.py $xml
done

# 3b. Process PS stack
python3 generate_topsApp_batch.py \
  --db_name bologna_slcs \
  --data_path /mnt/data/sbas_vs_ps_test_bologna/data/safe \
  --output_dir /mnt/data/sbas_vs_ps_test_bologna/configs/ps \
  --bmax 250 \
  --tmax 180

# Process all pairs
for xml in /mnt/data/sbas_vs_ps_test_bologna/configs/ps/*/topsApp.xml; do
  docker compose run --rm isce2-insar topsApp.py $xml
done
```

### Phase 4: Bridge to MintPy (10 minutes)

```bash
# 4a. Prepare SBAS data for MintPy
cd /home/ubuntu/work/isce2-playbook
./Scripts/prepare_for_mintpy.sh \
  /mnt/data/sbas_vs_ps_test_bologna/outputs/sbas/merged \
  /mnt/data/sbas_vs_ps_test_bologna/mintpy_input/sbas

# 4b. Prepare PS data for MintPy
./Scripts/prepare_for_mintpy.sh \
  /mnt/data/sbas_vs_ps_test_bologna/outputs/ps/merged \
  /mnt/data/sbas_vs_ps_test_bologna/mintpy_input/ps

# 4c. Create MintPy working directories
cd /home/ubuntu/work/mintpy-playbook
mkdir -p work/{bologna_sbas,bologna_ps}
ln -s /mnt/data/sbas_vs_ps_test_bologna/mintpy_input/sbas work/bologna_sbas/inputs
ln -s /mnt/data/sbas_vs_ps_test_bologna/mintpy_input/ps work/bologna_ps/inputs
```

### Phase 5: MintPy Time-Series (2-4 hours each)

```bash
# 5a. SBAS time-series
cd /home/ubuntu/work/mintpy-playbook
docker compose run --rm mintpy smallbaselineApp.py \
  --dir work/bologna_sbas \
  configs/bologna_sbas_mintpy.cfg

# Output: work/bologna_sbas/velocity.h5, timeseries_ERA5_ramp_demErr.h5

# 5b. PS time-series  
docker compose run --rm mintpy smallbaselineApp.py \
  --dir work/bologna_ps \
  configs/bologna_ps_mintpy.cfg

# Output: work/bologna_ps/velocity.h5, timeseries_ERA5_ramp_demErr.h5
```

### Phase 6: Comparison & Analysis

```bash
# Compare velocity maps
# Compare temporal coherence
# Compare displacement time-series at selected points
# Analyze differences in coverage and precision
```

## Expected Timeline

| Phase | Task | SBAS Time | PS Time | Notes |
|-------|------|-----------|---------|-------|
| 1 | Download SLCs | 2-4 hours | (same) | ~30 SLCs, 50-70 GB |
| 2 | Pair selection | 2 min | 2 min | Database query |
| 3 | ISCE2 processing | 1-2 days | 0.5-1 day | 200 vs 100 pairs |
| 4 | Bridge to MintPy | 5 min | 5 min | Data organization |
| 5 | MintPy analysis | 2-4 hours | 2-4 hours | Time-series inversion |
| **TOTAL** | **2-3 days** | **1.5-2 days** | **Parallel possible** |

## Key Comparisons

### Network Characteristics

| Metric | SBAS | PS |
|--------|------|-----|
| Temporal baseline | ≤ 48 days | ≤ 180 days |
| Perpendicular baseline | ≤ 100 m | ≤ 250 m |
| Number of pairs | 150-250 | 80-120 |
| Network redundancy | High (triangles) | Lower (sparse) |

### Expected Results

| Aspect | SBAS | PS |
|--------|------|-----|
| **Pixel density** | High (all coherent areas) | Lower (only stable scatterers) |
| **Best in** | Vegetated areas, broad deformation | Urban areas, point targets |
| **Noise level** | Lower (multilooked) | Higher (single look) |
| **Unwrapping** | Easier (high coherence) | Harder (lower coherence) |
| **Atmospheric errors** | Similar (both corrected) | Similar (both corrected) |
| **Precision** | ~5-10 mm/year | ~2-5 mm/year (on PSs) |

## Quality Metrics to Compare

1. **Temporal coherence maps** - Which pixels are reliable?
2. **Velocity maps** - Do they show same subsidence patterns?
3. **Time-series at test points** - Urban vs rural comparison
4. **Phase closure** - Network unwrapping errors
5. **Atmospheric correction effectiveness** - Before/after comparison

## Scientific Questions

1. Does SBAS provide better coverage in rural areas?
2. Does PS provide better precision in urban areas?
3. Are subsidence patterns consistent between methods?
4. Which method better resolves seasonal signals?
5. What is the trade-off between coverage and precision?

## Data Products

Both methods will produce:
- `velocity.h5` - Mean velocity (mm/year)
- `timeseries_ERA5_ramp_demErr.h5` - Corrected time-series
- `temporalCoherence.h5` - Pixel reliability
- `maskTempCoh.h5` - Quality mask

Compare these products side-by-side for scientific analysis.

---

## Quick Start Commands

```bash
# Start here!
cd /mnt/data/sbas_vs_ps_test_bologna

# 1. Check configuration
cat bologna_config.txt

# 2. Download data
python3 download_slcs.py

# 3. Monitor download
watch -n 60 'ls -lh data/safe/*.zip | wc -l'

# 4. Once complete, proceed to Phase 2 (pair selection)
```

## Contact & Support

For issues or questions:
- ISCE2: https://github.com/isce-framework/isce2
- MintPy: https://github.com/insarlab/MintPy
- ASF Data: https://search.asf.alaska.edu

---

**Status:** Ready to download! Run `python3 download_slcs.py` to begin.
