"""Selected-measurement field snapshots from the existing 2.5D solver."""
from collections import OrderedDict
from dataclasses import dataclass

from .receivers import measure_receivers
from .solver_2p5d import Solution25D, solve_source_pair
from .survey import SurveyCancelled, _integer
from .survey_simulation import SurveySimulationResult


@dataclass(frozen=True)
class FieldRequest:
    result: SurveySimulationResult
    measurement_index: int

    def __post_init__(self):
        if not isinstance(self.result,SurveySimulationResult):raise ValueError('Expected a completed survey snapshot')
        index=_integer(self.measurement_index,'measurement_index',0)
        if index>=len(self.result.data.measurements):raise ValueError('Measurement index is outside the completed survey')
        object.__setattr__(self,'measurement_index',index)

    @property
    def electrodes(self):
        return self.result.plan.survey.measurements[self.measurement_index].electrodes

    @property
    def source_key(self):
        e=self.electrodes
        return id(self.result),e.a_x_m,e.b_x_m,e.current_a


@dataclass(frozen=True)
class FieldResult:
    request: FieldRequest
    solution: Solution25D

    @property
    def measurement(self):
        # Cached fields can be shared by different M/N configurations; use the
        # requested receivers, not those stored in the original source solve.
        return measure_receivers(self.solution,electrodes=self.request.electrodes)


def default_measurement_index(result):
    """Choose the widest requested level, then midpoint nearest the tunnel."""
    entries=result.plan.survey.measurements
    return min(range(len(entries)),key=lambda i:(-entries[i].level,
               abs(entries[i].electrodes.center_x_m-result.plan.tunnel.center_x_m)))


def solve_field_request(request,*,cancelled=None,progress=None):
    """One extra source solve, using the completed survey's exact grid/settings."""
    def check():
        if cancelled is not None and cancelled():raise SurveyCancelled('Selected field superseded')
    check()
    if progress is not None:progress(0,1)
    data=request.result.data
    solution=solve_source_pair(request.result.model.conductivity,request.electrodes,
                **request.result.plan.grid.solver_kwargs(),background_conductivity=data.background_conductivity,
                n_wavenumbers=data.n_wavenumbers,k_min=data.k_min_per_m,k_max=data.k_max_per_m)
    check()
    if progress is not None:progress(1,1)
    return FieldResult(request,solution)


class SourceFieldCache:
    """Bounded per-app cache; keys include snapshot identity, source A/B and I.

    Values hold a strong reference to the owning snapshot, preventing object-ID
    reuse from producing a stale cache hit. No sparse factorizations are retained.
    """
    def __init__(self,capacity=2):
        self.capacity=_integer(capacity,'capacity');self._items=OrderedDict()

    def get(self,request):
        item=self._items.get(request.source_key)
        if item is None or item.request.result is not request.result:return None
        self._items.move_to_end(request.source_key)
        return FieldResult(request,item.solution)

    def put(self,result):
        key=result.request.source_key;self._items[key]=result;self._items.move_to_end(key)
        while len(self._items)>self.capacity:self._items.popitem(last=False)

    def retain(self,results):
        allowed={id(result) for result in results if result is not None}
        for key in list(self._items):
            if key[0] not in allowed:del self._items[key]

    def clear(self):self._items.clear()

    def __len__(self):return len(self._items)
