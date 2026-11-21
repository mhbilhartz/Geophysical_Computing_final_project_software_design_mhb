"""Surface survey planning and forward orchestration; no PDE assembly or UI.

All electrode indices are zero-based and stored in A, B, M, N label order.
Only source fields within this one fixed-model run are reused. Scalar data are
retained; the large field arrays are discarded after each source group.
"""
from dataclasses import dataclass
import csv
import hashlib
from numbers import Integral
from pathlib import Path
from time import perf_counter

import numpy as np

from .electrodes import ElectrodeArray, _finite, _positive
from .receivers import ReceiverMeasurement, geometric_factor, measure_receivers
from .solver_2p5d import solve_source_pair


class SurveyCancelled(RuntimeError):
    """A caller cancelled between source solves; no partial result is returned."""


def _integer(value, name, minimum=1):
    if isinstance(value,bool) or not isinstance(value,Integral) or value<minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}')
    return int(value)


def _source_key(array):
    return array.a_x_m,array.b_x_m,array.current_a


@dataclass(frozen=True)
class SurveyMeasurement:
    level: int
    electrode_indices: tuple[int,int,int,int]  # A, B, M, N.
    electrodes: ElectrodeArray

    def __post_init__(self):
        object.__setattr__(self,'level',_integer(self.level,'level'))
        indices=tuple(_integer(i,'electrode index',0) for i in self.electrode_indices)
        if len(indices)!=4 or len(set(indices))!=4:
            raise ValueError('Exactly four distinct A/B/M/N electrode indices are required')
        if not isinstance(self.electrodes,ElectrodeArray):
            raise ValueError('electrodes must be an ElectrodeArray')
        object.__setattr__(self,'electrode_indices',indices)


@dataclass(frozen=True)
class Survey:
    electrode_positions_x_m: tuple[float,...]
    measurements: tuple[SurveyMeasurement,...]

    def __post_init__(self):
        positions=tuple(_finite(x,'electrode position') for x in self.electrode_positions_x_m)
        measurements=tuple(self.measurements)
        if len(positions)<4 or any(a>=b for a,b in zip(positions,positions[1:])):
            raise ValueError('A survey requires at least four strictly increasing electrode positions')
        if not measurements:
            raise ValueError('A survey requires at least one measurement')
        for entry in measurements:
            if not isinstance(entry,SurveyMeasurement):
                raise ValueError('Each entry must be a SurveyMeasurement')
            if max(entry.electrode_indices)>=len(positions):
                raise ValueError('Measurement index lies outside the physical electrode line')
            for index,coordinate in zip(entry.electrode_indices,entry.electrodes.positions_x_m.values()):
                if positions[index]!=coordinate:
                    raise ValueError('Measurement coordinates must match the indexed physical electrodes')
        object.__setattr__(self,'electrode_positions_x_m',positions)
        object.__setattr__(self,'measurements',measurements)

    @property
    def unique_source_pair_count(self):
        return len({_source_key(entry.electrodes) for entry in self.measurements})

    def validate_domain(self,x_min_m,x_max_m,*,boundary_padding_m=0.):
        lower=_finite(x_min_m,'x_min_m');upper=_finite(x_max_m,'x_max_m')
        padding=_finite(boundary_padding_m,'boundary_padding_m')
        if lower>=upper or not np.isfinite(upper-lower) or padding<0:
            raise ValueError('Domain width must be finite/positive and padding nonnegative')
        left,right=self.electrode_positions_x_m[0],self.electrode_positions_x_m[-1]
        if not lower<left<right<upper:
            raise ValueError('The entire physical electrode line must lie strictly inside the domain')
        if min(left-lower,upper-right)<padding:
            raise ValueError('Physical electrode line violates the requested boundary padding')


def generate_survey(array_type,*,electrode_count=9,electrode_spacing_m=5.,
                    line_start_x_m=30.,levels=(1,2),current_a=1.,
                    receiver_spacing_steps=1,dipole_spacing_steps=1):
    """Generate every valid translation at each requested level on a fixed line.

    Uniform line spacing is p. Level l means:
    Wenner: a=l*p; indices A=i, M=i+l, N=i+2l, B=i+3l.
    Schlumberger: A-M=N-B=l*p; MN=receiver_spacing_steps*p.
    Dipole-dipole: n=l; AB=MN=dipole_spacing_steps*p; B-M=n*AB.
    Every requested level must fit the line; oversized levels are rejected.
    Output order is requested level order, then increasing left electrode index.
    """
    if array_type not in ('wenner','schlumberger','dipole-dipole'):
        raise ValueError('array_type must be wenner, schlumberger, or dipole-dipole')
    count=_integer(electrode_count,'electrode_count',4)
    if count>1001:
        raise ValueError('This project supports at most 1001 physical electrodes per line')
    pitch=_positive(electrode_spacing_m,'electrode_spacing_m')
    start=_finite(line_start_x_m,'line_start_x_m')
    current=_positive(current_a,'current_a')
    receiver_steps=_integer(receiver_spacing_steps,'receiver_spacing_steps')
    dipole_steps=_integer(dipole_spacing_steps,'dipole_spacing_steps')
    if array_type!='schlumberger' and receiver_steps!=1:
        raise ValueError('receiver_spacing_steps applies only to Schlumberger')
    if array_type!='dipole-dipole' and dipole_steps!=1:
        raise ValueError('dipole_spacing_steps applies only to dipole-dipole')
    try:
        requested=tuple(_integer(level,'level') for level in levels)
    except TypeError as exc:
        raise ValueError('levels must be a nonempty iterable of positive integers') from exc
    if not requested or len(set(requested))!=len(requested):
        raise ValueError('levels must be nonempty and contain no duplicates')
    offsets=[]
    for level in requested:
        if array_type=='wenner':
            a,b,m,n=0,3*level,level,2*level
        elif array_type=='schlumberger':
            a,b,m,n=0,2*level+receiver_steps,level,level+receiver_steps
        else:
            a,b,m,n=0,dipole_steps,(level+1)*dipole_steps,(level+2)*dipole_steps
        if max(a,b,m,n)>=count:
            raise ValueError(f'Level {level} requires {max(a,b,m,n)+1} electrodes; line has {count}')
        offsets.append((level,(a,b,m,n)))
    positions=tuple(_finite(start+i*pitch,'electrode position') for i in range(count))
    entries=[]
    for level,indices in offsets:
        for first in range(count-max(indices)):
            shifted=tuple(first+index for index in indices)
            # All source coordinates come from the same physical line. This also
            # gives identical floating-point A/B keys across receiver configurations.
            array=ElectrodeArray(array_type,*(positions[index] for index in shifted),current)
            geometric_factor(array)  # Reject unresolved geometry during planning.
            entries.append(SurveyMeasurement(level,shifted,array))
    return Survey(positions,tuple(entries))


@dataclass(frozen=True)
class SourcePairDiagnostic:
    source_pair_id: int
    a_x_m: float
    b_x_m: float
    current_a: float
    measurement_count: int
    max_relative_mode_residual: float
    max_relative_mode_balance_error: float
    elapsed_seconds: float


@dataclass(frozen=True)
class SurveyResult:
    survey: Survey
    measurements: tuple[ReceiverMeasurement,...]
    source_diagnostics: tuple[SourcePairDiagnostic,...]
    width_m: float
    height_m: float
    x_origin_m: float
    nx: int
    nz: int
    background_conductivity: float
    n_wavenumbers: int
    k_min_per_m: float
    k_max_per_m: float
    conductivity_sha256: str
    elapsed_seconds: float

    @property
    def solve_count(self):
        return len(self.source_diagnostics)

    @property
    def max_relative_mode_residual(self):
        return max(d.max_relative_mode_residual for d in self.source_diagnostics)

    @property
    def max_relative_mode_balance_error(self):
        return max(d.max_relative_mode_balance_error for d in self.source_diagnostics)

    def records(self):
        """One ordered, unit-labeled flat record per planned measurement."""
        sources={(d.a_x_m,d.b_x_m,d.current_a):d for d in self.source_diagnostics}
        rows=[]
        for measurement_id,(planned,datum) in enumerate(zip(self.survey.measurements,self.measurements),1):
            array=planned.electrodes;source=sources[_source_key(array)]
            row=dict(measurement_id=measurement_id,array_type=array.array_type,level=planned.level,
                     spread_center_x_m=array.center_x_m,spread_m=array.span_m,
                     source_pair_id=source.source_pair_id,current_a=array.current_a)
            row.update({f'{label.lower()}_index':index for label,index in zip('ABMN',planned.electrode_indices)})
            row.update({f'{label.lower()}_x_m':x for label,x in array.positions_x_m.items()})
            row.update(potential_m_v=datum.potential_m_v,potential_n_v=datum.potential_n_v,
                       voltage_v=datum.voltage_v,primary_voltage_v=datum.primary_voltage_v,
                       secondary_voltage_v=datum.secondary_voltage_v,geometric_factor_m=datum.geometric_factor_m,
                       transfer_resistance_ohm=datum.transfer_resistance_ohm,
                       background_resistivity_ohm_m=datum.background_resistivity_ohm_m,
                       apparent_resistivity_ohm_m=datum.apparent_resistivity_ohm_m,
                       apparent_resistivity_anomaly_ohm_m=datum.apparent_resistivity_anomaly_ohm_m,
                       relative_apparent_resistivity_anomaly=datum.relative_apparent_resistivity_anomaly,
                       max_relative_mode_residual=source.max_relative_mode_residual,
                       max_relative_mode_balance_error=source.max_relative_mode_balance_error,
                       width_m=self.width_m,height_m=self.height_m,x_origin_m=self.x_origin_m,nx=self.nx,nz=self.nz,
                       n_wavenumbers=self.n_wavenumbers,k_min_per_m=self.k_min_per_m,k_max_per_m=self.k_max_per_m,
                       conductivity_sha256=self.conductivity_sha256)
            rows.append(row)
        return rows


def forward_survey(conductivity,survey,*,width=100.,height=50.,x_origin_m=0.,
                   background_conductivity=None,n_wavenumbers=64,k_min=None,k_max=None,
                   boundary_padding_m=0.,cancelled=None,progress=None):
    """Run one fixed conductivity snapshot using the Step 2/3 production code.

    All geometry/factors are checked before any PDE solve. Group by exact A/B/I;
    measure all matching receivers, then discard that field. No persistent field
    cache exists, and results remain in the original plan order. Any failure
    raises an exception without returning an incomplete survey result.
    Optional cancelled() and progress(completed_sources,total_sources) support
    live callers. A running sparse source solve finishes before cancellation.
    """
    start=perf_counter()
    if cancelled is not None and not callable(cancelled):raise ValueError('cancelled must be callable')
    if progress is not None and not callable(progress):raise ValueError('progress must be callable')
    def check_cancelled():
        if cancelled is not None and cancelled():raise SurveyCancelled('Survey superseded or session closed')
    check_cancelled()
    if not isinstance(survey,Survey):raise ValueError('survey must be a Survey')
    width=_positive(width,'width');height=_positive(height,'height')
    origin=_finite(x_origin_m,'x_origin_m');right=_finite(origin+width,'right domain edge')
    survey.validate_domain(origin,right,boundary_padding_m=boundary_padding_m)
    for entry in survey.measurements:geometric_factor(entry.electrodes)
    if np.iscomplexobj(conductivity):raise ValueError('Conductivity must be real')
    sigma=np.array(conductivity,dtype=float,copy=True)
    if sigma.ndim!=2 or min(sigma.shape)<2 or not np.all(np.isfinite(sigma)) or np.any(sigma<=0):
        raise ValueError('Conductivity must be a positive finite 2D array, both dimensions >=2')
    groups={}
    for index,entry in enumerate(survey.measurements):
        groups.setdefault(_source_key(entry.electrodes),[]).append(index)
    data=[None]*len(survey.measurements);diagnostics=[]
    if progress is not None:progress(0,len(groups))
    for source_id,indices in enumerate(groups.values(),1):
        check_cancelled()
        source=survey.measurements[indices[0]].electrodes
        model=solve_source_pair(sigma,source,width=width,height=height,x_origin_m=origin,
                                background_conductivity=background_conductivity,
                                n_wavenumbers=n_wavenumbers,k_min=k_min,k_max=k_max)
        check_cancelled()
        for index in indices:
            data[index]=measure_receivers(model,electrodes=survey.measurements[index].electrodes)
        diagnostics.append(SourcePairDiagnostic(source_id,source.a_x_m,source.b_x_m,source.current_a,len(indices),
                                                model.max_relative_mode_residual,model.max_relative_mode_balance_error,
                                                model.elapsed_seconds))
        settings=(model.background_conductivity,len(model.wavenumbers_per_m),
                  1e-6/max(width,height) if k_min is None else float(k_min),
                  20/min(model.dx,model.dz) if k_max is None else float(k_max))
        del model
        if progress is not None:progress(source_id,len(groups))
    check_cancelled()
    return SurveyResult(survey,tuple(data),tuple(diagnostics),width,height,origin,sigma.shape[1],sigma.shape[0],
                        *settings,
                        hashlib.sha256(sigma.tobytes()).hexdigest(),perf_counter()-start)


def export_survey_csv(result,path):
    """Write ordered scalar data; the caller chooses the output location."""
    if not isinstance(result,SurveyResult):raise ValueError('result must be a SurveyResult')
    target=Path(path)
    target.parent.mkdir(parents=True,exist_ok=True)
    rows=result.records()
    with target.open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return target
