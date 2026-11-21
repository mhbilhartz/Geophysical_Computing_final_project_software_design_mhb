"""Grid/domain planning and controlled solves: python -m tunnel_resistivity.grid_demo."""
import argparse
import csv
from dataclasses import asdict
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.patches import Circle, Rectangle
import numpy as np

from .grid import TunnelGeometry, suggest_grid, prepare_survey_model
from .survey import Survey, generate_survey, forward_survey


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=Path('outputs/grids_2p5d'))
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    tunnel=TunnelGeometry()
    report={'tunnel':asdict(tunnel),'host_resistivity_ohm_m':100.,
            'line':{'start_x_m':30.,'electrode_count':9,'pitch_m':5.,'levels':[1,2]},
            'spectral_settings':{'n_wavenumbers':64,'k_min_per_m':1e-8,'k_max_per_m':16.},
            'automatic_grids':[],'sensitivity':[]}
    fig,axes=plt.subplots(1,3,figsize=(13,4.5),layout='constrained')
    plans={}
    for ax,kind in zip(axes,('wenner','schlumberger','dipole-dipole')):
        plan=generate_survey(kind,current_a=.1);plans[kind]=plan
        grid=suggest_grid(plan,tunnel)
        model=prepare_survey_model(plan,tunnel,grid,tunnel_resistivity=5.)
        image=ax.imshow(1/model.conductivity,extent=(grid.x_min_m,grid.x_max_m,grid.height_m,0),
                        origin='upper',aspect='equal',cmap='viridis',norm=LogNorm(5,100))
        ax.add_patch(Rectangle((grid.x_min_m,0),grid.width_m,grid.height_m,fill=False,edgecolor='black',linewidth=.8))
        ax.add_patch(Circle((50,15),5,fill=False,edgecolor='white',linestyle='--'))
        ax.scatter(plan.electrode_positions_x_m,[0]*len(plan.electrode_positions_x_m),s=15,
                   marker='v',color='red',clip_on=False)
        ax.set(xlim=(-30,130),ylim=(80,0),xlabel='World horizontal x (m)',ylabel='Depth z (m)',
               title=f'{kind}\n{grid.nx}×{grid.nz} cells; {grid.width_m:g}×{grid.height_m:g} m')
        ax.set_facecolor('#eeeeee')
        report['automatic_grids'].append({'array_type':kind,'grid':asdict(grid),
                                         'diagnostics':model.diagnostics,'warnings':model.warnings})
        print(kind,asdict(grid),'cells',grid.cell_count,flush=True)
    fig.colorbar(image,ax=list(axes),label='Resistivity (Ω·m)',shrink=.8)
    fig.suptitle('Automatic domain footprints at identical physical scales\n'
                 'Red markers: surface electrodes. Gray area: outside each model. Water tunnel center (50,15) m.')
    fig.savefig(args.output_dir/'automatic_domains.png',dpi=150)
    fig.savefig(args.output_dir/'automatic_domains.pdf');plt.close(fig)

    plan=plans['wenner']
    entry=next(m for m in plan.measurements if m.level==2 and m.electrodes.center_x_m==50)
    single=Survey(plan.electrode_positions_x_m,(entry,))
    for material,rho in (('air',1e8),('water',5.)):
        for case,size,padding in (('Base',1.25,2.),('Finer cells',.625,2.),('Larger domain',1.25,3.)):
            grid=suggest_grid(single,tunnel,max_cell_size_m=size,padding_factor=padding)
            model=prepare_survey_model(single,tunnel,grid,tunnel_resistivity=rho)
            result=forward_survey(model.conductivity,single,n_wavenumbers=64,k_min=1e-8,k_max=16.,**grid.solver_kwargs())
            datum=result.measurements[0]
            row={'material':material,'case':case,**asdict(grid),'dx_m':grid.dx_m,'dz_m':grid.dz_m,
                 'cell_count':grid.cell_count,'rho_a_ohm_m':datum.apparent_resistivity_ohm_m,
                 'voltage_v':datum.voltage_v,'relative_area_error':model.diagnostics['relative_tunnel_area_error'],
                 'max_relative_mode_residual':result.max_relative_mode_residual,
                 'max_relative_mode_balance_error':result.max_relative_mode_balance_error,'elapsed_seconds':result.elapsed_seconds}
            report['sensitivity'].append(row)
            print(material,case,f'{grid.nx}×{grid.nz}',f'ρa={datum.apparent_resistivity_ohm_m:.8f} Ω·m',flush=True)
    with (args.output_dir/'sensitivity.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(report['sensitivity'][0]));writer.writeheader();writer.writerows(report['sensitivity'])
    fig,axes=plt.subplots(1,2,figsize=(10,4.5),layout='constrained')
    for ax,material,color in zip(axes,('air','water'),('tab:orange','tab:blue')):
        selected=[r for r in report['sensitivity'] if r['material']==material]
        ax.plot(range(3),[r['rho_a_ohm_m']-100 for r in selected],'o-',color=color)
        ax.set_xticks(range(3),[r['case'] for r in selected])
        ax.set(ylabel='Apparent resistivity − host (Ω·m)',title=f'{material}: one central Wenner datum')
        ax.grid(alpha=.3)
    fig.suptitle('Change resolution and padding separately; same electrodes/current/circle\n'
                 'No analytical tunnel solution: these are sensitivity checks, not accuracy bounds')
    fig.savefig(args.output_dir/'grid_domain_sensitivity.png',dpi=150)
    fig.savefig(args.output_dir/'grid_domain_sensitivity.pdf');plt.close(fig)
    (args.output_dir/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Saved planning/sensitivity figures, CSV and JSON to {args.output_dir}')


if __name__=='__main__':main()
