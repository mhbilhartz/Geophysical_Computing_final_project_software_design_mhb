"""Nine static A/B/M/N examples: python -m tunnel_resistivity.receiver_demo.

A comparison of single measurements, not an automatically generated survey.
"""
import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from .electrodes import wenner, schlumberger, dipole_dipole
from .geometry import circular_tunnel
from .receivers import measure_receivers
from .solver_2p5d import solve_source_pair


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=Path('outputs/receivers_2p5d'))
    args=parser.parse_args()
    width,height,nx,nz=200.,100.,160,80
    center,depth,radius=100.,15.,5.
    arrays=(wenner(center_x_m=center,spacing_m=10),
            schlumberger(center_x_m=center,ab_half_spacing_m=20,mn_half_spacing_m=2),
            dipole_dipole(center_x_m=center,spacing_m=5,separation_n=2))
    cases=(('Homogeneous',100.),('Air approximation',1e8),('Water approximation',5.))
    rows=[]
    for material,rho in cases:
        sigma,_=circular_tunnel(width=width,height=height,nx=nx,nz=nz,
                                center_x=center,depth=depth,radius=radius,
                                host_resistivity=100,tunnel_resistivity=rho)
        for array in arrays:
            solution=solve_source_pair(sigma,array,width=width,height=height)
            datum=measure_receivers(solution)
            row=dict(material=material,array_type=array.array_type,
                     width_m=width,height_m=height,nx=nx,nz=nz,
                     tunnel_center_x_m=center,tunnel_depth_m=depth,tunnel_radius_m=radius,
                     host_resistivity_ohm_m=100.,tunnel_resistivity_ohm_m=rho,
                     current_a=array.current_a,a_x_m=array.a_x_m,b_x_m=array.b_x_m,
                     m_x_m=array.m_x_m,n_x_m=array.n_x_m,
                     potential_m_v=datum.potential_m_v,potential_n_v=datum.potential_n_v,
                     voltage_v=datum.voltage_v,primary_voltage_v=datum.primary_voltage_v,
                     secondary_voltage_v=datum.secondary_voltage_v,
                     geometric_factor_m=datum.geometric_factor_m,
                     transfer_resistance_ohm=datum.transfer_resistance_ohm,
                     apparent_resistivity_ohm_m=datum.apparent_resistivity_ohm_m,
                     apparent_resistivity_anomaly_ohm_m=datum.apparent_resistivity_anomaly_ohm_m,
                     relative_apparent_resistivity_anomaly=datum.relative_apparent_resistivity_anomaly,
                     max_relative_mode_residual=solution.max_relative_mode_residual,
                     max_relative_mode_balance_error=solution.max_relative_mode_balance_error,
                     n_wavenumbers=len(solution.wavenumbers_per_m),
                     k_min_per_m=1e-6/max(width,height),k_max_per_m=20/min(solution.dx,solution.dz),
                     elapsed_seconds=solution.elapsed_seconds)
            rows.append(row)
            print(f'{material:20s} {array.array_type:15s} '
                  f'ΔV={datum.voltage_v:+.8f} V  K={datum.geometric_factor_m:+.5f} m  '
                  f'ρa={datum.apparent_resistivity_ohm_m:.6f} Ω·m',flush=True)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    with (args.output_dir/'measurements.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (args.output_dir/'measurements.json').write_text(json.dumps(rows,indent=2)+'\n')
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    labels=[array.array_type for array in arrays];positions=np.arange(len(arrays))
    for case_index,(material,_) in enumerate(cases):
        selected=[row for row in rows if row['material']==material]
        rhoa=[row['apparent_resistivity_ohm_m'] for row in selected]
        anomalies=[100*row['relative_apparent_resistivity_anomaly'] for row in selected]
        for ax,values in zip(axes,(rhoa,anomalies)):
            ax.bar(positions+(case_index-1)*.24,values,width=.24,label=material)
    for ax in axes:
        ax.set_xticks(positions,labels);ax.set_xlabel('Array configuration')
    handles,legend_labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,legend_labels,loc='outside lower center',ncol=3,frameon=False)
    axes[0].axhline(100,color='gray',linestyle='--',linewidth=.8)
    axes[0].set(ylabel='Apparent resistivity (Ω·m)',title='Single-measurement forward responses')
    axes[1].axhline(0,color='gray',linewidth=.8)
    axes[1].set(ylabel='Apparent resistivity anomaly (%)',title='Relative to the 100 Ω·m host')
    fig.suptitle('2.5D point electrodes: tunnel center depth 15 m, radius 5 m\n'
                 'Different array spreads sample different sensitivity patterns')
    fig.savefig(args.output_dir/'apparent_resistivity_comparison.png',dpi=150)
    plt.close(fig)
    print(f'Saved CSV, JSON, and comparison figure to {args.output_dir}')


if __name__=='__main__':
    main()
