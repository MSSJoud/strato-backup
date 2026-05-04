from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--validation-dir",
        default="/home/ubuntu/work/insar_mcmc/outputs_well_validation",
    )
    args = parser.parse_args()

    val_dir = Path(args.validation_dir)
    fig_dir = val_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    vec_dir = val_dir / "figures_vector"
    vec_dir.mkdir(parents=True, exist_ok=True)

    def savefig(fig: plt.Figure, stem: str) -> None:
        """Save PNG (high-DPI) and PDF (vector) side-by-side."""
        fig.savefig(fig_dir / f"{stem}.png", dpi=600, bbox_inches="tight")
        fig.savefig(vec_dir / f"{stem}.pdf", bbox_inches="tight", format="pdf")
        plt.close(fig)

    trusted = pd.read_csv(val_dir / "well_groundwater_validation_trusted_stations.csv")
    by_depth = pd.read_csv(val_dir / "well_groundwater_validation_by_depth.csv")
    lag_state = pd.read_csv(val_dir / "well_groundwater_validation_lag_state_counts.csv")
    trusted_gwb = pd.read_csv(val_dir / "well_groundwater_validation_trusted_gwb.csv")

    plt.style.use("default")

    # 1. Trusted station map
    fig, ax = plt.subplots(figsize=(8, 7), constrained_layout=True)
    sc = ax.scatter(
        trusted["lon"],
        trusted["lat"],
        c=trusted["corr_anom"],
        s=40 + 5 * trusted["n_matches"],
        cmap="viridis",
        vmin=-1,
        vmax=1,
    )
    for _, row in trusted.head(10).iterrows():
        ax.text(row["lon"], row["lat"], row["station_code"], fontsize=8)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Trusted wells panel")
    fig.colorbar(sc, ax=ax, shrink=0.8, label="anomaly correlation")
    savefig(fig, "trusted_wells_map")

    # 2. Lag histogram by best state
    fig, ax = plt.subplots(figsize=(9, 5), constrained_layout=True)
    if not lag_state.empty:
        pivot = (
            lag_state.pivot(index="best_lag_days", columns="best_state", values="n_series")
            .fillna(0)
            .sort_index()
        )
        x = range(len(pivot.index))
        width = 0.25
        states = list(pivot.columns)
        for i, state in enumerate(states):
            ax.bar(
                [xi + (i - (len(states) - 1) / 2) * width for xi in x],
                pivot[state].values,
                width=width,
                label=state,
            )
        ax.set_xticks(list(x))
        ax.set_xticklabels([str(v) for v in pivot.index])
        ax.legend()
    ax.set_title("Best lag counts by best state")
    ax.set_xlabel("Best lag (days)")
    ax.set_ylabel("Number of stations")
    savefig(fig, "lag_histogram_by_state")

    # 3. Depth summary
    fig, ax = plt.subplots(figsize=(7, 5), constrained_layout=True)
    ax.bar(by_depth["depth_class"], by_depth["median_corr"], color="#4C78A8")
    ax.set_ylim(0, 1)
    ax.set_title("Median well correlation by depth class")
    ax.set_ylabel("Median anomaly correlation")
    ax.set_xlabel("")
    savefig(fig, "depth_class_summary")

    # 4. Trusted aquifer groups
    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
    plot_df = trusted_gwb.sort_values("median_corr", ascending=True).tail(10)
    ax.barh(plot_df["gwb_name"], plot_df["median_corr"], color="#72B7B2")
    ax.set_xlim(0, 1)
    ax.set_title("Trusted aquifer groups")
    ax.set_xlabel("Median anomaly correlation")
    ax.set_ylabel("")
    savefig(fig, "trusted_aquifer_groups")

    # 5. Best six station time-series panels
    top6 = trusted.sort_values(["corr_anom", "n_matches"], ascending=[False, False]).head(6)
    fig, axes = plt.subplots(3, 2, figsize=(13, 10), constrained_layout=True)
    axes = axes.ravel()
    for ax, (_, row) in zip(axes, top6.iterrows()):
        series_path = val_dir / "station_series" / f"{row['station_code']}_{row['measurement_type']}.csv"
        ser = pd.read_csv(series_path, parse_dates=["date"])
        ax.plot(ser["date"], ser["model_anom_z"], label="Model")
        ax.plot(ser["date"], ser["obs_anom_z"], label="Well")
        ax.set_title(f"{row['station_code']} | corr={row['corr_anom']:.3f} | lag={int(row['best_lag_days'])}d")
        ax.tick_params(axis="x", labelrotation=30)
    for ax in axes[2:]:
        ax.set_ylabel("z-anomaly")
    axes[0].legend()
    savefig(fig, "top6_station_timeseries")

    # 6. Compact summary panel
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), constrained_layout=True)
    sc = axes[0, 0].scatter(
        trusted["lon"], trusted["lat"], c=trusted["corr_anom"], s=40 + 5 * trusted["n_matches"], cmap="viridis", vmin=-1, vmax=1
    )
    axes[0, 0].set_title("Trusted wells map")
    axes[0, 0].set_xlabel("Longitude")
    axes[0, 0].set_ylabel("Latitude")
    fig.colorbar(sc, ax=axes[0, 0], shrink=0.8)

    axes[0, 1].bar(by_depth["depth_class"], by_depth["median_corr"], color="#4C78A8")
    axes[0, 1].set_ylim(0, 1)
    axes[0, 1].set_title("By depth class")
    axes[0, 1].set_ylabel("Median corr")
    axes[0, 1].set_xlabel("")

    if not lag_state.empty:
        pivot = (
            lag_state.pivot(index="best_lag_days", columns="best_state", values="n_series")
            .fillna(0)
            .sort_index()
        )
        x = range(len(pivot.index))
        width = 0.25
        states = list(pivot.columns)
        for i, state in enumerate(states):
            axes[1, 0].bar(
                [xi + (i - (len(states) - 1) / 2) * width for xi in x],
                pivot[state].values,
                width=width,
                label=state,
            )
        axes[1, 0].set_xticks(list(x))
        axes[1, 0].set_xticklabels([str(v) for v in pivot.index])
        axes[1, 0].legend(fontsize=8)
    axes[1, 0].set_title("Lag distribution")
    axes[1, 0].set_xlabel("Lag (days)")
    axes[1, 0].set_ylabel("Stations")

    top_for_panel = trusted.sort_values(["corr_anom", "n_matches"], ascending=[False, False]).head(8)
    axes[1, 1].axis("off")
    text_lines = [
        f"{r.station_code}: corr={r.corr_anom:.3f}, lag={int(r.best_lag_days)}d"
        for r in top_for_panel.itertuples(index=False)
    ]
    axes[1, 1].text(0.0, 1.0, "\n".join(text_lines), va="top", family="monospace", fontsize=10)
    axes[1, 1].set_title("Top trusted stations")
    savefig(fig, "well_validation_summary_panel")


if __name__ == "__main__":
    main()
