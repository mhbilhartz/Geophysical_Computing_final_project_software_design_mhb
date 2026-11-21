"""2.5D point-electrode source-pair solver on an x/depth cell-centered mesh.

Conductivity is independent of y, but point-source current spreads in 3D.
The full Fourier transform is Vhat(k)=integral V(y)*exp(-iky) dy. At y=0,
V = Vprimary + integral_0^infinity Vhat_secondary(k) dk / pi.

This module does not calculate receiver voltages, geometric factors or rho_a.
It leaves the original fixed-side-voltage solver unchanged.
"""

from dataclasses import dataclass
from numbers import Integral
from time import perf_counter
import warnings

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.sparse import coo_matrix, diags
from scipy.sparse.linalg import MatrixRankWarning, spsolve
from scipy.special import k0, k1

from .electrodes import ElectrodeArray, _finite, _positive
from .solver import _harmonic, cell_centers


@dataclass(frozen=True)
class ModeDiagnostic:
    wavenumber_per_m: float
    relative_residual: float
    relative_balance_error: float


@dataclass(frozen=True)
class Solution25D:
    """Fields on y=0, with cell-center arrays shaped (nz,nx).

    Potentials are volts; jx/jz are cell-center A/m², positive right/down.
    Unlike the original Solution, these currents are NOT face-current arrays.
    Jy=0 on this symmetry plane, but its y derivative need not be zero.
    The finite fields do not include the singular surface electrode locations.
    """

    x: np.ndarray
    z: np.ndarray
    conductivity: np.ndarray
    potential: np.ndarray
    primary_potential: np.ndarray
    secondary_potential: np.ndarray
    jx: np.ndarray
    jz: np.ndarray
    dx: float
    dz: float
    background_conductivity: float
    electrodes: ElectrodeArray
    wavenumbers_per_m: np.ndarray
    integration_weights_per_m: np.ndarray
    mode_diagnostics: tuple[ModeDiagnostic, ...]
    elapsed_seconds: float

    @property
    def max_relative_mode_residual(self):
        return max(d.relative_residual for d in self.mode_diagnostics)

    @property
    def max_relative_mode_balance_error(self):
        return max(d.relative_balance_error for d in self.mode_diagnostics)


def log_wavenumber_quadrature(*, n_wavenumbers=64, k_min, k_max):
    """Gauss-Legendre integration in log(k), returning k and dk weights.

    The caller must study node count AND finite cutoff sensitivity. Positive
    nodes avoid K0's k=0 singularity; truncation is never silently corrected.
    """
    if (isinstance(n_wavenumbers, bool) or not isinstance(n_wavenumbers, Integral)
            or not 8 <= n_wavenumbers <= 512):
        raise ValueError('n_wavenumbers must be an integer between 8 and 512')
    lower = _positive(k_min, 'k_min')
    upper = _positive(k_max, 'k_max')
    if lower >= upper:
        raise ValueError('k_min must be smaller than k_max')
    nodes, weights = leggauss(n_wavenumbers)
    lo, hi = np.log(lower), np.log(upper)
    half = (hi-lo)/2
    k = np.exp((hi+lo)/2 + half*nodes)
    weights = weights*half*k  # dk = k d(log k).
    return k, weights


def _primary(x, z, electrodes, sigma0, *, k=None):
    """Exact half-space primary: physical V (k=None) or Vhat (V m)."""
    ra = np.hypot(x-electrodes.a_x_m, z)
    rb = np.hypot(x-electrodes.b_x_m, z)
    if np.any(ra == 0) or np.any(rb == 0):
        raise ValueError('Point-source potential is singular at an electrode')
    if k is None:
        return electrodes.current_a/(2*np.pi*sigma0)*(1/ra-1/rb)
    return electrodes.current_a/(np.pi*sigma0)*(k0(k*ra)-k0(k*rb))


def _assemble_operator(sigma, dx, dz):
    """Visible four-neighbor flux balance; top Neumann, other faces Dirichlet.

    Side/bottom Dirichlet values refer to SECONDARY potential (zero). The mass
    coefficient multiplies k². Matrix conductances have units S/m.
    """
    nz, nx = sigma.shape
    tx = _harmonic(sigma[:, :-1], sigma[:, 1:])*dz/dx
    tz = _harmonic(sigma[:-1, :], sigma[1:, :])*dx/dz
    left = 2*sigma[:, 0]*dz/dx
    right = 2*sigma[:, -1]*dz/dx
    bottom = 2*sigma[-1, :]*dx/dz
    if any(not np.all(np.isfinite(a)) or np.any(a <= 0)
           for a in (tx, tz, left, right, bottom)):
        raise ValueError('Face conductances exceed floating-point range')
    rows, cols, values = [], [], []
    for iz in range(nz):
        for ix in range(nx):
            p = iz*nx+ix
            diagonal = 0.0
            neighbors = []
            if ix > 0:
                neighbors.append((p-1, tx[iz, ix-1]))
            if ix < nx-1:
                neighbors.append((p+1, tx[iz, ix]))
            if iz > 0:
                neighbors.append((p-nx, tz[iz-1, ix]))
            if iz < nz-1:
                neighbors.append((p+nx, tz[iz, ix]))
            for neighbor, conductance in neighbors:
                rows.append(p); cols.append(neighbor); values.append(-conductance)
                diagonal += conductance
            if ix == 0:
                diagonal += left[iz]
            if ix == nx-1:
                diagonal += right[iz]
            if iz == nz-1:
                diagonal += bottom[ix]
            # The missing top face contributes no secondary normal current.
            rows.append(p); cols.append(p); values.append(diagonal)
    mass = sigma.ravel()*dx*dz
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(mass)) or np.any(mass <= 0):
        raise ValueError('Grid/conductivity coefficients exceed floating-point range')
    operator = coo_matrix((values, (rows, cols)), shape=(nx*nz,nx*nz)).tocsr()
    return operator, mass, (left, right, bottom)


def _primary_gradient_hat(x, z, electrodes, sigma0, k):
    """Analytical primary mode derivatives, away from surface sources."""
    da, db = x-electrodes.a_x_m, x-electrodes.b_x_m
    ra, rb = np.hypot(da,z), np.hypot(db,z)
    ca, cb = k*k1(k*ra)/ra, k*k1(k*rb)/rb
    factor = electrodes.current_a/(np.pi*sigma0)
    return factor*(-ca*da+cb*db), factor*(-ca*z+cb*z)


def _contrast_forcing(sigma, x, z, dx, dz, electrodes, sigma0, k):
    """Interface forcing with no spurious bulk source in uniform material.

    The primary satisfies Laplacian(Vp_hat)=k²*Vp_hat away from A/B.
    Thus A_sigma Vs_hat = grad(sigma) dot grad(Vp_hat). Integrating the
    primary identity over each cell cancels its bulk mass/flux terms BEFORE
    discretization. Harmonic face sigma then gives the interface contribution
    (sigma_face-sigma_cell)*outward primary derivative*face length.

    Differencing sampled primary potentials in (A0-A_sigma)Vp instead would
    leave an O(h²) bulk residual amplified by sigma0/sigma_tunnel in air.
    """
    rhs = np.zeros_like(sigma)
    face_x = (x[:-1]+x[1:])/2
    face_z = (z[:-1]+z[1:])/2
    gx, _ = _primary_gradient_hat(face_x[None,:],z[:,None],electrodes,sigma0,k)
    _, gz = _primary_gradient_hat(x[None,:],face_z[:,None],electrodes,sigma0,k)
    sx = _harmonic(sigma[:,:-1],sigma[:,1:])
    sz = _harmonic(sigma[:-1,:],sigma[1:,:])
    rhs[:,:-1] += (sx-sigma[:,:-1])*gx*dz
    rhs[:,1:] -= (sx-sigma[:,1:])*gx*dz
    rhs[:-1,:] += (sz-sigma[:-1,:])*gz*dx
    rhs[1:,:] -= (sz-sigma[1:,:])*gz*dx
    # Outer face sigma equals its cell sigma, so no contrast contribution.
    # At top sources sigma=sigma0; primary carries the injection exactly.
    return rhs.ravel()


def _secondary_gradient(secondary, dx, dz):
    """Cell-center gradients from ghost cells matching secondary boundaries."""
    padded = np.pad(secondary, 1, mode='edge')
    padded[1:-1, 0] = -secondary[:, 0]     # Zero value at the left face.
    padded[1:-1, -1] = -secondary[:, -1]
    padded[-1, 1:-1] = -secondary[-1, :]   # Zero value at the bottom face.
    padded[0, 1:-1] = secondary[0, :]      # Zero derivative at the top face.
    gx = (padded[1:-1, 2:]-padded[1:-1, :-2])/(2*dx)
    gz = (padded[2:, 1:-1]-padded[:-2, 1:-1])/(2*dz)
    return gx, gz


def solve_source_pair(
    conductivity, electrodes, *, width=100.0, height=50.0, x_origin_m=0.0,
    background_conductivity=None, n_wavenumbers=64, k_min=None, k_max=None,
):
    """Numerically solve a buried conductivity anomaly with surface point A/B.

    sigma[nz,nx] is S/m. The top cell row must be homogeneous sigma0, ensuring
    the source neighborhood is background material. sigma0 defaults to its first
    value. Side/bottom secondary potential is zero: total potential there equals
    the homogeneous primary, an approximation requiring domain sensitivity tests.

    Geometry includes M/N for domain validation, but only A/B drive this solve.
    No receiver sampling, rho_a, complete survey or GUI change is performed.
    """
    start = perf_counter()
    if not isinstance(electrodes, ElectrodeArray):
        raise ValueError('electrodes must be a Step 1 ElectrodeArray')
    if np.iscomplexobj(conductivity):
        raise ValueError('Conductivity must be real')
    sigma = np.array(conductivity, dtype=float, copy=True)
    if sigma.ndim != 2 or min(sigma.shape) < 2:
        raise ValueError('Conductivity must have shape (nz,nx), both >= 2')
    if not np.all(np.isfinite(sigma)) or np.any(sigma <= 0):
        raise ValueError('Every conductivity must be finite and positive')
    nz, nx = sigma.shape
    width = _positive(width, 'width')
    height = _positive(height, 'height')
    origin = _finite(x_origin_m, 'x_origin_m')
    right_edge = _finite(origin+width, 'right domain edge')
    x, z, dx, dz = cell_centers(width, height, nx, nz)
    x = x+origin
    if (not np.all(np.isfinite(x)) or not np.all(np.isfinite(z))
            or not np.all(np.diff(x) > 0) or not np.all(np.diff(z) > 0)):
        raise ValueError('Grid centers cannot be resolved at floating-point precision')
    electrodes.validate_domain(origin, right_edge)
    sigma0 = _positive(sigma[0, 0] if background_conductivity is None else background_conductivity,
                       'background_conductivity')
    if not np.allclose(sigma[0], sigma0, rtol=1e-12, atol=0):
        raise ValueError('The entire top row must equal background_conductivity; surface anomalies are not supported yet')
    ks, weights = log_wavenumber_quadrature(
        n_wavenumbers=n_wavenumbers,
        k_min=1e-6/max(width,height) if k_min is None else k_min,
        k_max=20/min(dx,dz) if k_max is None else k_max,
    )
    base, mass, boundaries = _assemble_operator(sigma, dx, dz)
    xx, zz = np.meshgrid(x,z)
    secondary = np.zeros_like(sigma)
    diagnostics = []
    tiny = np.finfo(float).tiny
    for k, weight in zip(ks,weights):
        rhs = _contrast_forcing(sigma,x,z,dx,dz,electrodes,sigma0,k)
        matrix = base+diags(k*k*mass)
        if not np.all(np.isfinite(rhs)) or not np.all(np.isfinite(matrix.data)):
            raise ValueError('Spectral system exceeds floating-point range')
        if np.any(rhs):
            with warnings.catch_warnings():
                warnings.simplefilter('error',MatrixRankWarning)
                try:
                    values = spsolve(matrix.tocsc(),rhs)
                except MatrixRankWarning as exc:
                    raise RuntimeError('Numerically singular Fourier-mode system') from exc
        else:
            values = np.zeros(nx*nz)
        if not np.all(np.isfinite(values)):
            raise RuntimeError('Non-finite Fourier-mode solution')
        residual = float(np.max(np.abs(matrix @ values-rhs))/max(np.max(np.abs(rhs)),tiny))
        mode = values.reshape(sigma.shape)
        outward = (np.sum(boundaries[0]*mode[:,0]) + np.sum(boundaries[1]*mode[:,-1])
                    + np.sum(boundaries[2]*mode[-1,:]))
        absorption = k*k*mass*values
        scale = max(float(np.sum(np.abs(rhs))), float(np.sum(np.abs(absorption))),
                    float(np.sum(np.abs(boundaries[0]*mode[:,0]))+
                          np.sum(np.abs(boundaries[1]*mode[:,-1]))+
                          np.sum(np.abs(boundaries[2]*mode[-1,:]))),tiny)
        balance = float(abs(outward+np.sum(absorption)-np.sum(rhs))/scale)
        if not np.isfinite(residual) or not np.isfinite(balance):
            raise RuntimeError('Non-finite Fourier-mode diagnostic')
        diagnostics.append(ModeDiagnostic(float(k),residual,balance))
        secondary += (weight/np.pi)*mode

    primary = _primary(xx,zz,electrodes,sigma0)
    gx, gz = _secondary_gradient(secondary,dx,dz)
    ra, rb = np.hypot(xx-electrodes.a_x_m,zz), np.hypot(xx-electrodes.b_x_m,zz)
    factor = electrodes.current_a/(2*np.pi*sigma0)
    gx_primary = factor*(-(xx-electrodes.a_x_m)/ra**3+(xx-electrodes.b_x_m)/rb**3)
    gz_primary = factor*(-zz/ra**3+zz/rb**3)
    potential = primary+secondary
    jx, jz = -sigma*(gx_primary+gx), -sigma*(gz_primary+gz)
    if not all(np.all(np.isfinite(a)) for a in (potential,jx,jz,secondary)):
        raise RuntimeError('Non-finite reconstructed potential or current')
    return Solution25D(x,z,sigma,potential,primary,secondary,jx,jz,dx,dz,sigma0,electrodes,
                       ks,weights,tuple(diagnostics),perf_counter()-start)
