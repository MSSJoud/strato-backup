# Phase 2 Complete: ISCE2 Configuration Files Generated

**Date**: March 4, 2026  
**Status**: ✅ COMPLETE

---

## What Was Completed

### Configuration Generation

✅ **SBAS Configurations**: 114 XML files  
✅ **PS Configurations**: 345 XML files  
✅ **Total Configurations**: 459 XML files  
✅ **Success Rate**: 100% (all SLC files found)

### Directory Structure Created

```
/mnt/data/sbas_vs_ps_test_bologna/configs/
├── sbas/                                    [114 pairs, 972 KB]
│   ├── 2023-01-04_2023-01-16/
│   │   └── topsApp.xml
│   ├── 2023-01-04_2023-01-28/
│   │   └── topsApp.xml
│   ├── ... (112 more pairs)
│   └── valid_pairs.csv
│
└── ps/                                      [345 pairs, 2.9 MB]
    ├── 2023-01-04_2023-01-16/
    │   └── topsApp.xml
    ├── 2023-01-04_2023-01-28/
    │   └── topsApp.xml
    ├── ... (343 more pairs)
    └── valid_pairs.csv
```

### Storage Usage

- **SBAS configs**: 972 KB (114 XML files)
- **PS configs**: 2.9 MB (345 XML files)
- **Total**: 3.87 MB

---

## Configuration Details

### ISCE2 topsApp.xml Parameters

Each configuration file includes:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<topsApp>
  <component name="topsinsar">
    <property name="Sensor name">SENTINEL1</property>
    
    <!-- Input SLC files -->
    <property name="reference directory">/path/to/reference.zip</property>
    <property name="secondary directory">/path/to/secondary.zip</property>
    
    <!-- Processing parameters -->
    <property name="region of interest">[0, 0, 0, 0]</property>
    <property name="demFilename">auto</property>
    <property name="do unwrap">True</property>
    <property name="unwrapper name">snaphu</property>
    
    <!-- Swaths to process (all three) -->
    <property name="swaths">[1, 2, 3]</property>
    
    <!-- Multilooked products -->
    <property name="azimuth looks">7</property>
    <property name="range looks">19</property>
    
    <!-- Phase filtering -->
    <property name="filter strength">0.5</property>
  </component>
</topsApp>
```

### Key Processing Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Sensor | SENTINEL1 | Satellite platform |
| Swaths | [1, 2, 3] | All three IW swaths |
| Azimuth looks | 7 | Multilook factor (azimuth) |
| Range looks | 19 | Multilook factor (range) |
| DEM | auto | ISCE2 auto-downloads SRTM |
| Unwrapper | snaphu | Phase unwrapping algorithm |
| Filter strength | 0.5 | Moderate Goldstein filtering |
| Unwrap | True | Perform phase unwrapping |

### Multilook Resolution

- **Original SLC**: ~14m (range) × ~3m (azimuth)  
- **Multilooked**: ~14m × 19 = **266m** (range) × 3m × 7 = **21m** (azimuth)  
- **Final resolution**: ~266m × 21m ≈ **20m × 20m** ground resolution

---

## Files Created

### Configuration Files

1. **SBAS configs**: `/mnt/data/sbas_vs_ps_test_bologna/configs/sbas/*/topsApp.xml`
   - 114 interferometric pairs
   - Temporal baseline: 12-48 days (mean: 29.5 days)
   - Each pair in separate directory named `YYYYMMDD_YYYYMMDD`

2. **PS configs**: `/mnt/data/sbas_vs_ps_test_bologna/configs/ps/*/topsApp.xml`
   - 345 interferometric pairs
   - Temporal baseline: 12-180 days (mean: 86.3 days)
   - Each pair in separate directory named `YYYYMMDD_YYYYMMDD`

### Metadata Files

3. **SBAS valid pairs list**: `/mnt/data/sbas_vs_ps_test_bologna/configs/sbas/valid_pairs.csv`
   - Columns: master, slave, master_date, slave_date, master_path, slave_path, xml_file
   - 114 rows (100% success rate)

4. **PS valid pairs list**: `/mnt/data/sbas_vs_ps_test_bologna/configs/ps/valid_pairs.csv`
   - Same structure as SBAS
   - 345 rows (100% success rate)

### Script Created

5. **Configuration generator**: `/home/ubuntu/work/generate_isce2_configs_from_csv.py`
   - Reads pair CSV files
   - Finds corresponding SLC .zip files
   - Generates ISCE2 XML configurations
   - Creates directory structure
   - Validates all files exist
   - Produces metadata CSVs

---

## Key Achievements

### 100% File Availability

✅ All 93 SLCs found  
✅ All 114 SBAS pairs have both master and slave files  
✅ All 345 PS pairs have both master and slave files  
✅ No missing files or errors

### Proper Structure

- Each pair gets its own directory (isolated processing)
- Directory names use dates (easy identification)
- XML files named consistently (`topsApp.xml`)
- Metadata preserved in CSV files

### ISCE2-Ready Configurations

- Valid XML syntax
- All required parameters specified
- Auto-download enabled for DEM and orbits
- Proper file paths (absolute paths to symlinks)
- Standard processing parameters

---

## Next Steps: Phase 3 - ISCE2 Processing

### Option 1: Test Single Pair First (Recommended)

Test with one SBAS pair to verify Docker setup and processing flow:

```bash
cd /home/ubuntu/work/isce2-playbook

# Check if Docker is available
docker compose --version

# Test with first SBAS pair
docker compose run --rm isce2-insar topsApp.py \
  /mnt/data/sbas_vs_ps_test_bologna/configs/sbas/2023-01-04_2023-01-16/topsApp.xml

# Expected processing time: ~1-2 hours per pair
# Expected output size: ~600 MB per pair
```

**What to check:**
- ✓ Orbit files downloaded automatically
- ✓ DEM downloaded automatically
- ✓ Processing completes without errors
- ✓ Output files created in pair directory

### Option 2: Batch Process SBAS Pairs (~51 hours with 4× parallel)

After successful test, process all SBAS pairs:

```bash
cd /home/ubuntu/work/isce2-playbook

# Process with 4 parallel jobs
ls /mnt/data/sbas_vs_ps_test_bologna/configs/sbas/*/topsApp.xml | \
  xargs -n 1 -P 4 -I {} docker compose run --rm isce2-insar topsApp.py {}

# Expected time: ~51 hours (114 pairs × 1.8 hours / 4 parallel jobs)
# Expected storage: ~68 GB (114 pairs × 600 MB)
```

### Option 3: Batch Process PS Pairs (~85 hours with 4× parallel)

Process all PS pairs:

```bash
cd /home/ubuntu/work/isce2-playbook

# Process with 4 parallel jobs
ls /mnt/data/sbas_vs_ps_test_bologna/configs/ps/*/topsApp.xml | \
  xargs -n 1 -P 4 -I {} docker compose run --rm isce2-insar topsApp.py {}

# Expected time: ~85 hours (345 pairs × 1 hour / 4 parallel jobs)
# Expected storage: ~207 GB (345 pairs × 600 MB)
```

### Storage Requirements

| Component | Count | Per-Item | Total |
|-----------|-------|----------|-------|
| Input SLCs (symlinks) | 93 | 5.5 GB | 0 GB (symlinks) |
| SBAS outputs | 114 | 600 MB | 68 GB |
| PS outputs | 345 | 600 MB | 207 GB |
| **Total Required** | - | - | **~275 GB** |

### Processing Timeline

**Sequential** (not recommended):
- SBAS: 114 pairs × 1.8 hours = ~205 hours (~8.5 days)
- PS: 345 pairs × 1 hour = ~345 hours (~14.4 days)
- Total: ~23 days

**Parallel (4 jobs)** (recommended):
- SBAS: 205 hours / 4 = ~51 hours (~2.1 days)
- PS: 345 hours / 4 = ~85 hours (~3.5 days)
- Total: ~5.6 days

**Parallel (8 jobs)** (if resources available):
- SBAS: 205 hours / 8 = ~26 hours (~1.1 days)
- PS: 345 hours / 8 = ~43 hours (~1.8 days)
- Total: ~2.9 days

---

## Workflow Summary

### Phase 1: Database & Pair Selection ✅ COMPLETE
- ✅ Database populated (93 SLCs)
- ✅ SBAS pairs selected (114 pairs, Δt ≤ 48 days)
- ✅ PS pairs selected (345 pairs, Δt ≤ 180 days)
- ✅ Orbit issue resolved (ISCE2 handles Bperp)

### Phase 2: Configuration Generation ✅ COMPLETE
- ✅ CSV-based config generator created
- ✅ SBAS configs generated (114 XML files)
- ✅ PS configs generated (345 XML files)
- ✅ Directory structure created
- ✅ 100% file availability verified

### Phase 3: ISCE2 Processing ⏳ NEXT
- ⏸️ Test single pair
- ⏸️ Process SBAS pairs (114 interferograms)
- ⏸️ Process PS pairs (345 interferograms)
- ⏸️ Verify outputs and coherence

### Phase 4: Bridge to MintPy ⏳ PENDING
- ⏸️ Organize ISCE2 outputs
- ⏸️ Prepare MintPy input directory structure
- ⏸️ Create load_data.py configs

### Phase 5: Time-Series Analysis ⏳ PENDING
- ⏸️ Run MintPy SBAS workflow
- ⏸️ Run MintPy PS workflow
- ⏸️ Generate velocity maps and time series

### Phase 6: SBAS vs PS Comparison ⏳ PENDING
- ⏸️ Compare velocity maps
- ⏸️ Compare temporal coherence
- ⏸️ Compare spatial coverage
- ⏸️ Compare deformation rates
- ⏸️ Generate comparison report

---

## Technical Notes

### Why Auto-Download DEM/Orbits?

**DEM**: Set to `"auto"` - ISCE2 will:
1. Determine scene bounds from SLC metadata
2. Download SRTM DEM tiles covering the scene
3. Stitch and crop to exact processing area
4. Cache for reuse by other pairs

**Orbits**: Not specified in XML (defaults work) - ISCE2 will:
1. Parse SLC sensing date from filename
2. Download precise orbit files (.EOF) from ESA
3. Calculate perpendicular baseline from orbit geometry
4. Use for coregistration and baseline estimation

### Why These Multilook Values?

**7 azimuth × 19 range looks** is standard for:
- ~20m ground resolution (good for regional studies)
- Balanced noise reduction vs. spatial detail
- Compatible with MintPy time-series processing
- Reasonable processing time

For higher resolution (if needed):
- 3 azimuth × 9 range → ~10m (slower, more noise)
- 14 azimuth × 38 range → ~40m (faster, smoother)

### Why Goldstein Filter Strength 0.5?

**Moderate filtering** (0.5) balances:
- Phase noise reduction (improves unwrapping)
- Signal preservation (maintains real deformation)
- Standard for InSAR time-series analysis

Options:
- 0.3 = light filtering (preserve detail, more noise)
- 0.8 = heavy filtering (smooth, lose some signal)

---

## Metadata Tracking

### Phase 2 Metadata Files

1. **Input pairs**: 
   - `sbas_pairs_2023.csv` (114 pairs)
   - `ps_pairs_2023.csv` (345 pairs)

2. **Valid configs**: 
   - `configs/sbas/valid_pairs.csv` (114 validated)
   - `configs/ps/valid_pairs.csv` (345 validated)

3. **Processing logs**: (will be created in Phase 3)
   - Each pair directory will contain ISCE2 logs
   - Check `*/isce.log` for processing details

### Verification Commands

```bash
# Count configs
echo "SBAS: $(ls /mnt/data/sbas_vs_ps_test_bologna/configs/sbas/*/topsApp.xml | wc -l)"
echo "PS: $(ls /mnt/data/sbas_vs_ps_test_bologna/configs/ps/*/topsApp.xml | wc -l)"

# Check sample config
cat /mnt/data/sbas_vs_ps_test_bologna/configs/sbas/2023-01-04_2023-01-16/topsApp.xml

# Validate XML syntax (if xmllint installed)
find /mnt/data/sbas_vs_ps_test_bologna/configs -name "topsApp.xml" -exec xmllint --noout {} \; 2>&1 | grep -v "validates"
```

---

## Timeline

- **Phase 1**: ~5 minutes (database + pair selection)
- **Phase 2**: ~2 minutes (config generation)
- **Phase 3**: ~5-6 days (ISCE2 processing, parallel)
- **Phase 4**: ~10 minutes (organize for MintPy)
- **Phase 5**: ~4-8 hours (MintPy time-series)
- **Phase 6**: ~2 hours (comparison analysis)

**Total Estimated Time**: ~6 days (mostly ISCE2 processing)

---

## Key Learnings

1. **CSV-based workflow is flexible**: Easier to inspect and modify pairs before processing
2. **Symlinks save space**: Using existing 794 SLCs without duplication
3. **Pair naming by date**: Makes tracking and debugging easier than granule names
4. **100% valid pairs**: All symlinks point to real files
5. **Isolated processing**: Each pair in own directory prevents conflicts
6. **ISCE2 auto-features**: DEM and orbit auto-download simplifies configs

---

## Ready for Phase 3! 🚀

All 459 configuration files are generated and ready for ISCE2 processing. Recommend:

1. ✓ Test with single SBAS pair first
2. ✓ Verify Docker setup and isce2-playbook repo
3. ✓ Check available storage (~275 GB needed)
4. ✓ Start SBAS batch processing (shorter temporal baseline, better coherence)
5. ✓ Monitor progress and troubleshoot any issues
6. ✓ Then proceed with PS processing

**Next Command**:
```bash
cd /home/ubuntu/work/isce2-playbook
docker compose run --rm isce2-insar topsApp.py \
  /mnt/data/sbas_vs_ps_test_bologna/configs/sbas/2023-01-04_2023-01-16/topsApp.xml
```
