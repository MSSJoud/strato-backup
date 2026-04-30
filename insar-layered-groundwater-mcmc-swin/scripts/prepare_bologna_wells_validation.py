from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pandas as pd


def convert_utm_to_lonlat(df: pd.DataFrame, x_col: str, y_col: str) -> pd.DataFrame:
    coords = (
        df[[x_col, y_col]]
        .dropna()
        .drop_duplicates()
        .astype(float)
        .reset_index(drop=True)
    )
    if coords.empty:
        df["lon"] = pd.NA
        df["lat"] = pd.NA
        return df

    input_text = "".join(f"{x} {y}\n" for x, y in coords[[x_col, y_col]].itertuples(index=False))
    proc = subprocess.run(
        [
            "cs2cs",
            "-f",
            "%.10f",
            "+init=epsg:25832",
            "+to",
            "+init=epsg:4326",
        ],
        input=input_text,
        text=True,
        capture_output=True,
        check=True,
    )

    lon_vals: list[float] = []
    lat_vals: list[float] = []
    for line in proc.stdout.strip().splitlines():
        parts = line.split()
        lon_vals.append(float(parts[0]))
        lat_vals.append(float(parts[1]))

    coord_map = coords.copy()
    coord_map["lon"] = lon_vals
    coord_map["lat"] = lat_vals

    return df.merge(coord_map, on=[x_col, y_col], how="left")


def tidy_manual_metadata(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(
        columns={
            "Provincia": "province",
            "Codice": "station_code",
            "Tipologia stazione": "station_type",
            "Comune": "municipality",
            "Codice_GWB-PdG_2021-2027": "gwb_code",
            "Nome_GWB_2021-2027": "gwb_name",
            "XUTM-ETRS89": "x_utm_etrs89",
            "YUTM-ETRS89": "y_utm_etrs89",
            "Quota Piano Campagna (m)": "ground_elevation_m",
            "Profondità pozzo (m)": "well_depth_m",
            "Posizione filtri ": "filter_position",
            "N tot filtri": "n_filters",
            "Inizio filtri: da m": "filter_start_m",
            "Fine filtri: a m": "filter_end_m",
        }
    )
    df["source_type"] = "manual"
    return df


def tidy_automatic_metadata(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(
        columns={
            "Prov": "province",
            "Codice": "station_code",
            "Tipologia stazione": "station_type",
            "Comune": "municipality",
            "Codice_GWB_2021-2027": "gwb_code",
            "Nome_GWB_2021-2027": "gwb_name",
            "XUTM-ETRS89": "x_utm_etrs89",
            "YUTM-ETRS89": "y_utm_etrs89",
            "Quota Piano Campagna (m)": "ground_elevation_m",
            "Profondità pozzo (m)": "well_depth_m",
            "Posizione filtri ": "filter_position",
            "N tot filtri": "n_filters",
            "Inizio filtri: da m": "filter_start_m",
            "Fine filtri: a m": "filter_end_m",
            "Uso": "use",
        }
    )
    df["source_type"] = "automatic"
    return df


def tidy_manual_levels(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(
        columns={
            "Codice": "station_code",
            "Data": "date",
            "Piezometria (m)": "piezometry_m",
            "Soggiacenza (m)": "depth_to_water_m",
        }
    )
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df["measurement_type"] = "manual"
    return df


def tidy_automatic_levels(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(columns={"Data": "date"})
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    long_df = df.melt(id_vars=["date"], var_name="station_code", value_name="piezometry_m")
    long_df = long_df.dropna(subset=["piezometry_m"]).reset_index(drop=True)
    long_df["measurement_type"] = "automatic"
    long_df["depth_to_water_m"] = pd.NA
    return long_df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-dir",
        default="/home/ubuntu/work/insar_mcmc/outputs_external_bologna_wells",
    )
    parser.add_argument(
        "--output-dir",
        default="/home/ubuntu/work/insar_mcmc/outputs_external_bologna_wells/processed",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manual_meta = convert_utm_to_lonlat(tidy_manual_metadata(input_dir / "manual_metadata.csv"), "x_utm_etrs89", "y_utm_etrs89")
    automatic_meta = convert_utm_to_lonlat(tidy_automatic_metadata(input_dir / "automatic_metadata.csv"), "x_utm_etrs89", "y_utm_etrs89")

    manual_levels = tidy_manual_levels(input_dir / "manual_levels.csv")
    automatic_levels = tidy_automatic_levels(input_dir / "automatic_levels.csv")

    manual_joined = manual_levels.merge(
        manual_meta.drop(columns=["source_type"]),
        on="station_code",
        how="left",
    )
    automatic_joined = automatic_levels.merge(
        automatic_meta.drop(columns=["source_type"]),
        on="station_code",
        how="left",
    )

    all_levels = pd.concat([manual_joined, automatic_joined], ignore_index=True, sort=False)
    bologna_levels = all_levels.loc[all_levels["province"] == "BO"].copy()

    station_summary = pd.concat(
        [
            manual_meta.assign(metadata_source="manual"),
            automatic_meta.assign(metadata_source="automatic"),
        ],
        ignore_index=True,
        sort=False,
    ).drop_duplicates(subset=["station_code", "metadata_source"])

    manual_joined.to_csv(output_dir / "manual_wells_long.csv", index=False)
    automatic_joined.to_csv(output_dir / "automatic_wells_long.csv", index=False)
    all_levels.to_csv(output_dir / "all_wells_long.csv", index=False)
    bologna_levels.to_csv(output_dir / "bologna_wells_long.csv", index=False)
    station_summary.to_csv(output_dir / "station_metadata_combined.csv", index=False)

    summary = {
        "manual_metadata_rows": int(len(manual_meta)),
        "automatic_metadata_rows": int(len(automatic_meta)),
        "manual_measurements": int(len(manual_joined)),
        "automatic_measurements": int(len(automatic_joined)),
        "all_measurements": int(len(all_levels)),
        "bologna_measurements": int(len(bologna_levels)),
        "bologna_manual_stations_with_measurements": int(
            manual_joined.loc[manual_joined["province"] == "BO", "station_code"].nunique()
        ),
        "bologna_automatic_stations_with_measurements": int(
            automatic_joined.loc[automatic_joined["province"] == "BO", "station_code"].nunique()
        ),
        "bologna_measurement_start": (
            None if bologna_levels["date"].dropna().empty else bologna_levels["date"].min().strftime("%Y-%m-%d")
        ),
        "bologna_measurement_end": (
            None if bologna_levels["date"].dropna().empty else bologna_levels["date"].max().strftime("%Y-%m-%d")
        ),
        "crs_input": "ETRS89 / UTM zone 32N (EPSG:25832)",
        "crs_output": "WGS84 lon/lat (EPSG:4326)",
    }
    (output_dir / "bologna_wells_summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
