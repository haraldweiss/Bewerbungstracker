"""Tests für shared Dedup-Helper."""
import pytest
from services.job_sources.dedup import get_existing_job_urls, deduplicate
from services.job_sources.base import FetchedJob
from models import RawJob, JobSource, Application, User
from database import db


def test_get_existing_job_urls_combines_raw_jobs_and_applications(app, db_session):
    """Returns Set aller URLs aus RawJob + Application.link."""
    user = User(id="u1", email="t@t.de", password_hash="x")
    db_session.add(user)
    src = JobSource(name="x", type="rss", enabled=True)
    src.config = {"url": "x"}
    db_session.add(src)
    db_session.flush()

    rj = RawJob(source_id=src.id, external_id="e1",
                title="Dev", url="https://job.example/1")
    db_session.add(rj)

    app_row = Application(user_id="u1", company="C", position="P",
                          link="https://job.example/2")
    db_session.add(app_row)
    db_session.commit()

    urls = get_existing_job_urls()
    assert "https://job.example/1" in urls
    assert "https://job.example/2" in urls


def test_get_existing_job_urls_skips_null_links(app, db_session):
    """Application.link kann NULL sein — nicht in Set landen."""
    user = User(id="u2", email="x@x.de", password_hash="x")
    db_session.add(user)
    db_session.add(Application(user_id="u2", company="C", position="P", link=None))
    db_session.commit()

    urls = get_existing_job_urls()
    assert None not in urls


def test_deduplicate_removes_in_batch_url_duplicates():
    """Dieselbe URL 2x in jobs-Liste → nur 1x im Result."""
    jobs = [
        FetchedJob(external_id="a", title="T1", url="https://j.de/1"),
        FetchedJob(external_id="b", title="T1-dup", url="https://j.de/1"),
        FetchedJob(external_id="c", title="T2", url="https://j.de/2"),
    ]
    result = deduplicate(jobs, existing_urls=set())
    assert len(result) == 2
    assert {j.url for j in result} == {"https://j.de/1", "https://j.de/2"}


def test_deduplicate_excludes_existing_urls():
    """Jobs mit URL in existing_urls werden ausgefiltert."""
    jobs = [
        FetchedJob(external_id="a", title="T1", url="https://j.de/1"),
        FetchedJob(external_id="b", title="T2", url="https://j.de/2"),
    ]
    result = deduplicate(jobs, existing_urls={"https://j.de/1"})
    assert len(result) == 1
    assert result[0].url == "https://j.de/2"


def test_deduplicate_preserves_order():
    """Reihenfolge der ersten Vorkommen bleibt erhalten."""
    jobs = [
        FetchedJob(external_id="a", title="T1", url="https://j.de/1"),
        FetchedJob(external_id="b", title="T2", url="https://j.de/2"),
        FetchedJob(external_id="c", title="T1-dup", url="https://j.de/1"),
    ]
    result = deduplicate(jobs, existing_urls=set())
    assert [j.url for j in result] == ["https://j.de/1", "https://j.de/2"]


def test_deduplicate_handles_empty_input():
    """Leere Job-Liste → leeres Result."""
    assert deduplicate([], existing_urls=set()) == []


def test_deduplicate_skips_jobs_with_empty_url():
    """Jobs ohne URL (None oder '') werden übersprungen."""
    jobs = [
        FetchedJob(external_id="a", title="T1", url=""),
        FetchedJob(external_id="b", title="T2", url="https://j.de/2"),
        FetchedJob(external_id="c", title="T3", url=None),
    ]
    result = deduplicate(jobs, existing_urls=set())
    assert len(result) == 1
    assert result[0].url == "https://j.de/2"
