# MintPy Workflow Guide

A detailed explanation of every step in the MintPy `smallbaselineApp.py` InSAR time-series analysis pipeline.

---

## Pipeline Overview

MintPy's `smallbaselineApp.py` implements the Small Baseline Subset (SBAS) InSAR technique. Starting from a stack of unwrapped interferograms, it produces a displacement time-series and velocity map in the satellite line-of-sight (LOS) direction.

**Input:** Stack of unwrapped interferograms (phase, coherence, connected components) + geometry files (DEM, incidence angle, etc.)

**Output:** 3D displacement time-series (2D space × 1D time) + estimated velocity map

---

## Step-by-Step Breakdown

### Step 1: `load_data`

Reads interferograms and geometry files from disk and stores them in HDF5 format for efficient access.

- **Input:** Raw data files (ISCE, GAMMA, SNAP, etc. format)
- **Output:** `inputs/ifgramStack.h5`, `inputs/geometryRadar.h5`, `inputs/geometryGeo.h5`
- **Key parameters:** `mintpy.load.processor`, `mintpy.load.unwFile`, `mintpy.load.corFile`

The interferogram stack HDF5 contains all unwrapped phases, coherence values, and connected components. The geometry files contain the DEM, incidence angle, look direction, and coordinate lookup tables.

### Step 2: `modify_network`

Filters the interferogram network based on quality criteria.

- Removes interferograms with low average coherence
- Removes interferograms with excessive temporal or spatial baselines
- Applies any manual exclusion lists
- **Key parameter:** `mintpy.network.minCoherence`

### Step 3: `reference_point`

Selects a reference pixel — the spatial point to which all other pixels are referenced. MintPy selects the pixel with the highest average spatial coherence.

- **Key parameter:** `mintpy.reference.lalo` (manually specify lat/lon, or `auto`)
- The reference point should ideally be on stable, non-deforming ground

### Step 4: `quick_overview`

Generates a quick assessment before full inversion. Computes average velocity and temporal coherence using a simple approach. Useful for sanity-checking the data before committing to the full pipeline.

### Step 5: `correct_unwrap_error`

Detects and corrects phase unwrapping errors using phase closure analysis. Unwrapping errors are integer multiples of 2π that were incorrectly assigned during the unwrapping process.

- Methods: `bridging`, `phase_closure`, `bridging+phase_closure`
- **Key parameter:** `mintpy.unwrapError.method`

### Step 6: `invert_network`

The core step — inverts the redundant network of interferograms into a displacement time-series using weighted least squares. Each pixel is independently inverted.

- Weight functions: `var` (variance), `fim` (Fisher information matrix), `coh` (coherence), `no` (unweighted)
- **Output:** `timeseries.h5`, `temporalCoherence.h5`, `numInvIfgram.h5`
- **Key parameter:** `mintpy.networkInversion.weightFunc`

The temporal coherence measures how well the interferogram network is explained by the estimated time-series — higher values indicate better quality.

### Step 7: `correct_LOD`

Corrects for local oscillator drift, relevant only for Envisat ASAR data. Skipped for Sentinel-1 data.

### Step 8: `correct_SET`

Corrects solid Earth tides — periodic ground deformation caused by gravitational forces from the Moon and Sun. Typically small (< 1 cm) but systematic.

### Step 9: `correct_troposphere`

Corrects tropospheric delay — the largest error source for InSAR. Uses global atmospheric models (ERA5 from ECMWF) or a phase-elevation correlation approach.

- Methods: `pyaps` (ERA5, recommended), `height_correlation`, `no`
- Requires ERA5 account credentials for full correction
- **Key parameter:** `mintpy.troposphericDelay.method`

### Step 10: `deramp`

Removes large-scale phase ramps caused by orbital errors or ionospheric delay. Fits and removes a polynomial surface (linear or quadratic) from each acquisition.

- Options: `linear`, `quadratic`, `no`
- **Key parameter:** `mintpy.deramp`

### Step 11: `correct_topography`

Corrects DEM errors that propagate into the displacement time-series through the perpendicular baseline. Estimates the residual topographic phase and removes it.

- **Key parameter:** `mintpy.topographicResidual`
- **Output:** Updated time-series with DEM error correction; `demErr.h5` contains the estimated DEM error

### Step 12: `residual_RMS`

Computes the root mean square (RMS) of the residual time-series to assess quality. High residual RMS dates may indicate atmospheric artifacts or other noise sources that were not fully corrected.

### Step 13: `reference_date`

Selects the reference date (time=0) for the displacement time-series. By default, MintPy selects the date with the minimum residual RMS.

### Step 14: `velocity`

Estimates the linear displacement velocity from the corrected time-series using weighted least squares regression. Can also estimate periodic terms (annual, semi-annual) and polynomial terms.

- **Output:** `velocity.h5`
- **Key parameters:** `mintpy.velocity.startDate`, `mintpy.velocity.endDate`

### Step 15: `geocode`

Converts results from radar coordinates (range/azimuth) to geographic coordinates (latitude/longitude) using the lookup table from the geometry files.

- **Output:** `geo/` directory with geocoded HDF5 files

### Step 16: `google_earth`

Generates Google Earth KMZ files for easy visualization.

- **Output:** KMZ files for velocity, coherence, and other products

### Step 17: `hdfeos5`

Exports all results to HDF-EOS5 format, the standard for NASA's InSAR data distribution (e.g., via the Alaska Satellite Facility).

---

## Sign Convention

**Positive LOS velocity = motion toward the satellite (uplift for near-vertical looking).**

For the Fernandina dataset (descending orbit, ~34° incidence angle), positive values generally indicate uplift or eastward motion, and negative values indicate subsidence or westward motion.

---

## Key Output Files

| File | Description |
|------|-------------|
| `inputs/ifgramStack.h5` | Complete interferogram stack |
| `timeseries.h5` | Raw displacement time-series |
| `timeseries_*_demErr.h5` | Final corrected time-series |
| `temporalCoherence.h5` | Quality map (0–1, higher = better) |
| `velocity.h5` | Estimated displacement rate |
| `demErr.h5` | Estimated DEM error |
| `avgSpatialCoh.h5` | Average spatial coherence |
| `maskTempCoh.h5` | Mask based on temporal coherence threshold |

---

## References

- Yunjun, Z., Fattahi, H., and Amelung, F. (2019), Small baseline InSAR time series analysis: Unwrapping error correction and noise reduction, *Computers & Geosciences*, 133, 104331.
- Berardino, P., Fornaro, G., Lanari, R., and Sansosti, E. (2002), A new algorithm for surface deformation monitoring based on small baseline differential SAR interferograms, *IEEE TGRS*, 40(11), 2375-2383.

---

## Operational Commands (Bologna Subset Runtime)

These are practical commands used during long ISCE2 SBAS/PS runs for `/mnt/data/sbas_vs_ps_test_bologna`.

### 1) Follow the active batch log

```bash
tail -f /mnt/data/sbas_vs_ps_test_bologna/logs/sbas_latest.log
```

### 2) Show latest run logs

```bash
ls -lt /mnt/data/sbas_vs_ps_test_bologna/logs | head -n 10
```

### 3) Check active processing containers

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.RunningFor}}'
```

### 4) Parse run counters from log (start/done/fail/skip)

```bash
python3 - << 'PY'
import re, pathlib
log = pathlib.Path('/mnt/data/sbas_vs_ps_test_bologna/logs/sbas_latest.log')
text = log.read_text(errors='ignore') if log.exists() else ''
print('START', len(re.findall(r'\] START ', text)))
print('DONE ', len(re.findall(r'\] DONE ', text)))
print('FAIL ', len(re.findall(r'\] FAIL ', text)))
print('SKIP ', len(re.findall(r'\] SKIP ', text)))
PY
```

### 5) Get latest pair event from log

```bash
python3 - << 'PY'
import pathlib
log = pathlib.Path('/mnt/data/sbas_vs_ps_test_bologna/logs/sbas_latest.log')
text = log.read_text(errors='ignore').splitlines() if log.exists() else []
for line in reversed(text):
	if '] START ' in line or '] DONE ' in line or '] FAIL ' in line or '] SKIP ' in line:
		print(line)
		break
PY
```

### 6) Count generated unwrapped and dense outputs

```bash
find /mnt/data/sbas_vs_ps_test_bologna/configs/sbas -type f -name 'filt_topophase.unw.geo' | wc -l
find /mnt/data/sbas_vs_ps_test_bologna/configs/sbas -type f | grep -i dense | wc -l
```

### 7) Inspect recent failures

```bash
grep -n 'FAIL\|Traceback\|Exception\|not found' /mnt/data/sbas_vs_ps_test_bologna/logs/sbas_latest.log | tail -n 50
```

### 8) Restart SBAS batch with dense required

```bash
REQUIRE_DENSE=1 /home/ubuntu/work/run_isce2_subset_batch.sh sbas
```

### 9) Start PS batch (same runner)

```bash
REQUIRE_DENSE=1 /home/ubuntu/work/run_isce2_subset_batch.sh ps
```
