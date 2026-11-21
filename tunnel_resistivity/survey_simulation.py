"""Immutable live-app inputs and orchestration of the existing 2.5D backend."""
from dataclasses import dataclass
import math

from .electrodes import _positive
from .grid import (GridSpec, TunnelGeometry, PreparedSurveyModel, suggest_grid,
                   prepare_survey_model, _check_budget, _check_placement)
from .survey import Survey, SurveyResult, SurveyCancelled, _integer, generate_survey, forward_survey

PRESETS={'Air-filled':1e8,'Water-filled':5.}
MAX_CELLS=100_000
MAX_MEASUREMENTS=120


@dataclass(frozen=True)
class SurveyParameters:
    array_type: str = 'wenner'
    electrode_count: int = 9
    electrode_spacing_m: float = 5.
    line_start_x_m: float = 30.
    max_level: int = 2
    receiver_spacing_steps: int = 1
    dipole_spacing_steps: int = 1
    current_a: float = .1
    depth_m: float = 15.
    radius_m: float = 5.
    center_x_m: float = 50.
    host_resistivity: float = 100.
    tunnel_resistivity: float = 1e8
    grid_mode: str = 'Automatic'
    max_cell_size_m: float = 1.25
    padding_factor: float = 2.
    x_min_m: float = -30.
    x_max_m: float = 130.
    height_m: float = 80.
    nx: int = 128
    nz: int = 64


@dataclass(frozen=True)
class SurveyPlan:
    parameters: SurveyParameters
    survey: Survey
    tunnel: TunnelGeometry
    grid: GridSpec


@dataclass(frozen=True)
class SurveySimulationResult:
    plan: SurveyPlan
    model: PreparedSurveyModel
    data: SurveyResult


def plan_simulation(parameters):
    """Fast validation/counts for the UI; no model arrays or PDE solve."""
    if not isinstance(parameters,SurveyParameters):raise ValueError('Expected SurveyParameters')
    p=parameters
    for name in ('host_resistivity','tunnel_resistivity'):
        value=_positive(getattr(p,name),name)
        if not math.isfinite(1/value) or 1/value<=0:raise ValueError('Resistivity reciprocal must be finite and positive')
    level=_integer(p.max_level,'max_level')
    if level>1000:raise ValueError('max_level is too large')
    survey=generate_survey(p.array_type,electrode_count=p.electrode_count,electrode_spacing_m=p.electrode_spacing_m,
                           line_start_x_m=p.line_start_x_m,levels=range(1,level+1),current_a=p.current_a,
                           receiver_spacing_steps=p.receiver_spacing_steps,dipole_spacing_steps=p.dipole_spacing_steps)
    if len(survey.measurements)>MAX_MEASUREMENTS:
        raise ValueError(f'The live app supports at most {MAX_MEASUREMENTS} measurements; reduce electrodes or levels')
    tunnel=TunnelGeometry(p.center_x_m,p.depth_m,p.radius_m)
    if p.grid_mode=='Automatic':
        grid=suggest_grid(survey,tunnel,max_cell_size_m=p.max_cell_size_m,padding_factor=p.padding_factor,max_cells=MAX_CELLS)
    elif p.grid_mode=='Manual':
        grid=GridSpec(p.x_min_m,p.x_max_m,p.height_m,p.nx,p.nz)
        _check_budget(grid,MAX_CELLS);_check_placement(survey,tunnel,grid)
    else:raise ValueError('Choose Automatic or Manual grid mode')
    return SurveyPlan(p,survey,tunnel,grid)


def run_survey_plan(plan,*,cancelled=None,progress=None):
    """Prepare a fixed model snapshot and call the production survey solver."""
    if cancelled is not None and cancelled():raise SurveyCancelled('Survey superseded')
    p=plan.parameters
    model=prepare_survey_model(plan.survey,plan.tunnel,plan.grid,host_resistivity=p.host_resistivity,
                               tunnel_resistivity=p.tunnel_resistivity,max_cells=MAX_CELLS)
    data=forward_survey(model.conductivity,plan.survey,**plan.grid.solver_kwargs(),n_wavenumbers=64,
                        cancelled=cancelled,progress=progress)
    return SurveySimulationResult(plan,model,data)
