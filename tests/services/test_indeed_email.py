# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Unit-Tests für IndeedEmailAdapter — Parser-Pfade ohne echten IMAP-Call."""
from unittest.mock import patch

import pytest

from services.job_sources.indeed_email import (
    IndeedEmailAdapter,
    _decode_mime,
    _extract_body,
    _parse_subject,
    _strip_html,
)


# ── Parser-Helper ──────────────────────────────────────────────────────────


def test_strip_html_removes_tags_and_normalizes_whitespace():
    html = "<p>Hello <b>World</b></p>  <br/>  <span>foo</span>"
    assert _strip_html(html) == "Hello World foo"


def test_strip_html_strips_scripts_and_styles():
    html = "<style>body{color:red}</style>Visible<script>alert(1)</script>"
    assert _strip_html(html) == "Visible"


def test_strip_html_decodes_named_entities():
    assert _strip_html("a&nbsp;b &amp; c &lt;x&gt;") == "a b & c <x>"


def test_decode_mime_passes_plain_text():
    assert _decode_mime("Plain Subject") == "Plain Subject"
    assert _decode_mime("") == ""


def test_decode_mime_decodes_utf8():
    # Encoded "Köln"
    encoded = "=?utf-8?b?S8O2bG4=?="
    assert _decode_mime(encoded) == "Köln"


def test_parse_subject_german_pattern():
    title, company = _parse_subject("Neue Stelle: Senior Python Developer bei TechCorp - Indeed")
    assert title == "Senior Python Developer"
    assert company == "TechCorp"


def test_parse_subject_english_pattern():
    title, company = _parse_subject("New job: Backend Engineer at Acme Inc")
    assert title == "Backend Engineer"
    assert company == "Acme Inc"


def test_parse_subject_at_separator():
    title, company = _parse_subject("Senior Developer @ StartupX")
    assert title == "Senior Developer"
    assert company == "StartupX"


def test_parse_subject_returns_none_on_nonsense():
    title, company = _parse_subject("Random newsletter unrelated")
    assert title is None
    assert company is None


# ── Email-Parsing (kompletter Adapter, _parse_email Methode) ───────────────


def _make_adapter_no_user():
    """Adapter ohne User — für reine Parser-Tests, kein AI-Fallback."""
    return IndeedEmailAdapter(config={}, user=None)


def test_parse_email_extracts_from_subject_and_body_url():
    adapter = _make_adapter_no_user()
    email_data = {
        'message_id': '<abc@indeed.de>',
        'subject': 'Neue Stelle: Senior Python Developer bei TechCorp GmbH',
        'from': 'noreply@indeed.de',
        'date': 'Mon, 12 May 2026 09:00:00 +0200',
        'body': (
            "Wir haben eine neue Stelle für Sie gefunden:\n\n"
            "Stelle: Senior Python Developer\n"
            "Firma: TechCorp GmbH\n"
            "Ort: Berlin\n\n"
            "Jetzt bewerben: https://de.indeed.com/viewjob?jk=abc123xyz&from=alert\n"
        ),
    }
    job = adapter._parse_email(email_data)
    assert job is not None
    assert job.title == "Senior Python Developer"
    assert job.company == "TechCorp GmbH"
    assert job.location == "Berlin"
    assert "indeed.com/viewjob?jk=abc123xyz" in job.url
    assert job.external_id == job.url
    assert job.posted_at is not None


def test_parse_email_falls_back_to_body_when_subject_useless():
    adapter = _make_adapter_no_user()
    email_data = {
        'subject': 'Indeed Job Alert',  # no title/company pattern
        'body': (
            "Stelle: Data Engineer\n"
            "Firma: DataCo\n"
            "Ort: München\n"
            "https://de.indeed.com/viewjob?jk=xyz789\n"
        ),
        'message_id': '<m1>',
        'date': '',
        'from': '',
    }
    job = adapter._parse_email(email_data)
    assert job is not None
    assert job.title == "Data Engineer"
    assert job.company == "DataCo"
    assert job.location == "München"


def test_parse_email_returns_none_without_url():
    adapter = _make_adapter_no_user()
    email_data = {
        'subject': 'Neue Stelle: Foo bei Bar',
        'body': 'Some text without any URL.',
        'message_id': '<m1>',
        'date': '',
        'from': '',
    }
    assert adapter._parse_email(email_data) is None


def test_parse_email_returns_none_without_title():
    adapter = _make_adapter_no_user()
    email_data = {
        'subject': 'newsletter',
        'body': 'Visit https://de.indeed.com/viewjob?jk=abc but no title info.',
        'message_id': '<m1>',
        'date': '',
        'from': '',
    }
    assert adapter._parse_email(email_data) is None


def test_parse_email_truncates_long_fields():
    adapter = _make_adapter_no_user()
    long_company = "A" * 300
    email_data = {
        'subject': f"New job: My Title at {long_company}",
        'body': "https://de.indeed.com/viewjob?jk=abc",
        'message_id': '',
        'date': '',
        'from': '',
    }
    job = adapter._parse_email(email_data)
    assert job is not None
    assert job.company is not None
    assert len(job.company) <= 255


# ── Fetch-Validation (ohne IMAP) ───────────────────────────────────────────


def test_fetch_raises_without_user():
    adapter = IndeedEmailAdapter(config={'folder': 'Indeed'}, user=None)
    with pytest.raises(RuntimeError, match="User-Kontext"):
        adapter.fetch()


def test_fetch_raises_without_imap_credentials():
    class FakeUser:
        imap_host = None
        imap_user = None
        decrypted_imap_password = None
    adapter = IndeedEmailAdapter(config={'folder': 'Indeed'}, user=FakeUser())
    with pytest.raises(RuntimeError, match="IMAP-Credentials"):
        adapter.fetch()


def test_fetch_raises_on_invalid_folder_name():
    class FakeUser:
        imap_host = 'imap.example.com'
        imap_user = 'me@example.com'
        decrypted_imap_password = 'pw'
    adapter = IndeedEmailAdapter(
        config={'folder': 'bad\r\nfolder; DELETE *'},
        user=FakeUser(),
    )
    with pytest.raises(ValueError, match="Ordner-Name"):
        adapter.fetch()


# ── AI-Fallback (mocked) ───────────────────────────────────────────────────


def test_ai_fallback_called_when_fields_missing(monkeypatch):
    """Wenn Regex Title/Company/URL nicht findet, soll AI-Fallback greifen."""
    class FakeUser:
        id = 'user123'
        imap_host = 'imap.example.com'
        imap_user = 'u'
        decrypted_imap_password = 'p'
        def get_model_for(self, _feature):
            return ('ollama', 'llama2')
        def get_backup_config(self):
            return None

    adapter = IndeedEmailAdapter(config={}, user=FakeUser())

    def fake_ai_extract(user, subject, body):
        return {
            'title': 'AI Title',
            'company': 'AI Company',
            'location': 'AI Location',
            'url': 'https://de.indeed.com/viewjob?jk=ai_extracted',
        }

    monkeypatch.setattr(
        'services.job_sources.indeed_email._ai_extract',
        fake_ai_extract,
    )

    # Subject ohne klares Pattern, ABER von indeed → looks_like_indeed=True
    # → AI-Fallback wird getriggert (Pre-Filter passes)
    email_data = {
        'subject': 'Indeed weekly digest',
        'body': 'no obvious link or fields here',
        'message_id': '',
        'date': '',
        'from': 'noreply@indeed.com',
    }
    job = adapter._parse_email(email_data)
    assert job is not None
    assert job.title == 'AI Title'
    assert job.company == 'AI Company'
    assert job.location == 'AI Location'
    assert 'ai_extracted' in job.url


# ── parse_emails (Apps-Script-Mode) ────────────────────────────────────────


def test_parse_emails_accepts_external_email_list():
    adapter = _make_adapter_no_user()
    emails = [
        {
            'subject': 'Neue Stelle: Backend Engineer bei DataCorp',
            'body': 'Body text. https://de.indeed.com/viewjob?jk=apps_1',
            'from': 'noreply@indeed.com',
            'date': '2026-05-15T08:00:00Z',
            'id': 'msg_apps_1',
        },
        {
            'subject': 'Neue Stelle: Frontend Dev bei UICorp',
            'body': 'Visit https://de.indeed.com/viewjob?jk=apps_2 to apply',
            'from': 'jobs@indeed.com',
            'date': '2026-05-16T08:00:00Z',
        },
    ]
    jobs = adapter.parse_emails(emails)
    assert len(jobs) == 2
    assert jobs[0].title == 'Backend Engineer'
    assert jobs[0].company == 'DataCorp'
    assert 'apps_1' in jobs[0].url
    assert jobs[1].title == 'Frontend Dev'
    assert jobs[1].company == 'UICorp'


def test_parse_emails_falls_back_to_snippet_field_if_no_body():
    adapter = _make_adapter_no_user()
    emails = [{
        'subject': 'Neue Stelle: Test at TestCo',
        'snippet': 'https://de.indeed.com/viewjob?jk=snip_only',
        'from': 'x@indeed.com',
    }]
    jobs = adapter.parse_emails(emails)
    assert len(jobs) == 1
    assert 'snip_only' in jobs[0].url


def test_parse_emails_skips_malformed_entries():
    adapter = _make_adapter_no_user()
    emails = [
        "not a dict",
        None,
        {'subject': 'rubbish', 'body': 'no url no title'},  # parse fails → None
        {'subject': 'Job: A at B', 'body': 'https://de.indeed.com/viewjob?jk=valid'},
    ]
    jobs = adapter.parse_emails(emails)
    assert len(jobs) == 1
    assert 'valid' in jobs[0].url


def test_parse_emails_rejects_non_list_input():
    adapter = _make_adapter_no_user()
    with pytest.raises(ValueError, match="Liste"):
        adapter.parse_emails("not a list")


def test_parse_emails_works_without_user_context():
    """parse_emails braucht keinen User (kein IMAP-Connect). AI-Fallback
    wird nur bei user!=None aktiv."""
    adapter = IndeedEmailAdapter(config={}, user=None)
    jobs = adapter.parse_emails([{
        'subject': 'Neue Stelle: Dev at Corp',
        'body': 'https://de.indeed.com/viewjob?jk=nouser',
    }])
    assert len(jobs) == 1


def test_ai_fallback_skipped_for_non_indeed_emails(monkeypatch):
    """Random Newsletter ohne Indeed-Marker → kein AI-Call (Cost-Schutz)."""
    class FakeUser:
        id = 'u'
        imap_host = 'x'; imap_user = 'x'; decrypted_imap_password = 'x'
        def get_model_for(self, _): return ('ollama', 'llama2')
        def get_backup_config(self): return None

    adapter = IndeedEmailAdapter(config={}, user=FakeUser())
    called = {'count': 0}

    def fake_ai(user, subject, body):
        called['count'] += 1
        return {'title': 'X', 'company': 'Y', 'location': None, 'url': 'https://de.indeed.com/viewjob?jk=ai'}

    monkeypatch.setattr('services.job_sources.indeed_email._ai_extract', fake_ai)

    # Newsletter ohne Indeed-Bezug → kein AI-Call, return None
    result = adapter._parse_email({
        'subject': 'Newsletter vom April',
        'body': 'Lots of text. No indeed link. No job marker.',
        'from': 'newsletter@example.com',
    })
    assert result is None
    assert called['count'] == 0


def test_ai_fallback_budget_caps_calls(monkeypatch):
    """Bei vielen Job-Mails ohne Regex-Match: maximal AI_FALLBACK_BUDGET
    AI-Calls — verhindert Worker-Timeout bei großen Batches."""
    class FakeUser:
        id = 'u'
        imap_host = 'x'; imap_user = 'x'; decrypted_imap_password = 'x'
        def get_model_for(self, _): return ('ollama', 'llama2')
        def get_backup_config(self): return None

    adapter = IndeedEmailAdapter(config={}, user=FakeUser())
    adapter.AI_FALLBACK_BUDGET = 3  # für Test runter

    call_count = {'n': 0}
    def fake_ai(user, subject, body):
        call_count['n'] += 1
        return {'title': 'T', 'company': 'C', 'location': None,
                'url': 'https://de.indeed.com/viewjob?jk=ai' + str(call_count['n'])}
    monkeypatch.setattr('services.job_sources.indeed_email._ai_extract', fake_ai)

    # 10 Indeed-Mails ohne klares Subject → würden alle AI triggern
    emails = [
        {'subject': f'random subject {i}',
         'body': 'irrelevant',
         'from': 'jobs@indeed.com'}  # indeed im from → looks_like_indeed=True
        for i in range(10)
    ]
    jobs = adapter.parse_emails(emails)
    assert call_count['n'] == 3  # nur Budget-viele AI-Calls
    assert len(jobs) == 3  # nur die ersten 3 bekommen AI → haben Title+URL


def test_ai_budget_resets_between_runs():
    class FakeUser:
        id = 'u'
        imap_host = 'x'; imap_user = 'x'; decrypted_imap_password = 'x'
        def get_model_for(self, _): return ('ollama', 'llama2')
        def get_backup_config(self): return None

    adapter = IndeedEmailAdapter(config={}, user=FakeUser())
    adapter._ai_calls_used = 999
    adapter.parse_emails([])  # leerer Lauf
    assert adapter._ai_calls_used == 0


def test_ai_fallback_only_fills_missing_fields(monkeypatch):
    """Wenn Regex Title findet, soll AI nicht überschreiben."""
    class FakeUser:
        id = 'user123'
        imap_host = 'imap.example.com'
        imap_user = 'u'
        decrypted_imap_password = 'p'
        def get_model_for(self, _feature):
            return ('ollama', 'llama2')
        def get_backup_config(self):
            return None

    adapter = IndeedEmailAdapter(config={}, user=FakeUser())

    monkeypatch.setattr(
        'services.job_sources.indeed_email._ai_extract',
        lambda u, s, b: {
            'title': 'AI Override Title',
            'company': 'AI Override Co',
            'location': 'AI Loc',
            'url': 'https://de.indeed.com/viewjob?jk=ai',
        },
    )

    email_data = {
        'subject': 'New job: Real Title at Real Co',
        'body': 'https://de.indeed.com/viewjob?jk=regex_match',
        'message_id': '',
        'date': '',
        'from': '',
    }
    job = adapter._parse_email(email_data)
    assert job is not None
    # Regex-matched values must NOT be overridden by AI
    assert job.title == 'Real Title'
    assert job.company == 'Real Co'
    assert 'regex_match' in job.url
