from .base import fetch, ProductPrice
import re

STORE = "Paris"


async def search(query: str, limit: int = 5) -> list[ProductPrice]:
    results = []
    try:
        data = await fetch(
            "https://www.paris.cl/api/catalog_system/pub/products/search/",
            params={"ft": query, "_from": 0, "_to": limit - 1}
        )
        for item in (data or [])[:limit]:
            items_data = item.get("items", [{}])
            sellers = items_data[0].get("sellers", [{}]) if items_data else [{}]
            offer = sellers[0].get("commertialOffer", {}) if sellers else {}
            price = offer.get("Price")
            original = offer.get("ListPrice")
            link = item.get("link", "")
            results.append(ProductPrice(
                store=STORE,
                product_name=item.get("productName", query),
                url=link,
                price=float(price) if price else None,
                original_price=float(original) if original and original != price else None,
                sku=item.get("productId", ""),
            ))
    except Exception as e:
        results.append(ProductPrice(store=STORE, product_name=query, url="", price=None, error=str(e)))
    return results


async def scrape_url(url: str, product_name: str = "") -> ProductPrice:
    try:
        slug = url.rstrip("/").split("/p/")[-1].split("/")[0] if "/p/" in url else url.rstrip("/").split("/")[-1]
        data = await fetch(f"https://www.paris.cl/api/catalog_system/pub/products/search/{slug}/p")
        item = data[0] if data else {}
        items_data = item.get("items", [{}])
        sellers = items_data[0].get("sellers", [{}]) if items_data else [{}]
        offer = sellers[0].get("commertialOffer", {}) if sellers else {}
        price = offer.get("Price")
        original = offer.get("ListPrice")
        return ProductPrice(
            store=STORE,
            product_name=product_name or item.get("productName", url),
            url=url,
            price=float(price) if price else None,
            original_price=float(original) if original and original != price else None,
            sku=item.get("productId", ""),
        )
    except Exception as e:
        return ProductPrice(store=STORE, product_name=product_name or url, url=url, price=None, error=str(e))
