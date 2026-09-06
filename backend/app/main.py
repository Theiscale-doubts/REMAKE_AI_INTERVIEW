import uuid
import os
import json
import time
import logging
import bisect
import secrets
from contextlib import asynccontextmanager
import tempfile
import threading
from pathlib import Path
from dotenv import load_dotenv

# backend/ — the package lives in backend/app, so data files and .env sit one
# level up from this module rather than beside it.
_BACKEND_DIR = Path(__file__).resolve().parent.parent

# VOXHIRE_SKIP_DOTENV must be honoured HERE too, not only in tools.py: main is
# imported first and loads the .env into os.environ, so a guard further down
# the import chain is already too late to stop a test picking up real
# credentials and writing to the production spreadsheet.
if not os.getenv("VOXHIRE_SKIP_DOTENV"):
    load_dotenv(_BACKEND_DIR / ".env")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
log = logging.getLogger("voxhire.api")

from fastapi import FastAPI, HTTPException, UploadFile, File, Header, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from .storage import extract_values
from .agent import (
    run_agent_turn,
    end_session,
    session_count,
    GROQ_MODEL,
    NoLLMProviderError,
)
from .storage import (
    save_qa_tool,
    record_score,
    verify_sheets,
    sheets_status,
    search_sessions,
    invalidate_rows_cache,
    sync_queue_depth,
    flush_sync_queue,
)
from groq import Groq

# One shared Groq client. Building a client per request (as both /api/transcribe
# and /api/log used to) discards its connection pool every time, paying a fresh
# TLS handshake on each call — noticeable on Render's free tier, where latency
# is already the weak point. Built lazily so a missing key degrades that one
# endpoint instead of taking down startup.
_groq_client: Groq | None = None
_groq_client_lock = threading.Lock()


def _get_groq() -> Groq:
    global _groq_client
    if _groq_client is None:
        with _groq_client_lock:
            if _groq_client is None:
                key = os.getenv("GROQ_API_KEY", "").strip()
                if not key:
                    raise HTTPException(status_code=503, detail="Transcription/evaluation is not configured on the server.")
                _groq_client = Groq(api_key=key, timeout=60.0, max_retries=1)
    return _groq_client


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Startup checks: fail loudly about anything that silently loses data.

    Uses the lifespan API rather than the deprecated @app.on_event("startup").
    """
    if _DATA_DIR == str(_BACKEND_DIR):
        log.warning(
            "DATA_DIR is unset — JSON stores live in the app directory. On an "
            "ephemeral host (Render free tier) they are wiped on every deploy "
            "and cold start."
        )
    if not os.getenv("ADMIN_PASSWORD", "").strip() and not os.getenv("INVITE_CODES", "").strip():
        log.warning("No ADMIN_PASSWORD and no INVITE_CODES — /api/start is OPEN to anyone.")

    # One Sheets round trip, off the event loop. Sheets is the only durable copy
    # of an interview on an ephemeral host, so a broken credential must be
    # visible now — not after a redeploy has already destroyed the data.
    try:
        status = await run_in_threadpool(verify_sheets)
        if not status["reachable"]:
            log.critical(
                "DURABLE STORAGE UNAVAILABLE: %s | Completed interviews will be "
                "LOST on the next deploy or cold start.", status["detail"],
            )
    except Exception as exc:
        # Never let a check prevent the service from starting.
        log.error("Startup storage check failed to run: %s", exc)

    yield

    # Shutdown: give queued sheet writes a last chance to land. Render sends
    # SIGTERM before a deploy or a spin-down, so this is the difference between
    # a row reaching the durable store and sitting in a dead-letter file.
    try:
        stranded = await run_in_threadpool(flush_sync_queue, 8.0)
        if stranded:
            log.error("%d sheet write(s) could not be flushed before shutdown", stranded)
        else:
            log.info("Sheet write queue drained cleanly.")
    except Exception as exc:
        log.error("Failed to flush the sheet write queue: %s", exc)


app = FastAPI(
    lifespan=_lifespan,
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

# Hard ceiling on any request body. Starlette streams the body into memory, so
# without this a single client can push the 512MB instance into an OOM kill by
# POSTing a multi-hundred-megabyte payload — no auth required, since /api/save
# and /api/transcribe are both public by design.
_MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", str(12 * 1024 * 1024)))

# Global per-IP backstop across every endpoint, on top of the tighter
# per-endpoint limits below. Anything not individually limited is still covered.
_GLOBAL_RATE_LIMIT = int(os.getenv("GLOBAL_RATE_LIMIT", "240"))
_GLOBAL_RATE_WINDOW = 60


@app.middleware("http")
async def _guard_requests(request: Request, call_next):
    # Preflight must not be throttled or it breaks the browser, and it carries
    # no body worth checking.
    if request.method == "OPTIONS":
        return await call_next(request)

    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > _MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Request body too large."})

    if _rate_limited(f"global:{_client_ip(request)}", _GLOBAL_RATE_LIMIT, _GLOBAL_RATE_WINDOW):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please slow down and try again shortly."},
            headers={"Retry-After": str(_GLOBAL_RATE_WINDOW)},
        )

    response = await call_next(request)
    # Cheap hardening headers — this API is called cross-origin by the static
    # frontend, so there is no HTML to protect, but these cost nothing and stop
    # content-type games and referrer leakage of session ids in URLs.
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    return response

# ── On-disk stores ────────────────────────────────────────────────────────
# IMPORTANT — Render free tier has an EPHEMERAL filesystem. These files are
# wiped on every deploy and on every cold start after the service spins down
# (which the free tier does after ~15 minutes idle). Nothing written here
# survives that. Google Sheets (see tools.py) is the durable record; these
# files are a fast local cache in front of it.
#
# DATA_DIR points the stores at a mounted disk when one exists (Render paid
# tiers, or any host with a volume), which makes them genuinely durable with no
# code change. It falls back to the app directory, matching prior behavior.
_DATA_DIR = os.getenv("DATA_DIR", str(_BACKEND_DIR))
try:
    os.makedirs(_DATA_DIR, exist_ok=True)
except OSError as exc:
    log.warning("DATA_DIR %s is not writable (%s) — falling back to app dir", _DATA_DIR, exc)
    _DATA_DIR = str(_BACKEND_DIR)


def _load_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as exc:
        # A truncated file means a previous write was interrupted. Keep the
        # corrupt copy for post-mortem instead of silently overwriting it —
        # this is candidate interview data, and "it just came back empty" is
        # the worst possible failure mode for it.
        log.error("Store %s is unreadable (%s) — starting empty", path, exc)
        try:
            os.replace(path, path + ".corrupt")
            log.error("Corrupt store preserved at %s.corrupt", path)
        except OSError:
            pass
        return {}


def _flush_json(path: str, store: dict) -> None:
    """Write the store atomically.

    The previous implementation opened the real file and dumped straight into
    it: a crash, OOM kill, or Render spin-down mid-write left a half-written
    file that the next boot could not parse — and the old loader quietly
    treated that as an empty store, losing every session, evaluation or invite
    code it held. Writing to a temp file in the same directory and renaming it
    makes the swap atomic, so a reader sees either the old file or the new one.
    """
    tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(store, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception as exc:
        log.warning("Could not persist %s: %s", path, exc)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


_SESSION_FILE = os.path.join(_DATA_DIR, "session_store.json")
_store_lock = threading.Lock()
_session_qa: dict[str, list] = _load_json(_SESSION_FILE)

def _flush_store(store: dict) -> None:
    _flush_json(_SESSION_FILE, store)

# ── Evaluation cache ──────────────────────────────────────────────────────
# The LLM evaluation is generated ONCE per session and persisted here, so the
# candidate's result page and the admin's result page (and their PDF downloads)
# always show the exact same score and feedback. Without this cache, every page
# load re-ran the LLM and produced a slightly different evaluation.
_EVAL_FILE = os.path.join(_DATA_DIR, "eval_store.json")
_eval_lock = threading.Lock()
_eval_store: dict = _load_json(_EVAL_FILE)

def _flush_eval_store(store: dict) -> None:
    _flush_json(_EVAL_FILE, store)

# ── Invite codes ──────────────────────────────────────────────────────────
# Dynamic single-use invite codes generated on demand by the operator via the
# /api/admin/* endpoints. Each entry: {created_at, expires_at, used}.
#
# NOTE: on an ephemeral filesystem (Render free tier) minted codes do NOT
# survive a redeploy or a cold start. Use INVITE_CODES (static, env-based) for
# anything that has to keep working across restarts.
_INVITE_FILE = os.path.join(_DATA_DIR, "invite_store.json")
_invite_lock = threading.Lock()
_INVITE_TTL_SECONDS = 24 * 60 * 60  # a fresh code stays valid 24h if never used
# Unambiguous alphabet — no 0/O or 1/I, so codes are easy to read aloud/type.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_invite_store: dict = _load_json(_INVITE_FILE)

def _flush_invite_store(store: dict) -> None:
    _flush_json(_INVITE_FILE, store)

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


# ── In-memory rate limiting ───────────────────────────────────────────────
# Per-IP sliding-window counters. Not distributed and reset on restart, so this
# is abuse/DoS deterrence for a single instance rather than a hard security
# boundary — but on a free-tier box with one worker, shedding load early IS the
# availability strategy: one unthrottled client can otherwise consume the only
# worker and take the service down for everyone.
_rate_buckets: dict[str, list[float]] = {}
_rate_lock = threading.Lock()
_rate_last_prune = 0.0
# Ceiling on tracked keys. The bucket dict was previously never pruned: every
# distinct client IP added a permanent entry, so a spray of spoofed
# X-Forwarded-For values grew it without bound — the rate limiter itself became
# the memory-exhaustion vector it was supposed to prevent.
_RATE_MAX_KEYS = 20_000
_RATE_PRUNE_INTERVAL = 60.0


def _client_ip(request: Request | None) -> str:
    # Render (and most PaaS) sit behind a proxy — the real client IP is the
    # first hop in X-Forwarded-For, not request.client.host (that's the proxy).
    # Note this header is client-controlled and trivially spoofed; the pruning
    # above is what keeps a spoofing client from growing the bucket dict.
    if request is None:
        return "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else "unknown"


def _prune_rate_buckets(now: float) -> None:
    """Drop empty/stale buckets. Caller must hold _rate_lock."""
    global _rate_last_prune
    if now - _rate_last_prune < _RATE_PRUNE_INTERVAL and len(_rate_buckets) < _RATE_MAX_KEYS:
        return
    _rate_last_prune = now
    stale = [k for k, hits in _rate_buckets.items() if not hits or hits[-1] < now - 3600]
    for k in stale:
        _rate_buckets.pop(k, None)
    if len(_rate_buckets) > _RATE_MAX_KEYS:
        # Still over the ceiling: drop the least recently active keys.
        ordered = sorted(_rate_buckets.items(), key=lambda kv: kv[1][-1] if kv[1] else 0)
        for k, _ in ordered[: len(_rate_buckets) - _RATE_MAX_KEYS]:
            _rate_buckets.pop(k, None)


def _rate_limited(key: str, limit: int, window_seconds: int) -> bool:
    """True if `key` has already hit `limit` calls within the trailing window."""
    now = time.time()
    with _rate_lock:
        _prune_rate_buckets(now)
        hits = _rate_buckets.setdefault(key, [])
        cutoff = now - window_seconds
        # Bisect instead of pop(0) in a loop: popping from the head of a list is
        # O(n) per element, so a client sitting at the limit made every single
        # request quadratic in the window size.
        keep = bisect.bisect_left(hits, cutoff)
        if keep:
            del hits[:keep]
        if len(hits) >= limit:
            return True
        hits.append(now)
        return False


def _enforce(request: Request | None, bucket: str, limit: int, window_seconds: int) -> None:
    """Rate-limit helper that raises 429 directly."""
    if _rate_limited(f"{bucket}:{_client_ip(request)}", limit=limit, window_seconds=window_seconds):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please slow down and try again shortly.",
            headers={"Retry-After": str(window_seconds)},
        )

# Field ceilings. Every one of these arrives from an unauthenticated public
# endpoint, so an unbounded str was a direct path to filling memory, the JSON
# stores and the Google Sheet with junk. The limits sit far above any real
# value: a spoken answer is a few hundred characters, a name a few dozen.
_MAX_TEXT = 8_000            # one transcribed answer or generated question
_MAX_NAME = 120
_MAX_EMAIL = 254             # RFC 5321 maximum
_MAX_ROLE = 64
_MAX_PHOTO_CHARS = 900_000   # ~650KB decoded — a webcam JPEG data URL


class ChatRequest(BaseModel):
    session_id: str = Field(max_length=64)
    message: str = Field(max_length=_MAX_TEXT)
    domain: str | None = Field(default=None, max_length=_MAX_ROLE)
    # The name as typed on the setup form — authoritative over whatever name
    # the model might infer from the transcribed "introduce yourself" answer,
    # since speech-to-text frequently mangles non-English (e.g. Hindi) names.
    name: str | None = Field(default=None, max_length=_MAX_NAME)

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
    # Capped so an oversized password field cannot burn memory or comparison
    # time on a brute-force attempt.
    password: str = Field(max_length=256)

class SaveRequest(BaseModel):
    question: str = Field(max_length=_MAX_TEXT)
    answer: str = Field(max_length=_MAX_TEXT)
    session_id: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, max_length=_MAX_NAME)
    email: str | None = Field(default=None, max_length=_MAX_EMAIL)
    role: str | None = Field(default=None, max_length=_MAX_ROLE)
    # Proctoring counters are client-reported and therefore untrusted; bound
    # them so a forged payload cannot store absurd values in the report.
    tab_switches: int | None = Field(default=None, ge=0, le=100_000)
    face_lost_count: int | None = Field(default=None, ge=0, le=100_000)
    face_lost_seconds: int | None = Field(default=None, ge=0, le=100_000)
    multiple_faces_count: int | None = Field(default=None, ge=0, le=100_000)
    movement_events: int | None = Field(default=None, ge=0, le=100_000)
    # Interview-time webcam snapshot (data URL). Sent once; stored on the first
    # entry of the session. Optional — absence just means no photo is shown.
    photo: str | None = Field(default=None, max_length=_MAX_PHOTO_CHARS)

@app.get("/api/check")
def start_chek():
    return {"session": " API is working fine"}


@app.get("/api/healthz")
def healthz():
    """Liveness + light operational stats (no secrets, safe to expose).

    `durable_storage` is the one to alert on: when it is not reachable, the
    service still works but every completed interview is being kept only in a
    store that the next restart erases.
    """
    sheets = sheets_status()
    return {
        "status": "ok" if sheets.get("reachable") else "degraded",
        "live_sessions": session_count(),
        "stored_sessions": len(_session_qa),
        "cached_evaluations": len(_eval_store),
        "durable_storage": {
            "configured": sheets.get("configured"),
            "reachable": sheets.get("reachable"),
            "detail": sheets.get("detail"),
            "checked_at": sheets.get("checked_at"),
            # Rows written locally but not yet accepted by the sheet. Steadily
            # non-zero means Sheets is failing and the durable copy is drifting.
            "pending_sync": sync_queue_depth(),
        },
    }


@app.get("/api/start")
def start_session(http_request: Request, code: str | None = None):
    # Invite codes are the only thing standing between the public internet and
    # a free LLM-backed interview, so the redemption endpoint is the one that
    # most needs a brute-force limit. 10/min and 60/hour per IP leaves a real
    # candidate mistyping their code plenty of room while making enumeration of
    # the 32^8 code space hopeless.
    _enforce(http_request, "start", limit=10, window_seconds=60)
    _enforce(http_request, "start-hr", limit=60, window_seconds=3600)
    if code is not None and len(code) > 64:
        raise HTTPException(status_code=400, detail="Invalid invite code.")
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
def create_invite(
    http_request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    """Mint a fresh single-use invite code (requires a valid operator token)."""
    _enforce(http_request, "admin-invite", limit=60, window_seconds=60)
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
def list_invites(
    http_request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    """List every minted code with its status and (once redeemed) which session
    and candidate it produced. Powers the admin console's code table."""
    _enforce(http_request, "admin-list", limit=60, window_seconds=60)
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
def delete_invite(
    code: str,
    http_request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    """Delete a single invite code from the store (requires operator token)."""
    _enforce(http_request, "admin-delete", limit=60, window_seconds=60)
    if not _valid_admin_token(x_admin_token or ""):
        raise HTTPException(status_code=401, detail="Invalid or expired admin session. Please sign in again.")
    with _invite_lock:
        existed = _invite_store.pop(code, None) is not None
        if existed:
            _flush_invite_store(_invite_store)
    if not existed:
        raise HTTPException(status_code=404, detail="Code not found.")
    return {"status": "deleted", "code": code}


@app.get("/api/admin/results")
async def list_results(
    http_request: Request,
    q: str = "",
    limit: int = 50,
    offset: int = 0,
    refresh: bool = False,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    """Search completed interviews in the durable store.

    Results used to be reachable only by walking back from an invite record, so
    deleting a code — or losing the invite store on a restart, which an
    ephemeral filesystem guarantees — made a perfectly intact interview
    unreachable. This reads the durable sheet directly, so a result is
    findable by name, email, role or session id for as long as the sheet has it.

    Admin-gated: unlike /api/log this returns candidate names and emails in
    bulk, which is exactly the kind of thing that should never be public.
    """
    _enforce(http_request, "admin-results", limit=60, window_seconds=60)
    if not _valid_admin_token(x_admin_token or ""):
        raise HTTPException(status_code=401, detail="Invalid or expired admin token.")

    if len(q) > 200:
        raise HTTPException(status_code=400, detail="Search term is too long.")
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    # A forced refresh bypasses the read cache, so it is rate-limited harder —
    # each one is a full spreadsheet fetch against a shared quota.
    if refresh:
        _enforce(http_request, "admin-results-refresh", limit=10, window_seconds=60)

    # Sheet reads are blocking network I/O; keep them off the event loop.
    payload = await run_in_threadpool(
        search_sessions, query=q, limit=limit, offset=offset, force=refresh
    )
    payload["pending_sync"] = sync_queue_depth()
    return payload


@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest, http_request: Request):
    # Generous cap — a full 9-question interview makes ~9 calls here, so this
    # only bites automated abuse/cost-drain, never a real candidate.
    _enforce(http_request, "chat", limit=30, window_seconds=60)
    _enforce(http_request, "chat-hr", limit=300, window_seconds=3600)

    try:
        # run_agent_turn does a blocking LLM call; keep it off the event loop.
        agent_response = await run_in_threadpool(
            run_agent_turn,
            message=request.message,
            session_id=request.session_id,
            domain=request.domain,
            name=request.name,
        )
    except NoLLMProviderError as e:
        log.error("/api/chat unavailable: %s", e)
        raise HTTPException(status_code=503, detail="The interview service is not configured. Please contact the administrator.")
    except Exception as e:
        # Log the real error server-side only — never echo internal exception
        # details (stack internals, library errors) back to the client.
        log.error("/api/chat failed for session %s: %s", request.session_id, e)
        raise HTTPException(status_code=502, detail="Failed to generate the next question. Please try again.")

    return agent_response


# Ceilings on the public write path. /api/save takes no authentication by
# design (the candidate's browser posts to it mid-interview with only a session
# id), so these are what stop it being used as free unbounded storage.
_MAX_ENTRIES_PER_SESSION = 40      # comfortably above agent.MAX_QUESTIONS (15)
_MAX_STORED_SESSIONS = int(os.getenv("MAX_STORED_SESSIONS", "400"))


def _evict_oldest_sessions() -> None:
    """Bound the in-memory/on-disk session store. Caller holds _store_lock.

    Without a ceiling this dict grew for the life of the process, holding every
    transcript and webcam snapshot ever posted — on a 512MB instance that is an
    OOM waiting to happen, and it is reachable by anyone who can POST.
    """
    if len(_session_qa) <= _MAX_STORED_SESSIONS:
        return
    # Evict least-recently-written first. Sessions are dicts of Q&A lists with
    # no timestamp of their own, so insertion order (Python dicts preserve it)
    # is the available proxy and is accurate enough for a backstop.
    overflow = len(_session_qa) - _MAX_STORED_SESSIONS
    for sid in list(_session_qa.keys())[:overflow]:
        _session_qa.pop(sid, None)
        _eval_store.pop(sid, None)
    log.warning("Session store over capacity — evicted %d oldest session(s)", overflow)


def _valid_photo(photo: str | None) -> bool:
    """Accept only an image data URL. The photo is echoed into the report and
    the admin console, so a raw string here would be an obvious injection
    vector; restricting the prefix keeps it to what the webcam actually sends.
    """
    return bool(photo) and photo.startswith(("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,"))


@app.post("/api/save")
def save_endpoint(request: SaveRequest, http_request: Request):
    # Roughly one save per answered question. 40/min per IP is far above a real
    # candidate's pace and still shuts down a flood.
    _enforce(http_request, "save", limit=40, window_seconds=60)

    # Store in memory and persist to disk so restarts don't lose data
    if request.session_id:
        with _store_lock:
            if request.session_id not in _session_qa:
                _session_qa[request.session_id] = []
                _evict_oldest_sessions()
            entries = _session_qa.setdefault(request.session_id, [])
            # Idempotency for client retries. The frontend retries a failed
            # save, and a response lost in flight after the server committed
            # would otherwise append the same answer twice — polluting the
            # transcript the evaluation is scored from. An identical repeat of
            # the most recent entry is treated as the retry it is.
            if entries and entries[-1].get("Question") == request.question \
                    and entries[-1].get("Answer") == request.answer:
                log.info("Duplicate save ignored for session %s", request.session_id)
                return {"status": "ok", "duplicate": True}
            if len(entries) >= _MAX_ENTRIES_PER_SESSION:
                # A real interview can never reach this. Reject rather than
                # grow, so one session id cannot be used as an append-only sink.
                raise HTTPException(status_code=409, detail="This interview already has the maximum number of recorded answers.")
            entries.append({
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
            if _valid_photo(request.photo) and not entries[0].get("Photo"):
                entries[0]["Photo"] = request.photo
            _flush_store(_session_qa)

    # Also persist to CSV + Google Sheets (best effort). Sheets is the durable
    # record on an ephemeral filesystem, so a failure here is logged rather than
    # silently swallowed — a quietly broken Sheets credential used to mean
    # every interview was being kept only in a store that a redeploy wipes.
    try:
        save_qa_tool(
            request.question, request.answer, request.session_id,
            request.name, request.email, request.role,
            request.tab_switches, request.face_lost_count, request.face_lost_seconds,
            request.multiple_faces_count, request.movement_events,
            request.photo if _valid_photo(request.photo) else None,
        )
    except Exception as exc:
        log.warning("Durable save failed for session %s: %s", request.session_id, exc)

    return {"status": "ok"}

_MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10MB — comfortably covers a 10-minute single answer at typical webm/Opus bitrates, well above realistic usage (a full 9-question interview is 10-15 min total)

@app.post("/api/transcribe")
async def transcribe_audio(file: UploadFile = File(...), http_request: Request = None):
    """Transcribe audio using Groq Whisper."""
    if _rate_limited(f"transcribe:{_client_ip(http_request)}", limit=60, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down and try again shortly.")

    client = _get_groq()
    audio_bytes = await file.read()
    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large.")
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio upload.")
    try:
        # The Groq SDK call is synchronous. Awaiting it directly on the event
        # loop blocked EVERY concurrent request for the duration of the
        # transcription — with one worker, that serialized the whole service.
        transcription = await run_in_threadpool(
            lambda: client.audio.transcriptions.create(
                file=(file.filename or "audio.webm", audio_bytes),
                model=os.getenv("WHISPER_MODEL", "whisper-large-v3-turbo"),
                language="en",
                response_format="verbose_json",
                temperature=0.0,
            )
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
    except HTTPException:
        raise
    except Exception as e:
        # Log server-side, return a generic message — the provider's error text
        # can carry internal detail and is not useful to a candidate.
        log.error("Transcription failed: %s", e)
        raise HTTPException(status_code=502, detail="Transcription failed. Please try recording again.")

# Per-session lock for evaluation. Without it, the result page and the admin
# page opening the same brand-new session at once both miss the cache and both
# fire a full evaluation at the LLM — double cost, double latency, and two
# different scores racing to be written last. The lock makes the second caller
# wait and then read the cache.
_eval_session_locks: dict[str, threading.Lock] = {}
_eval_locks_guard = threading.Lock()


def _eval_lock_for(session_id: str) -> threading.Lock:
    with _eval_locks_guard:
        # Bounded: one small lock object per session, cleared with the store.
        if len(_eval_session_locks) > 1000:
            for sid in list(_eval_session_locks.keys())[:500]:
                _eval_session_locks.pop(sid, None)
        return _eval_session_locks.setdefault(session_id, threading.Lock())


@app.get("/api/log/{session_id}")
async def get_interview_results(session_id: str, http_request: Request) -> InterviewResult:
    '''Generate interview evaluation using Groq LLM based on the interview log.'''
    # This is the single most expensive endpoint (a full-transcript LLM call on
    # a cache miss), so it gets the tightest limit of any public route.
    _enforce(http_request, "log", limit=20, window_seconds=60)
    _enforce(http_request, "log-hr", limit=120, window_seconds=3600)

    if len(session_id) > 64:
        raise HTTPException(status_code=400, detail="Invalid session id.")

    Groq_api_key = os.getenv("GROQ_API_KEY")

    # Check in-memory store first (most reliable on Render)
    if session_id in _session_qa and _session_qa[session_id]:
        log_rows = _session_qa[session_id]
        log.info("Loaded %d Q&A pairs from memory for session %s", len(log_rows), session_id)
    else:
        # Sheets/CSV lookup is blocking network+disk I/O; off the event loop it
        # goes, or it stalls every other request on this single-worker instance.
        log_str = await run_in_threadpool(extract_values, session_id_to_find=session_id)
        try:
            log_rows = json.loads(log_str)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Failed to parse interview log.")

    if not log_rows:
        raise HTTPException(status_code=404, detail="Interview log not found. Please complete the interview first.")

    first_entry = log_rows[0]

    # Serve the stored evaluation if this session was already evaluated, so
    # every viewer (candidate or admin) gets the identical score and feedback.
    cached = _eval_store.get(session_id)
    if cached and "score" in cached and "feedback" in cached:
        score = float(cached["score"])
        feedback = str(cached["feedback"])
        return _build_result(log_rows, first_entry, score, feedback)

    transcript = f"""
        Interview for: {first_entry.get('Role', 'N/A')}
        Candidate: {first_entry.get('Name', 'N/A')} ({first_entry.get('Email', 'N/A')})

        Questions and Answers:
    """
    for idx, qa in enumerate(log_rows, 1):
        transcript += f"\nQ{idx}: {qa.get('Question', 'N/A')}\n"
        transcript += f"A{idx}: {qa.get('Answer', 'N/A')}\n"

    # The interview extends past the 9-question minimum only when the
    # candidate is already performing well (see agent.py's adaptive-length
    # logic) — reaching that extended stage is itself a signal of sustained
    # strength, so responses from question 13 onward get graded on a
    # slightly gentler curve. Only added to the prompt when it actually
    # applies, so a normal 9-question interview costs no extra tokens here.
    extension_note = ""
    if len(log_rows) > 12:
        extension_note = (
            f"\nEXTENDED INTERVIEW NOTE: this interview ran to {len(log_rows)} questions "
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
    
    client = _get_groq()

    # Single-flight: hold this session's lock across the LLM call so two viewers
    # opening the fresh result at once produce one evaluation, not two.
    lock = _eval_lock_for(session_id)

    def _evaluate() -> str:
        with lock:
            # Re-check under the lock — the request we queued behind may have
            # just written the evaluation we were about to pay for again.
            cached_inner = _eval_store.get(session_id)
            if cached_inner and "score" in cached_inner and "feedback" in cached_inner:
                return ""
            message = client.chat.completions.create(
                model=GROQ_MODEL,
                max_tokens=2000,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.choices[0].message.content or ""

    try:
        # Blocking SDK call — same reasoning as /api/transcribe above.
        response_text = await run_in_threadpool(_evaluate)
    except Exception as e:
        log.error("Evaluation failed for session %s: %s", session_id, e)
        raise HTTPException(status_code=502, detail="Failed to generate the evaluation. Please try again shortly.")

    if not response_text:
        # Another request won the race and cached the evaluation while we waited.
        cached = _eval_store.get(session_id)
        if cached:
            return _build_result(log_rows, first_entry, float(cached["score"]), str(cached["feedback"]))
        raise HTTPException(status_code=502, detail="Failed to generate the evaluation. Please try again shortly.")

    # Extract score and feedback
    score = extract_score(response_text)
    feedback = extract_feedback(response_text)
    # Fill the score into this session's existing row. The previous call here
    # appended a free-floating ["Evaluation", "Score: x", "Feedback: y"] row,
    # whose cells landed under the Question/Answer/Session_id headers and so
    # showed up as a bogus extra record in the sheet.
    await run_in_threadpool(record_score, session_id, score)

    # Persist so later views of this session reuse this exact evaluation.
    with _eval_lock:
        _eval_store[session_id] = {"score": score, "feedback": feedback, "evaluated_at": time.time()}
        _flush_eval_store(_eval_store)

    # The score just changed this session's row; drop the read cache so the
    # admin results list shows it immediately instead of after the TTL.
    invalidate_rows_cache()

    # The interview is over and scored — release the agent's per-session state
    # (chat history, covered topics, difficulty) instead of waiting out its TTL.
    end_session(session_id)

    return _build_result(log_rows, first_entry, score, feedback)


def _build_result(log_rows: list, first_entry: dict, score: float, feedback: str) -> InterviewResult:
    # Counters are cumulative on the frontend, so the highest value is the final total.
    # Values may come back as strings (CSV/Sheets fallback) — parse defensively.
    def _final(key: str) -> int:
        values = []
        for entry in log_rows:
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
