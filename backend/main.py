import uuid
import os
import json
import time
import secrets
import threading
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


from fastapi import FastAPI, HTTPException, UploadFile, File, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from tools import extract_values
from agent import run_agent_turn, GROQ_MODEL
from tools import save_qa_tool, record_score
from groq import Groq


app = FastAPI(
    title="VoxHire API",
    description="AI-powered mock interview platform backend.",
    version="1.0.0",
    contact={"name": "Akshat Trivedi", "url": "https://github.com/Akshat-Trivedi14"},
)

_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
# Support wildcard "*" to allow all origins (useful when frontend domain changes),
# or comma-separated list of specific origins for tighter control.
_allow_all = _raw_origins.strip() == "*"
_allowed_origins = ["*"] if _allow_all else [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=not _allow_all,  # credentials require explicit origins, not "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session store: loaded from disk on startup, written on every save.
# Survives backend restarts on Render (persistent disk / /tmp fallback).
_SESSION_FILE = os.path.join(os.path.dirname(__file__), "session_store.json")
_store_lock = threading.Lock()

def _load_store() -> dict:
    try:
        with open(_SESSION_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _flush_store(store: dict) -> None:
    try:
        with open(_SESSION_FILE, "w") as f:
            json.dump(store, f)
    except Exception as e:
        print(f"Warning: could not persist session store: {e}")

_session_qa: dict[str, list] = _load_store()

# ── Evaluation cache ──────────────────────────────────────────────────────
# The LLM evaluation is generated ONCE per session and persisted here, so the
# candidate's result page and the admin's result page (and their PDF downloads)
# always show the exact same score and feedback. Without this cache, every page
# load re-ran the LLM and produced a slightly different evaluation.
_EVAL_FILE = os.path.join(os.path.dirname(__file__), "eval_store.json")
_eval_lock = threading.Lock()

def _load_eval_store() -> dict:
    try:
        with open(_EVAL_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _flush_eval_store(store: dict) -> None:
    try:
        with open(_EVAL_FILE, "w") as f:
            json.dump(store, f)
    except Exception as e:
        print(f"Warning: could not persist eval store: {e}")

_eval_store: dict = _load_eval_store()

# ── Invite codes ──────────────────────────────────────────────────────────
# Dynamic single-use invite codes generated on demand by the operator via the
# /api/admin/* endpoints. Persisted to disk the same way as the session store so
# codes survive backend restarts. Each entry: {created_at, expires_at, used}.
_INVITE_FILE = os.path.join(os.path.dirname(__file__), "invite_store.json")
_invite_lock = threading.Lock()
_INVITE_TTL_SECONDS = 24 * 60 * 60  # a fresh code stays valid 24h if never used
# Unambiguous alphabet — no 0/O or 1/I, so codes are easy to read aloud/type.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

def _load_invite_store() -> dict:
    try:
        with open(_INVITE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _flush_invite_store(store: dict) -> None:
    try:
        with open(_INVITE_FILE, "w") as f:
            json.dump(store, f)
    except Exception as e:
        print(f"Warning: could not persist invite store: {e}")

_invite_store: dict = _load_invite_store()

def _generate_invite_code(length: int = 8) -> str:
    """Return a random code that is not already present in the store."""
    while True:
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))
        if code not in _invite_store:
            return code

def _consume_invite_code(code: str, session_id: str) -> bool:
    """Atomically validate and burn a dynamic invite code.

    Returns True only if the code exists, is unused, and is not expired — in
    which case it is marked used and linked to the session it created, so it can
    never be redeemed again. Any failure (unknown/used/expired) returns False
    without mutating the store.
    """
    with _invite_lock:
        entry = _invite_store.get(code)
        if not entry or entry.get("used"):
            return False
        if time.time() > entry.get("expires_at", 0):
            return False
        entry["used"] = True
        entry["used_at"] = time.time()
        entry["session_id"] = session_id
        _flush_invite_store(_invite_store)
        return True

# ── Admin session tokens ──────────────────────────────────────────────────
# Short-lived bearer tokens issued after a correct admin-password check. Held in
# memory only (the operator re-enters the password if the backend restarts).
_admin_tokens: dict[str, float] = {}
_ADMIN_TOKEN_TTL_SECONDS = 6 * 60 * 60  # 6h operator session

def _issue_admin_token() -> str:
    now = time.time()
    # Opportunistically prune expired tokens so the dict can't grow unbounded.
    for tok in [t for t, exp in _admin_tokens.items() if exp < now]:
        _admin_tokens.pop(tok, None)
    token = secrets.token_urlsafe(32)
    _admin_tokens[token] = now + _ADMIN_TOKEN_TTL_SECONDS
    return token

def _valid_admin_token(token: str) -> bool:
    if not token:
        return False
    expires_at = _admin_tokens.get(token)
    if expires_at is None:
        return False
    if time.time() > expires_at:
        _admin_tokens.pop(token, None)
        return False
    return True


# ── Simple in-memory rate limiting ────────────────────────────────────────
# Fixed per-IP sliding-window counters, held in memory (same tradeoff as the
# admin-token store above: not distributed, resets on restart — fine for
# abuse/brute-force deterrence on a single instance rather than a hard
# security boundary).
_rate_buckets: dict[str, list[float]] = {}
_rate_lock = threading.Lock()

def _client_ip(request: Request) -> str:
    # Render (and most PaaS) sit behind a proxy — the real client IP is the
    # first hop in X-Forwarded-For, not request.client.host (that's the proxy).
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def _rate_limited(key: str, limit: int, window_seconds: int) -> bool:
    """True if `key` has already hit `limit` calls within the trailing window."""
    now = time.time()
    with _rate_lock:
        hits = _rate_buckets.setdefault(key, [])
        cutoff = now - window_seconds
        while hits and hits[0] < cutoff:
            hits.pop(0)
        if len(hits) >= limit:
            return True
        hits.append(now)
        return False

class ChatRequest(BaseModel):
    session_id: str
    message: str
    domain: str | None = None
    # The name as typed on the setup form — authoritative over whatever name
    # the model might infer from the transcribed "introduce yourself" answer,
    # since speech-to-text frequently mangles non-English (e.g. Hindi) names.
    name: str | None = None

class InterviewResult(BaseModel):
    score: float
    feedback: str
    # Per-category percentages parsed from the evaluation, computed server-side
    # so the breakdown cannot be forged from the browser/devtools.
    communication: int = 0
    technical: int = 0
    problem_solving: int = 0
    photo: str = ""
    name: str = ""
    email: str = ""
    role: str = ""
    tab_switches: int = 0
    face_lost_count: int = 0
    face_lost_seconds: int = 0
    multiple_faces_count: int = 0
    movement_events: int = 0

class AdminVerifyRequest(BaseModel):
    password: str

class SaveRequest(BaseModel):
    question: str
    answer: str
    session_id: str | None = None
    name: str | None = None
    email: str | None = None
    role: str | None = None
    tab_switches: int | None = None
    face_lost_count: int | None = None
    face_lost_seconds: int | None = None
    multiple_faces_count: int | None = None
    movement_events: int | None = None
    # Interview-time webcam snapshot (data URL). Sent once; stored on the first
    # entry of the session. Optional — absence just means no photo is shown.
    photo: str | None = None

@app.get("/api/check")
def start_chek():
    return {"session": " API is working fine"}
@app.get("/api/start")
def start_session(code: str | None = None):
    # Invite gate. Two independent sources, checked in order:
    #   1. Dynamic single-use codes minted via /api/admin/invite (consumed here).
    #   2. Static always-valid codes from the INVITE_CODES env var (fallback).
    # The gate is active whenever either mechanism is configured; if neither is
    # (e.g. local development with no ADMIN_PASSWORD and no INVITE_CODES), it is
    # disabled and any request is allowed through — preserving prior behavior.
    provided = (code or "").strip()
    static_codes = [c.strip() for c in os.getenv("INVITE_CODES", "").split(",") if c.strip()]
    admin_configured = bool(os.getenv("ADMIN_PASSWORD", "").strip())
    gate_enabled = bool(static_codes) or admin_configured

    # Generate the session id up front so a dynamic code can be linked to the
    # session it creates (lets the admin page map code → session → result).
    session_id = str(uuid.uuid4())

    if gate_enabled:
        allowed = False
        # Try the dynamic store first — this burns the code and links this session.
        if provided and _consume_invite_code(provided, session_id):
            allowed = True
        # Fall back to a static always-valid code (never consumed, never linked).
        elif provided and provided in static_codes:
            allowed = True
        if not allowed:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired invite code. Please check the code you received and try again.",
            )

    return {"session_id": session_id}


@app.post("/api/admin/verify")
def admin_verify(request: AdminVerifyRequest, http_request: Request):
    """Exchange the admin password for a short-lived operator token."""
    # 5 attempts per 15 minutes per IP — generous for a human mistyping their
    # password, but shuts down automated brute-forcing of ADMIN_PASSWORD.
    if _rate_limited(f"admin-verify:{_client_ip(http_request)}", limit=5, window_seconds=900):
        raise HTTPException(status_code=429, detail="Too many attempts. Please try again later.")

    admin_password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not admin_password:
        raise HTTPException(status_code=503, detail="Admin access is not configured on the server.")
    # Constant-time comparison to avoid leaking the password via timing.
    if not secrets.compare_digest(request.password, admin_password):
        raise HTTPException(status_code=401, detail="Incorrect password.")
    token = _issue_admin_token()
    return {"token": token, "expires_in": _ADMIN_TOKEN_TTL_SECONDS}


@app.post("/api/admin/invite")
def create_invite(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
    """Mint a fresh single-use invite code (requires a valid operator token)."""
    if not _valid_admin_token(x_admin_token or ""):
        raise HTTPException(status_code=401, detail="Invalid or expired admin session. Please sign in again.")
    now = time.time()
    entry = {"created_at": now, "expires_at": now + _INVITE_TTL_SECONDS, "used": False}
    with _invite_lock:
        code = _generate_invite_code()
        _invite_store[code] = entry
        _flush_invite_store(_invite_store)
    return {"code": code, "expires_at": entry["expires_at"], "valid_hours": _INVITE_TTL_SECONDS // 3600}


@app.get("/api/admin/invites")
def list_invites(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
    """List every minted code with its status and (once redeemed) which session
    and candidate it produced. Powers the admin console's code table."""
    if not _valid_admin_token(x_admin_token or ""):
        raise HTTPException(status_code=401, detail="Invalid or expired admin session. Please sign in again.")
    now = time.time()
    with _invite_lock:
        snapshot = list(_invite_store.items())
    items = []
    for code, entry in snapshot:
        used = bool(entry.get("used"))
        expires_at = entry.get("expires_at", 0)
        session_id = entry.get("session_id")
        name, email, has_result = "", "", False
        # Pull the candidate's details (and confirm a result exists) from the
        # saved Q&A for the linked session, if the interview produced any answers.
        if session_id and _session_qa.get(session_id):
            first = _session_qa[session_id][0]
            name = first.get("Name") or ""
            email = first.get("Email") or ""
            has_result = True
        # Status:
        #   used   → redeemed and the candidate answered at least one question
        #   aborted→ redeemed but no answer was ever saved
        #   expired→ never redeemed and past its expiry
        #   unused → never redeemed, still valid
        if used:
            status = "used" if has_result else "aborted"
        elif now > expires_at:
            status = "expired"
        else:
            status = "unused"
        items.append({
            "code": code,
            "status": status,
            "created_at": entry.get("created_at"),
            "expires_at": expires_at,
            "session_id": session_id,
            "name": name,
            "email": email,
            "has_result": has_result,
        })
    items.sort(key=lambda x: x.get("created_at") or 0, reverse=True)
    return {"invites": items}


@app.delete("/api/admin/invite/{code}")
def delete_invite(code: str, x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
    """Delete a single invite code from the store (requires operator token)."""
    if not _valid_admin_token(x_admin_token or ""):
        raise HTTPException(status_code=401, detail="Invalid or expired admin session. Please sign in again.")
    with _invite_lock:
        existed = _invite_store.pop(code, None) is not None
        if existed:
            _flush_invite_store(_invite_store)
    if not existed:
        raise HTTPException(status_code=404, detail="Code not found.")
    return {"status": "deleted", "code": code}


@app.post("/api/chat")
def chat_endpoint(request: ChatRequest, http_request: Request):
    # Generous cap — a full 9-question interview makes ~9 calls here, so this
    # only bites automated abuse/cost-drain, never a real candidate.
    if _rate_limited(f"chat:{_client_ip(http_request)}", limit=60, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down and try again shortly.")
    try:
        print ("Received chat request:", request)
        agent_response = run_agent_turn(
    message=request.message,
    session_id=request.session_id,
    domain=request.domain,
    name=request.name,
)

    except Exception as e:
        # Log the real error server-side only — never echo internal exception
        # details (stack internals, library errors) back to the client.
        print(f"ERROR in /api/chat: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate the next question. Please try again.")

    return agent_response


@app.post("/api/save")
def save_endpoint(request: SaveRequest):
    # Store in memory and persist to disk so restarts don't lose data
    if request.session_id:
        with _store_lock:
            if request.session_id not in _session_qa:
                _session_qa[request.session_id] = []
            _session_qa[request.session_id].append({
                "Question": request.question,
                "Answer": request.answer,
                "Session_id": request.session_id,
                "Name": request.name or "",
                "Email": request.email or "",
                "Role": request.role or "",
                "TabSwitches": request.tab_switches or 0,
                "FaceLostCount": request.face_lost_count or 0,
                "FaceLostSeconds": request.face_lost_seconds or 0,
                "MultipleFacesCount": request.multiple_faces_count or 0,
                "MovementEvents": request.movement_events or 0,
            })
            # Keep the snapshot on the FIRST entry only (that's what the report
            # reads), and never overwrite one already captured. This also avoids
            # duplicating the base64 image across every Q&A entry.
            if request.photo and not _session_qa[request.session_id][0].get("Photo"):
                _session_qa[request.session_id][0]["Photo"] = request.photo
            _flush_store(_session_qa)

    # Also persist to CSV + Google Sheets (best effort)
    try:
        save_qa_tool(
            request.question, request.answer, request.session_id,
            request.name, request.email, request.role,
            request.tab_switches, request.face_lost_count, request.face_lost_seconds,
            request.multiple_faces_count, request.movement_events,
            request.photo,
        )
    except Exception:
        pass

    return {"status": "ok"}

_MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10MB — comfortably covers a 10-minute single answer at typical webm/Opus bitrates, well above realistic usage (a full 9-question interview is 10-15 min total)

@app.post("/api/transcribe")
async def transcribe_audio(file: UploadFile = File(...), http_request: Request = None):
    """Transcribe audio using Groq Whisper."""
    if _rate_limited(f"transcribe:{_client_ip(http_request)}", limit=60, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down and try again shortly.")

    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")
    client = Groq(api_key=groq_api_key)
    audio_bytes = await file.read()
    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large.")
    try:
        transcription = client.audio.transcriptions.create(
            file=(file.filename or "audio.webm", audio_bytes),
            model="whisper-large-v3-turbo",
            language="en",
            response_format="verbose_json",
            temperature=0.0,
        )
        text = (transcription.text or "").strip()

        # Whisper hallucinates phrases like "Thank you." on silent audio.
        # verbose_json exposes no_speech_prob per segment; treat high values as silence.
        segments = getattr(transcription, "segments", None) or []
        no_speech_probs = []
        for seg in segments:
            prob = seg.get("no_speech_prob") if isinstance(seg, dict) else getattr(seg, "no_speech_prob", None)
            if prob is not None:
                no_speech_probs.append(prob)
        if no_speech_probs and (sum(no_speech_probs) / len(no_speech_probs)) > 0.6:
            return {"transcript": "", "warning": "no_speech_detected"}

        # Whisper's signature hallucinations on silence — a real answer is never
        # just one of these phrases.
        HALLUCINATION_PHRASES = {
            "thank you", "thank you.", "thanks.", "thanks",
            "thanks for watching", "thanks for watching.",
            "thank you for watching", "thank you for watching.",
            "you", "you.", "bye.", "bye", ".", "",
        }
        if text.lower().strip() in HALLUCINATION_PHRASES:
            return {"transcript": "", "warning": "no_speech_detected"}

        return {"transcript": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

@app.get("/api/log/{session_id}")
async def get_interview_results(session_id: str) -> InterviewResult:
    '''Generate interview evaluation using Groq LLM based on the interview log.'''
    Groq_api_key = os.getenv("GROQ_API_KEY")

    # Check in-memory store first (most reliable on Render)
    if session_id in _session_qa and _session_qa[session_id]:
        log = _session_qa[session_id]
        print(f"Loaded {len(log)} Q&A pairs from memory for session {session_id}")
    else:
        log_str = extract_values(session_id_to_find=session_id)
        print("Extracted log:", log_str)
        try:
            log = json.loads(log_str)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Failed to parse interview log.")

    if not log:
        raise HTTPException(status_code=404, detail="Interview log not found. Please complete the interview first.")

    first_entry = log[0]

    # Serve the stored evaluation if this session was already evaluated, so
    # every viewer (candidate or admin) gets the identical score and feedback.
    cached = _eval_store.get(session_id)
    if cached and "score" in cached and "feedback" in cached:
        score = float(cached["score"])
        feedback = str(cached["feedback"])
        return _build_result(log, first_entry, score, feedback)

    transcript = f"""
        Interview for: {first_entry.get('Role', 'N/A')}
        Candidate: {first_entry.get('Name', 'N/A')} ({first_entry.get('Email', 'N/A')})

        Questions and Answers:
    """
    for idx, qa in enumerate(log, 1):
        transcript += f"\nQ{idx}: {qa.get('Question', 'N/A')}\n"
        transcript += f"A{idx}: {qa.get('Answer', 'N/A')}\n"

    # The interview extends past the 9-question minimum only when the
    # candidate is already performing well (see agent.py's adaptive-length
    # logic) — reaching that extended stage is itself a signal of sustained
    # strength, so responses from question 13 onward get graded on a
    # slightly gentler curve. Only added to the prompt when it actually
    # applies, so a normal 9-question interview costs no extra tokens here.
    extension_note = ""
    if len(log) > 12:
        extension_note = (
            f"\nEXTENDED INTERVIEW NOTE: this interview ran to {len(log)} questions "
            "(beyond the normal 9), which only happens when the candidate was already "
            "performing well through question 12 — reaching this stage is itself a "
            "positive signal. For responses from question 13 onward specifically: score "
            "slightly more generously than the strict scale below would otherwise imply — "
            "roughly +0.2 for genuinely strong answers in that range, and about 0.2 less "
            "harsh for weaker ones there. Questions 1-12 are still graded on the normal "
            "strict scale with no adjustment.\n"
        )

    prompt = f"""You are an expert technical interviewer evaluating a candidate's interview performance.
{extension_note}

{transcript}

Provide a concise evaluation in the following format:

SCORE: [number between 0-10 with one decimal, e.g., 7.5]

FEEDBACK:

## Overall Performance
[2-3 sentences summarizing the candidate's performance]

## Strengths
- [Strength 1]
- [Strength 2]
- [Strength 3]

## Areas for Improvement
- [Specific actionable improvement 1]
- [Specific actionable improvement 2]
- [Specific actionable improvement 3]

## Communication ([score out of 100]%)
[1-2 sentences on clarity, articulation, and engagement]

## Technical Knowledge ([score out of 100]%)
[1-2 sentences on depth and accuracy of technical understanding]

## Problem-Solving ([score out of 100]%)
[1-2 sentences on approach and methodology]

EVALUATION GUIDELINES:
- SCORE: Provide an overall score between 0-10 with one decimal place based on complete performance.
- STRICT SCORING SCALE — you are a bar-raiser at a top-tier company; grade like one:
  * 0.0-3.0: Weak — vague, incorrect, or off-topic answers; little demonstrated understanding
  * 3.1-5.0: Below the bar — partial understanding, shallow answers, misses the WHY behind concepts
  * 5.1-6.7: Solid but ordinary — mostly correct, reasonable depth; THIS IS WHERE MOST CANDIDATES LAND. A decent, competent interview caps at 6.7.
  * 6.8-8.0: VERY RARE — reserved for consistently precise, deep answers covering trade-offs and edge cases unprompted, with strong reasoning on nearly every question
  * 8.1-10.0: EXTREMELY RARE, almost never given — flawless, expert-level answers throughout that would impress a senior interviewer at a top company; anything above 9 should essentially never happen
- The vast majority of interviews MUST score 6.7 or below. Exceeding 6.7 requires spectacular, consistently outstanding answers across the whole transcript — treat it as an exception you must justify with specific quotes.
- Short, generic, or partially wrong answers must pull the score down sharply. Never give benefit of the doubt.
- SKIPPED / REFUSED / NON-ANSWERS: treat these as failures, not neutral gaps. If the candidate repeatedly says things like "skip this", "I don't know", "pass", gives a one-word non-answer, or otherwise declines to engage with most questions, that is disengagement, not partial credit — score the overall interview in the 2.0-3.0 range (or lower if nearly every question was skipped/blank). Do not let a couple of stronger answers average this up into the "Below the bar" or "Solid" bands — count each skip as a near-zero for that question when judging the whole transcript.
- PERCENTAGES: Assign individual scores out of 100 for each category independently, applying the same strictness (most candidates: 40-67%; above 67% only for genuinely strong areas):
  * 86-100%: Exceptional performance, demonstrates mastery (rare)
  * 68-85%: Strong performance, shows solid competency (uncommon)
  * 55-67%: Good performance, meets expectations
  * 45-54%: Adequate performance, room for improvement
  * 30-44%: Below expectations, needs significant improvement
  * Below 30%: Poor performance, major gaps identified
- Reference specific examples from the transcript to justify each score.
- Scores should reflect actual demonstrated capability, not potential.
- Keep each section brief and actionable. Use bullet points for lists. Be direct and constructive.
"""
    
    client = Groq(api_key=Groq_api_key)

    try:
        message = client.chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=2000,
            temperature=0.0,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Parse the response
        response_text = message.choices[0].message.content
    except Exception as e:
        print(f"ERROR generating evaluation for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate the evaluation. Please try again shortly.")

    
    # Extract score and feedback
    score = extract_score(response_text)
    feedback = extract_feedback(response_text)
    # Fill the score into this session's existing row. The previous call here
    # appended a free-floating ["Evaluation", "Score: x", "Feedback: y"] row,
    # whose cells landed under the Question/Answer/Session_id headers and so
    # showed up as a bogus extra record in the sheet.
    record_score(session_id, score)

    # Persist so later views of this session reuse this exact evaluation.
    with _eval_lock:
        _eval_store[session_id] = {"score": score, "feedback": feedback, "evaluated_at": time.time()}
        _flush_eval_store(_eval_store)

    return _build_result(log, first_entry, score, feedback)


def _build_result(log: list, first_entry: dict, score: float, feedback: str) -> InterviewResult:
    # Counters are cumulative on the frontend, so the highest value is the final total.
    # Values may come back as strings (CSV/Sheets fallback) — parse defensively.
    def _final(key: str) -> int:
        values = []
        for entry in log:
            try:
                values.append(int(float(entry.get(key) or 0)))
            except (ValueError, TypeError):
                pass
        return max(values, default=0)

    communication, technical, problem_solving = extract_category_scores(feedback, score)

    return InterviewResult(
        score=score,
        feedback=feedback,
        communication=communication,
        technical=technical,
        problem_solving=problem_solving,
        photo=str(first_entry.get("Photo") or ""),
        name=str(first_entry.get("Name") or ""),
        email=str(first_entry.get("Email") or ""),
        role=str(first_entry.get("Role") or ""),
        tab_switches=_final("TabSwitches"),
        face_lost_count=_final("FaceLostCount"),
        face_lost_seconds=_final("FaceLostSeconds"),
        multiple_faces_count=_final("MultipleFacesCount"),
        movement_events=_final("MovementEvents"),
    )

def extract_category_scores(feedback: str, score: float) -> tuple[int, int, int]:
    """Parse the per-category percentages the LLM embeds in its feedback headings,
    e.g. '## Communication (72%)'. These are the authoritative breakdown values —
    parsing happens on the server from the persisted evaluation so the numbers
    are identical for every viewer and cannot be tampered with client-side.

    Falls back to a score-derived value only when a heading has no percentage.
    """
    import re

    def _find(label_pattern: str) -> int | None:
        # Match e.g. "## Communication (72%)" or "Communication Skills - 72%"
        m = re.search(
            rf'{label_pattern}[^\n\d]*?(\d{{1,3}})\s*%',
            feedback,
            re.IGNORECASE,
        )
        if m:
            return max(0, min(int(m.group(1)), 100))
        return None

    fallback = int(max(0.0, min(score, 10.0)) * 10)

    communication = _find(r'Communication')
    technical = _find(r'Technical\s*Knowledge')
    problem_solving = _find(r'Problem[\s-]*Solving')

    return (
        communication if communication is not None else fallback,
        technical if technical is not None else fallback,
        problem_solving if problem_solving is not None else fallback,
    )


def extract_score(response: str) -> float:
    """Extract the score from the LLM's response."""
    import re
    
    # Tolerate markdown emphasis around the label (models often render it as
    # "**SCORE:** 5.0") — \**\s* on both sides of the colon absorbs that.
    score_match = re.search(r'\**SCORE:\**\s*(\d+\.?\d*)', response, re.IGNORECASE)

    if score_match:
        try:
            score = float(score_match.group(1))
            return min(max(score, 0), 10)
        except (ValueError, IndexError):
            pass
    
    fallback_match = re.search(r'(\d+\.?\d*)\s*/\s*10', response)
    if fallback_match:
        try:
            return float(fallback_match.group(1))
        except (ValueError, IndexError):
            pass

    # Parsing failed — return a mid-band score consistent with the strict scale
    return 5.0

def extract_feedback(response: str) -> str:
    """Extract the feedback section from the LLM's response."""
    import re
    
    feedback_match = re.search(r'\**FEEDBACK:\**\s*(.+)', response, re.IGNORECASE | re.DOTALL)

    if feedback_match:
        return feedback_match.group(1).strip().lstrip('*').strip()

    score_match = re.search(r'\**SCORE:\**\s*\d+\.?\d*', response, re.IGNORECASE)
    if score_match:
        return response[score_match.end():].strip()

    return response.strip()

    
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
