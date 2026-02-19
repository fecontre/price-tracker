import sqlite3
import os
import json
from pathlib import Path
from scrapers.base import ProductPrice

DB_PATH = Path(os.environ.get("DB_PATH", "/tmp/retailscope.db"))


def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    c = conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT '',
            is_own INTEGER DEFAULT 0,
            search_query TEXT DEFAULT '',
            urls TEXT DEFAULT '{}',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
            date TEXT NOT NULL,
            store TEXT NOT NULL,
            price REAL,
            original_price REAL,
            url TEXT,
            sku TEXT,
            error TEXT,
            scraped_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_prices_product_date ON prices(product_id, date);
        CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);
    """)
    c.commit()
    c.close()


# ── Products ──────────────────────────────────────────────
def get_products(active_only=True) -> list[dict]:
    c = conn()
    q = "SELECT * FROM products"
    if active_only:
        q += " WHERE active=1"
    q += " ORDER BY is_own DESC, name"
    rows = [dict(r) for r in c.execute(q).fetchall()]
    c.close()
    for r in rows:
        r["urls"] = json.loads(r.get("urls") or "{}")
    return rows


def get_product(pid: int) -> dict | None:
    c = conn()
    row = c.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    c.close()
    if not row:
        return None
    r = dict(row)
    r["urls"] = json.loads(r.get("urls") or "{}")
    return r


def add_product(name: str, category: str = "", is_own: bool = False,
                search_query: str = "", urls: dict = None) -> int:
    c = conn()
    cur = c.execute(
        "INSERT INTO products (name, category, is_own, search_query, urls) VALUES (?,?,?,?,?)",
        (name, category, int(is_own), search_query, json.dumps(urls or {}))
    )
    pid = cur.lastrowid
    c.commit()
    c.close()
    return pid


def update_product(pid: int, **fields):
    if "urls" in fields:
        fields["urls"] = json.dumps(fields["urls"])
    if "is_own" in fields:
        fields["is_own"] = int(fields["is_own"])
    sets = ", ".join(f"{k}=?" for k in fields)
    c = conn()
    c.execute(f"UPDATE products SET {sets} WHERE id=?", (*fields.values(), pid))
    c.commit()
    c.close()


def delete_product(pid: int):
    c = conn()
    c.execute("DELETE FROM products WHERE id=?", (pid,))
    c.commit()
    c.close()


# ── Prices ────────────────────────────────────────────────
def save_prices(product_id: int, prices: list[ProductPrice]):
    c = conn()
    c.executemany("""
        INSERT INTO prices (product_id, date, store, price, original_price, url, sku, error)
        VALUES (?,?,?,?,?,?,?,?)
    """, [(product_id, p.date, p.store, p.price, p.original_price, p.url, p.sku, p.error)
          for p in prices])
    c.commit()
    c.close()


def get_latest_prices(product_id: int) -> list[dict]:
    c = conn()
    rows = c.execute("""
        SELECT p1.* FROM prices p1
        INNER JOIN (
            SELECT store, MAX(date) as md FROM prices WHERE product_id=? GROUP BY store
        ) p2 ON p1.store=p2.store AND p1.date=p2.md AND p1.product_id=?
        WHERE p1.price IS NOT NULL
        ORDER BY p1.price
    """, (product_id, product_id)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_price_history(product_id: int, store: str = None, days: int = 90) -> list[dict]:
    c = conn()
    q = """
        SELECT date, store, MIN(price) as price, MIN(original_price) as original_price
        FROM prices
        WHERE product_id=? AND date >= date('now', ?) AND price IS NOT NULL
    """
    params = [product_id, f"-{days} days"]
    if store:
        q += " AND store=?"
        params.append(store)
    q += " GROUP BY date, store ORDER BY date"
    rows = c.execute(q, params).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_dashboard_stats() -> dict:
    c = conn()
    stats = {
        "total_products": c.execute("SELECT COUNT(*) FROM products WHERE active=1").fetchone()[0],
        "own_products": c.execute("SELECT COUNT(*) FROM products WHERE active=1 AND is_own=1").fetchone()[0],
        "competitor_products": c.execute("SELECT COUNT(*) FROM products WHERE active=1 AND is_own=0").fetchone()[0],
        "last_scrape": c.execute("SELECT MAX(date) FROM prices").fetchone()[0],
        "total_price_records": c.execute("SELECT COUNT(*) FROM prices").fetchone()[0],
    }
    c.close()
    return stats


def get_categories() -> list[str]:
    c = conn()
    rows = c.execute("SELECT DISTINCT category FROM products WHERE category!='' ORDER BY category").fetchall()
    c.close()
    return [r[0] for r in rows]


def get_price_alerts(threshold_pct: float = 5.0) -> list[dict]:
    """Productos donde el precio bajó más de X% en las últimas 24h."""
    c = conn()
    rows = c.execute("""
        SELECT p.name, pr.store, pr.price as new_price, prev.price as old_price,
               ROUND((1 - pr.price/prev.price)*100, 1) as drop_pct
        FROM prices pr
        JOIN prices prev ON pr.product_id=prev.product_id AND pr.store=prev.store
            AND prev.date = date(pr.date, '-1 day')
        JOIN products p ON p.id=pr.product_id
        WHERE pr.date = date('now')
          AND pr.price IS NOT NULL AND prev.price IS NOT NULL
          AND pr.price < prev.price
          AND (1 - pr.price/prev.price)*100 >= ?
        ORDER BY drop_pct DESC
    """, (threshold_pct,)).fetchall()
    c.close()
    return [dict(r) for r in rows]
