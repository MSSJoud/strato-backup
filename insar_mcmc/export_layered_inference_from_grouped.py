#!/usr/bin/env python3
"""Construct a practical 5-layer posterior from the stable grouped Stage 1 result.

This is a conditional layered decomposition:
- the grouped posterior load state is treated as the stable inferred load signal
- W3RA layer proportions distribute that inferred load back into S0, Ss, Sd, Sr
- Sg is kept directly from the grouped posterior
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np


LAYER_NAMES = ("S0", "Ss", "Sd", "Sg", "Sr")
LOAD_IDX = (0, 1, 2, 4)


@dataclass
class LayeredExportConfig:
    grouped_results_path: str = "/home/ubuntu/work/insar_mcmc/outputs_stage1_bologna_real_full_grouped_quick/stage1_bologna_real_results.npz"
    output_dir: str = "/home/ubuntu/work/insar_mcmc/outputs_layered_inference_from_grouped"
    zero_tol: float = 1e-8


def normalize_weights(weights: np.ndarray, axis: int = 0) -> np.ndarray:
    denom = np.sum(weights, axis=axis, keepdims=True)
    safe = np.where(denom > 0, weights / denom, 0.0)
    return safe.astype(np.float32)


def main(cfg: LayeredExportConfig) -> dict:
    src = np.load(cfg.grouped_results_path)
    field_names = tuple(str(x) for x in src["field_names"].tolist())
    if field_names != ("Load_total", "Sg"):
        raise ValueError(f"Expected grouped results with fields ('Load_total','Sg'), got {field_names}.")

    x_group = src["x_prior"].astype(np.float32)  # (T, 2, H, W)
    z_layers = src["z_layers"].astype(np.float32)  # (T, 5, H, W)
    lat = src["lat"].astype(np.float32)
    lon = src["lon"].astype(np.float32)
    time = src["time"]

    load_group = x_group[:, 0]
    sg_group = x_group[:, 1]
    z_load = z_layers[:, LOAD_IDX]
    z_load_sum = np.sum(z_load, axis=1)

    direct_w = np.zeros_like(z_load, dtype=np.float32)
    direct_mask = np.abs(z_load_sum) > cfg.zero_tol
    direct_w[:, 0][direct_mask] = z_load[:, 0][direct_mask] / z_load_sum[direct_mask]
    direct_w[:, 1][direct_mask] = z_load[:, 1][direct_mask] / z_load_sum[direct_mask]
    direct_w[:, 2][direct_mask] = z_load[:, 2][direct_mask] / z_load_sum[direct_mask]
    direct_w[:, 3][direct_mask] = z_load[:, 3][direct_mask] / z_load_sum[direct_mask]

    fallback_static = normalize_weights(np.mean(np.abs(z_load), axis=0), axis=0)  # (4, H, W)
    fallback_time = np.repeat(fallback_static[None, ...], z_load.shape[0], axis=0)
    weights = np.where(direct_mask[:, None, :, :], direct_w, fallback_time).astype(np.float32)

    layered = np.zeros_like(z_layers, dtype=np.float32)
    layered[:, 0] = load_group * weights[:, 0]
    layered[:, 1] = load_group * weights[:, 1]
    layered[:, 2] = load_group * weights[:, 2]
    layered[:, 3] = sg_group
    layered[:, 4] = load_group - (layered[:, 0] + layered[:, 1] + layered[:, 2])

    load_reconstructed = layered[:, list(LOAD_IDX)].sum(axis=1)
    tws = layered.sum(axis=1)

    summary = {
        "config": asdict(cfg),
        "shape": {
            "time": int(layered.shape[0]),
            "height": int(layered.shape[2]),
            "width": int(layered.shape[3]),
            "layers": int(layered.shape[1]),
        },
        "consistency": {
            "load_sum_rmse": float(np.sqrt(np.mean((load_reconstructed - load_group) ** 2))),
            "load_sum_max_abs": float(np.max(np.abs(load_reconstructed - load_group))),
            "sg_identity_rmse": float(np.sqrt(np.mean((layered[:, 3] - sg_group) ** 2))),
        },
        "notes": {
            "type": "conditional layered decomposition from grouped posterior",
            "interpretation": "S0,Ss,Sd,Sr are distributed from grouped Load_total using W3RA layer shares; Sg is taken directly from grouped posterior.",
        },
    }

    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_dir / "layered_inference_from_grouped.npz",
        x_layered=layered,
        x_grouped=x_group,
        load_weights=weights,
        load_total=load_group,
        sg=sg_group,
        tws=tws,
        z_layers=z_layers,
        lat=lat,
        lon=lon,
        time=time,
        field_names=np.array(LAYER_NAMES),
    )
    (out_dir / "layered_inference_from_grouped_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return summary


def parse_args() -> LayeredExportConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grouped-results-path", default=LayeredExportConfig.grouped_results_path)
    parser.add_argument("--output-dir", default=LayeredExportConfig.output_dir)
    parser.add_argument("--zero-tol", type=float, default=LayeredExportConfig.zero_tol)
    args = parser.parse_args()
    return LayeredExportConfig(
        grouped_results_path=args.grouped_results_path,
        output_dir=args.output_dir,
        zero_tol=args.zero_tol,
    )


if __name__ == "__main__":
    main(parse_args())
