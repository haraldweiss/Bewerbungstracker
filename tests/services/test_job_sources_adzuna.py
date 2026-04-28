import json
from pathlib import Path
import responses
from services.job_sources.adzuna import AdzunaAdapter

FIX = Path(__file__).parent.parent / "fixtures" / "adzuna_response.json"


@responses.activate
def test_adzuna_adapter_parses():
    responses.add(
        responses.GET,
        "https://api.adzuna.com/v1/api/jobs/de/search/1",
        json=json.loads(FIX.read_text()),
        status=200,
    )

    adapter = AdzunaAdapter(config={
        "app_id": "id123", "app_key": "key456",
        "country": "de", "what": "react", "where": "Berlin",
        "results_per_page": 50,
    })
    jobs = adapter.fetch()
    assert len(jobs) == 1
    assert jobs[0].external_id == "1234567890"
    assert jobs[0].company == "ACME GmbH"
    assert jobs[0].location == "Berlin"
