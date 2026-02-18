from .falabella import FalabellaScraper
from .ripley import RipleyScraper
from .paris import ParisScraper
from .mercadolibre import MercadoLibreScraper
from .sodimac import SodimacScraper
from .easy import EasyScraper
from .travelclub import TravelClubScraper

SCRAPERS = {
    "falabella": FalabellaScraper,
    "ripley": RipleyScraper,
    "paris": ParisScraper,
    "mercadolibre": MercadoLibreScraper,
    "sodimac": SodimacScraper,
    "easy": EasyScraper,
    "travelclub": TravelClubScraper,
}
