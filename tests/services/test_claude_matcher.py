# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
from unittest.mock import MagicMock, patch
from services.job_matching.claude_matcher import match_job_with_claude, MatchResult


def test_match_job_returns_structured_result():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"score": 85, "reasoning": "Great fit", "missing_skills": ["k8s"]}')],
        usage=MagicMock(input_tokens=400, output_tokens=80),
    )

    cv_summary = "Senior Frontend Developer, 8 years React/TypeScript"
    job = {"title": "Sr React Dev", "description": "React, TypeScript", "location": "Berlin"}

    result = match_job_with_claude(client=mock_client, model="claude-haiku-4-5",
                                   cv_summary=cv_summary, job=job)
    assert isinstance(result, MatchResult)
    assert result.score == 85
    assert result.reasoning == "Great fit"
    assert "k8s" in result.missing_skills
    assert result.tokens_in == 400
    assert result.tokens_out == 80


def test_match_job_handles_invalid_json():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='not json at all')],
        usage=MagicMock(input_tokens=100, output_tokens=20),
    )
    result = match_job_with_claude(client=mock_client, model="claude-haiku-4-5",
                                   cv_summary="x", job={"title": "y", "description": "z"})
    assert result.score == 0
    assert "fehlgeschlagen" in result.reasoning.lower()


def test_build_user_message_without_feedback():
    from services.job_matching.claude_matcher import _build_user_message
    msg = _build_user_message("CV-text", {"title": "T", "description": "D"})
    assert "<user_feedback_history>" not in msg
    assert "<untrusted_cv>" in msg
    assert "<untrusted_job>" in msg


def test_build_user_message_with_feedback():
    from services.job_matching.claude_matcher import _build_user_message
    fc = "<user_feedback_history>\nstuff\n</user_feedback_history>"
    msg = _build_user_message("CV", {"title": "T", "description": "D"}, fc)
    pos_fc = msg.find("user_feedback_history")
    pos_job = msg.find("<untrusted_job>")
    assert pos_fc > -1 and pos_job > -1 and pos_fc < pos_job


def test_match_job_with_feedback_context_uses_system_message():
    """Mit feedback_context wird der System-Message-Pfad benutzt."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"score": 70, "reasoning": "ok", "missing_skills": []}')],
        usage=MagicMock(input_tokens=200, output_tokens=40),
    )
    fc = "<user_feedback_history>\nbla\n</user_feedback_history>"
    result = match_job_with_claude(
        client=mock_client, model="claude-haiku-4-5",
        cv_summary="cv", job={"title": "t", "description": "d"},
        feedback_context=fc,
    )
    assert result.score == 70
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert "system" in call_kwargs
    assert "user_feedback_history" in call_kwargs["messages"][0]["content"]


def test_match_job_without_feedback_context_uses_legacy_path():
    """Ohne feedback_context wird der legacy single-prompt-Pfad genutzt."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"score": 50, "reasoning": "x", "missing_skills": []}')],
        usage=MagicMock(input_tokens=100, output_tokens=20),
    )
    match_job_with_claude(
        client=mock_client, model="claude-haiku-4-5",
        cv_summary="cv", job={"title": "t", "description": "d"},
    )
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert "system" not in call_kwargs
    assert "<untrusted_cv>" not in call_kwargs["messages"][0]["content"]
