import json
from pathlib import Path
import responses
from services.job_sources.bundesagentur import BundesagenturAdapter

FIX = Path(__file__).parent.parent / "fixtures" / "bundesagentur_response.json"


@responses.activate
def test_bundesagentur_parses():
    responses.add(
        responses.GET,
        "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs",
        json=json.loads(FIX.read_text()),
        status=200,
    )
    adapter = BundesagenturAdapter(config={"was": "Frontend", "wo": "10115", "umkreis": 25})
    jobs = adapter.fetch()
    assert len(jobs) == 1
    assert jobs[0].external_id == "10000-1234567890-S"
    assert jobs[0].company == "Tech Solutions GmbH"
    assert "Berlin" in jobs[0].location
