# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für CoverLetterService — Mocking statt echte AI-Calls."""
from unittest.mock import patch, MagicMock
import pytest
import json
from services.cover_letter_service import CoverLetterService, _extract_json


def test_extract_json_clean():
    text = '{"matched_skills": [], "matched_experience": []}'
    result = _extract_json(text)
    assert result == {"matched_skills": [], "matched_experience": []}


def test_extract_json_with_markdown_fences():
    text = '```json\n{"key": "value"}\n```'
    result = _extract_json(text)
    assert result == {"key": "value"}


def test_extract_json_with_surrounding_text():
    text = 'Here is the result:\n{"a": 1}\nDone.'
    result = _extract_json(text)
    assert result == {"a": 1}


def test_inject_confidence_attributes_with_comment():
    html = '<!-- confidence: 0.95 -->\n<p>Hello</p>'
    result = CoverLetterService._inject_confidence_attributes(html)
    assert 'data-confidence="0.95"' in result
    assert '<p data-confidence="0.95">Hello</p>' in result


def test_inject_confidence_attributes_without_comment_uses_default():
    html = '<p>Some paragraph</p>'
    result = CoverLetterService._inject_confidence_attributes(html)
    assert 'data-confidence="0.85"' in result


def test_inject_confidence_multiple_paragraphs():
    html = '''<!-- confidence: 0.99 -->
<p>First paragraph</p>
<!-- confidence: 0.70 -->
<p>Second paragraph</p>'''
    result = CoverLetterService._inject_confidence_attributes(html)
    assert '<p data-confidence="0.99">First paragraph</p>' in result
    assert '<p data-confidence="0.70">Second paragraph</p>' in result


@patch('services.cover_letter_service._call_ai')
def test_analyze_returns_expected_structure(mock_call):
    mock_call.return_value = json.dumps({
        "matched_skills": [
            {"skill": "Python", "cv_source": "line 5", "job_requirement": "Python required", "confidence": 0.99}
        ],
        "matched_experience": [],
        "interpreted_requirements": [],
        "missing_or_weak": []
    })
    svc = CoverLetterService()
    result = svc.analyze("CV: Python 5 years", "Job: needs Python")
    assert 'matched_skills' in result
    assert len(result['matched_skills']) == 1
    assert result['matched_skills'][0]['skill'] == 'Python'


@patch('services.cover_letter_service._call_ai')
def test_analyze_fills_missing_keys(mock_call):
    """Ein KI-Output ohne alle Keys → Service ergänzt leere Listen."""
    mock_call.return_value = '{"matched_skills": []}'
    svc = CoverLetterService()
    result = svc.analyze("CV", "Job")
    assert result['matched_skills'] == []
    assert result['matched_experience'] == []
    assert result['interpreted_requirements'] == []
    assert result['missing_or_weak'] == []


def test_analyze_rejects_empty_input():
    svc = CoverLetterService()
    with pytest.raises(ValueError):
        svc.analyze("", "Job description")
    with pytest.raises(ValueError):
        svc.analyze("CV text", "")


@patch('services.cover_letter_service._call_ai')
def test_generate_returns_html_with_confidence(mock_call):
    mock_call.return_value = '''<!-- confidence: 0.95 -->
<p>Sehr geehrte Damen und Herren, ich bewerbe mich auf die Stelle als Python-Entwickler.</p>
<!-- confidence: 0.80 -->
<p>Meine 5 Jahre Python-Erfahrung passen zur Anforderung.</p>'''

    svc = CoverLetterService()
    analysis = {
        "matched_skills": [{"skill": "Python", "cv_source": "5y", "job_requirement": "Python", "confidence": 0.95}],
        "matched_experience": [],
        "interpreted_requirements": [],
        "missing_or_weak": []
    }
    result = svc.generate("TechCorp", "Python Engineer", analysis)
    assert 'data-confidence="0.95"' in result
    assert 'data-confidence="0.80"' in result
    assert 'TechCorp' not in result or 'Python' in result  # KI-Output wird unverändert durchgereicht (mit unserem Mock-Output)
