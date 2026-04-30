# Synthetic demo

This repository includes a minimal synthetic grouped inversion demo so that visitors can run something immediately in the container before the full scientific workflow is fully migrated.

## What it does

The demo:

- generates synthetic grouped hydrologic states
  - `ShallowLoad`
  - `DeepLoad`
  - `Groundwater`
- generates synthetic observations
  - `InSAR`
  - `GRACE`
  - `SMAP`
- applies a simple grouped state-space update
- compares prior and posterior performance
- writes a figure, summary JSON, and time-series CSV

## Run

```bash
docker compose run --rm app hisi demo-synthetic --output-dir /workspace/outputs/demo
```

## Outputs

- `outputs/demo/synthetic_demo_summary.json`
- `outputs/demo/synthetic_demo_timeseries.csv`
- `outputs/demo/synthetic_demo_figure.png`

## Why it is useful

This demo is not the full Emilia-Romagna scientific workflow. Instead, it gives a visitor:

- a working container command
- a reproducible example output
- an immediate sense of the grouped inversion idea

It is the first practical entry point while the larger path-cleanup and workflow migration are still in progress.

