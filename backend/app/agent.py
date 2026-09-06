import dotenv
import os as _os
# VOXHIRE_SKIP_DOTENV lets tests exercise the "no API keys configured" path
# without the developer's local .env silently supplying them.
if not _os.getenv("VOXHIRE_SKIP_DOTENV"):
    dotenv.load_dotenv(_os.path.join(_os.path.dirname(_os.path.dirname(__file__)), ".env"))
from typing import Dict, Optional
from dataclasses import dataclass, field
import logging
import random
import re
import threading
import time
import warnings
from langchain_core._api.deprecation import LangChainDeprecationWarning
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI

# RunnableWithMessageHistory is deprecated in favor of LangGraph's persistence,
# but migrating would mean rearchitecting the whole session/history flow here
# for no functional gain — the API still works fine. Silence just this one
# warning instead of leaving noisy deprecation output on every request.
warnings.filterwarnings("ignore", category=LangChainDeprecationWarning, message=".*RunnableWithMessageHistory.*")

log = logging.getLogger("voxhire.agent")

# Single source of truth for the Groq model id — Groq periodically retires
# model names (this broke twice from a stale hardcoded "llama-3.3-70b-versatile"
# in two different files), so every Groq call in the backend must import this
# constant instead of hardcoding its own string. Override via GROQ_MODEL in
# .env if Groq retires this one too — no code change needed.
GROQ_MODEL = _os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

OPENAI_MODEL = _os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Per-call ceilings. Without an explicit timeout an unresponsive provider pins a
# worker until the client gives up — on a single free-tier instance that is the
# whole backend, so every request behind it stalls too.
LLM_TIMEOUT_SECONDS = float(_os.getenv("LLM_TIMEOUT_SECONDS", "45"))
LLM_MAX_RETRIES = int(_os.getenv("LLM_MAX_RETRIES", "1"))

# LLM instances are built lazily and defensively. Constructing ChatOpenAI or
# ChatGroq raises immediately when its API key is absent, so building them at
# import time (as this module used to) meant a missing OPENAI_API_KEY took the
# entire backend down at boot with an opaque traceback — even though Groq alone
# is a perfectly good configuration. Now a provider that cannot be built is
# simply skipped, and the service starts as long as at least one key is present.
def _build_openai_llm():
    if not _os.getenv("OPENAI_API_KEY", "").strip():
        return None
    return ChatOpenAI(
        model=OPENAI_MODEL,
        temperature=0.9,
        max_tokens=350,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
    )

def _build_groq_llm():
    if not _os.getenv("GROQ_API_KEY", "").strip():
        return None
    return ChatGroq(
        model=GROQ_MODEL,
        temperature=0.9,
        max_tokens=350,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
    )

def _try_build(name: str, builder):
    try:
        llm = builder()
    except Exception as exc:  # malformed key, unreachable config, SDK change
        log.warning("LLM provider %s unavailable: %s", name, exc)
        return None
    if llm is None:
        log.info("LLM provider %s skipped (no API key configured)", name)
    return llm

openai_llm = _try_build("openai", _build_openai_llm)
groq_llm = _try_build("groq", _build_groq_llm)

if not openai_llm and not groq_llm:
    # Deliberately a warning, not a hard failure: the service still boots so
    # /api/check, the admin endpoints and already-stored results keep working.
    # Only /api/chat is degraded, and it reports the misconfiguration itself.
    log.error(
        "No LLM provider configured — set GROQ_API_KEY and/or OPENAI_API_KEY. "
        "/api/chat will return 503 until one is present."
    )

# Adaptive interview length: every interview is at least MIN_QUESTIONS long.
# Past that, the interview extends one question at a time, capped at
# MAX_QUESTIONS, for as long as the candidate isn't visibly struggling.
# Gating this on the numeric difficulty level reaching 4 (which requires an
# actual STRONG rating) turned out too strict in practice — models are
# conservative about handing out STRONG even for genuinely strong answers, so
# that bar was rarely met and the feature almost never fired. Using "the most
# recent judgment wasn't WEAK" instead is a more robust, more achievable
# reading of "going well": a WEAK answer stops further extension immediately,
# but steady ADEQUATE-or-better performance keeps it going.
MIN_QUESTIONS = 9
MAX_QUESTIONS = 15

# Net tally the candidate must hold for the interview to run past MIN_QUESTIONS.
# 1 means "at least one more STRONG answer than WEAK ones so far" — an interview
# of uniformly ADEQUATE answers sits at 0 and ends at MIN_QUESTIONS.
EXTENSION_MIN_PERFORMANCE = 1
# Bounds on the tally. The ceiling keeps it responsive to a late decline; the
# floor stops a bad start from being mathematically impossible to recover from.
PERFORMANCE_CEILING = 3
PERFORMANCE_FLOOR = -3

# The QUALITY self-judgment turned out unreliable on its own too — testing
# showed the model defaults to ADEQUATE even for bare "I don't know"/"skip"
# non-answers, so extension would trigger for a struggling candidate just as
# readily as a strong one. This deterministic, zero-token check catches the
# obvious non-answer case directly from the raw message instead of trusting
# the model's self-report for it — same phrases the evaluation prompt already
# treats as disengagement (see the SKIPPED/REFUSED guideline in main.py).
_NON_ANSWER_PHRASES = {
    "i don't know", "i dont know", "not sure", "skip", "skip this",
    "skip this question", "pass", "no idea", "i have no idea",
    "not familiar", "i don't know how to answer", "i dont know how to answer",
    "haven't learned that", "i haven't learned that", "i don't know that",
}

def _looks_like_non_answer(message: str) -> bool:
    cleaned = message.strip().lower().rstrip(".!? ")
    if len(cleaned) < 12:
        return True
    return any(phrase in cleaned for phrase in _NON_ANSWER_PHRASES)

# ── Session state ─────────────────────────────────────────────────────────
# All per-session interview state lives in ONE record per session, evicted on a
# TTL. This replaces eight parallel module-level dicts (domains, topics, counts,
# difficulty, names, totals, last-quality, history) that were only ever written
# and never cleaned up: on a long-lived instance they grew without bound, and
# every lookup had to defensively handle a session present in one dict but
# missing from another. A single record makes that class of bug unrepresentable
# and gives eviction exactly one place to happen.
#
# This matters concretely on Render's free tier (512MB): each session holds a
# chat history plus topic lists, and an abandoned interview — the common case,
# candidates close the tab — previously leaked all of it forever.
SESSION_TTL_SECONDS = int(_os.getenv("SESSION_TTL_SECONDS", str(6 * 60 * 60)))
MAX_TRACKED_SESSIONS = int(_os.getenv("MAX_TRACKED_SESSIONS", "500"))


@dataclass
class SessionState:
    domain: str
    history: InMemoryChatMessageHistory = field(default_factory=InMemoryChatMessageHistory)
    topics_covered: list = field(default_factory=list)
    question_count: int = 0
    difficulty: int = 3          # STARTING_DIFFICULTY; set explicitly on create
    name: Optional[str] = None
    total_questions: int = 9     # MIN_QUESTIONS; set explicitly on create
    last_quality: Optional[str] = None
    # Running performance tally across the whole interview: +1 per STRONG
    # answer, -1 per WEAK one, and -1 for a deterministic non-answer. Clamped
    # so it stays responsive — a candidate who was excellent early cannot bank
    # enough credit to keep extending through a collapse at the end.
    performance: int = 0
    # How many of each required bucket (Python/SQL) have been asked so far.
    # Credited by the engine when it forces the topic, not inferred from the
    # model's self-reported TOPIC line — so the quota cannot be missed because
    # the model mislabelled or omitted a line.
    required_covered: dict = field(default_factory=dict)
    last_seen: float = field(default_factory=time.time)


_sessions: Dict[str, SessionState] = {}
_sessions_lock = threading.Lock()


def _evict_stale_sessions(now: float) -> None:
    """Drop sessions idle past the TTL; if still over the cap, drop oldest first.

    Caller must hold _sessions_lock.
    """
    cutoff = now - SESSION_TTL_SECONDS
    for sid in [s for s, st in _sessions.items() if st.last_seen < cutoff]:
        _sessions.pop(sid, None)
    # Hard ceiling as a backstop: a burst of sessions inside one TTL window
    # should still not be able to exhaust memory.
    if len(_sessions) > MAX_TRACKED_SESSIONS:
        oldest = sorted(_sessions.items(), key=lambda kv: kv[1].last_seen)
        for sid, _ in oldest[: len(_sessions) - MAX_TRACKED_SESSIONS]:
            _sessions.pop(sid, None)


def _get_or_create_session(session_id: str, domain: str | None) -> SessionState:
    now = time.time()
    with _sessions_lock:
        state = _sessions.get(session_id)
        if state is None:
            state = SessionState(
                domain=_normalize_domain(domain),
                difficulty=STARTING_DIFFICULTY,
                total_questions=MIN_QUESTIONS,
            )
            _sessions[session_id] = state
        state.last_seen = now
        # Evict after inserting, so the cap is an exact ceiling on live
        # sessions rather than a ceiling that the new arrival then exceeds.
        # The session just touched is the newest, so it is never the victim.
        _evict_stale_sessions(now)
        return state


def end_session(session_id: str) -> None:
    """Release a finished interview's state.

    Called once the interview is evaluated — without this, completed sessions
    stayed resident until the TTL expired, which on a small instance is the
    difference between holding a handful of sessions and holding every session
    since the last deploy.
    """
    with _sessions_lock:
        _sessions.pop(session_id, None)


def session_count() -> int:
    """Live session count, surfaced by the health endpoint for monitoring."""
    with _sessions_lock:
        return len(_sessions)

# Cap how much prior conversation is resent to the model each turn. The model
# doesn't need the verbatim old Q&A to stay coherent — covered topics and the
# adaptive difficulty level already carry that state forward turn to turn —
# so this bounds per-request tokens instead of letting them grow with every
# question asked in the interview.
HISTORY_TURNS_TO_KEEP = 3  # keep the last 3 Q&A exchanges (6 messages)

def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    """History callback for RunnableWithMessageHistory.

    Reads the history off the session record so it is evicted with the rest of
    that session's state, rather than living in a separate dict that nothing
    ever cleaned up.
    """
    state = _get_or_create_session(session_id, None)
    history = state.history
    max_messages = HISTORY_TURNS_TO_KEEP * 2
    if len(history.messages) > max_messages:
        history.messages = history.messages[-max_messages:]
    return history

# Difficulty bar applied to every domain unless the domain defines its own
DEFAULT_DIFFICULTY = (
    "The candidate is a FRESHER (entry-level). Difficulty mix across the interview: most "
    "questions (roughly 7 of 9) must be MID-LEVEL — clear, fresher-friendly conceptual "
    "questions that test solid fundamentals, the kind a well-prepared graduate can answer. "
    "Include AT MOST 2 genuinely hard, top-company (Google/Meta/Amazon) style questions that "
    "probe WHY and trade-offs — place these in the middle or later part of the interview, "
    "never back-to-back. Frame questions around simple realistic scenarios where natural, "
    "and keep everything strictly verbal and theoretical: NO code writing, NO whiteboard "
    "problems, NO calculations to perform."
)

# Adaptive difficulty: a 1-5 scale the model targets each turn, driven by whether the
# candidate's previous answer was strong, adequate, or weak (see run_agent_turn).
STARTING_DIFFICULTY = 3
DIFFICULTY_LEVELS = {
    1: "Very easy — a basic definitional or recall question; simple concept check, minimal depth expected.",
    2: "Easy — a straightforward fundamentals question a well-prepared fresher answers confidently.",
    3: "Medium — a solid conceptual question testing real understanding; the default interview level.",
    4: "Hard — a probing WHY/trade-off question, genuinely challenging, top-company style.",
    5: "Very hard — an expert-level, multi-layered trade-off question that would challenge a strong senior candidate.",
}

# Each technical role gets an explicit scope boundary, stating both what it
# owns and — more importantly — what belongs to a *neighbouring* role and must
# therefore be left alone. Without this the three technical interviews converge:
# every one of them drifts toward generic "explain overfitting / explain A/B
# testing" questions, because those sit plausibly inside all three topic lists.
DOMAIN_SCOPE = {
    "data_analytics": (
        "SCOPE — DATA ANALYTICS: you are interviewing an ANALYST. Own the descriptive layer: "
        "SQL, BI tools, dashboards, business metrics, cohort/funnel analysis, data quality, and "
        "communicating findings to stakeholders. The defining question is 'what happened, and "
        "what should the business do about it'. DO NOT ask about model training, algorithm "
        "internals, ML theory, or LLMs — those belong to the data science and AI engineering "
        "interviews. Statistics here is applied and interpretive (reading a test result, "
        "choosing a metric), never derivational."
    ),
    "datascience": (
        "SCOPE — DATA SCIENCE: you are interviewing a DATA SCIENTIST. Own the inferential and "
        "predictive layer: statistical inference, experiment DESIGN, modelling, validation, "
        "causal reasoning. The defining question is 'why is this happening, and what will happen "
        "next'. DO NOT ask about BI tooling (Tableau/Power BI/Excel), dashboard design, or "
        "report formatting — those belong to the data analytics interview. DO NOT ask about "
        "LLM/RAG/agent systems — those belong to the AI engineering interview."
    ),
    "ai_engineer": (
        "SCOPE — AI ENGINEERING: you are interviewing an AI ENGINEER. Own the applied LLM systems "
        "layer: transformers, embeddings, RAG, prompting, agents, evaluation of generative "
        "output, inference cost and latency, and shipping/operating these systems. The defining "
        "question is 'how do you build and run a reliable system on top of a model you did not "
        "train'. DO NOT ask classical ML theory (bias-variance, regularization maths, tree "
        "ensembles) — that belongs to the data science interview. DO NOT ask BI/dashboard "
        "questions — those belong to the data analytics interview."
    ),
}

# Every technical interview must include a fixed quota of Python and SQL
# questions. Leaving this to the topic sampler was not enough — sampling picks
# 8 of ~23 topics per turn, so a given interview could easily finish having
# asked neither. These quotas are scheduled and enforced by the engine (see
# _required_slots and run_agent_turn), not merely suggested to the model.
#
# The questions stay conceptual and answerable out loud: this is a spoken
# interview, so "write a query that..." is unanswerable by design. "Explain what
# this construct does and when you would reach for it" tests the same knowledge
# and actually works over voice.
REQUIRED_TOPIC_QUOTAS = {
    "data_analytics": [
        {
            "tag": "SQL",
            "count": 2,
            "topics": [
                "SQL — joins and grain (INNER vs LEFT, what fan-out is and how a join silently duplicates rows, why row counts change)",
                "SQL — aggregation and window functions (GROUP BY vs PARTITION BY, HAVING vs WHERE, running totals, RANK vs ROW_NUMBER, deduplicating with a window)",
            ],
        },
        {
            "tag": "Python",
            "count": 2,
            "topics": [
                "Python/pandas — reshaping and joining data (merge vs concat, groupby-aggregate, pivot vs melt, why an operation returns a copy or a view)",
                "Python/pandas — cleaning semantics (NaN vs None vs empty string, dtype surprises, why a filter silently drops rows, vectorized operations vs iterating rows)",
            ],
        },
    ],
    "datascience": [
        {
            "tag": "SQL",
            "count": 2,
            "topics": [
                "SQL for analysis — assembling a modelling dataset (joining fact and dimension tables, choosing the grain, why a careless join leaks future information into training data)",
                "SQL — window functions for temporal features (LAG/LEAD, rolling aggregates, point-in-time correctness, computing a label without leaking the future)",
            ],
        },
        {
            "tag": "Python",
            "count": 2,
            "topics": [
                "Python for modelling — the fit/transform contract (why a scaler or encoder is fit on train only, what leaks when it is fit on the full dataset, why pipelines exist)",
                "Python — numpy/pandas semantics that bite (broadcasting, vectorization vs loops, in-place mutation and chained-assignment surprises, memory and dtype cost on large frames)",
            ],
        },
    ],
    "ai_engineer": [
        {
            "tag": "SQL",
            "count": 2,
            "topics": [
                "SQL for AI systems — retrieval and filtering (metadata filters alongside vector search, why pre-filtering and post-filtering give different results, joining chunks back to source documents)",
                "SQL for AI systems — logging and evaluation (modelling a traces/evals table, aggregating quality and cost per model version, finding regressions between two releases)",
            ],
        },
        {
            "tag": "Python",
            "count": 2,
            "topics": [
                "Python for LLM services — concurrency and I/O (why LLM calls are I/O-bound, async vs threads, batching, timeouts and retries with backoff, why a blocking call stalls a server)",
                "Python for LLM services — robustness (validating and parsing model output, handling malformed JSON, retry and fallback structure, streaming responses, managing token/cost accounting)",
            ],
        },
    ],
}


def _required_slots(total_questions: int, n_required: int) -> list:
    """Question numbers at which a required (Python/SQL) topic should be asked.

    Spread evenly rather than front-loaded, and never on Q1-Q2 — those belong to
    the introduction and a warm-up, where a sudden "explain window functions"
    lands badly. The final question is also left free so the interview can close
    on something conversational.
    """
    if n_required <= 0:
        return []
    first = 3
    last = max(first, total_questions - 1)
    if n_required == 1:
        return [(first + last) // 2]
    step = (last - first) / (n_required - 1)
    return [round(first + i * step) for i in range(n_required)]


# Domain-specific question banks with topic tags
DOMAIN_QUESTIONS = {
    "datascience": {
        "difficulty": (
            "The candidate is a FRESHER (entry-level data scientist). Difficulty mix across the "
            "interview: most questions (roughly 7 of 9) must be MID-LEVEL — clear conceptual questions "
            "on fundamentals (e.g. what overfitting is and how to detect it, when to use precision vs "
            "recall, why we split train/test) that a well-prepared graduate can answer. Include AT MOST "
            "2 genuinely hard, top-company (Google/Meta/Amazon) style questions probing WHY and "
            "trade-offs (e.g. L1 sparsity geometry, offline-vs-launch metric gaps) — place these "
            "mid-to-late in the interview, never back-to-back. Use simple realistic framings (churn, "
            "fraud, recommendations) where natural, and keep everything strictly verbal and "
            "theoretical: NO code writing, NO math derivations to write out, NO datasets or numbers "
            "to compute on."
        ),
        "topics": [
            "Statistical inference (CLT, confidence interval interpretation, p-value misconceptions, Type I/II errors, statistical power)",
            "Multiple testing and experiment pitfalls (p-hacking, Bonferroni/FDR corrections, peeking problem, novelty effects)",
            "Probability reasoning (Bayes' theorem in practice, conditional probability, base-rate fallacy, common distributions and where they arise)",
            "Estimation theory (maximum likelihood vs MAP, how MLE connects to loss functions, bootstrap intuition)",
            "Bias-variance tradeoff (decomposition, how it drives model and hyperparameter choices, double descent awareness)",
            "Regularization theory (L1 vs L2 geometry, why L1 induces sparsity, elastic net, regularization as a prior)",
            "Linear and logistic regression depth (assumptions and violations, multicollinearity, coefficient and odds-ratio interpretation)",
            "Tree ensembles (why bagging reduces variance vs boosting reduces bias, random forest decorrelation, gradient boosting/XGBoost concepts)",
            "Model evaluation theory (ROC-AUC vs PR-AUC under class imbalance, calibration, log-loss vs accuracy, metric choice under asymmetric business costs)",
            "Class imbalance (why accuracy misleads, resampling vs class weights vs threshold tuning, evaluation under imbalance)",
            "Feature engineering and leakage (target leakage, train/serving skew, high-cardinality encoding, target encoding risks)",
            "Validation design (k-fold vs stratified vs time-series splits, nested CV, why random splits fail on temporal or grouped data)",
            "Optimization concepts (SGD vs batch, learning rate effects, momentum/Adam intuition, local minima vs saddle points)",
            "Deep learning theory (backpropagation intuition, vanishing/exploding gradients, batch norm, dropout as regularization, embeddings, when deep learning beats classical ML)",
            "Unsupervised learning (k-means assumptions and failure modes, DBSCAN vs hierarchical, PCA intuition, curse of dimensionality)",
            "Causal inference (confounders vs mediators vs colliders, observational methods — propensity scores, difference-in-differences, instrumental variables at concept level)",
            "Experimentation at scale (power and sample size reasoning, randomization units, network interference, sequential testing, offline metric vs launch metric gaps)",
            "Time series concepts (stationarity, autocorrelation, leakage in temporal validation, classical vs ML forecasting trade-offs)",
            "ML in production (model drift detection, retraining strategy, offline/online metric mismatch, monitoring what matters)",
            "Metric and product sense (diagnosing a sudden metric drop, defining success metrics for a model launch, guardrail metrics)"
        ],
        "sample_starters": [
            "Why does L1 regularization drive some coefficients exactly to zero while L2 only shrinks them?",
            "Your fraud model shows 99% accuracy — why might that be meaningless, and what would you evaluate instead?",
            "How do bagging and boosting differ in which component of error they attack?",
            "What does a p-value actually mean, and what's the most common way people misinterpret it?",
            "You ran 20 A/B tests and one came back significant at 0.05 — how do you interpret that?",
            "When would ROC-AUC mislead you, and why would PR-AUC be the better choice?",
            "What is target leakage? Give a realistic example of how it silently inflates offline performance.",
            "Why can't you use standard k-fold cross-validation on time-series data, and what do you use instead?",
            "Your A/B test showed a significant lift, but the full launch shows no impact — what could explain the gap?",
            "Explain how maximum likelihood estimation connects to the loss functions we minimize in practice.",
            "Why do vanishing gradients occur in deep networks, and which techniques mitigate them?",
            "What assumptions does k-means make about cluster shape, and when does it fail badly?",
            "How would you estimate the causal effect of a feature on retention when you can't run an experiment?",
            "A key business metric dropped 10% week-over-week — walk me through your investigation, step by step.",
            "How would you detect that a deployed model's performance is degrading, before the business notices?",
            "Why is a confounder different from a mediator, and why does controlling for the wrong one hurt you?"
        ]
    },
    "hr(humain recourse) + managerial": {
        "topics": [
            "Self-introduction and professional background (walk me through your resume, career journey)",
            "Strengths (top strengths, what you excel at, how they add value)",
            "Weaknesses and self-improvement (honest weakness, steps taken to improve)",
            "Career goals and aspirations (short-term and long-term goals, where you see yourself in 5 years)",
            "Motivation and work values (what drives you, what kind of work energizes you)",
            "Why this company and role (research on the company, alignment with values and mission)",
            "Teamwork and collaboration (working in teams, handling different personalities)",
            "Leadership and initiative (taking ownership, leading without authority, stepping up)",
            "Conflict resolution (handling disagreements with teammates or managers, staying professional)",
            "Handling pressure and deadlines (working under stress, managing multiple priorities)",
            "Achievements and accomplishments (proudest professional achievement, impact delivered)",
            "Adaptability and change management (adjusting to new environments, handling uncertainty)",
            "Communication skills (how you communicate upward and across teams)",
            "Failure and learnings (a time you failed, what you learned, how you bounced back)",
            "Cultural fit and work style (preferred work environment, collaboration style)",
            "Feedback and criticism (receiving constructive feedback, acting on it)",
            "Work-life balance and self-management (managing time, staying productive)",
            "Salary and career expectations (what you're looking for, negotiation mindset)"
        ],
        "sample_starters": [
            "Tell me about yourself and walk me through your professional journey",
            "What would you say are your top three strengths?",
            "What is one weakness you are actively working on improving?",
            "Where do you see yourself professionally in the next 3 to 5 years?",
            "What motivates you the most in your work?",
            "Why are you interested in this role and our company specifically?",
            "Describe a time you had to work closely with a difficult teammate. How did you handle it?",
            "Tell me about a time you took initiative without being asked",
            "Describe a situation where you disagreed with your manager. What did you do?",
            "How do you manage your work when you have multiple deadlines at the same time?",
            "What is your proudest professional achievement so far?",
            "Tell me about a time you had to adapt quickly to a major change at work",
            "Tell me about a time you failed at something. What did you learn from it?",
            "How do you prefer to receive feedback from your manager?",
            "Describe your ideal work environment and team culture",
            "How do you handle a situation where you strongly disagree with a team decision?",
            "Tell me about a time you went above and beyond what was expected of you",
            "How do you stay productive and maintain focus when working under pressure?"
        ]
    },
    "data_analytics": {
        "topics": [
            "SQL fundamentals (SELECT, WHERE, JOIN types, GROUP BY, aggregations)",
            "Advanced SQL (subqueries, CTEs, window functions, CASE statements, query optimization)",
            "Data visualization principles (chart selection, chart types for different data, color theory, accessibility)",
            "Dashboard design (layout, hierarchy, interactivity, KPI placement, dashboard vs report)",
            "Data storytelling (narrative structure, audience adaptation, actionable insights, executive communication)",
            "Business metrics and KPIs (CAC, churn rate, LTV, conversion rates, retention metrics)",
            "Funnel analysis (drop-off identification, conversion optimization, user journey mapping)",
            "A/B testing and experimentation (statistical significance, sample size, hypothesis testing)",
            "Data cleaning techniques (handling missing values, outlier detection, duplicate removal strategies)",
            "Data quality frameworks (accuracy, completeness, consistency, timeliness, validation checks)",
            "Excel concepts (formulas, pivot tables, VLOOKUP/XLOOKUP, conditional formatting, data analysis)",
            "Tableau concepts (calculated fields, parameters, filters, actions, LOD expressions)",
            "Power BI principles (DAX basics, relationships, data modeling, measures vs columns)",
            "Exploratory Data Analysis techniques (distributions, correlations, patterns, summary statistics)",
            "Statistical concepts for analysts (mean, median, mode, standard deviation, percentiles, variance)",
            "Data segmentation and cohort analysis",
            "Pandas concepts for data manipulation (DataFrames, filtering, grouping, merging - conceptual understanding ONLY, NO code writing)",
            "Data transformation principles (pivoting, melting, aggregating, reshaping)",
            "Reporting best practices (executive summaries, formatting, clarity, actionability)",
            "Stakeholder communication (translating technical findings, managing expectations, presenting insights)",
            "Data ethics and privacy (GDPR basics, PII handling, anonymization, responsible analytics)",
            "Data warehousing concepts (fact tables, dimension tables, star schema, snowflake schema)",
            "ETL/ELT pipeline concepts (data flow, transformations, loading strategies)",
            "Real-world business scenarios (e-commerce analytics, marketing attribution, product analytics, customer behavior)"
        ],
        "sample_starters": [
            "How do you choose the right visualization for different data types?",
            "Explain window functions in SQL and when you'd use them",
            "What KPIs would you track for an e-commerce website?",
            "How do you handle duplicate records in a dataset?",
            "Explain the difference between a dashboard and a report",
            "What's your approach to exploratory data analysis?",
            "How would you optimize a slow SQL query?",
            "When would you use a LEFT JOIN vs an INNER JOIN in SQL?",
            "How do you identify and handle outliers in your data?",
            "What metrics would you use to measure customer retention?",
            "Explain how you would present technical findings to non-technical stakeholders",
            "How do you ensure data quality in your analysis?",
            "What's the difference between a measure and a dimension in BI tools?",
            "Describe your process for cleaning a messy dataset",
            "How would you design a dashboard for executive leadership?",
            "What statistical concepts are most important for data analysts?",
            "How do you handle missing values in different scenarios?",
            "Explain the concept of a data warehouse and its components",
            "What's your approach to A/B test analysis?",
            "How would you explain customer lifetime value to a marketing team?"
        ]
    },
    "ai_engineer": {
        "difficulty": (
            "The candidate is a FRESHER (entry-level AI engineer). Difficulty mix across the "
            "interview: most questions (roughly 7 of 9) must be MID-LEVEL — clear conceptual "
            "questions on fundamentals (e.g. what an embedding is, why RAG beats fine-tuning for "
            "fresh facts, what temperature controls) that a well-prepared graduate can answer. "
            "Include AT MOST 2 genuinely hard, top-company (Google/Meta/OpenAI) style questions "
            "probing WHY and trade-offs (e.g. why attention is quadratic and what that costs you, "
            "when chunking strategy silently destroys retrieval quality) — place these mid-to-late "
            "in the interview, never back-to-back. Use simple realistic framings (a support "
            "chatbot, a document Q&A system, a summarization pipeline) where natural, and keep "
            "everything strictly verbal and theoretical: NO code writing, NO prompt text to draft "
            "on the spot, NO math derivations to write out."
        ),
        "topics": [
            "Transformer architecture fundamentals (self-attention, multi-head attention, positional encoding, encoder vs decoder)",
            "Tokenization (subword tokenizers, BPE, vocabulary size, why token counts matter for cost and context)",
            "Embeddings (vector representations, semantic similarity, cosine similarity, embedding model selection)",
            "Pretraining vs fine-tuning vs prompting (when each is appropriate, cost and data trade-offs)",
            "Parameter-efficient fine-tuning concepts (LoRA, adapters, why full fine-tuning is often unnecessary)",
            "Prompt engineering principles (zero-shot, few-shot, chain-of-thought, system vs user instructions)",
            "Decoding and generation parameters (temperature, top-p, top-k, greedy vs sampling, determinism)",
            "Retrieval-Augmented Generation (RAG) architecture (indexing, retrieval, reranking, generation stages)",
            "Chunking strategies for RAG (chunk size, overlap, semantic vs fixed splitting, impact on retrieval quality)",
            "Vector databases and search (ANN indexes, HNSW concepts, hybrid search, metadata filtering)",
            "Hallucination (why LLMs hallucinate, detection strategies, grounding and citation techniques)",
            "Context windows and long-context handling (truncation, summarization, lost-in-the-middle effects)",
            "LLM evaluation (offline benchmarks, LLM-as-judge, human eval, golden datasets, regression testing)",
            "Agents and tool use (function calling, ReAct-style loops, planning, failure modes of autonomous agents)",
            "Multi-step orchestration concepts (chaining, routing, when an agent is overkill versus a fixed pipeline)",
            "Guardrails and safety (prompt injection, jailbreaks, input/output filtering, PII handling)",
            "Inference optimization (quantization, batching, KV caching, latency vs throughput vs quality trade-offs)",
            "Cost management (token accounting, model tiering, caching, when a smaller model is the right call)",
            "LLMOps and deployment (versioning prompts and models, monitoring, observability, drift, rollback)",
            "Model selection trade-offs (open vs closed models, size vs latency vs quality, self-hosting considerations)",
            "Multimodal and speech concepts (vision-language models, speech-to-text, cross-modal embeddings)",
            "Real-world AI system scenarios (support chatbots, document Q&A, summarization pipelines, semantic search)"
        ],
        "sample_starters": [
            "What is self-attention actually computing, and why did it replace recurrence in sequence models?",
            "When would you choose RAG over fine-tuning a model, and when is that the wrong call?",
            "What does the temperature parameter control, and when would you set it to zero?",
            "Why do large language models hallucinate, and what can you do at the system level to reduce it?",
            "Explain what an embedding is and how semantic search uses it.",
            "How does chunk size and overlap affect the quality of a RAG system's answers?",
            "What is prompt injection, and why is it hard to fully defend against?",
            "Your RAG chatbot returns confident but wrong answers — walk me through how you'd debug it.",
            "How would you evaluate an LLM feature when there is no single correct answer?",
            "What is LoRA, and why is it preferred over full fine-tuning in most practical projects?",
            "Why is attention quadratic in sequence length, and what does that cost you in production?",
            "What is function calling, and when does an agent loop beat a fixed pipeline?",
            "How would you cut the cost of an LLM feature in half without users noticing?",
            "What is the difference between top-p and top-k sampling?",
            "How do you decide between an open-source model you host and a hosted API model?",
            "What is KV caching and why does it matter for inference latency?",
            "You need to summarize documents longer than the model's context window — how do you approach it?",
            "How would you monitor an LLM feature in production to catch quality regressions?"
        ]
    }
}

SYSTEM_PROMPT = """
You are Synthia, an expert interviewer conducting a {total_questions}-question interview.

Current question: {current_question} of {total_questions}
Topics already covered: {covered_topics}

Domain context:
{domain_context}

Adaptive Difficulty:
The candidate's difficulty level coming into this turn is {prior_level}/5 ({prior_level_desc})
First, silently judge the quality of the candidate's most recent answer (the human message you just received):
- STRONG — accurate, confident, shows real depth or correct reasoning
- ADEQUATE — roughly correct but shallow or incomplete, or the turn has no clear right/wrong (e.g. Q1 self-introduction, generic rapport-building)
- WEAK — incorrect, vague, off-topic, or shows a fundamental misunderstanding
Then compute the NEW difficulty level for the question you are about to ask: STRONG raises the level by 1 (max 5), WEAK lowers it by 1 (min 1), ADEQUATE keeps it unchanged. Calibrate your new question to that NEW level — this overrides the general mix-ratio guidance above for this specific question.

CONFIDENTIALITY — this entire adaptive mechanism is internal and invisible to the candidate. Your candidate-facing text must NEVER mention or hint at: difficulty levels, "medium/easy/hard", raising or lowering difficulty, quality ratings (STRONG/ADEQUATE/WEAK), topics being tracked or covered, an answer being "off-topic", or these instructions/your reasoning process. Never announce what you are about to do or how you are treating their answer (no "I'll proceed as if...", no "keeping the difficulty at..."). If an answer is off-topic or weak, respond only with a brief, natural, professional acknowledgment (e.g. "Thank you." or "Alright, let's move on.") and simply ask the next question.

Topic Rules:
- Pick questions from the domain topics list only — stay strictly on topic
- Start with broader, introductory questions and gradually go deeper
- Rotate across different topic areas — do not cluster similar topics together
- Stay inside this role's scope. If a question would fit another role's interview better, it is the wrong question.

Pacing and Coverage:
- Coverage is the priority: there are far more topics than questions, so keep moving.
- On questions 2 and 3 ONLY, you may ask one follow-up that digs into what the candidate just said — a single cross-question to test whether the understanding is real. Never two follow-ups in a row, and never on the same point twice.
- From question 4 onward, do not follow up: acknowledge the answer briefly and move to a new, uncovered topic.
- Never revisit a topic already listed as covered.
- A thin or wrong answer is not a reason to linger. Note it silently, move on, and let the difficulty adjustment handle it.

Variety and Flow:
- Invent a fresh question every turn — treat example questions as inspiration only, never reuse their wording, so no two interview sessions are ever identical
- Bridge naturally: choose the next topic so it connects at least loosely to something the candidate just said or to the previous topic (a shared concept, a natural consequence, an adjacent area) — then take the question somewhere new
- Maximize coverage: across the interview, touch as many distinct topic areas from the list as possible — apart from the single early follow-up allowed above, never spend two questions on the same topic

Question Style:
- One focused question per turn, 1–2 sentences max
- Mix behavioral and situational questions naturally
- For HR: use real-world scenarios and STAR-style prompts (Situation, Task, Action, Result); judge answer quality by depth and specificity, not factual correctness
- For technical domains: concepts only, no code writing

Response Format:
- One brief, natural interviewer remark on their previous answer (skip on Q1) — spoken like a human interviewer would, never commentary about your process, ratings, or difficulty
- One new question from an uncovered topic, calibrated to the new difficulty level you computed above
- Then, on the second-to-last line by itself, write exactly: QUALITY: <STRONG|ADEQUATE|WEAK>
- Then, on the very last line by itself, write exactly: TOPIC: <the topic name you chose from the list>
  (these two lines are stripped before the candidate sees your message — never omit either one)

Language: English only.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", "{system_prompt}"),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
])
def _with_memory(llm):
    return RunnableWithMessageHistory(
        prompt | llm,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )


# Ordered provider chain, built from whichever providers actually initialized.
# Only configured providers appear, so a Groq-only deployment (the natural
# free-tier setup — Groq has a free API tier, OpenAI does not) no longer pays a
# guaranteed-to-fail OpenAI round trip before every single question.
#
# LLM_PROVIDER_ORDER overrides the preference, e.g. "groq,openai" to lead with
# Groq for latency, or "groq" to pin one provider.
_LLM_REGISTRY = {"openai": openai_llm, "groq": groq_llm}
_DEFAULT_ORDER = ["openai", "groq"]
_requested_order = [
    n.strip().lower()
    for n in _os.getenv("LLM_PROVIDER_ORDER", ",".join(_DEFAULT_ORDER)).split(",")
    if n.strip()
]
_PROVIDERS = [
    (name, _with_memory(_LLM_REGISTRY[name]))
    for name in _requested_order
    if _LLM_REGISTRY.get(name) is not None
]

if _PROVIDERS:
    log.info("LLM providers active, in order: %s", ", ".join(n for n, _ in _PROVIDERS))


class NoLLMProviderError(RuntimeError):
    """Raised when no LLM provider is configured — surfaced by the API as 503."""


def safe_invoke_agent(payload, session_id):
    """Invoke the first provider that succeeds, falling through on failure.

    The previous version fell back to Groq only when OpenAI's error text matched
    a quota/rate-limit keyword, so an invalid or revoked OPENAI_API_KEY (a 401,
    with none of those words in it) aborted the interview outright even with a
    perfectly healthy Groq key sitting right there. Any provider failure now
    advances to the next provider; only exhausting all of them raises.
    """
    if not _PROVIDERS:
        raise NoLLMProviderError(
            "No LLM provider is configured. Set GROQ_API_KEY and/or OPENAI_API_KEY."
        )

    last_error: Exception | None = None
    for name, chain in _PROVIDERS:
        try:
            return chain.invoke(payload, config={"configurable": {"session_id": session_id}})
        except Exception as exc:
            last_error = exc
            log.warning("LLM provider %s failed (%s): %s", name, type(exc).__name__, exc)

    raise last_error  # type: ignore[misc]


# The interview supports exactly four domains. Anything else is rejected at the
# door (see _normalize_domain) rather than silently falling through to an empty
# topic list, which would leave the model to invent an unguided interview.
HR_DOMAIN = "hr(humain recourse) + managerial"

_DOMAIN_ALIASES = {
    "hr": HR_DOMAIN,
    "hr / managerial": HR_DOMAIN,
    "hr/managerial": HR_DOMAIN,
    "human resources": HR_DOMAIN,
    "managerial": HR_DOMAIN,
    HR_DOMAIN: HR_DOMAIN,
    "data analytics": "data_analytics",
    "data_analytics": "data_analytics",
    "data analyst": "data_analytics",
    "analytics": "data_analytics",
    "datascience": "datascience",
    "data science": "datascience",
    "data_science": "datascience",
    "data scientist": "datascience",
    "ai_engineer": "ai_engineer",
    "ai engineer": "ai_engineer",
    "ai-engineer": "ai_engineer",
    "aiengineer": "ai_engineer",
    "ml engineer": "ai_engineer",
    "machine learning engineer": "ai_engineer",
}

# Fallback for an unrecognized role. HR is the safe default: it is the one
# domain that makes sense for any candidate regardless of their background.
DEFAULT_DOMAIN = HR_DOMAIN

def _normalize_domain(domain: str) -> str:
    key = (domain or "").lower().strip()
    resolved = _DOMAIN_ALIASES.get(key)
    if resolved is None:
        print(f"WARNING: unsupported domain {domain!r} — falling back to {DEFAULT_DOMAIN!r}")
        return DEFAULT_DOMAIN
    return resolved

def run_agent_turn(message: str, session_id: str, domain: str | None = None, name: str | None = None):
    # One record per session, created on first turn and evicted on a TTL. A
    # request arriving without a domain still gets a valid (fallback) one and
    # initialized counters rather than failing on the first turn.
    state = _get_or_create_session(session_id, domain)

    # The typed name is authoritative over anything the model might infer from
    # the transcribed "introduce yourself" answer — speech-to-text frequently
    # mangles non-English names. Store it once; later calls omit it.
    if name and name.strip():
        state.name = name.strip()

    domain_text = state.domain

    state.question_count += 1
    current_q = state.question_count

    # Get domain-specific context
    domain_info = DOMAIN_QUESTIONS[domain_text]
    all_topics = domain_info.get("topics", [])

    # Track covered topics (moved up so we can filter the topics list below —
    # already-covered topics are dead weight in the prompt since the model is
    # told never to revisit them anyway)
    covered = state.topics_covered
    covered_str = ", ".join(covered) if covered else "None yet"
    uncovered_topics = [t for t in all_topics if t.split("(")[0].strip() not in covered]

    # Show only a random slice of the uncovered topics each turn, not the
    # whole list. Two effects, both wanted: (1) a big domain like data
    # analytics has 20+ topics, and models tend to gravitate to the same
    # "safe" ones (A/B testing, SQL joins...) turn after turn, session after
    # session, when shown the full list every time — a shuffled subset breaks
    # that bias and spreads real coverage across the field. (2) it's strictly
    # fewer tokens than listing everything, so this is a variety win and a
    # cost win at the same time, not a tradeoff between them.
    TOPIC_SAMPLE_SIZE = 8
    topics_list = random.sample(uncovered_topics, min(TOPIC_SAMPLE_SIZE, len(uncovered_topics)))

    # Build domain context with the sampled topics only
    domain_context = ""
    difficulty = domain_info.get("difficulty", DEFAULT_DIFFICULTY)
    if difficulty:
        domain_context += f"DIFFICULTY CALIBRATION:\n{difficulty}\n\n"
    scope = DOMAIN_SCOPE.get(domain_text)
    if scope:
        domain_context += f"{scope}\n\n"
    domain_context += f"AVAILABLE TOPICS FOR {domain_text.upper()}:\n"
    for i, topic in enumerate(topics_list, 1):
        domain_context += f"{i}. {topic}\n"

    # Add starter questions for inspiration on the first question only — later
    # turns already have real candidate answers to bridge from, so the extra
    # examples stop earning their token cost.
    sample_starters = domain_info.get("sample_starters", [])
    if sample_starters and current_q == 1:
        random_samples = random.sample(sample_starters, min(3, len(sample_starters)))
        domain_context += f"\nEXAMPLE QUESTIONS (for inspiration, vary your wording):\n"
        for sample in random_samples:
            domain_context += f"- {sample}\n"

    # Adaptive difficulty: level going into this turn, before we know how the
    # candidate's latest answer scores (that's judged by the model this turn).
    prior_level = state.difficulty

    # Adaptive interview length. Extending past MIN_QUESTIONS requires
    # DEMONSTRATED STRENGTH, not merely the absence of failure.
    #
    # The previous gate was "the last answer wasn't WEAK", which in practice
    # extended almost every interview to the maximum: models are reluctant to
    # label an answer WEAK and default to ADEQUATE, so a candidate giving
    # entirely mediocre answers cleared the bar every turn and sat through 15
    # questions. Requiring a net-positive tally instead means a wholly ADEQUATE
    # interview scores 0 and correctly ends at MIN_QUESTIONS, while a candidate
    # who is genuinely performing well earns the extra questions.
    decided_total = state.total_questions
    if current_q + 1 >= decided_total and decided_total < MAX_QUESTIONS:
        going_well = (
            state.performance >= EXTENSION_MIN_PERFORMANCE
            and state.last_quality != "WEAK"
            and not _looks_like_non_answer(message)
        )
        if going_well:
            decided_total = min(MAX_QUESTIONS, decided_total + 1)
    state.total_questions = decided_total

    # ── Required Python/SQL quota ─────────────────────────────────────────
    # The question about to be generated (Q1 is hardcoded on the frontend, so
    # this call produces question current_q + 1).
    asked_number = min(current_q + 1, decided_total)
    quotas = REQUIRED_TOPIC_QUOTAS.get(domain_text, [])
    total_required = sum(b["count"] for b in quotas)
    done_required = sum(state.required_covered.get(b["tag"], 0) for b in quotas)
    forced_topic = None
    forced_tag = None

    if quotas and done_required < total_required:
        slots = _required_slots(decided_total, total_required)
        # How many quota slots the interview has already reached.
        due = sum(1 for slot in slots if slot <= asked_number)
        questions_left = max(0, decided_total - asked_number)
        remaining_required = total_required - done_required
        # Ask now if a scheduled slot has come due, or if the interview is
        # running out of room to fit what is still owed. The second condition
        # is the guarantee: the quota is always met before the interview ends,
        # even when the adaptive length lands short.
        if due > done_required or remaining_required > questions_left:
            for bucket in quotas:
                used = state.required_covered.get(bucket["tag"], 0)
                if used < bucket["count"]:
                    forced_topic = bucket["topics"][used]
                    forced_tag = bucket["tag"]
                    break

    if forced_topic:
        # Credit it here rather than trusting the returned TOPIC line.
        state.required_covered[forced_tag] = state.required_covered.get(forced_tag, 0) + 1
        domain_context += (
            f"\n\nMANDATORY TOPIC FOR THIS QUESTION — this overrides the topic list above.\n"
            f"Ask exactly one {forced_tag} question on: {forced_topic}\n"
            f"Pitch it at MEDIUM difficulty: a clear, practical question a well-prepared "
            f"fresher can answer out loud. It must be conceptual and spoken — ask what "
            f"something does, why it behaves that way, or which approach they would choose "
            f"and why. NEVER ask them to write, dictate, or recite code or a query.\n"
            f"Write it as a natural interview question. Do not mention that it was required, "
            f"and still end your reply with the QUALITY: and TOPIC: lines as normal "
            f"(use TOPIC: {forced_tag}).\n"
        )

    # Create system prompt with session context.
    # The first question ("Introduce yourself.") is hardcoded on the frontend,
    # so this call generates question current_q + 1 of the interview.
    system_prompt = SYSTEM_PROMPT.format(
        domain_context=domain_context,
        covered_topics=covered_str,
        current_question=min(current_q + 1, decided_total),
        total_questions=decided_total,
        prior_level=prior_level,
        prior_level_desc=DIFFICULTY_LEVELS[prior_level],
    )
    
    system_prompt += f"\n\nSTRICT DOMAIN: {domain_text}. Ask ONLY {domain_text} questions. Ignore off-topic responses."

    candidate_name = state.name
    if candidate_name:
        system_prompt += (
            f"\n\nCANDIDATE NAME: The candidate's name is exactly \"{candidate_name}\" (as they "
            "typed it themselves). If you address them by name at any point, use this exact "
            "spelling — never substitute a different name or spelling you think you heard in "
            "their spoken introduction, since speech-to-text can mishear names, especially "
            "non-English ones."
        )
    
    result = safe_invoke_agent(
    {
        "input": message,
        "system_prompt": system_prompt
    },
    session_id=session_id
    )

    
    response_text = result.content

    # Adaptive difficulty: the model judges the quality of the answer it just
    # received on a trailing "QUALITY: ..." line; use that to bump the level
    # up/down for the next question, then strip the line from the candidate view.
    quality_match = re.search(r"^\s*QUALITY:\s*(STRONG|ADEQUATE|WEAK)\s*$", response_text, re.MULTILINE | re.IGNORECASE)
    if quality_match:
        quality = quality_match.group(1).upper()
    else:
        quality = "ADEQUATE"  # model omitted the line, or wrote it malformed — hold difficulty steady
    # Always strip any QUALITY:-prefixed line from the candidate view, even a
    # malformed one with no value — at temperature 0.9 the model occasionally
    # emits a bare "QUALITY:" and stops instead of following through with the
    # word, which would otherwise leak into the candidate-facing text.
    response_text = re.sub(r"\n?\s*QUALITY:.*$", "", response_text, flags=re.MULTILINE | re.IGNORECASE).strip()

    state.last_quality = quality

    if quality == "STRONG":
        state.performance += 1
        state.difficulty = min(5, prior_level + 1)
    elif quality == "WEAK":
        state.performance -= 1
        state.difficulty = max(1, prior_level - 1)
    else:
        # ADEQUATE decays the tally one step toward zero rather than holding it.
        # Without decay a single STRONG answer early on kept the tally positive
        # for the rest of the interview, so one good moment in an otherwise
        # mediocre performance still bought every extra question. Extending now
        # requires sustained quality, not one high point.
        if state.performance > 0:
            state.performance -= 1
        elif state.performance < 0:
            state.performance += 1
        state.difficulty = prior_level

    # A deterministic non-answer costs a point regardless of how the model rated
    # it — testing showed models happily call "skip this" ADEQUATE, which is
    # exactly the case this tally exists to catch.
    if _looks_like_non_answer(message):
        state.performance -= 1

    state.performance = max(PERFORMANCE_FLOOR, min(PERFORMANCE_CEILING, state.performance))

    # The model declares its chosen topic on a trailing "TOPIC: ..." line;
    # record it for the no-repeat rule and strip it from the candidate-facing text.
    topic_match = re.search(r"^\s*TOPIC:\s*(.+?)\s*$", response_text, re.MULTILINE | re.IGNORECASE)
    if topic_match:
        chosen_topic = topic_match.group(1).split("(")[0].strip()
        if chosen_topic and chosen_topic not in covered:
            state.topics_covered.append(chosen_topic)
    # Always strip a TOPIC:-prefixed line from the candidate view, matching
    # the same defensive handling as QUALITY: above, even if it had no usable
    # value (falls through to the keyword heuristic below in that case).
    response_text = re.sub(r"\n?\s*TOPIC:.*$", "", response_text, flags=re.MULTILINE | re.IGNORECASE).strip()
    if not topic_match:
        # Fallback: keyword heuristic if the model omitted the TOPIC line
        lowered = response_text.lower()
        for topic in topics_list:
            topic_keywords = topic.split('(')[0].strip().lower()
            if any(keyword in lowered for keyword in topic_keywords.split()):
                if topic not in covered:
                    state.topics_covered.append(topic.split('(')[0].strip())
                    break

    log.info(
        "session=%s domain=%s q=%d/%d quality=%s difficulty=%d->%d perf=%d topics=%d",
        session_id, domain_text, min(current_q + 1, decided_total), decided_total,
        quality, prior_level, state.difficulty, state.performance, len(state.topics_covered),
    )

    return {
        "question": response_text,
        "total_questions": decided_total,
        "is_last_question": (current_q + 1) >= decided_total,
    }
