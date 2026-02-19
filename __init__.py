from . import falabella, ripley, paris, mercadolibre, sodimac, easy
from .base import ProductPrice

STORES = {
    "falabella": falabella,
    "ripley": ripley,
    "paris": paris,
    "mercadolibre": mercadolibre,
    "sodimac": sodimac,
    "easy": easy,
}

STORE_LABELS = {
    "falabella": "Falabella",
    "ripley": "Ripley",
    "paris": "Paris",
    "mercadolibre": "MercadoLibre",
    "sodimac": "Sodimac",
    "easy": "Easy",
}

STORE_COLORS = {
    "falabella": "#7cb242",
    "ripley": "#7b2d8b",
    "paris": "#e4002b",
    "mercadolibre": "#ffe600",
    "sodimac": "#0070c0",
    "easy": "#ff6600",
}
