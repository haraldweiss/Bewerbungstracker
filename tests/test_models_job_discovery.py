import pytest
from datetime import datetime
from app import create_app
from database import db
from models import JobSource


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_job_source_creates_global(app):
    src = JobSource(
        name="Bundesagentur Frontend",
        type="bundesagentur",
        config={"was": "Frontend", "wo": "10115"},
        enabled=True,
        crawl_interval_min=60,
    )
    db.session.add(src)
    db.session.commit()

    assert src.id is not None
    assert src.user_id is None  # global
    assert src.consecutive_failures == 0
    assert src.config == {"was": "Frontend", "wo": "10115"}


def test_job_source_user_owned(app, user_factory):
    user = user_factory()
    src = JobSource(
        user_id=user.id,
        name="Mein RSS-Feed",
        type="rss",
        config={"url": "https://example.com/feed.xml"},
    )
    db.session.add(src)
    db.session.commit()

    assert src.user_id == user.id
