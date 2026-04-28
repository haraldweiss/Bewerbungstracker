"""Claude-basierte Job-Bewertung (Phase A: nutzt Server-Key).

Phase B refactored das auf User-spezifische Provider — die Funktion
`match_job_with_claude` bleibt aber gleich, der `client` und `model`
kommen dann aus der Provider-Factory.
"""
import json as _json
from dataclasses import dataclass


PROMPT_TEMPLATE = """Du bewertest, wie gut die folgende Stellenausschreibung zu meinem CV passt.

MEIN CV (Zusammenfassung):
{cv_summary}

STELLENAUSSCHREIBUNG:
Titel: {title}
Standort: {location}
Beschreibung: {description}

Antworte AUSSCHLIESSLICH mit einem gültigen JSON-Objekt im Format:
{{"score": <0-100>, "reasoning": "<2-3 Sätze, deutsch>", "missing_skills": ["<skill1>", "<skill2>"]}}

Keine Erläuterungen drum herum. Nur das JSON-Objekt.
"""


@dataclass
class MatchResult:
    score: float
    reasoning: str
    missing_skills: list
    tokens_in: int
    tokens_out: int


def _build_prompt(cv_summary: str, job: dict) -> str:
    return PROMPT_TEMPLATE.format(
        cv_summary=cv_summary[:3000],
        title=job.get("title", ""),
        location=job.get("location", ""),
        description=(job.get("description") or "")[:5000],
    )


def match_job_with_claude(client, model: str, cv_summary: str, job: dict) -> MatchResult:
    """Ruft Claude auf, parst Antwort, gibt MatchResult zurück.

    Bei ungültiger JSON-Antwort: Fallback auf score=0, reasoning="fehlgeschlagen".
    Tokens werden immer geloggt (auch bei Fehler).
    """
    prompt = _build_prompt(cv_summary, job)
    response = client.messages.create(
        model=model,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    tokens_in = getattr(response.usage, "input_tokens", 0)
    tokens_out = getattr(response.usage, "output_tokens", 0)

    if text.startswith("```"):
        text = text.split("```", 2)[1].lstrip("json\n").strip()

    try:
        data = _json.loads(text)
        return MatchResult(
            score=float(data.get("score", 0)),
            reasoning=str(data.get("reasoning", "")),
            missing_skills=list(data.get("missing_skills") or []),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
    except Exception:
        return MatchResult(
            score=0,
            reasoning="Bewertung fehlgeschlagen (ungültiges JSON von Claude).",
            missing_skills=[],
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
