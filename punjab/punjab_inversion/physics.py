from dataclasses import dataclass
import random

import numpy as np
import torch


@dataclass(frozen=True)
class PhysicsConfig:
    E: float = 1e9
    nu: float = 0.25
    rho_w: float = 1000.0
    g: float = 9.81
    alpha: float = 0.8
    Hg: float = 150.0
    Seff: float = 0.2
    dx: float = 10000.0
    dy: float = 10000.0
    a_load: float = 3000.0
    a_poro: float = 3000.0


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def build_elastic_kernel(E: float, nu: float, dx: float, dy: float, a: float, nx: int, ny: int) -> np.ndarray:
    xgrid = (np.arange(nx) - nx / 2) * dx
    ygrid = (np.arange(ny) - ny / 2) * dy
    xx, yy = np.meshgrid(xgrid, ygrid)
    r = np.sqrt(xx ** 2 + yy ** 2)
    r[r < 1e-6] = 1e-6
    return (1 + nu) / (np.pi * E * (1 - nu)) * (1 - np.exp(-r / a)) / r


def build_poroelastic_kernel(
    E: float,
    nu: float,
    alpha: float,
    hg: float,
    dx: float,
    dy: float,
    a: float,
    nx: int,
    ny: int,
) -> np.ndarray:
    xgrid = (np.arange(nx) - nx / 2) * dx
    ygrid = (np.arange(ny) - ny / 2) * dy
    xx, yy = np.meshgrid(xgrid, ygrid)
    r = np.sqrt(xx ** 2 + yy ** 2)
    r[r < 1e-6] = 1e-6
    factor = alpha * (1 + nu) * hg * 9.81 / (np.pi * E * (1 - nu))
    return factor * (1 - np.exp(-r / a)) / r


def build_fft_kernels(ny: int, nx: int, physics: PhysicsConfig, device: str | torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    g_load = build_elastic_kernel(physics.E, physics.nu, physics.dx, physics.dy, physics.a_load, nx, ny)
    g_poro = build_poroelastic_kernel(
        physics.E,
        physics.nu,
        physics.alpha,
        physics.Hg,
        physics.dx,
        physics.dy,
        physics.a_poro,
        nx,
        ny,
    )
    g_load_fft = torch.fft.fft2(torch.fft.ifftshift(torch.tensor(g_load, dtype=torch.float32, device=device)))
    g_poro_fft = torch.fft.fft2(torch.fft.ifftshift(torch.tensor(g_poro, dtype=torch.float32, device=device)))
    return g_load_fft, g_poro_fft


def build_fft_kernels_numpy(ny: int, nx: int, physics: PhysicsConfig) -> tuple[np.ndarray, np.ndarray]:
    g_load = build_elastic_kernel(physics.E, physics.nu, physics.dx, physics.dy, physics.a_load, nx, ny)
    g_poro = build_poroelastic_kernel(
        physics.E,
        physics.nu,
        physics.alpha,
        physics.Hg,
        physics.dx,
        physics.dy,
        physics.a_poro,
        nx,
        ny,
    )
    g_load_fft = np.fft.fft2(np.fft.ifftshift(g_load))
    g_poro_fft = np.fft.fft2(np.fft.ifftshift(g_poro))
    return g_load_fft, g_poro_fft


def fft_convolve2d(field: torch.Tensor, kernel_fft: torch.Tensor) -> torch.Tensor:
    return torch.fft.ifft2(torch.fft.fft2(field) * kernel_fft).real


def fft_convolve2d_numpy(field: np.ndarray, kernel_fft: np.ndarray) -> np.ndarray:
    return np.fft.ifft2(np.fft.fft2(field) * kernel_fft).real.astype(np.float32)


def forward_physics_torch(
    y_pred: torch.Tensor,
    g_load_fft: torch.Tensor,
    g_poro_fft: torch.Tensor,
    physics: PhysicsConfig,
    sg_index: int = 3,
    load_indices: tuple[int, ...] | None = None,
) -> torch.Tensor:
    if load_indices is None:
        load_indices = tuple(i for i in range(y_pred.shape[1]) if i != sg_index)
    delta_l = physics.rho_w * y_pred[:, list(load_indices)].sum(dim=1)
    delta_p = physics.rho_w * physics.g * (y_pred[:, sg_index] / physics.Seff)
    uz_load = fft_convolve2d(delta_l, g_load_fft)
    uz_poro = fft_convolve2d(delta_p, g_poro_fft)
    return (uz_load + uz_poro).unsqueeze(1)


def forward_two_layer_torch(
    y_pred: torch.Tensor,
    g_load_fft: torch.Tensor,
    g_poro_fft: torch.Tensor,
    physics: PhysicsConfig,
) -> torch.Tensor:
    delta_l = physics.rho_w * y_pred[:, 0]
    delta_p = physics.rho_w * physics.g * (y_pred[:, 1] / physics.Seff)
    uz_load = fft_convolve2d(delta_l, g_load_fft)
    uz_poro = fft_convolve2d(delta_p, g_poro_fft)
    return (uz_load + uz_poro).unsqueeze(1)


def forward_five_layer_components_numpy(
    layers: np.ndarray,
    physics: PhysicsConfig,
    sg_index: int = 3,
    load_indices: tuple[int, ...] = (0, 1, 2, 4),
) -> np.ndarray:
    """Convert a 5-layer storage cube into layerwise deformation contributions.

    Parameters
    ----------
    layers
        Array with shape ``(T, K, H, W)``.
    physics
        Physics constants for the elastic and poroelastic kernels.
    sg_index
        Index of the groundwater / poroelastic layer.
    load_indices
        Indices treated as elastic loading layers.

    Returns
    -------
    np.ndarray
        Array with shape ``(T, K, H, W)`` containing each layer's deformation
        contribution before summation.
    """

    if layers.ndim != 4:
        raise ValueError(f"Expected layers with shape (T,K,H,W), got {layers.shape}.")

    t_steps, n_layers, ny, nx = layers.shape
    if sg_index < 0 or sg_index >= n_layers:
        raise ValueError(f"sg_index={sg_index} is invalid for K={n_layers}.")

    g_load_fft, g_poro_fft = build_fft_kernels_numpy(ny, nx, physics)
    components = np.zeros_like(layers, dtype=np.float32)

    for t in range(t_steps):
        for k in range(n_layers):
            field = layers[t, k].astype(np.float32)
            if k == sg_index:
                delta = physics.rho_w * physics.g * (field / physics.Seff)
                components[t, k] = fft_convolve2d_numpy(delta, g_poro_fft)
            elif k in load_indices:
                delta = physics.rho_w * field
                components[t, k] = fft_convolve2d_numpy(delta, g_load_fft)
            else:
                components[t, k] = 0.0

    return components


def forward_five_layer_total_numpy(
    layers: np.ndarray,
    physics: PhysicsConfig,
    sg_index: int = 3,
    load_indices: tuple[int, ...] = (0, 1, 2, 4),
) -> np.ndarray:
    return forward_five_layer_components_numpy(
        layers,
        physics=physics,
        sg_index=sg_index,
        load_indices=load_indices,
    ).sum(axis=1)
