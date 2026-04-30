#!/usr/bin/env python3
"""
MintPy Docker Playbook — Step 4: Generate Publication-Quality Figures
=====================================================================
Creates a comprehensive set of analysis figures from MintPy outputs:
  1. Velocity map with DEM hillshade
  2. Temporal coherence map
  3. Interferogram network plot
  4. Displacement time-series at selected points
  5. Velocity histogram
  6. Residual RMS time-series
  7. Summary dashboard (multi-panel)
"""

import os
import sys
import glob
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import h5py
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.colors import Normalize
from datetime import datetime

# Configuration
DATASET = os.environ.get('DATASET', 'FernandinaSenDT128')
WORK_DIR = f'/data/{DATASET}/mintpy'
OUT_DIR = '/workspace/outputs'
FIG_FORMAT = os.environ.get('FIGURE_FORMAT', 'png')
FIG_DPI = int(os.environ.get('FIGURE_DPI', 300))

os.makedirs(OUT_DIR, exist_ok=True)


def safe_read(filepath, dataset=None):
    """Safely read an HDF5 dataset, returning None if unavailable."""
    try:
        with h5py.File(filepath, 'r') as f:
            if dataset:
                return f[dataset][:]
            # Return the first 2D dataset found
            for key in f.keys():
                if len(f[key].shape) >= 2:
                    return f[key][:]
    except Exception as e:
        print(f"  ⚠ Could not read {filepath}: {e}")
        return None


def read_dates(filepath):
    """Read date array from a time-series HDF5 file."""
    try:
        with h5py.File(filepath, 'r') as f:
            return [d.decode() for d in f['date'][:]]
    except:
        return None


def date_str_to_dt(date_str):
    """Convert YYYYMMDD string to datetime."""
    return datetime.strptime(date_str, '%Y%m%d')


# =============================================================================
# Figure 1: Velocity Map
# =============================================================================
def plot_velocity_map():
    """Generate a velocity map with optional DEM shading."""
    print("  [1/7] Velocity map...")
    vel = safe_read(f'{WORK_DIR}/velocity.h5', 'velocity')
    if vel is None:
        return

    fig, ax = plt.subplots(1, 1, figsize=(10, 8))

    # Convert to cm/yr
    vel_cm = vel * 100.0
    vel_cm[vel_cm == 0] = np.nan

    # Symmetric colorbar centered at 0
    vmax = np.nanpercentile(np.abs(vel_cm), 95)
    im = ax.imshow(vel_cm, cmap='jet', vmin=-vmax, vmax=vmax,
                   interpolation='nearest')

    # Add DEM hillshade if available
    dem = safe_read(f'{WORK_DIR}/inputs/geometryRadar.h5', 'height')
    if dem is not None:
        from matplotlib.colors import LightSource
        ls = LightSource(azdeg=315, altdeg=45)
        hillshade = ls.hillshade(dem, vert_exag=2)
        ax.imshow(hillshade, cmap='gray', alpha=0.3)

    cbar = fig.colorbar(im, ax=ax, shrink=0.7, pad=0.02)
    cbar.set_label('LOS Velocity (cm/yr)', fontsize=12)

    ax.set_title(f'LOS Velocity — {DATASET}', fontsize=14, fontweight='bold')
    ax.set_xlabel('Range (pixels)')
    ax.set_ylabel('Azimuth (pixels)')

    fig.tight_layout()
    fig.savefig(f'{OUT_DIR}/fig01_velocity_map.{FIG_FORMAT}', dpi=FIG_DPI,
                bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print("    ✓ Saved fig01_velocity_map")


# =============================================================================
# Figure 2: Temporal Coherence
# =============================================================================
def plot_temporal_coherence():
    """Generate temporal coherence map."""
    print("  [2/7] Temporal coherence...")
    coh = safe_read(f'{WORK_DIR}/temporalCoherence.h5')
    if coh is None:
        return

    fig, ax = plt.subplots(1, 1, figsize=(10, 8))
    im = ax.imshow(coh, cmap='gray', vmin=0, vmax=1, interpolation='nearest')
    cbar = fig.colorbar(im, ax=ax, shrink=0.7, pad=0.02)
    cbar.set_label('Temporal Coherence', fontsize=12)
    ax.set_title(f'Temporal Coherence — {DATASET}', fontsize=14, fontweight='bold')
    ax.set_xlabel('Range (pixels)')
    ax.set_ylabel('Azimuth (pixels)')

    fig.tight_layout()
    fig.savefig(f'{OUT_DIR}/fig02_temporal_coherence.{FIG_FORMAT}', dpi=FIG_DPI,
                bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print("    ✓ Saved fig02_temporal_coherence")


# =============================================================================
# Figure 3: Interferogram Network
# =============================================================================
def plot_network():
    """Plot interferogram network (temporal baseline vs perpendicular baseline)."""
    print("  [3/7] Interferogram network...")
    try:
        with h5py.File(f'{WORK_DIR}/inputs/ifgramStack.h5', 'r') as f:
            date12_list = [d.decode() for d in f['date'][:]]
            if 'bperp' in f.keys():
                bperp = f['bperp'][:]
            else:
                bperp = None
            drop = f['dropIfgram'][:] if 'dropIfgram' in f.keys() else None
    except Exception as e:
        print(f"    ⚠ Skipped: {e}")
        return

    # Parse dates
    dates = sorted(set([d[:8] for d in date12_list] + [d[9:] for d in date12_list]))
    date_dts = [date_str_to_dt(d) for d in dates]

    fig, ax = plt.subplots(1, 1, figsize=(14, 5))

    # Plot date markers
    if bperp is not None:
        ax.scatter(date_dts, bperp, c='blue', s=30, zorder=5)
        ax.set_ylabel('Perpendicular Baseline (m)', fontsize=12)
    else:
        ax.scatter(date_dts, range(len(date_dts)), c='blue', s=30, zorder=5)
        ax.set_ylabel('Acquisition Index', fontsize=12)

    ax.set_title(f'Interferogram Network — {DATASET}\n{len(date12_list)} interferograms, {len(dates)} acquisitions',
                 fontsize=13, fontweight='bold')
    ax.set_xlabel('Date', fontsize=12)
    ax.tick_params(axis='x', rotation=45)

    fig.tight_layout()
    fig.savefig(f'{OUT_DIR}/fig03_network.{FIG_FORMAT}', dpi=FIG_DPI,
                bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print("    ✓ Saved fig03_network")


# =============================================================================
# Figure 4: Displacement Time-Series at Selected Points
# =============================================================================
def plot_timeseries_points():
    """Plot displacement time-series at interesting points."""
    print("  [4/7] Displacement time-series...")

    # Find the most corrected time-series
    ts_files = sorted(glob.glob(f'{WORK_DIR}/timeseries*.h5'))
    if not ts_files:
        print("    ⚠ No time-series file found")
        return

    ts_file = ts_files[-1]  # Most processed
    dates = read_dates(ts_file)
    ts = safe_read(ts_file, 'timeseries')
    if ts is None or dates is None:
        return

    date_dts = [date_str_to_dt(d) for d in dates]
    ntime, nrow, ncol = ts.shape

    # Select sample points (center, corners of high-deformation area)
    points = {
        'Center': (nrow // 2, ncol // 2),
        'Upper-left quarter': (nrow // 4, ncol // 4),
        'Lower-right quarter': (3 * nrow // 4, 3 * ncol // 4),
    }

    # Also find pixel with maximum displacement
    last_frame = ts[-1]
    valid_mask = np.isfinite(last_frame) & (last_frame != 0)
    if valid_mask.any():
        max_idx = np.unravel_index(np.nanargmax(np.abs(last_frame * valid_mask)), last_frame.shape)
        points['Max displacement'] = max_idx

    fig, ax = plt.subplots(1, 1, figsize=(12, 6))
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12']

    for i, (label, (row, col)) in enumerate(points.items()):
        disp = ts[:, row, col] * 100  # Convert to cm
        if np.all(disp == 0) or np.all(np.isnan(disp)):
            continue
        ax.plot(date_dts, disp, 'o-', label=f'{label} ({row},{col})',
                color=colors[i % len(colors)], markersize=3, linewidth=1)

    ax.axhline(0, color='gray', linewidth=0.5, linestyle='--')
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('LOS Displacement (cm)', fontsize=12)
    ax.set_title(f'Displacement Time-Series — {DATASET}\nFile: {os.path.basename(ts_file)}',
                 fontsize=13, fontweight='bold')
    ax.legend(loc='best', fontsize=9)
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(f'{OUT_DIR}/fig04_timeseries.{FIG_FORMAT}', dpi=FIG_DPI,
                bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print("    ✓ Saved fig04_timeseries")


# =============================================================================
# Figure 5: Velocity Histogram
# =============================================================================
def plot_velocity_histogram():
    """Histogram of velocity values."""
    print("  [5/7] Velocity histogram...")
    vel = safe_read(f'{WORK_DIR}/velocity.h5', 'velocity')
    if vel is None:
        return

    vel_cm = vel.flatten() * 100
    vel_cm = vel_cm[np.isfinite(vel_cm) & (vel_cm != 0)]

    fig, ax = plt.subplots(1, 1, figsize=(10, 5))
    ax.hist(vel_cm, bins=100, color='steelblue', edgecolor='white', linewidth=0.5, alpha=0.8)
    ax.axvline(np.median(vel_cm), color='red', linestyle='--', linewidth=1.5,
               label=f'Median: {np.median(vel_cm):.2f} cm/yr')
    ax.axvline(np.mean(vel_cm), color='orange', linestyle='--', linewidth=1.5,
               label=f'Mean: {np.mean(vel_cm):.2f} cm/yr')
    ax.set_xlabel('LOS Velocity (cm/yr)', fontsize=12)
    ax.set_ylabel('Pixel Count', fontsize=12)
    ax.set_title(f'Velocity Distribution — {DATASET}', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(f'{OUT_DIR}/fig05_velocity_histogram.{FIG_FORMAT}', dpi=FIG_DPI,
                bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print("    ✓ Saved fig05_velocity_histogram")


# =============================================================================
# Figure 6: Residual RMS
# =============================================================================
def plot_residual_rms():
    """Plot residual RMS over time if available."""
    print("  [6/7] Residual RMS...")
    rms_file = f'{WORK_DIR}/timeseriesResidual.h5'
    if not os.path.exists(rms_file):
        rms_files = glob.glob(f'{WORK_DIR}/timeseriesResidual*.h5')
        if rms_files:
            rms_file = rms_files[0]
        else:
            print("    ⚠ No residual time-series found, skipping")
            return

    dates = read_dates(rms_file)
    ts_resid = safe_read(rms_file, 'timeseries')
    if ts_resid is None or dates is None:
        return

    date_dts = [date_str_to_dt(d) for d in dates]

    # Compute RMS for each date
    rms = []
    for i in range(ts_resid.shape[0]):
        frame = ts_resid[i].flatten()
        valid = frame[np.isfinite(frame) & (frame != 0)]
        rms.append(np.sqrt(np.mean(valid**2)) * 100 if len(valid) > 0 else 0)

    fig, ax = plt.subplots(1, 1, figsize=(12, 5))
    ax.bar(date_dts, rms, width=10, color='steelblue', alpha=0.8)
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Residual RMS (cm)', fontsize=12)
    ax.set_title(f'Residual Phase RMS — {DATASET}', fontsize=14, fontweight='bold')
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, alpha=0.3, axis='y')

    fig.tight_layout()
    fig.savefig(f'{OUT_DIR}/fig06_residual_rms.{FIG_FORMAT}', dpi=FIG_DPI,
                bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print("    ✓ Saved fig06_residual_rms")


# =============================================================================
# Figure 7: Summary Dashboard
# =============================================================================
def plot_dashboard():
    """Multi-panel summary dashboard."""
    print("  [7/7] Summary dashboard...")

    vel = safe_read(f'{WORK_DIR}/velocity.h5', 'velocity')
    coh = safe_read(f'{WORK_DIR}/temporalCoherence.h5')
    dem = safe_read(f'{WORK_DIR}/inputs/geometryRadar.h5', 'height')

    if vel is None:
        print("    ⚠ Skipped (velocity unavailable)")
        return

    fig = plt.figure(figsize=(16, 12))
    gs = GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.25)

    # Panel A: Velocity
    ax1 = fig.add_subplot(gs[0, 0])
    vel_cm = vel * 100
    vel_cm[vel_cm == 0] = np.nan
    vmax = np.nanpercentile(np.abs(vel_cm), 95)
    im1 = ax1.imshow(vel_cm, cmap='jet', vmin=-vmax, vmax=vmax)
    fig.colorbar(im1, ax=ax1, shrink=0.8, label='cm/yr')
    ax1.set_title('(a) LOS Velocity', fontweight='bold')

    # Panel B: Temporal Coherence
    ax2 = fig.add_subplot(gs[0, 1])
    if coh is not None:
        im2 = ax2.imshow(coh, cmap='gray', vmin=0, vmax=1)
        fig.colorbar(im2, ax=ax2, shrink=0.8, label='Coherence')
    ax2.set_title('(b) Temporal Coherence', fontweight='bold')

    # Panel C: DEM
    ax3 = fig.add_subplot(gs[1, 0])
    if dem is not None:
        im3 = ax3.imshow(dem, cmap='terrain')
        fig.colorbar(im3, ax=ax3, shrink=0.8, label='Elevation (m)')
    ax3.set_title('(c) DEM', fontweight='bold')

    # Panel D: Velocity histogram
    ax4 = fig.add_subplot(gs[1, 1])
    vel_flat = vel_cm.flatten()
    vel_valid = vel_flat[np.isfinite(vel_flat)]
    if len(vel_valid) > 0:
        ax4.hist(vel_valid, bins=80, color='steelblue', edgecolor='white',
                 linewidth=0.3, alpha=0.8)
        ax4.axvline(np.median(vel_valid), color='red', linestyle='--',
                    label=f'Median: {np.median(vel_valid):.2f} cm/yr')
    ax4.set_xlabel('LOS Velocity (cm/yr)')
    ax4.set_ylabel('Count')
    ax4.set_title('(d) Velocity Distribution', fontweight='bold')
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    fig.suptitle(f'MintPy Analysis Summary — {DATASET}', fontsize=16, fontweight='bold', y=0.98)

    fig.savefig(f'{OUT_DIR}/fig07_dashboard.{FIG_FORMAT}', dpi=FIG_DPI,
                bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print("    ✓ Saved fig07_dashboard")


# =============================================================================
# Main
# =============================================================================
def main():
    print("══════════════════════════════════════════════════════════════")
    print("  Step 4: Generate Publication-Quality Figures")
    print(f"  Dataset: {DATASET}")
    print(f"  Output:  {OUT_DIR}/")
    print(f"  Format:  {FIG_FORMAT} @ {FIG_DPI} DPI")
    print("══════════════════════════════════════════════════════════════")

    if not os.path.isdir(WORK_DIR):
        print(f"\n✗ ERROR: Work directory not found: {WORK_DIR}")
        print("  Run the pipeline (Steps 1-2) first.")
        sys.exit(1)

    print("")
    plot_velocity_map()
    plot_temporal_coherence()
    plot_network()
    plot_timeseries_points()
    plot_velocity_histogram()
    plot_residual_rms()
    plot_dashboard()

    print("")
    n_figs = len(glob.glob(f'{OUT_DIR}/fig*.{FIG_FORMAT}'))
    print(f"✅ Step 4 complete — {n_figs} figures saved to {OUT_DIR}/")


if __name__ == '__main__':
    main()
