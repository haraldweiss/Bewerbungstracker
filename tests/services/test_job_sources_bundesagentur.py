# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
import base64
import json
from pathlib import Path
import re

import responses
from services.job_sources.bundesagentur import (
    BundesagenturAdapter,
    _translate_arbeitszeit,
)

FIX = Path(__file__).parent.parent / "fixtures" / "bundesagentur_response.json"

# API-Stand 2026-08-04: Listing auf v6 gehoben (v4 -> 404), Details weiterhin v4.
LISTING_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
DETAIL_BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails"


def _listing_body() -> dict:
    return json.loads(FIX.read_text())


@responses.activate
def test_bundesagentur_parses_listing_only_fallback():
    """Wenn Detail-Endpoint nicht erreichbar/404, fällt der Adapter auf
    Listing-Daten zurück (description=None) — kein Hard-Fail."""
    responses.add(responses.GET, LISTING_URL,
                  json=_listing_body(), status=200)
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
                  json=_listing_body(), status=200)
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
    listing_with_many = {"ergebnisliste": [
        {"referenznummer": f"REF-{i}",
         "stellenangebotsTitel": f"Job {i}",
         "firma": "Co",
         "stellenlokationen": [
             {"adresse": {"plz": "1011" + str(i % 10), "ort": "Berlin", "region": "B"}}
         ]}
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


@responses.activate
def test_bundesagentur_translates_arbeitszeit_param():
    """v6 erwartet Kennungen (vz/tz/ho/...), Legacy-Werte werden übersetzt;
    der übersetzte Wert landet im Listing-Query."""
    responses.add(responses.GET, LISTING_URL,
                  json={"ergebnisliste": []}, status=200)

    adapter = BundesagenturAdapter(config={
        "was": "x", "wo": "10115", "arbeitszeit": "vollzeit;teilzeit",
    })
    adapter.fetch()
    assert len(responses.calls) == 1
    q = responses.calls[0].request.url
    assert "arbeitszeit=vz%3Btz" in q or "arbeitszeit=vz;tz" in q


def test_translate_arbeitszeit():
    assert _translate_arbeitszeit("vollzeit") == "vz"
    assert _translate_arbeitszeit("teilzeit") == "tz"
    assert _translate_arbeitszeit("remote") == "ho"
    assert _translate_arbeitszeit("vollzeit;teilzeit") == "vz;tz"
    assert _translate_arbeitszeit("vz") == "vz"
    # Unbekannte Codes unangetastet
    assert _translate_arbeitszeit("sonderfall") == "sonderfall"
    assert _translate_arbeitszeit("") == ""
