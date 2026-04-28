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
import re
from dataclasses import dataclass

from services.job_matching.cv_tokenizer import CVTokens


_TOKEN_RE = re.compile(r"[a-zA-ZäöüÄÖÜß0-9]+(?:[.\+#][a-zA-ZäöüÄÖÜß0-9]+)*")
_REMOTE_RE = re.compile(r"\bremote\b|\bhomeoffice\b|fully\s+remote", re.IGNORECASE)
_PLZ_RE = re.compile(r"\b\d{5}\b")


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


def score_job(cv: CVTokens, job: dict, ctx: PrefilterContext) -> float:
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
    cv_size = max(len(cv.skills) * 3 + len(cv.titles) * 2 + len(cv.freetext), 1)
    pct = min(raw_score / cv_size, 1.0) * 100
    return round(pct, 2)
