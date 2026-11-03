"""Run from the repository root: python -m analysis.run_experiments.

Writes submission artifacts to analysis/results/, not ignored outputs/.
Every potential/current field comes from the unchanged production solver.
"""

import csv
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, Normalize
from matplotlib.patches import Circle
import numpy as np
import scipy

from tunnel_resistivity.diagnostics import diagnostics
from tunnel_resistivity.geometry import circular_tunnel
from tunnel_resistivity.solver import solve_conductivity, solve_homogeneous


OUT = Path(__file__).resolve().parent / 'results'
MATERIALS = {'air': 1e8, 'water': 5.0}
COLORS = {'air': '#D55E00', 'water': '#0072B2'}
# Grid-aligned translations hold the rasterized circle unchanged in A.
DEPTHS = (7.5, 10, 15, 20, 25, 30, 35)
RADII = (2, 3, 4, 5, 7, 9)
RATIOS = (0.01, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 100, 1e4, 1e6)


@dataclass(frozen=True)
class Case:
    width_m: float = 100.0
    height_m: float = 50.0
    nx: int = 240
    nz: int = 120
    center_x_m: float = 50.0
    depth_m: float = 15.0
    radius_m: float = 5.0
    host_resistivity_ohm_m: float = 100.0
    tunnel_resistivity_ohm_m: float = 1e8


def solve_case(case, reference_cache):
    """Sample a circle and call the same solver as the Panel app."""
    sigma, mask = circular_tunnel(
        width=case.width_m, height=case.height_m, nx=case.nx, nz=case.nz,
        center_x=case.center_x_m, depth=case.depth_m, radius=case.radius_m,
        host_resistivity=case.host_resistivity_ohm_m,
        tunnel_resistivity=case.tunnel_resistivity_ohm_m,
    )
    model = solve_conductivity(sigma, width=case.width_m, height=case.height_m,
                               left_potential=1.0, right_potential=0.0)
    key = (case.width_m, case.height_m, case.nx, case.nz, case.host_resistivity_ohm_m)
    if key not in reference_cache:
        reference_cache[key] = solve_homogeneous(
            width=case.width_m, height=case.height_m, nx=case.nx, nz=case.nz,
            conductivity=1 / case.host_resistivity_ohm_m,
            left_potential=1.0, right_potential=0.0,
        )
    return model, reference_cache[key], mask


def summarize(case, model, reference, mask):
    """Define surface amplitude, both signed peaks, and an outer half-height span.

    Surface potential is reconstructed from the first row using the insulating
    top-face derivative, as in the app. The span includes the central zero gap
    of the two-lobed anomaly; it is NOT a single-lobe FWHM or a detection width.
    """
    if (not np.array_equal(model.x, reference.x) or
            not np.array_equal(model.z, reference.z) or
            (model.left_potential, model.right_potential) !=
            (reference.left_potential, reference.right_potential)):
        raise ValueError('Tunnel and reference must use matching grids and boundary conditions')
    info = diagnostics(model, reference)
    if (not np.all(np.isfinite(model.conductivity)) or np.any(model.conductivity <= 0) or
            info['relative_boundary_current_imbalance'] > 1e-8 or
            info['max_cell_imbalance_over_max_face_current'] > 1e-8 or
            model.residual_inf > 1e-11 or
            model.potential.min() < -1e-9 or model.potential.max() > 1+1e-9):
        raise RuntimeError('Numerical checks failed; do not interpret this case')
    surface = model.potential[0] - reference.potential[0]
    amplitude = float(np.max(np.abs(surface)))
    imposed_gradient = (model.left_potential-model.right_potential) / case.width_m
    reference_current = float(reference.jx[:, 0].sum()*reference.dz)
    jx = (model.jx[:, :-1]+model.jx[:, 1:])/2
    jz = (model.jz[:-1]+model.jz[1:])/2
    record = {**asdict(case), 'left_potential_V': 1.0, 'right_potential_V': 0.0,
              'top_bottom_normal_current_A_m2': 0.0,
              'dx_m': model.dx, 'dz_m': model.dz,
              'first_row_depth_m': float(model.z[0]),
              'resistivity_ratio_tunnel_host': case.tunnel_resistivity_ohm_m / case.host_resistivity_ohm_m,
              'applied_gradient_V_m': imposed_gradient,
              'surface_abs_peak_V': amplitude,
              'surface_positive_peak_V': float(surface.max()),
              'surface_negative_peak_V': float(surface.min()),
              'surface_peak_over_applied_gradient_m': amplitude / abs(imposed_gradient),
              'reference_current_A_per_m': reference_current,
              'current_change_percent': 100*(info['entering_current_A_per_m']/reference_current-1),
              'rasterized_area_m2': float(mask.sum()*model.dx*model.dz),
              'area_error_percent': 100*(mask.sum()*model.dx*model.dz/(np.pi*case.radius_m**2)-1),
              'mean_tunnel_current_density_A_m2': float(np.hypot(jx,jz)[mask].mean()),
              **info}
    # Matching materials have no meaningful peak coordinate or half-height span.
    if amplitude < 1e-12:
        record.update(surface_abs_peak_x_m=None, positive_peak_offset_m=None,
                      negative_peak_offset_m=None, outer_half_amplitude_span_m=None)
    else:
        # Symmetric peaks can differ by roundoff: use the leftmost tied maximum.
        tied = np.flatnonzero(np.abs(surface) >= amplitude*(1-1e-10))
        half = np.flatnonzero(np.abs(surface) >= amplitude/2)
        record.update(surface_abs_peak_x_m=float(model.x[tied[0]]),
                      positive_peak_offset_m=float(model.x[np.argmax(surface)]-case.center_x_m),
                      negative_peak_offset_m=float(model.x[np.argmin(surface)]-case.center_x_m),
                      outer_half_amplitude_span_m=float(model.x[half[-1]]-model.x[half[0]]))
    return record, surface


def experiment_plan():
    """One parameter at a time except deliberately documented domain controls."""
    base = Case()
    plan = []
    for material, rho in MATERIALS.items():
        for d in DEPTHS:
            plan.append(('A_depth', material, replace(base, depth_m=d, tunnel_resistivity_ohm_m=rho)))
        for r in RADII:
            plan.append(('B_radius', material, replace(base, radius_m=r, tunnel_resistivity_ohm_m=rho)))
    for ratio in RATIOS:
        plan.append(('C_contrast', 'contrast', replace(base, tunnel_resistivity_ohm_m=100*ratio)))
    for material, rho in MATERIALS.items():
        for nx in (80,160,240):
            plan.append(('D_grid', material, replace(base, nx=nx, nz=nx//2, tunnel_resistivity_ohm_m=rho)))
        # Fixed dx=dz, fixed center depth, centered in each domain; same 1 V drop.
        for width in (100,150,200):
            plan.append(('D_side', material, replace(base, width_m=width, nx=int(width*2.4),
                         center_x_m=width/2, tunnel_resistivity_ohm_m=rho)))
        # One bottom-boundary check at the widest domain, with the same E0 and mesh.
        plan.append(('D_bottom', material, replace(base, width_m=200, height_m=100,
                     nx=480, nz=240, center_x_m=100, tunnel_resistivity_ohm_m=rho)))
    # Scale BOTH resistivities, keeping contrast fixed: V unchanged, J halves.
    plan.append(('host_scaling_control', 'water', replace(base, host_resistivity_ohm_m=200,
                                                        tunnel_resistivity_ohm_m=10)))
    return plan


def write_csv(path, rows):
    with path.open('w',newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def save_figure(fig, name):
    fig.savefig(OUT/f'{name}.png', dpi=200)
    fig.savefig(OUT/f'{name}.pdf')
    plt.close(fig)


def trend_statistics(records, case_data):
    """Derived descriptive numbers; these fits are not universal scaling laws."""
    trends=[]
    def add(material,metric,value,units):
        trends.append(dict(material=material,metric=metric,value=float(value),units=units))
    for material in MATERIALS:
        def select(experiment):
            return [r for r in records if r['experiment']==experiment and r['material']==material]
        depth=select('A_depth')
        slope=np.polyfit(np.log([r['depth_m'] for r in depth]),
                         np.log([r['surface_abs_peak_V'] for r in depth]),1)[0]
        add(material,'depth_loglog_slope_over_7p5_to_35_m',slope,'dimensionless')
        add(material,'depth_7p5_to_35_m_amplitude_decrease_percent',
            100*(1-depth[-1]['surface_abs_peak_V']/depth[0]['surface_abs_peak_V']),'percent')
        radius=select('B_radius')
        log_r=np.log([r['radius_m'] for r in radius]);log_a=np.log([r['surface_abs_peak_V'] for r in radius])
        coefficients=np.polyfit(log_r,log_a,1)
        fitted=np.polyval(coefficients,log_r)
        add(material,'radius_loglog_slope_over_2_to_9_m',coefficients[0],'dimensionless')
        add(material,'radius_loglog_fit_r_squared',1-np.sum((fitted-log_a)**2)/np.sum((log_a-log_a.mean())**2),'dimensionless')
        add(material,'radius_2_to_9_m_amplitude_ratio',radius[-1]['surface_abs_peak_V']/radius[0]['surface_abs_peak_V'],'dimensionless')
        add(material,'radius_2_to_9_m_outer_span_change_percent',
            100*(radius[-1]['outer_half_amplitude_span_m']/radius[0]['outer_half_amplitude_span_m']-1),'percent')
        grid=select('D_grid')
        add(material,'grid_160_to_240_surface_change_percent',100*(grid[-1]['surface_abs_peak_V']/grid[-2]['surface_abs_peak_V']-1),'percent')
        add(material,'grid_160_to_240_total_current_change_percent',100*(grid[-1]['entering_current_A_per_m']/grid[-2]['entering_current_A_per_m']-1),'percent')
        side=select('D_side')
        add(material,'width_100_to_200_normalized_surface_change_percent',
            100*(side[-1]['surface_peak_over_applied_gradient_m']/side[0]['surface_peak_over_applied_gradient_m']-1),'percent')
        add(material,'width_150_to_200_normalized_surface_change_percent',
            100*(side[-1]['surface_peak_over_applied_gradient_m']/side[-2]['surface_peak_over_applied_gradient_m']-1),'percent')
        bottom=select('D_bottom')[0]
        add(material,'height_50_to_100_at_width_200_surface_change_percent',
            100*(bottom['surface_abs_peak_V']/side[-1]['surface_abs_peak_V']-1),'percent')
    contrast=[r for r in records if r['experiment']=='C_contrast']
    add('air','contrast_ratio_1e4_to_1e6_surface_change_percent',
        100*(contrast[-1]['surface_abs_peak_V']/contrast[-2]['surface_abs_peak_V']-1),'percent')
    base=case_data[replace(Case(),tunnel_resistivity_ohm_m=5)][0]
    scaled=case_data[replace(Case(),host_resistivity_ohm_m=200,tunnel_resistivity_ohm_m=10)][0]
    add('water','both_resistivities_doubled_max_potential_difference',np.max(np.abs(base.potential-scaled.potential)),'V')
    add('water','both_resistivities_doubled_total_current_ratio',scaled.jx[:,0].sum()/base.jx[:,0].sum(),'dimensionless')
    return trends


def style_axis(ax):
    ax.grid(alpha=.2)
    ax.spines[['top','right']].set_visible(False)


def make_figures(records, case_data):
    def select(experiment, material):
        return [r for r in records if r['experiment']==experiment and r['material']==material]

    fig,ax=plt.subplots(figsize=(7,4.5),layout='constrained')
    for material in MATERIALS:
        rows=select('A_depth',material)
        ax.loglog([r['depth_m'] for r in rows], [1000*r['surface_abs_peak_V'] for r in rows],
                  'o-',color=COLORS[material],label=material.capitalize())
    ax.set(xlabel='Tunnel center depth (m)',ylabel='Peak absolute surface ΔV (mV)',
           title='Depth sensitivity: radius 5 m, host 100 Ω·m')
    ax.legend();style_axis(ax);save_figure(fig,'01_depth')

    fig,axes=plt.subplots(1,2,figsize=(11,4.3),layout='constrained')
    for material in MATERIALS:
        rows=select('B_radius',material)
        radii=np.array([r['radius_m'] for r in rows])
        amplitudes=np.array([1000*r['surface_abs_peak_V'] for r in rows])
        axes[0].loglog(radii,amplitudes,'o-',color=COLORS[material],label=material.capitalize())
        axes[1].plot(radii,[r['outer_half_amplitude_span_m'] for r in rows],
                     'o-',color=COLORS[material],label=material.capitalize())
    anchor=select('B_radius','air')[3]['surface_abs_peak_V']*1000
    axes[0].loglog(radii,anchor*(radii/5)**2,'k--',label='r² guide, anchored at air r=5 m')
    axes[0].set(xlabel='Tunnel radius (m)',ylabel='Peak absolute surface ΔV (mV)',title='Size sensitivity at depth 15 m')
    axes[1].set(xlabel='Tunnel radius (m)',ylabel='Outer half-amplitude span (m)',
                title='Relative-height footprint (includes central gap)',ylim=(0,80))
    for ax in axes: ax.legend(fontsize=8);style_axis(ax)
    save_figure(fig,'02_radius')

    fig,axes=plt.subplots(1,2,figsize=(11,4.3),layout='constrained')
    rows=select('C_contrast','contrast')
    axes[0].semilogx([r['resistivity_ratio_tunnel_host'] for r in rows],
                     [r['surface_abs_peak_V']*1000 for r in rows],'o-',color='#333333')
    axes[0].axvline(1,color='gray',ls='--',lw=1)
    axes[0].set(xlabel='Resistivity ratio ρ tunnel / ρ host (dimensionless)',
                ylabel='Peak absolute surface ΔV (mV)',title='Contrast response and saturation')
    for material,rho in [('air',1e8),('water',5),('matched',100)]:
        case=replace(Case(),tunnel_resistivity_ohm_m=rho)
        model,ref,mask=case_data[case]
        delta=model.potential[0]-ref.potential[0]
        axes[1].plot(model.x-case.center_x_m,delta*1000,
                     color=COLORS.get(material,'gray'),label=f'{material.capitalize()}: {rho:g} Ω·m')
    axes[1].axhline(0,color='gray',lw=.7)
    axes[1].set(xlabel='Surface distance from tunnel center (m)',ylabel='Surface ΔV (mV)',
                title='Air and water reverse the signed anomaly')
    axes[1].legend(fontsize=8)
    for ax in axes: style_axis(ax)
    save_figure(fig,'03_contrast_and_profiles')

    fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
    norms=[LogNorm(5,1e8),Normalize(0,1),LogNorm(1e-10,3e-4)]
    labels=['Resistivity (Ω·m)','Potential (V)','Current density magnitude (A/m²)']
    cmaps=['viridis','viridis','magma']
    for i,(material,rho) in enumerate(MATERIALS.items()):
        model,ref,mask=case_data[replace(Case(),tunnel_resistivity_ohm_m=rho)]
        jx=(model.jx[:,:-1]+model.jx[:,1:])/2
        jz=(model.jz[:-1]+model.jz[1:])/2
        fields=[1/model.conductivity,model.potential,np.hypot(jx,jz)]
        for col,field in enumerate(fields):
            ax=axes[i,col]
            image=ax.pcolormesh(np.linspace(0,100,241),np.linspace(0,50,121),
                                field,shading='flat',cmap=cmaps[col],norm=norms[col],rasterized=True)
            ax.add_patch(Circle((50,15),5,fill=False,ls='--',edgecolor='gray',lw=1))
            ax.set(xlabel='Horizontal distance x (m)',ylabel='Depth z (m)',
                   xlim=(0,100),ylim=(50,0),
                   title=f'{material.capitalize()}: '+['Resistivity','Potential','Current flow'][col])
            ax.set_aspect('equal')
            if i==1: fig.colorbar(image,ax=axes[:,col],label=labels[col],shrink=.85)
        xx,zz=np.meshgrid(model.x,model.z)
        q=axes[i,2].quiver(xx[::9,::9],zz[::9,::9],jx[::9,::9],jz[::9,::9],
                           color='cyan',angles='xy',scale_units='xy',scale=5e-5,width=.003)
        axes[i,2].quiverkey(q,.72,1.02,1e-4,'1e-4 A/m²',labelpos='E')
    fig.suptitle('Representative scenarios: ρ host = 100 Ω·m; air = 10⁸ Ω·m; water = 5 Ω·m\n'
                 'Depth 15 m, radius 5 m, 240 × 120 cells; side potentials 1 V / 0 V')
    save_figure(fig,'04_representative_maps')

    fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
    for material in MATERIALS:
        rows=select('D_grid',material)
        axes[0,0].plot([r['dx_m'] for r in rows],[r['surface_abs_peak_V']*1000 for r in rows],
                       'o-',color=COLORS[material],label=material.capitalize())
        rows=select('D_side',material)
        widths=[r['width_m'] for r in rows]
        axes[1,0].plot(widths,[r['surface_abs_peak_V']*1000 for r in rows],
                       'o-',color=COLORS[material],label=material.capitalize()+', H=50 m')
        axes[1,1].plot(widths,[r['surface_peak_over_applied_gradient_m'] for r in rows],
                       'o-',color=COLORS[material],label=material.capitalize()+', H=50 m')
        taller=select('D_bottom',material)[0]
        axes[1,0].plot(200,taller['surface_abs_peak_V']*1000,'*',color=COLORS[material],ms=12)
        axes[1,1].plot(200,taller['surface_peak_over_applied_gradient_m'],'*',
                       color=COLORS[material],ms=12,label=material.capitalize()+', H=100 m')
    rows=select('D_grid','air')
    axes[0,1].plot([r['dx_m'] for r in rows],[r['area_error_percent'] for r in rows],'ko-')
    axes[0,1].axhline(0,color='gray',lw=.8)
    axes[0,0].set(xlabel='Grid spacing dx = dz (m)',ylabel='Peak absolute surface ΔV (mV)',title='Grid sensitivity: same physical circle')
    axes[0,1].set(xlabel='Grid spacing dx = dz (m)',ylabel='Rasterized area error (%)',title='The stair-stepped circle changes with the grid')
    axes[1,0].set(xlabel='Domain width W (m)',ylabel='Peak absolute surface ΔV (mV)',title='Raw response: imposed gradient 1 V / W changes')
    axes[1,1].set(xlabel='Domain width W (m)',ylabel='Peak ΔV / imposed gradient (m)',title='Gradient-normalized response: boundary sensitivity')
    for ax in axes.flat: style_axis(ax)
    for ax in (axes[0,0],axes[1,0],axes[1,1]): ax.legend(fontsize=7)
    save_figure(fig,'05_grid_domain_sensitivity')


def main():
    plt.rcParams.update({'font.size':10,'axes.titlesize':11,'savefig.bbox':'tight'})
    OUT.mkdir(parents=True,exist_ok=True)
    references,case_data,records,profiles={}, {}, [], []
    for index,(experiment,material,case) in enumerate(experiment_plan(),start=1):
        if case not in case_data:
            case_data[case]=solve_case(case,references)
        model,reference,mask=case_data[case]
        values,surface=summarize(case,model,reference,mask)
        record={'case_id':f'{index:02d}', 'experiment':experiment,'material':material,**values}
        records.append(record)
        profiles.extend({'case_id':record['case_id'],'experiment':experiment,'material':material,
                         'x_m':float(x),'offset_from_center_m':float(x-case.center_x_m),
                         'surface_delta_V':float(delta)} for x,delta in zip(model.x,surface))
        print(f"{index:02d} {experiment:20s} {material:8s} A={1000*values['surface_abs_peak_V']:.6f} mV",flush=True)
    write_csv(OUT/'summary.csv',records)
    write_csv(OUT/'surface_profiles.csv',profiles)
    write_csv(OUT/'trend_statistics.csv',trend_statistics(records,case_data))
    make_figures(records,case_data)
    solver_path=Path(__file__).resolve().parents[1]/'tunnel_resistivity'/'solver.py'
    metadata={'numpy':np.__version__,'scipy':scipy.__version__,'matplotlib':matplotlib.__version__,
              'solver_sha256':hashlib.sha256(solver_path.read_bytes()).hexdigest(),
              'rows':len(records),'unique_tunnel_solves':len(case_data),'homogeneous_solves':len(references),
              'surface_definition':'First-row potential, zero-normal-gradient top-face reconstruction',
              'span_definition':'Outer span where abs(surface delta) >= 0.5*peak, including the central zero gap',
              'domain_normalization':'A/E0, E0=(V_left-V_right)/W; units m; not apparent resistivity',
              'peak_tie_rule':'Leftmost absolute maximum tied within relative 1e-10; signed peaks recorded separately',
              'checks':'Every case: positive finite conductivity, bounded V, residual and local/global conservation'}
    (OUT/'provenance.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print('Saved',OUT)


if __name__=='__main__':
    main()
