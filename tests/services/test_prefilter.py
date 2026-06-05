# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
from services.job_matching.cv_tokenizer import CVTokens
from services.job_matching.prefilter import score_job, PrefilterContext, detect_job_type


def _ctx(language_filter=None, region_filter=None):
    return PrefilterContext(
        language_filter=language_filter or ["de", "en"],
        region_filter=region_filter,
    )


def test_score_high_for_full_overlap():
    cv = CVTokens(
        skills={"react", "typescript", "python"},
        titles={"senior frontend developer"},
        freetext={"javascript", "node.js"},
    )
    job = {
        "title": "Senior Frontend Developer (React/TypeScript)",
        "description": "Wir suchen mit React, TypeScript und Python. JavaScript-Profi.",
        "location": "Berlin",
    }
    score = score_job(cv, job, _ctx())
    assert score >= 70

def test_score_low_for_no_overlap():
    cv = CVTokens(skills={"java", "spring"})
    job = {"title": "Designer", "description": "Figma, Adobe XD", "location": "Hamburg"}
    score = score_job(cv, job, _ctx())
    assert score < 20

def test_region_filter_drops_score_to_zero():
    cv = CVTokens(skills={"react"})
    job = {"title": "React Dev", "description": "React", "location": "München, 80331"}
    ctx = _ctx(region_filter={"plz_prefixes": ["10", "11"], "remote_ok": False})
    assert score_job(cv, job, ctx) == 0

def test_remote_ok_overrides_region_filter():
    cv = CVTokens(skills={"react"})
    job = {"title": "React Dev (Remote)", "description": "React, fully remote", "location": "Munich"}
    ctx = _ctx(region_filter={"plz_prefixes": ["10"], "remote_ok": True})
    assert score_job(cv, job, ctx) > 0


def test_text_blob_cv_normalization_capped():
    """Bei Text-Blob-CVs (CV-Volltext-Upload) wird das Pool gecappt damit
    der Score nicht von hunderten Boilerplate-Tokens (Adresse, Floskeln)
    verdünnt wird. Sonst würden relevante Hits in einstelligen Prozent-
    Werten ertrinken.
    """
    # Riesiger freetext-Pool wie bei einem PDF-CV-Upload
    cv = CVTokens(
        skills=set(),
        titles=set(),
        freetext={f"boilerplate{i}" for i in range(300)} | {"python", "docker", "siem", "kubernetes"},
    )
    job = {
        "title": "Senior Security Engineer",
        "description": "Wir suchen Erfahrung mit Python, Docker, Kubernetes und SIEM.",
        "location": "Berlin",
    }
    score = score_job(cv, job, _ctx())
    # Vor dem Cap-Fix wäre der Score ~1-2% gewesen (4 Hits / 304 Pool).
    # Nach Cap auf 50: 4 / 50 = 8% → noch besser durch zusätzliche Token-Hits.
    assert score >= 8, f"Erwarte score >= 8, got {score}"


def test_detect_job_type_werkstudent():
    assert detect_job_type("Werkstudent IT-Support (m/w/d)") == "werkstudent"
    assert detect_job_type("Werkstudentin Data") == "werkstudent"
    assert detect_job_type("Werkstudierende Cloud") == "werkstudent"
    assert detect_job_type("Werkstudenten gesucht") == "werkstudent"


def test_detect_job_type_freelance():
    assert detect_job_type("Freelancer Kundenberater") == "freelance"
    assert detect_job_type("Senior Engineer (freiberuflich)") == "freelance"
    assert detect_job_type("Freiberufler Backend") == "freelance"
    # 'auf Rechnungsbasis' = klar freelance; bare 'auf Rechnung' (Zahlungsart)
    # ist KEIN Freelance-Signal und darf NICHT matchen.
    assert detect_job_type("Tätigkeit auf Rechnungsbasis") == "freelance"
    assert detect_job_type("Zahlung auf Rechnung möglich") is None


def test_detect_job_type_temp_agency_full_word():
    assert detect_job_type("IT-Support via Arbeitnehmerüberlassung") == "temp_agency"
    assert detect_job_type("Zeitarbeit Logistik") == "temp_agency"
    assert detect_job_type("Leiharbeit Kundenservice") == "temp_agency"


def test_detect_job_type_au_only_as_standalone_word():
    # Positivfall: "AÜ" als eigenes Wort
    assert detect_job_type("Senior Engineer (AÜ)") == "temp_agency"
    # Negativfall: "AÜ" als Substring darf NICHT matchen
    assert detect_job_type("Bautätigkeit prüfen") is None
    assert detect_job_type("Genauigkeit zählt") is None


def test_detect_job_type_returns_none_for_normal_title():
    assert detect_job_type("Senior Cyber Security Analyst (m/w/d)") is None
    assert detect_job_type("DevOps Engineer Berlin") is None


def test_detect_job_type_handles_none_and_empty():
    assert detect_job_type(None) is None
    assert detect_job_type("") is None
    assert detect_job_type("   ") is None


def test_detect_job_type_case_insensitive():
    assert detect_job_type("WERKSTUDENT") == "werkstudent"
    assert detect_job_type("FreElAnCeR") == "freelance"
