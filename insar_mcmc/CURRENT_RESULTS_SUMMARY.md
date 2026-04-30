# Current Results Summary

## Current Main Result

The current best real-data result is the **grouped balanced multisensor Stage 1** model on the corrected Bologna MintPy/W3RA overlap, using:

- InSAR deformation anomalies
- GRACE regional anomalies
- refreshed SMAP surface soil moisture

The grouped posterior state is

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

This is the current scientifically supported estimator. The earlier unconstrained layered inversion is not the supported result, and the current Stage 2 Swin residual learner is still experimental.

## Internal Validation

On the corrected overlap run:

- regional InSAR posterior $R^2 \approx 0.971$
- regional GRACE posterior $R^2 \approx 0.487$
- regional SMAP posterior $R^2 \approx 0.618$
- tiled InSAR posterior $R^2 \approx 0.905$

Posterior grouped magnitudes remain physically plausible:

- `ShallowLoad` abs max about `52.1 mm`
- `DeepLoad` abs max about `88.1 mm`
- `Groundwater` abs max about `48.1 mm`

## Independent Wells Validation

The grouped posterior was compared against Bologna wells using:

- spatial interpolation from the Kalman tile grid to each well
- nearest-date temporal matching
- lag search over
  $$
  -90,-60,-30,-14,0,14,30,60,90 \text{ days}
  $$

### Overall panel

- `83` station series evaluated
- all `83` positive after best state / best lag matching
- `74` with correlation at least `0.3`
- `62` with correlation at least `0.5`
- median correlation about `0.704`
- top-10 mean correlation about `0.947`

### By depth

- shallow wells: median correlation about `0.767`
- intermediate wells: median correlation about `0.731`
- deep wells: median correlation about `0.617`

### Best-state counts

- `Groundwater`: `42`
- `ShallowLoad`: `25`
- `DeepLoad`: `16`

This means the grouped groundwater signal is strongly supported, but the well response is not purely groundwater-only everywhere, which is physically plausible in a coupled loading / groundwater deformation system.

## Trusted Validation Subset

Using conservative reliability criteria, a trusted panel can be defined:

- `6` trusted hydrogeologic groups
- `21` trusted stations

Trusted hydrogeologic groups:

1. `Pianura Alluvionale Appenninica - confinato superiore`
2. `Freatico di pianura fluviale`
3. `Conoide Zena-Idice - confinato superiore`
4. `Conoide Reno-Lavino - libero`
5. `Conoide Reno-Lavino - confinato inferiore`
6. `Conoidi montane e Sabbie gialle orientali`

This trusted subset was defined after the full well-validation exercise as a conservative interpretation panel, not as an a priori selection rule. A station entered the trusted subset if its best-matching grouped state was `Groundwater`, its best-lag anomaly correlation was at least `0.6`, it had at least `10` matched observations, and it belonged to a hydrogeologic group that showed consistently strong validation behavior across multiple stations. This trusted subset is the recommended external-validation panel for figures, interpretation, and writing.

## Current Conclusion

The current supported conclusion is:

1. grouped balanced multisensor Stage 1 is working and is the best real-data formulation so far
2. the grouped posterior is physically sane in scale
3. the grouped groundwater component has encouraging independent support from wells
4. full layered hydrology is still not the validated real-data result
5. Stage 2 Swin should still be treated as exploratory rather than as the main estimator

## Key Files

- [hybrid_results_notebook.ipynb](/home/ubuntu/work/insar_mcmc/hybrid_results_notebook.ipynb)
- [well_validation_summary_panel.png](/home/ubuntu/work/insar_mcmc/outputs_well_validation/figures/well_validation_summary_panel.png)
- [trusted_wells_map.png](/home/ubuntu/work/insar_mcmc/outputs_well_validation/figures/trusted_wells_map.png)
- [trusted_aquifer_groups.png](/home/ubuntu/work/insar_mcmc/outputs_well_validation/figures/trusted_aquifer_groups.png)
- [top6_station_timeseries.png](/home/ubuntu/work/insar_mcmc/outputs_well_validation/figures/top6_station_timeseries.png)
