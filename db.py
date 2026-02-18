import sqlite3
import os
from pathlib import Path
from scrapers.base import ProductPrice

# Cloud Run con volumen montado en /data, local usa carpeta del proyecto
DB_PATH = Path(os.environ.get("DB_PATH", "/data/prices.db"))


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            search_query TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER REFERENCES products(id),
            store TEXT NOT NULL,
            url TEXT NOT NULL,
            UNIQUE(product_id, store)
        );

        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            store TEXT NOT NULL,
            product_name TEXT NOT NULL,
            url TEXT,
            price REAL,
            original_price REAL,
            currency TEXT DEFAULT 'CLP',
            error TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);
        CREATE INDEX IF NOT EXISTS idx_prices_store ON prices(store);
        CREATE INDEX IF NOT EXISTS idx_prices_product ON prices(product_name);
    """)
    conn.commit()
    conn.close()


def save_prices(prices: list[ProductPrice]):
    conn = get_conn()
    conn.executemany("""
        INSERT INTO prices (date, store, product_name, url, price, original_price, currency, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [(p.date, p.store, p.product_name, p.url, p.price, p.original_price, p.currency, p.error)
          for p in prices])
    conn.commit()
    conn.close()


def get_products() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT id, name, search_query FROM products ORDER BY name").fetchall()
    result = []
    for pid, name, query in rows:
        urls = dict(conn.execute(
            "SELECT store, url FROM urls WHERE product_id=?", (pid,)
        ).fetchall())
        result.append({"id": pid, "name": name, "search_query": query, "urls": urls})
    conn.close()
    return result


def add_product(name: str, search_query: str = "", urls: dict = None) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT OR IGNORE INTO products (name, search_query) VALUES (?, ?)",
        (name, search_query)
    )
    product_id = cur.lastrowid or conn.execute(
        "SELECT id FROM products WHERE name=?", (name,)
    ).fetchone()[0]
    if urls:
        for store, url in urls.items():
            if url:
                conn.execute(
                    "INSERT OR REPLACE INTO urls (product_id, store, url) VALUES (?, ?, ?)",
                    (product_id, store, url)
                )
    conn.commit()
    conn.close()
    return product_id


def delete_product(product_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM urls WHERE product_id=?", (product_id,))
    conn.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()


def get_price_history(product_name: str = None, days: int = 30) -> list[dict]:
    conn = get_conn()
    query = """
        SELECT date, store, product_name, price, original_price, url, error
        FROM prices
        WHERE date >= date('now', ? )
    """
    params = [f"-{days} days"]
    if product_name:
        query += " AND product_name LIKE ?"
        params.append(f"%{product_name}%")
    query += " ORDER BY date DESC, store"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [
        {"date": r[0], "store": r[1], "product_name": r[2],
         "price": r[3], "original_price": r[4], "url": r[5], "error": r[6]}
        for r in rows
    ]


def get_latest_prices() -> list[dict]:
    """Último precio registrado por producto y tienda."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT p1.date, p1.store, p1.product_name, p1.price, p1.original_price, p1.url
        FROM prices p1
        INNER JOIN (
            SELECT store, product_name, MAX(date) as max_date
            FROM prices
            GROUP BY store, product_name
        ) p2 ON p1.store = p2.store
            AND p1.product_name = p2.product_name
            AND p1.date = p2.max_date
        WHERE p1.price IS NOT NULL
        ORDER BY p1.product_name, p1.price
    """).fetchall()
    conn.close()
    return [
        {"date": r[0], "store": r[1], "product_name": r[2],
         "price": r[3], "original_price": r[4], "url": r[5]}
        for r in rows
    ]


def get_summary_stats() -> dict:
    conn = get_conn()
    total_records = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
    total_products = conn.execute("SELECT COUNT(DISTINCT product_name) FROM prices").fetchone()[0]
    last_run = conn.execute("SELECT MAX(date) FROM prices").fetchone()[0]
    stores = conn.execute("SELECT DISTINCT store FROM prices ORDER BY store").fetchall()
    conn.close()
    return {
        "total_records": total_records,
        "total_products": total_products,
        "last_run": last_run,
        "stores": [s[0] for s in stores],
    }
