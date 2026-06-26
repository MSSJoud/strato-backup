# Figure Captions — GRSL Submission (vector PDF, 7.16" double-column)

---

## Main Figures

**Figure 1.**
Study area and validation setting.
*(Left panel)* Shaded-relief DTM of northern Italy generated from SRTM/ETOPO1 data. White dots mark the full Emilia-Romagna well network. The red rectangle outlines the shared InSAR/W3RA Bologna overlap domain used throughout the analysis.
*(Right panel)* Zoom on the Bologna overlap domain showing all Bologna-province well stations (light grey dots) and the trusted validation subset (gold stars) selected for independent groundwater verification.

**Figure 2.**
Overall study workflow. The top row represents the synthetic pre-stage, which validates the deformation-space inversion machinery under known-truth conditions. The bottom row represents the real-data branch, in which the grouped state vector [S0+Ss, Sd+Sr, Sg] is estimated from InSAR, GRACE, and refreshed SMAP observations (with SWOT as an exploratory extension) over the shared 22 × 24 Bologna grid. The grouped posterior is then validated independently against piezometric well records.

**Figure 3.**
Synthetic Stage 1 skill metrics.
*(Bar chart)* $R^2$ scores for the four key diagnostics recovered by the deformation-space Kalman inversion under synthetic (known-truth) conditions: groundwater state Sg, grouped load total, total water storage (TWS), and reconstructed deformation. All metrics exceed 0.95, confirming that the inversion machinery recovers the target quantities faithfully in the model-consistent setting.
*(Right panel)* Summary of the synthetic experiment configuration.

**Figure 4.**
Grouped Stage 1 temporal fit for the Bologna overlap.
Three regional anomaly time-series panels compare observed (black solid), prior (gray dashed), and posterior (blue solid) signals for InSAR line-of-sight deformation, GRACE terrestrial water storage, and SMAP surface soil moisture over the full 2017–2024 overlap period. The legend is intentionally omitted in-panel to preserve readability at print size.

**Figure 5.**
Independent well validation of the grouped groundwater posterior.
*(Left panel)* Spatial distribution of Bologna-province well stations with correlation ≥ 0.6 (trusted subset) coloured by anomaly correlation against the grouped Sg posterior. Grey dots show the broader Emilia-Romagna network.
*(Upper right)* Violin plots of best-match anomaly correlation by aquifer depth class (deep, intermediate, shallow) with individual station jitter overlaid.
*(Lower right)* Stacked bar chart of best-lag/best-state assignments across all evaluated well series, showing the dominant lag and which grouped state best matches each station.

**Figure 6.**
Representative model–well anomaly time-series comparisons for the six highest-correlation trusted stations. Blue curves show the standardised grouped Sg anomaly; orange curves show the standardised piezometric head anomaly. Station code, Pearson correlation, and optimal lag are indicated in each panel title.

**Figure 7.**
Comprehensive well validation summary.
*(Top-left map)* Emilia-Romagna well monitoring network (grey dots) with the nine highest-correlation trusted Bologna stations highlighted as red stars.
*(Right, 3 × 3 panels)* Standardised anomaly time-series comparisons between the grouped Groundwater (Sg) posterior (blue) and observed piezometric head anomalies (orange) for the nine selected stations. Station code is shown in the panel title; Pearson correlation and optimal lag are annotated inside each frame.
*(Bottom-left)* Violin plots of best-match anomaly correlation stratified by aquifer depth class (deep, intermediate, shallow), with individual station values overlaid.
*(Bottom-centre)* Stacked bar chart of best-lag/best-state assignments across all evaluated well series.

---

## Supplementary Figures

**Figure S1.**
Trusted hydrogeologic groups ranked by median anomaly correlation. Only groups containing at least one trusted station (correlation ≥ 0.3) are shown.

**Figure S2.**
Histogram of best-lag assignments across all evaluated well series, broken down by best-matching grouped state (ShallowLoad, DeepLoad, Groundwater). The distribution reveals that the majority of wells are best matched at short lags (0–30 days) with the Groundwater state.

**Figure S3.**
Depth-class validation summary showing median and mean anomaly correlation for deep, intermediate, and shallow aquifer categories. Deeper wells show systematically higher correlations with the grouped Sg posterior, consistent with the multi-month storage integration captured by the model.

**Figure S4.**
Conditioning diagnostics comparing three successive formulations: the original five-layer patch estimator, the early grouped patch estimator, and the current grouped multisensor Kalman formulation.
*(Left)* Operator condition number κ(J) on a log scale.
*(Centre)* Column-scale spread on a log scale.
*(Right)* Maximum absolute off-diagonal column correlation. The current formulation achieves the best conditioning across all three metrics.

**Figure S5.**
SWOT data overlap diagnostic. Raw available dates for RiverSP and LakeSP products (blue bars) versus the number of dates retained after nearest-date temporal fusion with the InSAR/W3RA timeline (orange bars). The sparse SWOT overlap (≤ 9 dates retained) explains the absence of material improvement when SWOT is added as an additional constraint.

**Figure S6.**
Static overview of the full Emilia-Romagna well monitoring network (grey dots) with the trusted Bologna validation subset highlighted (gold stars). The tight spatial cluster near Bologna reflects the dense monitoring coverage of the Po Plain aquifer system.

**Figure S7.**
Overview of the nine selected highest-correlation trusted wells.
*(Left)* Regional map with selected station positions marked by red stars.
*(Right, 3 × 3 panels)* Model (blue) versus well (orange) standardised anomaly time-series for each of the nine stations. Panel titles give the station code, Pearson correlation, and optimal lag in days.

**Figure S8.**
Grouped-state anomaly diagnostics at three representative dates (start, middle, and end of the overlap period). Rows correspond to ShallowLoad (S0+Ss), DeepLoad (Sd+Sr), and Groundwater (Sg). Diverging colour scales are symmetric around zero within each state.

**Figure S9.**
Grouped-state long-term spatial diagnostics. Left column: temporal mean anomaly maps. Right column: linear trend maps (mm/yr). Rows correspond to ShallowLoad (S0+Ss), DeepLoad (Sd+Sr), and Groundwater (Sg).
