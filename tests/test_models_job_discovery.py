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


def test_user_job_sources_backref(app, user_factory):
    user = user_factory()
    db.session.add(JobSource(user_id=user.id, name="A", type="rss",
                              config={"url": "x"}))
    db.session.add(JobSource(user_id=user.id, name="B", type="rss",
                              config={"url": "y"}))
    db.session.commit()
    db.session.refresh(user)
    assert len(user.job_sources) == 2
    assert {s.name for s in user.job_sources} == {"A", "B"}


from models import RawJob


def test_raw_job_dedup_per_source(app):
    src = JobSource(name="Test", type="rss", config={"url": "x"})
    db.session.add(src)
    db.session.flush()

    job1 = RawJob(
        source_id=src.id,
        external_id="abc-123",
        title="Frontend",
        company="ACME",
        url="https://example.com/job/1",
        crawl_status="raw",
    )
    db.session.add(job1)
    db.session.commit()

    # Selbe (source_id, external_id) sollte UNIQUE-Constraint verletzen
    job_dup = RawJob(
        source_id=src.id,
        external_id="abc-123",
        title="Andere Daten",
        url="https://example.com/job/2",
        crawl_status="raw",
    )
    db.session.add(job_dup)
    with pytest.raises(Exception):
        db.session.commit()
    db.session.rollback()
