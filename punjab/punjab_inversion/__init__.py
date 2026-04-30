"""Lightweight package exports for Punjab inversion utilities.

This module avoids importing plotting-heavy helpers at package import time.
Callers still get the same public names, but they are loaded lazily from the
owning submodule the first time they are accessed.
"""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "PriorAlignmentConfig": "priors",
    "GRACE_CANDIDATE_PATTERNS": "priors",
    "punjab_month_index": "priors",
    "align_w3ra_to_punjab_dates": "priors",
    "align_grace_to_punjab_dates": "priors",
    "compute_w3ra_anomalies": "priors",
    "compute_grace_anomalies": "priors",
    "basin_mean_timeseries": "priors",
    "discover_grace_candidates": "priors",
    "interpolate_w3ra_tile": "priors",
    "summarize_grace_alignment": "priors",
    "summarize_w3ra_alignment": "priors",
    "load_simple_h5_grid": "paper_figures",
    "compute_time_valid_fraction": "paper_figures",
    "build_support_mask": "paper_figures",
    "decode_netcdf_time": "comparison_figures",
    "load_h5_netcdf_variable": "comparison_figures",
    "robust_limits": "comparison_figures",
    "latest_valid_slice": "comparison_figures",
    "anomaly_relative_to_time_mean": "comparison_figures",
    "basin_mean_timeseries_np": "comparison_figures",
    "select_active_bbox": "comparison_figures",
    "select_finite_bbox": "comparison_figures",
    "make_punjab_comparison_maps": "comparison_figures",
    "make_punjab_comparison_individual_panels": "comparison_figures",
    "make_punjab_comparison_timeseries": "comparison_figures",
    "make_support_mask_figure": "paper_figures",
    "copy_existing_figure": "paper_figures",
    "make_prior_ablation_figure": "paper_figures",
    "load_prediction_archive_metadata": "paper_figures",
    "load_netcdf_h5_metadata": "paper_figures",
    "make_baseline_export_panel": "paper_figures",
    "normalize_field": "metrics",
    "batch_correlation_torch": "metrics",
    "amplitude_penalty_torch": "metrics",
    "anisotropic_total_variation": "metrics",
    "rmse": "metrics",
    "r2_score_np": "metrics",
    "corr_np": "metrics",
    "mae": "metrics",
    "bias_np": "metrics",
    "nrmse_np": "metrics",
    "fit_slope_np": "metrics",
    "fit_intercept_np": "metrics",
    "WindowAttention3D": "models",
    "SwinBlock3D": "models",
    "SwinStage3D": "models",
    "PatchEmbed3D": "models",
    "PatchMerging3D": "models",
    "PatchExpand3D": "models",
    "ContextConditionedTwoLayerSwinUNet3D": "models",
    "ContextConditionedResidualSwinUNet3D": "models",
    "DualDecoderFrequencySeparatedSwinUNet3D": "models",
    "NoiseConditionedDualDecoderSwinUNet3D": "models",
    "PhysicsConfig": "physics",
    "build_elastic_kernel": "physics",
    "build_fft_kernels": "physics",
    "build_fft_kernels_numpy": "physics",
    "build_poroelastic_kernel": "physics",
    "fft_convolve2d": "physics",
    "fft_convolve2d_numpy": "physics",
    "forward_five_layer_components_numpy": "physics",
    "forward_five_layer_total_numpy": "physics",
    "forward_physics_torch": "physics",
    "forward_two_layer_torch": "physics",
    "set_seed": "physics",
    "PredictionArchive": "punjab_prediction_viewer",
    "PredictionArchiveSummary": "punjab_prediction_viewer",
    "build_baseline_prediction_archive": "punjab_prediction_viewer",
    "export_prediction_archive_to_netcdf": "punjab_prediction_viewer",
    "launch_notebook_prediction_viewer": "punjab_prediction_viewer",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f".{module_name}", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + __all__)
