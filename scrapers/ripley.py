from .base import fetch, ProductPrice
import re

STORE = "Ripley"


async def search(query: str, limit: int = 5) -> list[ProductPrice]:
    results = []
    try:
        data = await fetch(
            "https://simple.ripley.cl/api/2.0/page/search/",
            params={"q": query, "page": 1, "per_page": limit}
        )
        items = data.get("results", [])
        for item in items[:limit]:
            prices = item.get("prices", {})
            price = prices.get("sale_price") or prices.get("base_price")
            original = prices.get("base_price") if prices.get("sale_price") else None
            url = "https://simple.ripley.cl" + item.get("url", "")
            results.append(ProductPrice(
                store=STORE,
                product_name=item.get("name", query),
                url=url,
                price=float(price) if price else None,
                original_price=float(original) if original else None,
                sku=item.get("sku", ""),
            ))
    except Exception as e:
        results.append(ProductPrice(store=STORE, product_name=query, url="", price=None, error=str(e)))
    return results


async def scrape_url(url: str, product_name: str = "") -> ProductPrice:
    try:
        slug = url.rstrip("/").split("/")[-1]
        data = await fetch(f"https://simple.ripley.cl/api/2.0/products/{slug}/")
        prices = data.get("prices", {})
        price = prices.get("sale_price") or prices.get("base_price")
        original = prices.get("base_price") if prices.get("sale_price") else None
        return ProductPrice(
            store=STORE,
            product_name=product_name or data.get("name", url),
            url=url,
            price=float(price) if price else None,
            original_price=float(original) if original else None,
            sku=data.get("sku", ""),
        )
    except Exception as e:
        return ProductPrice(store=STORE, product_name=product_name or url, url=url, price=None, error=str(e))
