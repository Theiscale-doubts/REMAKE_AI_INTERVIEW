import { useState, useEffect, useCallback } from "react";
import { useLocation } from "wouter";
import {
  Lock,
  KeyRound,
  Copy,
  Check,
  Loader2,
  ArrowRight,
  ShieldCheck,
  RefreshCw,
  FileText,
  Trash2,
  Search,
  X,
} from "lucide-react";
import PoweredByIScale from "@/components/PoweredByIScale";
import SiteFooter from "@/components/SiteFooter";
import { roleLabel } from "@/roles";

const API_BASE_URL = `${(import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "")}/api`;

interface SessionResult {
  session_id: string;
  name: string;
  email: string;
  role: string;
  score: number | null;
  questions_answered: number;
  started_at: string;
  updated_at: string;
  has_photo: boolean;
}

interface Invite {
  code: string;
  status: "unused" | "used" | "expired" | "aborted";
  created_at: number | null;
  expires_at: number;
  session_id: string | null;
  name: string;
  email: string;
  has_result: boolean;
}

/**
 * Operator-only page to mint single-use interview invite codes and view the
 * result of each redeemed code. Password check exchanges for a short-lived
 * token (kept in memory only — a refresh clears it and re-prompts).
 */
export default function Admin() {
  const [, setLocation] = useLocation();

  const [password, setPassword] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  const [code, setCode] = useState<string | null>(null);
  const [validHours, setValidHours] = useState<number | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [invites, setInvites] = useState<Invite[]>([]);
  const [loadingInvites, setLoadingInvites] = useState(false);

  // Results lookup. Reads the durable sheet directly rather than walking back
  // from an invite record, so a result stays findable after its code is
  // deleted or the invite store is wiped by a restart.
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SessionResult[]>([]);
  const [resultsTotal, setResultsTotal] = useState(0);
  const [loadingResults, setLoadingResults] = useState(false);
  const [resultsError, setResultsError] = useState<string | null>(null);
  const [resultsSource, setResultsSource] = useState<string | null>(null);
  const [pendingSync, setPendingSync] = useState(0);
  const [refreshingResults, setRefreshingResults] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const expireSession = useCallback((msg: string) => {
    setToken(null);
    setVerifyError(msg);
  }, []);

  const fetchInvites = useCallback(
    async (tok: string) => {
      setLoadingInvites(true);
      try {
        const res = await fetch(`${API_BASE_URL}/admin/invites`, {
          headers: { "X-Admin-Token": tok },
        });
        if (res.status === 401) {
          expireSession("Your session expired. Please sign in again.");
          return;
        }
        const data = await res.json().catch(() => ({}));
        if (res.ok) setInvites(data.invites || []);
      } catch {
        // Non-fatal — the list just stays as-is.
      } finally {
        setLoadingInvites(false);
      }
    },
    [expireSession]
  );

  const fetchResults = useCallback(
    async (tok: string, search: string, forceRefresh = false) => {
      if (forceRefresh) setRefreshingResults(true);
      else setLoadingResults(true);
      setResultsError(null);
      try {
        const params = new URLSearchParams({ q: search, limit: "50" });
        if (forceRefresh) params.set("refresh", "true");
        const res = await fetch(`${API_BASE_URL}/admin/results?${params}`, {
          headers: { "X-Admin-Token": tok },
        });
        if (res.status === 401) {
          expireSession("Your session expired. Please sign in again.");
          return;
        }
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          setResultsError(data.detail || "Could not load results. Please try again.");
          return;
        }
        setResults(data.results || []);
        setResultsTotal(data.total ?? 0);
        setResultsSource(data.source ?? null);
        setPendingSync(data.pending_sync ?? 0);
      } catch {
        setResultsError("Could not reach the server. Please check your connection.");
      } finally {
        setLoadingResults(false);
        setRefreshingResults(false);
      }
    },
    [expireSession]
  );

  // Load the code list as soon as we have a valid session token.
  useEffect(() => {
    if (token) fetchInvites(token);
  }, [token, fetchInvites]);

  // Debounced search — one request after typing settles, not one per keystroke.
  // Each uncached request is a full spreadsheet fetch against a shared quota.
  useEffect(() => {
    if (!token) return;
    const id = setTimeout(() => fetchResults(token, query), query ? 350 : 0);
    return () => clearTimeout(id);
  }, [token, query, fetchResults]);

  const verify = async () => {
    if (!password.trim() || verifying) return;
    setVerifying(true);
    setVerifyError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/admin/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setVerifyError(data.detail || "Could not verify. Please try again.");
        return;
      }
      setToken(data.token);
      setPassword("");
    } catch {
      setVerifyError("Could not reach the server. Please check your connection and try again.");
    } finally {
      setVerifying(false);
    }
  };

  const generate = async () => {
    if (!token || generating) return;
    setGenerating(true);
    setGenerateError(null);
    setCopied(false);
    try {
      const res = await fetch(`${API_BASE_URL}/admin/invite`, {
        method: "POST",
        headers: { "X-Admin-Token": token },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (res.status === 401) {
          expireSession("Your session expired. Please sign in again.");
          return;
        }
        setGenerateError(data.detail || "Could not generate a code. Please try again.");
        return;
      }
      setCode(data.code);
      setValidHours(data.valid_hours ?? null);
      fetchInvites(token); // refresh the list with the new code
    } catch {
      setGenerateError("Could not reach the server. Please check your connection and try again.");
    } finally {
      setGenerating(false);
    }
  };

  const deleteInvite = async (target: string) => {
    if (!token || deleting) return;
    setDeleting(target);
    try {
      const res = await fetch(`${API_BASE_URL}/admin/invite/${encodeURIComponent(target)}`, {
        method: "DELETE",
        headers: { "X-Admin-Token": token },
      });
      if (res.status === 401) {
        expireSession("Your session expired. Please sign in again.");
        return;
      }
      if (res.ok || res.status === 404) {
        setConfirmDelete(null);
        fetchInvites(token);
      }
    } catch {
      // Non-fatal — leave the row in place; the operator can retry.
    } finally {
      setDeleting(null);
    }
  };

  const copy = async () => {
    if (!code) return;
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard blocked — the code is still visible for manual copy.
    }
  };

  const statusStyles: Record<Invite["status"], string> = {
    unused: "border-hairline-strong text-txt-mid",
    used: "border-[rgba(201,154,114,.45)] bg-[rgba(201,154,114,.14)] text-acc-copper",
    aborted: "border-[rgba(201,154,114,.22)] text-[#B89476]",
    expired: "border-hairline text-txt-low",
  };

  return (
    <div className="admin-copper min-h-screen bg-ink text-txt-hi font-display antialiased selection:bg-[rgba(201,154,114,.35)] flex flex-col">
      <header className="sticky top-0 z-20 backdrop-blur-xl bg-ink/[.82] border-b border-hairline">
        <div className="max-w-5xl mx-auto px-4 sm:px-7 h-16 flex items-center justify-between gap-3">
          <div className="flex flex-col leading-tight">
            <span className="text-[15px] font-bold tracking-[0.1em]">VOXHIRE</span>
            <span className="text-[9.5px] font-medium tracking-[0.2em] text-txt-low uppercase">Admin Console</span>
          </div>
          <PoweredByIScale />
        </div>
      </header>

      <main className="flex-1 flex items-start justify-center px-4 sm:px-6 py-8 sm:py-14">
        {!token ? (
          <div className="vh-card-raised w-full max-w-md p-9 animate-fade-up mt-8">
            <div className="mx-auto h-12 w-12 rounded-xl bg-[rgba(201,154,114,.1)] border border-[rgba(201,154,114,.35)] grid place-items-center mb-6">
              <Lock className="h-[22px] w-[22px] text-acc-copper" />
            </div>
            <h1 className="text-2xl tracking-[-0.02em] font-semibold text-center">Admin access</h1>
            <p className="mt-2 mb-7 text-center text-[13.5px] leading-relaxed text-txt-mid">
              Enter the admin password to generate and manage interview invite codes.
            </p>
            <label className="block text-[13px] font-medium text-txt-hi mb-2">Password</label>
            <div className="relative">
              <KeyRound className="absolute left-3.5 top-1/2 -translate-y-1/2 h-[15px] w-[15px] text-txt-low" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && verify()}
                placeholder="Enter admin password"
                autoFocus
                className="vh-input text-[13.5px] pl-10 pr-4 py-3.5"
              />
            </div>
            {verifyError && (
              <div className="mt-4 flex items-start gap-3 text-[13px] text-acc-copper border border-[rgba(201,154,114,.35)] bg-[rgba(201,154,114,.08)] rounded-xl px-4 py-3">
                <ShieldCheck className="h-4 w-4 mt-0.5 flex-shrink-0" />
                <span>{verifyError}</span>
              </div>
            )}
            <button
              onClick={verify}
              disabled={verifying || !password.trim()}
              className="vh-btn-copper w-full mt-6 py-3.5 text-[14px]"
            >
              {verifying ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Verifying…
                </>
              ) : (
                <>
                  Continue
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        ) : (
          <div className="w-full max-w-2xl space-y-6 animate-fade-up">
            {/* Generate */}
            <div className="vh-card-raised p-5 sm:p-8">
              <div className="flex items-center gap-3.5 mb-1">
                <span className="h-9 w-9 rounded-[11px] bg-[rgba(201,154,114,.1)] border border-[rgba(201,154,114,.35)] grid place-items-center flex-shrink-0">
                  <ShieldCheck className="h-[18px] w-[18px] text-acc-copper" />
                </span>
                <h1 className="text-xl tracking-[-0.02em] font-semibold">Generate invite code</h1>
              </div>
              <p className="mb-6 text-[13.5px] leading-relaxed text-txt-mid">
                Each code works for a single interview and expires if unused.
              </p>

              {code && (
                <div className="mb-6 rounded-xl border border-hairline-strong bg-bg-2 p-5 text-center">
                  <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-txt-low mb-2.5">New invite code</p>
                  <div className="flex items-center justify-center gap-3">
                    <span className="text-2xl font-semibold tracking-[0.15em] tabular-nums text-txt-hi select-all">{code}</span>
                    <button
                      onClick={copy}
                      title="Copy to clipboard"
                      className="flex-shrink-0 h-9 w-9 grid place-items-center rounded-lg border border-hairline-strong bg-surface-1 text-txt-mid transition-colors duration-200 hover:border-[rgba(201,154,114,.5)] hover:text-txt-hi"
                    >
                      {copied ? <Check className="h-4 w-4 text-acc-copper" /> : <Copy className="h-4 w-4" />}
                    </button>
                  </div>
                  {validHours != null && (
                    <p className="mt-3 text-[11.5px] text-txt-low">Valid for {validHours} hours or until used once.</p>
                  )}
                </div>
              )}

              {generateError && (
                <div className="mb-6 flex items-start gap-3 text-[13px] text-acc-copper border border-[rgba(201,154,114,.35)] bg-[rgba(201,154,114,.08)] rounded-xl px-4 py-3">
                  <ShieldCheck className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span>{generateError}</span>
                </div>
              )}

              <button onClick={generate} disabled={generating} className="vh-btn-copper w-full py-3.5 text-[14px]">
                {generating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Generating…
                  </>
                ) : (
                  <>
                    <KeyRound className="h-4 w-4" />
                    {code ? "Generate another code" : "Generate invite code"}
                  </>
                )}
              </button>
            </div>

            {/* Codes list */}
            <div className="vh-card p-5 sm:p-8">
              <div className="flex items-center justify-between mb-5">
                <h2 className="text-[15px] tracking-[-0.01em] font-semibold">Invite codes</h2>
                <button
                  onClick={() => token && fetchInvites(token)}
                  disabled={loadingInvites}
                  className="inline-flex items-center gap-2 text-[12px] text-txt-mid hover:text-txt-hi transition-colors disabled:opacity-50"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${loadingInvites ? "animate-spin" : ""}`} />
                  Refresh
                </button>
              </div>

              {invites.length === 0 ? (
                <p className="text-[13px] text-txt-low py-6 text-center">
                  {loadingInvites ? "Loading…" : "No codes generated yet."}
                </p>
              ) : (
                <div className="space-y-2.5">
                  {invites.map((inv) => (
                    <div
                      key={inv.code}
                      className="flex flex-col xs:flex-row xs:items-center justify-between gap-3 px-4 py-3 rounded-xl border border-hairline bg-bg-2"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2.5">
                          <span className="font-semibold tracking-[0.1em] tabular-nums text-txt-hi">{inv.code}</span>
                          <span className={`text-[10px] font-medium uppercase tracking-[0.1em] rounded-full border px-2 py-0.5 ${statusStyles[inv.status]}`}>
                            {inv.status}
                          </span>
                        </div>
                        <p className="mt-1 text-[12px] text-txt-mid truncate">
                          {inv.name || inv.email
                            ? `${inv.name}${inv.name && inv.email ? " · " : ""}${inv.email}`
                            : inv.status === "aborted"
                              ? "Redeemed but no answers"
                              : inv.status === "expired"
                                ? "Expired, never used"
                                : "Not started yet"}
                        </p>
                      </div>
                      <div className="flex-shrink-0">
                        {confirmDelete === inv.code ? (
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-[12px] text-txt-mid whitespace-nowrap">Delete?</span>
                            <button
                              onClick={() => deleteInvite(inv.code)}
                              disabled={deleting === inv.code}
                              className="inline-flex items-center gap-1.5 rounded-lg border border-[rgba(201,154,114,.5)] bg-[rgba(201,154,114,.14)] px-3 py-2 text-[12.5px] font-medium text-acc-copper transition-colors duration-200 hover:bg-[rgba(201,154,114,.22)] disabled:opacity-50"
                            >
                              {deleting === inv.code ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Yes, delete"}
                            </button>
                            <button
                              onClick={() => setConfirmDelete(null)}
                              className="rounded-lg border border-hairline-strong bg-surface-1 px-3 py-2 text-[12.5px] font-medium text-txt-mid transition-colors duration-200 hover:text-txt-hi"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            {inv.has_result && inv.session_id && (
                              <button
                                onClick={() => setLocation(`/results/${inv.session_id}`)}
                                className="inline-flex items-center gap-2 rounded-lg border border-hairline-strong bg-surface-1 px-3.5 py-2 text-[12.5px] font-medium text-txt-hi transition-colors duration-200 hover:border-[rgba(201,154,114,.5)]"
                              >
                                <FileText className="h-3.5 w-3.5 text-acc-copper" />
                                View result
                              </button>
                            )}
                            <button
                              onClick={() => setConfirmDelete(inv.code)}
                              title="Delete code"
                              className="flex-shrink-0 h-9 w-9 grid place-items-center rounded-lg border border-hairline-strong bg-surface-1 text-txt-low transition-colors duration-200 hover:border-[rgba(201,154,114,.5)] hover:text-acc-copper"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Results lookup */}
            <div className="vh-card p-5 sm:p-8">
              <div className="flex items-center justify-between gap-3 mb-1">
                <h2 className="text-[15px] tracking-[-0.01em] font-semibold">Interview results</h2>
                <button
                  onClick={() => token && fetchResults(token, query, true)}
                  disabled={refreshingResults}
                  title="Re-read the spreadsheet, bypassing the cache"
                  className="inline-flex items-center gap-2 text-[12px] text-txt-mid hover:text-txt-hi transition-colors disabled:opacity-50"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${refreshingResults ? "animate-spin" : ""}`} />
                  Refresh
                </button>
              </div>
              <p className="text-[12.5px] text-txt-low mb-5">
                Search every completed interview by name, email, role, session ID, or a question
                that was asked. Works without the invite code.
              </p>

              <div className="relative mb-5">
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-[15px] w-[15px] text-txt-low pointer-events-none" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search by name, email, role, or session ID…"
                  className="vh-input text-[13.5px] pl-10 pr-10 py-3"
                />
                {query && (
                  <button
                    onClick={() => setQuery("")}
                    title="Clear search"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-txt-low hover:text-txt-hi transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>

              {/* A non-zero queue means the durable copy is behind — say so
                  rather than letting the list look authoritative when it isn't. */}
              {pendingSync > 0 && (
                <div className="mb-4 rounded-xl border border-[rgba(201,154,114,.3)] bg-[rgba(201,154,114,.07)] px-4 py-3">
                  <p className="text-[12.5px] text-acc-copper">
                    {pendingSync} interview{pendingSync === 1 ? "" : "s"} still syncing to the
                    spreadsheet — they may not appear here yet.
                  </p>
                </div>
              )}
              {resultsSource === "csv" && (
                <div className="mb-4 rounded-xl border border-[rgba(177,18,38,.3)] bg-[rgba(177,18,38,.07)] px-4 py-3">
                  <p className="text-[12.5px] text-[#DFA2A8]">
                    Showing local records — the spreadsheet is unreachable. This copy does not
                    survive a restart.
                  </p>
                </div>
              )}
              {resultsError && (
                <p className="mb-4 text-[12.5px] text-[#E05860]">{resultsError}</p>
              )}

              {loadingResults ? (
                <p className="text-[13px] text-txt-low py-6 text-center">Loading…</p>
              ) : results.length === 0 ? (
                <p className="text-[13px] text-txt-low py-6 text-center">
                  {query ? `No interviews match “${query}”.` : "No completed interviews yet."}
                </p>
              ) : (
                <>
                  <div className="space-y-2.5">
                    {results.map((r) => (
                      <div
                        key={r.session_id}
                        className="flex flex-col xs:flex-row xs:items-center justify-between gap-3 px-4 py-3 rounded-xl border border-hairline bg-bg-2"
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-2.5 flex-wrap">
                            <span className="font-semibold text-txt-hi truncate">
                              {r.name || "Unnamed candidate"}
                            </span>
                            {r.role && (
                              <span className="text-[10px] font-medium uppercase tracking-[0.1em] rounded-full border border-hairline-strong px-2 py-0.5 text-txt-mid">
                                {roleLabel(r.role)}
                              </span>
                            )}
                            {r.score !== null && (
                              <span className="text-[10px] font-medium uppercase tracking-[0.1em] rounded-full border border-[rgba(201,154,114,.45)] bg-[rgba(201,154,114,.14)] px-2 py-0.5 text-acc-copper tabular-nums">
                                {r.score.toFixed(1)} / 10
                              </span>
                            )}
                          </div>
                          <p className="mt-1 text-[12px] text-txt-mid truncate">
                            {r.email || "no email"}
                            {r.questions_answered ? ` · ${r.questions_answered} answers` : ""}
                            {r.updated_at ? ` · ${r.updated_at}` : ""}
                          </p>
                        </div>
                        <div className="flex-shrink-0">
                          <button
                            onClick={() => setLocation(`/results/${r.session_id}`)}
                            className="inline-flex items-center gap-2 rounded-lg border border-hairline-strong bg-surface-1 px-3 py-2 text-[12.5px] font-medium text-txt-mid transition-colors duration-200 hover:text-txt-hi"
                          >
                            <FileText className="h-3.5 w-3.5 text-acc-copper" />
                            View result
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                  {resultsTotal > results.length && (
                    <p className="mt-4 text-[12px] text-txt-low text-center">
                      Showing {results.length} of {resultsTotal} — narrow your search to see more.
                    </p>
                  )}
                </>
              )}
            </div>
          </div>
        )}
      </main>

      <SiteFooter maxWidth="max-w-5xl" />
    </div>
  );
}
