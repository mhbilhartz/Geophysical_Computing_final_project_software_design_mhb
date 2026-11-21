"""Grid/domain planning and model preparation for the existing survey solver.

Physical x coordinates are preserved when domains move. Automatic padding and
resolution rules are heuristics, not certified error-controlled boundaries.
No numerical PDE method or Panel controls are implemented in this module.
"""
from dataclasses import dataclass
import math
import warnings

import numpy as np

from .electrodes import _finite, _positive
from .geometry import circular_tunnel
from .solver import cell_centers
from .survey import Survey, _integer

DEFAULT_MAX_CELLS=100_000


@dataclass(frozen=True)
class TunnelGeometry:
    center_x_m: float = 50.
    depth_m: float = 15.
    radius_m: float = 5.

    def __post_init__(self):
        center=_finite(self.center_x_m,'center_x_m')
        depth=_positive(self.depth_m,'depth_m');radius=_positive(self.radius_m,'radius_m')
        if depth<=radius:
            raise ValueError('The tunnel must be fully buried: center depth must exceed radius')
        if not center-radius<center<center+radius or not math.isfinite(center+radius) or not math.isfinite(center-radius):
            raise ValueError('Tunnel x extent cannot be resolved at floating-point precision')
        _finite(depth+radius,'tunnel bottom')
        object.__setattr__(self,'center_x_m',center)
        object.__setattr__(self,'depth_m',depth)
        object.__setattr__(self,'radius_m',radius)

    @property
    def roof_depth_m(self):
        return self.depth_m-self.radius_m


@dataclass(frozen=True)
class GridSpec:
    x_min_m: float
    x_max_m: float
    height_m: float
    nx: int
    nz: int

    def __post_init__(self):
        left=_finite(self.x_min_m,'x_min_m');right=_finite(self.x_max_m,'x_max_m')
        width=_positive(right-left,'grid width');height=_positive(self.height_m,'height_m')
        nx=_integer(self.nx,'nx',2);nz=_integer(self.nz,'nz',2)
        try:
            dx=_positive(width/nx,'dx');dz=_positive(height/nz,'dz')
        except OverflowError as exc:
            raise ValueError('Grid counts exceed floating-point range') from exc
        if not (left<left+dx/2<right-dx/2<right and left+dx/2<left+1.5*dx<right):
            raise ValueError('Grid x centers cannot be resolved at floating-point precision')
        if not 0<dz/2<height-dz/2<height:
            raise ValueError('Grid depth centers cannot be resolved at floating-point precision')
        for name,value in (('x_min_m',left),('x_max_m',right),('height_m',height),('nx',nx),('nz',nz)):
            object.__setattr__(self,name,value)

    @property
    def width_m(self):return self.x_max_m-self.x_min_m

    @property
    def dx_m(self):return self.width_m/self.nx

    @property
    def dz_m(self):return self.height_m/self.nz

    @property
    def cell_count(self):return self.nx*self.nz

    def solver_kwargs(self):
        return {'width':self.width_m,'height':self.height_m,'x_origin_m':self.x_min_m}

    def cell_centers(self):
        x,z,_,_=cell_centers(self.width_m,self.height_m,self.nx,self.nz)
        return x+self.x_min_m,z


def _require_geometry(survey,tunnel):
    if not isinstance(survey,Survey):raise ValueError('survey must be a Survey')
    if not isinstance(tunnel,TunnelGeometry):raise ValueError('tunnel must be a TunnelGeometry')


def _check_budget(grid,max_cells):
    budget=_integer(max_cells,'max_cells',4)
    if grid.cell_count>budget:
        raise ValueError(f'Grid requires {grid.nx} × {grid.nz} = {grid.cell_count} cells; budget is {budget}. '
                         'Choose a smaller domain/line or less demanding resolution, or explicitly increase max_cells. '
                         'The grid was not silently coarsened.')


def _check_placement(survey,tunnel,grid):
    survey.validate_domain(grid.x_min_m,grid.x_max_m)
    if not (grid.x_min_m<tunnel.center_x_m-tunnel.radius_m and
            tunnel.center_x_m+tunnel.radius_m<grid.x_max_m and
            tunnel.depth_m+tunnel.radius_m<grid.height_m):
        raise ValueError('The complete tunnel must lie strictly inside the grid')
    if not grid.dz_m/2<tunnel.roof_depth_m:
        raise ValueError('Refine nz: the first cell-center row must lie above the tunnel roof to preserve the homogeneous surface row')


def suggest_grid(survey,tunnel,*,max_cell_size_m=1.25,padding_factor=2.,min_padding_m=10.,
                 side_padding_m=None,bottom_padding_m=None,cells_per_radius=4.,
                 cells_per_electrode_spacing=4.,max_cells=DEFAULT_MAX_CELLS):
    """Choose bounds and nx/nz without allocating a conductivity array.

    S=max measurement spread, p=min physical electrode separation.
    P=max(min_padding_m,padding_factor*S); explicit side/bottom padding overrides P.
    Bounds enclose the complete electrode line AND circle, plus side padding.
    Bottom=max(tunnel bottom,S/2)+bottom padding; the top remains z=0.
    dx<=min(max_cell_size,radius/cells_per_radius,p/cells_per_electrode_spacing).
    dz<=min(max_cell_size,radius/cells_per_radius,roof_depth/2), keeping two
    complete host rows above the roof. Counts round UP, never coarsen to budget.
    """
    _require_geometry(survey,tunnel)
    size=_positive(max_cell_size_m,'max_cell_size_m')
    factor=_positive(padding_factor,'padding_factor');minimum=_positive(min_padding_m,'min_padding_m')
    radius_cells=_positive(cells_per_radius,'cells_per_radius')
    spacing_cells=_positive(cells_per_electrode_spacing,'cells_per_electrode_spacing')
    if radius_cells<4 or spacing_cells<2:
        raise ValueError('Automatic planning requires cells_per_radius >=4 and cells_per_electrode_spacing >=2')
    span=max(entry.electrodes.span_m for entry in survey.measurements)
    pitch=min(b-a for a,b in zip(survey.electrode_positions_x_m,survey.electrode_positions_x_m[1:]))
    padding=_positive(max(minimum,factor*span),'automatic padding')
    sides=padding if side_padding_m is None else _positive(side_padding_m,'side_padding_m')
    bottom=padding if bottom_padding_m is None else _positive(bottom_padding_m,'bottom_padding_m')
    left=_finite(min(survey.electrode_positions_x_m[0],tunnel.center_x_m-tunnel.radius_m)-sides,'left boundary')
    right=_finite(max(survey.electrode_positions_x_m[-1],tunnel.center_x_m+tunnel.radius_m)+sides,'right boundary')
    height=_positive(max(tunnel.depth_m+tunnel.radius_m,span/2)+bottom,'height')
    width=_positive(right-left,'width')
    target_dx=_positive(min(size,tunnel.radius_m/radius_cells,pitch/spacing_cells),'target dx')
    target_dz=_positive(min(size,tunnel.radius_m/radius_cells,tunnel.roof_depth_m/2),'target dz')
    ratios=(width/target_dx,height/target_dz)
    if not all(math.isfinite(ratio) for ratio in ratios):
        raise ValueError('Requested grid resolution exceeds floating-point range')
    nx=max(2,math.ceil(ratios[0]));nz=max(2,math.ceil(ratios[1]))
    if width/nx>target_dx:nx+=1
    if height/nz>target_dz:nz+=1
    grid=GridSpec(left,right,height,nx,nz)
    _check_budget(grid,max_cells);_check_placement(survey,tunnel,grid)
    return grid


@dataclass(frozen=True)
class PreparedSurveyModel:
    survey: Survey
    tunnel: TunnelGeometry
    grid: GridSpec
    host_resistivity_ohm_m: float
    tunnel_resistivity_ohm_m: float
    conductivity: np.ndarray
    tunnel_mask: np.ndarray
    diagnostics: dict
    warnings: tuple[str,...]


def prepare_survey_model(survey,tunnel,grid,*,host_resistivity=100.,tunnel_resistivity=1e8,
                         max_cells=DEFAULT_MAX_CELLS):
    """Validate an automatic OR manual grid, then call the original geometry.

    Geometry center_x in circular_tunnel is local to the rectangle. Convert
    world x to x-center-minus-left-edge here; neither electrodes nor tunnel
    location are moved when grid bounds change. This function performs no solve.
    """
    _require_geometry(survey,tunnel)
    if not isinstance(grid,GridSpec):raise ValueError('grid must be a GridSpec')
    _check_budget(grid,max_cells);_check_placement(survey,tunnel,grid)
    host=_positive(host_resistivity,'host_resistivity');rho=_positive(tunnel_resistivity,'tunnel_resistivity')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always',UserWarning)
        sigma,mask=circular_tunnel(width=grid.width_m,height=grid.height_m,nx=grid.nx,nz=grid.nz,
                                    center_x=tunnel.center_x_m-grid.x_min_m,depth=tunnel.depth_m,
                                    radius=tunnel.radius_m,host_resistivity=host,tunnel_resistivity=rho)
    if np.any(mask[0]):raise ValueError('Tunnel intersects the top model row; refine the grid')
    pitch=min(b-a for a,b in zip(survey.electrode_positions_x_m,survey.electrode_positions_x_m[1:]))
    background_rows=next((i for i,row in enumerate(mask) if np.any(row)),grid.nz)
    area=float(np.count_nonzero(mask)*grid.dx_m*grid.dz_m)
    circle_area=math.pi*tunnel.radius_m**2
    aspect=max(grid.dx_m/grid.dz_m,grid.dz_m/grid.dx_m)
    notes=[str(w.message) for w in caught]
    if pitch/grid.dx_m<4:
        notes.append('Fewer than four horizontal cells per minimum electrode spacing; check receiver interpolation sensitivity.')
    if aspect>4:
        notes.append('Cell aspect ratio exceeds four; inspect conditioning and directional grid sensitivity.')
    if not np.allclose(sigma[1],1/host,rtol=1e-12,atol=0):
        notes.append('The second conductivity row contains the anomaly; surface receivers use first-row reconstruction there.')
    info={'width_m':grid.width_m,'height_m':grid.height_m,'x_min_m':grid.x_min_m,'x_max_m':grid.x_max_m,
          'nx':grid.nx,'nz':grid.nz,'cell_count':grid.cell_count,'dx_m':grid.dx_m,'dz_m':grid.dz_m,
          'cells_per_radius_x':tunnel.radius_m/grid.dx_m,'cells_per_radius_z':tunnel.radius_m/grid.dz_m,
          'cells_per_min_electrode_spacing_x':pitch/grid.dx_m,'cell_aspect_ratio':aspect,
          'roof_clearance_m':tunnel.roof_depth_m,'bottom_clearance_m':grid.height_m-tunnel.depth_m-tunnel.radius_m,
          'left_tunnel_clearance_m':tunnel.center_x_m-tunnel.radius_m-grid.x_min_m,
          'right_tunnel_clearance_m':grid.x_max_m-tunnel.center_x_m-tunnel.radius_m,
          'minimum_electrode_side_clearance_m':min(survey.electrode_positions_x_m[0]-grid.x_min_m,
                                                   grid.x_max_m-survey.electrode_positions_x_m[-1]),
          'geometric_host_rows_above_tunnel':background_rows,
          'sampled_tunnel_area_m2':area,'circle_area_m2':circle_area,'relative_tunnel_area_error':(area-circle_area)/circle_area,
          'measurement_count':len(survey.measurements),'unique_source_pair_count':survey.unique_source_pair_count}
    return PreparedSurveyModel(survey,tunnel,grid,host,rho,sigma,mask,info,tuple(dict.fromkeys(notes)))
