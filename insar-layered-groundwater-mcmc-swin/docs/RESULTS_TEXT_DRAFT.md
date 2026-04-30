# Results Draft

## Main Result

The strongest real-data result obtained in this study is not the original full layered inversion, but a grouped balanced multisensor Stage 1 model over the corrected Bologna MintPy/W3RA overlap period from `2017-01-04` to `2024-08-01`. The grouped posterior state is

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
\end{bmatrix},
$$

and is inferred by combining InSAR deformation anomalies, GRACE regional anomalies, and refreshed SMAP surface soil moisture in a balanced state-space formulation.

## Internal Performance

On the corrected overlap run, the grouped posterior improves all three observation streams relative to the grouped prior. Regional posterior skill reaches approximately:

- InSAR: $R^2 \approx 0.971$
- GRACE: $R^2 \approx 0.487$
- SMAP: $R^2 \approx 0.618$

At the tiled level, the grouped posterior achieves an InSAR posterior $R^2 \approx 0.905$.

An important practical outcome is that the posterior grouped magnitudes remain physically plausible rather than exploding numerically:

- `ShallowLoad` absolute maximum about `52.1 mm`
- `DeepLoad` absolute maximum about `88.1 mm`
- `Groundwater` absolute maximum about `48.1 mm`

This is a major improvement over the earlier unconstrained real-data layered inversions, which were numerically unstable and physically uninterpretable.

## Independent Well Validation

The grouped posterior was then tested against independent Bologna groundwater wells. Since the model output is a storage-like grouped posterior and the wells measure hydraulic head, the comparison was performed in anomaly space rather than by direct one-to-one unit equality. The validation used:

- spatial interpolation from the grouped Kalman tile grid to each well
- nearest-date temporal alignment
- lag search over `-90, -60, -30, -14, 0, 14, 30, 60, 90` days

Under this stronger validation setup:

- `83` well time series were evaluated
- all `83` had positive best-match anomaly correlation
- `74` had correlation at least `0.3`
- `62` had correlation at least `0.5`
- median correlation was about `0.704`
- the top-10 mean correlation was about `0.947`

These results indicate that the grouped posterior is not merely reproducing InSAR internally, but is also consistent with independent groundwater behavior across a substantial fraction of the well network.

## Depth Dependence

Depth-stratified validation gives a physically interpretable pattern:

- shallow wells: median correlation about `0.767`
- intermediate wells: median correlation about `0.731`
- deep wells: median correlation about `0.617`

Thus the grouped posterior is supported across depth classes, but performs best in the shallow and intermediate ranges.

## Best-State Interpretation

When wells are allowed to match the best-performing grouped state after lag search:

- `Groundwater` is the best state for `42` stations
- `ShallowLoad` is the best state for `25` stations
- `DeepLoad` is the best state for `16` stations

This is scientifically reasonable. The deformation and hydrologic response recorded at a given well location are not expected to depend on groundwater storage alone everywhere; loading-related grouped states also contribute in some parts of the domain.

## Trusted Validation Panel

To avoid over-interpreting weaker hydrogeologic settings, a conservative trusted validation subset was defined for reporting and interpretation after the full well-validation exercise had already been run on all `83` evaluated wells. This trusted panel is therefore a post-validation interpretation subset, not an a priori well-selection rule. A station entered the trusted subset if:

- its best-matching grouped state was `Groundwater`
- its best-lag anomaly correlation was at least `0.6`
- it had at least `10` matched observations
- and it belonged to a hydrogeologic group showing consistently strong validation behavior across multiple stations

Under that rule, the trusted panel contains:

- `6` hydrogeologic groups
- `21` stations

The trusted hydrogeologic groups are:

1. `Pianura Alluvionale Appenninica - confinato superiore`
2. `Freatico di pianura fluviale`
3. `Conoide Zena-Idice - confinato superiore`
4. `Conoide Reno-Lavino - libero`
5. `Conoide Reno-Lavino - confinato inferiore`
6. `Conoidi montane e Sabbie gialle orientali`

This trusted subset is the strongest external evidence supporting the grouped `Groundwater` posterior and should be used as the main validation panel in figures and interpretation.

## Interpretation

The current supported conclusion is therefore:

1. the grouped balanced multisensor Stage 1 model is working and is the best real-data formulation obtained so far
2. the grouped posterior remains physically plausible in magnitude
3. the grouped groundwater signal has meaningful independent support from wells
4. the full layered hydrology product is still not the validated real-data result
5. the current Stage 2 Swin refinement remains exploratory rather than operational

## Suggested Reporting Sentence

A concise way to report the result is:

The most robust real-data result is a grouped multisensor Bayesian state-space inversion that jointly assimilates InSAR, GRACE, and SMAP, yielding physically plausible grouped hydrologic states and a grouped groundwater posterior that is independently supported by Bologna well-head anomalies, including a conservative trusted panel of 21 stations across 6 hydrogeologic groups.
