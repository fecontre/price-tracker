from .base import BaseScraper, ProductPrice


class MercadoLibreScraper(BaseScraper):
    store_name = "MercadoLibre"

    def __init__(self, page):
        self.page = page

    async def scrape_url(self, url: str) -> ProductPrice:
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(2000)
            name = await self._get_text(self.page, ["h1.ui-pdp-title", "h1"])
            price = await self._get_price(self.page, [
                ".ui-pdp-price__second-line .andes-money-amount__fraction",
                ".andes-money-amount__fraction",
            ])
            original = await self._get_price(self.page, [
                ".ui-pdp-price__original-value .andes-money-amount__fraction",
            ])
            return ProductPrice(store=self.store_name, product_name=name or url, url=url, price=price, original_price=original)
        except Exception as e:
            return ProductPrice(store=self.store_name, product_name=url, url=url, price=None, error=str(e))

    async def search_product(self, query: str) -> list[ProductPrice]:
        try:
            await self.page.goto(f"https://listado.mercadolibre.cl/{query.replace(' ', '-')}", wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(2000)
            links = await self.page.eval_on_selector_all("a.ui-search-link", "els => [...new Set(els.map(e=>e.href))].slice(0,3)")
            return [await self.scrape_url(l) for l in links[:3]]
        except Exception as e:
            return [ProductPrice(store=self.store_name, product_name=query, url="", price=None, error=str(e))]
