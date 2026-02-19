import httpx
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class ProductPrice:
    store: str
    product_name: str
    url: str
    price: Optional[float]
    original_price: Optional[float] = None
    currency: str = "CLP"
    date: str = field(default_factory=lambda: str(date.today()))
    sku: Optional[str] = None
    error: Optional[str] = None


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-CL,es;q=0.9",
}


async def fetch(url: str, params: dict = None, headers: dict = None) -> dict | list | None:
    h = {**HEADERS, **(headers or {})}
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        r = await client.get(url, params=params, headers=h)
        r.raise_for_status()
        return r.json()
