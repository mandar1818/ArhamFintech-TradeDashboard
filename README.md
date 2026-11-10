# Arham Fintech — BSE Trade Operations Dashboard

A full-stack trade operations application built with **FastAPI**, **SQLite (SQLAlchemy)**, **Server-Sent Events (SSE)**, and **React + TypeScript + Vite**.

> **Simulated Data Notice:** All seeded trade records, pulled BSE batches, prices, and clearing delays are simulated for technical assessment purposes. The application does not connect to a live exchange feed or execute real trades.

---

## Project Purpose

This repository implements an internal trade operations dashboard that lets operators inspect stored equity trades immediately (`GET /getTrades`) while triggering long-running asynchronous BSE trade ingestion jobs (`POST /pull-trades`) and receiving live status updates in the browser (`GET /events`) without manual page refreshes or polling timers.

---

## Problem Statement

Exchange batch settlement feeds often introduce high latency (modeled here as a configurable 15-minute / 900-second delay). Calling a slow upstream feed synchronously from web endpoints causes two operational problems:

1. **HTTP Timeout Failures:** Reverse proxies, load balancers, and browser clients enforce 30–60 second request timeouts, causing synchronous 15-minute endpoints to fail with gateway timeouts (`504`).
2. **Blocked Read Queries:** Holding HTTP workers open or blocking `GET /getTrades` behind active ingestion prevents operators from searching, filtering, and paginating existing trade records.

To solve this cleanly, `GET /getTrades` queries SQLite directly and immediately, `POST /pull-trades` returns HTTP `202 Accepted` with a persistent `job_id` while delegating execution to an async background worker, and `GET /events` pushes lifecycle updates over SSE so connected browsers refresh automatically once ingestion commits.

---

## Technology Stack

- **Backend:** Python 3.12, FastAPI, Uvicorn, SQLAlchemy 2.x, Pydantic v2, `pydantic-settings`
- **Database:** SQLite in Write-Ahead Logging mode (`PRAGMA journal_mode=WAL`)
- **Real-Time Events:** Server-Sent Events (`StreamingResponse` + in-memory `SSEBroker` queues on backend; browser `EventSource` on frontend)
- **Frontend:** React 18, TypeScript 5, Vite 5, Lucide icons
- **Testing & Type Checking:** `pytest`, `pytest-asyncio`, `httpx`, `tsc`, `vite build`

---

## Architecture Overview

1. **Fast Local Reads (`GET /getTrades`):** Queries indexed SQLite tables (`trades`) using WAL mode concurrency and returns paginated records, filtered subsets, and portfolio totals (`total_trades`, `total_quantity`, `total_value`, `unique_clients`) immediately regardless of whether a background pull is active.
2. **Non-Blocking Ingestion Trigger (`POST /pull-trades`):** Creates a `PENDING` record in `ingestion_jobs` (protected by a partial unique index + `asyncio.Lock` to reject concurrent pulls with `409 Conflict`), spawns an in-process `asyncio.Task`, and returns `202 Accepted` immediately.
3. **Atomic Post-Completion Persistence:** Newly fetched trades remain staged in memory until the simulated fetch finishes, then write atomically in a single SQLite transaction alongside `status='COMPLETED'` using `INSERT ... ON CONFLICT(trade_id) DO NOTHING`. Failed jobs leave zero partial trades.
4. **SSE Push Synchronization (`GET /events`):** Broadcasts `connected`, `job_queued`, `job_started`, `job_progress`, `job_retrying`, `job_completed`, and `job_failed` frames to connected browsers. On `job_completed`, the React app executes a single refresh against `/getTrades`, `/trades/filters`, and `/jobs` without `setInterval` polling.

See [Architecture.md](./Architecture.md) for Mermaid diagrams, request/ingestion/SSE lifecycles, SQLite persistence details, and scaling trade-offs.

---

## Project Structure

```text
ArhamFintech-TradeDashboard/
├── .env.example
├── .gitignore
├── Architecture.md
├── README.md
├── backend/
│   ├── .env.example
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                      # FastAPI app factory, lifespan, CORS, exception handlers
│   │   ├── core/
│   │   │   ├── config.py                # pydantic-settings configuration
│   │   │   ├── exceptions.py            # Structured JSON error handlers & custom exceptions
│   │   │   └── logging.py               # Structured JSON logger setup
│   │   ├── database/
│   │   │   ├── base.py                  # SQLAlchemy declarative Base
│   │   │   └── session.py               # SQLite WAL engine & session factory
│   │   ├── models/
│   │   │   ├── trade.py                 # Trade ORM model & B-tree/composite indexes
│   │   │   └── ingestion_job.py         # IngestionJob ORM model & single-active partial index
│   │   ├── schemas/                     # Pydantic v2 request/response contracts
│   │   ├── services/
│   │   │   ├── bse_mock_service.py      # Simulated Indian equity seed & BSE batch feed
│   │   │   ├── seed_service.py          # Idempotent initial SQLite seeding (>= 3,000 rows)
│   │   │   ├── trade_service.py         # Ledger query, search, filter, sort & KPI aggregation
│   │   │   ├── sse_broker.py            # In-memory SSE subscriber registry & frame formatter
│   │   │   └── ingestion_service.py     # Async worker coordinator, retries & atomic commits
│   │   └── routers/                     # REST & SSE routers (/getTrades, /pull-trades, /jobs, /events, /health)
│   └── tests/                           # Backend pytest suite
└── frontend/
    ├── .env.example
    ├── index.html
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    └── src/
        ├── api/client.ts                # Typed fetch wrapper & API error handling
        ├── hooks/useTradeEvents.ts      # Browser EventSource hook with reconnect handling
        ├── types/trade.ts               # TypeScript contracts matching API schemas
        ├── utils/format.ts              # INR currency & IST timestamp formatters
        ├── index.css                    # Dashboard styles
        ├── App.tsx                      # Root dashboard state & single-fetch SSE sync
        └── components/
            ├── ErrorBoundary.tsx
            ├── Header.tsx
            ├── IngestionStatusBanner.tsx
            ├── KpiGrid.tsx
            ├── LatestTradesStrip.tsx    # Compact 5-row recent execution blotter
            ├── TradeLedger.tsx          # Searchable, filterable, sortable, paginated ledger
            └── IngestionHistory.tsx     # Persistent SQLite pull audit table
```

---

## Installation Instructions

### Prerequisites

- Python 3.11+ (tested with Python 3.12)
- Node.js 18+ and npm

### 1. Create Environment Files

Copy the templates before running the servers:

**Windows (PowerShell):**
```powershell
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env
```

**macOS / Linux:**
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

### 2. Install Backend Dependencies

```powershell
cd backend
python -m venv .venv

# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS / Linux: source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Install Frontend Dependencies

```powershell
cd frontend
npm install
```

---

## Configuration Details

Backend variables in `backend/.env` (loaded via `pydantic-settings`):

| Variable | Default | Description |
| :--- | :--- | :--- |
| `APP_NAME` | `Arham Fintech BSE Trade Dashboard API` | Service title shown in OpenAPI/Swagger |
| `APP_ENV` | `development` | Environment label |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `DATABASE_URL` | `sqlite:///./data/trades.db` | SQLite connection URI (directory auto-created) |
| `SEED_TRADE_COUNT` | `3250` | Initial simulated trades seeded when `trades` table is empty (minimum 3,000 for assessment) |
| `BSE_PULL_DELAY_SECONDS` | `900` | Simulated BSE exchange delay in seconds (`900` = 15 min; set `10`–`20` for quick local testing) |
| `BSE_DEFAULT_BATCH_SIZE` | `50` | Default number of simulated trades fetched per ingestion job |
| `BSE_MAX_RETRIES` | `2` | Maximum automatic retry attempts after transient upstream failures |
| `BSE_RETRY_DELAY_SECONDS` | `2.0` | Delay in seconds between retry attempts |
| `SSE_HEARTBEAT_SECONDS` | `15.0` | Interval for `: heartbeat` SSE keepalive frames |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed frontend origins |

Frontend variable in `frontend/.env`:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | Backend base URL for REST calls and `EventSource` `/events` |

> **Testing vs. 15-Minute Default:** `.env.example` sets `BSE_PULL_DELAY_SECONDS=900` (15 minutes) to match the assessment specification. Change it to `BSE_PULL_DELAY_SECONDS=15` in `backend/.env` when demonstrating or verifying a full completion cycle locally.

---

## Running Backend & Frontend

### Run the Backend

From the `backend/` directory with the virtual environment activated:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

*(Keep `--workers 1`, the default, because `asyncio` background tasks and `SSEBroker` live in process memory.)*

Interactive API docs:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

### Run the Frontend

In a separate terminal from `frontend/`:

```powershell
npm run dev
```

Dashboard URL: `http://127.0.0.1:5173`

---

## API Endpoints

| Method | Endpoint | Response Code | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/getTrades` | `200 OK` | Immediate SQLite ledger query. Params: `page`, `page_size` (1–200), `search` (`trade_id`, `symbol`, `client`), `symbol`, `client`, `sort_by` (`timestamp`, `trade_id`, `client`, `symbol`, `quantity`, `price`, `value`), `sort_order` (`asc`, `desc`). Returns paginated items plus global and filtered KPI summaries. |
| `GET` | `/trades/filters` | `200 OK` | Returns sorted distinct `symbols` and `clients` stored in SQLite. |
| `POST` | `/pull-trades` | `202 Accepted` / `409 Conflict` | Creates a `PENDING` job, spawns the background worker, and returns `{ job_id, status, message, estimated_delay_seconds, batch_size, max_retries, created_at }` immediately. Optional JSON body supports `batch_size`, `simulate_failure`, and `simulate_transient_failures`. Returns `409 Conflict` if another job is active. |
| `GET` | `/jobs` | `200 OK` | Returns persistent job history, currently active job (if any), and `last_successful_sync`. |
| `GET` | `/jobs/{job_id}` | `200 OK` / `404 Not Found` | Returns detailed status and counts for one ingestion job. |
| `GET` | `/events` | `200 OK` (`text/event-stream`) | Persistent SSE stream emitting `connected`, `job_queued`, `job_started`, `job_progress`, `job_retrying`, `job_completed`, `job_failed`, and periodic `: heartbeat` keepalive comments. |
| `GET` | `/health` | `200 OK` | Verifies SQLite connectivity (`SELECT 1`), trade count, active job ID, and connected SSE subscriber count. |

---

## Testing Commands

### Backend Test Suite (`pytest`)

From project root:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests -v
```

*(Covers idempotent seeding >= 3,000 rows, `/getTrades` filtering/search/sorting/pagination, non-blocking reads during slow pulls, immediate `202` response, post-completion atomic writes, `409` duplicate pull prevention, `trade_id` deduplication, retry recovery, failed rollback, `404`/`422`/crash recovery, OpenAPI/CORS, and multi-client SSE streaming.)*

### Frontend Type Check & Production Build

From project root:

```powershell
# Standalone TypeScript check:
frontend\node_modules\.bin\tsc.cmd -p frontend\tsconfig.app.json --noEmit

# Strict TypeScript build + Vite production bundle:
npm --prefix frontend run build
```

---

## Known Limitations

1. **In-process `asyncio.Task` execution is not crash-durable:** Restarting Uvicorn terminates running tasks cleanly and discards uncommitted batches. At next startup, `recover_interrupted_jobs()` marks stale active jobs as `FAILED` so future pulls can proceed, but interrupted pulls must be re-triggered manually.
2. **In-memory `SSEBroker` requires a single server process:** Subscriber queues reside in Python process memory; scaling to multiple Uvicorn workers (`--workers > 1`) or multiple pods requires external pub/sub such as Redis.
3. **No server-side event replay buffer:** SSE frames include an `id` field, and reconnecting clients reconcile via the `connected` snapshot (`active_job` / `latest_job`), but intermediate progress ticks emitted during an offline window are not replayed.
4. **SQLite single-writer bottleneck:** SQLite WAL handles concurrent reads well at assessment scale, while high concurrent write throughput across services would require PostgreSQL.
5. **No operator authentication:** Endpoints assume trusted local usage without JWT/OAuth2 or per-user audit trails.
6. **Simulated market dataset:** Stock symbols, institutional client names, quantities, prices, and clearing delays are simulated.
