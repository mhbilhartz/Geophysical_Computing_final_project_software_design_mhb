"""Static source-pair comparison: python -m tunnel_resistivity.demo_2p5d.

This is a backend demonstration, without receiver sampling or Panel changes.
"""
import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.patches import Circle
import numpy as np

from .electrodes import wenner
from .geometry import circular_tunnel
from .solver_2p5d import solve_source_pair


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path('outputs/source_pair_2p5d'))
    args = parser.parse_args()
    width, height, center, depth, radius = 200., 100., 100., 15., 5.
    array = wenner(center_x_m=center, spacing_m=10, current_a=1)
    models = []
    for name,rho in (('Air approximation',1e8),('Water approximation',5.)):
        sigma,_ = circular_tunnel(width=width,height=height,nx=160,nz=80,
                                  center_x=center,depth=depth,radius=radius,
                                  host_resistivity=100,tunnel_resistivity=rho)
        models.append((name,rho,solve_source_pair(sigma,array,width=width,height=height)))
    fig,axes = plt.subplots(4,2,figsize=(13,16),layout='constrained')
    vlim = max(np.max(abs(s.potential)) for _,_,s in models)
    slim = max(np.max(abs(s.secondary_potential)) for _,_,s in models)
    currents = [np.hypot(s.jx,s.jz) for _,_,s in models]
    jmax = max(np.max(j) for j in currents)
    extent = (0,width,height,0)
    report = {'domain_m':[width,height], 'grid':[160,80],
              'tunnel_center_m':[center,depth], 'tunnel_radius_m':radius,
              'host_resistivity_ohm_m':100, 'current_A':1,
              'electrodes_x_m':array.positions_x_m, 'cases':{}}
    for col,(name,rho,s) in enumerate(models):
        specs = ((1/s.conductivity,'Resistivity (Ω·m)',dict(norm=LogNorm(5,1e8),cmap='viridis')),
                 (s.potential,'Electrical potential (V)',dict(vmin=-vlim,vmax=vlim,cmap='RdBu_r')),
                 (s.secondary_potential,'Tunnel − homogeneous potential (V)',dict(vmin=-slim,vmax=slim,cmap='RdBu_r')),
                 (currents[col],'Current-density magnitude (A/m²)',dict(norm=LogNorm(jmax*1e-8,jmax),cmap='magma')))
        for row,(field,label,style) in enumerate(specs):
            ax=axes[row,col]
            image=ax.imshow(field,extent=extent,origin='upper',aspect='equal',**style)
            fig.colorbar(image,ax=ax,label=label)
            ax.set(xlabel='Horizontal distance x (m)',ylabel='Depth z (m)')
            ax.set_title(f'{name}: {label}',fontsize=11)
            ax.add_patch(Circle((center,depth),radius,fill=False,edgecolor='gray',linestyle='--'))
            for source,label_,color in ((array.a_x_m,'A +1 A','red'),(array.b_x_m,'B −1 A','blue')):
                ax.plot(source,0,'v',color=color,clip_on=False)
                if row==0:
                    ax.annotate(label_,(source,0),xytext=(0,-9),textcoords='offset points',
                                ha='center',va='top',color=color,fontsize=9)
        # Unit arrows show direction; the color bar shows magnitude.
        xx,zz=np.meshgrid(s.x,s.z);stride=(slice(None,None,5),slice(None,None,6))
        magnitude=np.maximum(currents[col],np.finfo(float).tiny)
        axes[3,col].quiver(xx[stride],zz[stride],(s.jx/magnitude)[stride],(s.jz/magnitude)[stride],
                           angles='xy',scale_units='xy',scale=.32,color='cyan',width=.002)
        axes[3,col].set_title(f'{name}: current magnitude\nUnit arrows show direction',fontsize=11)
        report['cases'][name] = {
            'tunnel_resistivity_ohm_m':rho,
            'max_abs_secondary_V':float(np.max(abs(s.secondary_potential))),
            'max_relative_mode_residual':s.max_relative_mode_residual,
            'max_relative_mode_balance_error':s.max_relative_mode_balance_error,
            'wavenumber_count':len(s.wavenumbers_per_m),
            'elapsed_seconds':s.elapsed_seconds,
        }
    fig.suptitle('2.5D surface source/return pair; conductivity invariant along y\n'
                 'Flat insulating surface away from A/B; primary values at side/bottom walls')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    fig.savefig(args.output_dir/'source_pair_comparison.png',dpi=150)
    plt.close(fig)
    (args.output_dir/'diagnostics.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    print(f'Saved comparison and diagnostics to {args.output_dir}')


if __name__=='__main__':
    main()
