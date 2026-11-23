"""Browser/worker adapter; delegates all numerical work to production modules.

No Panel, threads, HTTP server, or second numerical solver is used here.
"""
import base64
import csv
from dataclasses import asdict, replace
import io
import json
import platform

import matplotlib
matplotlib.use('Agg')
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.transforms import Bbox
import numpy as np
import scipy

from .fields import FieldRequest, SourceFieldCache, default_measurement_index, solve_field_request
from .survey import _integer
from .survey_plotting import build_field_figure, build_surface_figure, build_survey_figure, build_survey_map
from .survey_simulation import PRESETS, SurveyParameters, plan_simulation, run_survey_plan

MAX_BROWSER_CELLS = 32768
MAX_BROWSER_ELECTRODES = 64
# Four levels on 64 electrodes need at most 232 source pairs / 238 data.
# These are work limits; the separate cell-memory guard is unchanged.
MAX_BROWSER_SOURCES = 256
MAX_BROWSER_MEASUREMENTS = 256
DEFAULT_PARAMETERS = replace(SurveyParameters(), electrode_count=7)


def browser_plan(parameters, material):
    """Validate before allocating arrays; retain the production grid rules."""
    if material not in (*PRESETS, 'Custom'):
        raise ValueError('Choose Air-filled, Water-filled or Custom')
    p = SurveyParameters(**parameters)
    if _integer(p.electrode_count,'electrode_count',4) > MAX_BROWSER_ELECTRODES:
        raise ValueError(f'The browser supports at most {MAX_BROWSER_ELECTRODES} physical electrodes')
    if material in PRESETS:
        p = replace(p, tunnel_resistivity=PRESETS[material])
    plan = plan_simulation(p,max_measurements=MAX_BROWSER_MEASUREMENTS)
    if plan.grid.cell_count > MAX_BROWSER_CELLS:
        raise ValueError(f'This grid has {plan.grid.cell_count:,} cells; browser limit is '
                         f'{MAX_BROWSER_CELLS:,}. Reduce the domain, spacing or resolution. '
                         'The grid has not been silently coarsened.')
    if plan.survey.unique_source_pair_count > MAX_BROWSER_SOURCES:
        raise ValueError(f'This survey needs {plan.survey.unique_source_pair_count} source solves; '
                         f'browser limit is {MAX_BROWSER_SOURCES}. Reduce electrodes or levels.')
    if len(plan.survey.measurements) > MAX_BROWSER_MEASUREMENTS:
        raise ValueError(f'Browser limit is {MAX_BROWSER_MEASUREMENTS} measurements; reduce electrodes or levels.')
    return plan


def _png(figure, bbox=None):
    output = io.BytesIO()
    figure.savefig(output, format='png', dpi=110, bbox_inches=bbox, pad_inches=.08)
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')


def _panels(figure, groups):
    """Export original axes with their color bars for a one-column phone layout."""
    title = figure._suptitle
    if title is not None:title.set_visible(False)
    FigureCanvasAgg(figure)
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    images = []
    for axes in groups:
        bbox = Bbox.union([ax.get_tightbbox(renderer) for ax in axes])
        bbox = bbox.transformed(figure.dpi_scale_trans.inverted()).padded(.08)
        images.append(_png(figure, bbox))
    if title is not None:title.set_visible(True)
    return images


def _metadata(result):
    p = result.plan.parameters
    return dict(parameters=asdict(p), grid=asdict(result.plan.grid),
                measurements=len(result.data.measurements), sources=result.data.solve_count,
                seconds=result.data.elapsed_seconds,
                max_mode_residual=result.data.max_relative_mode_residual,
                max_mode_balance=result.data.max_relative_mode_balance_error,
                warnings=list(result.model.warnings),
                versions={'python':platform.python_version(), 'numpy':np.__version__,
                          'scipy':scipy.__version__, 'matplotlib':matplotlib.__version__})


def _records(result):
    rows = result.data.records()
    p = result.plan.parameters
    for row in rows:
        row.update(tunnel_center_x_m=p.center_x_m, tunnel_depth_m=p.depth_m,
                   tunnel_radius_m=p.radius_m, host_resistivity_ohm_m=p.host_resistivity,
                   tunnel_resistivity_ohm_m=p.tunnel_resistivity,
                   physical_electrode_count=p.electrode_count,
                   physical_electrode_spacing_m=p.electrode_spacing_m,
                   receiver_spacing_steps=p.receiver_spacing_steps,
                   dipole_spacing_steps=p.dipole_spacing_steps,
                   python_version=platform.python_version(), numpy_version=np.__version__,
                   scipy_version=scipy.__version__, matplotlib_version=matplotlib.__version__)
    return rows


class BrowserEngine:
    """A worker-owned engine with explicit two-snapshot retention by the UI."""
    def __init__(self):
        self.results = {}
        self.fields = SourceFieldCache(2)

    def retain(self, identifiers):
        allowed = set(identifiers)
        self.results = {key:value for key,value in self.results.items() if key in allowed}
        self.fields.retain(tuple(self.results.values()))

    def survey(self, identifier, parameters, material, progress=None):
        plan = browser_plan(parameters, material)
        if progress:
            progress({'phase':'plan', 'grid':asdict(plan.grid),
                      'measurements':len(plan.survey.measurements),
                      'sources':plan.survey.unique_source_pair_count})
        def notify(done, total):
            if progress:progress({'phase':'survey', 'done':done, 'total':total})
        result = run_survey_plan(plan, progress=notify)
        self.results[identifier] = result
        try:
            rows = _records(result)
            csv_text = io.StringIO()
            writer = csv.DictWriter(csv_text, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
            overview = build_survey_figure(result)
            # The field maps already show the model; use the original profile axes.
            profile = _panels(overview, [(overview.axes[1],)])[0]
            selected = default_measurement_index(result)
            field = self.field(identifier, selected, progress=progress)
            return dict(identifier=identifier, metadata=_metadata(result), records=rows,
                        csv=csv_text.getvalue(), profile=profile, selected=selected, field=field)
        except Exception:
            self.results.pop(identifier, None)
            raise

    def field(self, identifier, measurement_index, progress=None):
        if identifier not in self.results:
            raise ValueError('That completed snapshot is no longer available. Update the simulation.')
        result = self.results[identifier]
        request = FieldRequest(result, measurement_index)
        field = self.fields.get(request)
        if field is None:
            if progress:progress({'phase':'field', 'measurement':measurement_index+1})
            field = solve_field_request(request)
            self.fields.put(field)
        figure = build_field_figure(field)
        names = ('Resistivity (Ω·m)', 'Potential (V)', 'Current magnitude (A/m²)', 'Tunnel − reference (V)')
        for ax, title in zip(figure.axes[:4], names):ax.set_title(title)
        panels = _panels(figure, [(figure.axes[i], figure.axes[i+4]) for i in range(4)])
        datum = field.measurement
        return dict(identifier=identifier, index=measurement_index,
                    electrodes=request.electrodes.positions_x_m,
                    voltage_v=datum.voltage_v,
                    secondary_voltage_v=datum.secondary_voltage_v,
                    apparent_resistivity_ohm_m=datum.apparent_resistivity_ohm_m,
                    panels=panels, png=_png(figure),
                    surface=_png(build_surface_figure(field)),
                    survey_map=_png(build_survey_map(result, measurement_index)))

    def handle(self, request, progress=None):
        kind = request['kind']
        if kind == 'survey':
            return self.survey(request['id'], request['parameters'], request['material'], progress)
        if kind == 'field':
            return self.field(request['identifier'], request['index'], progress)
        if kind == 'retain':
            self.retain(request['identifiers'])
            return None
        raise ValueError('Unknown browser operation')
