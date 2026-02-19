from .base import fetch, ProductPrice
import re

STORE = "Sodimac"


async def search(query: str, limit: int = 5) -> list[ProductPrice]:
    results = []
    try:
        data = await fetch(
            "https://www.sodimac.cl/sodimac-cl/search/results",
            params={"Ntt": query, "No": 0, "Nrpp": limit, "sortBy": "Default", "v": "json"}
        )
        items = data.get("data", {}).get("searchResults", {}).get("resultsets", [{}])[0].get("results", [])
        for item in items[:limit]:
            prices = item.get("prices", {})
            price = prices.get("internetPrice") or prices.get("normalPrice")
            original = prices.get("normalPrice") if prices.get("internetPrice") else None
            pid = item.get("id", "")
            url = f"https://www.sodimac.cl/sodimac-cl/product/{pid}" if pid else ""
            results.append(ProductPrice(
                store=STORE,
                product_name=item.get("name", query),
                url=url,
                price=float(price) if price else None,
                original_price=float(original) if original else None,
                sku=str(pid),
            ))
    except Exception as e:
        results.append(ProductPrice(store=STORE, product_name=query, url="", price=None, error=str(e)))
    return results


async def scrape_url(url: str, product_name: str = "") -> ProductPrice:
    try:
        match = re.search(r"/product/([^/]+)", url)
        if not match:
            raise ValueError("URL no válida para Sodimac")
        pid = match.group(1)
        data = await fetch(f"https://www.sodimac.cl/sodimac-cl/product/{pid}/json")
        prices = data.get("prices", {})
        price = prices.get("internetPrice") or prices.get("normalPrice")
        original = prices.get("normalPrice") if prices.get("internetPrice") else None
        return ProductPrice(
            store=STORE,
            product_name=product_name or data.get("name", url),
            url=url,
            price=float(price) if price else None,
            original_price=float(original) if original else None,
            sku=str(pid),
        )
    except Exception as e:
        return ProductPrice(store=STORE, product_name=product_name or url, url=url, price=None, error=str(e))
