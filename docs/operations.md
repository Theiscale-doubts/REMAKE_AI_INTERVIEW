# Operations reference

Internal notes. Not for distribution.

---

## APIs Used and How to Get Them

### 1. Groq API — **Required**

Used for: audio transcription (Whisper) and interview evaluation (openai/gpt-oss-120b), plus a fallback for the interview agent itself if the OpenAI call fails.

**Get it:**
1. Go to [console.groq.com](https://console.groq.com)
2. Sign up for a free account
3. Navigate to **API Keys** → **Create API Key**
4. Copy the key (starts with `gsk_...`)

**Environment variable:**
```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
```

**Free tier limits:** 14,400 requests/day, 30 requests/minute (as of 2025).

---

### 2. OpenAI API — **Required**

Used for: the AI interviewer agent (primary LLM, `gpt-4o-mini`). Falls back to Groq automatically if the call fails or rate-limits.

**Get it:**
1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Sign in / create an account and set up billing (no free tier — usage is billed per token)
3. Click **Create new secret key**
4. Copy the key (starts with `sk-...`)

**Environment variable:**
```
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Pricing:** `gpt-4o-mini` is $0.15 / 1M input tokens, $0.60 / 1M output tokens (as of 2026) — chosen specifically for low per-interview cost.

---

### 3. Google Sheets API — **Optional**

Used for: persisting interview Q&A logs to a Google Sheet for review. The app falls back to local CSV if not configured.

**Get it (Service Account method):**
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project (or select an existing one)
3. Enable the **Google Sheets API** and **Google Drive API** in *APIs & Services → Library*
4. Go to *APIs & Services → Credentials → Create Credentials → Service Account*
5. Fill in a name, click **Create and Continue**, then **Done**
6. Click the service account you just created → **Keys** tab → **Add Key → Create new key → JSON**
7. Download the `.json` file — this is your credentials file
8. Open the file and copy its entire contents as a single-line JSON string
9. Create a Google Sheet named **"Interview"** and share it (Editor access) with the `client_email` from the credentials JSON

**Environment variable:**
```
google_credentials_json={"type":"service_account","project_id":"...","private_key_id":"...","private_key":"-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n","client_email":"...","client_id":"...","auth_uri":"...","token_uri":"...","auth_provider_x509_cert_url":"...","client_x509_cert_url":"..."}
```

> Paste the full JSON as one line — no line breaks.

---

### 4. VITE_API_URL — **Required for production**

Tells the frontend where the backend is hosted.

**Environment variable (frontend build):**
```
VITE_API_URL=https://your-backend.onrender.com
```

For local development this defaults to `http://localhost:8000` if not set.

---

## Environment Variables Summary

### Backend — `backend/.env`

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key for Whisper transcription, evaluation, and the interview-agent fallback |
| `OPENAI_API_KEY` | Yes | OpenAI API key for the interview agent (primary LLM) |
| `google_credentials_json` | No | Full service account JSON (one line) for Google Sheets logging |
| `ALLOWED_ORIGINS` | No | Comma-separated frontend URLs for CORS (defaults to `*`) |
| `PORT` | No | Port to run on (defaults to `8000`) |

**Example `backend/.env`:**
```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
google_credentials_json={"type":"service_account",...}
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### Frontend — build-time env

| Variable | Required | Description |
|---|---|---|
| `VITE_API_URL` | Yes (prod) | Full URL of the deployed backend, e.g. `https://api.yourdomain.com` |

Set this in a `frontend/.env` file for local builds, or in your hosting dashboard for production.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/check` | Health check |
| `GET` | `/api/start` | Create a new session (returns `session_id`). Rate-limited: 2 per IP per 24 hours |
| `POST` | `/api/chat` | Send candidate message, get next interview question |
| `POST` | `/api/save` | Save a Q&A pair for a session |
| `POST` | `/api/transcribe` | Upload audio file, get transcript text back |
| `GET` | `/api/log/{session_id}` | Generate score + feedback for a completed session |

### POST /api/chat
```json
{
  "session_id": "uuid-string",
  "message": "candidate's answer text",
  "domain": "datascience"
}
```

### POST /api/save
```json
{
  "session_id": "uuid-string",
  "question": "What is overfitting?",
  "answer": "When a model memorizes training data...",
  "name": "Jane Doe",
  "email": "jane@example.com",
  "role": "Data Scientist"
}
```

### POST /api/transcribe
`multipart/form-data` with a `file` field containing a `.webm` / `.mp3` / `.wav` audio file.

---

## Rate Limiting

The backend enforces **2 interview sessions per IP address per 24 hours** to prevent abuse. This resets automatically. There is no persistent database for this — it lives in memory and resets on backend restart.
