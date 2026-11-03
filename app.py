"""Panel entry point: run `panel serve app.py --show` from this directory."""

from tunnel_resistivity.app import create_app

create_app().servable(title="2D Electrical Resistivity Simulator")
