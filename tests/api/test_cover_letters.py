# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für /api/cover-letters Endpoints."""
import json
import pytest
from unittest.mock import patch, MagicMock
from database import db
from models import CoverLetter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cl(user, **kwargs) -> CoverLetter:
    """Erstellt einen CoverLetter direkt in der DB (kein HTTP)."""
    defaults = dict(
        user_id=user.id,
        job_title='Python Developer',
        company_name='ACME GmbH',
        job_description='Wir suchen einen erfahrenen Python-Entwickler für unser Team.',
        tone='professional',
        length='medium',
        focus='balanced',
        status='draft',
    )
    defaults.update(kwargs)
    cl = CoverLetter(**defaults)
    db.session.add(cl)
    db.session.commit()
    return cl


# ---------------------------------------------------------------------------
# POST /api/cover-letters/create
# ---------------------------------------------------------------------------

def test_create_cover_letter_valid(client, auth_headers):
    """Valider Request → 201, Draft-Status, keine content-Felder in Antwort."""
    headers, user = auth_headers
    r = client.post('/api/cover-letters/create', headers=headers, json={
        'job_title': 'Software Engineer',
        'company_name': 'TechCorp',
        'job_description': 'Wir suchen einen Software-Ingenieur mit Python-Erfahrung.',
    })
    assert r.status_code == 201
    body = r.get_json()
    assert body['job_title'] == 'Software Engineer'
    assert body['company_name'] == 'TechCorp'
    assert body['status'] == 'draft'
    # include_content=False: content nicht in Listenansicht
    assert 'content' not in body
    assert 'analysis' not in body

    # In DB persistiert
    cl = CoverLetter.query.filter_by(user_id=user.id).first()
    assert cl is not None
    assert cl.job_title == 'Software Engineer'


def test_create_cover_letter_with_config(client, auth_headers):
    """Optionale tone/length/focus werden korrekt gespeichert."""
    headers, _ = auth_headers
    r = client.post('/api/cover-letters/create', headers=headers, json={
        'job_title': 'DevOps Engineer',
        'company_name': 'StartupX',
        'job_description': 'CI/CD, Kubernetes, Docker — wir brauchen Verstärkung.',
        'tone': 'technical',
        'length': 'short',
        'focus': 'technical',
    })
    assert r.status_code == 201
    body = r.get_json()
    assert body['tone'] == 'technical'
    assert body['length'] == 'short'
    assert body['focus'] == 'technical'


def test_create_cover_letter_missing_job_title(client, auth_headers):
    """Fehlendes job_title → 400."""
    headers, _ = auth_headers
    r = client.post('/api/cover-letters/create', headers=headers, json={
        'company_name': 'TechCorp',
        'job_description': 'Wir suchen einen Entwickler.',
    })
    assert r.status_code == 400
    assert 'job_title' in r.get_json()['error']


def test_create_cover_letter_missing_company(client, auth_headers):
    """Fehlendes company_name → 400."""
    headers, _ = auth_headers
    r = client.post('/api/cover-letters/create', headers=headers, json={
        'job_title': 'Developer',
        'job_description': 'Wir suchen einen Entwickler.',
    })
    assert r.status_code == 400
    assert 'company_name' in r.get_json()['error']


def test_create_cover_letter_missing_description(client, auth_headers):
    """Fehlendes job_description → 400."""
    headers, _ = auth_headers
    r = client.post('/api/cover-letters/create', headers=headers, json={
        'job_title': 'Developer',
        'company_name': 'TechCorp',
    })
    assert r.status_code == 400
    assert 'job_description' in r.get_json()['error']


def test_create_cover_letter_invalid_tone(client, auth_headers):
    """Ungültiger tone → 400 mit Fehlermeldung."""
    headers, _ = auth_headers
    r = client.post('/api/cover-letters/create', headers=headers, json={
        'job_title': 'Developer',
        'company_name': 'TechCorp',
        'job_description': 'Wir suchen einen Entwickler.',
        'tone': 'aggressive',
    })
    assert r.status_code == 400
    assert 'tone' in r.get_json()['error']


def test_create_cover_letter_invalid_length(client, auth_headers):
    """Ungültige length → 400."""
    headers, _ = auth_headers
    r = client.post('/api/cover-letters/create', headers=headers, json={
        'job_title': 'Developer',
        'company_name': 'TechCorp',
        'job_description': 'Wir suchen einen Entwickler.',
        'length': 'extra-long',
    })
    assert r.status_code == 400
    assert 'length' in r.get_json()['error']


def test_create_cover_letter_invalid_focus(client, auth_headers):
    """Ungültiger focus → 400."""
    headers, _ = auth_headers
    r = client.post('/api/cover-letters/create', headers=headers, json={
        'job_title': 'Developer',
        'company_name': 'TechCorp',
        'job_description': 'Wir suchen einen Entwickler.',
        'focus': 'sales',
    })
    assert r.status_code == 400
    assert 'focus' in r.get_json()['error']


def test_create_cover_letter_requires_auth(client):
    """Ohne Token → 401."""
    r = client.post('/api/cover-letters/create', json={
        'job_title': 'Developer',
        'company_name': 'TechCorp',
        'job_description': 'Wir suchen einen Entwickler.',
    })
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/cover-letters/<id>
# ---------------------------------------------------------------------------

def test_get_cover_letter(client, auth_headers):
    """GET /<id> gibt serialisierten Cover Letter zurück."""
    headers, user = auth_headers
    cl = _make_cl(user, content='<p>Test-Content</p>',
                  analysis_json='{"matched_skills": []}')

    r = client.get(f'/api/cover-letters/{cl.id}', headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body['id'] == cl.id
    assert body['job_title'] == cl.job_title
    assert body['company_name'] == cl.company_name
    assert body['status'] == 'draft'
    # include_content=True bei Detail-Ansicht
    assert 'content' in body
    assert body['content'] == '<p>Test-Content</p>'
    assert 'analysis' in body
    assert body['analysis'] == {'matched_skills': []}


def test_get_cover_letter_not_found(client, auth_headers):
    """Nicht-existente ID → 404."""
    headers, _ = auth_headers
    r = client.get('/api/cover-letters/nonexistent-id', headers=headers)
    assert r.status_code == 404


def test_get_cover_letter_other_user(client, auth_headers, user_factory):
    """Cover Letter eines anderen Users → 404 (User-Isolation)."""
    headers, _ = auth_headers
    other_user = user_factory()
    cl = _make_cl(other_user)

    r = client.get(f'/api/cover-letters/{cl.id}', headers=headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/cover-letters/
# ---------------------------------------------------------------------------

def test_list_cover_letters(client, auth_headers):
    """GET / gibt Liste eigener Cover Letters zurück."""
    headers, user = auth_headers
    _make_cl(user, job_title='Job A')
    _make_cl(user, job_title='Job B')

    r = client.get('/api/cover-letters/', headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert 'cover_letters' in body
    assert len(body['cover_letters']) == 2
    titles = [cl['job_title'] for cl in body['cover_letters']]
    assert 'Job A' in titles
    assert 'Job B' in titles


def test_list_cover_letters_user_isolation(client, auth_headers, user_factory):
    """GET / gibt nur eigene Cover Letters zurück, nicht die anderer User."""
    headers, user = auth_headers
    other_user = user_factory()
    _make_cl(user, job_title='Mein Job')
    _make_cl(other_user, job_title='Fremder Job')

    r = client.get('/api/cover-letters/', headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    titles = [cl['job_title'] for cl in body['cover_letters']]
    assert 'Mein Job' in titles
    assert 'Fremder Job' not in titles


def test_list_cover_letters_empty(client, auth_headers):
    """GET / mit keinen Cover Letters → leere Liste."""
    headers, _ = auth_headers
    r = client.get('/api/cover-letters/', headers=headers)
    assert r.status_code == 200
    assert r.get_json()['cover_letters'] == []


def test_list_cover_letters_no_content_fields(client, auth_headers):
    """Listenantwort enthält keine content/analysis/job_description Felder."""
    headers, user = auth_headers
    _make_cl(user, content='<p>Langer Text</p>',
             analysis_json='{"matched_skills": [{"skill": "Python"}]}')

    r = client.get('/api/cover-letters/', headers=headers)
    assert r.status_code == 200
    cl_list = r.get_json()['cover_letters']
    assert len(cl_list) == 1
    assert 'content' not in cl_list[0]
    assert 'analysis' not in cl_list[0]
    assert 'job_description' not in cl_list[0]


# ---------------------------------------------------------------------------
# PATCH /api/cover-letters/<id>
# ---------------------------------------------------------------------------

def test_update_cover_letter_content(client, auth_headers):
    """PATCH content → 200, neuer Inhalt gespeichert."""
    headers, user = auth_headers
    cl = _make_cl(user)

    r = client.patch(f'/api/cover-letters/{cl.id}', headers=headers, json={
        'content': '<p data-confidence="0.9">Neuer Inhalt</p>',
    })
    assert r.status_code == 200
    body = r.get_json()
    assert body['content'] == '<p data-confidence="0.9">Neuer Inhalt</p>'

    db.session.refresh(cl)
    assert cl.content == '<p data-confidence="0.9">Neuer Inhalt</p>'


def test_update_cover_letter_status(client, auth_headers):
    """PATCH status → 200, Status aktualisiert."""
    headers, user = auth_headers
    cl = _make_cl(user, status='generated')

    r = client.patch(f'/api/cover-letters/{cl.id}', headers=headers, json={
        'status': 'finalized',
    })
    assert r.status_code == 200
    assert r.get_json()['status'] == 'finalized'


def test_update_cover_letter_invalid_status(client, auth_headers):
    """Ungültiger Status → 400."""
    headers, user = auth_headers
    cl = _make_cl(user)

    r = client.patch(f'/api/cover-letters/{cl.id}', headers=headers, json={
        'status': 'rejected',
    })
    assert r.status_code == 400
    assert 'status' in r.get_json()['error']


def test_update_cover_letter_config_fields(client, auth_headers):
    """PATCH tone/length/focus → 200, Felder aktualisiert."""
    headers, user = auth_headers
    cl = _make_cl(user)

    r = client.patch(f'/api/cover-letters/{cl.id}', headers=headers, json={
        'tone': 'casual',
        'length': 'long',
        'focus': 'projects',
    })
    assert r.status_code == 200
    body = r.get_json()
    assert body['tone'] == 'casual'
    assert body['length'] == 'long'
    assert body['focus'] == 'projects'


def test_update_cover_letter_not_found(client, auth_headers):
    """PATCH auf nicht-existente ID → 404."""
    headers, _ = auth_headers
    r = client.patch('/api/cover-letters/doesnotexist', headers=headers, json={
        'status': 'finalized',
    })
    assert r.status_code == 404


def test_update_cover_letter_other_user(client, auth_headers, user_factory):
    """PATCH auf Cover Letter eines anderen Users → 404 (User-Isolation)."""
    headers, _ = auth_headers
    other_user = user_factory()
    cl = _make_cl(other_user)

    r = client.patch(f'/api/cover-letters/{cl.id}', headers=headers, json={
        'status': 'finalized',
    })
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/cover-letters/<id>
# ---------------------------------------------------------------------------

def test_delete_cover_letter(client, auth_headers):
    """DELETE /<id> → 200, aus DB entfernt."""
    headers, user = auth_headers
    cl = _make_cl(user)
    cl_id = cl.id

    r = client.delete(f'/api/cover-letters/{cl_id}', headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body['status'] == 'deleted'
    assert body['id'] == cl_id

    assert CoverLetter.query.get(cl_id) is None


def test_delete_cover_letter_not_found(client, auth_headers):
    """DELETE auf nicht-existente ID → 404."""
    headers, _ = auth_headers
    r = client.delete('/api/cover-letters/nonexistent', headers=headers)
    assert r.status_code == 404


def test_delete_cover_letter_other_user(client, auth_headers, user_factory):
    """DELETE auf Cover Letter eines anderen Users → 404."""
    headers, _ = auth_headers
    other_user = user_factory()
    cl = _make_cl(other_user)

    r = client.delete(f'/api/cover-letters/{cl.id}', headers=headers)
    assert r.status_code == 404
    # Noch in DB
    assert CoverLetter.query.get(cl.id) is not None


# ---------------------------------------------------------------------------
# POST /api/cover-letters/<id>/generate
# ---------------------------------------------------------------------------

def test_generate_without_cv_text(client, auth_headers):
    """POST /<id>/generate ohne cv_text → 400."""
    headers, user = auth_headers
    cl = _make_cl(user)

    r = client.post(f'/api/cover-letters/{cl.id}/generate', headers=headers, json={})
    assert r.status_code == 400
    assert 'cv_text' in r.get_json()['error']


def test_generate_cover_letter_not_found(client, auth_headers):
    """POST /nonexistent/generate → 404."""
    headers, _ = auth_headers
    r = client.post('/api/cover-letters/nonexistent/generate', headers=headers, json={
        'cv_text': 'Mein Lebenslauf...',
    })
    assert r.status_code == 404


def test_generate_other_user_cover_letter(client, auth_headers, user_factory):
    """POST generate auf Cover Letter eines anderen Users → 404."""
    headers, _ = auth_headers
    other_user = user_factory()
    cl = _make_cl(other_user)

    r = client.post(f'/api/cover-letters/{cl.id}/generate', headers=headers, json={
        'cv_text': 'Mein Lebenslauf...',
    })
    assert r.status_code == 404


def test_generate_success(client, auth_headers):
    """POST /<id>/generate mit Mock-Service → 200, content + analysis gespeichert."""
    headers, user = auth_headers
    long_desc = 'Wir suchen einen Python-Entwickler mit Erfahrung in Flask, SQLAlchemy und REST-APIs. ' * 3
    cl = _make_cl(user, job_description=long_desc)

    fake_analysis = {
        'matched_skills': [{'skill': 'Python', 'confidence': 0.95}],
        'matched_experience': [],
        'interpreted_requirements': [],
        'missing_or_weak': [],
    }
    fake_content = '<p data-confidence="0.95">Sehr geehrte Damen und Herren...</p>'

    with patch('api.cover_letters.CoverLetterService') as MockSvc:
        instance = MockSvc.return_value
        instance.analyze.return_value = fake_analysis
        instance.generate.return_value = fake_content

        r = client.post(f'/api/cover-letters/{cl.id}/generate', headers=headers, json={
            'cv_text': 'Python-Entwickler mit 5 Jahren Erfahrung in Flask und REST-APIs.',
        })

    assert r.status_code == 200
    body = r.get_json()
    assert body['status'] == 'generated'
    assert body['content'] == fake_content
    assert body['analysis'] == fake_analysis

    db.session.refresh(cl)
    assert cl.content == fake_content
    assert cl.status == 'generated'
    assert cl.analysis_json is not None


def test_generate_runtime_error_returns_503(client, auth_headers):
    """RuntimeError in Service → 503."""
    headers, user = auth_headers
    long_desc = 'Wir suchen einen Python-Entwickler. ' * 5
    cl = _make_cl(user, job_description=long_desc)

    with patch('api.cover_letters.CoverLetterService') as MockSvc:
        instance = MockSvc.return_value
        instance.analyze.side_effect = RuntimeError('AI-Service nicht erreichbar')

        r = client.post(f'/api/cover-letters/{cl.id}/generate', headers=headers, json={
            'cv_text': 'Erfahrener Entwickler.',
        })

    assert r.status_code == 503
    assert 'AI-Service' in r.get_json()['error']


def test_generate_short_description_returns_400(client, auth_headers):
    """Zu kurze job_description (< 50 Zeichen) → 400."""
    headers, user = auth_headers
    cl = _make_cl(user, job_description='Kurz.')

    r = client.post(f'/api/cover-letters/{cl.id}/generate', headers=headers, json={
        'cv_text': 'Erfahrener Entwickler.',
    })
    assert r.status_code == 400
    assert 'Stellenbeschreibung' in r.get_json()['error']


# ---------------------------------------------------------------------------
# POST /api/cover-letters/<id>/export
# ---------------------------------------------------------------------------

def test_export_without_content(client, auth_headers):
    """Export ohne Content (nur Draft) → 400."""
    headers, user = auth_headers
    cl = _make_cl(user)  # content=None

    r = client.post(f'/api/cover-letters/{cl.id}/export', headers=headers, json={
        'format': 'pdf',
    })
    assert r.status_code == 400
    assert 'Inhalt' in r.get_json()['error']


def test_export_not_found(client, auth_headers):
    """Export von nicht-existenter ID → 404."""
    headers, _ = auth_headers
    r = client.post('/api/cover-letters/nonexistent/export', headers=headers, json={
        'format': 'pdf',
    })
    assert r.status_code == 404


def test_export_invalid_format(client, auth_headers):
    """Ungültiges Format → 400."""
    headers, user = auth_headers
    cl = _make_cl(user, content='<p>Anschreiben</p>')

    r = client.post(f'/api/cover-letters/{cl.id}/export', headers=headers, json={
        'format': 'txt',
    })
    assert r.status_code == 400
    assert 'format' in r.get_json()['error']


def test_export_pdf_success(client, auth_headers):
    """Export als PDF mit Mock-ExportService → 200, binary response."""
    headers, user = auth_headers
    cl = _make_cl(user, content='<p>Sehr geehrte Damen und Herren...</p>',
                  status='generated')
    fake_pdf_bytes = b'%PDF-1.4 fake pdf content'

    with patch('api.cover_letters.ExportService') as MockExp:
        instance = MockExp.return_value
        instance.to_pdf.return_value = fake_pdf_bytes

        r = client.post(f'/api/cover-letters/{cl.id}/export', headers=headers, json={
            'format': 'pdf',
            'applicant_name': 'Max Mustermann',
        })

    assert r.status_code == 200
    assert r.content_type == 'application/pdf'
    assert r.data == fake_pdf_bytes

    # exported_at gesetzt
    db.session.refresh(cl)
    assert cl.exported_at is not None


def test_export_docx_success(client, auth_headers):
    """Export als DOCX mit Mock-ExportService → 200, DOCX content-type."""
    headers, user = auth_headers
    cl = _make_cl(user, content='<p>Sehr geehrte Damen und Herren...</p>',
                  status='generated')
    fake_docx_bytes = b'PK\x03\x04fake docx zip content'

    with patch('api.cover_letters.ExportService') as MockExp:
        instance = MockExp.return_value
        instance.to_docx.return_value = fake_docx_bytes

        r = client.post(f'/api/cover-letters/{cl.id}/export', headers=headers, json={
            'format': 'docx',
        })

    assert r.status_code == 200
    assert 'wordprocessingml' in r.content_type
    assert r.data == fake_docx_bytes


def test_export_other_user(client, auth_headers, user_factory):
    """Export von Cover Letter eines anderen Users → 404."""
    headers, _ = auth_headers
    other_user = user_factory()
    cl = _make_cl(other_user, content='<p>Anschreiben</p>')

    r = client.post(f'/api/cover-letters/{cl.id}/export', headers=headers, json={
        'format': 'pdf',
    })
    assert r.status_code == 404


def test_export_import_error_returns_503(client, auth_headers):
    """ImportError (fehlende Library) → 503."""
    headers, user = auth_headers
    cl = _make_cl(user, content='<p>Anschreiben</p>')

    with patch('api.cover_letters.ExportService') as MockExp:
        instance = MockExp.return_value
        instance.to_pdf.side_effect = ImportError('reportlab not installed')

        r = client.post(f'/api/cover-letters/{cl.id}/export', headers=headers, json={
            'format': 'pdf',
        })

    assert r.status_code == 503
    assert 'Library' in r.get_json()['error']


def test_generate_uses_cover_letter_override(client, auth_header, db_session):
    """Wenn User feature_model_overrides für cover_letter gesetzt hat,
    wird der Override genutzt statt user.ai_provider."""
    import json as _j
    from unittest.mock import patch, MagicMock
    from models import CoverLetter

    headers, user = auth_header
    user.ai_provider = 'ollama'
    user.ai_provider_model = 'mistral-nemo:12b'
    user.feature_model_overrides = _j.dumps({
        'cover_letter': {'provider': 'claude', 'model': 'claude-haiku-4-5-20251001'},
    })
    db_session.commit()

    cl = CoverLetter(
        user_id=user.id,
        job_title='Engineer', company_name='X',
        job_description='Wir suchen einen erfahrenen Senior Engineer mit Python und Cloud Skills, langfristig.',
        tone='professional', length='medium', focus='balanced',
        status='draft',
    )
    db_session.add(cl); db_session.commit()

    fake_analysis = {'matched_skills': [], 'matched_experience': [],
                     'interpreted_requirements': [], 'missing_or_weak': []}
    fake_content = '<!-- confidence: 0.9 -->\n<p>Test</p>'

    with patch('api.cover_letters.CoverLetterService') as MockSvc:
        instance = MockSvc.return_value
        instance.analyze.return_value = fake_analysis
        instance.generate.return_value = fake_content

        r = client.post(f'/api/cover-letters/{cl.id}/generate',
                        json={'cv_text': 'Python Dev 5y'}, headers=headers)
        assert r.status_code == 200

        call_kwargs = instance.analyze.call_args.kwargs
        assert call_kwargs.get('provider') == 'claude'
        assert call_kwargs.get('model') == 'claude-haiku-4-5-20251001'

        gen_kwargs = instance.generate.call_args.kwargs
        assert gen_kwargs.get('provider') == 'claude'
        assert gen_kwargs.get('model') == 'claude-haiku-4-5-20251001'
