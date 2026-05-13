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

# Known valid Claude models (from Claude's API docs as of 2026-05)
KNOWN_MODELS = {
    'claude-opus-4-7',
    'claude-sonnet-4-6',
    'claude-haiku-4-5-20251001',
    # Legacy models
    'claude-3-5-sonnet',
    'claude-3-opus',
    'claude-3-sonnet',
}

# Known invalid/deprecated models (from production errors)
INVALID_MODELS = {
    'claude-3-5-sonnet-20241022',  # 404: model not found (never existed in API)
}


def _normalize_model(model: Optional[str]) -> str:
    """Returns model if valid, otherwise DEFAULT_MODEL.

    - Checks explicit KNOWN_MODELS list first
    - Rejects INVALID_MODELS
    - Accepts any claude-* model (for forward compatibility)
    - Falls back to DEFAULT_MODEL for anything else
    """
    if not model or not isinstance(model, str):
        return DEFAULT_MODEL
    model = model.strip()
    if not model:
        return DEFAULT_MODEL

    # Reject known invalid models first
    if model in INVALID_MODELS:
        logger.warning('Invalid model "%s", falling back to %s', model, DEFAULT_MODEL)
        return DEFAULT_MODEL

    # Check if it's a known good model
    if model in KNOWN_MODELS:
        return model

    # Accept claude-* models for forward compatibility, but log unknown ones
    if model.startswith('claude-'):
        if model not in KNOWN_MODELS:
            logger.debug('Using unknown claude model "%s" (not in KNOWN_MODELS)', model)
        return model

    # Unknown model → fall back to default
    logger.warning('Unknown model "%s", falling back to %s', model, DEFAULT_MODEL)
    return DEFAULT_MODEL


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
    # Normalize model first
    model = _normalize_model(model)

    if ai_provider_client.is_enabled() and user_id:
        client = ai_provider_client.get_client()
        try:
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
        except Exception as e:
            # Provider unavailable or failed → fall back to direct Anthropic
            logger.warning('AI Provider Service failed (%s: %s), falling back to direct Anthropic', provider, e)

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
- Schreibe natürliches, authentisches Deutsch — als würde ein Mensch es sprechen

⛔ ABSOLUT ZU VERMEIDEN — Diese Wörter verraten ChatGPT:
  HIGH RISK: "eintauchen", "versiert", "navigieren", "gewährleisten", "dynamisches Umfeld", "hiermit bewerbe ich mich"
  MEDIUM RISK: "mit Begeisterung", "präzise", "umfassend", "ganzheitlich"
  PATTERN RISK: "nicht nur...sondern auch", "tauchen Sie ein in", mehrere Gedankenstriche pro Absatz

🎯 STATTDESSEN NUTZEN:
  - Konkrete Beispiele statt generische Floskeln
  - "Ich freue mich auf..." statt "Mit Begeisterung lese ich..."
  - "Ihre Anforderung passt zu meiner Erfahrung..." statt "Meine versierte Expertise..."
  - "Ich interessiere mich für..." statt "Hiermit bewerbe ich mich..."
  - Kommas oder Punkte statt "nicht nur...sondern auch"
  - Max. 1 Gedankenstrich pro Absatz, besser: gar keine

✅ AUTHENTIZITÄT-Check vor dem Output:
  - Lies den Text durch die Augen eines Personalers — wirkt er natürlich?
  - Kein Satz sollte wirken, als hätte ihn eine KI geschrieben
  - Nutze deine Kenntnisse über echte Bewerbungen, nicht Standard-Templates"""


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
                        provider=provider, model=model, max_tokens=2000,
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
                            provider=provider, model=model, max_tokens=2000,
                            fallback_kwargs=fallback_kwargs)
        # Entferne eventuelle Markdown-Codefences
        raw_html = re.sub(r'```(?:html)?\n?', '', raw_html).replace('```', '').strip()
        # Sanitize KI-verdächtige Wörter (Fallback-Filter)
        raw_html = self._sanitize_ai_suspicious_words(raw_html)
        return self._inject_confidence_attributes(raw_html)

    @staticmethod
    def _sanitize_ai_suspicious_words(html: str) -> str:
        """Fallback-Filter: Ersetzt/entfernt verdächtige KI-Wörter.

        Dies ist ein Sicherheitsnetz, falls die KI sie trotzdem nutzt.
        Nutzt Case-Insensitive Matching bei Wort-Grenzen.
        """
        # Mapping: verdächtiges Wort -> Replacement
        replacements = {
            r'\beintauchen(d|en|e|es|s|r|m)?\b': 'vertiefen',
            r'\bversiert(e|en|er|es|em|a|as)?\b': 'erfahren',
            r'\bnavigieren(d|en|e|es|t|)?\b': 'bewältigen',
            r'\bgewährleisten(d|en|e|s|t|)?\b': 'sicherstellen',
            r'\b[Dd]ynamisches?\s+Umfeld\b': 'anspruchsvollen Umfeld',
            r'\bhiermit\s+bewerbe\s+ich\s+mich\b': 'ich bewerbe mich',
            r'\bHiermit\s+bewerbe\s+ich\s+mich\b': 'Ich bewerbe mich',
            r'\bmit\s+Begeisterung\b': 'mit großem Interesse',
            r'\bpräzise(n|r|m|s|)?\b': 'sorgfältig',
            r'\bumfassend(e|en|er|es|em|a|as)?\b': 'gründlich',
            r'\bganzheitlich(e|en|er|es|em|a|as)?\b': 'vollständig',
            r'\btauchen\s+Sie\s+ein\s+in\s+eine\s+Welt\b': 'entdecken Sie',
            # Mehrfache Gedankenstriche: ersetze mit Komma
            r'\s–\s[^–]*–\s': ', ',
        }

        result = html
        for pattern, replacement in replacements.items():
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        return result

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

    @staticmethod
    def check_ai_detectability(html: str) -> Dict[str, Any]:
        """Prüft HTML auf KI-verdächtige Wörter/Muster.

        Returns dict mit:
          has_risks: bool
          risk_level: 'low'|'medium'|'high'
          findings: [
            {
              risk: 'high'|'medium'|'low',
              word_or_pattern: 'eintauchen',
              reason: 'ChatGPT-typische Formulierung',
              context: 'Ich möchte tief eintauchen...',  (sentence snippet)
              count: 2
            }
          ]
          recommendations: [str, ...]
        """
        # Definiere verdächtige Wörter mit Risiko-Level
        SUSPICIOUS_WORDS = {
            # HIGH RISK — sehr ChatGPT-typisch
            'high': [
                (r'\beintauchen\b', 'ChatGPT-typische Übersetzung von "delve"'),
                (r'\bversiert\b', 'Übermäßig formal, sehr KI-verdächtig'),
                (r'\bnavigieren\b', 'Selten in Bewerbungen, ChatGPT-Muster'),
                (r'\bgewährleisten\b', 'Zu steif, selten im natürlichen Deutsch'),
                (r'\bdynamisch(?:e[ns]?)?\s+Umfeld', 'Klassische KI-Phrase'),
                (r'\bhiermit\s+bewerbe\s+ich\s+mich\b', 'Überalte formale Eröffnung'),
                (r'\bnicht\s+nur\s*[^,]*?,\s*sondern\s+auch\b', '"Nicht nur...sondern auch" ist KI-Signal'),
            ],
            # MEDIUM RISK — typisch aber nicht eindeutig
            'medium': [
                (r'\bmit\s+Begeisterung\b', 'Zu gewollt, generisches Phraschen-Deutsch'),
                (r'\bpräzise\b', 'Übernutzung durch KI in Bewerbungen'),
                (r'\bumfassend\b', 'Generische KI-Floskeln'),
                (r'\bganzheitlich\b', 'Übermäßig verwendet von KI'),
                (r'\btauchen\s+Sie\s+ein\s+in\s+eine\s+Welt', 'Sehr typisch für ChatGPT'),
                (r'\bgedankenstrich.*gedankenstrich', 'Mehrere Gedankenstriche pro Absatz = KI-Signal'),
            ],
            # LOW RISK — vorsichtiger, aber verdächtig bei Häufung
            'low': [
                (r'\b(werden|kann|haben)\b', 'Übernutzung von Hilfsverben (nur bei 5+ Hits)',
                 'count_threshold'),  # besonderes Flag: nur zählen, wenn Häufung
            ],
        }

        # Entferne HTML-Tags für Text-Analyse
        text = re.sub(r'<[^>]+>', '', html)
        findings = []

        for risk_level, patterns in SUSPICIOUS_WORDS.items():
            for pattern_tuple in patterns:
                if len(pattern_tuple) == 3 and pattern_tuple[2] == 'count_threshold':
                    pattern, reason = pattern_tuple[0], pattern_tuple[1]
                    # Zähle Vorkommen, warnung nur bei 5+
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    if len(matches) >= 5:
                        findings.append({
                            'risk': risk_level,
                            'word_or_pattern': pattern.replace(r'\b', '').replace('\\', ''),
                            'reason': reason,
                            'count': len(matches),
                            'context': None,  # zu viele Matches für Kontext
                        })
                else:
                    pattern, reason = pattern_tuple[0], pattern_tuple[1]
                    matches = list(re.finditer(pattern, text, re.IGNORECASE))
                    if matches:
                        # Extrahiere Kontext (±30 chars)
                        contexts = []
                        for m in matches[:2]:  # max 2 Beispiele
                            start = max(0, m.start() - 30)
                            end = min(len(text), m.end() + 30)
                            snippet = text[start:end].replace('\n', ' ')
                            if start > 0:
                                snippet = '...' + snippet
                            if end < len(text):
                                snippet = snippet + '...'
                            contexts.append(snippet.strip())

                        findings.append({
                            'risk': risk_level,
                            'word_or_pattern': pattern.replace(r'\b', '').replace('\\', ''),
                            'reason': reason,
                            'count': len(matches),
                            'examples': contexts[:1],
                        })

        # Aggregiere Risk-Level
        risk_levels = [f['risk'] for f in findings]
        if 'high' in risk_levels:
            overall_risk = 'high'
        elif 'medium' in risk_levels:
            overall_risk = 'medium'
        elif risk_levels:
            overall_risk = 'low'
        else:
            overall_risk = None

        # Empfehlungen basierend auf Findings
        recommendations = []
        if overall_risk == 'high':
            recommendations.append(
                '🚨 HOHE WARNUNG: Mehrere ChatGPT-typische Wörter erkannt. '
                'Personaler könnten KI-Generierung vermuten.'
            )
        elif overall_risk == 'medium':
            recommendations.append(
                '⚠️ MITTLERE WARNUNG: Einige KI-verdächtige Formulierungen erkannt. '
                'Überarbeiten würde helfen.'
            )
        else:
            recommendations.append('✅ Keine kritischen KI-Indikatoren erkannt.')

        recommendations.extend([
            'Nutze mehr persönliche Beispiele und konkrete Projekte',
            'Ersetze generische Floskeln durch deine eigenen Worte',
            'Lies das Anschreiben laut vor — Übernatürlichkeit fällt sofort auf',
        ])

        return {
            'has_risks': bool(findings),
            'risk_level': overall_risk,
            'finding_count': len(findings),
            'findings': sorted(findings, key=lambda f: {'high': 0, 'medium': 1, 'low': 2}[f['risk']]),
            'recommendations': recommendations,
        }
