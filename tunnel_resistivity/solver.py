"""Conservative finite differences for div(sigma grad(V)) = 0.

Coordinates are x (rightward), z (downward), in meters. Arrays use [iz, ix].
Currents assume unit thickness in the unmodeled third dimension.
"""

from dataclasses import dataclass, replace
from numbers import Integral
import warnings

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import MatrixRankWarning, spsolve


@dataclass(frozen=True)
class Solution:
    """Potential at cell centers and current density at cell faces.

    potential: (nz, nx) in V; jx: (nz, nx+1), jz: (nz+1, nx) in A/m².
    Face current is positive rightward/downward. x and z are cell centers.
    conductivity is a scalar for solve_homogeneous, an array otherwise.
    """

    x: np.ndarray
    z: np.ndarray
    potential: np.ndarray
    jx: np.ndarray
    jz: np.ndarray
    dx: float
    dz: float
    conductivity: float | np.ndarray
    left_potential: float
    right_potential: float
    residual_inf: float


def cell_centers(width, height, nx, nz):
    """Validate a rectangular grid and return x, z, dx, dz (meters)."""
    for name, count in (("nx", nx), ("nz", nz)):
        if isinstance(count, bool) or not isinstance(count, Integral) or count < 2:
            raise ValueError(f"{name} must be an integer >= 2")
    for name, value in (("width", width), ("height", height)):
        if not np.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    dx, dz = width / nx, height / nz
    if not np.isfinite(dx) or not np.isfinite(dz) or min(dx, dz) <= 0:
        raise ValueError("Cell dimensions must be representable and positive")
    return (np.arange(nx) + 0.5) * dx, (np.arange(nz) + 0.5) * dz, dx, dz


def solve_homogeneous(
    *, width: float = 100.0, height: float = 50.0,
    nx: int = 80, nz: int = 40, conductivity: float = 0.01,
    left_potential: float = 1.0, right_potential: float = 0.0,
) -> Solution:
    """Original homogeneous API, now sharing the variable-conductivity assembly.

    Dimensions are in meters, conductivity in S/m, potentials in volts.
    Resistivity (ohm m) is 1/conductivity. nx and nz count cells.
    """
    cell_centers(width, height, nx, nz)
    if np.ndim(conductivity) != 0 or not np.isfinite(conductivity) or conductivity <= 0:
        raise ValueError("conductivity must be a finite positive scalar")
    result = solve_conductivity(
        np.full((nz, nx), conductivity, dtype=float), width=width, height=height,
        left_potential=left_potential, right_potential=right_potential,
    )
    # Preserve the original scalar conductivity attribute for existing callers.
    return replace(result, conductivity=float(conductivity))


def _harmonic(a, b):
    """Equal half-cell resistances in series; avoids the product a*b."""
    low, high = np.minimum(a, b), np.maximum(a, b)
    return low / (0.5 + 0.5 * (low / high))


def solve_conductivity(
    conductivity: np.ndarray, *, width: float = 100.0, height: float = 50.0,
    left_potential: float = 1.0, right_potential: float = 0.0,
) -> Solution:
    """Solve with a positive finite (nz, nx) cell-conductivity array, in S/m.

    Left/right faces have fixed potentials; top/bottom have zero normal current.
    Conductivity is piecewise constant within cells. Shared interior faces use
    harmonic averages, and boundary faces use the adjacent cell conductivity.
    """
    sigma = np.array(conductivity, dtype=float, copy=True)
    if sigma.ndim != 2 or min(sigma.shape) < 2:
        raise ValueError("conductivity must have shape (nz, nx), both >= 2")
    if not np.all(np.isfinite(sigma)) or np.any(sigma <= 0):
        raise ValueError("Every conductivity must be finite and positive")
    nz, nx = sigma.shape
    x, z, dx, dz = cell_centers(width, height, nx, nz)
    if not np.isfinite(left_potential) or not np.isfinite(right_potential):
        raise ValueError("Boundary potentials must be finite")

    # One conductivity per shared face, used by BOTH neighboring cells.
    sx = _harmonic(sigma[:, :-1], sigma[:, 1:])
    sz = _harmonic(sigma[:-1, :], sigma[1:, :])
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        tx = sx * (dz / dx)
        tz = sz * (dx / dz)
        left_t = sigma[:, 0] * (2 * dz / dx)
        right_t = sigma[:, -1] * (2 * dz / dx)
    for coefficient in (tx, tz, left_t, right_t):
        if not np.all(np.isfinite(coefficient)) or np.any(coefficient <= 0):
            raise ValueError("Conductance is outside floating-point range")
    rows, cols, data = [], [], []
    rhs = np.zeros(nx * nz)

    for iz in range(nz):
        for ix in range(nx):
            p = iz * nx + ix
            diagonal = 0.0
            # For each connected neighbor N, add T * (V_P - V_N).
            neighbors = []
            if ix > 0:
                neighbors.append((p - 1, tx[iz, ix - 1]))
            if ix < nx - 1:
                neighbors.append((p + 1, tx[iz, ix]))
            if iz > 0:
                neighbors.append((p - nx, tz[iz - 1, ix]))
            if iz < nz - 1:
                neighbors.append((p + nx, tz[iz, ix]))
            for neighbor, conductance in neighbors:
                rows.append(p)
                cols.append(neighbor)
                data.append(-conductance)
                diagonal += conductance

            # Side boundaries are dx/2 from the adjacent cell centers.
            # Use local boundary conductance; move the known voltage to rhs.
            if ix == 0:
                diagonal += left_t[iz]
                rhs[p] += left_t[iz] * left_potential
            if ix == nx - 1:
                diagonal += right_t[iz]
                rhs[p] += right_t[iz] * right_potential
            # Missing top/bottom neighbors contribute zero normal flux.
            # They are NOT fixed at zero potential.
            rows.append(p)
            cols.append(p)
            data.append(diagonal)

    if not np.all(np.isfinite(data)) or not np.all(np.isfinite(rhs)):
        raise ValueError("System coefficients are outside floating-point range")
    matrix = coo_matrix((data, (rows, cols)), shape=(nx * nz, nx * nz)).tocsr()
    with warnings.catch_warnings():
        warnings.simplefilter("error", MatrixRankWarning)
        try:
            values = spsolve(matrix, rhs)
        except MatrixRankWarning as exc:
            raise RuntimeError("Numerically singular system; reduce conductivity contrast") from exc
    if not np.all(np.isfinite(values)):
        raise RuntimeError("Sparse solve returned non-finite potentials")
    potential = values.reshape(nz, nx)
    residual_inf = float(np.max(np.abs(matrix @ values - rhs)))

    # J = -sigma grad(V), with the same distances as matrix assembly.
    jx = np.empty((nz, nx + 1))
    jx[:, 1:-1] = -sx * np.diff(potential, axis=1) / dx
    jx[:, 0] = -sigma[:, 0] * (potential[:, 0] - left_potential) / (dx / 2)
    jx[:, -1] = -sigma[:, -1] * (right_potential - potential[:, -1]) / (dx / 2)
    jz = np.zeros((nz + 1, nx))  # Boundary faces stay exactly insulating.
    jz[1:-1, :] = -sz * np.diff(potential, axis=0) / dz
    if not np.isfinite(residual_inf) or not np.all(np.isfinite(jx)) or not np.all(np.isfinite(jz)):
        raise RuntimeError("Non-finite flux or residual; check parameter scales")
    return Solution(x, z, potential, jx, jz, dx, dz, sigma,
                    left_potential, right_potential, residual_inf)
