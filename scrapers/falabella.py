from .base import fetch, ProductPrice
import re


STORE = "Falabella"


def _parse_price(val) -> float | None:
    if val is None:
        return None
    return float(re.sub(r"[^\d.]", "", str(val))) or None


async def search(query: str, limit: int = 5) -> list[ProductPrice]:
    results = []
    try:
        data = await fetch(
            "https://www.falabella.com/s/browse/v1/listing/cl",
            params={"query": query, "page": 1, "limit": limit, "zones": "RM_13_1"}
        )
        items = data.get("data", {}).get("results", [])
        for item in items[:limit]:
            prices = item.get("prices", [])
            price = None
            original = None
            for p in prices:
                label = p.get("label", "").lower()
                val = _parse_price(p.get("price"))
                if "internet" in label or "cmr" in label:
                    price = val
                elif "normal" in label:
                    original = val
            if price is None and prices:
                price = _parse_price(prices[0].get("price"))

            slug = item.get("slug", "")
            pid = item.get("id", "")
            url = f"https://www.falabella.com/falabella-cl/product/{pid}/{slug}" if pid else ""

            results.append(ProductPrice(
                store=STORE,
                product_name=item.get("displayName", query),
                url=url,
                price=price,
                original_price=original,
                sku=str(pid),
            ))
    except Exception as e:
        results.append(ProductPrice(store=STORE, product_name=query, url="", price=None, error=str(e)))
    return results


async def scrape_url(url: str, product_name: str = "") -> ProductPrice:
    # Extraer ID del producto de la URL y consultar API
    try:
        match = re.search(r"/product/(\d+)/", url)
        if not match:
            raise ValueError("URL no válida para Falabella")
        pid = match.group(1)
        data = await fetch(
            f"https://www.falabella.com/s/browse/v1/product/cl/{pid}",
            params={"zones": "RM_13_1"}
        )
        product = data.get("data", {})
        prices = product.get("prices", [])
        price = None
        original = None
        for p in prices:
            label = p.get("label", "").lower()
            val = _parse_price(p.get("price"))
            if "internet" in label or "cmr" in label:
                price = val
            elif "normal" in label:
                original = val
        if price is None and prices:
            price = _parse_price(prices[0].get("price"))

        return ProductPrice(
            store=STORE,
            product_name=product_name or product.get("displayName", url),
            url=url,
            price=price,
            original_price=original,
            sku=str(pid),
        )
    except Exception as e:
        return ProductPrice(store=STORE, product_name=product_name or url, url=url, price=None, error=str(e))
