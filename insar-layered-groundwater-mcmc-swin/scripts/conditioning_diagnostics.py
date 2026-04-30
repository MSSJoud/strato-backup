#!/usr/bin/env python3
"""Conditioning diagnostics for Bologna inverse formulations.

This script compares:

1. the old ill-conditioned five-layer Stage 1 patch run,
2. the old grouped Stage 1 patch run,
3. the current grouped multisensor Kalman Stage 1 run.

It reports:
- column norms / scale spread
- singular values of the stacked sensitivity matrix
- condition number and effective rank
- pairwise column correlations
- information-matrix eigenvalues / condition number
- dynamic observability-style Gramian for the grouped state-space model
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from insar_mcmc.stage1_bologna_multisensor_kalman import (  # noqa: E402
    BolognaMultisensorKalmanConfig,
    PhysicsConfig,
    align_nearest_series,
    align_optional_series,
    anomaly_1d,
    forward_five_layer_components_numpy,
    load_series,
    safe_std,
    scalar_slope,
)


EPS = 1e-12


@dataclass
class DiagnosticConfig:
    old_five_layer_npz: str = "/home/ubuntu/work/insar_mcmc/outputs_stage1_bologna_real_patch20_std/stage1_bologna_real_results.npz"
    old_grouped_npz: str = "/home/ubuntu/work/insar_mcmc/outputs_stage1_bologna_real_patch20_grouped/stage1_bologna_real_results.npz"
    kalman_summary_json: str = "/home/ubuntu/work/insar_mcmc/outputs_stage1_bologna_multisensor_kalman_overlap2025_smaprefresh/stage1_bologna_multisensor_kalman_summary.json"
    output_dir: str = "/home/ubuntu/work/insar_mcmc/outputs_conditioning_diagnostics"


def matrix_effective_rank(svals: np.ndarray, tol_ratio: float = 1e-6) -> int:
    if svals.size == 0:
        return 0
    return int(np.sum(svals > tol_ratio * svals[0]))


def safe_condition_number(svals: np.ndarray) -> float | None:
    if svals.size == 0:
        return None
    smax = float(svals[0])
    smin = float(svals[-1])
    if smin <= EPS:
        return None
    return float(smax / smin)


def pairwise_column_correlation(matrix: np.ndarray) -> dict[str, dict[str, float]]:
    n_cols = matrix.shape[1]
    out: dict[str, dict[str, float]] = {}
    for i in range(n_cols):
        out[str(i)] = {}
        xi = matrix[:, i]
        for j in range(n_cols):
            xj = matrix[:, j]
            if i == j:
                out[str(i)][str(j)] = 1.0
                continue
            mask = np.isfinite(xi) & np.isfinite(xj)
            if mask.sum() < 2:
                out[str(i)][str(j)] = float("nan")
            else:
                out[str(i)][str(j)] = float(np.corrcoef(xi[mask], xj[mask])[0, 1])
    return out


def matrix_summary(matrix: np.ndarray, names: list[str]) -> dict:
    col_norms = np.linalg.norm(matrix, axis=0)
    scale_spread = float(np.max(col_norms) / max(np.min(col_norms), EPS))
    svals = np.linalg.svd(matrix, compute_uv=False)
    info = matrix.T @ matrix
    evals = np.linalg.eigvalsh(info)
    pos_evals = evals[evals > EPS]
    info_cond = None if pos_evals.size == 0 else float(pos_evals[-1] / pos_evals[0])
    return {
        "shape": [int(matrix.shape[0]), int(matrix.shape[1])],
        "column_names": names,
        "column_norms": {name: float(val) for name, val in zip(names, col_norms)},
        "column_scale_spread": scale_spread,
        "singular_values": [float(v) for v in svals],
        "condition_number": safe_condition_number(svals),
        "effective_rank_1e-6": matrix_effective_rank(svals, tol_ratio=1e-6),
        "effective_rank_1e-4": matrix_effective_rank(svals, tol_ratio=1e-4),
        "information_eigenvalues": [float(v) for v in evals],
        "information_condition_number": info_cond,
        "column_correlation": pairwise_column_correlation(matrix),
    }


def build_design_from_saved_result(npz_path: str) -> dict:
    arr = np.load(npz_path)
    z_layers = arr["z_layers"].astype(np.float32)
    if "field_names" in arr.files:
        field_names = [str(x) for x in arr["field_names"].tolist()]
    else:
        field_names = ["S0", "Ss", "Sd", "Sg", "Sr"]

    components = forward_five_layer_components_numpy(
        z_layers,
        physics=PhysicsConfig(),
        sg_index=3,
        load_indices=(0, 1, 2, 4),
    )

    if field_names == ["S0", "Ss", "Sd", "Sg", "Sr"]:
        design = components.transpose(0, 2, 3, 1).reshape(-1, 5).astype(np.float64)
    elif field_names == ["Load_total", "Sg"]:
        grouped = np.stack(
            [
                components[:, [0, 1, 2, 4]].sum(axis=1),
                components[:, 3],
            ],
            axis=1,
        )
        design = grouped.transpose(0, 2, 3, 1).reshape(-1, 2).astype(np.float64)
    else:
        raise ValueError(f"Unsupported field_names in {npz_path}: {field_names}")

    # Drop rows that are all zero or non-finite.
    valid = np.isfinite(design).all(axis=1) & (np.linalg.norm(design, axis=1) > 0)
    design = design[valid]

    # Also inspect a column-standardized version to separate pure collinearity from scale spread.
    col_std = np.std(design, axis=0)
    col_std = np.where(col_std > EPS, col_std, 1.0)
    design_std = design / col_std[None, :]

    return {
        "field_names": field_names,
        "raw_design": design,
        "std_design": design_std,
    }


def compute_old_stage_diagnostics(npz_path: str) -> dict:
    built = build_design_from_saved_result(npz_path)
    return {
        "field_names": built["field_names"],
        "raw": matrix_summary(built["raw_design"], built["field_names"]),
        "column_standardized": matrix_summary(built["std_design"], built["field_names"]),
    }


def build_kalman_stacked_operators(cfg: BolognaMultisensorKalmanConfig) -> dict:
    data = load_series(cfg)
    t_steps = len(data["times"])

    insar_scale = safe_std(data["y_insar"])
    grace_scale = safe_std(data["y_grace"])
    smap_scale = safe_std(data["y_smap"][np.isfinite(data["y_smap"])]) if np.isfinite(data["y_smap"]).any() else 1.0
    swot_river_scale = safe_std(data["y_swot_river"][np.isfinite(data["y_swot_river"])]) if np.isfinite(data["y_swot_river"]).any() else 1.0
    swot_lake_scale = safe_std(data["y_swot_lake"][np.isfinite(data["y_swot_lake"])]) if np.isfinite(data["y_swot_lake"]).any() else 1.0

    smap_slope = scalar_slope(data["z_state"][:, 0], data["y_smap"], ridge_eps=cfg.ridge_eps)
    swot_river_slope = scalar_slope(data["z_state"][:, 0], data["y_swot_river"], ridge_eps=cfg.ridge_eps)
    swot_lake_slope = scalar_slope(data["z_state"][:, 0], data["y_swot_lake"], ridge_eps=cfg.ridge_eps)

    rows = []
    row_labels = []
    info_sum = np.zeros((3, 3), dtype=np.float64)
    gramian = np.zeros((3, 3), dtype=np.float64)
    phi = cfg.state_persistence

    for t in range(t_steps):
        local_rows = []
        local_rs = []

        if np.isfinite(data["y_insar"][t]) and np.all(np.isfinite(data["z_def"][t])):
            row = data["z_def"][t] / insar_scale
            local_rows.append(row)
            local_rs.append(cfg.r_insar ** 2)
            rows.append(row)
            row_labels.append(f"t{t}_insar")

        if np.isfinite(data["y_grace"][t]) and np.all(np.isfinite(data["z_state"][t])):
            row = data["z_state"][t] / grace_scale
            local_rows.append(row)
            local_rs.append(cfg.r_grace ** 2)
            rows.append(row)
            row_labels.append(f"t{t}_grace")

        if np.isfinite(data["y_smap"][t]) and np.isfinite(smap_slope) and abs(smap_slope) > 0 and np.isfinite(data["z_state"][t, 0]):
            row = np.array([smap_slope * data["z_state"][t, 0], 0.0, 0.0], dtype=np.float64) / smap_scale
            local_rows.append(row)
            local_rs.append(cfg.r_smap ** 2)
            rows.append(row)
            row_labels.append(f"t{t}_smap")

        if np.isfinite(data["y_swot_river"][t]) and np.isfinite(swot_river_slope) and abs(swot_river_slope) > 0 and np.isfinite(data["z_state"][t, 0]):
            row = np.array([swot_river_slope * data["z_state"][t, 0], 0.0, 0.0], dtype=np.float64) / swot_river_scale
            local_rows.append(row)
            local_rs.append(cfg.r_swot_river ** 2)
            rows.append(row)
            row_labels.append(f"t{t}_swot_river")

        if np.isfinite(data["y_swot_lake"][t]) and np.isfinite(swot_lake_slope) and abs(swot_lake_slope) > 0 and np.isfinite(data["z_state"][t, 0]):
            row = np.array([swot_lake_slope * data["z_state"][t, 0], 0.0, 0.0], dtype=np.float64) / swot_lake_scale
            local_rows.append(row)
            local_rs.append(cfg.r_swot_lake ** 2)
            rows.append(row)
            row_labels.append(f"t{t}_swot_lake")

        for row, rv in zip(local_rows, local_rs):
            info_sum += np.outer(row, row) / rv
            # simple observability-style weighting back through the scalar-persistence dynamics
            gramian += (phi ** (2 * (t_steps - 1 - t))) * (np.outer(row, row) / rv)

    if not rows:
        raise RuntimeError("No valid observation rows were built for Kalman diagnostics.")

    stacked = np.stack(rows, axis=0)
    svals = np.linalg.svd(stacked, compute_uv=False)
    gram_evals = np.linalg.eigvalsh(gramian)
    info_evals = np.linalg.eigvalsh(info_sum)
    pos_gram = gram_evals[gram_evals > EPS]
    pos_info = info_evals[info_evals > EPS]

    return {
        "state_names": ["ShallowLoad", "DeepLoad", "Groundwater"],
        "n_rows": int(stacked.shape[0]),
        "row_labels_sample": row_labels[:12],
        "stacked_operator": matrix_summary(stacked, ["ShallowLoad", "DeepLoad", "Groundwater"]),
        "information_eigenvalues": [float(v) for v in info_evals],
        "information_condition_number": None if pos_info.size == 0 else float(pos_info[-1] / pos_info[0]),
        "observability_gramian_eigenvalues": [float(v) for v in gram_evals],
        "observability_condition_number": None if pos_gram.size == 0 else float(pos_gram[-1] / pos_gram[0]),
        "scales": {
            "insar_scale": float(insar_scale),
            "grace_scale": float(grace_scale),
            "smap_scale": float(smap_scale),
            "swot_river_scale": float(swot_river_scale),
            "swot_lake_scale": float(swot_lake_scale),
            "smap_slope": float(smap_slope),
            "swot_river_slope": float(swot_river_slope),
            "swot_lake_slope": float(swot_lake_slope),
        },
    }


def main() -> None:
    cfg = DiagnosticConfig()
    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(cfg.kalman_summary_json) as f:
        kalman_summary = json.load(f)
    kalman_cfg = BolognaMultisensorKalmanConfig(**kalman_summary["config"])

    results = {
        "config": asdict(cfg),
        "old_five_layer_patch": compute_old_stage_diagnostics(cfg.old_five_layer_npz),
        "old_grouped_patch": compute_old_stage_diagnostics(cfg.old_grouped_npz),
        "current_grouped_kalman": build_kalman_stacked_operators(kalman_cfg),
    }

    out_path = out_dir / "conditioning_diagnostics_summary.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(out_path)


if __name__ == "__main__":
    main()
