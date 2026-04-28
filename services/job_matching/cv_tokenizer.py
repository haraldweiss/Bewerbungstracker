"""CV-Tokenizer für Pre-Filter-Scoring.

Extrahiert aus dem cv_data_json eines Users drei Token-Mengen:
- skills (Skill-Liste, z.B. "react", "python")
- titles (Job-Titel-Historie)
- freetext (Tokens aus Summary/Cover-Letter, lowercased)

Das Format orientiert sich am bestehenden cv_data_json-Schema.
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

    Args:
        cv_data: dict mit Schlüssel 'cv' → {skills, experiences, summary, ...}
    """
    tokens = CVTokens()
    if not cv_data or not isinstance(cv_data, dict):
        return tokens

    cv = cv_data.get('cv') or {}

    # Skills: Liste von Strings
    for skill in cv.get('skills') or []:
        if isinstance(skill, str):
            tokens.skills.add(skill.strip().lower())

    # Titel: aus experiences[].title
    for exp in cv.get('experiences') or []:
        if isinstance(exp, dict) and exp.get('title'):
            tokens.titles.add(exp['title'].strip().lower())

    # Freetext: Summary, Bio, Cover-Letter-Templates
    for field_name in ('summary', 'bio', 'cover_letter'):
        if cv.get(field_name):
            tokens.freetext |= _tokenize_text(cv[field_name])

    return tokens
