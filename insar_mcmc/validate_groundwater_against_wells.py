from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def zscore(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").astype(float)
    std = s.std(ddof=0)
    if not np.isfinite(std) or std == 0:
        return pd.Series(np.nan, index=s.index)
    return (s - s.mean()) / std


def nearest_tile_indices(lon: float, lat: float, lon_tiles: np.ndarray, lat_tiles: np.ndarray) -> tuple[int, int, float]:
    dist2 = (lon_tiles - lon) ** 2 + (lat_tiles - lat) ** 2
    iy, ix = np.unravel_index(np.argmin(dist2), dist2.shape)
    return int(iy), int(ix), float(np.sqrt(dist2[iy, ix]))


def idw_weights(lon: float, lat: float, lon_tiles: np.ndarray, lat_tiles: np.ndarray, power: float = 2.0) -> tuple[np.ndarray, float]:
    dist2 = (lon_tiles - lon) ** 2 + (lat_tiles - lat) ** 2
    min_dist = float(np.sqrt(np.min(dist2)))
    if np.min(dist2) < 1e-12:
        weights = np.zeros_like(dist2, dtype=float)
        weights[np.unravel_index(np.argmin(dist2), dist2.shape)] = 1.0
        return weights, min_dist
    weights = 1.0 / np.maximum(dist2, 1e-12) ** (power / 2.0)
    weights = weights / np.sum(weights)
    return weights.astype(float), min_dist


def interp_tile_series(x_tiles: np.ndarray, weights: np.ndarray) -> np.ndarray:
    # x_tiles: (T, S, Y, X)
    return np.einsum("tsyx,yx->ts", x_tiles, weights)


def align_nearest(model_df: pd.DataFrame, obs_df: pd.DataFrame, tolerance_days: int) -> pd.DataFrame:
    left = obs_df.sort_values("date").copy()
    right = model_df.sort_values("date").copy()
    merged = pd.merge_asof(
        left,
        right,
        on="date",
        direction="nearest",
        tolerance=pd.Timedelta(days=tolerance_days),
    )
    model_cols = [c for c in right.columns if c != "date"]
    merged = merged.dropna(subset=model_cols).reset_index(drop=True)
    return merged


def prepare_obs_series(aligned: pd.DataFrame) -> tuple[pd.DataFrame | None, str | None, str | None]:
    work = aligned.copy()
    if "piezometry_m" in work and work["piezometry_m"].notna().sum() >= 3:
        work["obs_value"] = pd.to_numeric(work["piezometry_m"], errors="coerce")
        return work, "piezometry_m", "same_sign_expected"
    if "depth_to_water_m" in work and work["depth_to_water_m"].notna().sum() >= 3:
        work["obs_value"] = -pd.to_numeric(work["depth_to_water_m"], errors="coerce")
        return work, "neg_depth_to_water_m", "inverted_depth_to_water"
    return None, None, None


def corr_rmse(a: pd.Series, b: pd.Series) -> tuple[float, float]:
    valid = pd.DataFrame({"a": a, "b": b}).dropna()
    if len(valid) < 3:
        return float("nan"), float("nan")
    corr = float(valid["a"].corr(valid["b"]))
    rmse = float(np.sqrt(np.mean((valid["a"] - valid["b"]) ** 2)))
    return corr, rmse


def classify_depth(well_depth_m: float | int | None) -> str:
    if well_depth_m is None or not np.isfinite(well_depth_m):
        return "unknown"
    depth = float(well_depth_m)
    if depth <= 20.0:
        return "shallow"
    if depth <= 100.0:
        return "intermediate"
    return "deep"


def lagged_alignment(
    station_df: pd.DataFrame,
    model_df: pd.DataFrame,
    tolerance_days: int,
    lag_days: int,
) -> pd.DataFrame:
    shifted = model_df.copy()
    shifted["date"] = shifted["date"] + pd.Timedelta(days=lag_days)
    return align_nearest(model_df=shifted, obs_df=station_df, tolerance_days=tolerance_days)


def evaluate_state_lags(
    station_df: pd.DataFrame,
    model_df: pd.DataFrame,
    state_col: str,
    tolerance_days: int,
    lag_days_list: list[int],
) -> tuple[dict | None, pd.DataFrame | None]:
    best: dict | None = None
    best_aligned: pd.DataFrame | None = None
    for lag_days in lag_days_list:
        aligned = lagged_alignment(station_df=station_df, model_df=model_df[["date", state_col]], tolerance_days=tolerance_days, lag_days=lag_days)
        aligned = aligned.rename(columns={state_col: "model_value"})
        work, obs_kind, sign_note = prepare_obs_series(aligned)
        if work is None:
            continue
        work["model_anom_z"] = zscore(work["model_value"])
        work["obs_anom_z"] = zscore(work["obs_value"])
        corr, rmse = corr_rmse(work["model_anom_z"], work["obs_anom_z"])
        valid_n = int(pd.DataFrame({"a": work["model_anom_z"], "b": work["obs_anom_z"]}).dropna().shape[0])
        if not np.isfinite(corr):
            continue
        record = {
            "state": state_col,
            "lag_days": int(lag_days),
            "corr_anom": corr,
            "rmse_anom_z": rmse,
            "n_matches": valid_n,
            "obs_kind": obs_kind,
            "obs_transform_note": sign_note,
        }
        if best is None or record["corr_anom"] > best["corr_anom"]:
            best = record
            best_aligned = work.copy()
    return best, best_aligned


def summarize_station(
    station_df: pd.DataFrame,
    model_df: pd.DataFrame,
    tolerance_days: int,
    lag_days_list: list[int],
) -> dict | None:
    nearest_aligned = align_nearest(model_df=model_df, obs_df=station_df, tolerance_days=tolerance_days)
    if nearest_aligned.empty:
        return None

    work, obs_kind, sign_note = prepare_obs_series(nearest_aligned)
    if work is None:
        return None

    state_bests: dict[str, dict] = {}
    best_overall: dict | None = None
    best_aligned: pd.DataFrame | None = None
    for state_col in ["groundwater_model", "shallowload_model", "deepload_model"]:
        best_state, aligned_state = evaluate_state_lags(
            station_df=station_df,
            model_df=model_df,
            state_col=state_col,
            tolerance_days=tolerance_days,
            lag_days_list=lag_days_list,
        )
        if best_state is None:
            continue
        state_bests[state_col] = best_state
        if best_overall is None or best_state["corr_anom"] > best_overall["corr_anom"]:
            best_overall = best_state
            best_aligned = aligned_state

    if best_overall is None or best_aligned is None:
        return None

    work["groundwater_anom_z"] = zscore(work["groundwater_model"])
    zero_corr, zero_rmse = corr_rmse(work["groundwater_anom_z"], zscore(work["obs_value"]))

    return {
        "station_code": station_df["station_code"].iloc[0],
        "measurement_type": station_df["measurement_type"].iloc[0],
        "municipality": station_df["municipality"].iloc[0],
        "gwb_name": station_df["gwb_name"].iloc[0],
        "lon": float(station_df["lon"].iloc[0]),
        "lat": float(station_df["lat"].iloc[0]),
        "depth_class": classify_depth(station_df["well_depth_m"].iloc[0]),
        "well_depth_m": (
            None if pd.isna(station_df["well_depth_m"].iloc[0]) else float(station_df["well_depth_m"].iloc[0])
        ),
        "filter_start_m": (
            None if pd.isna(station_df["filter_start_m"].iloc[0]) else float(station_df["filter_start_m"].iloc[0])
        ),
        "filter_end_m": (
            None if pd.isna(station_df["filter_end_m"].iloc[0]) else float(station_df["filter_end_m"].iloc[0])
        ),
        "tile_y": int(station_df["tile_y"].iloc[0]),
        "tile_x": int(station_df["tile_x"].iloc[0]),
        "tile_lon": float(station_df["tile_lon"].iloc[0]),
        "tile_lat": float(station_df["tile_lat"].iloc[0]),
        "tile_distance_deg": float(station_df["tile_distance_deg"].iloc[0]),
        "interp_distance_deg": float(station_df["interp_distance_deg"].iloc[0]),
        "obs_kind": obs_kind,
        "obs_transform_note": sign_note,
        "n_matches": int(best_overall["n_matches"]),
        "date_start": best_aligned["date"].min().strftime("%Y-%m-%d"),
        "date_end": best_aligned["date"].max().strftime("%Y-%m-%d"),
        "corr_anom": float(best_overall["corr_anom"]),
        "rmse_anom_z": float(best_overall["rmse_anom_z"]),
        "corr_groundwater_lag0": zero_corr,
        "rmse_groundwater_lag0": zero_rmse,
        "best_state": best_overall["state"].replace("_model", ""),
        "best_lag_days": int(best_overall["lag_days"]),
        "corr_groundwater_best": state_bests.get("groundwater_model", {}).get("corr_anom"),
        "lag_groundwater_best_days": state_bests.get("groundwater_model", {}).get("lag_days"),
        "corr_shallowload_best": state_bests.get("shallowload_model", {}).get("corr_anom"),
        "lag_shallowload_best_days": state_bests.get("shallowload_model", {}).get("lag_days"),
        "corr_deepload_best": state_bests.get("deepload_model", {}).get("corr_anom"),
        "lag_deepload_best_days": state_bests.get("deepload_model", {}).get("lag_days"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--kalman-results",
        default="/home/ubuntu/work/insar_mcmc/outputs_stage1_bologna_multisensor_kalman_tiled_overlap2025_smaprefresh/stage1_bologna_multisensor_kalman_tiled_results.npz",
    )
    parser.add_argument(
        "--wells-csv",
        default="/home/ubuntu/work/insar_mcmc/outputs_external_bologna_wells/processed/bologna_wells_long.csv",
    )
    parser.add_argument(
        "--output-dir",
        default="/home/ubuntu/work/insar_mcmc/outputs_well_validation",
    )
    parser.add_argument("--tolerance-days", type=int, default=14)
    parser.add_argument("--min-matches", type=int, default=5)
    parser.add_argument("--lag-days", default="-90,-60,-30,-14,0,14,30,60,90")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    res = np.load(args.kalman_results)
    time = pd.to_datetime(res["time"])
    state_names = list(res["state_names"])
    gw_idx = state_names.index("Groundwater")
    sh_idx = state_names.index("ShallowLoad")
    dp_idx = state_names.index("DeepLoad")
    x_tiles = res["x_tiles"]
    lon_tiles = res["lon_tiles"]
    lat_tiles = res["lat_tiles"]
    lag_days_list = [int(v.strip()) for v in str(args.lag_days).split(",") if v.strip()]

    wells = pd.read_csv(args.wells_csv, parse_dates=["date"])
    wells = wells.dropna(subset=["station_code", "date", "lon", "lat"]).copy()

    tile_records = []
    unique_stations = wells[
        ["station_code", "measurement_type", "municipality", "lon", "lat", "well_depth_m"]
    ].drop_duplicates()
    for row in unique_stations.itertuples(index=False):
        iy, ix, dist = nearest_tile_indices(row.lon, row.lat, lon_tiles, lat_tiles)
        weights, interp_dist = idw_weights(row.lon, row.lat, lon_tiles, lat_tiles)
        tile_records.append(
            {
                "station_code": row.station_code,
                "measurement_type": row.measurement_type,
                "tile_y": iy,
                "tile_x": ix,
                "tile_lon": float(lon_tiles[iy, ix]),
                "tile_lat": float(lat_tiles[iy, ix]),
                "tile_distance_deg": dist,
                "interp_distance_deg": interp_dist,
                "interp_weights_json": json.dumps(weights.tolist()),
            }
        )
    station_tiles = pd.DataFrame(tile_records)
    wells = wells.merge(station_tiles, on=["station_code", "measurement_type"], how="left")

    rows = []
    series_dir = out_dir / "station_series"
    series_dir.mkdir(parents=True, exist_ok=True)

    for (station_code, measurement_type), station_df in wells.groupby(["station_code", "measurement_type"], dropna=False):
        weights = np.array(json.loads(station_df["interp_weights_json"].iloc[0]), dtype=float)
        interp_states = interp_tile_series(x_tiles, weights)
        model_df = pd.DataFrame(
            {
                "date": time,
                "shallowload_model": interp_states[:, sh_idx],
                "deepload_model": interp_states[:, dp_idx],
                "groundwater_model": interp_states[:, gw_idx],
            }
        )
        summary = summarize_station(station_df.copy(), model_df, args.tolerance_days, lag_days_list)
        if summary is None:
            continue
        if summary["n_matches"] < args.min_matches:
            continue
        rows.append(summary)

        best_state_col = f"{summary['best_state']}_model"
        best_lag_days = int(summary["best_lag_days"])
        aligned = lagged_alignment(
            station_df=station_df.copy(),
            model_df=model_df[["date", best_state_col]],
            tolerance_days=args.tolerance_days,
            lag_days=best_lag_days,
        ).rename(columns={best_state_col: "model_value"})
        if summary["obs_kind"] == "piezometry_m":
            aligned["obs_value"] = pd.to_numeric(aligned["piezometry_m"], errors="coerce")
        else:
            aligned["obs_value"] = -pd.to_numeric(aligned["depth_to_water_m"], errors="coerce")
        aligned["model_anom_z"] = zscore(aligned["model_value"])
        aligned["obs_anom_z"] = zscore(aligned["obs_value"])
        aligned["model_state"] = summary["best_state"]
        aligned["lag_days"] = summary["best_lag_days"]
        aligned.to_csv(series_dir / f"{station_code}_{measurement_type}.csv", index=False)

    summary_df = pd.DataFrame(rows).sort_values(["corr_anom", "n_matches"], ascending=[False, False]).reset_index(drop=True)
    summary_df.to_csv(out_dir / "well_groundwater_validation_summary.csv", index=False)

    by_depth = (
        summary_df.groupby("depth_class", dropna=False)
        .agg(
            n_series=("station_code", "size"),
            median_corr=("corr_anom", "median"),
            mean_corr=("corr_anom", "mean"),
            n_corr_ge_0_3=("corr_anom", lambda s: int((s >= 0.3).sum())),
            n_corr_ge_0_5=("corr_anom", lambda s: int((s >= 0.5).sum())),
        )
        .reset_index()
        if not summary_df.empty
        else pd.DataFrame()
    )
    by_depth.to_csv(out_dir / "well_groundwater_validation_by_depth.csv", index=False)

    lag_state = (
        summary_df.groupby(["best_state", "best_lag_days"], dropna=False)
        .size()
        .reset_index(name="n_series")
        .sort_values(["best_state", "best_lag_days"])
        if not summary_df.empty
        else pd.DataFrame()
    )
    lag_state.to_csv(out_dir / "well_groundwater_validation_lag_state_counts.csv", index=False)

    by_gwb = (
        summary_df.groupby("gwb_name", dropna=False)
        .agg(
            n_series=("station_code", "size"),
            median_corr=("corr_anom", "median"),
            mean_corr=("corr_anom", "mean"),
            n_corr_ge_0_3=("corr_anom", lambda s: int((s >= 0.3).sum())),
            n_corr_ge_0_5=("corr_anom", lambda s: int((s >= 0.5).sum())),
        )
        .reset_index()
        .sort_values(["n_series", "median_corr"], ascending=[False, False])
        if not summary_df.empty
        else pd.DataFrame()
    )
    by_gwb.to_csv(out_dir / "well_groundwater_validation_by_gwb.csv", index=False)

    shortlist = (
        summary_df.loc[summary_df["n_matches"] >= 10]
        .sort_values(["corr_anom", "n_matches"], ascending=[False, False])
        .reset_index(drop=True)
        if not summary_df.empty
        else pd.DataFrame()
    )
    shortlist.to_csv(out_dir / "well_groundwater_validation_topstations.csv", index=False)

    trusted_gwb = (
        by_gwb.loc[
            (by_gwb["n_series"] >= 3)
            & (by_gwb["median_corr"] >= 0.7)
            & ((by_gwb["n_corr_ge_0_5"] / by_gwb["n_series"]) >= 0.6)
        ]
        .sort_values(["n_series", "median_corr"], ascending=[False, False])
        .reset_index(drop=True)
        if not by_gwb.empty
        else pd.DataFrame()
    )
    trusted_gwb.to_csv(out_dir / "well_groundwater_validation_trusted_gwb.csv", index=False)

    trusted_stations = (
        summary_df.loc[
            summary_df["gwb_name"].isin(trusted_gwb["gwb_name"])
            & (summary_df["best_state"] == "groundwater")
            & (summary_df["corr_anom"] >= 0.6)
            & (summary_df["n_matches"] >= 10)
        ]
        .sort_values(["corr_anom", "n_matches"], ascending=[False, False])
        .reset_index(drop=True)
        if not summary_df.empty and not trusted_gwb.empty
        else pd.DataFrame()
    )
    trusted_stations.to_csv(out_dir / "well_groundwater_validation_trusted_stations.csv", index=False)

    overall = {
        "n_station_series_evaluated": int(len(summary_df)),
        "tolerance_days": int(args.tolerance_days),
        "min_matches": int(args.min_matches),
        "lag_days_tested": lag_days_list,
        "top_10_mean_corr": (
            None if summary_df.empty else float(summary_df.head(10)["corr_anom"].mean())
        ),
        "median_corr": (
            None if summary_df.empty else float(summary_df["corr_anom"].median())
        ),
        "n_positive_corr": (
            None if summary_df.empty else int((summary_df["corr_anom"] > 0).sum())
        ),
        "n_corr_ge_0_3": (
            None if summary_df.empty else int((summary_df["corr_anom"] >= 0.3).sum())
        ),
        "n_corr_ge_0_5": (
            None if summary_df.empty else int((summary_df["corr_anom"] >= 0.5).sum())
        ),
        "n_best_groundwater": (
            None if summary_df.empty else int((summary_df["best_state"] == "groundwater").sum())
        ),
        "n_best_shallowload": (
            None if summary_df.empty else int((summary_df["best_state"] == "shallowload").sum())
        ),
        "n_best_deepload": (
            None if summary_df.empty else int((summary_df["best_state"] == "deepload").sum())
        ),
        "n_trusted_gwb_groups": (
            None if trusted_gwb.empty else int(len(trusted_gwb))
        ),
        "n_trusted_stations": (
            None if trusted_stations.empty else int(len(trusted_stations))
        ),
    }
    (out_dir / "well_groundwater_validation_overview.json").write_text(json.dumps(overall, indent=2))


if __name__ == "__main__":
    main()
