"""Reproducible small surveys: python -m tunnel_resistivity.survey_demo.

Plots show apparent resistivity against spread midpoint, not inferred depth.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from .geometry import circular_tunnel
from .survey import generate_survey, forward_survey, export_survey_csv


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=Path('outputs/surveys_2p5d'))
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    plans={kind:generate_survey(kind,electrode_count=9,electrode_spacing_m=5,
                                line_start_x_m=30,levels=(1,2),current_a=.1)
           for kind in ('wenner','schlumberger','dipole-dipole')}
    report={'model':{'width_m':100.,'height_m':50.,'nx':80,'nz':40,'host_resistivity_ohm_m':100.,
                     'tunnel_center_x_m':50.,'tunnel_depth_m':15.,'tunnel_radius_m':5.},
            'line':{'electrode_count':9,'line_start_x_m':30.,'electrode_spacing_m':5.,
                    'levels':[1,2],'current_a':.1},
            'solver':{'n_wavenumbers':64,'k_min_per_m':1e-8,'k_max_per_m':16.},
            'cases':[]}
    results={}
    for material,rho in (('homogeneous',100.),('air',1e8),('water',5.)):
        sigma,_=circular_tunnel(nx=80,nz=40,center_x=50,depth=15,radius=5,
                                host_resistivity=100,tunnel_resistivity=rho)
        np.save(args.output_dir/f'conductivity_{material}.npy',sigma)
        for kind,plan in plans.items():
            result=forward_survey(sigma,plan,n_wavenumbers=64,k_min=1e-8,k_max=16.)
            results[material,kind]=result
            export_survey_csv(result,args.output_dir/f'{material}_{kind}.csv')
            values=[datum.apparent_resistivity_ohm_m for datum in result.measurements]
            case={'material':material,'array_type':kind,'tunnel_resistivity_ohm_m':rho,
                  'measurement_count':len(result.measurements),'source_solve_count':result.solve_count,
                  'min_apparent_resistivity_ohm_m':min(values),'max_apparent_resistivity_ohm_m':max(values),
                  'max_relative_mode_residual':result.max_relative_mode_residual,
                  'max_relative_mode_balance_error':result.max_relative_mode_balance_error,
                  'conductivity_sha256':result.conductivity_sha256,'elapsed_seconds':result.elapsed_seconds,
                  'source_diagnostics':[asdict(item) for item in result.source_diagnostics]}
            report['cases'].append(case)
            print(f'{material:11s} {kind:15s}: {len(values):2d} measurements, {result.solve_count:2d} source solves; '
                  f'ρa {min(values):.5f}–{max(values):.5f} Ω·m',flush=True)
    fig,axes=plt.subplots(1,3,figsize=(14,4.5),layout='constrained')
    for ax,(kind,plan) in zip(axes,plans.items()):
        for material,color in (('air','tab:orange'),('water','tab:blue')):
            rows=results[material,kind].records()
            for level,style in ((1,'o-'),(2,'s--')):
                selected=[row for row in rows if row['level']==level]
                ax.plot([r['spread_center_x_m'] for r in selected],
                        [r['apparent_resistivity_ohm_m'] for r in selected],style,color=color,
                        label=f'{material}, level {level}',markersize=4)
        ax.axhline(100,color='gray',linestyle=':',label='Homogeneous 100 Ω·m')
        ax.axvline(50,color='gray',linewidth=.6,alpha=.6)
        ax.set(xlabel='Full electrode-spread midpoint x (m)',ylabel='Apparent resistivity (Ω·m)',title=kind)
        ax.grid(alpha=.2)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=5,fontsize=9,frameon=False)
    fig.suptitle('Small generated surface surveys: fixed electrodes, 5 m pitch\n'
                 'Levels mean Wenner a/p; Schlumberger A–M gap/p; dipole–dipole n. No inferred depth.')
    fig.savefig(args.output_dir/'survey_profiles.png',dpi=150)
    fig.savefig(args.output_dir/'survey_profiles.pdf')
    plt.close(fig)
    (args.output_dir/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Saved 9 measurement CSVs, conductivity arrays, summary JSON and profile figures to {args.output_dir}')


if __name__=='__main__':main()
