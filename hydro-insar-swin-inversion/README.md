# hydro-insar-swin-inversion

Container-oriented software repository for **physics-aware inversion of hydrologic storage from InSAR deformation and multisensor constraints**.

This repository is the **software-side companion** to the paper-facing repository:

- Paper companion: `https://github.com/MSSJoud/insar-layered-groundwater-mcmc-swin`

The paper case study is:

**Hybrid MCMC and Physics-Aware Transformer-Based Inversion of Layered Hydrologic Storage from InSAR Deformation: Case Study of Emilia-Romagna, Italy**  
**Mehdi Joud** and **Chandrakanta Ojha**

## Purpose of this repository

This repository is intended to become the reusable, containerized software framework behind the paper workflow.

Compared with the paper repository, this repo focuses on:

- containerized execution
- reusable configuration
- study-area portability
- clearer data mounts and runtime layout
- software-oriented documentation

The Emilia-Romagna application is included as an **example case**, not as the only intended use.

## Current status

This is the **initial container-ready scaffold** of the software repository.

Included now:

- Dockerfile and `docker-compose.yml`
- Python package skeleton
- CLI entry point
- runnable synthetic grouped inversion demo
- configuration schema and example config
- data layout and container usage documentation
- Emilia-Romagna example configuration

Still under active migration from the research workspace:

- full end-to-end pipeline wiring
- path cleanup for all legacy scripts
- study-area-generic execution wrappers
- fully reproducible example runs
- automated tests for the full workflow

So the repository is already useful as a **software foundation**, but it is not yet the final fully automated pipeline release.

## Scientific scope

The framework is intended to support:

- grouped or layered hydrologic storage inversion from InSAR deformation
- Bayesian / MCMC inversion components
- multisensor balancing and state-space assimilation
- external constraints such as GRACE, SMAP, SWOT, and wells
- optional transformer-based residual refinement

## Why containerization matters here

A container is especially valuable for this project because it stabilizes:

- geospatial dependencies such as `rasterio`, `xarray`, `netCDF4`, `h5py`
- notebook and plotting environments
- scientific Python versioning
- reproducibility across different machines

The design goal is:

- code inside the container
- data mounted from the host
- outputs written to mounted folders

## Repository layout

```text
src/hydro_insar_swin_inversion/  Python package
app/                             Container entrypoint helpers
configs/                         Example configs
docs/                            Software and runtime documentation
examples/                        Example case descriptions
scripts/                         Future workflow wrappers
```

## Quick start

### Build

```bash
docker compose build
```

### Validate the default example config

```bash
docker compose run --rm app hisi check-config /workspace/configs/emilia_romagna.example.yaml
```

### Print runtime paths

```bash
docker compose run --rm app hisi show-paths /workspace/configs/emilia_romagna.example.yaml
```

### Run the minimal synthetic demo

```bash
docker compose run --rm app hisi demo-synthetic --output-dir /workspace/outputs/demo
```

This writes:

- `outputs/demo/synthetic_demo_summary.json`
- `outputs/demo/synthetic_demo_timeseries.csv`
- `outputs/demo/synthetic_demo_figure.png`

### Start a notebook server

```bash
docker compose up notebook
```

## Data model

This repository assumes mounted host directories such as:

- `/workspace` for the repo itself
- `/data/raw` for raw or externally managed datasets
- `/data/derived` for intermediate derived products
- `/workspace/outputs` for generated outputs within the repo working tree

See:

- `docs/DATA_LAYOUT.md`
- `docs/CONTAINER_USAGE.md`

## Example case

The repository ships with an example config for:

- Emilia-Romagna / Bologna overlap workflow

See:

- `configs/emilia_romagna.example.yaml`
- `examples/emilia_romagna.md`

## Relationship to the paper repository

Recommended usage:

- use the **paper repository** for figures, manuscript-facing summaries, and validated case-study outputs
- use this **software repository** for reusable execution, containerization, and future generalization to other study areas

## Roadmap

Short-term:

- migrate core Stage 1 grouped workflow into config-driven wrappers
- make notebook and figure generation run entirely from mounted inputs
- add sample execution commands for the Emilia-Romagna example

Medium-term:

- support multiple study areas cleanly
- expand the synthetic demo into a fuller reproducible tutorial
- add tests and CI checks

Long-term:

- release a stable, fully reproducible containerized workflow
