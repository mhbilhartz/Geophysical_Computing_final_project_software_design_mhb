"""Live survey entry point: python -m panel serve app.py --show."""
from tunnel_resistivity.survey_app import create_app

create_app().servable(title='2.5D Electrical Resistivity Survey Simulator')
