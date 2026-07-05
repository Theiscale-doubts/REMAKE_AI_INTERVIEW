# VoxHire

AI-powered mock interview platform. Candidates pick a domain, speak or type their answers, and receive a detailed score + feedback report at the end.

## Documentation

| Doc | Description |
|---|---|
| [Architecture](docs/architecture.md) | System design, data flow, key decisions |
| [API Reference](docs/api-reference.md) | All endpoints with request/response shapes |
| [Backend Guide](docs/backend-guide.md) | Agent logic, session store, adding domains |
| [Frontend Guide](docs/frontend-guide.md) | Pages, routing, recording flow, build |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + TypeScript + Tailwind CSS |
| Routing | Wouter (hash-based, SPA-safe on static hosts) |
| Backend | FastAPI (Python 3.11) |
| AI Agent | LangChain — Google Gemini 2.5 Flash (primary) / Groq Llama 3.3 70B (fallback) |
| Transcription | Groq Whisper Large v3 Turbo |
| Evaluation | Groq Llama 3.3 70B Versatile |
| Data Storage | In-memory dict + JSON file persistence + Google Sheets (optional) |
| Deployment | Render.com (backend + frontend) or Hostinger (static frontend) |

---

## APIs Used and How to Get Them

### 1. Groq API — **Required**

Used for: audio transcription (Whisper) and interview evaluation (Llama 3.3).

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

### 2. Google Gemini API — **Required**

Used for: the AI interviewer agent (primary LLM). Falls back to Groq automatically if quota is hit.

**Get it:**
1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Sign in with a Google account
3. Click **Create API key** → choose a project (or create one)
4. Copy the key (starts with `AIza...`)

**Environment variable:**
```
GOOGLE_API_KEY=AIzaxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Free tier limits:** 1,500 requests/day on Gemini 2.5 Flash (as of 2025).

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
| `GROQ_API_KEY` | Yes | Groq API key for Whisper transcription and Llama evaluation |
| `GOOGLE_API_KEY` | Yes | Google Gemini API key for the interview agent |
| `google_credentials_json` | No | Full service account JSON (one line) for Google Sheets logging |
| `ALLOWED_ORIGINS` | No | Comma-separated frontend URLs for CORS (defaults to `*`) |
| `PORT` | No | Port to run on (defaults to `8000`) |

**Example `backend/.env`:**
```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
GOOGLE_API_KEY=AIzaxxxxxxxxxxxxxxxxxxxxxxxxx
google_credentials_json={"type":"service_account",...}
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### Frontend — build-time env

| Variable | Required | Description |
|---|---|---|
| `VITE_API_URL` | Yes (prod) | Full URL of the deployed backend, e.g. `https://api.yourdomain.com` |

Set this in a `frontend/.env` file for local builds, or in your hosting dashboard for production.

---

## Interview Domains

| Domain key | Description |
|---|---|
| `datascience` | Statistics, ML, feature engineering, model validation, A/B testing |
| `data_analytics` | SQL, dashboards, BI tools, KPIs, data storytelling |
| `hr` | Behavioral, situational, STAR-method, career goals, conflict resolution |
| `product` | Roadmap, prioritization (RICE/MoSCoW/Kano), user research, metrics |
| `frontend` | HTML/CSS, JavaScript, React, TypeScript, performance, accessibility |
| `devops` | CI/CD, Docker, Kubernetes, IaC, cloud, monitoring, Linux |

Each session runs **8–10 questions**. The agent tracks covered topics and never repeats.

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

## Local Development

### Backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt

# Create backend/.env with the variables listed above, then:
python main.py
# → running on http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install

# Optional: create frontend/.env
# VITE_API_URL=http://localhost:8000

npm run dev
# → running on http://localhost:5173
```

---

## Production Deployment

### Option A — Render.com (recommended)

The repo includes `render.yaml` which defines both services. Push to GitHub and connect the repo in the Render dashboard.

Set these environment variables in the Render dashboard for **voxhire-backend**:
- `GROQ_API_KEY`
- `GOOGLE_API_KEY`
- `google_credentials_json` (optional)
- `ALLOWED_ORIGINS` — set to your frontend URL

Set these for **voxhire-frontend**:
- `VITE_API_URL` — set to your backend service URL

Render's SPA rewrite rule (`/* → /index.html`) is already in `render.yaml`.

### Option B — Hostinger (static frontend)

1. Build the frontend:
   ```bash
   cd frontend
   npm run build
   ```
2. Upload the entire contents of `frontend/dist/public/` to your Hostinger `public_html/` folder.
3. The `.htaccess` file in `frontend/client/public/` is automatically included in the build — it handles SPA routing on Apache.
4. Deploy the backend separately (Render, Railway, etc.) and point `VITE_API_URL` to it before building.

---

## Project Structure

```
VoxHire-main/
├── backend/
│   ├── main.py             # FastAPI app, all endpoints
│   ├── agent.py            # LangChain interview agent (Gemini + Groq)
│   ├── tools.py            # CSV + Google Sheets persistence
│   ├── requirements.txt
│   └── .env                # (not committed) your API keys
├── frontend/
│   ├── client/
│   │   ├── src/
│   │   │   ├── App.tsx     # Router + route definitions
│   │   │   └── pages/      # Home, Interview, Results, NotFound
│   │   └── public/
│   │       └── .htaccess   # Apache SPA routing (copied into build)
│   ├── vite.config.ts
│   └── package.json
├── render.yaml             # Render.com deployment config
└── README.md
```

---

## Rate Limiting

The backend enforces **2 interview sessions per IP address per 24 hours** to prevent abuse. This resets automatically. There is no persistent database for this — it lives in memory and resets on backend restart.
