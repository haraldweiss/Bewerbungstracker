from pathlib import Path
import responses
from services.job_sources.rss import RssAdapter
from services.job_sources.base import FetchedJob


FIXTURE = Path(__file__).parent.parent / "fixtures" / "rss_stepstone_sample.xml"


@responses.activate
def test_rss_adapter_parses_two_jobs():
    rss_xml = FIXTURE.read_text()
    responses.add(responses.GET, "https://example.com/feed.xml", body=rss_xml,
                  content_type="application/rss+xml", status=200)

    adapter = RssAdapter(config={"url": "https://example.com/feed.xml"})
    jobs = adapter.fetch()

    assert len(jobs) == 2
    assert isinstance(jobs[0], FetchedJob)
    assert jobs[0].external_id == "stepstone-12345"
    assert "Senior Frontend" in jobs[0].title
    assert jobs[0].url == "https://www.stepstone.de/jobs/senior-frontend-12345"
