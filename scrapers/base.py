from dataclasses import dataclass, field
from datetime import date
from typing import Optional
from abc import ABC, abstractmethod


@dataclass
class ProductPrice:
    store: str
    product_name: str
    url: str
    price: Optional[float]
    original_price: Optional[float] = None
    currency: str = "CLP"
    date: str = field(default_factory=lambda: str(date.today()))
    error: Optional[str] = None


class BaseScraper(ABC):
    store_name: str = ""

    @abstractmethod
    async def scrape_url(self, url: str) -> ProductPrice:
        pass

    @abstractmethod
    async def search_product(self, query: str) -> list[ProductPrice]:
        pass

    async def _get_text(self, page, selectors: list[str]) -> str:
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    text = await el.inner_text()
                    if text.strip():
                        return text.strip()
            except Exception:
                pass
        return ""

    async def _get_price(self, page, selectors: list[str]) -> Optional[float]:
        import re
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    text = await el.inner_text()
                    cleaned = re.sub(r"[^\d]", "", text)
                    if cleaned:
                        return float(cleaned)
            except Exception:
                pass
        return None
