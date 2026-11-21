"""Field/survey figures: python -m tunnel_resistivity.visualization_demo."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np

from .fields import FieldRequest,default_measurement_index,solve_field_request
from .survey_plotting import build_field_figure,build_surface_figure,build_survey_map
from .survey_simulation import SurveyParameters,plan_simulation,run_survey_plan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=Path('outputs/visualizations_2p5d'))
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    report=[]
    for material,rho in (('homogeneous',100.),('air',1e8),('water',5.)):
        result=run_survey_plan(plan_simulation(SurveyParameters(tunnel_resistivity=rho)))
        index=default_measurement_index(result)
        field=solve_field_request(FieldRequest(result,index))
        for name,figure in (('fields',build_field_figure(field)),('surface',build_surface_figure(field)),
                            ('survey_map',build_survey_map(result,index))):
            figure.savefig(args.output_dir/f'{material}_{name}.png',dpi=160)
            figure.savefig(args.output_dir/f'{material}_{name}.pdf')
        s=field.solution;measurement=field.measurement
        np.savez_compressed(args.output_dir/f'{material}_selected_fields.npz',x_m=s.x,z_m=s.z,
                            conductivity_S_m=s.conductivity,potential_V=s.potential,
                            primary_potential_V=s.primary_potential,secondary_potential_V=s.secondary_potential,
                            jx_A_m2=s.jx,jz_A_m2=s.jz)
        record={'material':material,'parameters':asdict(result.plan.parameters),'grid':asdict(result.plan.grid),
                'measurement_id':index+1,'electrodes_x_m':field.request.electrodes.positions_x_m,
                'current_A':field.request.electrodes.current_a,'voltage_V':measurement.voltage_v,
                'secondary_voltage_V':measurement.secondary_voltage_v,
                'apparent_resistivity_ohm_m':measurement.apparent_resistivity_ohm_m,
                'max_relative_mode_residual':s.max_relative_mode_residual,
                'max_relative_mode_balance_error':s.max_relative_mode_balance_error,
                'n_wavenumbers':result.data.n_wavenumbers,'k_min_per_m':result.data.k_min_per_m,
                'k_max_per_m':result.data.k_max_per_m,'conductivity_sha256':result.data.conductivity_sha256}
        report.append(record)
        print(f'{material}: measurement {index+1}, ρa={measurement.apparent_resistivity_ohm_m:.9f} Ω·m; '
              f'secondary receiver voltage={measurement.secondary_voltage_v:.9g} V',flush=True)
    (args.output_dir/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Saved field/surface/configuration PNG/PDF figures, selected-field arrays and summary to {args.output_dir}')


if __name__=='__main__':main()
