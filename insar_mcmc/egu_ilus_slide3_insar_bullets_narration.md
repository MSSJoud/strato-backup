# EGU Slide 3 – InSAR Data
## Sentinel-1 Surface Deformation · Bologna / Po Plain · 2017–2024

---

### SLIDE BULLETS

**Sentinel-1 SAR Interferometry**
- Sensor: Sentinel-1 A/B · C-band (λ ≈ 5.6 cm) · descending pass · IW TOPS mode
- 362 acquisitions · 4 January 2017 – 1 August 2024 (~7.5 years)
- Spatial domain: Bologna / Emilia-Romagna · Po Plain  
  (lat 43.8–45.9 °N, lon 10.2–12.5 °E)

**Processing Pipeline**
- Containerised InSAR processing with **ZARVAN-AID** – GPU-accelerated modified ISCE2+
- Phase time-series inversion and atmospheric/error corrections via **MintPy**
- Atmospheric: ERA5 tropospheric delay + Solid-Earth tides (SET)
- Systematic: orbital ramp removal + DEM error estimation

**Time-Series Reference Frame**
- Spatial reference: stable reference pixel over water body (MintPy convention)
- Result: cumulative LOS displacement (mm) relative to first acquisition 2017-01-04
- Displacement range: −83 mm (subsidence) to +19 mm (uplift) over 7.5 years

**Domain Overview**
- 22 × 24 water-balance grid cells (~10 km resolution, W3RA native grid)
- Dominant signal: long-term land subsidence in Po Plain (clay compaction + groundwater)
- Seasonal oscillations superimposed on secular trend

---

### NARRATION SCRIPT

> *(Slide 3 – video starts playing automatically)*

> "Our primary observational dataset is a Sentinel-1 SAR interferometric time series
> processed over the Bologna and Emilia-Romagna region in the Po Plain of northern Italy.

> The animation you can see shows cumulative line-of-sight displacement maps from
> January 2017 through August 2024 – a record of three hundred sixty-two acquisitions
> over seven and a half years.

> The data were processed using a containerised, GPU-accelerated pipeline
> developed by ZARVAN-AID, based on a modified version of ISCE2-plus,
> followed by MintPy for time-series inversion.
> Several systematic error sources were corrected:
> ERA5 tropospheric delays, solid-Earth tides,
> orbital ramp, and DEM-phase errors.

> The colour scale shows line-of-sight displacement in millimetres,
> with blue indicating subsidence – motion away from the sensor –
> and red indicating uplift.
> The dominant signal across the Po Plain is a secular subsidence
> reaching up to 83 millimetres over the record,
> driven by natural clay compaction and anthropogenic groundwater extraction.

> On top of this long-term trend you can see seasonal oscillations,
> particularly visible in the agricultural lowlands south of Bologna.
> These seasonal signals are what our Bayesian state-space framework
> will use – together with GRACE-FO water storage anomalies
> and SMAP soil moisture – to partition the deformation
> into its shallow, deep, and groundwater components."

---

### NOTES FOR PRESENTER

- Video length: ~30 s at 12 fps (362 frames)
- Video file: `egu_ilus_insar_deformation_video.mp4`  (H.264, yuv420p, compatible with PowerPoint/Keynote)
- Suggested transition: auto-advance at ~32 s; next slide is the GRACE/SMAP data overview
- If video does not loop, set looping in presentation software
- Colour scale is capped at ±40 mm to reveal seasonal structure; extremes exist but are localised

---

### DATA PROVENANCE TABLE (for backup slide or speaker notes)

| Item | Value |
|------|-------|
| Satellite | Sentinel-1 A/B (ESA Copernicus) |
| Band / wavelength | C-band · 5.6 cm |
| Geometry | Descending pass · IW TOPS mode |
| Processing software | ZARVAN-AID containerised ISCE2+ (GPU) + MintPy |
| Atmospheric correction | ERA5 tropospheric delay |
| Other corrections | Solid-Earth tides · orbital ramp · DEM error |
| Temporal reference | 4 January 2017 |
| Spatial reference | Stable water-body pixel (MintPy) |
| Number of acquisitions | 362 |
| Period | 2017-01-04 to 2024-08-01 |
| Domain | Lat 43.8–45.9 °N · Lon 10.2–12.5 °E |
| Grid resolution (analysis) | ~10 km (W3RA 0.1° grid, 22 × 24 cells) |
| LOS displacement range | −83 mm to +19 mm (cumulative) |
