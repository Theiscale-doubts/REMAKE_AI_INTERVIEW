# VoxHire

Internal AI voice-interview platform. Candidates redeem an invite code, answer
spoken questions from an adaptive interviewer, and a scored report is produced
for the hiring team.

> Private repository — internal use only. Not for redistribution.

## Stack

React + Vite + TypeScript (static frontend) · FastAPI + Python 3.11 (API) ·
LangChain over Groq / OpenAI · Google Sheets as the durable record.

## Layout

```
backend/    FastAPI service — app/ (package) and tests/
frontend/   React SPA — src/, built to dist/ as static files
docs/       setup, operations reference, agent notes, design handoff
```

## Running locally

Backend:

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in the values
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
pnpm install
pnpm dev
```

Tests (no network or API keys required):

```bash
cd backend && pip install -r requirements-dev.txt && pytest
```

## Documentation

Configuration, environment variables, endpoints and deployment are documented in
[`docs/`](docs/) — start with [setup](docs/setup.md) and
[operations](docs/operations.md).
