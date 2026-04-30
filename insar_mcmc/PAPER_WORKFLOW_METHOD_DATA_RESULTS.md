# Paper Workflow: Method, Data, Synthetic Validation, and Results

## 1. Aim Of The Study

The aim of this study is to infer hydrologically meaningful subsurface signals from land deformation by combining:

1. InSAR time-series deformation,
2. W3RA hydrologic model states,
3. external hydrologic constraints,
4. a dynamic Bayesian state-space model,
5. and independent groundwater-well validation.

The original ambition was a full five-layer inversion for

$$
\{S0, Ss, Sd, Sg, Sr\},
$$

but the applied real-data work showed that the unconstrained layered inverse problem is not practically stable. The current validated real-data formulation is therefore a **grouped Stage 1 multisensor inversion**, while the full five-layer synthetic work is retained as a pre-stage validation block.

---

## 2. Recommended Paper Structure

The paper workflow can be written in this order:

1. Study area and datasets
2. InSAR processing and overlap construction
3. Synthetic validation framework
4. Real-data grouped multisensor inversion
5. External validation with groundwater wells
6. Results
7. Discussion

This order is important because it makes the logic transparent:

- first show that the inversion machinery works in a controlled synthetic setting,
- then explain why the unconstrained layered real-data inversion is not sufficient,
- then present the grouped multisensor formulation as the stable applied solution,
- and finally validate the grouped groundwater posterior using independent wells.

---

## 3. Overall Workflow Used In This Study

### 3.1 Pre-stage: Synthetic Validation

The synthetic stage is not the final applied result. It is a controlled pre-stage used to verify that the inversion machinery can recover known signals under model-consistent conditions.

Workflow:

1. Generate synthetic W3RA-like storage fields for
   $$
   S0, Ss, Sd, Sg, Sr.
   $$
2. Convert them into deformation-space predictors using the same forward physics used later in the real inversion.
3. Construct synthetic observations
   $$
   Y_{t,p} = Z_{t,p}\theta_{t,p} + \varepsilon_{t,p}.
   $$
4. Run Stage 1 MCMC to recover posterior states.
5. Test whether Stage 2 residual learning can improve that posterior in synthetic data.

### 3.2 Real-data applied workflow

For the real Bologna application, the final workflow is:

1. Process the MintPy InSAR time series.
2. Aggregate the InSAR product onto the native W3RA grid.
3. Build the shared InSAR/W3RA overlap period.
4. Prepare external constraints:
   - GRACE
   - SMAP
   - SWOT
   - groundwater wells
5. Run the grouped balanced multisensor Stage 1 model.
6. Validate the grouped `Groundwater` posterior against wells.

---

## 4. Study Area And Hydrogeologic Setting

The applied study domain is the Bologna overlap area extracted from the broader Emilia-Romagna region in northern Italy. In the corrected MintPy/W3RA overlap used for the final grouped inversion, the working bounding box is:

- longitude `10.2` to `12.5`
- latitude `43.8` to `45.9`

This overlap domain is represented on the native shared W3RA grid of `22 x 24` cells for the period `2017-01-04` to `2024-08-01`.

For interpretation, the area is not treated as a single homogeneous groundwater body. Instead, the validation framework uses hydrogeologic categorization from the ARPAE groundwater monitoring network, together with well-depth grouping. In practice, two complementary categorizations are used:

1. **Depth classes**
   - shallow
   - intermediate
   - deep
2. **Hydrogeologic / GWB classes**
   - for example `Freatico di pianura fluviale`,
   - `Pianura Alluvionale Appenninica - confinato superiore`,
   - `Conoide Reno-Lavino - libero`,
   - `Conoide Reno-Lavino - confinato inferiore`,
   - and related alluvial-cone / confined-aquifer groups.

These categories are important in this study because the grouped posterior is not interpreted only by fit statistics, but also by whether it behaves consistently across hydrogeologically meaningful well subsets.

---

## 5. Data Summary Table

| Dataset | Product / file used in this study | Source | Coverage used here | Variables used | Role in study | Processing used before assimilation |
|---|---|---|---|---|---|---|
| InSAR | `timeseries_SET_ERA5_ramp_demErr.h5` | Local MintPy/Hyp3 processing of Sentinel-1 | `2017-01-04` to `2025-06-27`, 394 acquisitions | LOS deformation time series | Main observation stream | MintPy time-series inversion; then aggregated to W3RA grid; anomalies used in Stage 1 |
| InSAR interferogram stack | `inputs/ifgramStack.h5` | Local MintPy inputs | 555 interferograms | unwrapped phase, coherence | Documents network construction | Used to quantify number of interferograms and network properties |
| W3RA | `W3RA_2010_2024_.nc` and overlap products | Local hydrologic model run | overlap with InSAR: `2017-01-04` to `2024-08-01` | `S0, Ss, Sd, Sg, Sr` | Prior hydrologic state | Regridded/overlapped to InSAR; anomalies used for grouped state construction |
| GRACE | `GRCTellus.JPL.200204_202512.GLO.RL06.3M.MSCNv04CRI.nc` | JPL GRACE/GRACE-FO Mascon | aligned to 362 overlap dates | `lwe_thickness` anomalies | Regional storage / TWS-like constraint | regional mean over Bologna overlap bbox; anomaly aligned to InSAR timeline |
| SMAP | `SPL3SMP_E` matched granules | NASA NSIDC via Earthaccess | 358 matched files, 254 valid dates over overlap | surface soil moisture | External shallow-hydrologic constraint | one granule per InSAR date query; regional mean over overlap bbox; aligned to model timeline |
| SWOT | `SWOT_L2_HR_RiverSP_reach_2.0`, `SWOT_L2_HR_LakeSP_obs_2.0` | NASA PO.DAAC via Earthaccess | Bologna overlap subset: river 816 rows / 33 dates, lake 3421 rows / 34 dates | river/lake surface-water summaries | Exploratory external surface-water constraint | bbox subset + nearest-date matching with 14-day tolerance |
| Wells | ARPAE manual + automatic groundwater level data | ARPAE Emilia-Romagna | `2009-01-01` to `2024-12-18`; overlap validation uses `2017-01-04` to `2024-08-01` | piezometric head, depth to water | Independent validation of grouped groundwater signal | metadata merge, UTM-to-lon/lat conversion, spatial matching to tiles, lagged anomaly correlation |

---

## 6. Data Sources And References

### 6.1 InSAR / MintPy / processing context

The InSAR time series used in this study is the MintPy product:

- local file: [timeseries_SET_ERA5_ramp_demErr.h5](/mnt/data/aoi_3_bologna/mintpy_filtered/timeseries_SET_ERA5_ramp_demErr.h5)

The dataset attributes show:

- `394` acquisitions
- `555` interferograms in the stack
- `descending` geometry
- HyP3-based upstream unwrapped inputs
- MintPy inversion with:
  - solid Earth tides correction
  - ERA5 correction
  - DEM-error correction
  - quadratic deramping

Key local metadata from the HDF5 attributes:

- `mintpy.networkInversion.numIfgram = 555`
- `mintpy.network.maxTempBaseline = 60`
- `mintpy.network.maxPerpBaseline = 100`
- `mintpy.networkInversion.weightFunc = var`
- `mintpy.deramp = quadratic`
- `mintpy.solidEarthTides = yes`

Useful references:

- MintPy documentation: https://mintpy.readthedocs.io/
- ASF HyP3 documentation: https://hyp3-docs.asf.alaska.edu/

### 6.2 W3RA

The local W3RA source file used to build the overlap is:

- [W3RA_2010_2024_.nc](/mnt/data/data_bologna_swin_test/w3ra/W3RA_2010_2024_.nc)

The final overlap products are:

- [insar_mintpy2025_on_w3ra_grid.nc](/home/ubuntu/work/insar_mcmc/outputs_bologna_2025_overlap/insar_mintpy2025_on_w3ra_grid.nc)
- [w3ra_on_mintpy2025_overlap.nc](/home/ubuntu/work/insar_mcmc/outputs_bologna_2025_overlap/w3ra_on_mintpy2025_overlap.nc)
- [w3ra_on_mintpy2025_overlap_anom.nc](/home/ubuntu/work/insar_mcmc/outputs_bologna_2025_overlap/w3ra_on_mintpy2025_overlap_anom.nc)

The overlap summary is:

- [bologna_mintpy2025_w3ra_overlap_summary.json](/home/ubuntu/work/insar_mcmc/outputs_bologna_2025_overlap/bologna_mintpy2025_w3ra_overlap_summary.json)

It shows:

- shared period: `2017-01-04` to `2024-08-01`
- `362` shared times
- native overlap grid: `22 x 24`
- bbox:
  - lon `10.2` to `12.5`
  - lat `43.8` to `45.9`

### 6.3 GRACE

GRACE/GRACE-FO was used as a regional-scale external storage constraint.

Local file used:

- [GRCTellus.JPL.200204_202512.GLO.RL06.3M.MSCNv04CRI.nc](/mnt/data/punjab_grace_mascon_l3/GRCTellus.JPL.200204_202512.GLO.RL06.3M.MSCNv04CRI.nc)

Processed outputs:

- [bologna_grace_region_timeseries.csv](/home/ubuntu/work/insar_mcmc/outputs_external_constraints_overlap2025/bologna_grace_region_timeseries.csv)
- [bologna_grace_alignment_summary.json](/home/ubuntu/work/insar_mcmc/outputs_external_constraints_overlap2025/bologna_grace_alignment_summary.json)

Official source:

- JPL GRACE Mascon RL06.3 announcement / product context: https://podaac.jpl.nasa.gov/announcements/2024-09-12-Release-of-GRACE-FO-JPL-RL06.3-for-L2-3-and-MASCON-Data-Sets

In this study, GRACE was used as:

- `lwe_thickness` anomaly
- regional mean over the Bologna overlap bbox
- aligned to the 362-date overlap timeline

### 6.4 SMAP

SMAP was used as an external shallow soil-moisture constraint.

Download script used:

- [download_bologna_smap_matched.py](/home/ubuntu/work/insar_mcmc/download_bologna_smap_matched.py)

The script queries:

- short name `SPL3SMP_E`

Refreshed SMAP outputs:

- [bologna_smap_surface_soil_moisture_timeseries.csv](/home/ubuntu/work/insar_mcmc/outputs_external_constraints_overlap2025/smap_processed_fast4/bologna_smap_surface_soil_moisture_timeseries.csv)
- [bologna_smap_surface_soil_moisture_summary.json](/home/ubuntu/work/insar_mcmc/outputs_external_constraints_overlap2025/smap_processed_fast4/bologna_smap_surface_soil_moisture_summary.json)

Summary:

- `358` matched SMAP downloads
- `254` valid dates extracted
- overlap span `2017-01-04` to `2024-08-01`

Official source:

- NSIDC SMAP Enhanced L3 Radiometer Global Daily 9 km EASE-Grid Soil Moisture (`SPL3SMP_E`): https://nsidc.org/data/spl3smp_e/versions/1

Processing used here:

1. query one daily SMAP granule per InSAR date,
2. subset to the Bologna overlap bbox,
3. compute regional mean surface soil moisture,
4. align the extracted series to the overlap timeline.

### 6.5 SWOT

SWOT was used as an exploratory external surface-water constraint.

Download / processing scripts:

- [download_emilia_romagna_swot_bbox.py](/home/ubuntu/work/insar_mcmc/download_emilia_romagna_swot_bbox.py)
- [prepare_bologna_swot_overlap.py](/home/ubuntu/work/insar_mcmc/prepare_bologna_swot_overlap.py)

Products used:

- `SWOT_L2_HR_RiverSP_reach_2.0`
- `SWOT_L2_HR_LakeSP_obs_2.0`

Processed Bologna-overlap summary:

- [swot_bologna_overlap_summary.json](/home/ubuntu/work/insar_mcmc/outputs_external_constraints/swot_bologna_overlap2025/swot_bologna_overlap_summary.json)

Summary:

- river rows: `816`
- lake rows: `3421`
- river times: `33`
- lake times: `34`
- after nearest-date fusion into the multisensor bundle, only `9` usable matched dates per SWOT stream

Official sources:

- RiverSP reach product: https://podaac.jpl.nasa.gov/dataset/SWOT_L2_HR_RiverSP_reach_2.0
- LakeSP product: https://podaac.jpl.nasa.gov/dataset/SWOT_L2_HR_LakeSP_2.0

Interpretation in this study:

- SWOT was successfully prepared and tested,
- but it did not materially improve the current Bologna grouped inversion because the time overlap with the other streams is too sparse.

### 6.6 Wells

Groundwater wells were used for independent validation.

Downloaded sources:

- manual metadata:
  `https://docs.google.com/spreadsheets/d/1ow4Kj4ZkWNPSXJ93GxX4FpCQw-wuoABchbXEa9tJaxU/export?format=csv`
- manual levels:
  `https://docs.google.com/spreadsheets/d/1L4nOROdiMCB-S3WYPKxGWeHzgdhHeeXRO5ti8wl9Pck/export?format=csv`
- automatic metadata:
  `https://docs.google.com/spreadsheets/d/1n-4wBynQQtY7pgCx9Fjmq_X1yAy1Gp79chxH1zTWVd0/export?format=csv`
- automatic levels:
  `https://docs.google.com/spreadsheets/d/1YebnLh92xRmlYoumk1l814WACocUL2bUpTeraXOajYA/export?format=csv`

Catalog pages:

- ARPAE groundwater datasets:
  https://dati.arpae.it/it/dataset?q=sotterranee

Processed outputs:

- [bologna_wells_long.csv](/home/ubuntu/work/insar_mcmc/outputs_external_bologna_wells/processed/bologna_wells_long.csv)
- [bologna_wells_summary.json](/home/ubuntu/work/insar_mcmc/outputs_external_bologna_wells/processed/bologna_wells_summary.json)

Coverage:

- `19,467` Bologna measurements total
- `113` manual stations with measurements
- `4` automatic stations with measurements
- full measurement span `2009-01-01` to `2024-12-18`

The well metadata use `ETRS89 / UTM zone 32N`, converted here to WGS84 lon/lat for spatial matching.

---

## 6. Preprocessing Workflow Used In This Study

### 6.1 InSAR preprocessing and overlap construction

1. Start from the MintPy time-series product [timeseries_SET_ERA5_ramp_demErr.h5](/mnt/data/aoi_3_bologna/mintpy_filtered/timeseries_SET_ERA5_ramp_demErr.h5).
2. Use the corrected MintPy scene with `394` acquisitions and `555` interferograms.
3. Limit the overlap period to dates shared with the local W3RA product.
4. Aggregate the MintPy deformation from the original `4881 x 3985` scene to the native W3RA grid (`22 x 24`).
5. Build the corrected shared overlap:
   - [build_bologna_mintpy_w3ra_overlap.py](/home/ubuntu/work/insar_mcmc/build_bologna_mintpy_w3ra_overlap.py)
6. Final overlap period used:
   - `2017-01-04` to `2024-08-01`
   - `362` dates

### 6.2 W3RA preprocessing

1. Read the local W3RA model run.
2. Extract the five storage layers:
   - `S0`
   - `Ss`
   - `Sd`
   - `Sg`
   - `Sr`
3. Intersect W3RA dates with the corrected InSAR dates.
4. Save both raw overlap states and anomaly overlap states.

### 6.3 External constraints preprocessing

#### GRACE

1. Extract the GRACE regional mean over the Bologna overlap bbox.
2. Convert to anomalies.
3. Align to the 362-date overlap timeline.

#### SMAP

1. Query one SMAP daily granule per InSAR date using Earthaccess.
2. Keep only matched daily granules.
3. Subset to the Bologna overlap bbox.
4. Compute regional mean surface soil moisture.
5. Use the refreshed product, not the earlier sparse/obsolete set.

#### SWOT

1. Query SWOT RiverSP and LakeSP products by bbox.
2. Subset to the Bologna overlap bbox.
3. Build river and lake summary time series.
4. Use nearest-date matching with a `14`-day tolerance.
5. Treat SWOT as exploratory because only `9` matched dates per stream survive the final bundle fusion.

#### Wells

1. Download manual and automatic level tables plus metadata.
2. Merge time series with station metadata by `Codice`.
3. Convert UTM coordinates to lon/lat.
4. Filter to the overlap period for validation.
5. Use anomaly-space validation rather than raw-value equality.

---

## 7. Synthetic Validation Workflow

### 7.1 Synthetic Stage 1

Script:

- [stage1_pure_mcmc.py](/home/ubuntu/work/insar_mcmc/stage1_pure_mcmc.py)

Model:

$$
Y_{t,p} = Z_{t,p}\theta_{t,p} + \varepsilon_{t,p},
$$

$$
\theta_{t,p} = \theta_{t-1,p} + \eta_{t,p}.
$$

Synthetic setup used in the clean run:

- `24` time steps
- `12 x 12` spatial grid
- `5` layers
- `noise_scale = 0.0`

Key result:

- state recovery is strong for all five layers
- `Load_total` and `TWS` are recovered with very high skill
- deformation-space recovery is also strong

From the saved summary:

- `Load_total` state $R^2 \approx 0.976`
- `TWS` state $R^2 \approx 0.980`
- deformation $R^2 \approx 0.980`
- `Sg` state $R^2 \approx 0.981`

Interpretation:

- the inversion machinery works in a model-consistent synthetic setting,
- but synthetic success does not guarantee identifiability in real data.

### 7.2 Synthetic Stage 2

Script:

- [stage2_synthetic_residual.py](/home/ubuntu/work/insar_mcmc/stage2_synthetic_residual.py)

Purpose:

- test whether a Swin residual learner can improve the Stage 1 posterior when the residual is known in synthetic data.

Outcome:

- Stage 2 works technically,
- but when synthetic Stage 1 is already very accurate, Stage 2 adds little benefit.

Interpretation:

- Stage 2 is better viewed as a possible lag/mismatch learner,
- not as the main reason the real-data workflow works.

---

## 8. Final Applied Method Used For The Paper

### 8.1 Why the full layered inversion was not retained as the main applied result

The unconstrained real-data five-layer inversion was found to be numerically ill-conditioned and physically implausible in scale. Therefore the current applied method is the grouped multisensor Stage 1 formulation.

### 8.2 Grouped latent state

The final applied latent grouped state is

$$
\mathbf{x}_t^{\mathrm{grp}}
=
\begin{bmatrix}
\mathrm{ShallowLoad}_t \\
\mathrm{DeepLoad}_t \\
\mathrm{Groundwater}_t
\end{bmatrix}
=
\begin{bmatrix}
S0_t + Ss_t \\
Sd_t + Sr_t \\
Sg_t
\end{bmatrix}.
$$

### 8.3 Grouped state-space model

The grouped real-data model can be written as

$$
\mathbf{x}_t = A \mathbf{x}_{t-1} + \eta_t
$$

with observation operators for:

- InSAR deformation
- GRACE regional storage anomaly
- SMAP regional surface soil moisture
- exploratory SWOT summaries

The current implementation uses a balanced Kalman-type state-space formulation in which the grouped W3RA prior is corrected through multiplicative state factors.

Script:

- [stage1_bologna_multisensor_kalman.py](/home/ubuntu/work/insar_mcmc/stage1_bologna_multisensor_kalman.py)

Spatial extension:

- [stage1_bologna_multisensor_kalman_tiled.py](/home/ubuntu/work/insar_mcmc/stage1_bologna_multisensor_kalman_tiled.py)

---

## 9. Real-data Results To Report

### 9.1 Main grouped Stage 1 result

Regional posterior metrics:

- InSAR: $R^2 \approx 0.971$
- GRACE: $R^2 \approx 0.487$
- SMAP: $R^2 \approx 0.618$

Tiled posterior metric:

- InSAR tiled posterior: $R^2 \approx 0.905$

Magnitude sanity:

- `ShallowLoad` abs max `52.1 mm`
- `DeepLoad` abs max `88.1 mm`
- `Groundwater` abs max `48.1 mm`

### 9.2 SWOT test

SWOT was added as an observation term in an exploratory Stage 1 extension.

Result:

- technically successful,
- but no material improvement because the matched SWOT overlap is too sparse.

So SWOT should be described as:

- included in testing,
- useful for future extension,
- not a major driver of the current best result.

### 9.3 Well validation

Validation script:

- [validate_groundwater_against_wells.py](/home/ubuntu/work/insar_mcmc/validate_groundwater_against_wells.py)

Figure-generation script:

- [make_well_validation_figures.py](/home/ubuntu/work/insar_mcmc/make_well_validation_figures.py)

Well-validation summary:

- `83` station series evaluated
- all `83` positive after best state / best lag matching
- `74` with correlation `>= 0.3`
- `62` with correlation `>= 0.5`
- median correlation `0.704`
- top-10 mean correlation `0.947`

Depth-wise:

- shallow: median `0.767`
- intermediate: median `0.731`
- deep: median `0.617`

Best-state counts:

- `Groundwater`: `42`
- `ShallowLoad`: `25`
- `DeepLoad`: `16`

Trusted subset:

A conservative trusted subset was defined only after the full well-validation exercise had been completed on all evaluated stations. It is therefore a post-validation interpretation subset, not an a priori station-selection rule. A well entered the trusted subset if:

- its best-matching grouped state was `Groundwater`
- its best-lag anomaly correlation was at least `0.6`
- it had at least `10` matched observations
- and it belonged to a hydrogeologic group showing consistently strong validation behavior across multiple stations

Under that rule, the trusted subset contains:

- `6` trusted hydrogeologic groups
- `21` trusted stations

Trusted groups:

1. `Pianura Alluvionale Appenninica - confinato superiore`
2. `Freatico di pianura fluviale`
3. `Conoide Zena-Idice - confinato superiore`
4. `Conoide Reno-Lavino - libero`
5. `Conoide Reno-Lavino - confinato inferiore`
6. `Conoidi montane e Sabbie gialle orientali`

### 9.4 Interpretation to use in the paper

The defensible applied conclusion is:

1. the grouped balanced multisensor Stage 1 model is the current best Bologna result,
2. it is physically sane in magnitude,
3. it is supported by independent groundwater wells,
4. the full layered inversion is not yet the validated real-data result,
5. and the Stage 2 Swin residual learner remains exploratory.

---

## 10. Suggested Figures For The Paper

The figure set already prepared in this study is:

- [well_validation_summary_panel.png](/home/ubuntu/work/insar_mcmc/outputs_well_validation/figures/well_validation_summary_panel.png)
- [trusted_wells_map.png](/home/ubuntu/work/insar_mcmc/outputs_well_validation/figures/trusted_wells_map.png)
- [trusted_aquifer_groups.png](/home/ubuntu/work/insar_mcmc/outputs_well_validation/figures/trusted_aquifer_groups.png)
- [lag_histogram_by_state.png](/home/ubuntu/work/insar_mcmc/outputs_well_validation/figures/lag_histogram_by_state.png)
- [depth_class_summary.png](/home/ubuntu/work/insar_mcmc/outputs_well_validation/figures/depth_class_summary.png)
- [top6_station_timeseries.png](/home/ubuntu/work/insar_mcmc/outputs_well_validation/figures/top6_station_timeseries.png)

Recommended paper figure sequence:

1. study area and data domains
2. overlap construction and grouped-state schematic
3. synthetic validation summary
4. grouped real-data performance table
5. wells validation summary panel
6. trusted wells map
7. top six station comparisons

---

## 11. Files To Cite Internally In The Paper Workflow

Main result summary:

- [CURRENT_RESULTS_SUMMARY.md](/home/ubuntu/work/insar_mcmc/CURRENT_RESULTS_SUMMARY.md)

Results narrative:

- [RESULTS_TEXT_DRAFT.md](/home/ubuntu/work/insar_mcmc/RESULTS_TEXT_DRAFT.md)

Main notebook:

- [hybrid_results_notebook.ipynb](/home/ubuntu/work/insar_mcmc/hybrid_results_notebook.ipynb)

Presentation notebook:

- [hybrid_results_presentation.ipynb](/home/ubuntu/work/insar_mcmc/hybrid_results_presentation.ipynb)

---

## 12. Short Final Statement

If you need one short workflow statement for the paper:

This study first validated the deformation-space inversion machinery on synthetic five-layer W3RA data, then applied a grouped balanced multisensor Bayesian state-space model to the corrected Bologna MintPy/W3RA overlap using InSAR, GRACE, and refreshed SMAP, tested SWOT as an exploratory surface-water constraint, and finally validated the grouped groundwater posterior against independent ARPAE well-head observations using lag-aware anomaly correlation and a conservative trusted hydrogeologic subset.
