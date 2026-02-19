import asyncio
import logging
from datetime import date
from scrapers import STORES
from scrapers.base import ProductPrice
import db

log = logging.getLogger(__name__)


async def scrape_product(product: dict) -> list[ProductPrice]:
    results = []
    urls = product.get("urls", {})
    query = product.get("search_query", "").strip()
    name = product["name"]

    tasks = []
    store_keys = []

    for store_key, module in STORES.items():
        url = urls.get(store_key, "").strip()
        if url:
            tasks.append(module.scrape_url(url, name))
            store_keys.append(store_key)
        elif query:
            tasks.append(_search_first(module, query, name))
            store_keys.append(store_key)

    if tasks:
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        for outcome in outcomes:
            if isinstance(outcome, Exception):
                results.append(ProductPrice(store="unknown", product_name=name,
                                            url="", price=None, error=str(outcome)))
            elif isinstance(outcome, list):
                results.extend(outcome)
            else:
                results.append(outcome)

    return results


async def _search_first(module, query: str, name: str) -> ProductPrice:
    found = await module.search(query, limit=1)
    if found:
        r = found[0]
        r.product_name = name
        return r
    return ProductPrice(store=module.STORE, product_name=name, url="", price=None, error="Sin resultados")


async def run_all() -> dict:
    db.init()
    products = db.get_products()
    if not products:
        log.warning("No hay productos configurados")
        return {"scraped": 0, "prices": 0, "errors": 0}

    total_prices = 0
    total_errors = 0

    # Scrape todos los productos en paralelo (por producto), secuencial por tienda
    for product in products:
        log.info(f"Scrapeando: {product['name']}")
        try:
            prices = await scrape_product(product)
            db.save_prices(product["id"], prices)
            ok = sum(1 for p in prices if p.price)
            err = sum(1 for p in prices if p.error)
            total_prices += ok
            total_errors += err
            log.info(f"  {ok} precios obtenidos, {err} errores")
        except Exception as e:
            log.error(f"  Error: {e}")
            total_errors += 1

    return {
        "scraped": len(products),
        "prices": total_prices,
        "errors": total_errors,
        "date": str(date.today()),
    }
