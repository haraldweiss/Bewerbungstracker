# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from services.job_matching.claude_matcher import MatchResult
from services.job_matching.claude_utils import (
    _parse_match_response, _retry_backoff_hours, _result_is_content_failure,
    MATCH_MAX_EVAL_ATTEMPTS, MATCH_OLLAMA_FALLBACK_MODEL,
)
import services.job_matching.claude_utils as cu


def test_parse_invalid_json_sets_failed_flag():
    r = _parse_match_response("not json at all", 100, 20)
    assert r.failed is True
    assert r.score == 0


def test_parse_valid_score_zero_is_not_failed():
    r = _parse_match_response('{"score": 0, "reasoning": "kein Fit", "missing_skills": []}', 100, 20)
    assert r.failed is False
    assert r.score == 0


def test_backoff_curve():
    assert _retry_backoff_hours(1) == 1
    assert _retry_backoff_hours(2) == 2
    assert _retry_backoff_hours(3) == 4
    assert _retry_backoff_hours(4) == 8
    assert _retry_backoff_hours(5) == 12   # gekappt


def test_content_failure_detection():
    assert _result_is_content_failure(_parse_match_response("xx", 1, 1)) is True
    ok = MatchResult(score=42, reasoning="ok", missing_skills=[], tokens_in=1, tokens_out=1)
    assert _result_is_content_failure(ok) is False


def test_constants_defaults():
    assert MATCH_MAX_EVAL_ATTEMPTS == 5
    assert MATCH_OLLAMA_FALLBACK_MODEL == "gemma4:12b"


# ----- Task 4: Ollama-Fallback-Kette + Failure-Handling -----

def _resp(text, via='opencode', fallback_used=False, model='deepseek-v4-flash-free'):
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
        via=via, fallback_used=fallback_used, model=model)


class _FakeClient:
    """chat() liefert je nach provider-Argument eine vorprogrammierte Antwort."""
    def __init__(self, by_provider):
        self.by_provider = by_provider
        self.calls = []

    def chat(self, *, user_id, provider, model, messages, max_tokens, **kw):
        self.calls.append(provider)
        r = self.by_provider[provider]
        if isinstance(r, Exception):
            raise r
        return r() if callable(r) else r


def _make_match_and_user(db_session, user_factory):
    from models import RawJob, JobMatch, JobSource
    u = user_factory(ai_provider='opencode', ai_provider_model='deepseek-v4-flash-free')
    src = JobSource(name='test', type='rss', config='{}', enabled=True, crawl_interval_min=60)
    db_session.add(src); db_session.flush()
    raw = RawJob(source_id=src.id, external_id='e1', title='IT Admin',
                 description='Linux, Netzwerk', location='Berlin', url='http://x')
    db_session.add(raw); db_session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=u.id, prefilter_score=20.0,
                 match_score=None, status='new', eval_attempts=0)
    db_session.add(m); db_session.flush()
    return u, raw, m


def test_ollama_fallback_succeeds_on_opencode_prose(app, db_session, user_factory):
    u, raw, m = _make_match_and_user(db_session, user_factory)
    fake = _FakeClient({
        'opencode': _resp('Hier meine Einschätzung in Prosa, kein JSON.'),
        'ollama': _resp('{"score": 73, "reasoning": "passt", "missing_skills": []}',
                        via='ollama', model='gemma4:12b'),
    })
    with patch.object(cu.ai_provider_client, 'get_client', return_value=fake), \
         patch.object(cu, '_summarize_description', side_effect=lambda *a, **k: raw.description):
        ok = cu._run_match_via_service(u, m, raw, 'CV', 'opencode', 'deepseek-v4-flash-free')
    assert ok is True
    assert m.match_score == 73
    assert m.eval_attempts == 0
    assert 'ollama' in fake.calls


def test_content_failure_increments_attempts_when_ollama_also_prose(app, db_session, user_factory):
    u, raw, m = _make_match_and_user(db_session, user_factory)
    fake = _FakeClient({
        'opencode': _resp('Prosa'),
        'ollama': _resp('Auch Prosa', via='ollama'),
    })
    with patch.object(cu.ai_provider_client, 'get_client', return_value=fake), \
         patch.object(cu, '_summarize_description', side_effect=lambda *a, **k: raw.description):
        ok = cu._run_match_via_service(u, m, raw, 'CV', 'opencode', 'deepseek-v4-flash-free')
    assert ok is False
    assert m.match_score is None          # KEIN Fake-Score 0
    assert m.eval_attempts == 1
    assert m.match_reasoning is None      # < 5 -> unauffällig


def test_infra_failure_leaves_attempts_untouched(app, db_session, user_factory):
    u, raw, m = _make_match_and_user(db_session, user_factory)
    fake = _FakeClient({'opencode': RuntimeError('connection refused')})
    with patch.object(cu.ai_provider_client, 'get_client', return_value=fake):
        ok = cu._run_match_via_service(u, m, raw, 'CV', 'opencode', 'deepseek-v4-flash-free')
    assert ok is False
    assert m.match_score is None
    assert m.eval_attempts == 0           # Infra zählt NICHT zur Kappe


def test_local_factory_content_failure_no_fake_score(app, db_session, user_factory):
    u, raw, m = _make_match_and_user(db_session, user_factory)
    failed = MatchResult(score=0, reasoning="Bewertung fehlgeschlagen (ungültiges JSON von Provider).",
                         missing_skills=[], tokens_in=1, tokens_out=1, failed=True)
    with patch.object(cu, 'match_job_with_claude', return_value=failed), \
         patch.object(cu.ai_provider_client, 'is_enabled', return_value=False), \
         patch.object(cu.ProviderFactory, 'get_client', return_value=object()):
        ok = cu._run_match_via_local_factory(u, m, raw, 'CV', 'ollama', 'gemma4:12b')
    assert ok is False
    assert m.match_score is None
    assert m.eval_attempts == 1


def test_retry_branch_selects_low_prefilter_failed_match(app, db_session, user_factory):
    from models import RawJob, JobMatch, JobSource
    from services.tasks.handlers.cron_claude_match import handle_cron_claude_match
    u = user_factory(ai_provider='opencode', ai_provider_model='deepseek-v4-flash-free')
    src = JobSource(name='test', type='rss', config='{}', enabled=True, crawl_interval_min=60)
    db_session.add(src); db_session.flush()
    raw = RawJob(source_id=src.id, external_id='r9', title='IT Admin', description='Linux', url='http://x')
    db_session.add(raw); db_session.flush()
    old = datetime.utcnow() - timedelta(hours=5)
    m = JobMatch(raw_job_id=raw.id, user_id=u.id, prefilter_score=20.0, match_score=None,
                 status='new', eval_attempts=1, updated_at=old)
    db_session.add(m); db_session.commit()

    called = {}
    def fake_run(client, user, match):
        called['id'] = match.id
        match.match_score = 80.0
        match.eval_attempts = 0
        return True

    with patch('services.job_matching.claude_utils._run_claude_match_for', side_effect=fake_run), \
         patch('services.ai_provider_client.is_enabled', return_value=True):
        handle_cron_claude_match({})
    assert called.get('id') == m.id


def test_retry_branch_ignores_fresh_low_prefilter(app, db_session, user_factory):
    from models import RawJob, JobMatch, JobSource
    from services.tasks.handlers.cron_claude_match import handle_cron_claude_match
    u = user_factory(ai_provider='opencode', ai_provider_model='deepseek-v4-flash-free')
    src = JobSource(name='test2', type='rss', config='{}', enabled=True, crawl_interval_min=60)
    db_session.add(src); db_session.flush()
    raw = RawJob(source_id=src.id, external_id='r10', title='X', description='Y', url='http://x')
    db_session.add(raw); db_session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=u.id, prefilter_score=20.0, match_score=None,
                 status='new', eval_attempts=0, updated_at=datetime.utcnow() - timedelta(hours=5))
    db_session.add(m); db_session.commit()
    called = {}
    with patch('services.job_matching.claude_utils._run_claude_match_for',
               side_effect=lambda c, u, mm: called.setdefault('id', mm.id) or True), \
         patch('services.ai_provider_client.is_enabled', return_value=True):
        handle_cron_claude_match({})
    assert 'id' not in called   # eval_attempts=0 + prefilter<50 -> NICHT gezogen


def test_fifth_content_failure_sets_permanent_marker(app, db_session, user_factory):
    u, raw, m = _make_match_and_user(db_session, user_factory)
    m.eval_attempts = 4
    fake = _FakeClient({'opencode': _resp('Prosa'), 'ollama': _resp('Prosa', via='ollama')})
    with patch.object(cu.ai_provider_client, 'get_client', return_value=fake), \
         patch.object(cu, '_summarize_description', side_effect=lambda *a, **k: raw.description):
        cu._run_match_via_service(u, m, raw, 'CV', 'opencode', 'deepseek-v4-flash-free')
    assert m.eval_attempts == 5
    assert m.match_reasoning == cu.PERMANENT_FAIL_REASONING
    assert m.match_score is None
