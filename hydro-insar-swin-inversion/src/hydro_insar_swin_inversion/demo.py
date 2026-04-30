from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


@dataclass
class DemoResults:
    summary: dict
    timeseries: pd.DataFrame


def _r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = np.sum((y_true - np.mean(y_true)) ** 2)
    if np.isclose(denom, 0.0):
        return 0.0
    return float(1.0 - np.sum((y_true - y_pred) ** 2) / denom)


def run_synthetic_demo(
    output_dir: str | Path,
    n_steps: int = 72,
    seed: int = 42,
) -> DemoResults:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(seed)
    state_names = ["ShallowLoad", "DeepLoad", "Groundwater"]

    a_true = np.array(
        [
            [0.84, 0.06, 0.00],
            [0.03, 0.90, 0.02],
            [0.00, 0.05, 0.93],
        ],
        dtype=float,
    )
    a_filter = np.array(
        [
            [0.80, 0.03, 0.00],
            [0.02, 0.87, 0.01],
            [0.00, 0.03, 0.89],
        ],
        dtype=float,
    )

    q_true = np.diag([0.30, 0.18, 0.15])
    q_filter = np.diag([0.35, 0.25, 0.20])

    h_insar = np.array([[0.85, 0.55, 1.10]], dtype=float)
    h_grace = np.array([[1.05, 0.95, 0.90]], dtype=float)
    h_smap = np.array([[1.10, 0.15, 0.00]], dtype=float)
    r_insar = np.array([[0.10]], dtype=float)
    r_grace = np.array([[0.20]], dtype=float)
    r_smap = np.array([[0.08]], dtype=float)

    seasonal = np.stack(
        [
            2.1 * np.sin(np.linspace(0, 6 * np.pi, n_steps)),
            1.3 * np.cos(np.linspace(0, 4 * np.pi, n_steps) + 0.5),
            1.8 * np.sin(np.linspace(0, 3 * np.pi, n_steps) + 1.1),
        ],
        axis=1,
    )

    x_true = np.zeros((n_steps, 3), dtype=float)
    x_true[0] = np.array([1.5, -0.8, 0.5]) + seasonal[0]
    for t in range(1, n_steps):
        x_true[t] = a_true @ x_true[t - 1] + seasonal[t] * 0.08 + rng.multivariate_normal(np.zeros(3), q_true)

    y_insar = (x_true @ h_insar.T).ravel() + rng.normal(0.0, np.sqrt(r_insar[0, 0]), size=n_steps)
    y_grace = (x_true @ h_grace.T).ravel() + rng.normal(0.0, np.sqrt(r_grace[0, 0]), size=n_steps)
    y_smap = (x_true @ h_smap.T).ravel() + rng.normal(0.0, np.sqrt(r_smap[0, 0]), size=n_steps)

    x_prior = np.zeros((n_steps, 3), dtype=float)
    x_post = np.zeros((n_steps, 3), dtype=float)
    p_post = np.diag([1.0, 1.0, 1.0])

    identity = np.eye(3)

    h_stack = [h_insar, h_grace, h_smap]
    y_stack = [y_insar, y_grace, y_smap]
    r_stack = [r_insar, r_grace, r_smap]

    x_prev = np.zeros(3, dtype=float)
    for t in range(n_steps):
        x_fore = a_filter @ x_prev
        p_fore = a_filter @ p_post @ a_filter.T + q_filter
        x_prior[t] = x_fore

        x_upd = x_fore.copy()
        p_upd = p_fore.copy()
        for h, y, r in zip(h_stack, y_stack, r_stack):
            innovation = np.array([y[t]]) - h @ x_upd
            s = h @ p_upd @ h.T + r
            k = p_upd @ h.T @ np.linalg.inv(s)
            x_upd = x_upd + (k @ innovation).ravel()
            p_upd = (identity - k @ h) @ p_upd

        x_post[t] = x_upd
        p_post = p_upd
        x_prev = x_upd

    y_insar_prior = (x_prior @ h_insar.T).ravel()
    y_insar_post = (x_post @ h_insar.T).ravel()
    y_grace_prior = (x_prior @ h_grace.T).ravel()
    y_grace_post = (x_post @ h_grace.T).ravel()
    y_smap_prior = (x_prior @ h_smap.T).ravel()
    y_smap_post = (x_post @ h_smap.T).ravel()

    metrics = {
        "insar": {"prior_r2": _r2_score(y_insar, y_insar_prior), "post_r2": _r2_score(y_insar, y_insar_post)},
        "grace": {"prior_r2": _r2_score(y_grace, y_grace_prior), "post_r2": _r2_score(y_grace, y_grace_post)},
        "smap": {"prior_r2": _r2_score(y_smap, y_smap_prior), "post_r2": _r2_score(y_smap, y_smap_post)},
    }
    state_metrics = {
        name: {
            "prior_r2": _r2_score(x_true[:, i], x_prior[:, i]),
            "post_r2": _r2_score(x_true[:, i], x_post[:, i]),
        }
        for i, name in enumerate(state_names)
    }

    summary = {
        "demo_name": "synthetic_grouped_multisensor_demo",
        "n_steps": n_steps,
        "seed": seed,
        "state_names": state_names,
        "observation_streams": ["InSAR", "GRACE", "SMAP"],
        "metrics": metrics,
        "state_metrics": state_metrics,
    }

    index = pd.date_range("2017-01-01", periods=n_steps, freq="MS")
    frame = pd.DataFrame(
        {
            "date": index,
            "truth_shallowload": x_true[:, 0],
            "truth_deepload": x_true[:, 1],
            "truth_groundwater": x_true[:, 2],
            "prior_shallowload": x_prior[:, 0],
            "prior_deepload": x_prior[:, 1],
            "prior_groundwater": x_prior[:, 2],
            "post_shallowload": x_post[:, 0],
            "post_deepload": x_post[:, 1],
            "post_groundwater": x_post[:, 2],
            "obs_insar": y_insar,
            "prior_insar": y_insar_prior,
            "post_insar": y_insar_post,
            "obs_grace": y_grace,
            "prior_grace": y_grace_prior,
            "post_grace": y_grace_post,
            "obs_smap": y_smap,
            "prior_smap": y_smap_prior,
            "post_smap": y_smap_post,
        }
    )

    (output_dir / "synthetic_demo_summary.json").write_text(json.dumps(summary, indent=2))
    frame.to_csv(output_dir / "synthetic_demo_timeseries.csv", index=False)

    fig, axes = plt.subplots(2, 3, figsize=(15, 8), constrained_layout=True)
    plot_specs = [
        ("ShallowLoad", "truth_shallowload", "prior_shallowload", "post_shallowload"),
        ("DeepLoad", "truth_deepload", "prior_deepload", "post_deepload"),
        ("Groundwater", "truth_groundwater", "prior_groundwater", "post_groundwater"),
        ("InSAR", "obs_insar", "prior_insar", "post_insar"),
        ("GRACE", "obs_grace", "prior_grace", "post_grace"),
        ("SMAP", "obs_smap", "prior_smap", "post_smap"),
    ]
    for ax, (title, obs_col, prior_col, post_col) in zip(axes.ravel(), plot_specs):
        ax.plot(frame["date"], frame[obs_col], label="Observed / truth", lw=1.8)
        ax.plot(frame["date"], frame[prior_col], label="Prior", lw=1.4, alpha=0.85)
        ax.plot(frame["date"], frame[post_col], label="Posterior", lw=1.6, alpha=0.95)
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=25)
    axes[0, 0].legend(loc="best")
    fig.suptitle("Minimal synthetic grouped inversion demo", fontsize=14)
    fig.savefig(output_dir / "synthetic_demo_figure.png", dpi=220, bbox_inches="tight")
    plt.close(fig)

    return DemoResults(summary=summary, timeseries=frame)

