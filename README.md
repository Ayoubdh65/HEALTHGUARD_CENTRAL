# HealthGuard Central Server

Central server that receives synced vital-sign data from HealthGuard edge nodes (Raspberry Pi).

## Deploy on Render

### Option A – One-Click Blueprint (Recommended)

1. Push this repo to GitHub.
2. Go to [Render Dashboard](https://dashboard.render.com) → **Blueprints** → **New Blueprint Instance**.
3. Connect your GitHub repo.
4. Render will auto-create the web service + PostgreSQL database.
5. Set the `ALLOWED_API_KEYS` environment variable in the dashboard.

### Option B – Manual Setup

1. **Create a PostgreSQL database**:
   - Render Dashboard → **New** → **PostgreSQL** → Free plan → Create.
   - Copy the **Internal Database URL**.

2. **Create a Web Service**:
   - Render Dashboard → **New** → **Web Service** → Connect GitHub repo.
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

3. **Set Environment Variables** (in the Web Service settings):
   - `DATABASE_URL` = the Internal Database URL from step 1
   - `ALLOWED_API_KEYS` = your API key (must match your edge node's `CENTRAL_API_KEY`)

## Configure Your Edge Node

Edit the `.env` file on your edge node:

```env
CENTRAL_SERVER_URL=https://<your-service-name>.onrender.com/api
CENTRAL_API_KEY=<same key as ALLOWED_API_KEYS above>
SYNC_INTERVAL_SECONDS=60
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sync/upload` | Receive vitals from edge nodes |
| GET | `/api/sync/devices` | List registered edge devices |
| GET | `/api/sync/stats` | Sync statistics |
| GET | `/health` | Health check |
| GET | `/docs` | Swagger API docs |
