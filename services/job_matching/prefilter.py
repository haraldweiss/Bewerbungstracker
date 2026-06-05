# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Lokales Keyword-Scoring (Pre-Filter vor Claude-Match).

Score-Logik:
- Skill-Overlap: × 3 Gewichtung
- Titel-Overlap: × 2
- Freetext-Overlap: × 1
- Normalisiert auf 0-100 (Anteil des CV-Token-Pools, der im Job vorkommt)

Negative Filter (Score = 0):
- Region-Filter (PLZ-Präfix) und nicht "Remote"
- Sprache-Filter (Heuristik: deutsche/englische Wörter im Titel)
"""

from __future__ import annotations
import re
from dataclasses import dataclass

from services.job_matching.cv_tokenizer import CVTokens
from services.job_matching.learner import compute_score_adjustment


_TOKEN_RE = re.compile(r"[a-zA-ZäöüÄÖÜß0-9]+(?:[.\+#][a-zA-ZäöüÄÖÜß0-9]+)*")
_REMOTE_RE = re.compile(r"\bremote\b|\bhomeoffice\b|fully\s+remote", re.IGNORECASE)
_PLZ_RE = re.compile(r"\b\d{5}\b")

# Quick-Reasons-Phase-1: Job-Typ-Detection für User.job_type_blacklist.
# Reihenfolge der Keys = Match-Priorität (erster Hit gewinnt).
# Keywords case-insensitive, Word-Boundary via re.search r'\b...\b'.
_JOB_TYPE_PATTERNS = [
    ('werkstudent', re.compile(
        r'\b(?:werkstudent|werkstudenten|werkstudentin|werkstudierende)\b',
        re.IGNORECASE,
    )),
    ('freelance', re.compile(
        r'\b(?:freelancer|freelance|freiberuflich|freiberufler|'
        r'selbstständig|auf rechnungsbasis)\b',
        re.IGNORECASE,
    )),
    ('temp_agency', re.compile(
        r'\b(?:arbeitnehmerüberlassung|aü|leiharbeit|zeitarbeit)\b',
        re.IGNORECASE,
    )),
]


def detect_job_type(title: str | None) -> str | None:
    """Liefert ersten Hit ∈ {'werkstudent','freelance','temp_agency'} oder None.

    Word-Boundary-Match (re.IGNORECASE). "AÜ" matcht nur als eigenständiges
    Wort, nicht als Substring von "Bautätigkeit" o.Ä.
    """
    if not title or not title.strip():
        return None
    for label, pattern in _JOB_TYPE_PATTERNS:
        if pattern.search(title):
            return label
    return None


@dataclass
class PrefilterContext:
    language_filter: list  # z.B. ["de", "en"]
    region_filter: dict | None  # z.B. {"plz_prefixes": ["10","11"], "remote_ok": True}


def _tokenize(text: str) -> set:
    return {m.group().lower() for m in _TOKEN_RE.finditer(text or "")}


def _matches_region(job: dict, region: dict) -> bool:
    text = f"{job.get('location') or ''} {job.get('description') or ''}"

    if region.get("remote_ok") and _REMOTE_RE.search(text):
        return True

    prefixes = region.get("plz_prefixes") or []
    if not prefixes:
        return True
    plzs = _PLZ_RE.findall(text)
    return any(plz.startswith(p) for plz in plzs for p in prefixes)


def _detect_language(job: dict) -> str:
    text = (job.get("title") or "").lower()
    de_markers = ["entwickler", "stelle", "berater", "leiter", "kaufmann", "kauffrau", "ingenieur"]
    if any(m in text for m in de_markers):
        return "de"
    return "en"  # default


def score_job(cv: CVTokens, job: dict, ctx: PrefilterContext,
              user=None, raw_job_id: int | None = None) -> float:
    # Sprach-Filter
    lang = _detect_language(job)
    if lang not in (ctx.language_filter or []):
        return 0.0

    # Region-Filter
    if ctx.region_filter and not _matches_region(job, ctx.region_filter):
        return 0.0

    job_tokens = _tokenize(job.get("title", "")) | _tokenize(job.get("description", ""))
    if not job_tokens:
        return 0.0

    skill_hits = len(cv.skills & job_tokens)
    title_hits = len(cv.titles & job_tokens) + sum(
        1 for t in cv.titles if t in (job.get("title") or "").lower()
    )
    freetext_hits = len(cv.freetext & job_tokens)

    raw_score = skill_hits * 3 + title_hits * 2 + freetext_hits * 1

    # Normalisierungs-Pool: bei Text-Blob-CVs (PDF/DOCX-Upload, freetext kann
    # 300+ Tokens inkl. Adresse/Boilerplate enthalten) würde der echte
    # CV-Pool den Score auf einstellige Prozent verdünnen. Cap bei 50 — das
    # entspricht ungefähr der Größe einer typischen strukturierten Skill-Liste.
    raw_pool = len(cv.skills) * 3 + len(cv.titles) * 2 + len(cv.freetext)
    effective_pool = max(min(raw_pool, 50), 1)
    pct = min(raw_score / effective_pool, 1.0) * 100
    score_value = round(pct, 2)

    # Adaptive-Learning Adjustment (optional, backward-compat)
    if user is not None and raw_job_id is not None:
        score_value = compute_score_adjustment(user, raw_job_id, score_value)

    return score_value
