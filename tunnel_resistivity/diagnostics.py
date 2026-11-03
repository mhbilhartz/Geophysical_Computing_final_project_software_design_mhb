"""Conservation and anomaly diagnostics using solver face fluxes."""

import numpy as np


def diagnostics(model, reference):
    net = np.diff(model.jx, axis=1) * model.dz + np.diff(model.jz, axis=0) * model.dx
    scale = max(np.max(np.abs(model.jx)) * model.dz, np.max(np.abs(model.jz)) * model.dx)
    incoming = float(model.jx[:, 0].sum() * model.dz)
    outgoing = float(model.jx[:, -1].sum() * model.dz)
    return {
        "entering_current_A_per_m": incoming,
        "leaving_current_A_per_m": outgoing,
        "relative_boundary_current_imbalance": abs(incoming - outgoing) / abs(incoming),
        "max_cell_imbalance_over_max_face_current": float(np.max(np.abs(net)) / scale),
        "residual_inf_A_per_m": model.residual_inf,
        "potential_min_V": float(model.potential.min()),
        "potential_max_V": float(model.potential.max()),
        "max_abs_potential_anomaly_V": float(np.max(np.abs(model.potential - reference.potential))),
        "max_abs_surface_anomaly_V": float(np.max(np.abs(model.potential[0] - reference.potential[0]))),
    }
