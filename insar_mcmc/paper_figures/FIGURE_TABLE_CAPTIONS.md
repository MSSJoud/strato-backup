# Paper Figures, Tables, and Captions
## Main figures
- `figure_1.png`: Study area and validation setting. Left: DTM background for the broader Bologna scene with the shared InSAR/W3RA overlap marked by a red box. Right: zoom on the overlap domain showing Bologna well stations, with the trusted validation subset highlighted by stars.
- `figure_2.png`: Overall study workflow. The synthetic pre-stage validates the deformation-space inversion machinery under known truth, whereas the real-data branch uses the grouped state [S0+Ss, Sd+Sr, Sg], assimilates InSAR, GRACE, and refreshed SMAP (with SWOT as an exploratory extension), and validates the grouped groundwater posterior against wells.
- `figure_3.png`: Compact synthetic validation summary. The deformation-space Stage 1 inversion achieves strong recovery in the model-consistent synthetic setting, especially for grouped states and deformation skill.
- `figure_4.png`: Main grouped Stage 1 temporal fit over the Bologna overlap. Panels show observed (black solid), prior (gray dashed), and posterior (blue solid) regional anomaly time-series for InSAR, GRACE, and SMAP; no in-panel legend is used to preserve readability at print size.
- `figure_5.png`: Independent well validation of the grouped posterior. Gray dots show the broader Emilia-Romagna well network, while the trusted Bologna wells with correlation greater than or equal to 0.6 are highlighted as small colored dots and starred markers. The lower panel summarizes the best-lag / best-state distribution, and the upper-right panel summarizes depth-class validation.
- `figure_6.png`: Representative well time-series comparisons for the strongest trusted stations. Blue curves denote the grouped model anomaly and orange curves denote standardized well-head anomalies.

## Supplementary figures
- `figure_s1.png`: Trusted hydrogeologic groups ranked by median well correlation.
- `figure_s2.png`: Histogram of best lag by best-matching grouped state across validated wells.
- `figure_s3.png`: Depth-class validation summary showing mean and median anomaly correlation.
- `figure_s4.png`: Conditioning comparison across the old layered patch, old grouped patch, and current grouped multisensor formulation, using operator condition number, column-scale spread, and maximum off-diagonal column correlation.
- `figure_s5.png`: SWOT overlap diagnostic showing the reduction from raw river/lake dates to matched dates retained in the nearest-date multisensor bundle.
- `figure_s6.png`: Static overview of the Emilia-Romagna well network with the trusted Bologna subset highlighted.
- `figure_s7.png`: Overview of nine selected trusted wells. Left: regional well network with the selected stations marked by red stars. Right: model-versus-well anomaly time-series comparisons for the same nine stations.
- `figure_s8.png`: Grouped-state spatial diagnostics: ShallowLoad, DeepLoad, and Groundwater maps at three representative dates (start, mid, end of record) plus the temporal mean map. Diverging color scale is state-wise and symmetric around zero.
- `figure_s9.png`: Grouped-state long-term spatial diagnostics: temporal mean maps and linear trend maps (mm/yr) for ShallowLoad, DeepLoad, and Groundwater.

## Table 1

Data summary used in the main paper.

| Dataset | Product / source | Coverage used | Variables used | Role in study | Preprocessing before assimilation |
| --- | --- | --- | --- | --- | --- |
| InSAR | MintPy time series | 2017-01-04 to 2025-06-27, 394 acquisitions, 555 interferograms | LOS deformation | Main observation stream | MintPy inversion; anomalies; aggregated to W3RA grid |
| W3RA | Local W3RA overlap products | 2017-01-04 to 2024-08-01, shared 22 x 24 grid | S0, Ss, Sd, Sg, Sr | Model prior / grouped state basis | Overlap construction and anomaly conversion |
| GRACE | JPL mascon RL06.3 | 362 aligned overlap dates | lwe_thickness anomaly | Regional TWS-like constraint | Regional mean over overlap bbox |
| SMAP | SPL3SMP_E | 358 downloads, 254 valid dates | Surface soil moisture | Shallow hydrologic constraint | Regional mean over overlap bbox |
| SWOT | RiverSP + LakeSP | 33 river dates / 34 lake dates, 9 retained after nearest-date fusion | Surface-water summaries | Exploratory surface-water constraint | BBox subset and nearest-date matching |
| Wells | ARPAE manual + automatic | 2009-01-01 to 2024-12-18 | Piezometric head, depth to water | Independent validation | Metadata merge, lon/lat conversion, lagged anomaly comparison |

## Table 2

Synthetic and real experiment-block summary.

| Stage | State formulation | Observations | Goal | Output |
| --- | --- | --- | --- | --- |
| Synthetic Stage 1 | [S0, Ss, Sd, Sg, Sr] | Synthetic deformation Y and model-side Z | Validate inversion machinery | Posterior synthetic state and deformation skill |
| Synthetic Stage 2 | Residual / lag refinement | Synthetic InSAR window + Stage 1 prior | Check whether learned residuals add value | Exploratory residual diagnostic |
| Real grouped Stage 1 | [S0+Ss, Sd+Sr, Sg] | InSAR + GRACE + refreshed SMAP | Stable applied estimator | Grouped posterior state |
| Exploratory SWOT extension | [S0+Ss, Sd+Sr, Sg] | InSAR + GRACE + SMAP + SWOT | Test added surface-water information | No material improvement under sparse overlap |
| Well validation | Grouped posterior vs well anomalies | ARPAE manual + automatic wells | Independent support for groundwater signal | Station-wise lagged correlations and trusted subset |

## Table 3

Main quantitative results table for the main paper.

| Metric | Value |
| --- | --- |
| Regional InSAR posterior $R^2$ | 0.9706 |
| Regional GRACE posterior $R^2$ | 0.4865 |
| Regional SMAP posterior $R^2$ | 0.6180 |
| Tiled InSAR posterior $R^2$ | 0.9046 |
| max |ShallowLoad| (mm) | 52.1104 |
| max |DeepLoad| (mm) | 88.1108 |
| max |Groundwater| (mm) | 48.1393 |
| Well series evaluated | 83 |
| Median well correlation | 0.7043 |
| Wells with corr >= 0.3 | 74 |
| Wells with corr >= 0.5 | 62 |
| Trusted groups / stations | 6 / 21 |

## Table S1

Hydrogeologic group validation summary (top groups by median correlation).

| gwb_name | n_series | median_corr | mean_corr | n_corr_ge_0_3 | n_corr_ge_0_5 |
| --- | --- | --- | --- | --- | --- |
| Conoide Sillaro-Sellustra - confinato superiore | 2 | 0.8302 | 0.8302 | 2 | 2 |
| Conoide Zena-Idice - confinato superiore | 5 | 0.8118 | 0.8333 | 5 | 5 |
| Pianura Alluvionale Appenninica - confinato superiore | 11 | 0.8042 | 0.7293 | 10 | 9 |
| Transizione Pianura Appenninica-Padana - confinato superiore | 2 | 0.7800 | 0.7800 | 2 | 2 |
| Conoide Reno-Lavino - libero | 4 | 0.7776 | 0.7810 | 4 | 4 |
| Conoide Reno-Lavino - confinato inferiore | 4 | 0.7670 | 0.7491 | 4 | 4 |
| Conoidi montane e Sabbie gialle orientali | 4 | 0.7627 | 0.6947 | 4 | 3 |
| Conoide Sillaro - libero | 2 | 0.7608 | 0.7608 | 2 | 2 |
| Freatico di pianura fluviale | 10 | 0.7586 | 0.7543 | 10 | 10 |
| Conoide Zena-Idice - libero | 2 | 0.7034 | 0.7034 | 2 | 2 |
| Conoide Quaderna - confinato | 1 | 0.6870 | 0.6870 | 1 | 1 |
| Conoide Sillaro-Sellustra - confinato inferiore | 4 | 0.6750 | 0.5892 | 3 | 3 |
| Conoide Santerno - libero | 3 | 0.6631 | 0.6163 | 3 | 2 |
| Conoide Samoggia - confinato inferiore | 2 | 0.6093 | 0.6093 | 2 | 2 |
| Conoide Zena-Idice - confinato inferiore | 2 | 0.5631 | 0.5631 | 2 | 1 |

## Table S2

Trusted wells subset used for the core interpretation.

| station_code | municipality | gwb_name | depth_class | n_matches | corr_anom | best_lag_days |
| --- | --- | --- | --- | --- | --- | --- |
| BO57-01 | OZZANO DELL'EMILIA | Conoide Zena-Idice - confinato superiore | intermediate | 11 | 0.9467 | 90 |
| BO28-00 | CASTEL MAGGIORE | Pianura Alluvionale Appenninica - confinato superiore | intermediate | 11 | 0.9289 | 14 |
| BO89-00 | ZOLA PREDOSA | Conoide Reno-Lavino - confinato inferiore | deep | 15 | 0.9068 | -60 |
| BO-F12-00 | CASTENASO | Freatico di pianura fluviale | shallow | 15 | 0.8860 | 90 |
| BO-F21-00 | BOLOGNA | Freatico di pianura fluviale | shallow | 20 | 0.8841 | 14 |
| BO55-02 | SAN LAZZARO DI SAVENA | Conoide Zena-Idice - confinato superiore | intermediate | 12 | 0.8806 | 14 |
| BOF2-01 | CASTELLO D'ARGILE | Pianura Alluvionale Appenninica - confinato superiore | intermediate | 13 | 0.8480 | 90 |
| BO13-00 | CALDERARA DI RENO | Conoide Reno-Lavino - confinato inferiore | deep | 15 | 0.8299 | -60 |
| BOA5-00 | CASTENASO | Conoide Zena-Idice - confinato superiore | deep | 15 | 0.8118 | -30 |
| BOF9-00 | CASTELLO D'ARGILE | Pianura Alluvionale Appenninica - confinato superiore | deep | 13 | 0.8042 | 90 |
| BO60-00 | CASTEL SAN PIETRO TERME | Conoidi montane e Sabbie gialle orientali | deep | 12 | 0.8015 | 14 |
| BOF7-00 | BENTIVOGLIO | Pianura Alluvionale Appenninica - confinato superiore | intermediate | 14 | 0.7950 | -30 |
| BO-F15-00 | CASTEL GUELFO DI BOLOGNA | Freatico di pianura fluviale | shallow | 20 | 0.7749 | 0 |
| BO-F18-00 | MORDANO | Freatico di pianura fluviale | shallow | 18 | 0.7691 | 14 |
| BO-F04-00 | MALALBERGO | Freatico di pianura fluviale | shallow | 19 | 0.7658 | 60 |
| BO-F02-00 | SALA BOLOGNESE | Freatico di pianura fluviale | shallow | 20 | 0.7514 | 14 |
| BO47-01 | BOLOGNA | Conoide Reno-Lavino - libero | deep | 12 | 0.7496 | 14 |
| BO75-01 | CASTENASO | Conoide Zena-Idice - confinato superiore | intermediate | 13 | 0.7484 | 30 |
| BOF6-00 | ZOLA PREDOSA | Conoide Reno-Lavino - libero | deep | 12 | 0.7133 | 14 |
| BO30-00 | BOLOGNA | Conoide Reno-Lavino - confinato inferiore | deep | 84 | 0.7041 | 30 |
| BO-F16-00 | IMOLA | Freatico di pianura fluviale | shallow | 19 | 0.6748 | -30 |

## Table S3

Conditioning diagnostics before and after grouping / balancing.

| Formulation | kappa(J) | kappa(I) | Effective rank | Scale spread |
| --- | --- | --- | --- | --- |
| Old 5-layer patch | 2164655.2713 | 88113562818.4218 | 4 | 1261765.2246 |
| Old grouped patch | 45352.0671 | 2056809987.4801 | 2 | 30108.6344 |
| Current grouped multisensor | 69.8769 | 4882.7747 | 3 | 67.0005 |

## Table S4

SWOT overlap and matched-date summary.

| SWOT overlap metric | Value |
| --- | --- |
| RiverSP raw dates | 33 |
| LakeSP raw dates | 34 |
| RiverSP dates retained after nearest-date fusion | 9 |
| LakeSP dates retained after nearest-date fusion | 9 |
| Nearest-date tolerance (days) | 14 |

## Table S5

Synthetic validation metrics supporting the pre-stage feasibility check.

| Synthetic metric | Value |
| --- | --- |
| Sg state $R^2$ | 0.9809 |
| Load total $R^2$ | 0.9759 |
| TWS $R^2$ | 0.9795 |
| Deformation $R^2$ | 0.9797 |
