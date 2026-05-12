# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Cover Letter Service — Analysis & Generation mit Confidence-Scores.

Two-phase pipeline:
  1. analyze(cv_text, job_description) → JSON mit matched_skills/experience/interpreted
  2. generate(...) → HTML mit data-confidence-Attributen pro <p>

Beide Phasen nutzen den ai_provider_client (oder Anthropic-Fallback).
"""
from __future__ import annotations
import os
import re
import json
import logging
from typing import Optional, Dict, Any
from services import ai_provider_client

logger = logging.getLogger(__name__)

# Confidence-Schwellen für Frontend-Coloring
CONFIDENCE_FACT = 0.85       # >= = grün (faktisch)
CONFIDENCE_MOSTLY = 0.70     # >= = gelb (überwiegend faktisch)
                              # < 0.70 = orange (interpretiert)

LENGTH_WORDS = {
    'short': '200-300',
    'medium': '350-450',
    'long': '550-700',
}

DEFAULT_MODEL = 'claude-haiku-4-5-20251001'


def _get_direct_anthropic_client():
    """Lazy import Anthropic SDK für Fallback-Modus (kein ai-provider-service)."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return None
    try:
        from anthropic import Anthropic
        return Anthropic(api_key=api_key)
    except ImportError:
        return None


def _call_ai(system_prompt: str, user_prompt: str, user_id: Optional[str] = None,
             provider: str = 'claude', model: str = DEFAULT_MODEL,
             max_tokens: int = 2000,
             fallback_kwargs: Optional[Dict[str, Any]] = None) -> str:
    """Sendet Chat-Call via ai_provider_client (wenn enabled) oder direkt an Anthropic.

    Optional fallback_kwargs (z.B. {'fallback_provider': 'claude', 'fallback_model': '...',
    'fallback_config': {'api_key': '...'}}) wird an client.chat() durchgereicht.

    Returns: Text der KI-Antwort.
    Raises: RuntimeError wenn weder Service-Modus noch ANTHROPIC_API_KEY verfügbar.
    """
    if ai_provider_client.is_enabled() and user_id:
        client = ai_provider_client.get_client()
        response = client.chat(
            user_id=user_id, provider=provider, model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            **(fallback_kwargs or {}),
        )
        return (response.content[0].text if response.content else '').strip()

    # Fallback: direkter Anthropic-Call
    client = _get_direct_anthropic_client()
    if client is None:
        raise RuntimeError("Weder AI_PROVIDER_SERVICE_URL noch ANTHROPIC_API_KEY gesetzt")
    response = client.messages.create(
        model=model, max_tokens=max_tokens, system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return (response.content[0].text if response.content else '').strip()


def _extract_json(text: str) -> Dict[str, Any]:
    """Extrahiert JSON aus KI-Output (entfernt Markdown, balanced braces).

    Mistral/Llama/Ollama-Modelle liefern oft erklärenden Text drumherum oder
    schließende Klammern an falscher Stelle. Wir nutzen balanced-brace-matching
    statt greedy regex und loggen den raw output bei Fehler für Debugging.
    """
    # Entferne Markdown-Codefences + <think>-Blöcke (reasoning models)
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    cleaned = re.sub(r'```(?:json)?\n?', '', cleaned)
    cleaned = cleaned.replace('```', '').strip()

    # Balanced-brace-matching: erstes { bis zur matchenden }
    start = cleaned.find('{')
    if start < 0:
        logger.error("Kein '{' in KI-Output gefunden. Raw output: %s", text[:500])
        raise ValueError(f"KI-Antwort enthält kein JSON-Objekt. Bitte erneut versuchen.")

    depth = 0
    in_string = False
    escape = False
    end = -1
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if end < 0:
        logger.error("Unbalanced braces in KI-Output. Raw: %s", text[:500])
        raise ValueError("KI-Antwort hat unvollständiges JSON. Bitte erneut versuchen.")

    candidate = cleaned[start:end]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        logger.error("JSON-Parse-Fehler: %s\nKandidat: %s\nRaw KI-Output: %s",
                     e, candidate[:500], text[:500])
        raise ValueError(
            f"KI-Antwort ist kein valides JSON: {e.msg}. "
            f"Modell-Wahl prüfen — Cover-Letter braucht ein starkes Modell "
            f"(Claude, GPT-4, Llama-70B). Mistral-7B oder kleinere Modelle "
            f"liefern oft kein sauberes JSON."
        )


ANALYSIS_SYSTEM = """Du bist ein präziser Recruiting-Analyst. Du vergleichst einen CV mit einer Stellenausschreibung und gibst NUR FAKTEN zurück, keine Erfindungen.

WICHTIG:
- confidence 0.85-1.0 = direkt aus CV ableitbar (z.B. Skill steht wörtlich drin)
- confidence 0.70-0.85 = teilweise faktisch (CV erwähnt verwandtes)
- confidence < 0.70 = interpretiert/abgeleitet (nicht direkt im CV)
- confidence < 0.3 = NICHT verwenden (zu spekulativ)

Antworte AUSSCHLIEßLICH mit validem JSON, keine Markdown-Codeblöcke, kein Erklärungstext drumherum."""


GENERATION_SYSTEM = """Du bist ein professioneller Bewerbungstexter. Du schreibst deutsche Anschreiben, die NUR auf vorgegebenen Fakten basieren — niemals erfindest du Skills, Projekte oder Erfahrungen.

REGELN:
- Jeder Absatz beginnt mit HTML-Kommentar <!-- confidence: 0.XX -->
- Nutze NUR die in der Analyse vorhandenen Fakten
- Schreibe in HTML mit <p>-Tags, KEIN Markdown
- Schreibe natürliches Deutsch, vermeide Floskeln"""


class CoverLetterService:
    """Zweistufige Anschreiben-Generierung mit Confidence-Scoring."""

    def analyze(self, cv_text: str, job_description: str,
                user_id: Optional[str] = None,
                provider: str = 'claude',
                model: Optional[str] = None,
                fallback_kwargs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Phase 1: CV ↔ Job-Posting Matching mit Confidence-Scores.

        Returns dict mit Keys:
          matched_skills: [{skill, cv_source, job_requirement, confidence}]
          matched_experience: [{experience, cv_source, alignment, confidence}]
          interpreted_requirements: [{requirement, reasoning, confidence}]
          missing_or_weak: [{requirement, cv_status, confidence_of_fit}]
        """
        if not cv_text.strip() or not job_description.strip():
            raise ValueError("CV-Text und Job-Beschreibung dürfen nicht leer sein")

        user_prompt = f"""Analysiere folgenden CV gegen folgende Stellenausschreibung.

=== CV ===
{cv_text}

=== STELLENAUSSCHREIBUNG ===
{job_description}

Gib EIN JSON-Objekt zurück mit dieser Struktur (keine Markdown-Codefences):
{{
  "matched_skills": [
    {{"skill": "Python", "cv_source": "Zeile/Sektion im CV", "job_requirement": "exakte Anforderung", "confidence": 0.95}}
  ],
  "matched_experience": [
    {{"experience": "5 Jahre Backend", "cv_source": "Position bei XYZ 2020-2025", "alignment": "Senior-Rolle", "confidence": 0.92}}
  ],
  "interpreted_requirements": [
    {{"requirement": "Startup-Mentalität", "reasoning": "abgeleitet aus 'fast-paced' im Posting", "confidence": 0.65}}
  ],
  "missing_or_weak": [
    {{"requirement": "Kubernetes", "cv_status": "nicht erwähnt", "confidence_of_fit": 0.2}}
  ]
}}"""

        text = _call_ai(ANALYSIS_SYSTEM, user_prompt, user_id=user_id,
                        provider=provider, model=model or DEFAULT_MODEL, max_tokens=2000,
                        fallback_kwargs=fallback_kwargs)
        analysis = _extract_json(text)

        # Defensive: sicherstellen dass alle erwarteten Keys existieren
        for key in ('matched_skills', 'matched_experience', 'interpreted_requirements', 'missing_or_weak'):
            analysis.setdefault(key, [])

        return analysis

    def generate(self, company_name: str, job_title: str, analysis: Dict[str, Any],
                 tone: str = 'professional', length: str = 'medium',
                 focus: str = 'balanced', user_id: Optional[str] = None,
                 applicant_name: Optional[str] = None,
                 provider: str = 'claude',
                 model: Optional[str] = None,
                 fallback_kwargs: Optional[Dict[str, Any]] = None) -> str:
        """Phase 2: Anschreiben-Text basierend auf Analyse generieren.

        Returns: HTML-String mit <p data-confidence="0.XX">…</p>-Absätzen.
        """
        word_count = LENGTH_WORDS.get(length, LENGTH_WORDS['medium'])
        analysis_json = json.dumps(analysis, ensure_ascii=False, indent=2)
        applicant_line = f"Bewerber: {applicant_name}" if applicant_name else ""

        user_prompt = f"""Schreibe ein deutsches Anschreiben für {company_name} ({job_title}).

{applicant_line}

Nutze AUSSCHLIESSLICH diese Fakten aus der Analyse:
{analysis_json}

ANFORDERUNGEN:
- Ton: {tone} (professional|casual|technical)
- Länge: {word_count} Wörter
- Fokus: {focus} (technical|leadership|projects|balanced)
- KEINE Items mit confidence < 0.3 verwenden
- Jeder <p>-Absatz beginnt mit <!-- confidence: 0.XX --> (entspricht höchster verwendeter confidence im Absatz)
- Format: nur HTML, keine Markdown-Codefences

BEISPIEL:
<!-- confidence: 0.95 -->
<p>Sehr geehrte Damen und Herren, mit großem Interesse habe ich Ihre Ausschreibung gelesen…</p>

<!-- confidence: 0.85 -->
<p>Meine 5-jährige Python-Erfahrung deckt sich genau mit Ihrer Anforderung…</p>

Gib NUR die HTML-Absätze zurück, keine Erklärung."""

        raw_html = _call_ai(GENERATION_SYSTEM, user_prompt, user_id=user_id,
                            provider=provider, model=model or DEFAULT_MODEL, max_tokens=2000,
                            fallback_kwargs=fallback_kwargs)
        # Entferne eventuelle Markdown-Codefences
        raw_html = re.sub(r'```(?:html)?\n?', '', raw_html).replace('```', '').strip()
        return self._inject_confidence_attributes(raw_html)

    @staticmethod
    def _inject_confidence_attributes(html: str) -> str:
        """Wandelt <!-- confidence: 0.95 --> Kommentare in data-confidence-Attribute um.

        Der nächste <p>-Tag nach einem Confidence-Kommentar bekommt das Attribut.
        Fehlt ein Kommentar, wird default 0.85 (fact-grenze) gesetzt.
        """
        out_lines = []
        pending_confidence: Optional[str] = None
        for line in html.splitlines():
            m = re.search(r'<!--\s*confidence:\s*([\d.]+)\s*-->', line)
            if m:
                pending_confidence = m.group(1)
                # Comment-only Zeile überspringen
                stripped = re.sub(r'<!--.*?-->', '', line).strip()
                if not stripped:
                    continue
                line = stripped
            if '<p>' in line and pending_confidence is not None:
                line = line.replace('<p>', f'<p data-confidence="{pending_confidence}">', 1)
                pending_confidence = None
            elif '<p>' in line:
                # Default Confidence falls kein Kommentar davor stand
                line = line.replace('<p>', '<p data-confidence="0.85">', 1)
            out_lines.append(line)
        return '\n'.join(l for l in out_lines if l.strip())
