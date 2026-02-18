import asyncio
import logging
from playwright.async_api import async_playwright
from scrapers import SCRAPERS
from scrapers.base import ProductPrice
import db

log = logging.getLogger(__name__)


async def run_tracker() -> list[ProductPrice]:
    db.init_db()
    products = db.get_products()

    if not products:
        log.warning("No hay productos configurados. Agrega productos desde el panel web.")
        return []

    all_results: list[ProductPrice] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="es-CL",
        )
        page = await context.new_page()

        for product in products:
            log.info(f"Procesando: {product['name']}")
            for store, ScraperClass in SCRAPERS.items():
                scraper = ScraperClass(page)
                url = product["urls"].get(store, "").strip()
                query = product.get("search_query", "")

                try:
                    if url:
                        result = await scraper.scrape_url(url)
                        result.product_name = product["name"]
                        all_results.append(result)
                    elif query:
                        found = await scraper.search_product(query)
                        for r in found[:1]:
                            r.product_name = product["name"]
                            all_results.append(r)
                except Exception as e:
                    log.error(f"  [{store}] error: {e}")
                    all_results.append(ProductPrice(
                        store=store, product_name=product["name"],
                        url=url or "", price=None, error=str(e)
                    ))

                await page.wait_for_timeout(1200)

        await browser.close()

    db.save_prices(all_results)
    ok = sum(1 for r in all_results if r.price)
    log.info(f"Completado: {ok}/{len(all_results)} precios obtenidos")
    return all_results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_tracker())
