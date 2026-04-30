# Mathematical Proof Of Estimation Feasibility

In this part I am going to prove what kind of estimates can be called optimal in this hybrid model, under which assumptions this is true, and in what sense the resulting estimates are acceptable. The correct conclusion is not that the method always gives a unique physical truth, but that under the model assumptions it gives a well-defined posterior estimate, and that this estimate is optimal in the Bayesian decision-theoretic sense associated with the chosen loss.

## 1. Functional Setting

Let $\Omega \subset \mathbb{R}^2$ be the spatial domain and let $T \in \mathbb{N}$ be the number of acquisition times.

Define the state space

$$
X = \left(L^2(\Omega)\right)^5,
$$

with state

$$
\mathbf{x}_t =
\begin{bmatrix}
S0_t \\
Ss_t \\
Sd_t \\
Sg_t \\
Sr_t
\end{bmatrix}
\in X.
$$

The observation space is

$$
Y = L^2(\Omega).
$$

After discretization on a grid with $P$ spatial cells, these become

$$
X_h = \mathbb{R}^{5P},
\qquad
Y_h = \mathbb{R}^{P}.
$$

The time-stacked spaces are

$$
\mathcal{X}_h = \mathbb{R}^{5PT},
\qquad
\mathcal{Y}_h = \mathbb{R}^{PT}.
$$

## 2. Forward Operator

Define the linear forward deformation operator

$$
\mathcal{A} : X \to Y
$$

by

$$
\mathcal{A}(\mathbf{x}_t)
=
G_{\mathrm{load}} * (S0_t + Ss_t + Sd_t + Sr_t)
+ G_{\mathrm{poro}} * Sg_t.
$$

After discretization this is a matrix operator

$$
A_h : X_h \to Y_h.
$$

Let $\mathbf{z}_t \in X_h$ denote the W3RA prior state, and define the diagonal multiplication operator

$$
D(\mathbf{z}_t) : \mathbb{R}^{5P} \to X_h,
\qquad
D(\mathbf{z}_t)\boldsymbol{\theta}_t = \boldsymbol{\theta}_t \odot \mathbf{z}_t.
$$

Then the Stage 1 prior state is

$$
\mathbf{x}^{\mathrm{prior}}_t = D(\mathbf{z}_t)\boldsymbol{\theta}_t.
$$

The observation model becomes

$$
\mathbf{y}_t = A_h D(\mathbf{z}_t)\boldsymbol{\theta}_t + \boldsymbol{\varepsilon}_t.
$$

## 3. Dynamic Bayesian State-Space Model

For each time step:

### Observation equation

$$
\mathbf{y}_t = H_t \boldsymbol{\theta}_t + \boldsymbol{\varepsilon}_t,
\qquad
H_t := A_h D(\mathbf{z}_t),
$$

with

$$
\boldsymbol{\varepsilon}_t \sim \mathcal{N}(\mathbf{0}, R_t).
$$

### Evolution equation

$$
\boldsymbol{\theta}_t = \boldsymbol{\theta}_{t-1} + \boldsymbol{\eta}_t,
$$

with

$$
\boldsymbol{\eta}_t \sim \mathcal{N}(\mathbf{0}, Q_t).
$$

Assume:

1. each $R_t \succ 0$
2. each $Q_t \succ 0$
3. the prior on $\boldsymbol{\theta}_1$ is proper Gaussian:
   $$
   \boldsymbol{\theta}_1 \sim \mathcal{N}(m_0, P_0), \qquad P_0 \succ 0
   $$
4. the discretized model is finite-dimensional

## 4. Existence Of The Posterior

Let

$$
\boldsymbol{\Theta} :=
\begin{bmatrix}
\boldsymbol{\theta}_1 \\
\vdots \\
\boldsymbol{\theta}_T
\end{bmatrix}
\in \mathcal{X}_h.
$$

Let the stacked observation vector be

$$
\mathbf{y} :=
\begin{bmatrix}
\mathbf{y}_1 \\
\vdots \\
\mathbf{y}_T
\end{bmatrix}
\in \mathcal{Y}_h.
$$

Then the dynamic model induces a Gaussian prior

$$
\boldsymbol{\Theta} \sim \mathcal{N}(\mathbf{m}_0, \Sigma_0),
$$

for some proper covariance $\Sigma_0 \succ 0$ determined by $P_0$ and the $Q_t$.

The likelihood is Gaussian:

$$
\mathbf{y}\mid \boldsymbol{\Theta}
\sim
\mathcal{N}(K\boldsymbol{\Theta}, R),
$$

where $K$ is the stacked observation operator and $R$ is block diagonal from the $R_t$.

Therefore by Bayes' theorem:

$$
\pi(\boldsymbol{\Theta}\mid \mathbf{y})
\propto
\exp\left(
-\frac12 \|\mathbf{y} - K\boldsymbol{\Theta}\|_{R^{-1}}^2
-\frac12 \|\boldsymbol{\Theta} - \mathbf{m}_0\|_{\Sigma_0^{-1}}^2
\right).
$$

Since both terms are coercive quadratic forms, the posterior is proper Gaussian. Hence:

### Proposition 1

Under the assumptions above, the posterior distribution $\pi(\boldsymbol{\Theta}\mid \mathbf{y})$ exists, is unique, and has finite first and second moments.

## 5. The Posterior Mean And The MAP

Because the posterior is Gaussian, it has the form

$$
\boldsymbol{\Theta}\mid \mathbf{y}
\sim
\mathcal{N}(\hat{\boldsymbol{\Theta}}, \Sigma_{\mathrm{post}}),
$$

with

$$
\Sigma_{\mathrm{post}}
=
\left(K^\top R^{-1}K + \Sigma_0^{-1}\right)^{-1},
$$

and

$$
\hat{\boldsymbol{\Theta}}
=
\Sigma_{\mathrm{post}}
\left(K^\top R^{-1}\mathbf{y} + \Sigma_0^{-1}\mathbf{m}_0\right).
$$

This vector is both:

1. the posterior mean
2. the unique maximizer of the posterior density

because a Gaussian density is maximized at its mean.

### Proposition 2

In the linear-Gaussian Stage 1 model, the posterior mean and the MAP estimator coincide.

So in this case the estimate is not merely a maximum-likelihood estimator. It is a regularized Bayesian estimator, and its optimality comes from Bayesian risk minimization.

## 6. In What Sense Is It A Best Estimate?

The phrase "best estimate" must be defined with respect to a loss.

### Theorem 1: Posterior Mean Is Bayes-Optimal Under Squared Loss

Let the loss be

$$
L_2(\tilde{\boldsymbol{\Theta}}, \boldsymbol{\Theta})
=
\|\tilde{\boldsymbol{\Theta}} - \boldsymbol{\Theta}\|_2^2.
$$

Then the Bayes estimator is

$$
\tilde{\boldsymbol{\Theta}}^{\ast}
=
\mathbb{E}[\boldsymbol{\Theta}\mid \mathbf{y}].
$$

#### Proof

Consider the posterior expected loss:

$$
\mathbb{E}\left[
\|\tilde{\boldsymbol{\Theta}} - \boldsymbol{\Theta}\|_2^2
\mid \mathbf{y}
\right].
$$

Expand around the posterior mean $\bar{\boldsymbol{\Theta}} := \mathbb{E}[\boldsymbol{\Theta}\mid \mathbf{y}]$:

$$
\|\tilde{\boldsymbol{\Theta}} - \boldsymbol{\Theta}\|_2^2
=
\|\tilde{\boldsymbol{\Theta}} - \bar{\boldsymbol{\Theta}}\|_2^2
+ \|\boldsymbol{\Theta} - \bar{\boldsymbol{\Theta}}\|_2^2
- 2\langle \tilde{\boldsymbol{\Theta}} - \bar{\boldsymbol{\Theta}}, \boldsymbol{\Theta} - \bar{\boldsymbol{\Theta}} \rangle.
$$

Taking posterior expectation, the cross term vanishes, so

$$
\mathbb{E}\left[
\|\tilde{\boldsymbol{\Theta}} - \boldsymbol{\Theta}\|_2^2
\mid \mathbf{y}
\right]
=
\|\tilde{\boldsymbol{\Theta}} - \bar{\boldsymbol{\Theta}}\|_2^2
+ \mathbb{E}\left[\|\boldsymbol{\Theta} - \bar{\boldsymbol{\Theta}}\|_2^2 \mid \mathbf{y}\right].
$$

The second term does not depend on $\tilde{\boldsymbol{\Theta}}$, so the minimum is attained uniquely at

$$
\tilde{\boldsymbol{\Theta}} = \bar{\boldsymbol{\Theta}}.
$$

Therefore

$$
\tilde{\boldsymbol{\Theta}}^{\ast}
=
\mathbb{E}[\boldsymbol{\Theta}\mid \mathbf{y}].
$$

This proves that the posterior mean is the best estimator under posterior quadratic risk.

### Theorem 2: MAP Minimizes The Negative Log-Posterior

Let the objective be

$$
J(\boldsymbol{\Theta})
:=
-\log \pi(\boldsymbol{\Theta}\mid \mathbf{y}).
$$

Then the MAP estimator

$$
\hat{\boldsymbol{\Theta}}_{\mathrm{MAP}}
=
\arg\min_{\boldsymbol{\Theta}} J(\boldsymbol{\Theta})
$$

is the minimizer of the negative log-posterior, equivalently the penalized least-squares objective

$$
J(\boldsymbol{\Theta})
=
\frac12 \|\mathbf{y} - K\boldsymbol{\Theta}\|_{R^{-1}}^2
+ \frac12 \|\boldsymbol{\Theta} - \mathbf{m}_0\|_{\Sigma_0^{-1}}^2
+ \text{const}.
$$

So if by "best negative estimator" one means the minimizer of the negative log-posterior, then the MAP is exactly that object.

## 7. From $\boldsymbol{\theta}$ To The Posterior State

The posterior prior state is

$$
\mathbf{x}^{\mathrm{prior}}_t
=
D(\mathbf{z}_t)\hat{\boldsymbol{\theta}}_t
=
\hat{\boldsymbol{\theta}}_t \odot \mathbf{z}_t.
$$

Thus the induced estimator for the state is a transformed posterior estimator. If $\hat{\boldsymbol{\theta}}_t$ is the posterior mean, then

$$
\hat{\mathbf{x}}^{\mathrm{prior}}_t
=
D(\mathbf{z}_t)\mathbb{E}[\boldsymbol{\theta}_t\mid \mathbf{y}]
$$

is the corresponding posterior mean in the transformed parameterization because $D(\mathbf{z}_t)$ is linear in $\boldsymbol{\theta}_t$ once $\mathbf{z}_t$ is fixed.

## 8. What Cannot Be Claimed

The previous results do **not** prove that the recovered state is the unique physical truth.

The reason is that the forward operator is not injective on the full 5-layer state space. Indeed, the load layers enter through the same elastic kernel:

$$
\mathcal{A}(\mathbf{x}_t)
=
G_{\mathrm{load}} * (S0_t + Ss_t + Sd_t + Sr_t)
+ G_{\mathrm{poro}} * Sg_t.
$$

Hence any perturbation satisfying

$$
\delta S0_t + \delta Ss_t + \delta Sd_t + \delta Sr_t = 0,
\qquad
\delta Sg_t = 0,
$$

lies in the null space of the load contribution. Therefore:

### Proposition 3

The full 5-layer state is not uniquely identifiable from deformation alone without additional structure.

So the mathematically correct claim is:

- not unique inversion from deformation alone
- but existence of a proper posterior
- existence of Bayes-optimal estimates under chosen losses
- regularized, stable conditional estimation under the model assumptions

## 9. Short Constrained Extension

The pure model above is the default model and should be analyzed first.

If additional external constraints are introduced, the only formal change is that the posterior is conditioned on more information. Let $\mathbf{c}$ denote any extra observation or constraint data. Then

$$
\pi(\boldsymbol{\Theta}\mid \mathbf{y}, \mathbf{c})
\propto
\pi(\mathbf{y}\mid \boldsymbol{\Theta})
\pi(\mathbf{c}\mid \boldsymbol{\Theta})
\pi(\boldsymbol{\Theta}).
$$

Equivalently, the negative log-posterior becomes

$$
J_{\mathrm{constr}}(\boldsymbol{\Theta})
=
J_{\mathrm{pure}}(\boldsymbol{\Theta})
+ J_{\mathrm{ext}}(\boldsymbol{\Theta}).
$$

If $\pi(\mathbf{c}\mid \boldsymbol{\Theta})$ is proper Gaussian, or more generally if $J_{\mathrm{ext}}$ is proper, lower-semicontinuous, and coercive, then the same conclusions still follow:

1. the posterior remains proper
2. the MAP still minimizes the augmented negative log-posterior
3. the posterior mean remains Bayes-optimal under squared loss

So the constrained model does not require a new proof from scratch. It only augments the posterior by an extra proper likelihood or penalty term, and the rest follows under the same regularity assumptions.

## 10. Real-Data Conditioning Note

The results above prove existence and Bayesian optimality under the assumed model, but they do not guarantee that every applied real-data discretization is numerically well-conditioned.

In the real Bologna case, a practical difficulty appears when the forward-converted real predictors have very different amplitudes. If some columns of the real deformation design matrix are extremely small, then the posterior may still exist, but the inferred coefficients can become numerically unstable or physically uninformative.

So the correct real-data interpretation is:

1. the Bayesian estimator still exists under the assumed model
2. but the applied inverse problem may be poorly conditioned
3. therefore grouping state components can be the mathematically and numerically preferable first applied model

That is why the recommended first applied real-data state is

$$
\mathbf{x}_t^{\mathrm{grp}}
=
\begin{bmatrix}
\mathrm{ShallowLoad}_t \\
\mathrm{DeepLoad}_t \\
\mathrm{Groundwater}_t
\end{bmatrix},
\qquad
\mathrm{ShallowLoad}_t = S0_t + Ss_t,
\qquad
\mathrm{DeepLoad}_t = Sd_t + Sr_t,
\qquad
\mathrm{Groundwater}_t = Sg_t.
$$

The rest of the Bayesian and residual-learning formulation then follows in the same way, but on a better-conditioned grouped state space.

In the current applied Bologna implementation, Stage 2 is therefore first posed on this grouped state space rather than on the full five-layer real state, so that the residual estimator acts on a numerically better-conditioned posterior prior.

The current corrected grouped balanced multisensor Kalman implementation, using the newer MintPy scene aggregated onto the native W3RA grid over the shared period 2017-01-04 to 2024-08-01, is consistent with this argument: the grouped posterior stays in a tens-of-mm range rather than exploding to unphysical magnitudes, while posterior fit improves strongly over the grouped prior for InSAR, GRACE, and refreshed SMAP. Therefore the present evidence supports grouped balanced multisensor inference as the practically feasible real-data formulation, even though unconstrained full layered inversion is not practically feasible here.

An additional independent validation step is now available through Bologna groundwater wells. This does not identify the grouped groundwater state by equality of units, because the model output is a storage-like grouped posterior while the wells measure hydraulic head. However, after spatial interpolation to well locations and a lag search over plausible response delays, the grouped validation becomes substantially stronger: the evaluated station panel shows a positive best-match correlation throughout, with many stations in the moderate-to-strong range and a conservative trusted subset of hydrogeologic groups and stations. This strengthens the practical case that the grouped posterior is not merely an internal deformation-fitting artifact.

## 11. Role Of Stage 2

The Stage 1 to Stage 2 transition can be summarized as

$$
\mathbf{x}^{\mathrm{prior}}_t
=
\boldsymbol{\theta}_t \odot \mathbf{z}_t,
\qquad
\mathbf{x}^{\mathrm{final}}_t
=
\mathbf{x}^{\mathrm{prior}}_t + \hat{\mathbf{r}}_t.
$$

Let

$$
\mathbf{r}_t = \mathbf{x}_t - \mathbf{x}^{\mathrm{prior}}_t
$$

be the residual state.

Stage 2 learns a nonlinear residual map

$$
\hat{\mathbf{r}}_t = f_{\phi}(\xi_t),
$$

where $\xi_t$ collects:

- InSAR time windows
- coherence fields
- the Stage 1 prior state
- the Stage 1 posterior uncertainty

The final estimate is

$$
\mathbf{x}^{\mathrm{final}}_t
=
\mathbf{x}^{\mathrm{prior}}_t + \hat{\mathbf{r}}_t.
$$

What can be justified here is representational feasibility: in finite dimensions, a sufficiently expressive neural network can approximate continuous residual maps on compact sets. What cannot be proved in general is that optimization always finds the global best residual corrector.

For the current applied Bologna case, the theoretical existence of such a residual corrector should be distinguished from empirical usefulness. The present grouped real-data experiments show that Stage 1 already explains deformation extremely well on the reconstructed full map, whereas the current Stage 2 variants do not improve that full-map deformation criterion. Therefore the mathematically honest interpretation is:

1. Stage 2 remains a feasible nonlinear residual model in principle
2. but in the current applied real setting it is better regarded as an auxiliary lag/mismatch learner than as the primary estimator
3. the current stable applied estimator remains the grouped Stage 1 posterior prior

Likewise, if a five-layer product is later constructed by decomposing the stable grouped posterior `Load_total` into `S0, Ss, Sd, Sr` using W3RA layer shares while keeping `Sg` directly from the grouped posterior, that object is best understood as a conditional post-processing decomposition of the grouped estimate. It is useful diagnostically, but it does not by itself establish independent identifiability of each real load-side layer.

## 12. Final Conclusion

Under the linear-Gaussian Stage 1 model:

1. the posterior exists and is unique
2. the posterior mean is the Bayes estimator under squared loss
3. the MAP estimator minimizes the negative log-posterior
4. the induced state estimate
   $$
   \hat{\mathbf{x}}^{\mathrm{prior}}_t
   =
   \hat{\boldsymbol{\theta}}_t \odot \mathbf{z}_t
   $$
   is therefore a proper posterior estimate

So the strongest correct statement is:

The method yields best estimates in the Bayesian sense determined by the chosen loss function and prior assumptions, not necessarily unique physical truth and not necessarily plain maximum-likelihood estimates.

For the present Bologna application, the practical estimator that is currently supported by both internal multisensor fit and independent wells validation is the grouped balanced Stage 1 posterior, not the earlier unconstrained layered inversion and not the present Stage 2 residual learner.
