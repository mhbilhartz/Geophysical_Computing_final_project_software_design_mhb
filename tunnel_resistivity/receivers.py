"""Surface receivers and signed apparent resistivity for the 2.5D backend.

No PDE solve or plotting occurs here. The analytical singular primary is sampled
at z=0; only the smooth secondary correction is interpolated from the mesh.
"""
from dataclasses import dataclass
import math

import numpy as np

from .electrodes import ElectrodeArray, _positive
from .solver_2p5d import Solution25D, _primary


@dataclass(frozen=True)
class ReceiverMeasurement:
    """One A/B/M/N datum, with voltage polarity V_M - V_N.

    Geometric factor is signed (meters), voltage is volts, current amperes,
    transfer resistance ohms, and apparent resistivity ohm meters. Negative
    modeled apparent resistivity is retained, rather than clipped or absoluted.
    """
    electrodes: ElectrodeArray
    potential_m_v: float
    potential_n_v: float
    primary_voltage_v: float
    secondary_voltage_v: float
    geometric_factor_m: float
    background_resistivity_ohm_m: float

    @property
    def voltage_v(self):
        # Preserve the secondary contribution before subtracting total potentials.
        return self.primary_voltage_v + self.secondary_voltage_v

    @property
    def transfer_resistance_ohm(self):
        return self.voltage_v / self.electrodes.current_a

    @property
    def apparent_resistivity_ohm_m(self):
        return self.geometric_factor_m * self.transfer_resistance_ohm

    @property
    def apparent_resistivity_anomaly_ohm_m(self):
        """K * secondary voltage / I; avoids subtracting two nearly equal rho's."""
        return self.geometric_factor_m * (self.secondary_voltage_v / self.electrodes.current_a)

    @property
    def relative_apparent_resistivity_anomaly(self):
        return self.apparent_resistivity_anomaly_ohm_m / self.background_resistivity_ohm_m


def geometric_factor(electrodes):
    """Signed K=2*pi/(1/AM - 1/BM - 1/AN + 1/BN) for flat half-space.

    A injects +I; B withdraws I; receiver voltage is V_M-V_N. Distances are
    absolute x separations in meters. Scaling and fsum reduce cancellation;
    nearly degenerate geometries are rejected instead of returning unstable K.
    """
    if not isinstance(electrodes, ElectrodeArray):
        raise ValueError('electrodes must be an ElectrodeArray')
    a,b,m,n = (electrodes.a_x_m,electrodes.b_x_m,electrodes.m_x_m,electrodes.n_x_m)
    distances = (abs(a-m),abs(b-m),abs(a-n),abs(b-n))
    scale = max(distances)
    terms = tuple(sign*scale/distance for sign,distance in zip((1,-1,-1,1),distances))
    if not all(math.isfinite(t) for t in terms):
        raise ValueError('Electrode distances exceed numerical range')
    denominator = math.fsum(terms)
    if abs(denominator) <= 64*np.finfo(float).eps*math.fsum(abs(t) for t in terms):
        raise ValueError('Numerically degenerate geometry: geometric factor is unresolved')
    factor = (2*math.pi/denominator)*scale
    if not math.isfinite(factor) or factor == 0:
        raise ValueError('Geometric factor exceeds numerical range')
    return factor


def _surface_components(solution, x_m):
    """Return primary and reconstructed secondary arrays at surface positions."""
    if not isinstance(solution, Solution25D):
        raise ValueError('Surface receivers require a Solution25D, not the fixed-voltage solution')
    if np.iscomplexobj(x_m):
        raise ValueError('Receiver positions must be real')
    try:
        if np.asarray(x_m).dtype.kind not in 'fiu':
            raise ValueError('Receiver positions must be real numbers')
        positions = np.asarray(x_m,dtype=float)
    except (ValueError,TypeError,OverflowError) as exc:
        raise ValueError('Receiver positions must be finite real meters') from exc
    if positions.ndim > 1 or positions.size == 0 or not np.all(np.isfinite(positions)):
        raise ValueError('Receiver positions must be a finite scalar or nonempty 1D array')
    dx = _positive(solution.dx,'solution.dx')
    dz = _positive(solution.dz,'solution.dz')
    sigma0 = _positive(solution.background_conductivity,'background conductivity')
    x,z,secondary = solution.x,solution.z,solution.secondary_potential
    sigma = solution.conductivity
    if (x.ndim != 1 or z.ndim != 1 or len(x)<2 or len(z)<2
            or secondary.shape != (len(z),len(x))
            or sigma.shape != secondary.shape
            or not np.all(np.isfinite(x)) or not np.all(np.isfinite(z))
            or not np.allclose(np.diff(x),dx,rtol=1e-7,atol=0)
            or not np.allclose(z[:2],[dz/2,1.5*dz],rtol=1e-12,atol=0)
            or not np.all(np.isfinite(secondary[:2]))
            or not np.all(np.isfinite(sigma[:2])) or np.any(sigma[:2]<=0)
            or not np.allclose(sigma[0],sigma0,rtol=1e-12,atol=0)):
        raise ValueError('Receiver sampling requires a finite uniform cell-centered 2.5D grid')
    left,right = x[0]-dx/2,x[-1]+dx/2
    if np.any(positions <= left) or np.any(positions >= right):
        raise ValueError('Receivers must lie strictly inside the artificial side boundaries')
    # Even quadratic through z=dz/2 and 3dz/2 satisfies dVs/dz=0 at the surface.
    # Vs(x,0) = (9 Vs(x,dz/2) - Vs(x,3dz/2))/8.
    surface = (9*secondary[0]-secondary[1])/8
    # Do not extrapolate a smooth quadratic through a material interface.
    # The top cell alone gives an O(dz²) zero-normal-gradient reconstruction.
    same_material = np.isclose(sigma[1],sigma0,rtol=1e-12,atol=0)
    surface = np.where(same_material,surface,secondary[0])
    # Explicit zero-secondary face values support the two half-cell edge strips.
    support_x = np.concatenate(([left],x,[right]))
    support_v = np.concatenate(([0.],surface,[0.]))
    correction = np.interp(positions,support_x,support_v)
    with np.errstate(over='ignore',divide='ignore',invalid='ignore'):
        primary = _primary(positions,0.,solution.electrodes,sigma0)
    if not np.all(np.isfinite(primary)) or not np.all(np.isfinite(correction)):
        raise ValueError('Surface receiver potential exceeds numerical range')
    return primary,correction


def sample_surface_potential(solution, x_m):
    """Physical V(x,y=0,z=0), in volts; scalar or 1D array matching x_m.

    Analytical primary plus quadratic-to-surface/linear-in-x secondary. A
    second-row material contrast uses the first-row zero-gradient estimate.
    Source locations, out-of-domain positions, and nonfinite input are rejected.
    No extrapolation beyond the artificial side faces is allowed.
    """
    primary,correction = _surface_components(solution,x_m)
    result = primary+correction
    if not np.all(np.isfinite(result)):
        raise ValueError('Total surface receiver potential exceeds numerical range')
    return float(result) if np.ndim(result)==0 else result


def measure_receivers(solution, *, electrodes=None):
    """Sample M/N, calculate delta V, transfer resistance, and signed rho_a.

    Defaults to the configuration used for the source-pair solve. Another
    configuration may reuse that field only when A, B, and I match exactly.
    Changing sources/current requires another forward solve. This accepts only
    the 2.5D source-pair result, never the original fixed-voltage model.
    """
    if not isinstance(solution,Solution25D):
        raise ValueError('Receiver measurements require a Solution25D')
    array = solution.electrodes if electrodes is None else electrodes
    factor = geometric_factor(array)
    for name in ('a_x_m','b_x_m','current_a'):
        if getattr(array,name) != getattr(solution.electrodes,name):
            raise ValueError('A, B, and current must match the solved source pair; rerun the solver')
    array.validate_domain(solution.x[0]-solution.dx/2,solution.x[-1]+solution.dx/2)
    primary,secondary = _surface_components(solution,[array.m_x_m,array.n_x_m])
    potentials = primary+secondary
    result = ReceiverMeasurement(array,float(potentials[0]),float(potentials[1]),
                                 float(primary[0]-primary[1]),float(secondary[0]-secondary[1]),
                                 factor,1/solution.background_conductivity)
    values = (result.potential_m_v,result.potential_n_v,result.voltage_v,
              result.transfer_resistance_ohm,result.apparent_resistivity_ohm_m,
              result.background_resistivity_ohm_m,result.apparent_resistivity_anomaly_ohm_m,
              result.relative_apparent_resistivity_anomaly)
    if not all(math.isfinite(value) for value in values):
        raise ValueError('Receiver measurement exceeds numerical range')
    return result
