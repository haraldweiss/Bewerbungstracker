# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest
from datetime import datetime, timedelta
from app import create_app
from database import db
from models import ApiCall


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_estimate_cost_usd_haiku():
    from services.cost_tracker import estimate_cost_usd
    # Haiku 4.5: $1/MTok in, $5/MTok out
    usd = estimate_cost_usd('claude-haiku-4-5-20251001', tokens_in=1_000_000, tokens_out=1_000_000)
    assert usd == pytest.approx(6.0, rel=0.01)


def test_estimate_cost_usd_sonnet():
    from services.cost_tracker import estimate_cost_usd
    # Sonnet 4.6: $3/MTok in, $15/MTok out
    usd = estimate_cost_usd('claude-sonnet-4-6', tokens_in=1_000_000, tokens_out=1_000_000)
    assert usd == pytest.approx(18.0, rel=0.01)


def test_estimate_cost_usd_ollama_is_zero():
    from services.cost_tracker import estimate_cost_usd
    assert estimate_cost_usd('mistral-nemo:12b', 100_000, 100_000) == 0.0
    assert estimate_cost_usd('deepseek-r1:8b', 100_000, 100_000) == 0.0


def test_record_call_writes_api_calls_row(app):
    from services.cost_tracker import record_call
    record_call(user_id='u1', endpoint='ep', model='claude-haiku-4-5-20251001',
                tokens_in=1000, tokens_out=200, cost_usd=0.002, key_owner='server')
    db.session.commit()
    rows = ApiCall.query.filter_by(user_id='u1').all()
    assert len(rows) == 1
    assert rows[0].model == 'claude-haiku-4-5-20251001'
    assert rows[0].cost == pytest.approx(0.002)


def test_user_today_cost_cents_sums_today(app):
    from services.cost_tracker import record_call, user_today_cost_cents
    # 3 calls heute mit total 0.060 USD = 6 cents (eindeutig, kein banker's-rounding-Edge)
    for cost in (0.020, 0.030, 0.010):
        record_call(user_id='u1', endpoint='ep', model='m', tokens_in=1, tokens_out=1,
                    cost_usd=cost, key_owner='server')
    db.session.commit()
    assert user_today_cost_cents('u1') == 6


def test_user_today_cost_cents_ignores_yesterday(app):
    from services.cost_tracker import record_call, user_today_cost_cents
    record_call(user_id='u1', endpoint='ep', model='m', tokens_in=1, tokens_out=1,
                cost_usd=99.0, key_owner='server')
    # Manuelle Manipulation: gestern setzen
    db.session.flush()
    call = ApiCall.query.filter_by(user_id='u1').first()
    call.timestamp = datetime.utcnow() - timedelta(days=1, hours=2)
    db.session.commit()
    assert user_today_cost_cents('u1') == 0
