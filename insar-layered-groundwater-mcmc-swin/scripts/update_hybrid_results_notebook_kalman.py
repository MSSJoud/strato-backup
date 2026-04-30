#!/usr/bin/env python3
"""Append grouped balanced Kalman result sections to hybrid_results_notebook.ipynb."""

from __future__ import annotations

import json
from pathlib import Path


NOTEBOOK = Path("/home/ubuntu/work/insar_mcmc/hybrid_results_notebook.ipynb")


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
    nb = json.loads(NOTEBOOK.read_text())

    marker = "## Grouped Balanced Kalman"
    cells = nb["cells"]
    if any(marker in "".join(cell.get("source", [])) for cell in cells):
        print("Kalman section already present; leaving notebook unchanged.")
        return

    cells.extend(
        [
            md_cell(
                """## Grouped Balanced Kalman

This section shows the newer **real Bologna grouped balanced Kalman Stage 1** results.

Interpretation:

- this is the first real-data path that stays on physically sane grouped magnitudes
- it is still **grouped** (`ShallowLoad`, `DeepLoad`, `Groundwater`), not full layered inversion
- the main sanity question here is whether the posterior grouped states stay in the same rough order of magnitude as the W3RA anomalies instead of exploding"""
            ),
            code_cell(
                """KALMAN_REGIONAL_DIR = ROOT / 'outputs_stage1_bologna_multisensor_kalman'
KALMAN_TILED_DIR = ROOT / 'outputs_stage1_bologna_multisensor_kalman_tiled'

KALMAN_PATHS = {
    'regional_json': KALMAN_REGIONAL_DIR / 'stage1_bologna_multisensor_kalman_summary.json',
    'regional_npz': KALMAN_REGIONAL_DIR / 'stage1_bologna_multisensor_kalman_results.npz',
    'regional_csv': KALMAN_REGIONAL_DIR / 'stage1_bologna_multisensor_kalman_timeseries.csv',
    'tiled_json': KALMAN_TILED_DIR / 'stage1_bologna_multisensor_kalman_tiled_summary.json',
    'tiled_npz': KALMAN_TILED_DIR / 'stage1_bologna_multisensor_kalman_tiled_results.npz',
}

for name, path in KALMAN_PATHS.items():
    print(f'{name}: {path} | exists={path.exists()}')

kalman_regional_summary = load_json(KALMAN_PATHS['regional_json']) if KALMAN_PATHS['regional_json'].exists() else None
kalman_tiled_summary = load_json(KALMAN_PATHS['tiled_json']) if KALMAN_PATHS['tiled_json'].exists() else None
kalman_regional = np.load(KALMAN_PATHS['regional_npz']) if KALMAN_PATHS['regional_npz'].exists() else None
kalman_tiled = np.load(KALMAN_PATHS['tiled_npz']) if KALMAN_PATHS['tiled_npz'].exists() else None

if kalman_regional is not None:
    print('Kalman regional keys:', sorted(kalman_regional.files))
if kalman_tiled is not None:
    print('Kalman tiled keys:', sorted(kalman_tiled.files))"""
            ),
            code_cell(
                """if kalman_regional_summary is not None:
    print('Regional grouped Kalman metrics')
    rows = []
    for sensor in ['insar', 'grace', 'smap']:
        rows.append({
            'sensor': sensor,
            'prior_r2': kalman_regional_summary['metrics'][f'{sensor}_prior']['r2'],
            'post_r2': kalman_regional_summary['metrics'][f'{sensor}_post']['r2'],
            'delta_r2': kalman_regional_summary['metrics'][f'{sensor}_post']['r2'] - kalman_regional_summary['metrics'][f'{sensor}_prior']['r2'],
            'prior_corr': kalman_regional_summary['metrics'][f'{sensor}_prior']['corr'],
            'post_corr': kalman_regional_summary['metrics'][f'{sensor}_post']['corr'],
            'prior_rmse': kalman_regional_summary['metrics'][f'{sensor}_prior']['rmse'],
            'post_rmse': kalman_regional_summary['metrics'][f'{sensor}_post']['rmse'],
        })
    display(pd.DataFrame(rows).round(4))

if kalman_tiled_summary is not None:
    print('Tiled grouped Kalman fit and magnitude summary')
    display(pd.DataFrame([kalman_tiled_summary['metrics']['tile_insar_post']]).round(4))
    mag_df = pd.DataFrame(kalman_tiled_summary['magnitude']).T
    display(mag_df.round(4))

try:
    import xarray as xr
    w = xr.open_dataset('/mnt/data/mcma/01/w3ra_sub_anom.nc')
    raw_rows = []
    grouped_raw = {
        'ShallowLoad': (w['S0'] + w['Ss']).values,
        'DeepLoad': (w['Sd'] + w['Sr']).values,
        'Groundwater': w['Sg'].values,
    }
    for name, arr in grouped_raw.items():
        raw_rows.append({
            'state': name,
            'raw_abs_max_mm': float(np.nanmax(np.abs(arr))),
            'raw_std_mm': float(np.nanstd(arr)),
            'posterior_abs_max_mm': kalman_tiled_summary['magnitude'][name]['x_abs_max'] if kalman_tiled_summary is not None else np.nan,
        })
    raw_df = pd.DataFrame(raw_rows)
    raw_df['posterior_to_raw_absmax_ratio'] = raw_df['posterior_abs_max_mm'] / raw_df['raw_abs_max_mm']
    print('Sanity check against raw grouped W3RA anomalies')
    display(raw_df.round(4))
    w.close()
except Exception as exc:
    print('Could not compute raw W3RA sanity table:', exc)"""
            ),
            code_cell(
                """if kalman_tiled is not None:
    kalman_state_names = kalman_tiled['state_names'].tolist()
    kalman_lon = kalman_tiled['lon_tiles']
    kalman_lat = kalman_tiled['lat_tiles']
    kalman_field_dd = widgets.Dropdown(options=kalman_state_names + ['theta_ShallowLoad', 'theta_DeepLoad', 'theta_Groundwater', 'insar_obs', 'insar_post'], value='Groundwater', description='Field')
    kalman_time_sl = widgets.IntSlider(value=min(10, kalman_tiled['x_tiles'].shape[0] - 1), min=0, max=kalman_tiled['x_tiles'].shape[0] - 1, step=1, description='Time')
    kalman_out = widgets.Output()

    def get_kalman_field(field, tidx):
        if field in kalman_state_names:
            return kalman_tiled['x_tiles'][tidx, kalman_state_names.index(field)]
        if field.startswith('theta_'):
            name = field.split('_', 1)[1]
            return kalman_tiled['theta_tiles'][tidx, kalman_state_names.index(name)]
        if field == 'insar_obs':
            return kalman_tiled['y_obs_tiles'][tidx]
        if field == 'insar_post':
            return kalman_tiled['y_post_tiles'][tidx]
        raise ValueError(field)

    def refresh_kalman(*_):
        with kalman_out:
            kalman_out.clear_output(wait=True)
            arr = get_kalman_field(kalman_field_dd.value, kalman_time_sl.value)
            fig, ax = plt.subplots(1, 1, figsize=(6, 5))
            plot_lonlat(ax, kalman_lon, kalman_lat, arr, f'Kalman grouped | {kalman_field_dd.value} | t={kalman_time_sl.value}')
            plt.show()

    kalman_field_dd.observe(refresh_kalman, names='value')
    kalman_time_sl.observe(refresh_kalman, names='value')
    display(widgets.HBox([kalman_field_dd]), kalman_time_sl, kalman_out)
    refresh_kalman()
else:
    print('Tiled grouped Kalman output is not available.')"""
            ),
            code_cell(
                """if kalman_regional is not None:
    kalman_ts = pd.read_csv(KALMAN_PATHS['regional_csv'])
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), constrained_layout=True)

    axes[0].plot(pd.to_datetime(kalman_ts['time']), kalman_ts['y_insar'], label='InSAR obs')
    axes[0].plot(pd.to_datetime(kalman_ts['time']), kalman_ts['y_insar_post'], label='InSAR post')
    axes[0].plot(pd.to_datetime(kalman_ts['time']), kalman_ts['y_grace'], label='GRACE obs')
    axes[0].plot(pd.to_datetime(kalman_ts['time']), kalman_ts['y_grace_post'], label='GRACE post')
    axes[0].plot(pd.to_datetime(kalman_ts['time']), kalman_ts['y_smap'], label='SMAP obs')
    axes[0].plot(pd.to_datetime(kalman_ts['time']), kalman_ts['y_smap_post'], label='SMAP post')
    axes[0].set_title('Regional multisensor fit')
    axes[0].legend(ncol=3, fontsize=8)

    axes[1].plot(pd.to_datetime(kalman_ts['time']), kalman_ts['x_shallow'], label='ShallowLoad')
    axes[1].plot(pd.to_datetime(kalman_ts['time']), kalman_ts['x_deep'], label='DeepLoad')
    axes[1].plot(pd.to_datetime(kalman_ts['time']), kalman_ts['x_groundwater'], label='Groundwater')
    axes[1].set_title('Posterior grouped states')
    axes[1].legend()
    plt.show()

    print('Simple verdict')
    verdict = pd.DataFrame([{
        'question': 'Do grouped posterior magnitudes stay below 100 mm?',
        'answer': bool(max(v['x_abs_max'] for v in kalman_tiled_summary['magnitude'].values()) < 100.0) if kalman_tiled_summary is not None else None,
    }, {
        'question': 'Did regional InSAR R2 improve over prior?',
        'answer': bool(kalman_regional_summary['metrics']['insar_post']['r2'] > kalman_regional_summary['metrics']['insar_prior']['r2']) if kalman_regional_summary is not None else None,
    }, {
        'question': 'Did regional GRACE R2 improve over prior?',
        'answer': bool(kalman_regional_summary['metrics']['grace_post']['r2'] > kalman_regional_summary['metrics']['grace_prior']['r2']) if kalman_regional_summary is not None else None,
    }])
    display(verdict)
else:
    print('Regional grouped Kalman output is not available.')"""
            ),
            md_cell(
                """## Kalman Notes

- The grouped balanced Kalman path is now the most promising real-data direction.
- The tiled grouped posterior stays in an approximately tens-of-mm range rather than exploding to unphysical million-mm values.
- This is still not a full layered hydrology result, but it is a much more credible starting point for any later decomposition."""
            ),
        ]
    )

    NOTEBOOK.write_text(json.dumps(nb, indent=1))
    print(f"Updated {NOTEBOOK}")


if __name__ == "__main__":
    main()
