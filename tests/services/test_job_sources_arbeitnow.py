import json
from pathlib import Path
import responses
from services.job_sources.arbeitnow import ArbeitnowAdapter

FIX = Path(__file__).parent.parent / "fixtures" / "arbeitnow_response.json"


@responses.activate
def test_arbeitnow_parses_and_filters_tags():
    responses.add(responses.GET, "https://www.arbeitnow.com/api/job-board-api",
                  json=json.loads(FIX.read_text()), status=200)
    adapter = ArbeitnowAdapter(config={"tags": ["javascript"]})
    jobs = adapter.fetch()
    assert len(jobs) == 1
    assert jobs[0].external_id == "senior-react-engineer-acme"
    assert "Berlin" in jobs[0].location

@responses.activate
def test_arbeitnow_tag_filter_excludes():
    responses.add(responses.GET, "https://www.arbeitnow.com/api/job-board-api",
                  json=json.loads(FIX.read_text()), status=200)
    adapter = ArbeitnowAdapter(config={"tags": ["python"]})
    assert len(adapter.fetch()) == 0
