"""CV-Tokenizer für Pre-Filter-Scoring.

Extrahiert aus dem cv_data_json eines Users drei Token-Mengen:
- skills (Skill-Liste, z.B. "react", "python")
- titles (Job-Titel-Historie)
- freetext (Tokens aus Summary/Cover-Letter, lowercased)

Akzeptiert ZWEI cv_data_json-Schemas:

1. Strukturiert: ``{"cv": {"skills": [...], "experiences": [...], "summary": "..."}}``
   — vom hypothetischen CV-Editor in Phase 1/2 vorgesehen.

2. Text-Blob: ``{"cvData": {"fileName": "...", "text": "<volltext>"}, ...}``
   — tatsächliches Format des bestehenden Frontend-CV-Uploads (PDF/DOCX
   → Mammoth/pdf.js → Plaintext-Extraktion in einen `text`-String).

Bei Format 2 wandert der ganze CV-Text in `freetext` (keine strukturierte
Skill-Trennung möglich). Stop-Wörter (Adress-/Datum-Boilerplate) werden
NICHT herausgefiltert — die Hoffnung ist, dass die Job-Description bei
einem echten Match auch einige Skill-Wörter enthält und die Boilerplate
einfach nicht overlappt.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import re


_TOKEN_RE = re.compile(r"[a-zA-ZäöüÄÖÜß0-9]+(?:[.\+#][a-zA-ZäöüÄÖÜß0-9]+)*")


@dataclass
class CVTokens:
    skills: set = field(default_factory=set)
    titles: set = field(default_factory=set)
    freetext: set = field(default_factory=set)


def _tokenize_text(text: str) -> set:
    if not text:
        return set()
    return {m.group().lower() for m in _TOKEN_RE.finditer(text)}


def tokenize_cv(cv_data: dict | None) -> CVTokens:
    """Extrahiert Tokens aus cv_data_json.

    Akzeptiert beide Frontend-Formate (siehe Modul-Docstring).
    """
    tokens = CVTokens()
    if not cv_data or not isinstance(cv_data, dict):
        return tokens

    # ─── Format 1: strukturiert ─────────────────────────────────────────
    cv = cv_data.get('cv') or {}
    if isinstance(cv, dict):
        for skill in cv.get('skills') or []:
            if isinstance(skill, str):
                tokens.skills.add(skill.strip().lower())

        for exp in cv.get('experiences') or []:
            if isinstance(exp, dict) and exp.get('title'):
                tokens.titles.add(exp['title'].strip().lower())

        for field_name in ('summary', 'bio', 'cover_letter'):
            if cv.get(field_name):
                tokens.freetext |= _tokenize_text(cv[field_name])

    # ─── Format 2: Text-Blob aus PDF/DOCX-Upload ────────────────────────
    blob = cv_data.get('cvData') or {}
    if isinstance(blob, dict):
        text = blob.get('text')
        if isinstance(text, str) and text.strip():
            tokens.freetext |= _tokenize_text(text)

    return tokens
