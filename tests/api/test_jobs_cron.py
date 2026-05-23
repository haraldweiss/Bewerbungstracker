# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
import os
import json
from pathlib import Path
import pytest
import responses
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app import create_app
from database import db
from models import User, JobSource, RawJob, JobMatch, ApiCall


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("JOB_CRON_TOKEN", "test-token")
    # ProviderFactory liest ANTHROPIC_API_KEY direkt aus env — ohne Wert
    # scheitert _run_match_via_local_factory bevor der Mock greift.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@responses.activate
def test_crawl_source_picks_due_source_creates_raw_jobs_and_matches(app, client, user_factory):
    user = user_factory(job_discovery_enabled=True, cv_data_json='{"cv":{"skills":["react"]}}')

    rss_xml = (Path(__file__).parent.parent / "fixtures" / "rss_stepstone_sample.xml").read_text()
    responses.add(responses.GET, "https://example.com/feed.xml",
                  body=rss_xml, content_type="application/rss+xml", status=200)

    src = JobSource(name="Test", type="rss", config={"url": "https://example.com/feed.xml"},
                    enabled=True, crawl_interval_min=60)
    db.session.add(src)
    db.session.commit()

    r = client.post("/api/jobs/crawl-source", headers={"X-Cron-Token": "test-token"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["source_id"] == src.id
    assert body["new_jobs"] == 2
    assert body["matches_created"] == 2  # 2 jobs × 1 user

    raw_jobs = RawJob.query.all()
    assert len(raw_jobs) == 2
    matches = JobMatch.query.all()
    assert len(matches) == 2
    assert all(m.user_id == user.id for m in matches)
    assert all(m.status == "new" for m in matches)


def test_crawl_source_skips_sources_not_due(app, client):
    src = JobSource(name="Recent", type="rss", config={"url": "x"},
                    enabled=True, crawl_interval_min=60,
                    last_crawled_at=datetime.utcnow() - timedelta(minutes=5))
    db.session.add(src); db.session.commit()
    r = client.post("/api/jobs/crawl-source", headers={"X-Cron-Token": "test-token"})
    assert r.status_code == 200
    assert r.get_json()["source_id"] is None
    assert r.get_json()["reason"] == "no_source_due"


@responses.activate
def test_crawl_source_records_error_and_increments_failures(app, client):
    responses.add(responses.GET, "https://example.com/broken.xml", status=500)
    src = JobSource(name="Broken", type="rss", config={"url": "https://example.com/broken.xml"},
                    enabled=True, crawl_interval_min=60)
    db.session.add(src); db.session.commit()

    r = client.post("/api/jobs/crawl-source", headers={"X-Cron-Token": "test-token"})
    db.session.refresh(src)
    assert src.consecutive_failures == 1
    assert src.last_error is not None


def test_prefilter_scores_pending_matches(app, client, user_factory):
    user = user_factory(
        job_discovery_enabled=True,
        cv_data_json=json.dumps({"cv": {"skills": ["react", "typescript"]}}),
    )
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="1",
                 title="Senior React Developer", description="React, TypeScript, Berlin",
                 url="https://example.com/1", crawl_status='raw')
    db.session.add(raw); db.session.flush()
    db.session.add(JobMatch(raw_job_id=raw.id, user_id=user.id, status='new'))
    db.session.commit()

    r = client.post("/api/jobs/prefilter", headers={"X-Cron-Token": "test-token"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["scored"] == 1

    m = JobMatch.query.first()
    assert m.prefilter_score is not None
    assert m.prefilter_score > 0


def test_prefilter_dismisses_low_scores(app, client, user_factory):
    user = user_factory(
        job_discovery_enabled=True,
        cv_data_json=json.dumps({"cv": {"skills": ["python"]}}),
    )
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="1",
                 title="Designer", description="Figma",
                 url="https://example.com/1", crawl_status='raw')
    db.session.add(raw); db.session.flush()
    db.session.add(JobMatch(raw_job_id=raw.id, user_id=user.id, status='new'))
    db.session.commit()

    client.post("/api/jobs/prefilter", headers={"X-Cron-Token": "test-token"})
    m = JobMatch.query.first()
    assert m.status == 'dismissed'


def test_prefilter_calls_embed_raw_job(app, client, user_factory):
    """Verifiziert dass prefilter best-effort embed_raw_job aufruft."""
    user = user_factory(
        job_discovery_enabled=True,
        cv_data_json=json.dumps({"cv": {"skills": ["react"]}}),
    )
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="1",
                 title="React Developer", description="React, TS",
                 url="https://example.com/1", crawl_status='raw')
    db.session.add(raw); db.session.flush()
    db.session.add(JobMatch(raw_job_id=raw.id, user_id=user.id, status='new'))
    db.session.commit()

    with patch('api.jobs_cron.embed_raw_job') as mock_embed:
        mock_embed.return_value = True
        r = client.post("/api/jobs/prefilter", headers={"X-Cron-Token": "test-token"})
        assert r.status_code == 200
        mock_embed.assert_called_once()


def test_prefilter_resilient_to_embed_failure(app, client, user_factory):
    """Verifiziert dass prefilter weiterläuft wenn embed_raw_job exception wirft."""
    user = user_factory(
        job_discovery_enabled=True,
        cv_data_json=json.dumps({"cv": {"skills": ["react", "typescript"]}}),
    )
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="1",
                 title="Senior React Developer", description="React, TypeScript",
                 url="https://example.com/1", crawl_status='raw')
    db.session.add(raw); db.session.flush()
    db.session.add(JobMatch(raw_job_id=raw.id, user_id=user.id, status='new'))
    db.session.commit()

    with patch('api.jobs_cron.embed_raw_job', side_effect=RuntimeError("ollama down")):
        r = client.post("/api/jobs/prefilter", headers={"X-Cron-Token": "test-token"})
        assert r.status_code == 200
        body = r.get_json()
        assert body["scored"] == 1

    m = JobMatch.query.first()
    assert m.prefilter_score is not None


def test_claude_match_scores_top_n_per_user(app, client, user_factory):
    """Cron-Endpoint /claude-match bewertet die Top-N (per job_claude_budget_per_tick).

    Mock greift bei ProviderFactory.get_client + match_job_with_claude — das ist
    die Stelle, an der der echte Pfad in _run_match_via_local_factory landet.
    """
    user = user_factory(
        job_discovery_enabled=True,
        cv_data_json=json.dumps({"cv": {"skills": ["react"], "summary": "React expert"}}),
        job_claude_budget_per_tick=2,
    )
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    for i in range(5):
        raw = RawJob(source_id=src.id, external_id=f"id-{i}",
                     title=f"React Job {i}", description="React",
                     url=f"https://example.com/{i}", crawl_status='raw')
        db.session.add(raw); db.session.flush()
        db.session.add(JobMatch(raw_job_id=raw.id, user_id=user.id, status='new',
                                prefilter_score=70 + i))
    db.session.commit()

    fake_result = MagicMock(score=88, reasoning="ok", missing_skills=[],
                            tokens_in=100, tokens_out=20)
    with patch("api.jobs_cron.ProviderFactory.get_client", return_value=MagicMock()), \
         patch("api.jobs_cron.match_job_with_claude", return_value=fake_result):
        r = client.post("/api/jobs/claude-match", headers={"X-Cron-Token": "test-token"})

    body = r.get_json()
    assert body["matched"] == 2
    matched = JobMatch.query.filter(JobMatch.match_score.isnot(None)).all()
    assert len(matched) == 2


@patch("services.job_matching.notifier._send_push")
def test_notify_sends_for_high_score_only(mock_push, app, client, user_factory):
    user = user_factory(job_discovery_enabled=True, job_notification_threshold=80)
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="1", title="t", url="x", crawl_status='matched')
    db.session.add(raw); db.session.flush()
    db.session.add(JobMatch(raw_job_id=raw.id, user_id=user.id, status='new',
                            prefilter_score=80, match_score=85))
    raw2 = RawJob(source_id=src.id, external_id="2", title="t", url="x", crawl_status='matched')
    db.session.add(raw2); db.session.flush()
    db.session.add(JobMatch(raw_job_id=raw2.id, user_id=user.id, status='new',
                            prefilter_score=70, match_score=70))
    db.session.commit()

    r = client.post("/api/jobs/notify", headers={"X-Cron-Token": "test-token"})
    assert r.get_json()["notified"] == 1
    assert mock_push.call_count == 1


def test_cleanup_archives_old_unused_raw_jobs(app, client):
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    old_raw = RawJob(source_id=src.id, external_id="old", title="t", url="x",
                     crawl_status='matched',
                     created_at=datetime.utcnow() - timedelta(days=70))
    new_raw = RawJob(source_id=src.id, external_id="new", title="t", url="x",
                     crawl_status='matched')
    db.session.add_all([old_raw, new_raw]); db.session.commit()

    r = client.post("/api/jobs/cleanup", headers={"X-Cron-Token": "test-token"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["archived_raw_jobs"] == 1

    db.session.refresh(old_raw)
    assert old_raw.crawl_status == 'archived'


def test_run_claude_match_for_idempotent(app, user_factory):
    """Wenn match_score schon gesetzt ist, returnt der Helper sofort False ohne Claude-Call."""
    from api.jobs_cron import _run_claude_match_for
    from unittest.mock import MagicMock

    user = user_factory()
    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="Dev", url="https://j/1")
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new',
                 match_score=80, match_reasoning="bereits bewertet")
    db.session.add(m); db.session.commit()

    fake_client = MagicMock()
    result = _run_claude_match_for(fake_client, user, m)

    assert result is False
    assert m.match_score == 80
    fake_client.assert_not_called()


def test_run_claude_match_for_returns_false_when_budget_exhausted(app, user_factory):
    """Wenn Tagesbudget erschöpft: Helper returnt False, kein Claude-Call."""
    from api.jobs_cron import _run_claude_match_for
    from unittest.mock import MagicMock

    user = user_factory()
    user.job_daily_budget_cents = 50
    db.session.commit()

    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="Dev", url="https://j/1")
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new', match_score=None)
    db.session.add(m)
    # ApiCall mit cost 1.00 EUR füllt das Budget (50 cents) auf
    db.session.add(ApiCall(user_id=user.id, endpoint='/test', model='x',
                           tokens_in=0, tokens_out=0, cost=1.00, key_owner='server'))
    db.session.commit()

    fake_client = MagicMock()
    result = _run_claude_match_for(fake_client, user, m)

    assert result is False
    assert m.match_score is None


def test_run_claude_match_for_success_writes_all_fields(app, user_factory):
    """Helper schreibt match_score, reasoning, missing_skills, raw.crawl_status, ApiCall."""
    from api.jobs_cron import _run_claude_match_for
    from unittest.mock import patch, MagicMock

    user = user_factory(cv_data_json='{"cv": {"summary": "Dev"}}')
    user.job_daily_budget_cents = 1000
    db.session.commit()

    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()
    raw = RawJob(source_id=src.id, external_id="a", title="Dev",
                 url="https://j/1", crawl_status='raw')
    db.session.add(raw); db.session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new', match_score=None)
    db.session.add(m); db.session.commit()

    fake_result = MagicMock(score=88, reasoning="passt",
                            missing_skills=["docker", "k8s"],
                            tokens_in=20, tokens_out=20)
    fake_client = MagicMock()
    with patch("api.jobs_cron.match_job_with_claude", return_value=fake_result):
        result = _run_claude_match_for(fake_client, user, m)

    assert result is True
    db.session.refresh(m); db.session.refresh(raw)
    assert m.match_score == 88
    assert m.match_reasoning == "passt"
    assert m.missing_skills == ["docker", "k8s"]
    assert raw.crawl_status == "matched"
    # Verify ApiCall created
    api_calls = ApiCall.query.filter_by(user_id=user.id).all()
    assert len(api_calls) == 1
    assert api_calls[0].endpoint == '/api/jobs/match'


def test_auto_cron_skips_jobs_below_auto_threshold(app, user_factory, monkeypatch):
    """Auto-Cron bewertet nur prefilter_score >= AUTO_CLAUDE_THRESHOLD (50)."""
    from unittest.mock import patch, MagicMock
    from api.jobs_cron import AUTO_CLAUDE_THRESHOLD

    assert AUTO_CLAUDE_THRESHOLD == 50

    user = user_factory(cv_data_json='{"cv": {"summary": "Python Dev", "skills": ["python"]}}')
    user.job_discovery_enabled = True
    user.job_claude_budget_per_tick = 5
    user.job_daily_budget_cents = 1000
    db.session.commit()

    src = JobSource(name="x", type="rss", config={"url": "x"})
    db.session.add(src); db.session.flush()

    raw_low = RawJob(source_id=src.id, external_id="low", title="Low", url="https://j/low")
    raw_high = RawJob(source_id=src.id, external_id="high", title="High", url="https://j/high")
    db.session.add_all([raw_low, raw_high]); db.session.flush()

    m_low = JobMatch(raw_job_id=raw_low.id, user_id=user.id,
                     status='new', prefilter_score=40, match_score=None)
    m_high = JobMatch(raw_job_id=raw_high.id, user_id=user.id,
                      status='new', prefilter_score=60, match_score=None)
    db.session.add_all([m_low, m_high]); db.session.commit()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    fake_result = MagicMock(score=85, reasoning="ok",
                            missing_skills=[], tokens_in=10, tokens_out=10)
    with patch("api.jobs_cron._get_anthropic_client", return_value=MagicMock()), \
         patch("api.jobs_cron.match_job_with_claude", return_value=fake_result):
        client_t = app.test_client()
        r = client_t.post("/api/jobs/claude-match", headers={"X-Cron-Token": "test-token"})
        assert r.status_code == 200

    db.session.refresh(m_low)
    db.session.refresh(m_high)
    assert m_low.match_score is None    # geskippt (prefilter < 50)
    assert m_high.match_score == 85     # bewertet (prefilter >= 50)


def test_match_uses_feature_override(app, user_factory, db_session):
    """Wenn User feature_model_overrides für match gesetzt hat,
    wird der Override genutzt."""
    import json as _j
    from unittest.mock import patch, MagicMock
    from api.jobs_cron import _run_claude_match_for
    from models import JobSource, RawJob, JobMatch

    user = user_factory(cv_data_json='{"cv": {"summary": "Dev"}}')
    user.ai_provider = 'ollama'
    user.ai_provider_model = 'mistral-nemo:12b'
    user.feature_model_overrides = _j.dumps({
        'match': {'provider': 'claude', 'model': 'claude-haiku-4-5-20251001'},
    })
    user.job_daily_budget_cents = 1000
    db_session.commit()

    src = JobSource(name='x', type='rss', config={'url': 'x'})
    db_session.add(src); db_session.flush()
    raw = RawJob(source_id=src.id, external_id='a', title='Dev',
                 url='https://j/1', description='Wir suchen Python', crawl_status='raw')
    db_session.add(raw); db_session.flush()
    m = JobMatch(raw_job_id=raw.id, user_id=user.id, status='new', match_score=None)
    db_session.add(m); db_session.commit()

    fake_result = MagicMock(score=80, reasoning='ok', missing_skills=[],
                            tokens_in=10, tokens_out=10)
    captured = {}
    def fake_get_client(provider, *args, **kwargs):
        captured['provider'] = provider
        return MagicMock()

    with patch('api.jobs_cron.ProviderFactory.get_client', side_effect=fake_get_client), \
         patch('api.jobs_cron.match_job_with_claude', return_value=fake_result):
        _run_claude_match_for(None, user, m)

    assert captured.get('provider') == 'claude'


def test_estimate_cost_usd_does_not_round_sub_cent_calls_to_zero():
    """Regression: bei Haiku-Preisen sind typische Match-Calls <0.5¢ — die alte
    int-cents Variante rundete sie auf 0, sodass api_calls.cost fälschlich $0
    zeigte (Vorfall 2026-05-14: 18.435 Calls Anthropic-billed, DB sah $0).
    Nach Phase 2B: Funktion lebt in services/cost_tracker.py."""
    from services.cost_tracker import estimate_cost_usd
    # Haiku-typischer Match-Call: 2552 in / 241 out tokens
    cost = estimate_cost_usd('claude-haiku-4-5-20251001', 2552, 241)
    assert cost > 0.0, "sub-cent costs must not round to zero"
    assert cost < 0.01, "should still be sub-cent for haiku-typical call"
