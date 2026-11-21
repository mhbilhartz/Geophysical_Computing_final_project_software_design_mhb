"""Original fixed-voltage model: python -m panel serve legacy_app.py --show."""
from tunnel_resistivity.app import create_app

create_app().servable(title='Original 2D fixed-voltage resistivity model')
