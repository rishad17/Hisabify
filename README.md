# TakaWise AI

Smart expense tracker and AI budget planner for Bangladeshi users. Record expenses by text or voice in **English, Bangla (বাংলা) or Banglish**, track multiple wallets (Cash, bKash, Nagad, bank), plan monthly budgets, simulate purchases, and ask questions about your own finances.

> 🚧 Work in progress. Phases 0–5 done: sign-in, wallets, manual tracking, and AI entry by text or voice (English, বাংলা, Banglish).

## Core principle

The LLM only turns language into structured *proposals* and numbers into explanations.
**Python computes every number, PostgreSQL stores it, and the user confirms every write.**

## Tech stack

| Layer | Tech |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, shadcn/ui, TanStack Query, React Router, Recharts |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy 2, Alembic, psycopg 3 |
| Database & auth | Supabase (PostgreSQL + Auth) |
| AI | Gemini (structured output + function calling), Groq Whisper as speech-to-text fallback |
| Hosting | Vercel (frontend), Render (backend), Supabase (DB) |

## Repository layout

```
takawise/
├─ frontend/   React app (Vite)
├─ backend/    FastAPI app
└─ .github/    CI: lint + test both apps on every push
```

## Local development

**Requirements:** Node 20+ and Python 3.12+.

### Backend

```bash
cd backend
python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1   |   macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # then edit values
uvicorn app.main:app --reload # http://localhost:8000  (docs at /docs)
```

Run the checks:

```bash
pytest
ruff check . && ruff format --check .
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local    # VITE_API_URL=http://localhost:8000
npm run dev                   # http://localhost:5173
```

Other scripts: `npm run build`, `npm run lint`, `npm run typecheck`.

## Environment variables

| Where | Variable | Purpose | Secret? |
|---|---|---|---|
| backend | `ENVIRONMENT` | `development` / `test` / `production` (production hides `/docs`) | no |
| backend | `CORS_ORIGINS` | Comma-separated allowed browser origins | no |
| backend | `DATABASE_URL`, `SUPABASE_URL` | Phase 1 | **yes** (DB URL) |
| backend | `GEMINI_API_KEY`, `GROQ_API_KEY` | Phases 4–5 | **yes** |
| frontend | `VITE_API_URL` | Backend base URL | no (public) |
| frontend | `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` | Phase 1 | no (public by design) |

Anything prefixed `VITE_` is bundled into public JavaScript. **AI keys and database credentials live only in the backend.**

## API conventions

- Base path: `/api/v1` (liveness check at `/health`)
- Every error uses one shape: `{"error": {"code": "...", "message": "...", "details": ...}}`
- Money is sent as decimal **strings** (`"1250.00"`), never floats.

## Roadmap

- [x] Phase 0: Project setup
- [x] Phase 1: Auth, schema (deploy pending)
- [x] Phase 2: Ledger core (wallets, transactions, transfers)
- [x] Phase 3: Manual UI
- [x] Phase 4: AI text entry
- [x] Phase 5: Voice entry
- [ ] Phase 6: Budgets and commitments
- [ ] Phase 7: Dashboard analytics
- [ ] Phase 8: Assistant and purchase simulator
- [ ] Phase 9: Forecast and adaptive budgets
- [ ] Phase 10: Hardening and launch
