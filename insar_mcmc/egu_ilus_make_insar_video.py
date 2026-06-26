"""
egu_ilus_make_insar_video.py
----------------------------
Generate an animated MP4 of Sentinel-1 InSAR LOS cumulative deformation maps
over the Bologna / Emilia-Romagna domain (2017-2024) for EGU slide 3.

Output: egu_ilus_insar_deformation_video.mp4  (in same folder as this script)
"""

import numpy as np
import xarray as xr
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.colors import TwoSlopeNorm
from pathlib import Path
import sys

# ── paths ─────────────────────────────────────────────────────────────────────
HERE   = Path(__file__).parent
NC_IN  = HERE / "outputs_bologna_2025_overlap" / "insar_mintpy2025_on_w3ra_grid.nc"
OUTMP4 = HERE / "egu_ilus_insar_deformation_video.mp4"

# ── load data ──────────────────────────────────────────────────────────────────
print("Loading InSAR data …")
ds   = xr.open_dataset(NC_IN)
defo = ds["insar_deformation"].values.astype(float) * 1000.0   # m → mm (LOS)
lats = ds["lat"].values        # (22,24)
lons = ds["lon"].values
times = pd.to_datetime(ds.time.values)
ds.close()

print(f"  n_times={len(times)}, shape={defo.shape}, range=[{np.nanmin(defo):.1f}, {np.nanmax(defo):.1f}] mm")

# ── colour scale: symmetric about zero, capped at ±40 mm ──────────────────────
VMAX = 40.0
VMIN = -VMAX
norm = TwoSlopeNorm(vmin=VMIN, vcenter=0, vmax=VMAX)
CMAP = "RdBu_r"    # blue = subsidence (towards sensor), red = uplift

# ── figure layout ─────────────────────────────────────────────────────────────
FPS     = 12       # frames per second → ~30 s for 362 frames
DPI     = 120
FW, FH  = 9.0, 6.0

fig, ax = plt.subplots(figsize=(FW, FH), dpi=DPI)
fig.patch.set_facecolor("#0d0d1a")   # dark background for presentation

ax.set_facecolor("#0d0d1a")
ax.tick_params(colors="white", labelcolor="white")
for spine in ax.spines.values():
    spine.set_edgecolor("white")

# initial frame (all NaN → transparent, set first real frame)
first_valid = defo[0].copy()

pcm = ax.pcolormesh(
    lons, lats, first_valid,
    cmap=CMAP, norm=norm, shading="auto"
)

# coastline/border approximation: draw the Po Plain bounding box for context
bbox_lon = [10.2, 12.5, 12.5, 10.2, 10.2]
bbox_lat = [43.8, 43.8, 45.9, 45.9, 43.8]
ax.plot(bbox_lon, bbox_lat, color="white", lw=0.4, alpha=0.3, linestyle="--")

# colorbar
cbar = fig.colorbar(pcm, ax=ax, orientation="vertical", fraction=0.046, pad=0.04)
cbar.set_label("LOS displacement (mm)", color="white", fontsize=10)
cbar.ax.yaxis.set_tick_params(color="white", labelcolor="white")

# labels
ax.set_xlabel("Longitude (°E)", color="white", fontsize=10)
ax.set_ylabel("Latitude (°N)", color="white", fontsize=10)

# static info box (lower-left)
INFO = (
    "Sensor:   Sentinel-1 A/B  (C-band, ~5.6 cm)\n"
    "Track:    Descending  ·  IW mode\n"
    "Processing: ZARVAN-AID containerised ISCE2+ (GPU)\n"
    "Corrections: ERA5 tropo · Solid-Earth tides\n"
    "              Orbital ramp · DEM error\n"
    "Ref. frame: MintPy spatial reference (water body)\n"
    "Grid:      22 × 24 cells  ≈ 0.1° (~10 km)"
)
info_box = ax.text(
    0.01, 0.02, INFO,
    transform=ax.transAxes, fontsize=7,
    color="white", verticalalignment="bottom",
    bbox=dict(boxstyle="round,pad=0.4", facecolor="#0d0d1a", alpha=0.7,
              edgecolor="gray", linewidth=0.6)
)

# counter text (upper-right)
counter_text = ax.text(
    0.98, 0.97, "",
    transform=ax.transAxes, fontsize=9,
    color="white", verticalalignment="top", horizontalalignment="right",
    bbox=dict(boxstyle="round,pad=0.3", facecolor="#0d0d1a", alpha=0.7,
              edgecolor="gray", linewidth=0.6)
)

# date title (top-centre)
date_title = ax.set_title(
    "", color="white", fontsize=13, fontweight="bold", pad=8
)

# domain label
ax.text(
    0.5, 0.98,
    "Bologna / Emilia-Romagna · Po Plain",
    transform=ax.transAxes, fontsize=9, color="lightgray",
    verticalalignment="top", horizontalalignment="center"
)

ax.set_xlim(lons.min() - 0.05, lons.max() + 0.05)
ax.set_ylim(lats.min() - 0.05, lats.max() + 0.05)

plt.tight_layout(pad=0.8)

# ── animation callback ─────────────────────────────────────────────────────────
N = len(times)

def update(frame_idx):
    frame = defo[frame_idx]
    pcm.set_array(frame.ravel())
    date_str   = times[frame_idx].strftime("%Y-%m-%d")
    year_frac  = times[frame_idx].year + (times[frame_idx].dayofyear - 1) / 365.25
    date_title.set_text(f"InSAR LOS cumulative displacement  ·  {date_str}")
    counter_text.set_text(f"Acq {frame_idx + 1:3d} / {N}")
    return pcm, date_title, counter_text

ani = animation.FuncAnimation(
    fig, update,
    frames=N,
    interval=1000 // FPS,
    blit=True
)

# ── write MP4 ─────────────────────────────────────────────────────────────────
print(f"Writing MP4 to {OUTMP4}  ({N} frames @ {FPS} fps) …")
writer = animation.FFMpegWriter(
    fps=FPS,
    metadata=dict(
        title="Sentinel-1 InSAR deformation – Bologna 2017-2024",
        artist="ZARVAN-AID / EGU 2025",
        comment="Processed with MintPy; corrections: ERA5+SET+ramp+demErr"
    ),
    extra_args=[
        "-vcodec", "libx264",
        "-crf", "18",           # high quality
        "-preset", "slow",
        "-pix_fmt", "yuv420p",  # PowerPoint/Keynote compatible
    ]
)

try:
    ani.save(str(OUTMP4), writer=writer, dpi=DPI)
    print(f"Done → {OUTMP4}")
except Exception as e:
    print(f"FFMpeg failed: {e}\nFalling back to Pillow GIF …")
    gif_path = OUTMP4.with_suffix(".gif")
    pil_writer = animation.PillowWriter(fps=FPS)
    ani.save(str(gif_path), writer=pil_writer, dpi=DPI)
    print(f"Done → {gif_path}")

plt.close(fig)
