# AOI 3 HyP3/GAMMA Stepwise MintPy Guide

This guide documents the exact MintPy workflow used for the Bologna AOI 3 HyP3/GAMMA interferogram stack in:

- project data: `/mnt/data/aoi_3_bologna`
- filtered MintPy work directory: `/mnt/data/aoi_3_bologna/mintpy_filtered`
- active template: `/home/ubuntu/work/mintpy-playbook/configs/aoi_3_bologna_hyp3_filtered.cfg`

It is intentionally focused on the HyP3/GAMMA interferogram workflow and does not include the generic sample-data or demo `pipeline` service path.

## What This Workflow Starts From

This workflow starts from geocoded HyP3/GAMMA interferogram products, not raw Sentinel-1 SLCs.

Expected per-pair inputs include:

- `*_unw_phase_clipped.tif`
- `*_corr_clipped.tif`
- `*_dem_clipped.tif`
- `*_lv_theta_clipped.tif`
- `*_lv_phi_clipped.tif`
- `*_water_mask_clipped.tif`

MintPy loads those directly with:

- `mintpy.load.processor = hyp3`

## Runtime Services

For this AOI, the main container entrypoint is the `mintpy` service from [docker-compose.yml](/home/ubuntu/work/mintpy-playbook/docker-compose.yml).

Common commands:

```bash
cd /home/ubuntu/work/mintpy-playbook

# open a shell in the MintPy container
docker compose run --rm mintpy bash

# run one MintPy step
docker compose run --rm mintpy \
  smallbaselineApp.py /workspace/configs/aoi_3_bologna_hyp3_filtered.cfg \
  --dir /mnt/data/aoi_3_bologna/mintpy_filtered \
  --dostep load_data

# run the remaining workflow from the template
docker compose run --rm mintpy \
  smallbaselineApp.py /workspace/configs/aoi_3_bologna_hyp3_filtered.cfg \
  --dir /mnt/data/aoi_3_bologna/mintpy_filtered
```

For interactive inspection:

```bash
cd /home/ubuntu/work/mintpy-playbook
docker compose up jupyter
```

Then open `http://localhost:8888`.

## Active Template Choices

The current filtered HyP3 template is [aoi_3_bologna_hyp3_filtered.cfg](/home/ubuntu/work/mintpy-playbook/configs/aoi_3_bologna_hyp3_filtered.cfg).

Key settings used in this run:

- processor: `hyp3`
- network pruning:
  - `mintpy.network.maxTempBaseline = 60`
  - `mintpy.network.maxPerpBaseline = 100`
- reference point:
  - `mintpy.reference.lalo = auto`
- temporal coherence mask:
  - `mintpy.tempCohMask.min = 0.4`
- corrections:
  - `mintpy.solidEarthTides = yes`
  - `mintpy.troposphericDelay.method = pyaps`
  - `mintpy.troposphericDelay.weatherModel = ERA5`
  - `mintpy.troposphericDelay.weatherDir = /mnt/data/aoi_3_bologna_weather`
  - `mintpy.deramp = quadratic`
- export:
  - `mintpy.save.hdfEos5 = yes`

## Step Sequence Used For AOI 3

The sections below reflect the actual run path used for this HyP3 stack.

### 1. `load_data`

Purpose:

- read HyP3 GeoTIFF interferograms and geometry
- write MintPy HDF5 inputs

Main outputs:

- `inputs/ifgramStack.h5`
- `inputs/geometryGeo.h5`

Notes for this AOI:

- the stack is already geocoded
- `geometryGeo.h5` contains incidence angle, azimuth angle, DEM, and water mask

Command:

```bash
docker compose run --rm mintpy \
  smallbaselineApp.py /workspace/configs/aoi_3_bologna_hyp3_filtered.cfg \
  --dir /mnt/data/aoi_3_bologna/mintpy_filtered \
  --dostep load_data
```

### 2. `modify_network`

Purpose:

- evaluate and prune the interferogram network
- compute average spatial coherence
- produce network diagnostics

Main outputs:

- `avgSpatialCoh.h5`
- `waterMask.h5`
- `network.pdf`
- `coherenceMatrix.pdf`
- `coherenceHistory.pdf`
- `coherenceSpatialAvg.txt`
- `pbaseHistory.pdf`

This is the step to inspect when you want to understand:

- which interferograms were kept
- how coherence changes with time and baseline
- whether the network is well connected

### 3. `reference_point`

Purpose:

- choose the spatial zero point for the stack

Main outputs:

- updated `inputs/ifgramStack.h5` metadata
- `maskConnComp.h5`

AOI 3 note:

- a hard-coded Bologna reference point fell inside a masked region, so this workflow was switched to `auto`
- the selected reference pixel for this run is stored in the HDF5 metadata

### 4. `quick_overview`

Purpose:

- generate fast sanity-check products before full inversion

Main outputs:

- `avgPhaseVelocity.h5`
- `numTriNonzeroIntAmbiguity.h5`
- `numTriNonzeroIntAmbiguity.png`

Use this step to quickly spot:

- large-scale phase behavior
- unwrapping trouble from closure ambiguity

### 5. `correct_unwrap_error`

Purpose:

- optional unwrapping-error correction

AOI 3 note:

- this step was left OFF in the HyP3 template
- MintPy skipped it cleanly

### 6. `invert_network`

Purpose:

- invert the interferogram network into a displacement time series

Main outputs:

- `timeseries.h5`
- `temporalCoherence.h5`
- `numInvIfgram.h5`
- `maskTempCoh.h5`

This is the first step that creates the full LOS time series.

### 7. `correct_LOD`

Purpose:

- correct Envisat local oscillator drift

AOI 3 note:

- skipped because this is Sentinel-1, not Envisat

### 8. `correct_SET`

Purpose:

- remove solid Earth tide effects

Main outputs:

- `inputs/SET.h5`
- `timeseries_SET.h5`

AOI 3 note:

- MintPy used the Sentinel-1 sensing time metadata and treated the time of day as effectively constant across acquisitions, which is appropriate for this stack

### 9. `correct_troposphere`

Purpose:

- remove atmospheric delay using ERA5 and PyAPS

Required weather data:

- parent directory in config:
  - `/mnt/data/aoi_3_bologna_weather`
- actual GRIB files used by PyAPS:
  - `/mnt/data/aoi_3_bologna_weather/ERA5`

Main outputs:

- `inputs/ERA5.h5`
- `timeseries_SET_ERA5.h5`

AOI 3 note:

- this run used `394` ERA5 pressure-level GRIB files
- MintPy matched the acquisitions to the nearest hourly weather model time, which was `05:00 UTC`

### 10. `deramp`

Purpose:

- remove broad residual orbital or atmospheric ramps from each acquisition

Main output:

- `timeseries_SET_ERA5_ramp.h5`

AOI 3 note:

- the chosen ramp model is `quadratic`
- the mask used for fitting is `maskTempCoh.h5`

### 11. `correct_topography`

Purpose:

- estimate and remove DEM-related residual phase tied to perpendicular baseline

Main outputs:

- `timeseries_SET_ERA5_ramp_demErr.h5`
- `demErr.h5`

This step is required before the final velocity estimation in this workflow.

### 12. `residual_RMS`

Purpose:

- evaluate residual noise per acquisition
- pick a stable temporal reference date

Main outputs:

- `timeseriesResidual.h5`
- `timeseriesResidual_ramp.h5`
- `rms_timeseriesResidual_ramp.txt`
- `rms_timeseriesResidual_ramp.pdf`
- `reference_date.txt`

AOI 3 note:

- this run selected `20181201` as the reference date

### 13. `reference_date`

Purpose:

- apply or confirm the temporal zero date

AOI 3 note:

- with `auto`, MintPy relies on the residual-RMS stage to produce `reference_date.txt`
- once that file exists, the time series is anchored in time for downstream products

### 14. `velocity`

Purpose:

- estimate the LOS velocity from the corrected time series

Main outputs:

- `velocity.h5`
- `velocityERA5.h5`
- `velocity.png`

Interpretation note:

- these are LOS velocities, not full 3D or rigorously vertical velocities
- incidence angle is available in `inputs/geometryGeo.h5`, but one Sentinel-1 viewing geometry is not enough to uniquely separate vertical and horizontal motion

### 15. `geocode`

Purpose:

- geocode radar-coordinate products

AOI 3 note:

- skipped because the HyP3 stack is already geocoded

### 16. `google_earth`

Purpose:

- export browse products for Google Earth

Main output:

- `velocity.kmz`

### 17. `hdfeos5`

Purpose:

- package the final results in HDF-EOS5 format

Main output:

- `S1_IW123_168_0000_20170104_20250627.he5`

## Weather Download Helper

The ERA5 helper added for this AOI is:

- [07_download_era5_for_mintpy.py](/home/ubuntu/work/mintpy-playbook/scripts/07_download_era5_for_mintpy.py)

Typical usage:

```bash
cd /home/ubuntu/work/mintpy-playbook
python3 scripts/07_download_era5_for_mintpy.py --download
```

What it does:

- reads acquisition dates from `timeseries_SET.h5`
- downloads one ERA5 pressure-level GRIB per date
- stores them under `/mnt/data/aoi_3_bologna_weather/ERA5`

## Recommended Inspection Workflow

For this AOI, the most useful checkpoints are:

1. After `load_data`: inspect `inputs/ifgramStack.h5` and `inputs/geometryGeo.h5`
2. After `modify_network`: inspect `network.pdf`, `coherenceMatrix.pdf`, and `coherenceSpatialAvg.txt`
3. After `invert_network`: inspect `temporalCoherence.h5`, `maskTempCoh.h5`, and `timeseries.h5`
4. After `correct_troposphere`: compare `timeseries_SET.h5` and `timeseries_SET_ERA5.h5`
5. After `correct_topography`: inspect `demErr.h5` and the final corrected series `timeseries_SET_ERA5_ramp_demErr.h5`
6. After `velocity`: inspect `velocity.h5`, `velocityERA5.h5`, and `velocity.kmz`

## Practical Output Chain For This Run

The main time-series chain produced for AOI 3 is:

- `timeseries.h5`
- `timeseries_SET.h5`
- `timeseries_SET_ERA5.h5`
- `timeseries_SET_ERA5_ramp.h5`
- `timeseries_SET_ERA5_ramp_demErr.h5`

This makes it straightforward to compare the impact of each correction stage on any pixel or area.

## Sign And Interpretation Notes

- Results are in satellite line of sight
- units are meters in time-series files and meters per year in velocity files
- positive and negative values should be interpreted with the LOS convention stored by the MintPy product, not as direct vertical motion without additional assumptions

## Main References

- Yunjun, Z., Fattahi, H., and Amelung, F. (2019), Small baseline InSAR time series analysis: Unwrapping error correction and noise reduction, *Computers & Geosciences*, 133, 104331.
- Berardino, P., Fornaro, G., Lanari, R., and Sansosti, E. (2002), A new algorithm for surface deformation monitoring based on small baseline differential SAR interferograms, *IEEE Transactions on Geoscience and Remote Sensing*, 40(11), 2375-2383.
