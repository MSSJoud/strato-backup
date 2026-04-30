# Phase 1 Complete: Database & Pair Selection ✅

**Date:** March 4, 2026  
**Status:** Database populated, pairs selected (temporal baseline)

---

## ✅ What Was Completed

### 1. Database Population
- **PostgreSQL database**: `bologna_2023` created
- **Total SLCs**: 93 (from 2023-01-04 to 2023-12-30)
- **Unique dates**: 31 acquisition dates
- **Platform**: Sentinel-1A, Path 15, ASCENDING
- **Script**: `populate_slc_database.py` (FIXED date conversion bug)

### 2. Interferometric Pair Selection  
**Updated approach**: Temporal baseline only (explained below)

#### SBAS Pairs
- **Total**: 114 pairs
- **Temporal baseline**: 12-48 days (mean: 29.5 days)
- **File**: `sbas_pairs_2023.csv`

#### PS Pairs
- **Total**: 345 pairs
- **Temporal baseline**: 12-180 days (mean: 86.3 days)
- **File**: `ps_pairs_2023.csv`

---

## ⚠️ IMPORTANT: Orbit Issue Resolved

### The Problem
**Original approach was INCORRECT:**
- Script used orbit **numbers** (e.g., 46637, 46812) as perpendicular baseline
- Orbit numbers are just sequential IDs, NOT spatial baselines
- This resulted in unrealistic Bperp values (175-2625m)

### The Solution
**Updated approach (CORRECT):**
1. **Pair selection**: Based on **temporal baseline only**
2. **Perpendicular baseline**: Will be calculated by ISCE2 during processing
3. **Orbit files**: Must be downloaded separately (precise .EOF files)

### Why This Works
- **ISCE2's stackSentinel** automatically:
  - Downloads missing orbit files
  - Calculates precise perpendicular baselines from orbit geometry
  - Filters pairs based on actual Bperp during processing
  - Handles baseline refinement iteratively

---

## 📊 Updated Pair Statistics

### SBAS (Small Baseline Subset)
```
Constraint:  Temporal ≤ 48 days
Pairs:       114
Date range:  31 unique acquisition dates
Network:     Dense, short timeframes
```

**Pair format:**
```csv
master,slave,master_date,slave_date,path,orbit_diff,delta_days
S1A_IW_SLC__1SDV_20230104T171448_...,S1A_IW_SLC__1SDV_20230116T171448_...,2023-01-04,2023-01-16,15,175,12
```

### PS (Persistent Scatterer)
```
Constraint:  Temporal ≤ 180 days
Pairs:       345
Date range:  31 unique acquisition dates
Network:     Sparse, longer timeframes
```

---

## 🛰 Orbit File Download (Required)

### Why Orbit Files Are Needed
Precise orbit files (.EOF) provide:
- Satellite position at each time step (cm-level accuracy)
- Velocity vectors
- Enable perpendicular baseline calculation
- Required for accurate coregistration in ISCE2

### Option 1: ISCE2 Automatic Download (Recommended)
ISCE2's `stackSentinel.py` will download orbits automatically when processing:
```bash
# ISCE2 downloads orbits during stackSentinel
# No manual action needed!
```

### Option 2: Manual Download (Optional)
If you want to pre-download orbits:

**Using sentineleof (needs installation):**
```bash
pip install sentineleof

python download_orbits_for_slcs.py \
  --slc-dir /mnt/data/sbas_vs_ps_test_bologna/data/safe \
  --orbit-dir /mnt/data/sbas_vs_ps_test_bologna/data/orbit
```

**Using ISCE2 fetchOrbit.py (in Docker):**
```bash
docker compose run --rm isce2-insar bash

# Inside container:
for slc in /data/safe/*.zip; do
    fetchOrbit.py -i "$slc" -o /data/orbit
done
```

---

## 🔧 Scripts Updated

### Fixed Scripts
1. **`populate_slc_database.py`** ✅
   - Fixed date conversion (was storing as 1970-01-01)
   - Now correctly parses YYYYMMDD format (e.g., 20230104)
   - Added proper error handling

2. **`select_pairs_by_date.py`** ✅
   - Removed incorrect Bperp filtering
   - Now only uses temporal baseline
   - Clearly documents that orbit# ≠ Bperp
   - Groups SLCs by acquisition date (avoids same-day pairs)
   - Added warning messages about orbit files

### New Scripts
3. **`download_orbits_for_slcs.py`** 🆕
   - Downloads precise orbit .EOF files
   - Uses sentineleof package
   - Fallback instructions for ISCE2 fetchOrbit.py

---

## 📁 Files Created

```
/home/ubuntu/work/
├── populate_slc_database.py         - Database population (FIXED)
├── select_pairs_by_date.py          - Pair selection (UPDATED)
├── download_orbits_for_slcs.py      - Orbit download (NEW)
├── sbas_pairs_2023.csv              - 114 SBAS pairs
└── ps_pairs_2023.csv                - 345 PS pairs

PostgreSQL:
└── bologna_2023 database
    └── slc_data table (93 rows)
```

---

## 🚀 Next Steps: Phase 2

### Generate ISCE2 Configuration Files

You have the pair lists ready. Next phase:

```bash
# For SBAS stack
python generate_topsApp_batch.py \
  --csv sbas_pairs_2023.csv \
  --data_path /mnt/data/sbas_vs_ps_test_bologna/data/safe \
  --output_dir /mnt/data/sbas_vs_ps_test_bologna/configs/sbas

# For PS stack
python generate_topsApp_batch.py \
  --csv ps_pairs_2023.csv \
  --data_path /mnt/data/sbas_vs_ps_test_bologna/data/safe \
  --output_dir /mnt/data/sbas_vs_ps_test_bologna/configs/ps
```

This will generate XML config files for ISCE2 topsStack processing.

---

## 📝 Key Learnings

### What We Fixed:
1. ✅ **Date conversion bug**: PostgreSQL was storing all dates as 1970-01-01
2. ✅ **Orbit number misconception**: Orbit numbers (46637, etc.) are NOT perpendicular baselines
3. ✅ **Bperp calculation**: Requires precise orbit files, handled by ISCE2
4. ✅ **Same-day pairs**: Script now groups by date to avoid processing multiple frames from same acquisition

### What ISCE2 Will Handle:
- Download missing orbit files automatically
- Calculate precise perpendicular baselines from orbit geometry
- Filter pairs based on actual Bperp thresholds
- Refine baselines iteratively during coregistration

---

## ⏱️ Phase 1 Timeline

- Database creation: ~1 minute
- Pair selection (SBAS): ~1 minute
- Pair selection (PS): ~1 minute
- **Total Phase 1**: ~5 minutes

**Phase 1 Status**: ✅ COMPLETE

Ready for Phase 2: ISCE2 config generation!
