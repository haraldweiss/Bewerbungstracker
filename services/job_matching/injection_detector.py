# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Erkennt typische Prompt-Injection-Muster in untrusted Job-Descriptions.

Defense-in-Depth-Schicht: System-Prompt und untrusted_data-Tags sind die
primäre Verteidigung. Dieser Detector ist eine zusätzliche Heuristik, um
verdächtige Inhalte beim Crawl zu flaggen — der User sieht im UI ein
Warning-Badge bevor er den Match übernimmt.

Bewusst konservativ: lieber ein paar False-Positives bei pathologischen
Stellenanzeigen als geheime Anweisungen durchschlüpfen lassen.
"""

from __future__ import annotations
import re
from typing import List

# Tuple: (compiled-regex, label).
# Labels werden 1:1 in JobMatch.suspicious_reasons gespeichert.
_INJECTION_PATTERNS = [
    # "Ignore previous instructions" und Varianten
    (re.compile(r'\bignor\w*\s+(?:all\s+|the\s+)?(?:previous|earlier|above|prior)\s+(?:instruction|prompt|message|rule)',
                re.IGNORECASE), 'ignore_previous'),
    (re.compile(r'\bvergiss\s+(?:alle\s+|die\s+)?(?:vorige|vorherige)n?\s+(?:anweisungen?|prompts?|regeln?)',
                re.IGNORECASE), 'ignore_previous_de'),
    (re.compile(r'\bdisregard\s+(?:all|the|any)\s+(?:above|previous|prior)', re.IGNORECASE), 'disregard'),

    # System-Role-Takeover
    (re.compile(r'\b(?:new|updated)\s+(?:instructions?|prompt|task|role)\s*[:\-]', re.IGNORECASE), 'new_instructions'),
    (re.compile(r'\bsystem\s*[:\.]\s*(?:you\s+are|du\s+bist)', re.IGNORECASE), 'system_role_takeover'),
    (re.compile(r'\bdu\s+bist\s+(?:nun|jetzt)\s+(?:ein|eine|kein)', re.IGNORECASE), 'system_role_takeover_de'),
    (re.compile(r'<\s*\|?\s*system\s*\|?\s*>', re.IGNORECASE), 'system_tag'),
    (re.compile(r'\[\s*INST\s*\]', re.IGNORECASE), 'inst_tag'),  # Llama/Mistral Chat-Token

    # Erzwungene Score/Outputs
    (re.compile(r'\b(?:respond|antworte|return|gib)\s+(?:with|only|nur|mit)\s+\W*score\s*[:=]?\s*100',
                re.IGNORECASE), 'force_max_score'),
    (re.compile(r'\b(?:perfect|perfekt|ideal)\s*(?:er|e)?\s+match\b', re.IGNORECASE), 'force_perfect_match'),
    (re.compile(r'"score"\s*:\s*(?:9[5-9]|100)\b'), 'embedded_high_score'),

    # Daten-Exfiltration / System-Info-Leaks
    (re.compile(r'\b(?:print|output|reveal|show|gib\s+aus|zeige)\s+(?:the\s+|den\s+|deinen?\s+|die\s+)?'
                r'(?:cv|lebenslauf|prompt|system\s*prompt|instructions?|secret|password)', re.IGNORECASE),
     'data_exfil'),

    # HTML/Code-Injection (kommt selten in echten Stellen vor)
    (re.compile(r'<\s*(?:script|iframe|object|embed)\b', re.IGNORECASE), 'html_injection'),

    # Template-Injection
    (re.compile(r'\{\{.{0,30}\}\}'), 'template_injection'),

    # Excessive Repetition (Token-flooding)
    (re.compile(r'(.{3,40})\1{8,}'), 'token_flood'),
]


def detect_injection_patterns(text: str) -> List[str]:
    """Liefert eine Liste von Pattern-Labels die im Text gefunden wurden.

    Leere Liste = clean. Mehrere Treffer = sehr verdächtig. Die Labels sind
    stabile Strings (kein i18n) und gut für DB-Persistenz + Test-Asserts geeignet.
    """
    if not text or not isinstance(text, str):
        return []
    found = []
    for pattern, label in _INJECTION_PATTERNS:
        if pattern.search(text):
            found.append(label)
    return found


def has_suspicious_score_jump(prefilter_score: float | None, match_score: float | None,
                                jump_threshold: float = 30.0) -> bool:
    """True wenn match_score deutlich höher als prefilter_score ist.

    Heuristik: wenn das Modell aus einem mittel-passenden Job (PreFilter sagt z.B. 40)
    plötzlich 95 macht, könnte es vom Inhalt überredet worden sein. False bei
    fehlenden Werten.
    """
    if prefilter_score is None or match_score is None:
        return False
    return (match_score - prefilter_score) > jump_threshold
