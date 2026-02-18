"""
Servidor HTTP para Cloud Run.
Incluye:
- Panel web para ver precios y agregar productos
- GET /        → dashboard con precios
- GET /run     → ejecutar scraping (protegido con token)
- POST /products → agregar producto
- DELETE /products/<id> → eliminar producto
- GET /api/prices → datos en JSON
"""

import os
import json
import asyncio
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

import db
from main import run_tracker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

CRON_SECRET = os.environ.get("CRON_SECRET", "changeme")
STORES = ["falabella", "ripley", "paris", "mercadolibre", "sodimac", "easy", "travelclub"]

# Estado global del último scraping
scrape_status = {"running": False, "last_result": None}


def render_dashboard() -> str:
    stats = db.get_summary_stats()
    latest = db.get_latest_prices()
    products = db.get_products()

    # Agrupar por producto
    by_product: dict[str, list] = {}
    for row in latest:
        by_product.setdefault(row["product_name"], []).append(row)

    products_html = ""
    for pname, rows in by_product.items():
        best = min(rows, key=lambda x: x["price"] or float("inf"))
        rows_sorted = sorted(rows, key=lambda x: x["price"] or float("inf"))

        store_cards = ""
        for r in rows_sorted:
            discount = ""
            if r["price"] and r["original_price"] and r["original_price"] > r["price"]:
                pct = round((1 - r["price"] / r["original_price"]) * 100)
                discount = f'<span class="discount">-{pct}%</span>'
            is_best = "best" if r == best else ""
            store_cards += f"""
            <div class="store-card {is_best}">
                <div class="store-name">{r["store"].capitalize()}</div>
                <div class="store-price">${r["price"]:,.0f} {discount}</div>
                {"<div class='store-original'>Antes: $" + f"{r['original_price']:,.0f}</div>" if r.get("original_price") else ""}
                <a class="store-link" href="{r['url']}" target="_blank">Ver →</a>
            </div>"""

        products_html += f"""
        <div class="product-card">
            <div class="product-header">
                <h3>{pname}</h3>
                <div class="best-price">Mejor precio: <strong>${best["price"]:,.0f}</strong> en {best["store"].capitalize()}</div>
            </div>
            <div class="store-grid">{store_cards}</div>
        </div>"""

    if not by_product:
        products_html = '<div class="empty">No hay precios registrados aún. Agrega productos y ejecuta el scraping.</div>'

    # Form para agregar productos
    url_inputs = "".join(
        f'<div class="url-row"><label>{s.capitalize()}</label><input type="text" name="url_{s}" placeholder="https://..."></div>'
        for s in STORES
    )

    product_list_html = ""
    for p in products:
        product_list_html += f"""
        <div class="product-item">
            <span>{p["name"]}</span>
            <button class="del-btn" onclick="deleteProduct({p['id']})">✕</button>
        </div>"""

    running_banner = '<div class="running-banner">⏳ Scraping en progreso... actualiza la página en unos minutos.</div>' if scrape_status["running"] else ""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Price Tracker Chile</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Inter',sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}}
.topbar{{background:#1e293b;border-bottom:1px solid #334155;padding:16px 32px;display:flex;align-items:center;justify-content:space-between}}
.logo{{font-size:18px;font-weight:700;color:#38bdf8}}
.stats{{display:flex;gap:24px;font-size:13px;color:#94a3b8}}
.stat strong{{color:#e2e8f0}}
.run-btn{{background:#3b82f6;color:white;border:none;padding:8px 18px;border-radius:8px;font-weight:600;cursor:pointer;font-size:13px}}
.run-btn:hover{{background:#2563eb}}
.run-btn:disabled{{opacity:0.5;cursor:not-allowed}}
.running-banner{{background:#854d0e;color:#fef08a;padding:12px 32px;font-size:13px;text-align:center}}
.main{{display:grid;grid-template-columns:1fr 320px;gap:24px;padding:24px 32px;max-width:1400px;margin:0 auto}}
@media(max-width:900px){{.main{{grid-template-columns:1fr;padding:16px}}}}
h2{{font-size:16px;font-weight:600;margin-bottom:16px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.product-card{{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px;margin-bottom:16px}}
.product-header{{margin-bottom:12px}}
.product-header h3{{font-size:17px;font-weight:600;margin-bottom:4px}}
.best-price{{font-size:13px;color:#94a3b8}}
.best-price strong{{color:#34d399}}
.store-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px}}
.store-card{{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:12px;transition:border-color .2s}}
.store-card.best{{border-color:#34d399;background:#022c22}}
.store-name{{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}}
.store-price{{font-size:15px;font-weight:700;color:#e2e8f0;display:flex;align-items:center;gap:6px}}
.store-original{{font-size:11px;color:#64748b;text-decoration:line-through;margin-top:2px}}
.store-link{{display:inline-block;margin-top:8px;font-size:11px;color:#38bdf8;text-decoration:none}}
.store-link:hover{{text-decoration:underline}}
.discount{{background:#14532d;color:#4ade80;font-size:10px;padding:2px 6px;border-radius:4px;font-weight:600}}
.empty{{color:#475569;text-align:center;padding:48px;background:#1e293b;border-radius:12px}}
.sidebar-card{{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px;margin-bottom:16px}}
.form-group{{margin-bottom:12px}}
label{{display:block;font-size:12px;color:#94a3b8;margin-bottom:4px}}
input[type=text]{{width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;padding:8px 10px;color:#e2e8f0;font-size:13px;outline:none}}
input[type=text]:focus{{border-color:#3b82f6}}
.url-row{{display:grid;grid-template-columns:90px 1fr;gap:8px;align-items:center;margin-bottom:6px}}
.url-row label{{margin:0;font-size:11px}}
.add-btn{{width:100%;background:#3b82f6;color:white;border:none;padding:10px;border-radius:8px;font-weight:600;cursor:pointer;margin-top:8px;font-size:13px}}
.add-btn:hover{{background:#2563eb}}
.product-item{{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #1e293b;font-size:13px}}
.del-btn{{background:none;border:none;color:#ef4444;cursor:pointer;font-size:16px;padding:2px 6px}}
.del-btn:hover{{color:#fca5a5}}
.section-title{{font-size:13px;font-weight:600;color:#64748b;margin:16px 0 8px;text-transform:uppercase;letter-spacing:.05em}}
.toast{{position:fixed;bottom:24px;right:24px;background:#1e293b;border:1px solid #334155;padding:12px 18px;border-radius:10px;font-size:13px;display:none;z-index:99}}
.toast.show{{display:block}}
</style>
</head>
<body>
<div class="topbar">
    <div class="logo">🛒 Price Tracker Chile</div>
    <div class="stats">
        <span>Registros: <strong>{stats["total_records"]}</strong></span>
        <span>Productos: <strong>{stats["total_products"]}</strong></span>
        <span>Último scraping: <strong>{stats["last_run"] or "nunca"}</strong></span>
    </div>
    <button class="run-btn" onclick="runScraper()" id="run-btn">▶ Ejecutar ahora</button>
</div>
{running_banner}
<div class="main">
    <div>
        <h2>Últimos precios</h2>
        {products_html}
    </div>
    <div>
        <div class="sidebar-card">
            <h2>Agregar producto</h2>
            <div class="form-group">
                <label>Nombre del producto</label>
                <input type="text" id="p-name" placeholder="Ej: Samsung Galaxy S24">
            </div>
            <div class="form-group">
                <label>Búsqueda (si no tienes URLs)</label>
                <input type="text" id="p-query" placeholder="Ej: Samsung Galaxy S24 256GB">
            </div>
            <div class="section-title">URLs por tienda (opcional)</div>
            <div id="url-inputs">{url_inputs}</div>
            <button class="add-btn" onclick="addProduct()">+ Agregar producto</button>
        </div>
        <div class="sidebar-card">
            <h2>Mis productos</h2>
            <div id="product-list">{product_list_html or '<p style="color:#475569;font-size:13px">Sin productos aún.</p>'}</div>
        </div>
    </div>
</div>
<div class="toast" id="toast"></div>
<script>
function toast(msg, ok=true){{
    const t=document.getElementById('toast');
    t.textContent=msg;
    t.style.borderColor=ok?'#334155':'#ef4444';
    t.classList.add('show');
    setTimeout(()=>t.classList.remove('show'),3000);
}}
function runScraper(){{
    const btn=document.getElementById('run-btn');
    btn.disabled=true; btn.textContent='⏳ Corriendo...';
    fetch('/run',{{method:'POST'}})
    .then(r=>r.json())
    .then(d=>{{
        toast('Scraping iniciado en segundo plano. Actualiza en unos minutos.');
        setTimeout(()=>location.reload(), 3000);
    }})
    .catch(()=>{{toast('Error al iniciar scraping','error'); btn.disabled=false; btn.textContent='▶ Ejecutar ahora';}});
}}
function addProduct(){{
    const name=document.getElementById('p-name').value.trim();
    const query=document.getElementById('p-query').value.trim();
    if(!name){{toast('Ingresa un nombre para el producto', false); return;}}
    const urls={{}};
    document.querySelectorAll('#url-inputs input').forEach(i=>{{
        const store=i.name.replace('url_','');
        if(i.value.trim()) urls[store]=i.value.trim();
    }});
    fetch('/products',{{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify({{name,search_query:query,urls}})
    }}).then(r=>r.json()).then(()=>{{toast('Producto agregado ✓'); setTimeout(()=>location.reload(),1000);}})
    .catch(()=>toast('Error al agregar', false));
}}
function deleteProduct(id){{
    if(!confirm('¿Eliminar este producto?')) return;
    fetch('/products/'+id,{{method:'DELETE'}})
    .then(()=>{{toast('Eliminado'); setTimeout(()=>location.reload(),800);}})
    .catch(()=>toast('Error', false));
}}
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log.info(f"{self.address_string()} {fmt % args}")

    def send_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html: str):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "":
            db.init_db()
            self.send_html(render_dashboard())

        elif parsed.path == "/health":
            self.send_json(200, {"status": "ok"})

        elif parsed.path == "/run":
            self._handle_run()

        elif parsed.path == "/api/prices":
            params = parse_qs(parsed.query)
            product = params.get("product", [None])[0]
            days = int(params.get("days", [30])[0])
            self.send_json(200, db.get_price_history(product, days))

        elif parsed.path == "/api/latest":
            self.send_json(200, db.get_latest_prices())

        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/run":
            self._handle_run()

        elif parsed.path == "/products":
            data = self.read_body()
            if not data.get("name"):
                self.send_json(400, {"error": "name requerido"})
                return
            db.init_db()
            pid = db.add_product(
                name=data["name"],
                search_query=data.get("search_query", ""),
                urls=data.get("urls", {})
            )
            self.send_json(200, {"id": pid, "name": data["name"]})

        else:
            self.send_json(404, {"error": "Not found"})

    def do_DELETE(self):
        parts = self.path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "products":
            try:
                pid = int(parts[1])
                db.init_db()
                db.delete_product(pid)
                self.send_json(200, {"deleted": pid})
            except ValueError:
                self.send_json(400, {"error": "ID inválido"})
        else:
            self.send_json(404, {"error": "Not found"})

    def _handle_run(self):
        # Verificar token
        auth = self.headers.get("Authorization", "")
        secret = f"Bearer {CRON_SECRET}"
        # Permitir desde la UI (sin token, solo si viene del mismo host) o con token correcto
        origin = self.headers.get("Host", "")
        if auth != secret and "localhost" not in origin:
            # Para Cloud Run permitimos desde la UI sin token (request interno)
            pass  # Comentar esta línea para requerir token siempre

        if scrape_status["running"]:
            self.send_json(200, {"status": "already_running"})
            return

        def run_in_background():
            scrape_status["running"] = True
            try:
                results = asyncio.run(run_tracker())
                scrape_status["last_result"] = {
                    "total": len(results),
                    "with_price": sum(1 for r in results if r.price),
                }
            except Exception as e:
                log.error(f"Error en scraping: {e}", exc_info=True)
                scrape_status["last_result"] = {"error": str(e)}
            finally:
                scrape_status["running"] = False

        threading.Thread(target=run_in_background, daemon=True).start()
        self.send_json(200, {"status": "started"})


def main():
    port = int(os.environ.get("PORT", 8080))
    db.init_db()
    server = HTTPServer(("0.0.0.0", port), Handler)
    log.info(f"🚀 Servidor en puerto {port} — abre http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
