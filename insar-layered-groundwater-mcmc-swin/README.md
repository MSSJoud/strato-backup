# Hybrid MCMC and Physics-Aware Transformer-Based Inversion of Layered Hydrologic Storage from InSAR Deformation

Paper companion repository for:

**Hybrid MCMC and Physics-Aware Transformer-Based Inversion of Layered Hydrologic Storage from InSAR Deformation: Case Study of Emilia-Romagna, Italy**  
**Mehdi Joud** and **Chandrakanta Ojha**

## What this repository is

This repository collects the paper-facing code, notebooks, figures, and lightweight summary outputs for our layered-to-grouped hydrologic inversion workflow using:

- InSAR deformation time series
- W3RA hydrologic states
- GRACE mascon storage anomalies
- SMAP surface soil moisture
- exploratory SWOT surface-water constraints
- groundwater-well validation

The current supported real-data result is a **grouped Stage 1 multisensor estimator** for the Bologna / Emilia-Romagna case study, with independent support from groundwater wells.

## Method novelty

The methodological contribution of this work is the combination of:

1. **Bayesian MCMC inversion in deformation space**
2. **physics-aware grouping of layered hydrologic storage**
3. **multisensor balancing and Kalman-style state-space assimilation**
4. **physics-aware transformer residual learning as an exploratory Stage 2 extension**

In synthetic experiments, the inversion machinery is validated under known truth.  
In the real Emilia-Romagna application, the practically defensible estimator is the grouped multisensor posterior rather than a fully resolved five-layer recovery.

## What the method can currently do

- build a shared Bologna InSAR / W3RA overlap domain
- construct grouped hydrologic states from W3RA anomalies
- assimilate InSAR, GRACE, and refreshed SMAP in Stage 1
- test SWOT as an exploratory additional constraint
- validate the grouped groundwater signal against observed well-head anomalies
- generate paper figures, summary tables, and paper-facing notebooks

## Current study area

- **Region:** Emilia-Romagna, Italy
- **Applied case study:** Bologna overlap domain
- **Shared real-data overlap:** `2017-01-04` to `2024-08-01`
- **Shared grid used in the grouped inversion:** `22 x 24`

## Repository scope

This is a **clean paper companion repository**, not the full research workspace.

Included:

- core scripts used in the workflow
- paper-facing notebooks
- exported main and supplementary figures
- lightweight summary outputs (`.json`, `.csv`)
- method and results notes

Excluded on purpose:

- raw satellite data
- large intermediate arrays and model checkpoints
- local scratch outputs
- environment-specific absolute-path products

## Repository structure

```text
docs/          Method, theory, workflow, and paper-facing notes
scripts/       Core workflow and figure-generation scripts
notebooks/     Analysis and presentation notebooks
paper_figures/ Exported figures and figure/table captions
summaries/     Lightweight summary outputs used by the paper
```

## Recommended entry points

Start here if you want the paper-facing overview:

- `docs/PAPER_WORKFLOW_METHOD_DATA_RESULTS.md`
- `docs/CURRENT_RESULTS_SUMMARY.md`
- `paper_figures/paper_figures_notebook.ipynb`

For method details:

- `docs/HYBRID_MCMC_SWIN_METHOD.md`
- `docs/MATHEMATICAL_PROOF_OF_ESTIMATION_FEASIBILITY.md`
- `docs/CONDITIONING_METRICS_NOTE.tex`

For the main applied Stage 1 workflow:

- `scripts/stage1_bologna_multisensor_kalman.py`
- `scripts/stage1_bologna_multisensor_kalman_tiled.py`
- `scripts/validate_groundwater_against_wells.py`

## Installation

This repository is shared as a lightweight research companion. Some scripts depend on a larger local data environment and on geospatial/scientific Python packages.

A minimal starting point is:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Important note on reproducibility

Several scripts in this paper companion still reflect research-path conventions from the working environment used during development. A **containerized version is under development and will be published soon** to provide a cleaner end-to-end reproducible setup.

Until then, this repository should be understood as:

- a paper companion
- a code and figure release
- a transparent record of the workflow and current validated results

## Citation

If you use or refer to this repository, please cite the associated paper once available. A `CITATION.cff` file is included.

