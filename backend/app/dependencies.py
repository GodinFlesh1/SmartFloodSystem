from app.services.ea_api import EnvironmentAgencyService
from app.services.risk_calculator import RiskCalculator
from app.services.flood_predictor import FloodPredictor
from app.services.route_service import RouteService

ea_service = EnvironmentAgencyService()
risk_calc = RiskCalculator()
predictor = FloodPredictor()
route_service = RouteService()
