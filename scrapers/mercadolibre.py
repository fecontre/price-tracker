from .base import fetch, ProductPrice

STORE = "MercadoLibre"
SITE = "MLC"  # Chile


async def search(query: str, limit: int = 5) -> list[ProductPrice]:
    results = []
    try:
        data = await fetch(
            f"https://api.mercadolibre.com/sites/{SITE}/search",
            params={"q": query, "limit": limit}
        )
        for item in data.get("results", [])[:limit]:
            price = item.get("price")
            original = item.get("original_price")
            results.append(ProductPrice(
                store=STORE,
                product_name=item.get("title", query),
                url=item.get("permalink", ""),
                price=float(price) if price else None,
                original_price=float(original) if original else None,
                sku=item.get("id", ""),
            ))
    except Exception as e:
        results.append(ProductPrice(store=STORE, product_name=query, url="", price=None, error=str(e)))
    return results


async def scrape_url(url: str, product_name: str = "") -> ProductPrice:
    try:
        # Extraer el ID del item de la URL
        import re
        match = re.search(r"MLC-?(\d+)", url)
        if not match:
            raise ValueError("No se encontró ID de MercadoLibre en la URL")
        item_id = f"MLC{match.group(1)}"
        data = await fetch(f"https://api.mercadolibre.com/items/{item_id}")
        price = data.get("price")
        original = data.get("original_price")
        return ProductPrice(
            store=STORE,
            product_name=product_name or data.get("title", url),
            url=url,
            price=float(price) if price else None,
            original_price=float(original) if original else None,
            sku=item_id,
        )
    except Exception as e:
        return ProductPrice(store=STORE, product_name=product_name or url, url=url, price=None, error=str(e))
