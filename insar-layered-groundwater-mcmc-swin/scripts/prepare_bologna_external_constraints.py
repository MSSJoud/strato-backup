#!/usr/bin/env python3
"""Prepare Bologna external-constraint products.

Current scope:
- reuse the Punjab GRACE mascon alignment workflow for Bologna
- export a compact JSON spec with the Bologna bbox/time span

This script does not download remote data. It prepares local products that can
be consumed by later Stage 1 constrained experiments.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from punjab.punjab_inversion.priors import (  # noqa: E402
    align_grace_to_punjab_dates,
    basin_mean_timeseries,
    compute_grace_anomalies,
    summarize_grace_alignment,
)
from insar_mcmc.mintpy_h5_utils import load_insar_domain  # noqa: E402


@dataclass
class BolognaExternalConfig:
    insar_path: str = "/mnt/data/aoi_3_bologna/mintpy_filtered/timeseries_SET_ERA5_ramp_demErr.h5"
    grace_path: str = "/mnt/data/punjab_grace_mascon_l3/GRCTellus.JPL.200204_202512.GLO.RL06.3M.MSCNv04CRI.nc"
    grace_variable: str = "lwe_thickness"
    grace_uncertainty_variable: str = "uncertainty"
    output_dir: str = "/home/ubuntu/work/insar_mcmc/outputs_external_constraints"
    write_aligned_dataset: bool = True


def normalize_longitude_for_dataset(lon_value: float, lon_coords) -> float:
    lon_min = float(lon_coords.min())
    lon_max = float(lon_coords.max())
    if lon_min >= 0.0 and lon_max > 180.0 and lon_value < 0.0:
        return lon_value % 360.0
    return lon_value


def subset_grace_to_bbox(grace_ds: xr.Dataset, bbox: dict, variable_names: list[str]) -> xr.Dataset:
    lat0, lat1 = sorted((bbox["lat_min"], bbox["lat_max"]))
    ds = grace_ds[variable_names]
    lat_name = "lat" if "lat" in ds.coords else "latitude"
    lon_name = "lon" if "lon" in ds.coords else "longitude"

    lat_vals = ds[lat_name].values
    lon_vals = ds[lon_name].values
    lon0 = normalize_longitude_for_dataset(bbox["lon_min"], lon_vals)
    lon1 = normalize_longitude_for_dataset(bbox["lon_max"], lon_vals)
    lon0, lon1 = sorted((lon0, lon1))

    lat_step = abs(float(lat_vals[1] - lat_vals[0])) if lat_vals.size > 1 else 0.5
    lon_step = abs(float(lon_vals[1] - lon_vals[0])) if lon_vals.size > 1 else 0.5
    lat_pad = max(lat_step / 2.0, 0.25)
    lon_pad = max(lon_step / 2.0, 0.25)

    lat_slice = (
        slice(lat0 - lat_pad, lat1 + lat_pad)
        if float(lat_vals[0]) <= float(lat_vals[-1])
        else slice(lat1 + lat_pad, lat0 - lat_pad)
    )
    lon_slice = (
        slice(lon0 - lon_pad, lon1 + lon_pad)
        if float(lon_vals[0]) <= float(lon_vals[-1])
        else slice(lon1 + lon_pad, lon0 - lon_pad)
    )
    return ds.sel({lat_name: lat_slice, lon_name: lon_slice})


def run(cfg: BolognaExternalConfig) -> dict:
    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    domain = load_insar_domain(cfg.insar_path)
    bbox = {
        "lat_min": domain["lat_min"],
        "lat_max": domain["lat_max"],
        "lon_min": domain["lon_min"],
        "lon_max": domain["lon_max"],
    }

    grace_ds = xr.open_dataset(cfg.grace_path)
    try:
        variables = [cfg.grace_variable]
        if cfg.grace_uncertainty_variable in grace_ds.data_vars:
            variables.append(cfg.grace_uncertainty_variable)

        grace_bbox = subset_grace_to_bbox(grace_ds, bbox, variables)
        grace_aligned = align_grace_to_punjab_dates(
            grace_bbox,
            domain["times"],
            variable=cfg.grace_variable,
        )
        grace_anom = compute_grace_anomalies(grace_aligned, variable=cfg.grace_variable)
        grace_ts = basin_mean_timeseries(grace_aligned, variables=(cfg.grace_variable,))
        grace_ts_anom = basin_mean_timeseries(grace_anom, variables=(cfg.grace_variable,))
        grace_ts[f"{cfg.grace_variable}_mean_anom"] = grace_ts_anom[f"{cfg.grace_variable}_mean"].values

        summary = summarize_grace_alignment(grace_aligned, cfg.grace_variable, anomaly_ds=grace_anom)
        summary["config"] = asdict(cfg)
        summary["bologna_bbox"] = bbox
        summary["insar_time_start"] = str(domain["times"][0].date())
        summary["insar_time_end"] = str(domain["times"][-1].date())
        summary["insar_n_times"] = int(len(domain["times"]))
        summary["insar_shape"] = {"height": domain["height"], "width": domain["width"]}

        spec = {
            "bbox": bbox,
            "temporal": [str(domain["times"][0].date()), str(domain["times"][-1].date())],
            "insar_path": cfg.insar_path,
            "grace_path": cfg.grace_path,
        }

        (out_dir / "bologna_external_constraint_spec.json").write_text(json.dumps(spec, indent=2))
        (out_dir / "bologna_grace_alignment_summary.json").write_text(json.dumps(summary, indent=2))
        grace_ts.to_csv(out_dir / "bologna_grace_region_timeseries.csv", index=False)
        pd.DataFrame([summary]).to_csv(out_dir / "bologna_grace_alignment_table.csv", index=False)

        if cfg.write_aligned_dataset:
            grace_aligned.to_netcdf(out_dir / "bologna_grace_aligned.nc")
            grace_anom.to_netcdf(out_dir / "bologna_grace_aligned_anomalies.nc")

        return summary
    finally:
        grace_ds.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--insar-path", default=BolognaExternalConfig.insar_path)
    p.add_argument("--grace-path", default=BolognaExternalConfig.grace_path)
    p.add_argument("--grace-variable", default=BolognaExternalConfig.grace_variable)
    p.add_argument("--grace-uncertainty-variable", default=BolognaExternalConfig.grace_uncertainty_variable)
    p.add_argument("--output-dir", default=BolognaExternalConfig.output_dir)
    p.add_argument("--no-write-aligned-dataset", action="store_true")
    return p


def main() -> None:
    args = build_parser().parse_args()
    cfg = BolognaExternalConfig(
        insar_path=args.insar_path,
        grace_path=args.grace_path,
        grace_variable=args.grace_variable,
        grace_uncertainty_variable=args.grace_uncertainty_variable,
        output_dir=args.output_dir,
        write_aligned_dataset=not args.no_write_aligned_dataset,
    )
    summary = run(cfg)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
