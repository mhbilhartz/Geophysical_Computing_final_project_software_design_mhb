"""Collinear surface electrode geometry, independent of the PDE solver and UI.

A injects +I, B withdraws I, and receiver voltage is V_M - V_N. Coordinates
are meters along x; every electrode is at cross-line y=0 and surface depth z=0.
Array center means the midpoint of the FULL electrode spread for all arrays.
No potentials, geometric factors, or apparent resistivities are computed here.
"""

from dataclasses import dataclass
import math
from numbers import Integral, Real


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f'{name} must be a finite real number')
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f'{name} must be representable as a finite number') from exc
    if not math.isfinite(result):
        raise ValueError(f'{name} must be finite')
    return result


def _positive(value, name):
    result = _finite(value, name)
    if result <= 0:
        raise ValueError(f'{name} must be positive')
    return result


def _equal(a, b):
    # Relative tolerance accommodates ordinary coordinate rounding, without
    # treating two tiny but substantially different spacings as equal.
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=0.0)


@dataclass(frozen=True)
class ElectrodeArray:
    """One four-electrode measurement; use the named factories below.

    Named-array ordering and spacing are validated even on direct construction.
    Positive current amplitude fixes A as source and B as return. A negative
    receiver voltage is legitimate; polarity must remain consistent when the
    later apparent-resistivity calculation is implemented.
    """

    array_type: str
    a_x_m: float
    b_x_m: float
    m_x_m: float
    n_x_m: float
    current_a: float = 1.0

    def __post_init__(self):
        if self.array_type not in ('wenner', 'schlumberger', 'dipole-dipole'):
            raise ValueError('array_type must be wenner, schlumberger, or dipole-dipole')
        for name in ('a_x_m', 'b_x_m', 'm_x_m', 'n_x_m'):
            object.__setattr__(self, name, _finite(getattr(self, name), name))
        object.__setattr__(self, 'current_a', _positive(self.current_a, 'current_a (A)'))
        xs = tuple(self.positions_x_m.values())
        if len(set(xs)) != 4:
            raise ValueError('All four electrodes must be distinct; spacing may be below floating-point resolution')
        if not math.isfinite(max(xs)-min(xs)):
            raise ValueError('Electrode spread exceeds floating-point range')
        a, b, m, n = self.a_x_m, self.b_x_m, self.m_x_m, self.n_x_m
        if self.array_type in ('wenner', 'schlumberger'):
            if not a < m < n < b:
                raise ValueError('Wenner/Schlumberger ordering must be A < M < N < B')
            if self.array_type == 'wenner':
                if not (_equal(m-a, n-m) and _equal(n-m, b-n)):
                    raise ValueError('Wenner adjacent spacings must be equal')
            elif not _equal(m-a, b-n):
                raise ValueError('Schlumberger source and receiver pairs must share a center')
        else:
            if not a < b < m < n:
                raise ValueError('Dipole-dipole ordering must be A < B < M < N')
            if not _equal(b-a, n-m):
                raise ValueError('Source and receiver dipoles must have equal lengths')
            ratio = (m-b)/(b-a)
            if not math.isfinite(ratio) or round(ratio) < 1 or not _equal(ratio, round(ratio)):
                raise ValueError('Dipole separation B-to-M must be an integer n >= 1 times the dipole length')

    @property
    def positions_x_m(self):
        """Positions in label order A, B, M, N (NOT spatial order)."""
        return {'A': self.a_x_m, 'B': self.b_x_m, 'M': self.m_x_m, 'N': self.n_x_m}

    @property
    def source_currents_a(self):
        """Balanced source/return amplitudes, in amperes; not yet PDE sources."""
        return {'A': self.current_a, 'B': -self.current_a}

    @property
    def span_m(self):
        xs = self.positions_x_m.values()
        return max(xs)-min(xs)

    @property
    def center_x_m(self):
        xs = tuple(self.positions_x_m.values())
        return min(xs)/2 + max(xs)/2

    def validate_domain(self, x_min_m, x_max_m, *, boundary_padding_m=0.0):
        """Require all electrodes strictly inside the artificial side boundaries.

        Optional padding is a minimum distance to either side (equality allowed
        for positive padding). This is a geometry check, not a demonstration
        that the chosen padding is sufficient to remove boundary effects.
        """
        lower = _finite(x_min_m, 'x_min_m')
        upper = _finite(x_max_m, 'x_max_m')
        padding = _finite(boundary_padding_m, 'boundary_padding_m')
        if lower >= upper or not math.isfinite(upper-lower):
            raise ValueError('Domain must have a finite positive width')
        if padding < 0:
            raise ValueError('boundary_padding_m must be nonnegative')
        left = min(self.positions_x_m.values())
        right = max(self.positions_x_m.values())
        if not lower < left < right < upper:
            raise ValueError('Every electrode must lie strictly inside the domain sides')
        if left-lower < padding or upper-right < padding:
            raise ValueError('Electrode spread violates the requested side-boundary padding')


def wenner(*, center_x_m, spacing_m, current_a=1.0):
    """Spatial order A M N B, adjacent spacing a; full spread is 3a."""
    c = _finite(center_x_m, 'center_x_m')
    a = _positive(spacing_m, 'spacing_m')
    return ElectrodeArray('wenner', c-1.5*a, c+1.5*a, c-0.5*a, c+0.5*a, current_a)


def schlumberger(*, center_x_m, ab_half_spacing_m, mn_half_spacing_m, current_a=1.0):
    """Spatial order A M N B, with common midpoint; require 0 < MN/2 < AB/2.

    Small MN relative to AB is the usual survey choice; no additional arbitrary
    AB/MN ratio is imposed by this geometry module.
    """
    c = _finite(center_x_m, 'center_x_m')
    ab = _positive(ab_half_spacing_m, 'ab_half_spacing_m')
    mn = _positive(mn_half_spacing_m, 'mn_half_spacing_m')
    if mn >= ab:
        raise ValueError('mn_half_spacing_m must be smaller than ab_half_spacing_m')
    return ElectrodeArray('schlumberger', c-ab, c+ab, c-mn, c+mn, current_a)


def dipole_dipole(*, center_x_m, spacing_m, separation_n=1, current_a=1.0):
    """Spatial order A B M N; AB=MN=a, B-to-M gap=n*a, full spread=(n+2)*a.

    n is a positive integer. Center is the full spread midpoint, not the source
    dipole midpoint. Receiver polarity is always V_M - V_N, without a sign flip.
    """
    c = _finite(center_x_m, 'center_x_m')
    a = _positive(spacing_m, 'spacing_m')
    if isinstance(separation_n, bool) or not isinstance(separation_n, Integral) or separation_n < 1:
        raise ValueError('separation_n must be an integer >= 1')
    _positive(separation_n, 'separation_n')
    try:
        span = (int(separation_n)+2)*a
    except OverflowError as exc:
        raise ValueError('Electrode spread exceeds floating-point range') from exc
    left = c-span/2
    return ElectrodeArray('dipole-dipole', left, left+a, c+span/2-a, c+span/2, current_a)
