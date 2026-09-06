"""End-to-end interview simulation with a stubbed LLM.

Drives a full interview through run_agent_turn to prove the prompt assembly,
quota scheduling, topic tracking and difficulty adaptation all work together —
without ever calling a real model. Run with
    ./venv/bin/python -m pytest test_interview_flow.py -v
"""
import os
import re
import sys
import tempfile

import pytest

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="voxhire-flow-")
os.environ.setdefault("GROQ_API_KEY", "test-key")

from app import agent  # noqa: E402


class FakeLLM:
    """Records the system prompt it was given and returns a well-formed reply."""

    def __init__(self, quality="ADEQUATE"):
        self.prompts = []
        self.quality = quality

    def invoke(self, payload, config=None):
        sp = payload["system_prompt"]
        self.prompts.append(sp)
        # Echo back the mandated topic when the engine forced one, mirroring
        # what a compliant model does.
        m = re.search(r"Ask exactly one (\w+) question on: (.+)", sp)
        topic = m.group(1) if m else "Some topic"
        class R:
            content = f"Good. Here is the next question?\nQUALITY: {self.quality}\nTOPIC: {topic}"
        return R()


@pytest.fixture
def fake_llm(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(agent, "_PROVIDERS", [("fake", llm)])
    agent._sessions.clear()
    return llm


def _run_interview(llm, domain, session="flow-1", turns=12):
    replies = []
    for i in range(turns):
        r = agent.run_agent_turn(
            message="This is a substantive answer about the topic at hand.",
            session_id=session,
            domain=domain if i == 0 else None,
            name="Test Candidate" if i == 0 else None,
        )
        replies.append(r)
        if r["is_last_question"]:
            break
    return replies


@pytest.mark.parametrize("domain", ["data_analytics", "datascience", "ai_engineer"])
def test_full_interview_meets_python_and_sql_quota(fake_llm, domain):
    _run_interview(fake_llm, domain, session=f"flow-{domain}")
    state = agent._sessions[f"flow-{domain}"]
    assert state.required_covered.get("Python") == 2, state.required_covered
    assert state.required_covered.get("SQL") == 2, state.required_covered


@pytest.mark.parametrize("domain", ["data_analytics", "datascience", "ai_engineer"])
def test_mandatory_questions_forbid_code_writing(fake_llm, domain):
    _run_interview(fake_llm, domain, session=f"code-{domain}")
    mandated = [p for p in fake_llm.prompts if "MANDATORY TOPIC" in p]
    assert mandated, "no mandatory Python/SQL question was issued"
    for p in mandated:
        assert "NEVER ask them to write, dictate, or recite code" in p
        assert "MEDIUM difficulty" in p


def test_hr_interview_has_no_mandatory_python_or_sql(fake_llm):
    _run_interview(fake_llm, "hr", session="flow-hr")
    assert not any("MANDATORY TOPIC" in p for p in fake_llm.prompts)


@pytest.mark.parametrize("domain", ["data_analytics", "datascience", "ai_engineer"])
def test_scope_boundary_is_sent_every_turn(fake_llm, domain):
    _run_interview(fake_llm, domain, session=f"scope-{domain}", turns=4)
    assert all("SCOPE —" in p for p in fake_llm.prompts)


def test_pacing_rules_reach_the_model(fake_llm):
    _run_interview(fake_llm, "ai_engineer", session="pace", turns=3)
    p = fake_llm.prompts[0]
    assert "Pacing and Coverage" in p
    assert "questions 2 and 3 ONLY" in p
    assert "From question 4 onward, do not follow up" in p


def test_topics_are_tracked_and_not_repeated(fake_llm):
    _run_interview(fake_llm, "data_analytics", session="topics", turns=8)
    covered = agent._sessions["topics"].topics_covered
    assert len(covered) == len(set(covered)), covered


def test_difficulty_rises_on_strong_answers(monkeypatch):
    llm = FakeLLM(quality="STRONG")
    monkeypatch.setattr(agent, "_PROVIDERS", [("fake", llm)])
    agent._sessions.clear()
    for _ in range(4):
        agent.run_agent_turn("A strong, detailed answer.", "diff-up", domain="datascience")
    assert agent._sessions["diff-up"].difficulty == 5


def test_difficulty_falls_on_weak_answers(monkeypatch):
    llm = FakeLLM(quality="WEAK")
    monkeypatch.setattr(agent, "_PROVIDERS", [("fake", llm)])
    agent._sessions.clear()
    for _ in range(4):
        agent.run_agent_turn("uhh", "diff-down", domain="datascience")
    assert agent._sessions["diff-down"].difficulty == 1


def test_control_lines_are_stripped_from_candidate_text(fake_llm):
    r = agent.run_agent_turn("A real answer.", "strip", domain="ai_engineer")
    assert "QUALITY:" not in r["question"]
    assert "TOPIC:" not in r["question"]


def test_unknown_domain_still_produces_a_guided_interview(fake_llm):
    """A stale 'frontend' role must fall back to a real bank, not an empty one."""
    agent.run_agent_turn("An answer.", "legacy", domain="frontend")
    assert agent._sessions["legacy"].domain in agent.DOMAIN_QUESTIONS
    assert "AVAILABLE TOPICS FOR" in fake_llm.prompts[0]


def test_provider_fallback_when_the_first_provider_fails(monkeypatch):
    class Broken:
        def invoke(self, payload, config=None):
            raise RuntimeError("401 invalid api key")
    good = FakeLLM()
    monkeypatch.setattr(agent, "_PROVIDERS", [("broken", Broken()), ("good", good)])
    agent._sessions.clear()
    r = agent.run_agent_turn("An answer.", "fallback", domain="hr")
    assert r["question"]
    assert good.prompts, "should have fallen through to the healthy provider"


def test_session_state_is_released_when_ended(fake_llm):
    agent.run_agent_turn("An answer.", "cleanup", domain="hr")
    assert agent.session_count() == 1
    agent.end_session("cleanup")
    assert agent.session_count() == 0
