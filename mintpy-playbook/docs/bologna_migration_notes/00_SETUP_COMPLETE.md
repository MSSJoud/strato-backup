# Bologna SBAS vs PS Test - Setup Complete! ✅

**Date:** 2026-03-04  
**Status:** Ready for Processing

---

## 📊 What We Found

### Existing Data Discovery
✅ **794 valid Sentinel-1 SLCs** already downloaded in `/mnt/data/po_plain_italy/raw/slc/S1/ASC/path_15/`

**Coverage:**
- **680 SLCs (85.6%) cover Bologna region** (frames with acquisition time ~17:14:30-17:15:50)
- **Date range**: 2020-01-02 to 2026-01-24 (~6.1 years)
- **Temporal sampling**: 2.8 days average (very dense!)
- **Platforms**: Sentinel-1A (654 SLCs) + Sentinel-1B (140 SLCs)
- **Total storage**: 3.6 TB
- **Corrupted files**: 172 (0-byte or incomplete downloads)

### Selected Subset: 2023 Full Year
✅ **93 SLCs selected** for Bologna SBAS/PS comparison

**Subset Details:**
- **Date range**: 2023-01-04 to 2023-12-30 (360 days)
- **Platform**: Sentinel-1A only
- **Path**: 15 (ASCENDING)
- **Storage**: 510.6 GB
- **Expected SBAS pairs**: ~279 (Δt≤48d, B⊥≤100m)
- **Expected PS pairs**: ~465 (Δt≤180d, B⊥≤250m)

---

## 🔗 Setup Method: Symlinks (No Duplication!)

**Symlinks created**: 93 files  
**Source**: `/mnt/data/po_plain_italy/raw/slc/S1/ASC/path_15/`  
**Target**: `/mnt/data/sbas_vs_ps_test_bologna/data/safe/`

**Advantage**: No disk space wasted! Symlinks point to original files.

---

## 📁 Directory Structure

```
/mnt/data/sbas_vs_ps_test_bologna/
├── data/
│   └── safe/                          # 93 symlinked SLCs (2023)
├── configs/
│   ├── sbas/                          # SBAS configs (to be created)
│   └── ps/                            # PS configs (to be created)
├── outputs/
│   ├── sbas/                          # ISCE2 SBAS outputs
│   └── ps/                            # ISCE2 PS outputs
├── mintpy_input/
│   ├── sbas/                          # MintPy SBAS input
│   └── ps/                            # MintPy PS input
├── EXISTING_SLC_METADATA.csv          # All 794 SLCs metadata
├── EXISTING_SLC_BOLOGNA_SUBSET.csv    # 680 Bologna SLCs metadata
├── EXISTING_SLC_2023_SUBSET.csv       # 93 selected 2023 SLCs
├── SELECTED_SUBSET_2023_Full_Year.csv # Symlinked files list
└── COMPLETE_METADATA_TRACKER.md       # Full workflow tracker
```

---

## 🔐 Authentication Status

**Credentials exist**: ✅ Yes  
- `~/.netrc` configured
- `/home/ubuntu/work/credentials.py` configured

**Test download**: ⚠️ Authentication failed  
- Error: "Username or password is incorrect"
- **Impact**: None! We're using existing 2023 SLCs
- **If needed later**: Update credentials at NASA Earthdata (https://urs.earthdata.nasa.gov/)

---

## ✅ Completed Steps

- [x] Discovered existing SLC archive (794 valid files)
- [x] Inspected metadata and geographic coverage
- [x] Selected 2023 Bologna subset (93 SLCs)
- [x] Created symlinks to avoid duplication
- [x] Exported metadata to CSV
- [x] Tested authentication (credentials exist, may need update)

---

## 🚀 Next Steps: ISCE2 + MintPy Processing

### Phase 1: Populate Database & Select Pairs (~5 minutes)

```bash
cd /home/ubuntu/work

# 1. Create PostgreSQL database with SLC metadata
python granule_psql_database.py \
  --db_name bologna_2023 \
  --data_path /mnt/data/sbas_vs_ps_test_bologna/data/safe

# 2a. Select SBAS pairs (Δt≤48d, B⊥≤100m)
python select_s1_pairs_from_postgres.py \
  --db_name bologna_2023 \
  --bmax 100 \
  --tmax 48 \
  --output /mnt/data/sbas_vs_ps_test_bologna/configs/sbas/sbas_pairs_2023.csv

# 2b. Select PS pairs (Δt≤180d, B⊥≤250m)
python select_s1_pairs_from_postgres.py \
  --db_name bologna_2023 \
  --bmax 250 \
  --tmax 180 \
  --output /mnt/data/sbas_vs_ps_test_bologna/configs/ps/ps_pairs_2023.csv

# Expected results:
# - SBAS: ~279 pairs
# - PS: ~465 pairs
```

### Phase 2: Generate ISCE2 Configs (~10 minutes)

```bash
cd /home/ubuntu/work

# 3a. Generate ISCE2 XML configs for SBAS
python generate_topsApp_batch.py \
  --db_name bologna_2023 \
  --data_path /mnt/data/sbas_vs_ps_test_bologna/data/safe \
  --output_dir /mnt/data/sbas_vs_ps_test_bologna/configs/sbas \
  --bmax 100 \
  --tmax 48

# 3b. Generate ISCE2 XML configs for PS
python generate_topsApp_batch.py \
  --db_name bologna_2023 \
  --data_path /mnt/data/sbas_vs_ps_test_bologna/data/safe \
  --output_dir /mnt/data/sbas_vs_ps_test_bologna/configs/ps \
  --bmax 250 \
  --tmax 180

# This creates:
# - configs/sbas/DATE1_DATE2/topsApp.xml (×279)
# - configs/ps/DATE1_DATE2/topsApp.xml (×465)
```

### Phase 3: Process Interferograms with ISCE2 (~2-4 days parallel)

```bash
cd /home/ubuntu/work/isce2-playbook

# 4a. Process SBAS stack (parallel: 4× faster)
ls /mnt/data/sbas_vs_ps_test_bologna/configs/sbas/*/topsApp.xml | \
  xargs -n 1 -P 4 -I {} docker compose run --rm isce2-insar topsApp.py {}

# 4b. Process PS stack (parallel: 4× faster)
ls /mnt/data/sbas_vs_ps_test_bologna/configs/ps/*/topsApp.xml | \
  xargs -n 1 -P 4 -I {} docker compose run --rm isce2-insar topsApp.py {}

# Processing time estimate:
# - SBAS: ~51 hours (4× parallel) / ~205 hours (sequential)
# - PS: ~85 hours (4× parallel) / ~341 hours (sequential)
```

### Phase 4: Bridge to MintPy (~10 minutes)

```bash
cd /home/ubuntu/work/isce2-playbook

# 5a. Organize SBAS outputs for MintPy
./Scripts/prepare_for_mintpy.sh \
  /mnt/data/sbas_vs_ps_test_bologna/outputs/sbas/merged \
  /mnt/data/sbas_vs_ps_test_bologna/mintpy_input/sbas

# 5b. Organize PS outputs for MintPy
./Scripts/prepare_for_mintpy.sh \
  /mnt/data/sbas_vs_ps_test_bologna/outputs/ps/merged \
  /mnt/data/sbas_vs_ps_test_bologna/mintpy_input/ps
```

### Phase 5: MintPy Time-Series Analysis (~3-4 hours each)

```bash
cd /home/ubuntu/work/mintpy-playbook

# 6a. Run SBAS time-series
docker compose run --rm mintpy smallbaselineApp.py \
  --dir work/bologna_sbas \
  configs/bologna_sbas_mintpy.cfg

# 6b. Run PS time-series
docker compose run --rm mintpy smallbaselineApp.py \
  --dir work/bologna_ps \
  configs/bologna_ps_mintpy.cfg
```

### Phase 6: Compare Results (~2 hours)

```bash
cd /home/ubuntu/work/mintpy-playbook

# 7. Compare velocity maps
docker compose run --rm mintpy view.py work/bologna_sbas/velocity.h5 velocity -v -5 5
docker compose run --rm mintpy view.py work/bologna_ps/velocity.h5 velocity -v -5 5

# 8. Compare temporal coherence
docker compose run --rm mintpy view.py work/bologna_sbas/temporalCoherence.h5 -v 0 1
docker compose run --rm mintpy view.py work/bologna_ps/temporalCoherence.h5 -v 0 1

# 9. Extract time-series at test points
docker compose run --rm mintpy tsview.py work/bologna_sbas/timeseries_ERA5_ramp_demErr.h5
docker compose run --rm mintpy tsview.py work/bologna_ps/timeseries_ERA5_ramp_demErr.h5
```

---

## 📈 Expected Timeline (with 4× Parallelization)

| Phase | Task | Duration | Cumulative |
|-------|------|----------|------------|
| 1 | Database + Pair Selection | 5 min | 5 min |
| 2 | Generate Configs | 10 min | 15 min |
| 3 | ISCE2 SBAS Processing | 51 hrs | 51 hrs |
| 3 | ISCE2 PS Processing | 85 hrs | 85 hrs |
| 4 | Bridge to MintPy | 10 min | 85.25 hrs |
| 5 | MintPy SBAS Analysis | 3 hrs | 88.25 hrs |
| 5 | MintPy PS Analysis | 3 hrs | 91.25 hrs |
| 6 | Comparison | 2 hrs | 93.25 hrs |

**Total Time**: ~3.9 days (with 4× parallel processing)  
**Sequential Time**: ~10.4 days

---

## 📊 Expected Results: SBAS vs PS

### SBAS (Small Baseline Subset)
**Characteristics:**
- Dense network (~279 pairs)
- Short temporal baselines (≤48 days)
- Small perpendicular baselines (≤100m)
- Coherence threshold: 0.7

**Expected:**
- ✅ High pixel coverage (rural + urban)
- ✅ Good for distributed scatterers
- ⚠️ Lower precision (~5-10 mm/year)
- ⚠️ May have atmospheric artifacts

### PS (Persistent Scatterer)
**Characteristics:**
- Sparse network (~465 pairs)
- Long temporal baselines (≤180 days)
- Large perpendicular baselines (≤250m)
- Coherence threshold: 0.8

**Expected:**
- ✅ High precision (~2-5 mm/year on PSs)
- ✅ Good for stable scatterers (buildings)
- ⚠️ Lower pixel coverage (urban-focused)
- ⚠️ May miss distributed targets

### Comparison Questions to Answer:
1. How much better is PS precision on stable targets?
2. How much more coverage does SBAS provide?
3. Are subsidence patterns consistent between methods?
4. Which method better resolves seasonal signals?
5. What is the precision-coverage trade-off quantitatively?

---

## 🔍 Quality Metrics to Track

### Per Method:
- Temporal coherence map (pixel reliability)
- Velocity standard error
- Number of pixels with coherence > 0.7 (SBAS) or 0.85 (PS)
- Mean velocity over Bologna
- Velocity correlation coefficient (SBAS vs PS)

### Atmospheric Corrections (both methods):
- ERA5 tropospheric delay correction
- Linear orbital ramp removal
- DEM error correction
- Solid Earth tides (minor contribution)

---

## 📋 Metadata Tracking

**Stage 1**: ✅ SLC Metadata (COMPLETE)
- File: `EXISTING_SLC_METADATA.csv`
- File: `EXISTING_SLC_2023_SUBSET.csv`

**Stage 2**: Pair Metadata (PENDING)
- Will generate: `02_SBAS_PAIRS_METADATA.csv`
- Will generate: `02_PS_PAIRS_METADATA.csv`

**Stage 3**: Interferogram Metadata (PENDING)
- Will generate: `03_SBAS_INTERFEROGRAM_METADATA.csv`
- Will generate: `03_PS_INTERFEROGRAM_METADATA.csv`

**Stage 4**: Time-Series Metadata (PENDING)
- Will generate: `04_TIMESERIES_METADATA.csv`
- Will generate: `04_COMPARISON_REPORT.txt`

---

## 🎯 Summary

✅ **You have everything needed to start ISCE2 processing!**

**No download required** - 93 Bologna SLCs from 2023 are ready via symlinks.

**Next immediate action**: Run Phase 1 commands above to populate database and select pairs.

**Authentication note**: Credentials exist but may need updating if you want to download additional SLCs later. For now, focus on processing existing 2023 data.

---

**Files ready:**
- ✅ 93 SLC symlinks in `/mnt/data/sbas_vs_ps_test_bologna/data/safe/`
- ✅ MintPy configs in `/home/ubuntu/work/mintpy-playbook/configs/`
- ✅ Bridge scripts in `/home/ubuntu/work/isce2-playbook/Scripts/`
- ✅ Metadata CSVs for tracking

**Processing will generate "good" time-series with:**
- ✅ Atmospheric correction (ERA5)
- ✅ DEM error correction
- ✅ Orbital ramp removal
- ✅ Spatial referencing
- ✅ Ready for GPS validation

🚀 **Ready to process!**
