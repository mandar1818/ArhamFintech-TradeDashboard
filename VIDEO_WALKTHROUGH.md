# 5-Minute Video Walkthrough Script — BSE Trade Operations Dashboard

> **Recording Tip:** Set `BSE_PULL_DELAY_SECONDS=15` in `backend/.env` before starting Uvicorn so you can demonstrate a complete asynchronous ingestion pull, live SSE progress frames, and automatic UI update within the 5-minute recording window. Keep the terminal with FastAPI running visible or switch cleanly to it, and open Chrome DevTools (`Network` tab) on the dashboard tab.

---

## Demo Setup (Before Hitting Record)

1. Ensure `backend/.env` has `BSE_PULL_DELAY_SECONDS=15` and clean initial state (or delete `backend/data/trades.db*` and restart Uvicorn so `SEED_TRADE_COUNT=3250` starts fresh).
2. Terminal 1 running backend: `cd backend && .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
3. Terminal 2 running frontend: `cd frontend && npm run dev`
4. Browser windows open:
   - Tab 1: `http://127.0.0.1:5173` (Dashboard + DevTools **Network** tab open, filtered or set to `All` / `Fetch/XHR` & `EventStream`)
   - Tab 2: `http://127.0.0.1:8000/docs` (FastAPI Swagger UI)

---

## 5-Minute Demonstration Sequence

### 0:00 – 0:45 | Introduction, Initial Data & Zero-Polling SSE Setup
- **Screen to show:** Tab 1 (`http://127.0.0.1:5173`) showing header status pills (`SSE Connected`, `Last Sync`), 4 KPI cards (`Total Trades: 3,250`), `Latest Trade Records` 5-row blotter, `Trade Ledger`, and empty `Ingestion Pull History`. Briefly point to Browser DevTools **Network** tab showing `/events` (`type: eventsource`) open with zero repeating `setInterval` requests.
- **Concepts to explain:**
  - Simulated Indian equity dataset seeded automatically (>= 3,000 rows, default 3,250) into local SQLite in WAL mode.
  - Why SSE (`EventSource` on `GET /events`) replaces polling loops so idle dashboards generate no repetitive database queries.
- **Natural speaking point:**
  > "This is the Arham Fintech BSE Trade Operations Dashboard. When the backend starts up cleanly, it seeds 3,250 simulated Indian equity trades into SQLite—clearly labeled as simulated assessment data. In the top bar, you can see `SSE Connected` backed by a native `EventSource` connection to `GET /events`. If you look at Chrome DevTools Network tab, there is one persistent `events` stream open and zero `setInterval` polling traffic against `/getTrades`."

---

### 0:45 – 1:40 | Instant Ledger Reads, Search, Filtering, Sorting & Swagger `/docs`
- **Screen to show:**
  1. Dashboard **Trade Ledger**: type `RELIANCE` in search or pick `RELIANCE` in the Symbol filter + a Client filter, click a sortable column header (`Trade Value` or `Price`), show filtered KPI totals updating (`Filtered Qty` / `Filtered Value`), and click Next page / Reset.
  2. Switch briefly to Tab 2 (`http://127.0.0.1:8000/docs`) and execute `GET /health` and `GET /getTrades` (`symbol=RELIANCE`, `page_size=5`).
- **Concepts to explain:**
  - Server-side SQLite pagination, escaping `LIKE` wildcards, indexed filtering (`symbol`, `client`, `timestamp`), and non-blocking reads.
  - Note `.env` configuration (`BSE_PULL_DELAY_SECONDS=900` by default for 15 minutes, overridden to `15` seconds for this walkthrough).
- **Natural speaking point:**
  > "All ledger interactions—search, symbol and client filtering, sorting by trade value or price, and pagination—query SQLite directly via `GET /getTrades`. Because SQLite runs in WAL mode with indexes on `symbol`, `client`, and `timestamp`, ledger reads stay fast and never block behind upstream ingestion. In Swagger `/docs`, we can also inspect `/health`, `/trades/filters`, and the full typed API contract."

---

### 1:40 – 3:05 | Asynchronous Pull (`POST /pull-trades`), Avoiding the 30s Timeout & Duplicate Guard (`409`)
- **Screen to show:**
  1. Return to Tab 1 (`http://127.0.0.1:5173`) with DevTools **Network** tab visible.
  2. Click **Pull BSE Trades**. Immediately point out in DevTools that `POST /pull-trades` returns **HTTP `202 Accepted`** right away (`{ job_id, status: "PENDING" }`), while the **Ingestion Queued / Running** banner animates progress (`20%` -> `40%` -> `65%` -> `85%`) via `GET /events` EventStream frames!
  3. *While the 15s pull is still mid-flight*:
     - Interact briefly with the Trade Ledger (sort or filter a stock) to prove **`GET /getTrades` responds immediately** during active ingestion (`Total Trades` still `3,250` because nothing is committed until completion).
     - Switch to Tab 2 (`/docs`) -> `POST /pull-trades` -> **Execute** while the job is running to demonstrate **HTTP `409 Conflict`** returning `active_job_id` (concurrent pull protection).
- **Concepts to explain:**
  - Avoiding the 30-second HTTP proxy timeout by decoupling HTTP request acceptance (`202 Accepted` + persistent `PENDING` SQLite job) from background `asyncio.Task` execution.
  - Concurrent pull lock (`asyncio.Lock` + SQLite partial unique index `ix_ingestion_jobs_single_active`).
  - Staged post-completion commits: partial batches never appear mid-flight.
- **Natural speaking point:**
  > "Now I'll click `Pull BSE Trades`. In DevTools, notice `POST /pull-trades` returns `202 Accepted` in a few milliseconds—we don't hold the HTTP socket open during the simulated exchange delay, which avoids 30-second proxy timeouts. While the worker is running across progress milestones pushed over SSE, `GET /getTrades` still works normally and keeps showing 3,250 trades because nothing writes prematurely. If another client tries `POST /pull-trades` in Swagger while this pull is active, the backend rejects it immediately with `409 Conflict`."

---

### 3:05 – 3:55 | Completion Event, Atomic Persistence & Failure Safety
- **Screen to show:**
  1. Switch back to Tab 1 right as the 15-second pull finishes (`job_completed` fires in the EventStream tab).
  2. Point out automatic zero-refresh updates across all sections: KPI `Total Trades` updates from `3,250` -> `3,300`, `Last Sync` timestamp updates in IST, `Latest Trade Records` blotter displays the new `BSE PULL` trades at the top, and `Ingestion Pull History` logs `COMPLETED` (`50 / 50` inserted, `0` duplicates skipped).
  3. Briefly show a `409` or failure resilience path in Swagger (`POST /pull-trades` with `{ "simulate_failure": true }` if time permits, or jump cleanly to `pytest` showing failure rollback and retry recovery).
- **Concepts to explain:**
  - Single-fetch post-completion refresh pattern upon `job_completed`.
  - Atomic transaction using `INSERT ... ON CONFLICT(trade_id) DO NOTHING` paired with `status = 'COMPLETED'`.
- **Natural speaking point:**
  > "Once ingestion completes, the worker commits all 50 new trades and updates the job status in one atomic SQLite transaction with `ON CONFLICT(trade_id) DO NOTHING` for idempotency. It emits `job_completed` over SSE, and the React dashboard executes a single clean fetch to update KPIs from 3,250 to 3,300, bring the new `BSE PULL` rows to the top of the blotter, update `Last Sync`, and append the audit row in Ingestion Pull History."

---

### 3:55 – 5:00 | Code Architecture, Automated Tests & Honest Limitations
- **Screen to show:**
  1. Open editor or terminal briefly displaying project structure (`Architecture.md` Mermaid diagram or `backend/app/` + `frontend/src/` folders).
  2. Run tests in terminal: `backend\.venv\Scripts\python.exe -m pytest backend\tests -v` (`12 passed`) and `npm --prefix frontend run build` (`tsc -b && vite build` clean).
- **Concepts to explain:**
  - Clean separation into routers, services, models, schemas, and React hooks.
  - Honest single-process limitations (`asyncio.Task` not durable across crashes, `recover_interrupted_jobs()` on startup, in-memory `SSEBroker` single-worker scope -> production upgrade path with Celery/ARQ, Redis Pub/Sub, PostgreSQL).
- **Natural speaking point:**
  > "To wrap up, I'll run the 12 backend pytest tests—covering initial seeding, non-blocking reads, atomic persistence, `409` guards, duplicate IDs, retry recovery, failure rollback, and multi-client SSE streaming—alongside the strict TypeScript check and Vite production build. I've also documented current scope boundaries honestly in `README.md` and `Architecture.md`: because background workers and SSE queues run inside a single FastAPI process with SQLite WAL, scaling to multiple API workers would mean moving jobs to Celery or ARQ and SSE fan-out to Redis Pub/Sub. Thanks for watching."
