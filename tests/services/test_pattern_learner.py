"""Unit-Tests für Pattern-Lerner."""
import pytest
from services.job_sources.pattern_learner import (
    PATTERN_JSON_SCHEMA, validate_pattern_schema,
)
from services.job_sources.pattern_learner import compile_pattern, CompiledPattern


def test_valid_pattern_passes():
    p = {
        "subject_pattern": {
            "prefix_optional": True, "prefix_keywords": ["Neue Stelle"],
            "separator": "bei|at|@",
        },
        "body_card": {
            "url_labels": ["Jobangebot ansehen"],
            "fields_before_url": ["title", "company", "location"],
            "separator_lines_allowed": 5,
        },
        "filters": {
            "title_blacklist": ["Ihre Jobbenachrichtigung"],
            "company_blacklist_separators": ["----"],
        },
    }
    assert validate_pattern_schema(p) == []


def test_invalid_pattern_missing_subject_pattern():
    p = {
        "body_card": {
            "url_labels": ["X"], "fields_before_url": ["title"],
            "separator_lines_allowed": 0,
        },
        "filters": {"title_blacklist": [], "company_blacklist_separators": []},
    }
    errors = validate_pattern_schema(p)
    assert len(errors) >= 1
    assert any("subject_pattern" in e for e in errors)


def test_invalid_pattern_wrong_type():
    p = {
        "subject_pattern": {
            "prefix_optional": "not a bool",  # invalid
            "prefix_keywords": [], "separator": "bei",
        },
        "body_card": {
            "url_labels": ["X"], "fields_before_url": ["title"],
            "separator_lines_allowed": 0,
        },
        "filters": {"title_blacklist": [], "company_blacklist_separators": []},
    }
    assert len(validate_pattern_schema(p)) >= 1


def test_invalid_pattern_extra_field_rejected():
    p = {
        "subject_pattern": {
            "prefix_optional": True, "prefix_keywords": [], "separator": "bei",
        },
        "body_card": {
            "url_labels": ["X"], "fields_before_url": ["title"],
            "separator_lines_allowed": 0,
            "evil_field": "drop table users",
        },
        "filters": {"title_blacklist": [], "company_blacklist_separators": []},
    }
    assert len(validate_pattern_schema(p)) >= 1


def _valid_pattern_dict():
    return {
        "subject_pattern": {
            "prefix_optional": True, "prefix_keywords": ["Neue Stelle", "Job alert"],
            "separator": "bei|at|@",
        },
        "body_card": {
            "url_labels": ["Jobangebot ansehen", "View job"],
            "fields_before_url": ["title", "company", "location"],
            "separator_lines_allowed": 5,
        },
        "filters": {
            "title_blacklist": ["Ihre Jobbenachrichtigung", "Top-Jobs"],
            "company_blacklist_separators": ["----", "===="],
        },
    }


def test_compile_returns_compiled_pattern():
    cp = compile_pattern(_valid_pattern_dict())
    assert isinstance(cp, CompiledPattern)
    assert cp.body_card_re is not None
    assert cp.subject_re is not None
    assert cp.title_blacklist_re is not None


def test_compile_body_card_matches_linkedin_layout():
    cp = compile_pattern(_valid_pattern_dict())
    body = (
        "Senior Cybersecurity Consultant (m,w,d)\r\n"
        "QESTIT DACH\r\n"
        "Deutschland\r\n"
        "Mit Lebenslauf und Profil bewerben\r\n"
        "Jobangebot ansehen: https://www.linkedin.com/comm/jobs/view/4410189303/"
    )
    matches = list(cp.body_card_re.finditer(body))
    assert len(matches) >= 1
    m = matches[0]
    assert "Senior Cybersecurity Consultant" in m.group('title')
    assert "QESTIT DACH" in m.group('company')
    assert "Deutschland" in m.group('location')
    assert "linkedin.com/comm/jobs/view/4410189303" in m.group('url')


def test_compile_subject_optional_prefix():
    cp = compile_pattern(_valid_pattern_dict())
    m = cp.subject_re.match("Senior Engineer bei Acme GmbH")
    assert m and m.group('title') == "Senior Engineer" and m.group('company') == "Acme GmbH"
    m = cp.subject_re.match("Neue Stelle: Junior Dev bei Bcorp")
    assert m


def test_compile_title_blacklist():
    cp = compile_pattern(_valid_pattern_dict())
    assert cp.title_blacklist_re.search("Ihre Jobbenachrichtigung")
    assert cp.title_blacklist_re.search("Top-Jobs für Sie")
    assert not cp.title_blacklist_re.search("Senior Engineer")


from services.job_sources.pattern_learner import validate_pattern


def _sample_mails():
    body_match = (
        "Senior Engineer\r\nAcme GmbH\r\nBerlin\r\n"
        "Jobangebot ansehen: https://www.linkedin.com/comm/jobs/view/123"
    )
    body_nojob = "Random newsletter content with no job structure."
    return [
        {"subject": "Senior Engineer bei Acme GmbH", "body": body_match},
        {"subject": "DevOps bei Bcorp", "body": body_match.replace("Acme", "Bcorp")},
        {"subject": "Frontend bei Ccorp", "body": body_match.replace("Acme", "Ccorp")},
        {"subject": "Random Newsletter", "body": body_nojob},
    ]


def test_validate_counts_hits():
    cp = compile_pattern(_valid_pattern_dict())
    hit_rate, diags = validate_pattern(cp, _sample_mails())
    assert hit_rate == 0.75   # 3 of 4 match
    assert sum(1 for d in diags if d["matched"]) == 3


def test_validate_empty():
    cp = compile_pattern(_valid_pattern_dict())
    hit_rate, diags = validate_pattern(cp, [])
    assert hit_rate == 0.0 and diags == []


def test_validate_missing_body():
    cp = compile_pattern(_valid_pattern_dict())
    hit_rate, _ = validate_pattern(cp, [
        {"subject": "Test", "body": None},
        {"subject": "Test", "body": ""},
    ])
    assert hit_rate == 0.0


def test_validate_respects_title_blacklist():
    """Card that matches body_card_re but title is on blacklist → not counted."""
    cp = compile_pattern(_valid_pattern_dict())
    bad_body = (
        "Ihre Jobbenachrichtigung fuer X\r\n"
        "SomeCompany\r\nBerlin\r\n"
        "Jobangebot ansehen: https://linkedin.com/comm/jobs/view/99"
    )
    hit_rate, diags = validate_pattern(cp, [{"subject": "Test", "body": bad_body}])
    assert hit_rate == 0.0
    assert diags[0]["matched"] is False


def test_validate_counts_single_job_via_subject_fallback():
    """Indeed-Stil: kein body_card, aber Subject 'X bei Y' + URL im Body → Hit."""
    cp = compile_pattern(_valid_pattern_dict())
    indeed_style = [
        {
            "subject": "Senior Engineer bei Acme GmbH",
            "body": "Schau dir https://de.indeed.com/viewjob?jk=abc123 an",
        },
        {
            "subject": "DevOps Engineer bei Bcorp",
            "body": "Bewirb dich: https://de.indeed.com/viewjob?jk=def456",
        },
        # Newsletter ohne Job-Format
        {"subject": "Wochen-Newsletter", "body": "kein job"},
    ]
    hit_rate, diags = validate_pattern(cp, indeed_style)
    # 2 von 3 sollten matchen
    assert hit_rate == pytest.approx(2/3, abs=0.01)
    # Erste 2 via subject-Pfad
    assert diags[0]["via"] == "subject"
    assert diags[1]["via"] == "subject"
    assert diags[2]["matched"] is False
    assert diags[2]["via"] == "none"


from unittest.mock import MagicMock, patch
from services.job_sources.pattern_learner import fetch_sample_mails


def test_fetch_delegates_to_adapter():
    user = MagicMock()
    user.imap_host = "imap.gmail.com"
    user.imap_user = "u@x.de"
    user.decrypted_imap_password = "pw"
    fake_mails = [{"subject": "X", "body": "Y"}] * 10
    with patch(
        "services.job_sources.email_jobs.EmailJobsAdapter._fetch_emails",
        return_value=fake_mails,
    ) as m:
        result = fetch_sample_mails(
            user, platform="linkedin",
            folder="INBOX", lookback_days=30, n=10,
        )
    assert result == fake_mails
    assert m.called


def test_fetch_unknown_platform_raises():
    user = MagicMock()
    with pytest.raises(ValueError, match="Unknown platform"):
        fetch_sample_mails(user, platform="myspace",
                           folder="INBOX", lookback_days=30, n=10)


def test_fetch_missing_credentials_raises():
    user = MagicMock()
    user.imap_host = None  # missing!
    user.imap_user = "u@x.de"
    user.decrypted_imap_password = "pw"
    with pytest.raises(RuntimeError, match="IMAP-Credentials"):
        fetch_sample_mails(user, platform="linkedin",
                           folder="INBOX", lookback_days=30, n=10)


import json as _json
from services.job_sources.pattern_learner import ai_learn_pattern


def test_ai_learn_success(monkeypatch):
    """AI returns valid JSON matching schema → parsed dict returned."""
    valid = _json.dumps(_valid_pattern_dict())
    fake_chat = MagicMock(return_value={
        "content": valid, "provider": "ollama", "model": "qwen2.5",
    })
    monkeypatch.setattr(
        "services.ai_provider_client.AIProviderClient.chat", fake_chat,
    )
    user = MagicMock(id="test-uid", ai_provider="ollama", ai_provider_model="qwen2.5")
    result = ai_learn_pattern(
        user, train_samples=[{"subject": "X", "body": "Y"}], platform="linkedin",
    )
    assert result == _valid_pattern_dict()
    assert fake_chat.called


def test_ai_learn_invalid_json_retries_then_raises(monkeypatch):
    """AI returns invalid JSON → 1 retry, then RuntimeError."""
    fake_chat = MagicMock(return_value={
        "content": "not json at all", "provider": "ollama", "model": "q",
    })
    monkeypatch.setattr(
        "services.ai_provider_client.AIProviderClient.chat", fake_chat,
    )
    user = MagicMock(id="t", ai_provider="ollama", ai_provider_model="q")
    with pytest.raises(RuntimeError, match="AI"):
        ai_learn_pattern(
            user, train_samples=[{"subject": "X", "body": "Y"}], platform="linkedin",
        )
    assert fake_chat.call_count == 2  # initial + 1 retry


def test_ai_learn_normalizes_garbage_to_valid_pattern(monkeypatch):
    """AI returns wrong schema → Normalizer cleant + befuellt mit Defaults.

    Schwache lokale LLMs liefern oft halluzinierte Keys ('footer') oder
    fehlende ('filters'). Normalize-Layer macht daraus ein valides Pattern
    mit safe-Defaults (statt zu rejecten und 2x AI zu verschwenden).
    """
    garbage = _json.dumps({"random": "structure"})
    fake_chat = MagicMock(return_value={
        "content": garbage, "provider": "ollama", "model": "q",
    })
    monkeypatch.setattr(
        "services.ai_provider_client.AIProviderClient.chat", fake_chat,
    )
    user = MagicMock(id="t", ai_provider="ollama", ai_provider_model="q")
    result = ai_learn_pattern(
        user, train_samples=[{"subject": "X", "body": "Y"}], platform="linkedin",
    )
    # Nur 1 AI-Call — Normalize fix das Problem ohne Retry.
    assert fake_chat.call_count == 1
    # Pattern hat alle 3 required keys mit safe defaults.
    assert set(result.keys()) == {"subject_pattern", "body_card", "filters"}
    assert result["subject_pattern"]["prefix_optional"] is True
    assert result["body_card"]["fields_before_url"] == ["title", "company", "location"]
    assert result["filters"]["title_blacklist"] == []


def test_normalize_drops_unknown_top_level_keys():
    """normalize_pattern dropt 'footer' und 'header' aus AI-Output."""
    from services.job_sources.pattern_learner import normalize_pattern
    raw = {
        "subject_pattern": {"prefix_optional": True, "prefix_keywords": [], "separator": "bei"},
        "body_card": {"url_labels": ["X"], "fields_before_url": ["title"], "separator_lines_allowed": 3},
        "filters": {"title_blacklist": [], "company_blacklist_separators": []},
        "footer": "evil",
        "header": {"random": "stuff"},
    }
    out = normalize_pattern(raw)
    assert "footer" not in out
    assert "header" not in out
    assert set(out.keys()) == {"subject_pattern", "body_card", "filters"}


def test_normalize_remaps_fields_synonym():
    """'fields' → 'fields_before_url' (LLM-Synonym)."""
    from services.job_sources.pattern_learner import normalize_pattern
    raw = {
        "subject_pattern": {"prefix_optional": True, "prefix_keywords": [], "separator": "bei"},
        "body_card": {
            "url_labels": ["X"],
            "fields": ["title", "company"],  # LLM hat den falschen Key benutzt
            "separator_lines_allowed": 0,
        },
        "filters": {"title_blacklist": [], "company_blacklist_separators": []},
    }
    out = normalize_pattern(raw)
    assert out["body_card"]["fields_before_url"] == ["title", "company"]
    assert "fields" not in out["body_card"]


def test_ai_learn_strips_markdown_fences(monkeypatch):
    """AI wraps response in ```json fences → still parses correctly."""
    fenced = "```json\n" + _json.dumps(_valid_pattern_dict()) + "\n```"
    fake_chat = MagicMock(return_value={
        "content": fenced, "provider": "ollama", "model": "q",
    })
    monkeypatch.setattr(
        "services.ai_provider_client.AIProviderClient.chat", fake_chat,
    )
    user = MagicMock(id="t", ai_provider="ollama", ai_provider_model="q")
    result = ai_learn_pattern(
        user, train_samples=[{"subject": "X", "body": "Y"}], platform="linkedin",
    )
    assert result == _valid_pattern_dict()
    assert fake_chat.call_count == 1  # success on first try
