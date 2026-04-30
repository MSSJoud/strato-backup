# Bologna SBAS vs PS Test - Complete Metadata Tracking

**Test ID:** Bologna_2023_SBAS_PS_Comparison  
**Created:** 2026-03-04  
**Location:** Bologna, Italy (44.3-44.7°N, 11.1-11.6°E)

---

## ━━━ STAGE 1: SLC ACQUISITION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Area of Interest Summary
- **Location:** Bologna, Italy (Urban + Po Valley)
- **Coordinates:** 44.30-44.70°N, 11.10-11.60°E
- **Coverage:** ~2,000 km² (45 km × 45 km)
- **Center Point:** 45.3343°N, 9.5462°E
- **Terrain:** Po Valley plains + Apennines foothills
- **Landcover:** Urban (Bologna city) + Agricultural + Hills
- **Known Phenomena:** Urban subsidence from groundwater extraction

###  SLC Acquisition Details
```
Total SLCs Found:       91 acquisitions
Time Period:            2023-01-04 to 2023-12-30
Time Span:              360 days (~12 months)
Temporal Sampling:      ~4 days average interval

Satellites:
  • Sentinel-1A:        91 acquisitions (100%)
  
Paths/Tracks:
  • Path 15:            62 acquisitions (68%)
  • Path 117:           29 acquisitions (32%)
  
Orbit Direction:        ASCENDING
Beam Mode:              IW (Interferometric Wide Swath)
Polarization:           VV+VH (Dual-pol)
```

### Data Volume
```
Per SLC:                ~5.4 GB
Total SLCs:             491 GB
SBAS Interferograms:    ~136 GB (273 pairs × 500 MB)
PS Interferograms:      ~91 GB (182 pairs × 500 MB)
MintPy Processing:      ~10 GB
─────────────────────────────────────────────────
TOTAL STORAGE REQUIRED: ~729 GB
```

### Timeline Estimate
```
Phase 1 - SLC Download:         ~49 hours (491 GB @ 10 GB/hr)
Phase 2 - Pair Selection:       ~5 minutes
Phase 3 - ISCE2 Processing:     
  • SBAS:                       ~8.5 days (sequential) / ~2.1 days (4× parallel)
  • PS:                         ~14.2 days (sequential) / ~3.6 days (4× parallel)
Phase 4 - Bridge to MintPy:     ~10 minutes
Phase 5 - MintPy Time-Series:   ~2-4 hours each (SBAS + PS)
─────────────────────────────────────────────────
TOTAL:                          ~25 days (sequential) / ~5.8 days (parallel)
```

### Status
- [x] Search completed: 91 SLCs found
- [x] Metadata exported: `01_SLC_METADATA_20260304_100018.csv`
- [ ] Download initiated
- [ ] Download completed

---

## ━━━ STAGE 2: PAIR SELECTION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Expected Pair Statistics

#### SBAS (Small Baseline Subset)
```
Constraints:
  • Max Temporal Baseline:      48 days
  • Max Perpendicular Baseline:  100 meters
  
Expected Network:
  • Estimated Pairs:            ~273
  • Network Type:                Dense, redundant (many triangles)
  • Connections per SLC:         ~3
  • Processing Time:             ~205 hours sequential / ~51 hours parallel
```

#### PS (Persistent Scatterer)
```
Constraints:
  • Max Temporal Baseline:      180 days  
  • Max Perpendicular Baseline:  250 meters
  
Expected Network:
  • Max Possible Pairs:          4,095 (all combinations)
  • Estimated After Filtering:   ~455
  • Network Type:                Sparse, star-like
  • Connections per SLC:         ~5
  • Processing Time:             ~341 hours sequential / ~85 hours parallel
```

### Status
- [ ] SLCs loaded into PostgreSQL database
- [ ] SBAS pairs selected
- [ ] PS pairs selected
- [ ] Baseline plots generated
- [ ] Pair metadata exported

**Files to be created:**
- `02a_SBAS_PAIRS_METADATA.csv` - SBAS pair list with baselines
- `02b_PS_PAIRS_METADATA.csv` - PS pair list with baselines
- `02a_sbas_network_plot.png` - SBAS baseline plot
- `02b_ps_network_plot.png` - PS baseline plot

---

## ━━━ STAGE 3: INTERFEROGRAM GENERATION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### ISCE2 Processing Outputs (Per Interferogram)

**Expected Files:**
```
/mnt/data/sbas_vs_ps_test_bologna/outputs/[sbas|ps]/merged/interferograms/DATE1_DATE2/
├── filt_topophase.unw.geo          - Unwrapped phase (GeoTIFF)
├── filt_topophase.unw.geo.cor      - Coherence (GeoTIFF)
├── filt_topophase.unw.conncomp     - Connected components
├── filt_topophase.flat.geo         - Flattened interferogram
└── metadata.txt                    - Processing metadata
```

**Geometry Files (Shared):**
```
/mnt/data/sbas_vs_ps_test_bologna/outputs/[sbas|ps]/merged/geom_reference/
├── lat.rdr     - Latitude grid
├── lon.rdr     - Longitude grid
├── hgt.rdr     - Height (DEM)
└── los.rdr     - Line-of-sight geometry
```

### Quality Metrics to Track

#### Per Interferogram:
- Temporal baseline (days)
- Perpendicular baseline (meters)
- Mean coherence
- Coherence std dev
- Unwrapped area percentage
- Number of connected components
- Processing status (success/failure)
- Processing time

#### Per Method (SBAS vs PS):
- Total interferograms processed
- Success rate
- Mean coherence across stack
- Mean unwrapped area
- Total processing time

### Status
- [ ] ISCE2 batch configs generated
- [ ] SBAS processing initiated
- [ ] SBAS processing completed
- [ ] PS processing initiated
- [ ] PS processing completed
- [ ] Quality metrics computed

**Files to be created:**
- `03a_SBAS_INTERFEROGRAM_METADATA.csv` - Per-interferogram quality metrics
- `03b_PS_INTERFEROGRAM_METADATA.csv` - Per-interferogram quality metrics
- `03a_sbas_coherence_summary.png` - Coherence distribution
- `03b_ps_coherence_summary.png` - Coherence distribution

---

## ━━━ STAGE 4: MINTPY INPUT PREPARATION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Data Organization

**SBAS Input:**
```
/mnt/data/sbas_vs_ps_test_bologna/mintpy_input/sbas/
├── geometry/
│   ├── lat.rdr
│   ├── lon.rdr
│   ├── hgt.rdr
│   └── los.rdr
├── interferograms/
│   ├── 20230104_20230116/
│   │   ├── filt_topophase.unw.geo
│   │   ├── filt_topophase.unw.geo.cor
│   │   └── filt_topophase.unw.conncomp
│   └── ... (~273 pairs)
└── file_list.txt
```

**PS Input:**
```
/mnt/data/sbas_vs_ps_test_bologna/mintpy_input/ps/
├── geometry/
├── interferograms/
│   └── ... (~455 pairs)
└── file_list.txt
```

### Status
- [ ] SBAS data organized for MintPy
- [ ] PS data organized for MintPy
- [ ] File lists generated
- [ ] Symlinks created in mintpy-playbook/work/

**Files to be created:**
- `04_MINTPY_INPUT_SUMMARY.txt` - Data organization summary

---

## ━━━ STAGE 5: MINTPY TIME-SERIES ANALYSIS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### MintPy Processing Steps (17 steps × 2 methods = 34 steps total)

#### SBAS Time-Series
```
Work Directory: /home/ubuntu/work/mintpy-playbook/work/bologna_sbas/

Processing Steps:
 1. load_data          - Load interferogram stack → ifgramStack.h5
 2. modify_network     - Refine pair selection (coherence threshold)
 3. reference_point    - Select reference pixel (spatial anchor)
 4. quick_overview     - Initial velocity + coherence assessment
 5 unwrap_error       - Detect/correct unwrapping errors
 6. invert_network     - Network inversion → timeseries.h5
 7. correct_troposphere - ERA5 atmospheric correction
 8. deramp             - Remove orbital ramps
 9. correct_topography - DEM error correction
10. velocity           - Linear velocity estimation
11. geocode            - Convert radar → geographic coords
12. save_hdfeos5       - Export final products
```

#### PS Time-Series
```
Work Directory: /home/ubuntu/work/mintpy-playbook/work/bologna_ps/

(Same 12 steps as SBAS, different network characteristics)
```

### Expected Output Files

#### Primary Products (Both Methods):
```
velocity.h5                      - Mean velocity map (mm/year)
timeseries.h5                    - Raw displacement time-series
timeseries_ERA5.h5               - + Atmospheric correction
timeseries_ERA5_ramp.h5          - + Orbital ramp removal
timeseries_ERA5_ramp_demErr.h5   - + DEM error correction ← "GOOD" TIME-SERIES
temporalCoherence.h5             - Pixel reliability map (0-1)
maskTempCoh.h5                   - Quality mask
geo_velocity.h5                  - Geocoded velocity
geo_timeseries_ERA5_ramp_demErr.h5 - Geocoded time-series
```

#### Quality Control Files:
```
ifgramStack.h5                   - Loaded interferogram stack
geometryRadar.h5                 - Geometry in radar coordinates
geometryGeo.h5                   - Geometry in geographic coordinates
numTriNonzeroIntAmbiguity.h5    - Unwrapping error indicators
avgSpatialCoh.h5                 - Average spatial coherence
network.pdf                      - Network baseline plot
pic/                             - Figures directory
```

### Comparison Metrics

#### Coverage:
- SBAS pixels with temporal coherence > 0.7
- PS pixels with temporal coherence > 0.85
- Coverage ratio (SBAS/PS)

#### Precision:
- Mean velocity standard error (SBAS vs PS)
- Temporal coherence distribution
- Residual RMS after corrections

#### Subsidence Patterns:
- Velocity map comparison (visual)
- Velocity correlation coefficient
- Displacement time-series at test points

### Status
- [ ] SBAS MintPy processing initiated
- [ ] SBAS MintPy processing completed
- [ ] PS MintPy processing initiated
- [ ] PS MintPy processing completed
- [ ] Comparison metrics computed
- [ ] Final figures generated

**Files to be created:**
- `05a_SBAS_TIMESERIES_METADATA.txt` - SBAS processing summary
- `05b_PS_TIMESERIES_METADATA.txt` - PS processing summary
- `05c_SBAS_VS_PS_COMPARISON.txt` - Method comparison
- `05d_velocity_comparison.png` - Side-by-side velocity maps
- `05e_coverage_comparison.png` - Coverage comparison
- `05f_timeseries_comparison.png` - Sample time-series plots

---

## ━━━ FINAL PRODUCTS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Deliverables

#### SBAS Results:
```
✓ Velocity map:                      bologna_sbas_velocity.h5
✓ "Good" time-series:                bologna_sbas_timeseries_final.h5
  • Atmospheric corrected (ERA5)
  • DEM error corrected
  • Orbital ramps removed
  • Spatially referenced
✓ Temporal coherence:                bologna_sbas_temporal_coherence.h5
✓ Expected Precision:                ~5-10 mm/year
✓ Expected Coverage:                 High (all coherent areas)
```

#### PS Results:
```
✓ Velocity map:                      bologna_ps_velocity.h5
✓ "Good" time-series:                bologna_ps_timeseries_final.h5
  • Same corrections as SBAS
  • Higher coherence pixel selection
✓ Temporal coherence:                bologna_ps_temporal_coherence.h5
✓ Expected Precision:                ~2-5 mm/year (on PSs)
✓ Expected Coverage:                 Lower (urban-focused)
```

#### Comparison Report:
```
✓ Method comparison document
✓ Velocity map comparison (geocoded)
✓ Coverage statistics
✓ Precision analysis
✓ Subsidence pattern validation
✓ Publication-quality figures
```

---

## Progress Tracker

| Stage | Task | Status | Started | Completed | Duration |
|-------|------|--------|---------|-----------|----------|
| 1 | SLC Search | ✅ Done | 2026-03-04 10:00 | 2026-03-04 10:00 | 1 min |
| 1 | SLC Download | ⏸ Pending | - | - | ~49 hrs |
| 2 | SBAS Pair Selection | ⏸ Pending | - | - | ~3 min |
| 2 | PS Pair Selection | ⏸ Pending | - | - | ~3 min |
| 3 | SBAS ISCE2 Processing | ⏸ Pending | - | - | ~51 hrs (parallel) |
| 3 | PS ISCE2 Processing | ⏸ Pending | - | - | ~85 hrs (parallel) |
| 4 | SBAS MintPy Prep | ⏸ Pending | - | - | ~5 min |
| 4 | PS MintPy Prep | ⏸ Pending | - | - | ~5 min |
| 5 | SBAS Time-Series | ⏸ Pending | - | - | ~3 hrs |
| 5 | PS Time-Series | ⏸ Pending | - | - | ~3 hrs |
| 6 | Comparison Analysis | ⏸ Pending | - | - | ~2 hrs |

**Total Estimated Time:** ~5.8 days (with 4× parallelization)

---

## Next Steps

**To proceed with download:**
```bash
# 1. Set up ASF authentication (required)
echo 'ASFUsr = "your_username"' > /home/ubuntu/work/credentials.py  
echo 'ASFPwd = "your_password"' >> /home/ubuntu/work/credentials.py

# Or create .netrc:
echo 'machine urs.earthdata.nasa.gov login USERNAME password PASSWORD' > ~/.netrc
chmod 600 ~/.netrc

# 2. Start download
cd /mnt/data/sbas_vs_ps_test_bologna
python3 download_slcs.py

# 3. Monitor progress
watch -n 300 'ls -lh data/safe/*.zip | wc -l; echo "out of 91"'
```

**Metadata will be updated automatically at each stage!**
