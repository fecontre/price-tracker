# 🛒 Price Tracker Chile

Scraper de precios para Falabella, Ripley, Paris, MercadoLibre, Sodimac, Easy y Travel Club.
Los precios se guardan en una base de datos SQLite y se visualizan en un panel web incluido.

## Archivos del proyecto

```
price-tracker/
├── server.py          ← servidor web + panel de administración
├── main.py            ← orquestador del scraping
├── db.py              ← base de datos SQLite
├── scrapers/
│   ├── __init__.py
│   ├── base.py
│   ├── falabella.py
│   ├── ripley.py
│   ├── paris.py
│   ├── mercadolibre.py
│   ├── sodimac.py
│   ├── easy.py
│   └── travelclub.py
├── Dockerfile
├── requirements.txt
└── .dockerignore
```

## Deploy en Cloud Run (desde GitHub)

### 1. Sube estos archivos a GitHub
Crea un repositorio en github.com y sube todos estos archivos manteniendo la estructura de carpetas.

### 2. Configura Cloud Run
En Google Cloud Console → Cloud Run → Create Service:
- **Fuente**: Continuously deploy from a repository → selecciona tu repo de GitHub
- **Branch**: `^main$`
- **Build type**: Dockerfile
- **Service name**: `price-tracker`
- **Region**: `us-central1`
- **Memory**: 2 GiB
- **CPU**: 1
- **Timeout**: 900 segundos
- **Authentication**: Require authentication → NO (Allow unauthenticated)
- **Variables de entorno**:
  - `CRON_SECRET` = cualquier contraseña (ej: `mitoken123`)
  - `DB_PATH` = `/data/prices.db`

### 3. Agregar volumen para la base de datos
En la configuración del servicio → Volumes → Add volume:
- **Type**: In-memory (o Cloud Storage si quieres persistencia real)
- **Mount path**: `/data`

### 4. Configurar Cloud Scheduler (ejecución diaria)
```bash
gcloud scheduler jobs create http price-tracker-daily \
  --location us-central1 \
  --schedule "0 12 * * *" \
  --uri "https://TU-SERVICE-URL/run" \
  --headers "Authorization=Bearer mitoken123" \
  --attempt-deadline 900s
```
`0 12 * * *` = 9am hora Chile (UTC-3)

## Uso del panel web

Una vez desplegado, abre la URL de tu servicio Cloud Run en el navegador:
- Verás el dashboard con los últimos precios
- Usa el formulario lateral para agregar productos (por URL o por búsqueda)
- El botón "▶ Ejecutar ahora" dispara el scraping manualmente

## Variables de entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `PORT` | Puerto del servidor | `8080` |
| `CRON_SECRET` | Token para proteger /run | `changeme` |
| `DB_PATH` | Ruta de la base de datos | `/data/prices.db` |
