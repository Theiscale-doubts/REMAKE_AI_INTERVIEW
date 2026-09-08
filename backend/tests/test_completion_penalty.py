"""An interview that ends before the minimum length must be penalised.

Without this, a candidate who quits after three questions is graded only on
the three answers that exist — so their best moments carry the whole score and
can out-rank someone who sat the full interview.
"""
import os
import sys

import pytest

from app import main  # noqa: E402
from app.agent import MIN_QUESTIONS  # noqa: E402


def _penalise(score, answered, feedback="## Overall Performance\nSolid throughout."):
    return main._apply_completion_penalty(score, feedback, answered)


# ── No penalty once the floor is reached ──────────────────────────────────

@pytest.mark.parametrize("answered", [MIN_QUESTIONS, MIN_QUESTIONS + 1, 12, 15])
def test_complete_interviews_are_untouched(answered):
    score, feedback = _penalise(7.0, answered)
    assert score == 7.0
    assert "Incomplete Interview" not in feedback


# ── Short interviews are docked ───────────────────────────────────────────

@pytest.mark.parametrize("answered,expected", [
    (8, 6.2),   # one short
    (7, 5.4),
    (5, 3.8),
    (3, 2.2),
    (1, 0.6),   # abandoned almost immediately
])
def test_penalty_scales_with_how_much_was_missed(answered, expected):
    score, _ = _penalise(7.0, answered)
    assert score == pytest.approx(expected, abs=0.01), f"{answered} answers -> {score}"


def test_more_missing_questions_always_means_a_lower_score():
    scores = [_penalise(7.0, n)[0] for n in range(1, MIN_QUESTIONS + 1)]
    assert scores == sorted(scores), "penalty must be monotonic in questions answered"


def test_score_never_goes_below_zero():
    score, _ = _penalise(1.0, 1)
    assert score == 0.0


def test_a_short_interview_cannot_outscore_a_complete_one():
    """The exact unfairness this exists to prevent."""
    quitter, _ = _penalise(8.5, 3)      # three strong answers, then left
    completer, _ = _penalise(6.0, 9)    # sat the whole interview, decent
    assert completer > quitter


# ── The reason must be visible to a reviewer ──────────────────────────────

def test_feedback_explains_the_deduction():
    _, feedback = _penalise(7.0, 4)
    assert "## Incomplete Interview" in feedback
    assert "4 of the 9" in feedback
    assert "4.0" in feedback   # the penalty
    assert "3.0" in feedback   # the adjusted score


def test_original_feedback_is_preserved():
    _, feedback = _penalise(7.0, 4, "## Overall Performance\nClear communicator.")
    assert "Clear communicator." in feedback


def test_singular_wording_for_a_single_answer():
    _, feedback = _penalise(7.0, 1)
    assert "1 answer actually given" in feedback


# ── Configurability ───────────────────────────────────────────────────────

def test_penalty_rate_is_configurable(monkeypatch):
    monkeypatch.setattr(main, "INCOMPLETE_PENALTY_PER_QUESTION", 0.5)
    score, _ = _penalise(7.0, 8)
    assert score == pytest.approx(6.5, abs=0.01)
