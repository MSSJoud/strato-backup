#!/usr/bin/env python3
"""Create an interactive Emilia-Romagna SWOT notebook."""

from __future__ import annotations

import json
from pathlib import Path


NOTEBOOK = Path("/home/ubuntu/work/insar_mcmc/swot_emilia_romagna_notebook.ipynb")


def md_cell(text: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line if line.endswith("\n") else line + "\n" for line in text.splitlines()],
    }


def code_cell(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line if line.endswith("\n") else line + "\n" for line in text.splitlines()],
    }


def main() -> None:
    nb = {
        "cells": [
            md_cell(
                """# SWOT Emilia-Romagna Interactive Map

This notebook explores the separate SWOT download for Emilia-Romagna and the Bologna-overlap subset.

What SWOT measures here:

- rivers: surface-water reach observations such as `wse` (water surface elevation), `width`, `slope2`, and `d_x_area`
- lakes: surface-water observations such as `wse` and `area_total`

Important interpretation:

- SWOT is **not** deformation and **not** groundwater directly
- it is an external surface-water constraint
- unlike the older Bologna subset, the corrected MintPy/W3RA overlap used in this project now runs into **2024-08-01**
- the processed SWOT archive here spans **2023-11-22** to **2024-03-17**, so there is partial temporal overlap with the corrected scene

The interactive map below lets you click a river reach or lake feature and inspect its time series."""
            ),
            code_cell(
                """from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import ipywidgets as widgets
from IPython.display import display

ROOT = Path('/home/ubuntu/work/insar_mcmc')
PROC = ROOT / 'outputs_external_constraints' / 'swot_emilia_romagna_processed'
BOL = ROOT / 'outputs_external_constraints' / 'swot_bologna_overlap2025'

PATHS = {
    'summary_json': PROC / 'swot_emilia_romagna_summary.json',
    'river_features': PROC / 'swot_emilia_romagna_river_features.csv',
    'lake_features': PROC / 'swot_emilia_romagna_lake_features.csv',
    'river_summary': PROC / 'swot_emilia_romagna_river_summary.csv',
    'lake_summary': PROC / 'swot_emilia_romagna_lake_summary.csv',
    'river_latest': PROC / 'swot_emilia_romagna_river_latest.csv',
    'lake_latest': PROC / 'swot_emilia_romagna_lake_latest.csv',
    'bologna_summary_json': BOL / 'swot_bologna_overlap_summary.json',
    'bologna_river_summary': BOL / 'swot_bologna_overlap_river_summary.csv',
    'bologna_lake_summary': BOL / 'swot_bologna_overlap_lake_summary.csv',
}

for name, path in PATHS.items():
    print(f'{name}: {path} | exists={path.exists()}')

summary = json.loads(PATHS['summary_json'].read_text())
bologna_summary = json.loads(PATHS['bologna_summary_json'].read_text()) if PATHS['bologna_summary_json'].exists() else None
print(json.dumps(summary, indent=2))
if bologna_summary is not None:
    print(json.dumps(bologna_summary, indent=2))"""
            ),
            code_cell(
                """river = pd.read_csv(PATHS['river_features'])
lake = pd.read_csv(PATHS['lake_features'])
river_summary = pd.read_csv(PATHS['river_summary'])
lake_summary = pd.read_csv(PATHS['lake_summary'])
river_latest = pd.read_csv(PATHS['river_latest'])
lake_latest = pd.read_csv(PATHS['lake_latest'])
bologna_river_summary = pd.read_csv(PATHS['bologna_river_summary']) if PATHS['bologna_river_summary'].exists() else pd.DataFrame()
bologna_lake_summary = pd.read_csv(PATHS['bologna_lake_summary']) if PATHS['bologna_lake_summary'].exists() else pd.DataFrame()

for df in [river, lake, river_summary, lake_summary, river_latest, lake_latest, bologna_river_summary, bologna_lake_summary]:
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], utc=True, errors='coerce')

display(pd.DataFrame([{
    'regional_river_rows': len(river),
    'regional_lake_rows': len(lake),
    'regional_river_reaches': river['reach_id'].nunique(),
    'regional_lakes': lake['lake_id'].nunique(),
    'regional_time_start': min(river['time'].min(), lake['time'].min()),
    'regional_time_end': max(river['time'].max(), lake['time'].max()),
    'bologna_overlap_river_dates': int(bologna_river_summary['time'].nunique()) if not bologna_river_summary.empty else 0,
    'bologna_overlap_lake_dates': int(bologna_lake_summary['time'].nunique()) if not bologna_lake_summary.empty else 0,
}]))"""
            ),
            code_cell(
                """fig, axes = plt.subplots(2, 1, figsize=(12, 8), constrained_layout=True)

axes[0].plot(river_summary['time'], river_summary['wse_mean'], label='Regional river WSE mean')
axes[0].plot(river_summary['time'], river_summary['width_mean'], label='Regional river width mean')
if not bologna_river_summary.empty:
    axes[0].plot(bologna_river_summary['time'], bologna_river_summary['wse_mean'], '--', label='Bologna-overlap river WSE mean')
axes[0].set_title('River SWOT summary through time')
axes[0].legend()

axes[1].plot(lake_summary['time'], lake_summary['wse_mean'], label='Regional lake WSE mean')
axes[1].plot(lake_summary['time'], lake_summary['area_total_mean'], label='Regional lake area_total mean')
if not bologna_lake_summary.empty:
    axes[1].plot(bologna_lake_summary['time'], bologna_lake_summary['wse_mean'], '--', label='Bologna-overlap lake WSE mean')
axes[1].set_title('Lake SWOT summary through time')
axes[1].legend()

plt.show()"""
            ),
            code_cell(
                """# Build a clickable regional map. Clicking a point opens the feature time series.

river_latest = river_latest.dropna(subset=['p_lon', 'p_lat']).copy()
lake_latest = lake_latest.dropna(subset=['lon', 'lat']).copy()
river_latest['label'] = river_latest['river_name'].fillna('unknown').astype(str) + ' | reach ' + river_latest['reach_id'].astype(str)
lake_latest['label'] = lake_latest['lake_name'].fillna('unknown').astype(str) + ' | lake ' + lake_latest['lake_id'].astype(str)

map_fig = go.FigureWidget()
map_fig.add_trace(go.Scattergl(
    x=river_latest['p_lon'],
    y=river_latest['p_lat'],
    mode='markers',
    name='River reaches',
    marker=dict(size=7, color=river_latest['wse'], colorscale='Viridis', colorbar=dict(title='River WSE')),
    text=river_latest['label'],
    customdata=np.stack([river_latest['reach_id'].astype(str)], axis=-1),
    hovertemplate='%{text}<br>lon=%{x:.3f}<br>lat=%{y:.3f}<extra></extra>',
))
map_fig.add_trace(go.Scattergl(
    x=lake_latest['lon'],
    y=lake_latest['lat'],
    mode='markers',
    name='Lakes',
    marker=dict(size=8, symbol='diamond', color=lake_latest['wse'], colorscale='Turbo', colorbar=dict(title='Lake WSE', x=1.12)),
    text=lake_latest['label'],
    customdata=np.stack([lake_latest['lake_id'].astype(str)], axis=-1),
    hovertemplate='%{text}<br>lon=%{x:.3f}<br>lat=%{y:.3f}<extra></extra>',
))
map_fig.update_layout(
    title='SWOT Emilia-Romagna latest features',
    xaxis_title='Longitude',
    yaxis_title='Latitude',
    width=900,
    height=650,
    legend=dict(orientation='h'),
)

out = widgets.Output()

def show_river(reach_id: str):
    sub = river[river['reach_id'].astype(str) == str(reach_id)].sort_values('time')
    with out:
        out.clear_output(wait=True)
        if sub.empty:
            print(f'No river data for reach {reach_id}')
            return
        display(sub[['reach_id', 'river_name', 'p_lon', 'p_lat']].drop_duplicates().head(1))
        fig, axes = plt.subplots(3, 1, figsize=(10, 8), constrained_layout=True)
        axes[0].plot(sub['time'], pd.to_numeric(sub['wse'], errors='coerce'), marker='o')
        axes[0].set_title(f'River reach {reach_id} | WSE')
        axes[1].plot(sub['time'], pd.to_numeric(sub['width'], errors='coerce'), marker='o')
        axes[1].set_title('Width')
        axes[2].plot(sub['time'], pd.to_numeric(sub['slope2'], errors='coerce'), marker='o', label='slope2')
        if 'd_x_area' in sub.columns:
            axes[2].plot(sub['time'], pd.to_numeric(sub['d_x_area'], errors='coerce'), marker='o', label='d_x_area')
        axes[2].legend()
        axes[2].set_title('Slope / area signals')
        plt.show()

def show_lake(lake_id: str):
    sub = lake[lake['lake_id'].astype(str) == str(lake_id)].sort_values('time')
    with out:
        out.clear_output(wait=True)
        if sub.empty:
            print(f'No lake data for lake {lake_id}')
            return
        display(sub[['lake_id', 'lake_name', 'lon', 'lat']].drop_duplicates().head(1))
        fig, axes = plt.subplots(2, 1, figsize=(10, 6), constrained_layout=True)
        axes[0].plot(sub['time'], pd.to_numeric(sub['wse'], errors='coerce'), marker='o')
        axes[0].set_title(f'Lake {lake_id} | WSE')
        axes[1].plot(sub['time'], pd.to_numeric(sub['area_total'], errors='coerce'), marker='o')
        axes[1].set_title('Area total')
        plt.show()

def river_click(trace, points, selector):
    if points.point_inds:
        idx = points.point_inds[0]
        show_river(trace.customdata[idx][0])

def lake_click(trace, points, selector):
    if points.point_inds:
        idx = points.point_inds[0]
        show_lake(trace.customdata[idx][0])

map_fig.data[0].on_click(river_click)
map_fig.data[1].on_click(lake_click)

display(map_fig)
display(out)
print('Click a river or lake point in the map to view the feature time series.')"""
            ),
            md_cell(
                """## Notes

- The regional map uses the latest available observation per feature.
- Clicking a point shows the full time series for that reach or lake from the processed archive.
- The Bologna-overlap subset is available in the summary plots above and in:
  - `swot_bologna_overlap_river_summary.csv`
  - `swot_bologna_overlap_lake_summary.csv`
- SWOT is best interpreted here as a surface-water constraint, not a deformation or groundwater observation."""
            ),
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.13"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    NOTEBOOK.write_text(json.dumps(nb, indent=1))
    print(f"Wrote {NOTEBOOK}")


if __name__ == "__main__":
    main()
