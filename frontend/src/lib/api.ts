/**
 * Shared fetch wrapper for the VoxHire API.
 *
 * Written because several call sites did `await fetch(...)` and went straight
 * to `response.json()` without checking `response.ok`. An error response
 * ({"detail": "..."}) parses as perfectly valid JSON, so the failure looked
 * like success: the caller read `data.question`, got `undefined`, and rendered
 * a blank question while telling the candidate everything was fine.
 *
 * Every non-2xx now throws, and transient failures are retried before the
 * error ever reaches the UI — a single hiccup mid-interview should not cost
 * the candidate their session.
 */

export class ApiError extends Error {
  status: number;
  detail: string;
  retryable: boolean;

  constructor(status: number, detail: string) {
    super(detail || `Request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.retryable = RETRYABLE_STATUSES.has(status);
  }
}

// 429 (rate limited), 502/503/504 (provider hiccup, cold start, restart) are
// worth another attempt. 4xx like 400/409/422 are the caller's fault and will
// fail identically no matter how many times we try.
const RETRYABLE_STATUSES = new Set([408, 425, 429, 500, 502, 503, 504]);

const DEFAULT_RETRIES = 2;
const BASE_BACKOFF_MS = 900;

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Backoff for attempt n, honouring a server-sent Retry-After when present. */
function backoffFor(attempt: number, retryAfter: string | null): number {
  if (retryAfter) {
    const seconds = Number(retryAfter);
    if (Number.isFinite(seconds) && seconds > 0) {
      return Math.min(seconds * 1000, 10_000);
    }
  }
  // Exponential with jitter, so simultaneous clients don't retry in lockstep.
  return BASE_BACKOFF_MS * 2 ** attempt + Math.random() * 400;
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (body && typeof body.detail === "string") return body.detail;
  } catch {
    // Non-JSON error body (a proxy's HTML 502 page, say) — fall through.
  }
  return "";
}

export interface ApiFetchOptions {
  retries?: number;
  timeoutMs?: number;
  /** Called before each retry, for surfacing "retrying…" in the UI. */
  onRetry?: (attempt: number, error: ApiError | Error) => void;
}

/**
 * Fetch JSON from the API, throwing ApiError on any non-2xx response.
 * Retries transient failures (and network errors) with backoff.
 */
export async function apiFetch<T = any>(
  url: string,
  init: RequestInit = {},
  options: ApiFetchOptions = {},
): Promise<T> {
  const retries = options.retries ?? DEFAULT_RETRIES;
  const timeoutMs = options.timeoutMs ?? 45_000;
  let lastError: ApiError | Error = new Error("Request never ran");

  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, { ...init, signal: controller.signal });

      if (!response.ok) {
        const error = new ApiError(response.status, await readDetail(response));
        if (!error.retryable || attempt === retries) throw error;
        lastError = error;
        options.onRetry?.(attempt + 1, error);
        await sleep(backoffFor(attempt, response.headers.get("Retry-After")));
        continue;
      }

      // 204 and other empty bodies are valid successes.
      const text = await response.text();
      return (text ? JSON.parse(text) : {}) as T;
    } catch (err: any) {
      if (err instanceof ApiError) throw err;
      // Network failure, timeout, or malformed JSON on a 2xx.
      const wrapped = err?.name === "AbortError" ? new Error("The request timed out.") : err;
      if (attempt === retries) throw wrapped;
      lastError = wrapped;
      options.onRetry?.(attempt + 1, wrapped);
      await sleep(backoffFor(attempt, null));
    } finally {
      clearTimeout(timer);
    }
  }

  throw lastError;
}

/** Candidate-facing copy for a failed request. Never leaks internals. */
export function friendlyMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    // 4xx details are written for humans (invalid code, interview full, …).
    if (error.detail && error.status < 500 && error.status !== 429) return error.detail;
    if (error.status === 429) return "The service is busy right now. Please wait a few seconds and try again.";
    if (error.status === 503) return "The interview service is temporarily unavailable. Please try again in a moment.";
  }
  return fallback;
}
