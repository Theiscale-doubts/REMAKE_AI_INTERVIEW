"""Smoke + regression tests for the VoxHire backend.

Run:  ./venv/bin/python -m pytest test_backend.py -v

No network and no API keys required: every LLM call is stubbed. The point is to
prove the plumbing (domains, quotas, limits, stores, endpoints) behaves, not to
test the model.
"""
import importlib
import json
import os
import sys
import tempfile

import pytest

# Isolate the on-disk stores so tests never touch real interview data.
_TMP = tempfile.mkdtemp(prefix="voxhire-test-")
os.environ["DATA_DIR"] = _TMP
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-pw")
os.environ.pop("OPENAI_API_KEY", None)


from app import agent  # noqa: E402


# ── Domain configuration ──────────────────────────────────────────────────

EXPECTED_DOMAINS = {"hr(humain recourse) + managerial", "data_analytics", "datascience", "ai_engineer"}
TECHNICAL = ["data_analytics", "datascience", "ai_engineer"]


def test_exactly_four_domains():
    assert set(agent.DOMAIN_QUESTIONS) == EXPECTED_DOMAINS


def test_removed_domains_are_gone():
    for dead in ("frontend", "devops", "product"):
        assert dead not in agent.DOMAIN_QUESTIONS


@pytest.mark.parametrize("raw,expected", [
    ("hr", "hr(humain recourse) + managerial"),
    ("HR / Managerial", "hr(humain recourse) + managerial"),
    ("Data Analytics", "data_analytics"),
    ("data science", "datascience"),
    ("AI Engineer", "ai_engineer"),
    ("ml engineer", "ai_engineer"),
])
def test_alias_normalization(raw, expected):
    assert agent._normalize_domain(raw) == expected


@pytest.mark.parametrize("bad", ["frontend", "devops", "product", "", None, "nonsense"])
def test_unknown_domain_falls_back_not_empty(bad):
    """An unknown domain must resolve to a real bank, never an empty prompt."""
    resolved = agent._normalize_domain(bad)
    assert resolved in agent.DOMAIN_QUESTIONS
    assert agent.DOMAIN_QUESTIONS[resolved]["topics"]


def test_every_domain_bank_is_populated():
    for name, bank in agent.DOMAIN_QUESTIONS.items():
        assert len(bank["topics"]) >= 15, name
        assert len(bank["sample_starters"]) >= 10, name


def test_aliases_all_point_at_real_domains():
    assert set(agent._DOMAIN_ALIASES.values()) <= set(agent.DOMAIN_QUESTIONS)


# ── Python / SQL quota ────────────────────────────────────────────────────

def test_quota_defined_for_every_technical_role_only():
    assert set(agent.REQUIRED_TOPIC_QUOTAS) == set(TECHNICAL)
    for role, buckets in agent.REQUIRED_TOPIC_QUOTAS.items():
        tags = {b["tag"]: b["count"] for b in buckets}
        assert tags == {"Python": 2, "SQL": 2}, role
        for b in buckets:
            assert len(b["topics"]) == b["count"], role


def test_hr_has_no_python_or_sql_quota():
    assert "hr(humain recourse) + managerial" not in agent.REQUIRED_TOPIC_QUOTAS


def _replay_quota(domain, total):
    """Replay the engine's quota scheduling across one whole interview."""
    quotas = agent.REQUIRED_TOPIC_QUOTAS.get(agent._normalize_domain(domain), [])
    total_required = sum(b["count"] for b in quotas)
    covered, at = {}, []
    for current_q in range(1, total):
        asked = min(current_q + 1, total)
        done = sum(covered.get(b["tag"], 0) for b in quotas)
        if done >= total_required:
            break
        slots = agent._required_slots(total, total_required)
        due = sum(1 for s in slots if s <= asked)
        left = max(0, total - asked)
        if due > done or (total_required - done) > left:
            for b in quotas:
                if covered.get(b["tag"], 0) < b["count"]:
                    covered[b["tag"]] = covered.get(b["tag"], 0) + 1
                    at.append(asked)
                    break
    return covered, at


@pytest.mark.parametrize("domain", TECHNICAL)
@pytest.mark.parametrize("total", [9, 10, 11, 12, 13, 14, 15])
def test_quota_always_met(domain, total):
    covered, _ = _replay_quota(domain, total)
    assert covered.get("Python") == 2, covered
    assert covered.get("SQL") == 2, covered


@pytest.mark.parametrize("domain", TECHNICAL)
def test_quota_never_lands_on_first_two_questions(domain):
    _, at = _replay_quota(domain, 9)
    assert min(at) >= 3, at


def test_quota_questions_are_spread_not_clustered():
    _, at = _replay_quota("data_analytics", 15)
    assert len(set(at)) == 4
    assert max(at) - min(at) >= 6, at


# ── Role differentiation ──────────────────────────────────────────────────

def test_each_technical_role_has_a_scope_boundary():
    for role in TECHNICAL:
        assert role in agent.DOMAIN_SCOPE
        assert len(agent.DOMAIN_SCOPE[role]) > 200


def test_technical_roles_do_not_share_topic_headings():
    heads = {r: {t.split("(")[0].strip().lower() for t in agent.DOMAIN_QUESTIONS[r]["topics"]} for r in TECHNICAL}
    for a in TECHNICAL:
        for b in TECHNICAL:
            if a < b:
                assert not (heads[a] & heads[b]), f"{a} and {b} share: {heads[a] & heads[b]}"


# ── Session lifecycle / memory bounds ─────────────────────────────────────

def test_session_record_created_and_reused():
    agent._sessions.clear()
    s = agent._get_or_create_session("sess-a", "AI Engineer")
    assert s.domain == "ai_engineer"
    assert agent._get_or_create_session("sess-a", None) is s
    agent.end_session("sess-a")
    assert agent.session_count() == 0


def test_session_cap_is_an_exact_ceiling():
    agent._sessions.clear()
    original = agent.MAX_TRACKED_SESSIONS
    try:
        agent.MAX_TRACKED_SESSIONS = 5
        for i in range(50):
            agent._get_or_create_session(f"s{i}", "hr")
        assert agent.session_count() == 5
        assert "s49" in agent._sessions      # newest is never evicted
    finally:
        agent.MAX_TRACKED_SESSIONS = original
        agent._sessions.clear()


def test_stale_sessions_are_evicted():
    agent._sessions.clear()
    original = agent.SESSION_TTL_SECONDS
    try:
        agent._get_or_create_session("old", "hr")
        agent._sessions["old"].last_seen -= 10_000
        agent.SESSION_TTL_SECONDS = 60
        agent._get_or_create_session("new", "hr")
        assert "old" not in agent._sessions
        assert "new" in agent._sessions
    finally:
        agent.SESSION_TTL_SECONDS = original
        agent._sessions.clear()


def test_import_succeeds_with_no_llm_keys_at_all():
    """Missing API keys must not take the process down at import.

    Run in a clean subprocess with an empty DATA_DIR and no .env, because this
    module's own import already loaded the project's .env. Before the provider
    guard, importing agent.py with no OPENAI_API_KEY raised OpenAIError at
    module scope and the whole service failed to boot.
    """
    import subprocess
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "DATA_DIR": _TMP,
        "VOXHIRE_SKIP_DOTENV": "1",
    }
    code = (
        "from app import agent;"
        "assert agent.openai_llm is None;"
        "assert agent.groq_llm is None;"
        "assert agent._PROVIDERS == [];"
        "print('OK')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env=env, capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"import failed:\n{proc.stderr}"
    assert "OK" in proc.stdout


def test_no_provider_raises_typed_error_not_a_crash():
    """With no providers, callers get NoLLMProviderError (mapped to 503)."""
    saved = agent._PROVIDERS
    try:
        agent._PROVIDERS = []
        with pytest.raises(agent.NoLLMProviderError):
            agent.safe_invoke_agent({"input": "x", "system_prompt": "y"}, "sid")
    finally:
        agent._PROVIDERS = saved
