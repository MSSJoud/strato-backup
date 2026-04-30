# Hybrid MCMC + Swin + Physics Method

## Goal

Recover posterior W3RA storage states from InSAR deformation by combining:

1. a synthetic validation block used to verify identifiability and robustness
2. a Mehrnegar-style dynamic Bayesian state-space model in **deformation space**
3. a Swin residual learner in **state space**
4. a forward physics consistency check back to deformation

The target state is

$$
\mathbf{z}_{t,p}
=
\begin{bmatrix}
S0_{t,p} \\
Ss_{t,p} \\
Sd_{t,p} \\
Sg_{t,p} \\
Sr_{t,p}
\end{bmatrix},
$$

for time index $t$ and pixel or grid element $p$.

## Why This Differs From Mehrnegar

Mehrnegar assumes the observation and the model output are of the same kind:

$$
\mathbf{Y}_t \leftrightarrow \mathbf{Z}_t.
$$

In their GRACE case, both are storage-related quantities, so the MCMC estimates time-varying coefficients that reconcile modeled storage components with observed storage.

Here, the observation is InSAR deformation, not storage. So the W3RA state must first be pushed through a forward deformation model before the same logic applies. The key idea is therefore:

$$
\text{W3RA storage} \xrightarrow{\mathcal{F}} \text{modeled deformation},
$$

so that both sides of the Stage 1 Bayesian model live in deformation space.

## Forward Deformation Construction

To construct the predictor field in Stage 1, the W3RA state is converted into deformation through an elastic-plus-poroelastic forward model.

The intended full W3RA mapping is:

$$
\Delta \ell_t = \rho_w (S0_t + Ss_t + Sd_t + Sr_t),
$$

$$
\Delta p_t = \rho_w g \, \frac{Sg_t}{S_{\mathrm{eff}}},
$$

$$
u_t^{\text{load}} = G_{\text{load}} * \Delta \ell_t,
$$

$$
u_t^{\text{poro}} = G_{\text{poro}} * \Delta p_t,
$$

$$
u_t^{\text{tot}} = u_t^{\text{load}} + u_t^{\text{poro}}.
$$

To build a component-wise design matrix for MCMC, define:

$$
u_t^{(S0)} = \mathcal{F}_{\text{load}}(S0_t), \quad
u_t^{(Ss)} = \mathcal{F}_{\text{load}}(Ss_t), \quad
u_t^{(Sd)} = \mathcal{F}_{\text{load}}(Sd_t), \quad
u_t^{(Sr)} = \mathcal{F}_{\text{load}}(Sr_t), \quad
u_t^{(Sg)} = \mathcal{F}_{\text{poro}}(Sg_t).
$$

Then the deformation-side predictor vector at each $(t,p)$ is

$$
\mathbf{Z}_{t,p}
=
\begin{bmatrix}
u_{t,p}^{(S0)} &
u_{t,p}^{(Ss)} &
u_{t,p}^{(Sd)} &
u_{t,p}^{(Sg)} &
u_{t,p}^{(Sr)}
\end{bmatrix}.
$$

## Synthetic Validation Block

Synthetic validation is part of the method and should be completed before applying the workflow to real Bologna data.

Its role is to answer:

- can the deformation-space MCMC recover known latent states from forward-simulated deformation?
- can the Swin residual stage improve on the MCMC prior when the true residual is known?
- how sensitive is recovery to controlled observational corruption?

The synthetic workflow is:

1. generate synthetic W3RA-like storage layers
2. forward-convert them to deformation with the same elastic + poroelastic operator used in the real method
3. optionally add synthetic observation noise to the deformation field
4. run Stage 1 MCMC to obtain a posterior prior state
5. compare the posterior state against known synthetic truth
6. train Stage 2 residual learning against known synthetic residual
7. report clean and noisy recovery behavior

This validation block is not a separate deployed stage at inference time, but it is part of the overall scientific method because it establishes whether the inversion is capable of recovering the targeted signal under controlled conditions.

The synthetic data are generated as follows:

1. create smooth space-time storage fields for
   $$
   S0, Ss, Sd, Sg, Sr
   $$
2. convert them to deformation using the same forward model as in the real method
3. define a clean synthetic deformation cube
4. optionally add observation noise to that deformation cube for robustness experiments

In the clean validation case,

$$
\text{noise\_scale} = 0.00,
$$

which means no added synthetic noise.

## Stage 1: Dynamic MCMC Prior In Deformation Space

Stage 1 follows the Mehrnegar logic, but with deformation on both sides.

### Observation equation

$$
Y_{t,p} = \mathbf{Z}_{t,p} \, \boldsymbol{\theta}_{t,p} + \varepsilon_{t,p},
$$

with

$$
\varepsilon_{t,p} \sim \mathcal{N}(0, R_{t,p}).
$$

Here:

- $Y_{t,p}$ is observed InSAR deformation
- $\mathbf{Z}_{t,p}$ is the vector of forward-simulated deformation contributions from W3RA layers
- $\boldsymbol{\theta}_{t,p}$ is the latent coefficient vector

### Time evolution equation

Following Mehrnegar ESM.2, the latent coefficients evolve dynamically:

$$
\boldsymbol{\theta}_{t,p}
=
\boldsymbol{\theta}_{t-1,p}
+ \boldsymbol{\eta}_{t,p},
$$

with

$$
\boldsymbol{\eta}_{t,p} \sim \mathcal{N}(\mathbf{0}, \mathbf{Q}_{t,p}).
$$

### Important requirement

The latent coefficients must be free in **both space and time**:

$$
\boldsymbol{\theta}_{t,p} \neq \boldsymbol{\theta}_{t,p'}
\quad \text{and} \quad
\boldsymbol{\theta}_{t,p} \neq \boldsymbol{\theta}_{t',p}.
$$

This is the direct analogue of the Mehrnegar dynamic state-space logic.

### Posterior corrected state

Once $\boldsymbol{\theta}_{t,p}$ is estimated, the posterior corrected W3RA state is

$$
\mathbf{x}^{\text{prior}}_{t,p}
=
\boldsymbol{\theta}_{t,p} \odot \mathbf{z}_{t,p},
$$

where $\odot$ is elementwise multiplication and $\mathbf{z}_{t,p}$ is the original W3RA state vector.

So Stage 1 outputs:

- posterior mean state:
  $$
  \mathbf{x}^{\text{prior}}_{t,p}
  $$
- posterior uncertainty:
  $$
  \mathbf{\Sigma}^{\text{prior}}_{t,p}
  $$

These become the prior input to Stage 2.

## Stage 1 Synthetic Validation

Stage 1 should first be validated on synthetic data. This is important because, in real data, the true state is unknown.

### Synthetic protocol

1. Generate synthetic storage layers
2. Convert them to deformation using the same elastic + poroelastic forward operator
3. Add controlled noise
4. Run Stage 1 MCMC
5. Check whether the posterior state recovers the known synthetic truth

### Synthetic forward generation

The synthetic generator uses:

$$
\Delta \ell_t = \rho_w (S0_t + Ss_t + Sd_t),
$$

$$
\Delta p_t = \rho_w g \, \frac{Sg_t}{S_{\mathrm{eff}}},
$$

with additive noise:

- white noise
- spatially correlated noise
- seasonal noise

For the Bologna formulation, the load branch should include $Sr$ as well.

## Synthetic Noise Results

### Best noise setting

Across the synthetic noise-sweep benchmark, the best-performing regime is the clean case:

$$
\text{noise\_scale} = 0.00.
$$

For the balanced synthetic sweep, the best aggregate setting was:

| Training mode | Noise scale | Mean $R^2$ | Mean corr | Mean RMSE |
|---|---:|---:|---:|---:|
| `curriculum_balanced` | 0.00 | 0.559 | 0.759 | 4.952 |

### Best hybrid-style multiseed benchmark

For the hybrid-style multiseed residual-learning benchmark:

| Noise scale | Mean $R^2$ | Mean corr | Mean RMSE |
|---|---:|---:|---:|
| 0.00 | 0.729 | 0.855 | 3.810 |
| 0.01 | -0.086 | 0.022 | 7.846 |
| 0.02 | -0.127 | -0.020 | 7.992 |
| 0.05 | -0.179 | -0.016 | 8.169 |

Interpretation:

- the clean case is the correct validation anchor
- once additive noise is introduced, performance drops sharply
- therefore Stage 1 should first be validated under the clean synthetic regime, then reported under noise stress cases

## Stage 2: Swin Residual Correction In State Space

Stage 2 does **not** replace Stage 1. It corrects the Stage 1 posterior state estimate.

The Stage 1 to Stage 2 handoff can be summarized compactly as

$$
\mathbf{x}^{\text{prior}}_{t,p}

=
\boldsymbol{\theta}_{t,p} \odot \mathbf{z}_{t,p},
\qquad
\mathbf{x}^{\text{final}}_{t,p}
=
\mathbf{x}^{\text{prior}}_{t,p} + \hat{\mathbf{r}}_{t,p}.
$$

The Stage 1 prior state is:

$$
\mathbf{x}^{\text{prior}}_{t,p}
=
\boldsymbol{\theta}_{t,p} \odot \mathbf{z}_{t,p}.
$$

Define the unknown residual as:

$$
\mathbf{r}_{t,p}
=
\mathbf{x}_{t,p} - \mathbf{x}^{\text{prior}}_{t,p}.
$$

The Swin model estimates this residual from local spatiotemporal context:

$$
\hat{\mathbf{r}}_{t,p}
=
f_{\text{Swin}}
\left(
\mathbf{I}_{t-w+1:t,\mathcal{N}(p)},
\mathbf{C}_{\mathcal{N}(p)},
\mathbf{x}^{\text{prior}}_{t,\mathcal{N}(p)},
\mathbf{\Sigma}^{\text{prior}}_{t,\mathcal{N}(p)}
\right),
$$

where:

- $\mathbf{I}_{t-w+1:t,\mathcal{N}(p)}$ is the InSAR time window over a local neighborhood
- $\mathbf{C}_{\mathcal{N}(p)}$ is coherence and quality context
- $\mathbf{x}^{\text{prior}}$ is the Stage 1 prior state
- $\mathbf{\Sigma}^{\text{prior}}$ is the Stage 1 uncertainty

Then the corrected state is:

$$
\mathbf{x}^{\text{final}}_{t,p}
=
\mathbf{x}^{\text{prior}}_{t,p}
 + \hat{\mathbf{r}}_{t,p}.
$$

## Why Swin Is Useful Here

The map

$$
(\text{InSAR}, \text{coherence}, \text{prior}) \mapsto \text{state correction}
$$

is expected to be nonlinear and spatially structured. Swin is suitable because it can learn:

- local spatial context
- multiscale spatial organization
- short-term temporal patterns over the input window
- nonlinear corrections to the Bayesian prior

This is exactly the role of Stage 2.

For the applied Bologna case, the current empirical evidence is more conservative than the theoretical role above. The grouped real Stage 1 model already fits the observed deformation very strongly, and the present Stage 2 real runs do not yet improve the reconstructed full-map deformation fit. So, at the current stage of development, Stage 2 should be interpreted mainly as:

- a nonlinear diagnostic module for local space-time mismatch
- a possible learner of lagged deformation response relative to Stage 1 hydrologic states
- a research extension beyond the current stable applied grouped Stage 1 inversion

## Stage 3: Physics Closure Back To Deformation

The final corrected state must still explain the observed deformation:

$$
\hat{Y}_{t,p} = \mathcal{F}\left(\mathbf{x}^{\text{final}}_{t,p}\right).
$$

The real-data loss should therefore include at least:

### Physics consistency

$$
\mathcal{L}_{\text{phys}}
=
\left\|
\hat{Y}_t - Y_t
\right\|_2^2
$$

### Prior consistency

$$
\mathcal{L}_{\text{prior}}
=
\hat{\mathbf{r}}_t^\top
\left(\mathbf{\Sigma}^{\text{prior}}_t\right)^{-1}
\hat{\mathbf{r}}_t
$$

### Optional smoothness / regularization

$$
\mathcal{L}_{\text{tv}}
=
\mathrm{TV}\left(\mathbf{x}^{\text{final}}_t\right)
$$

Total loss:

$$
\mathcal{L}
=
\lambda_{\text{phys}} \mathcal{L}_{\text{phys}}
 + \lambda_{\text{prior}} \mathcal{L}_{\text{prior}}
 + \lambda_{\text{tv}} \mathcal{L}_{\text{tv}}.
$$

## Optional Constrained Extension

The default formulation above is the **pure model** and should be run first.

If external constraints are available later, they should be added as an optional extension to Stage 1, not as a replacement of the pure deformation-space formulation.

The Stage 1 state is still

$$
\mathbf{x}_{t,p}^{\text{prior}}
=
\boldsymbol{\theta}_{t,p} \odot \mathbf{z}_{t,p},
$$

but the posterior is now conditioned on additional observations or penalties:

$$
\pi(\boldsymbol{\Theta}\mid \mathbf{Y}^{\text{def}}, \mathbf{Y}^{\text{ext}})
\propto
\pi(\mathbf{Y}^{\text{def}}\mid \boldsymbol{\Theta})
\pi(\mathbf{Y}^{\text{ext}}\mid \boldsymbol{\Theta})
\pi(\boldsymbol{\Theta}).
$$

Equivalently, the negative log-posterior becomes the pure Stage 1 objective plus an external constraint term:

$$
J_{\text{constr}}(\boldsymbol{\Theta})
=
J_{\text{pure}}(\boldsymbol{\Theta})
+ \lambda_{\text{ext}} \, \mathcal{L}_{\text{ext}}(\boldsymbol{\Theta}).
$$

Here, $\mathbf{Y}^{\text{ext}}$ may represent any external hydrologic information that constrains selected components of the state. The methodological order should therefore be:

1. run the pure model with InSAR and deformation physics only
2. evaluate the posterior state and residual behavior
3. add external constraints and check whether they improve the posterior estimate

## Mathematical Note

The mathematical proof of feasibility, estimability, and the exact sense in which the estimates are optimal is given separately in:

- [MATHEMATICAL_PROOF_OF_ESTIMATION_FEASIBILITY.md](/home/ubuntu/work/insar_mcmc/MATHEMATICAL_PROOF_OF_ESTIMATION_FEASIBILITY.md)

## Real Bologna Note

The synthetic branch is only a validation block. The applied Bologna model must use

$$
Y = \text{real Bologna InSAR deformation},
\qquad
Z = \text{real W3RA state forward-converted to deformation components}.
$$

The first real Bologna Stage 1 tests showed two practical issues:

1. comparing raw InSAR deformation against W3RA anomalies is a preprocessing mismatch
2. the full 5-layer real deformation design can be strongly ill-conditioned, because some real load-side forward contributions are numerically tiny relative to the observed InSAR signal

Therefore, the current recommended real-data path is:

1. use anomaly / standardized observation space for the applied Stage 1 model
2. start the real inversion with grouped state channels
   - `Load_total = S0 + Ss + Sd + Sr`
   - `Sg`
3. use that grouped Stage 1 prior as the practical entry point to Stage 2 on real Bologna
4. only return to full 5-layer real refinement after the grouped real model is stable

The current applied Stage 2 implementation on real Bologna therefore learns grouped residuals for

$$
\bigl[\mathrm{Load\_total},\, Sg\bigr],
$$

using InSAR time windows and the grouped Stage 1 prior, with deformation-fit loss and prior regularization, before any later return to full five-layer refinement.

At present, the practical applied conclusion is:

1. grouped Stage 1 is the current stable real-data inversion result
2. grouped Stage 2 is still experimental
3. the most promising justification for Stage 2 is learning spatially varying temporal lag and local mismatch structure, rather than improving the already very strong Stage 1 deformation fit directly

For practical layered visualization and later comparison against external groundwater information such as wells, a conditional five-layer product can still be formed from the stable grouped Stage 1 result by:

1. taking the inferred grouped posterior `Load_total`
2. redistributing it back into `S0, Ss, Sd, Sr` using the corresponding W3RA layer shares
3. keeping `Sg` directly from the grouped posterior

This produces a useful layered diagnostic product, but it should be interpreted as a conditional decomposition of the grouped posterior, not as proof that the real five-layer inverse problem has already been uniquely identified.

## What The Method Finally Returns

The full method returns the posterior corrected storage state

$$
\mathbf{x}^{\text{final}}_{t,p}
=
\begin{bmatrix}
S0^{\text{final}}_{t,p} \\
Ss^{\text{final}}_{t,p} \\
Sd^{\text{final}}_{t,p} \\
Sg^{\text{final}}_{t,p} \\
Sr^{\text{final}}_{t,p}
\end{bmatrix}.
$$

So the primary output is not only $Sg$ and not only TWS. The primary output is the full posterior state vector.

From that state vector, groundwater is obtained directly as

$$
Sg^{\text{final}}_{t,p},
$$

and total water storage is derived as

$$
\mathrm{TWS}^{\text{final}}_{t,p}
=
S0^{\text{final}}_{t,p}
+ Ss^{\text{final}}_{t,p}
+ Sd^{\text{final}}_{t,p}
+ Sg^{\text{final}}_{t,p}
+ Sr^{\text{final}}_{t,p}.
$$

If needed, the load-only storage can also be derived as

$$
\mathrm{Load}^{\text{final}}_{t,p}
=
S0^{\text{final}}_{t,p}
+ Ss^{\text{final}}_{t,p}
+ Sd^{\text{final}}_{t,p}
+ Sr^{\text{final}}_{t,p}.
$$

## Recommended Implementation Order

1. Extend the forward physics to a 5-layer W3RA deformation operator:
   - load: `S0 + Ss + Sd + Sr`
   - poroelastic: `Sg`
2. Build the synthetic validation block for Stage 1 recovery
3. Validate Stage 1 against clean synthetic truth first
4. Report Stage 1 robustness under synthetic noise sweeps
5. Produce posterior prior state
   $$
   \mathbf{x}^{\text{prior}} = \boldsymbol{\theta} \odot \mathbf{z}
   $$
6. Build Stage 2 Swin residual learner
7. Pretrain Stage 2 on synthetic residual truth
8. Fine-tune Stage 2 on real InSAR with Stage 3 physics closure
9. For the real Bologna case, start Stage 2 with grouped `Load_total + Sg` priors before attempting full 5-layer refinement

## Bottom Line

The proposed hybrid is:

$$
\text{W3RA state}
\xrightarrow[\text{Stage 1 MCMC}]{\text{deformation-space Bayesian prior}}
\mathbf{x}^{\text{prior}}
\xrightarrow[\text{Stage 2 Swin}]{\text{nonlinear residual correction}}
\mathbf{x}^{\text{final}}
\xrightarrow[\text{Stage 3 physics}]{\mathcal{F}}
\hat{Y}.
$$

This is the intended full hybrid formulation:

- synthetic validation for identifiability and robustness
- Mehrnegar-style dynamic MCMC prior
- Swin residual correction
- final deformation consistency through physics

## Current Best Real-Data Result

For the current Bologna application, the strongest real-data result is not the full hybrid, but the **grouped balanced multisensor Kalman Stage 1** using:

- InSAR regional or tiled deformation anomalies
- GRACE mascon regional anomalies
- refreshed SMAP regional surface soil moisture

with the grouped state

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

In the corrected overlap run based on the newer MintPy scene, the grouped model is built on the shared MintPy/W3RA period

$$
2017\text{-}01\text{-}04 \;\; \text{to} \;\; 2024\text{-}08\text{-}01,
$$

with MintPy deformation aggregated onto the native W3RA grid. In the current best `InSAR + GRACE + refreshed SMAP` run, the grouped balanced Kalman model remains physically sane in scale:

- tiled `ShallowLoad` posterior max magnitude about `52.1 mm`
- tiled `DeepLoad` posterior max magnitude about `88.1 mm`
- tiled `Groundwater` posterior max magnitude about `48.1 mm`

and the regional posterior improves the currently reliable observation streams relative to the grouped prior, with approximate posterior $R^2$ values:

- InSAR: `0.971`
- GRACE: `0.487`
- SMAP: `0.618`

At the tiled-map level, the grouped posterior achieves an InSAR posterior $R^2$ of about `0.905`, again without leaving the physically plausible tens-of-mm range.

An independent well-based validation step is now also available. In its stronger current form, the grouped `Groundwater` state is compared against Bologna well-head anomalies after spatial interpolation to well locations and a lag search over plausible response delays. The results are encouraging:

- `83` station series can be evaluated
- all `83` are positive after best state / best lag matching
- `74` have correlation at least `0.3`
- `62` have correlation at least `0.5`
- the median anomaly correlation is about `0.704`
- the top-10 mean anomaly correlation is about `0.947`

Depth-stratified validation also looks physically sensible:

- shallow wells: median correlation about `0.767`
- intermediate wells: median correlation about `0.731`
- deep wells: median correlation about `0.617`

The best state is not always the grouped `Groundwater` component for every station, which is also reasonable in a coupled deformation system. Across the evaluated well panel:

- `Groundwater` is the best state for `42` stations
- `ShallowLoad` is the best state for `25` stations
- `DeepLoad` is the best state for `16` stations

Using simple reliability criteria, one can define a more conservative trusted external-validation panel consisting of:

- `6` trusted hydrogeologic groups
- `21` trusted stations

The trusted hydrogeologic groups are:

1. `Pianura Alluvionale Appenninica - confinato superiore`
2. `Freatico di pianura fluviale`
3. `Conoide Zena-Idice - confinato superiore`
4. `Conoide Reno-Lavino - libero`
5. `Conoide Reno-Lavino - confinato inferiore`
6. `Conoidi montane e Sabbie gialle orientali`

These well comparisons do not validate equality of units, because the grouped `Groundwater` state is a storage-like posterior quantity while the wells measure hydraulic head. They do, however, support temporal consistency of the grouped groundwater signal.

A separate SWOT-added Stage 1 test was also run. It works technically, but with only a few matched SWOT dates it does not materially improve the grouped result at present.

So the current best practical conclusion is:

1. grouped balanced multisensor Stage 1 is the best real-data direction so far
2. Stage 2 Swin remains experimental
3. the grouped `Groundwater` posterior now has encouraging independent support from wells
4. any later return to layered decomposition should start from this grouped posterior, not from the earlier ill-conditioned unconstrained inversion
