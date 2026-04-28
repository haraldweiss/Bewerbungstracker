import base64
import json
from pathlib import Path
import re

import responses
from services.job_sources.bundesagentur import BundesagenturAdapter

FIX = Path(__file__).parent.parent / "fixtures" / "bundesagentur_response.json"

LISTING_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
DETAIL_BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails"


@responses.activate
def test_bundesagentur_parses_listing_only_fallback():
    """Wenn Detail-Endpoint nicht erreichbar/404, fällt der Adapter auf
    Listing-Daten zurück (description=None) — kein Hard-Fail."""
    responses.add(responses.GET, LISTING_URL,
                  json=json.loads(FIX.read_text()), status=200)
    # Detail-Calls liefern alle 404
    responses.add_passthru(re.compile(rf"^{re.escape(DETAIL_BASE)}/.*"))

    adapter = BundesagenturAdapter(config={"was": "Frontend", "wo": "10115", "umkreis": 25})
    jobs = adapter.fetch()
    assert len(jobs) == 1
    assert jobs[0].external_id == "10000-1234567890-S"
    assert jobs[0].company == "Tech Solutions GmbH"
    assert "Berlin" in jobs[0].location


@responses.activate
def test_bundesagentur_enriches_with_detail():
    """Wenn Detail-Endpoint volle Beschreibung liefert, landet sie in
    job.description; Anstellungs-Tags werden angehängt."""
    refnr = "10000-1234567890-S"
    encoded = base64.b64encode(refnr.encode()).decode()

    responses.add(responses.GET, LISTING_URL,
                  json=json.loads(FIX.read_text()), status=200)
    responses.add(responses.GET, f"{DETAIL_BASE}/{encoded}", json={
        "stellenangebotsTitel": "Senior React Developer (m/w/d) - Detail",
        "stellenangebotsBeschreibung": "Erfahrung mit React, TypeScript, Node.js.",
        "arbeitszeitVollzeit": True,
        "arbeitszeitTeilzeitFlexibel": False,
        "vertragsdauer": "UNBEFRISTET",
        "stellenlokationen": [
            {"adresse": {"plz": "10178", "ort": "Berlin", "region": "BERLIN", "land": "DEUTSCHLAND"}},
        ],
    }, status=200)

    adapter = BundesagenturAdapter(config={"was": "Frontend", "wo": "10115", "umkreis": 25})
    jobs = adapter.fetch()
    assert len(jobs) == 1
    j = jobs[0]
    # Title aus detail bevorzugt
    assert "Detail" in j.title
    # Description vorhanden
    assert "React" in j.description
    # Anstellungs-Tags angehängt
    assert "vollzeit" in j.description.lower()
    assert "unbefristet" in j.description.lower()
    # Location aus stellenlokationen
    assert "10178" in j.location


@responses.activate
def test_bundesagentur_max_details_limit():
    """`max_details` config begrenzt wie viele Listing-Items Detail-fetched
    werden — der Rest entfällt komplett (nicht im Output)."""
    listing_with_many = {"stellenangebote": [
        {"refnr": f"REF-{i}", "titel": f"Job {i}",
         "arbeitgeber": "Co", "arbeitsort": {"plz": "1011" + str(i % 10), "ort": "Berlin", "region": "B"}}
        for i in range(5)
    ]}
    responses.add(responses.GET, LISTING_URL, json=listing_with_many, status=200)
    # Alle Details schlagen fehl — Adapter benutzt fallback
    responses.add_passthru(re.compile(rf"^{re.escape(DETAIL_BASE)}/.*"))

    adapter = BundesagenturAdapter(config={
        "was": "x", "wo": "10115", "umkreis": 25, "max_details": 2,
    })
    jobs = adapter.fetch()
    # 5 in listing aber nur 2 enriched → genau 2 im Output
    assert len(jobs) == 2
