import os, json, asyncio, logging, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import db
from main import run_all
from scrapers import STORE_LABELS, STORE_COLORS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

CRON_SECRET = os.environ.get("CRON_SECRET", "changeme")
scrape_status = {"running": False, "last": None}

# ── HTML Templates ─────────────────────────────────────────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#f0f2f7;--surface:#fff;--surface2:#f8f9fc;
  --border:#e4e8f0;--text:#0d1117;--muted:#6b7280;
  --accent:#2563eb;--accent-light:#dbeafe;
  --green:#059669;--green-light:#d1fae5;
  --red:#dc2626;--red-light:#fee2e2;
  --yellow:#d97706;--yellow-light:#fef3c7;
  --own:#7c3aed;--own-light:#ede9fe;
  --radius:10px;--shadow:0 1px 3px rgba(0,0,0,.08),0 4px 12px rgba(0,0,0,.05);
}
body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;font-size:14px}
a{color:inherit;text-decoration:none}
/* Layout */
.shell{display:flex;min-height:100vh}
.sidebar{width:220px;background:#0d1117;flex-shrink:0;display:flex;flex-direction:column;position:fixed;top:0;left:0;height:100vh;z-index:100}
.main{margin-left:220px;flex:1;display:flex;flex-direction:column;min-height:100vh}
.topbar{background:var(--surface);border-bottom:1px solid var(--border);padding:0 28px;height:60px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:50}
.content{padding:28px;flex:1}
/* Sidebar */
.sidebar-logo{padding:20px 20px 12px;border-bottom:1px solid #1e2d40}
.logo-mark{font-family:'DM Mono',monospace;font-size:18px;font-weight:500;color:#fff;letter-spacing:-.02em}
.logo-sub{font-size:10px;color:#4b5563;text-transform:uppercase;letter-spacing:.1em;margin-top:2px}
.nav{padding:12px 10px;flex:1;overflow-y:auto}
.nav-section{font-size:10px;color:#374151;text-transform:uppercase;letter-spacing:.1em;padding:8px 10px 4px;margin-top:8px}
.nav-item{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;color:#9ca3af;font-size:13px;font-weight:500;cursor:pointer;transition:all .15s;margin-bottom:2px}
.nav-item:hover,.nav-item.active{background:#1a2538;color:#fff}
.nav-item .icon{width:16px;text-align:center;font-size:15px;flex-shrink:0}
.sidebar-bottom{padding:12px;border-top:1px solid #1e2d40}
.run-btn{width:100%;background:#2563eb;color:#fff;border:none;border-radius:8px;padding:10px;font-weight:600;font-size:13px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px;font-family:'DM Sans',sans-serif;transition:background .2s}
.run-btn:hover{background:#1d4ed8}
.run-btn:disabled{background:#374151;cursor:not-allowed}
.run-pulse{width:8px;height:8px;border-radius:50%;background:#22c55e;animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
/* Topbar */
.page-title{font-size:17px;font-weight:700;color:var(--text)}
.page-subtitle{font-size:12px;color:var(--muted);margin-top:1px}
.topbar-right{display:flex;align-items:center;gap:12px}
.badge-running{background:#fef3c7;color:#92400e;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:600;display:none}
.badge-running.show{display:block}
/* Stats row */
.stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}
@media(max-width:900px){.stats-row{grid-template-columns:repeat(2,1fr)}}
.stat-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:18px 20px;box-shadow:var(--shadow)}
.stat-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}
.stat-value{font-size:28px;font-weight:700;color:var(--text);line-height:1}
.stat-sub{font-size:11px;color:var(--muted);margin-top:4px}
/* Product grid */
.section-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
.section-title{font-size:15px;font-weight:700}
.filter-row{display:flex;gap:8px;flex-wrap:wrap}
.filter-btn{padding:5px 12px;border-radius:999px;border:1px solid var(--border);background:var(--surface);font-size:12px;font-weight:500;cursor:pointer;color:var(--muted);transition:all .15s;font-family:'DM Sans',sans-serif}
.filter-btn.active,.filter-btn:hover{background:var(--accent);border-color:var(--accent);color:#fff}
.products-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:16px}
/* Product card */
.product-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden;box-shadow:var(--shadow);transition:box-shadow .2s}
.product-card:hover{box-shadow:0 4px 20px rgba(0,0,0,.1)}
.pc-header{padding:16px 18px 12px;border-bottom:1px solid var(--border);display:flex;align-items:flex-start;justify-content:space-between;gap:8px}
.pc-name{font-size:14px;font-weight:600;line-height:1.3}
.pc-meta{display:flex;gap:6px;margin-top:5px;flex-wrap:wrap}
.tag{padding:2px 8px;border-radius:999px;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.04em}
.tag-own{background:var(--own-light);color:var(--own)}
.tag-comp{background:var(--accent-light);color:var(--accent)}
.tag-cat{background:var(--surface2);color:var(--muted);border:1px solid var(--border)}
.pc-actions{display:flex;gap:6px;flex-shrink:0}
.icon-btn{width:28px;height:28px;border-radius:6px;border:1px solid var(--border);background:none;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:13px;color:var(--muted);transition:all .15s}
.icon-btn:hover{background:var(--surface2);color:var(--text)}
.icon-btn.danger:hover{background:var(--red-light);color:var(--red);border-color:var(--red)}
/* Price comparison table */
.price-table{width:100%}
.pt-row{display:flex;align-items:center;padding:8px 18px;gap:10px;border-bottom:1px solid var(--border);transition:background .1s}
.pt-row:last-child{border-bottom:none}
.pt-row:hover{background:var(--surface2)}
.pt-row.best{background:var(--green-light)}
.pt-row.best .pt-price{color:var(--green)}
.store-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.pt-store{font-size:12px;font-weight:500;color:var(--muted);width:100px;flex-shrink:0}
.pt-bar-wrap{flex:1;height:4px;background:var(--border);border-radius:999px;overflow:hidden}
.pt-bar{height:100%;border-radius:999px;transition:width .5s}
.pt-price{font-size:14px;font-weight:700;font-family:'DM Mono',monospace;text-align:right;width:100px;flex-shrink:0}
.pt-discount{font-size:10px;font-weight:600;color:var(--green);background:var(--green-light);padding:2px 5px;border-radius:4px;width:38px;text-align:center;flex-shrink:0}
.pt-link{font-size:11px;color:var(--accent);opacity:0;transition:opacity .2s}
.pt-row:hover .pt-link{opacity:1}
.no-price{color:var(--muted);font-size:12px;padding:8px 18px}
/* Chart */
.chart-wrap{padding:12px 18px 14px}
.chart-title{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}
/* Empty state */
.empty-state{text-align:center;padding:80px 20px;color:var(--muted)}
.empty-icon{font-size:48px;margin-bottom:12px}
.empty-title{font-size:16px;font-weight:600;color:var(--text);margin-bottom:6px}
.empty-sub{font-size:13px;line-height:1.6}
/* Admin panel */
.admin-grid{display:grid;grid-template-columns:1fr 380px;gap:20px}
@media(max-width:900px){.admin-grid{grid-template-columns:1fr}}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:22px;box-shadow:var(--shadow)}
.card-title{font-size:14px;font-weight:700;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid var(--border)}
.form-row{margin-bottom:14px}
.form-row label{display:block;font-size:12px;font-weight:600;color:var(--muted);margin-bottom:5px;text-transform:uppercase;letter-spacing:.04em}
input[type=text],input[type=url],select,textarea{width:100%;background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:9px 12px;font-size:13px;color:var(--text);font-family:'DM Sans',sans-serif;outline:none;transition:border-color .2s}
input:focus,select:focus,textarea:focus{border-color:var(--accent);background:#fff}
.toggle-row{display:flex;align-items:center;justify-content:space-between;padding:10px 12px;background:var(--surface2);border:1px solid var(--border);border-radius:8px;margin-bottom:10px}
.toggle-row label{font-size:13px;font-weight:500}
.toggle{width:36px;height:20px;background:var(--border);border-radius:999px;cursor:pointer;position:relative;transition:background .2s;border:none;flex-shrink:0}
.toggle.on{background:var(--accent)}
.toggle::after{content:'';position:absolute;width:14px;height:14px;background:#fff;border-radius:50%;top:3px;left:3px;transition:left .2s;box-shadow:0 1px 3px rgba(0,0,0,.2)}
.toggle.on::after{left:19px}
.url-grid{display:grid;grid-template-columns:90px 1fr;gap:6px 10px;align-items:center;margin-bottom:4px}
.url-grid label{font-size:11px;color:var(--muted);font-weight:500}
.btn{padding:9px 18px;border-radius:8px;font-weight:600;font-size:13px;cursor:pointer;border:none;font-family:'DM Sans',sans-serif;transition:all .2s;display:inline-flex;align-items:center;gap:6px}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover{background:#1d4ed8}
.btn-ghost{background:transparent;color:var(--muted);border:1px solid var(--border)}
.btn-ghost:hover{background:var(--surface2);color:var(--text)}
.btn-danger{background:var(--red-light);color:var(--red)}
.btn-danger:hover{background:var(--red);color:#fff}
.product-list-item{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border);gap:10px}
.product-list-item:last-child{border-bottom:none}
.pli-info{flex:1;min-width:0}
.pli-name{font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pli-meta{font-size:11px;color:var(--muted);margin-top:2px}
/* Toast */
.toast{position:fixed;bottom:24px;right:24px;background:#0d1117;color:#fff;padding:12px 18px;border-radius:10px;font-size:13px;font-weight:500;z-index:999;opacity:0;transform:translateY(8px);transition:all .25s;pointer-events:none}
.toast.show{opacity:1;transform:translateY(0)}
/* Alerts */
.alert-list{display:flex;flex-direction:column;gap:8px;margin-bottom:20px}
.alert-item{background:var(--green-light);border:1px solid #a7f3d0;border-radius:8px;padding:10px 14px;display:flex;align-items:center;justify-content:space-between;font-size:13px}
.alert-drop{font-weight:700;color:var(--green)}
"""

SCRIPT = """
const STORE_COLORS = """ + json.dumps(STORE_COLORS) + """;
let currentView = 'dashboard';

function nav(view) {
  currentView = view;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.view === view));
  loadView(view);
}

async function loadView(view) {
  const content = document.getElementById('content');
  const title = document.getElementById('page-title');
  const subtitle = document.getElementById('page-subtitle');
  if (view === 'dashboard') {
    title.textContent = 'Dashboard';
    subtitle.textContent = 'Precios actuales y comparación por tienda';
    content.innerHTML = '<div class="loading" style="text-align:center;padding:60px;color:var(--muted)">Cargando...</div>';
    const [products, stats] = await Promise.all([
      fetch('/api/products').then(r=>r.json()),
      fetch('/api/stats').then(r=>r.json())
    ]);
    renderDashboard(products, stats, content);
  } else if (view === 'admin') {
    title.textContent = 'Administración';
    subtitle.textContent = 'Gestiona productos propios y competencia';
    content.innerHTML = '<div style="text-align:center;padding:60px;color:var(--muted)">Cargando...</div>';
    const products = await fetch('/api/products?active=all').then(r=>r.json());
    renderAdmin(products, content);
  }
}

function renderDashboard(products, stats, container) {
  const alerts = products.flatMap(p =>
    (p.latest_prices || []).filter(pr => pr.drop_pct > 5).map(pr => ({...pr, product: p.name}))
  );

  let html = `
  <div class="stats-row">
    <div class="stat-card">
      <div class="stat-label">Productos propios</div>
      <div class="stat-value">${stats.own_products}</div>
      <div class="stat-sub">monitoreados</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Competencia</div>
      <div class="stat-value">${stats.competitor_products}</div>
      <div class="stat-sub">productos</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Registros de precio</div>
      <div class="stat-value">${stats.total_price_records.toLocaleString()}</div>
      <div class="stat-sub">histórico</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Último scraping</div>
      <div class="stat-value" style="font-size:16px;padding-top:4px">${stats.last_scrape || '—'}</div>
      <div class="stat-sub">fecha</div>
    </div>
  </div>`;

  // Filter bar
  const categories = [...new Set(products.map(p => p.category).filter(Boolean))];
  html += `
  <div class="section-header">
    <div class="section-title">Comparación de precios</div>
    <div class="filter-row">
      <button class="filter-btn active" onclick="filterProducts('all', this)">Todos</button>
      <button class="filter-btn" onclick="filterProducts('own', this)">Propios</button>
      <button class="filter-btn" onclick="filterProducts('comp', this)">Competencia</button>
      ${categories.map(c => `<button class="filter-btn" onclick="filterProducts('${c}', this)">${c}</button>`).join('')}
    </div>
  </div>
  <div class="products-grid" id="products-grid">`;

  if (!products.length) {
    html += `<div class="empty-state" style="grid-column:1/-1">
      <div class="empty-icon">📦</div>
      <div class="empty-title">Sin productos</div>
      <div class="empty-sub">Ve a Administración para agregar tus productos y los de la competencia</div>
    </div>`;
  }

  for (const p of products) {
    html += renderProductCard(p);
  }
  html += '</div>';
  container.innerHTML = html;

  // Draw mini charts
  for (const p of products) {
    if (p.price_history && p.price_history.length > 1) {
      drawMiniChart(p.id, p.price_history);
    }
  }
}

function renderProductCard(p) {
  const prices = p.latest_prices || [];
  const minPrice = prices.length ? Math.min(...prices.map(x => x.price)) : 0;
  const maxPrice = prices.length ? Math.max(...prices.map(x => x.price)) : 1;

  const typeTag = p.is_own
    ? '<span class="tag tag-own">Propio</span>'
    : '<span class="tag tag-comp">Competencia</span>';
  const catTag = p.category ? `<span class="tag tag-cat">${p.category}</span>` : '';

  let priceRows = '';
  if (!prices.length) {
    priceRows = '<div class="no-price">Sin precios registrados — ejecuta el scraping</div>';
  } else {
    for (const pr of prices) {
      const isBest = pr.price === minPrice;
      const barWidth = maxPrice > minPrice ? Math.round((1 - (pr.price - minPrice)/(maxPrice - minPrice)) * 80 + 20) : 100;
      const color = STORE_COLORS[pr.store.toLowerCase()] || '#6b7280';
      const discount = pr.original_price && pr.original_price > pr.price
        ? `-${Math.round((1 - pr.price/pr.original_price)*100)}%`
        : '';
      priceRows += `
      <div class="pt-row ${isBest ? 'best' : ''}">
        <div class="store-dot" style="background:${color}"></div>
        <div class="pt-store">${pr.store}</div>
        <div class="pt-bar-wrap"><div class="pt-bar" style="width:${barWidth}%;background:${color}40;border:1px solid ${color}60"></div></div>
        <div class="pt-price">$${pr.price.toLocaleString('es-CL')}</div>
        <div class="pt-discount">${discount}</div>
        ${pr.url ? `<a class="pt-link" href="${pr.url}" target="_blank">Ver →</a>` : '<div class="pt-link"></div>'}
      </div>`;
    }
  }

  const hasHistory = (p.price_history || []).length > 1;

  return `
  <div class="product-card" data-own="${p.is_own}" data-cat="${p.category || ''}">
    <div class="pc-header">
      <div>
        <div class="pc-name">${p.name}</div>
        <div class="pc-meta">${typeTag}${catTag}</div>
      </div>
      <div class="pc-actions">
        <button class="icon-btn" onclick="nav('admin')" title="Editar">✏️</button>
      </div>
    </div>
    <div class="price-table">${priceRows}</div>
    ${hasHistory ? `<div class="chart-wrap">
      <div class="chart-title">Evolución de precio (90 días)</div>
      <canvas id="chart-${p.id}" height="60" style="width:100%"></canvas>
    </div>` : ''}
  </div>`;
}

function drawMiniChart(productId, history) {
  const canvas = document.getElementById(`chart-${productId}`);
  if (!canvas) return;
  canvas.width = canvas.offsetWidth || 300;

  const ctx = canvas.getContext('2d');
  const stores = [...new Set(history.map(h => h.store))];
  const dates = [...new Set(history.map(h => h.date))].sort();

  const W = canvas.width, H = 60;
  const allPrices = history.map(h => h.price).filter(Boolean);
  const minP = Math.min(...allPrices) * 0.95;
  const maxP = Math.max(...allPrices) * 1.05;

  ctx.clearRect(0, 0, W, H);

  for (const store of stores) {
    const storeData = history.filter(h => h.store === store && h.price);
    if (storeData.length < 2) continue;
    const color = STORE_COLORS[store.toLowerCase()] || '#6b7280';

    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';

    storeData.forEach((point, i) => {
      const x = ((dates.indexOf(point.date)) / (dates.length - 1)) * (W - 4) + 2;
      const y = H - ((point.price - minP) / (maxP - minP)) * (H - 8) - 4;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();
  }
}

function filterProducts(filter, btn) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.product-card').forEach(card => {
    let show = true;
    if (filter === 'own') show = card.dataset.own === '1';
    else if (filter === 'comp') show = card.dataset.own === '0';
    else if (filter !== 'all') show = card.dataset.cat === filter;
    card.style.display = show ? '' : 'none';
  });
}

function renderAdmin(products, container) {
  const STORES = """ + json.dumps(list(STORE_LABELS.keys())) + """;
  const urlInputs = STORES.map(s => `
    <div class="url-grid">
      <label>${STORE_LABELS[s] || s}</label>
      <input type="url" name="url_${s}" placeholder="https://...">
    </div>`).join('');

  const productItems = products.map(p => `
    <div class="product-list-item">
      <div class="pli-info">
        <div class="pli-name">${p.name}</div>
        <div class="pli-meta">${p.is_own ? '🟣 Propio' : '🔵 Competencia'}${p.category ? ' · ' + p.category : ''}</div>
      </div>
      <div style="display:flex;gap:6px">
        <button class="btn btn-ghost" style="padding:5px 10px;font-size:12px" onclick="toggleActive(${p.id}, ${p.active})">${p.active ? 'Pausar' : 'Activar'}</button>
        <button class="btn btn-danger" style="padding:5px 10px;font-size:12px" onclick="deleteProduct(${p.id})">Eliminar</button>
      </div>
    </div>`).join('') || '<p style="color:var(--muted);font-size:13px;padding:8px 0">No hay productos aún</p>';

  container.innerHTML = `
  <div class="admin-grid">
    <div>
      <div class="card">
        <div class="card-title">Agregar producto</div>
        <div class="form-row">
          <label>Nombre del producto</label>
          <input type="text" id="p-name" placeholder="Ej: Samsung Galaxy S24 256GB Negro">
        </div>
        <div class="form-row">
          <label>Categoría</label>
          <input type="text" id="p-cat" placeholder="Ej: Smartphones, TV, Electrohogar">
        </div>
        <div class="toggle-row">
          <label>¿Es un producto propio?</label>
          <button class="toggle" id="p-own-toggle" onclick="this.classList.toggle('on')"></button>
        </div>
        <div class="form-row">
          <label>Búsqueda automática (si no tienes URLs)</label>
          <input type="text" id="p-query" placeholder="Ej: Samsung Galaxy S24 256GB">
        </div>
        <div class="form-row">
          <label>URLs por tienda (opcional — más preciso)</label>
          <div id="url-inputs">${urlInputs}</div>
        </div>
        <button class="btn btn-primary" onclick="addProduct()" style="width:100%;justify-content:center;margin-top:4px">
          + Agregar producto
        </button>
      </div>
    </div>
    <div>
      <div class="card">
        <div class="card-title">Productos registrados (${products.length})</div>
        <div id="product-list">${productItems}</div>
      </div>
    </div>
  </div>`;
}

const STORE_LABELS = """ + json.dumps(STORE_LABELS) + """;

async function addProduct() {
  const name = document.getElementById('p-name').value.trim();
  const cat = document.getElementById('p-cat').value.trim();
  const query = document.getElementById('p-query').value.trim();
  const isOwn = document.getElementById('p-own-toggle').classList.contains('on');
  if (!name) { toast('Ingresa un nombre', 'error'); return; }
  const urls = {};
  document.querySelectorAll('#url-inputs input').forEach(inp => {
    const store = inp.name.replace('url_', '');
    if (inp.value.trim()) urls[store] = inp.value.trim();
  });
  const r = await fetch('/api/products', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name, category: cat, is_own: isOwn, search_query: query, urls})
  });
  if (r.ok) {
    toast('Producto agregado ✓');
    setTimeout(() => nav('admin'), 800);
  } else toast('Error al agregar', 'error');
}

async function deleteProduct(id) {
  if (!confirm('¿Eliminar este producto y todo su historial de precios?')) return;
  const r = await fetch(`/api/products/${id}`, {method: 'DELETE'});
  if (r.ok) { toast('Eliminado'); setTimeout(() => nav('admin'), 600); }
}

async function toggleActive(id, current) {
  await fetch(`/api/products/${id}`, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({active: current ? 0 : 1})
  });
  nav('admin');
}

async function runScraper() {
  const btn = document.getElementById('run-btn');
  btn.disabled = true;
  btn.innerHTML = '<div class="run-pulse"></div> Corriendo...';
  document.getElementById('badge-running').classList.add('show');
  const r = await fetch('/api/run', {method: 'POST'});
  const data = await r.json();
  toast('Scraping iniciado — esto tarda ~1 minuto');
  setTimeout(() => {
    btn.disabled = false;
    btn.innerHTML = '▶ Ejecutar ahora';
    document.getElementById('badge-running').classList.remove('show');
    if (currentView === 'dashboard') loadView('dashboard');
  }, 65000);
}

function toast(msg, type='ok') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.background = type === 'error' ? '#dc2626' : '#0d1117';
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3000);
}

// Init
nav('dashboard');
"""


def full_html(body_content: str, active_view: str = "dashboard") -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RetailScope</title>
<style>{CSS}</style>
</head>
<body>
<div class="shell">
  <nav class="sidebar">
    <div class="sidebar-logo">
      <div class="logo-mark">RetailScope</div>
      <div class="logo-sub">Price Intelligence</div>
    </div>
    <div class="nav">
      <div class="nav-section">Análisis</div>
      <div class="nav-item" data-view="dashboard" onclick="nav('dashboard')">
        <span class="icon">📊</span> Dashboard
      </div>
      <div class="nav-section">Configuración</div>
      <div class="nav-item" data-view="admin" onclick="nav('admin')">
        <span class="icon">⚙️</span> Administración
      </div>
    </div>
    <div class="sidebar-bottom">
      <button class="run-btn" id="run-btn" onclick="runScraper()">▶ Ejecutar ahora</button>
    </div>
  </nav>
  <div class="main">
    <div class="topbar">
      <div>
        <div class="page-title" id="page-title">Dashboard</div>
        <div class="page-subtitle" id="page-subtitle">Precios actuales</div>
      </div>
      <div class="topbar-right">
        <div class="badge-running" id="badge-running">⏳ Scraping en progreso</div>
      </div>
    </div>
    <div class="content" id="content">
      <div style="text-align:center;padding:80px;color:var(--muted)">Cargando...</div>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>{SCRIPT}</script>
</body>
</html>"""


# ── Handler ────────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): log.info(f"{self.address_string()} {fmt % args}")

    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def do_GET(self):
        p = urlparse(self.path)
        path = p.path

        if path in ("/", ""):
            db.init()
            self.send_html(full_html(""))
            return

        if path == "/health":
            self.send_json(200, {"ok": True})
            return

        if path == "/api/stats":
            self.send_json(200, db.get_dashboard_stats())
            return

        if path == "/api/products":
            params = parse_qs(p.query)
            active_only = params.get("active", ["1"])[0] != "all"
            products = db.get_products(active_only=active_only)
            # Enrich with prices
            for prod in products:
                prod["latest_prices"] = db.get_latest_prices(prod["id"])
                prod["price_history"] = db.get_price_history(prod["id"], days=90)
            self.send_json(200, products)
            return

        if path.startswith("/api/products/") and path.count("/") == 3:
            pid = int(path.split("/")[-1])
            prod = db.get_product(pid)
            if prod:
                prod["latest_prices"] = db.get_latest_prices(pid)
                prod["price_history"] = db.get_price_history(pid, days=90)
                self.send_json(200, prod)
            else:
                self.send_json(404, {"error": "not found"})
            return

        if path == "/api/run":
            self._handle_run()
            return

        self.send_json(404, {"error": "not found"})

    def do_POST(self):
        p = urlparse(self.path)
        if p.path == "/api/products":
            data = self.read_body()
            if not data.get("name"):
                self.send_json(400, {"error": "name required"})
                return
            pid = db.add_product(
                name=data["name"],
                category=data.get("category", ""),
                is_own=data.get("is_own", False),
                search_query=data.get("search_query", ""),
                urls=data.get("urls", {})
            )
            self.send_json(200, {"id": pid})
            return

        if p.path == "/api/run":
            self._handle_run()
            return

        self.send_json(404, {"error": "not found"})

    def do_PATCH(self):
        p = urlparse(self.path)
        if p.path.startswith("/api/products/"):
            pid = int(p.path.split("/")[-1])
            data = self.read_body()
            db.update_product(pid, **data)
            self.send_json(200, {"ok": True})
        else:
            self.send_json(404, {"error": "not found"})

    def do_DELETE(self):
        p = urlparse(self.path)
        if p.path.startswith("/api/products/"):
            pid = int(p.path.split("/")[-1])
            db.delete_product(pid)
            self.send_json(200, {"ok": True})
        else:
            self.send_json(404, {"error": "not found"})

    def _handle_run(self):
        if scrape_status["running"]:
            self.send_json(200, {"status": "already_running"})
            return

        def bg():
            scrape_status["running"] = True
            try:
                result = asyncio.run(run_all())
                scrape_status["last"] = result
                log.info(f"Scraping completado: {result}")
            except Exception as e:
                log.error(f"Error en scraping: {e}", exc_info=True)
            finally:
                scrape_status["running"] = False

        threading.Thread(target=bg, daemon=True).start()
        self.send_json(200, {"status": "started"})


def main():
    port = int(os.environ.get("PORT", 8080))
    db.init()
    log.info(f"🚀 RetailScope en http://0.0.0.0:{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
