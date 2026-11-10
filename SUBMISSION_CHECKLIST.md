# Submission Checklist — Arham Fintech BSE Trade Operations Dashboard

Use this checklist before pushing to GitHub and emailing your final submission.

---

## 1. GitHub Readiness

- [x] Inspect [.gitignore](./.gitignore) — excludes `.env`, `.env.*` (while keeping `*.env.example`), `.venv/`, `node_modules/`, `dist/`, `build/`, `frontend/dist/`, `*.tsbuildinfo`, `backend/data/`, `*.db*`, `__pycache__/`, `.pytest_cache/`, temporary/backup files, and `*.log`.
- [x] Confirm no real `.env` files, API keys, credentials, local SQLite databases, or hardcoded local machine paths exist in tracked files.
- [ ] Verify GitHub repository visibility (`https://github.com/mandar1818/ArhamFintech-TradeDashboard`) and confirm `README.md` and `Architecture.md` Mermaid diagrams render cleanly in an incognito browser tab.

---

## 2. Final Application Testing

- [x] Backend tests pass (`backend\.venv\Scripts\python.exe -m pytest backend\tests -v`).
- [x] Strict TypeScript check and Vite production build pass (`tsc` + `npm --prefix frontend run build`).
- [ ] Verify live runtime manually before recording:
  - Copy `backend\.env.example` to `backend\.env` and `frontend\.env.example` to `frontend\.env` (set `BSE_PULL_DELAY_SECONDS=15` during live verification/demo).
  - Start backend: `cd backend && .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
  - Start frontend: `cd frontend && npm run dev`
  - Check `http://127.0.0.1:8000/docs`, `http://127.0.0.1:8000/health`, and `http://127.0.0.1:5173`.
  - Test search, symbol filter, client filter, sorting, pagination, `Pull BSE Trades` (`202 Accepted` + SSE live progress + automatic post-completion update), and concurrent `409 Conflict`.

---

## 3. Documentation Verification

- [x] [README.md](./README.md) reviewed (purpose, problem statement, stack, architecture summary, structure, install/run instructions, configuration variables, API reference, test commands, and honest known limitations).
- [x] [Architecture.md](./Architecture.md) reviewed (Mermaid diagrams, request/ingestion/SSE lifecycles, 30s timeout avoidance, SQLite WAL & schema integrity, failure/restart handling, scaling constraints).
- [x] `.env.example`, `backend/.env.example`, and `frontend/.env.example` reflect default `BSE_PULL_DELAY_SECONDS=900` (15 minutes) with instructions for testing `10–20` seconds.
- [ ] [VIDEO_WALKTHROUGH.md](./VIDEO_WALKTHROUGH.md) reviewed before recording the 5-minute walkthrough.

---

## 4. Video Recording

- [ ] Follow [VIDEO_WALKTHROUGH.md](./VIDEO_WALKTHROUGH.md) (~5 minutes total).
- [ ] Confirm screen capture resolution (1080p readable text) and clear microphone audio.
- [ ] Verify DevTools Network tab (`GET /events` EventStream + `202 Accepted` on `POST /pull-trades`) and Swagger `/docs` are legible on recording.
- [ ] Upload video (Loom / Google Drive / unlisted YouTube) and verify **anyone with the link can view** in an incognito window before attaching the URL.

---

## 5. Submission Email Details (Send Manually)

- **To:** `chirag.g@arhamfintech.ai`
- **CC:** `hr@arhamfintech.ai`
- **Subject:** `Software Engineer Technical Assessment Submission – BSE Trade Operations Dashboard`

### Suggested Email Body Template

```text
Hi Chirag and Arham Fintech Team,

Please find my technical assessment submission for the BSE Trade Operations Dashboard below:

- GitHub Repository: https://github.com/mandar1818/ArhamFintech-TradeDashboard
- 5-Minute Video Walkthrough: <INSERT_VIDEO_LINK>

Summary of Implementation:
- Backend: Python FastAPI, SQLite (WAL mode) with SQLAlchemy, asynchronous background ingestion worker with retries and atomic ON CONFLICT deduplication, and Server-Sent Events (GET /events).
- Frontend: React + TypeScript + Vite operations dashboard consuming GET /getTrades immediately and syncing via native browser EventSource without interval polling.
- Testing & Documentation: 12 automated backend pytest integration/unit tests, strict TypeScript + Vite production build verification, Swagger OpenAPI docs (/docs), README.md, and Architecture.md.

Local Quick Start:
1. Copy backend/.env.example to backend/.env (set BSE_PULL_DELAY_SECONDS=15 for quick local testing; defaults to 900s).
2. Run backend from backend/: uvicorn app.main:app --host 127.0.0.1 --port 8000
3. Run frontend from frontend/: npm install && npm run dev

Thank you for your time and consideration.

Best regards,
<YOUR_NAME>
<YOUR_CONTACT_DETAILS>
```
