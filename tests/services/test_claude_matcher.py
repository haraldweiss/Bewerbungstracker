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
