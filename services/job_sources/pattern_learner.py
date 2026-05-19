# SPDX-License-Identifier: AGPL-3.0-or-later
# (c) 2026 Harald Weiss
"""AI-gesteuerter Pattern-Lerner für Email-Job-Adapter.

Pipeline: fetch_sample_mails -> ai_learn_pattern -> compile_pattern ->
validate_pattern. Bei Hit-Rate >= Schwelle wird das Pattern als neue Row
in `learned_email_patterns` gespeichert (alte deaktiviert).
"""
from __future__ import annotations
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

try:
    from jsonschema import Draft7Validator
except ImportError:
    Draft7Validator = None

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CompiledPattern:
    """Aus JSON-Pattern gebaute Regex-Objekte (frozen)."""
    body_card_re: "re.Pattern"
    subject_re: "re.Pattern"
    title_blacklist_re: "re.Pattern | None"
    company_blacklist_separator_re: "re.Pattern | None"
    url_labels: tuple[str, ...]


_FIELD_BUILDERS = {
    "title":    r"[ \t]*(?P<title>\S[^\r\n]{2,200}\S)\s*\r?\n",
    "company":  r"[ \t]*(?P<company>\S[^\r\n]{1,150}\S)\s*\r?\n",
    "location": r"[ \t]*(?P<location>\S[^\r\n]{1,80}\S)\s*\r?\n",
    "extra":    r"[^\r\n]*\r?\n",
}


def compile_pattern(pattern: dict) -> CompiledPattern:
    """Baut Regex-Objekte aus dem JSON-Pattern.

    Raises:
        ValueError wenn fields_before_url unbekannte Werte enthält.
        re.error wenn ein gebautes Regex syntaktisch ungültig ist.
    """
    body_card = pattern["body_card"]
    parts = []
    for field in body_card["fields_before_url"]:
        if field not in _FIELD_BUILDERS:
            raise ValueError(f"Unknown field: {field}")
        parts.append(_FIELD_BUILDERS[field])
    n_sep = body_card["separator_lines_allowed"]
    parts.append(rf"(?:[^\r\n]*\r?\n){{0,{n_sep}}}?")
    labels_alt = "|".join(re.escape(lbl) for lbl in body_card["url_labels"])
    parts.append(rf"\s*(?:{labels_alt})\s*:?\s*")
    parts.append(r"(?P<url>https?://[^\s\r\n)<>\"']+)")
    body_card_re = re.compile(
        "^" + "".join(parts),
        re.IGNORECASE | re.MULTILINE,
    )

    sp = pattern["subject_pattern"]
    prefix_alt = "|".join(re.escape(kw) for kw in sp["prefix_keywords"]) or "."
    sep = sp["separator"]
    prefix_part = (
        rf"(?:(?:{prefix_alt})\s*:?\s*)?"
        if sp["prefix_optional"]
        else rf"(?:{prefix_alt})\s*:?\s*"
    )
    subject_re = re.compile(
        rf"^{prefix_part}(?P<title>.+?)\s+(?:{sep})\s+(?P<company>.+?)\s*$",
        re.IGNORECASE,
    )

    tb = pattern["filters"]["title_blacklist"]
    title_blacklist_re = None
    if tb:
        title_blacklist_re = re.compile(
            "|".join(f"(?:{phrase})" for phrase in tb),
            re.IGNORECASE,
        )

    cbs = pattern["filters"]["company_blacklist_separators"]
    company_blacklist_separator_re = None
    if cbs:
        company_blacklist_separator_re = re.compile(
            "^(?:" + "|".join(re.escape(s) for s in cbs) + r")+$"
        )

    return CompiledPattern(
        body_card_re=body_card_re,
        subject_re=subject_re,
        title_blacklist_re=title_blacklist_re,
        company_blacklist_separator_re=company_blacklist_separator_re,
        url_labels=tuple(body_card["url_labels"]),
    )


PATTERN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["subject_pattern", "body_card", "filters"],
    "properties": {
        "subject_pattern": {
            "type": "object",
            "additionalProperties": False,
            "required": ["prefix_optional", "prefix_keywords", "separator"],
            "properties": {
                "prefix_optional": {"type": "boolean"},
                "prefix_keywords": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 80},
                    "maxItems": 20,
                },
                "separator": {"type": "string", "maxLength": 50},
            },
        },
        "body_card": {
            "type": "object",
            "additionalProperties": False,
            "required": ["url_labels", "fields_before_url", "separator_lines_allowed"],
            "properties": {
                "url_labels": {
                    "type": "array", "minItems": 1, "maxItems": 10,
                    "items": {"type": "string", "maxLength": 80},
                },
                "fields_before_url": {
                    "type": "array", "minItems": 1, "maxItems": 5,
                    "items": {"enum": ["title", "company", "location", "extra"]},
                },
                "separator_lines_allowed": {
                    "type": "integer", "minimum": 0, "maximum": 20,
                },
            },
        },
        "filters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["title_blacklist", "company_blacklist_separators"],
            "properties": {
                "title_blacklist": {
                    "type": "array", "maxItems": 50,
                    "items": {"type": "string", "maxLength": 200},
                },
                "company_blacklist_separators": {
                    "type": "array", "maxItems": 10,
                    "items": {"type": "string", "maxLength": 50},
                },
            },
        },
    },
}


def normalize_pattern(raw: dict) -> dict:
    """Best-effort-Normalisierung des AI-Outputs vor Schema-Validation.

    Schwache lokale LLMs (Ollama/qwen3-coder/etc.) halluzinieren oft
    zusaetzliche Top-Level-Keys (z.B. 'footer') oder benennen Felder um
    (z.B. body_card.fields statt body_card.fields_before_url). Statt
    direkt zu rejecten:
      1. Unbekannte Top-Level- und Sub-Level-Felder stillschweigend droppen
      2. Synonyme remappen (fields → fields_before_url)
      3. Fehlende required-Felder mit safe Defaults fuellen

    Schema-Validation laeuft danach gegen das normalisierte Dict — falls
    es immer noch nicht passt, ist's wirklich kaputt.
    """
    if not isinstance(raw, dict):
        raise ValueError("Pattern muss ein Dict sein")

    allowed_top = {"subject_pattern", "body_card", "filters"}
    out: dict = {k: raw[k] for k in raw if k in allowed_top}

    # ── subject_pattern ──────────────────────────────────────────────
    sp_raw = raw.get("subject_pattern") or {}
    if not isinstance(sp_raw, dict):
        sp_raw = {}
    out["subject_pattern"] = {
        "prefix_optional": bool(sp_raw.get("prefix_optional", True)),
        "prefix_keywords": [
            str(k)[:80]
            for k in (sp_raw.get("prefix_keywords") or [])
            if isinstance(k, str)
        ][:20],
        "separator": str(sp_raw.get("separator") or "bei|at|@")[:50],
    }

    # ── body_card ────────────────────────────────────────────────────
    bc_raw = raw.get("body_card") or {}
    if not isinstance(bc_raw, dict):
        bc_raw = {}
    # Synonym-Mapping: 'fields' → 'fields_before_url'
    fields_raw = bc_raw.get("fields_before_url")
    if fields_raw is None:
        fields_raw = bc_raw.get("fields")
    if not isinstance(fields_raw, list):
        fields_raw = ["title", "company", "location"]
    allowed_field_values = {"title", "company", "location", "extra"}
    fields_clean = [
        f for f in fields_raw
        if isinstance(f, str) and f in allowed_field_values
    ][:5]
    if not fields_clean:
        fields_clean = ["title", "company", "location"]

    url_labels = bc_raw.get("url_labels")
    if not isinstance(url_labels, list):
        url_labels = []
    url_labels_clean = [
        str(lbl)[:80] for lbl in url_labels if isinstance(lbl, str)
    ][:10]
    if not url_labels_clean:
        url_labels_clean = ["Jobangebot ansehen", "View job"]

    sep_lines_raw = bc_raw.get("separator_lines_allowed", 5)
    try:
        sep_lines = int(sep_lines_raw)
        sep_lines = max(0, min(20, sep_lines))
    except (TypeError, ValueError):
        sep_lines = 5

    out["body_card"] = {
        "url_labels": url_labels_clean,
        "fields_before_url": fields_clean,
        "separator_lines_allowed": sep_lines,
    }

    # ── filters ──────────────────────────────────────────────────────
    f_raw = raw.get("filters") or {}
    if not isinstance(f_raw, dict):
        f_raw = {}
    out["filters"] = {
        "title_blacklist": [
            str(s)[:200] for s in (f_raw.get("title_blacklist") or [])
            if isinstance(s, str)
        ][:50],
        "company_blacklist_separators": [
            str(s)[:50] for s in (f_raw.get("company_blacklist_separators") or [])
            if isinstance(s, str)
        ][:10],
    }

    return out


def validate_pattern_schema(pattern: dict) -> list[str]:
    """Returns list of validation error messages (empty list if valid).

    Uses jsonschema Draft7 strict mode (additionalProperties=False everywhere).
    """
    if Draft7Validator is None:
        raise RuntimeError("jsonschema library not installed")
    validator = Draft7Validator(PATTERN_JSON_SCHEMA)
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(pattern)
    ]


def fetch_sample_mails(
    user, platform: str, folder: str, lookback_days: int, n: int = 30,
) -> list[dict]:
    """Holt N Email-Samples via IMAP (delegiert an EmailJobsAdapter).

    Raises:
        ValueError wenn platform nicht in PROFILES.
        RuntimeError wenn User keine IMAP-Credentials hat.
    """
    from services.job_sources.email_jobs import EmailJobsAdapter, PROFILES
    if platform not in PROFILES:
        raise ValueError(f"Unknown platform: {platform}")

    host = user.imap_host
    imap_user = user.imap_user
    pw = user.decrypted_imap_password
    if not host or not imap_user or not pw:
        raise RuntimeError("User hat keine IMAP-Credentials")

    adapter = EmailJobsAdapter(
        config={"folder": folder, "lookback_days": lookback_days, "limit": n},
        user=user,
        platform_profile=PROFILES[platform],
    )
    return adapter._fetch_emails(host, imap_user, pw, folder, lookback_days, n)


# Universelles URL-Fallback-Pattern für Single-Job-Mails (Indeed-Style):
# subject_re matched → suche IRGENDEINE URL im Body, das reicht als
# Hit-Indikator. Wird nicht im echten Adapter genutzt, nur in
# validate_pattern für die Train-Bewertung.
_ANY_URL_RE = re.compile(r"https?://[^\s\r\n)<>\"']+")


def validate_pattern(
    compiled: CompiledPattern, samples: list[dict]
) -> tuple[float, list[dict]]:
    """Misst Hit-Rate auf Sample-Mails — Hit wenn body_card ODER subject greift.

    Zwei akzeptierte Parsing-Pfade (spiegelt den echten Adapter):
      1. body_card_re findet ≥1 valide Card (LinkedIn/XING-Digest-Stil)
      2. subject_re matched + Body enthaelt ≥1 URL (Indeed-Single-Job-Stil)

    Returns:
        (hit_rate, diagnostics)
        - hit_rate ∈ [0.0, 1.0]
        - diagnostics: liste mit {subject, matched: bool, card_count: int,
          via: str} pro Sample-Mail (via: 'body_card', 'subject', 'none')
    """
    if not samples:
        return 0.0, []

    diagnostics: list[dict] = []
    matched_count = 0
    for em in samples:
        body = em.get("body") or ""
        subject = em.get("subject") or ""

        # ── Pfad 1: body_card_re (Multi-Card-Mails) ─────────────────────
        cards = list(compiled.body_card_re.finditer(body))
        valid_cards = []
        for m in cards:
            t = (m.group("title") or "").strip()
            c = (
                (m.group("company") or "").strip()
                if "company" in m.groupdict() else ""
            )
            if compiled.title_blacklist_re and compiled.title_blacklist_re.search(t):
                continue
            if (
                compiled.company_blacklist_separator_re
                and c
                and compiled.company_blacklist_separator_re.match(c)
            ):
                continue
            valid_cards.append(m)

        via = "none"
        is_match = False
        if valid_cards:
            via = "body_card"
            is_match = True
        else:
            # ── Pfad 2: Subject + URL im Body (Single-Job-Mails) ────────
            subj_m = compiled.subject_re.match(subject.strip())
            if subj_m:
                t = (subj_m.group("title") or "").strip()
                blacklisted = bool(
                    compiled.title_blacklist_re
                    and compiled.title_blacklist_re.search(t)
                )
                has_url = bool(_ANY_URL_RE.search(body))
                if not blacklisted and has_url:
                    via = "subject"
                    is_match = True

        if is_match:
            matched_count += 1
        diagnostics.append({
            "subject": subject[:80],
            "matched": is_match,
            "card_count": len(valid_cards),
            "via": via,
        })
    return matched_count / len(samples), diagnostics


_SYSTEM_PROMPT = (
    "Du bist ein Mail-Layout-Analyst. Aus den vorgelegten Job-Empfehlungs-"
    "Mails extrahierst du das Layout-Pattern und gibst es als striktes JSON "
    "zurueck. KEIN Markdown-Wrapping, KEINE Kommentare, KEINE zusaetzlichen "
    "Felder ausserhalb des Schemas."
)


_EXAMPLE_OUTPUT = {
    "subject_pattern": {
        "prefix_optional": True,
        "prefix_keywords": ["Neue Stelle", "Job alert"],
        "separator": "bei|at|@",
    },
    "body_card": {
        "url_labels": ["Jobangebot ansehen", "View job"],
        "fields_before_url": ["title", "company", "location"],
        "separator_lines_allowed": 5,
    },
    "filters": {
        "title_blacklist": ["Ihre Jobbenachrichtigung", "Top-Jobs"],
        "company_blacklist_separators": ["----"],
    },
}


def _build_user_prompt(
    train_samples: list[dict], platform: str, strict: bool = False,
) -> str:
    lines = [
        f"Platform: {platform}",
        "",
        "Gib EXAKT dieses JSON-Format zurueck — gleiche Top-Level-Keys",
        "(subject_pattern, body_card, filters), gleiche Sub-Felder.",
        "KEINE zusaetzlichen Keys wie 'footer', 'header' etc. — werden ignoriert.",
        "",
        "Beispiel-Output (Struktur exakt einhalten, Werte an deine Mails anpassen):",
        json.dumps(_EXAMPLE_OUTPUT, indent=2, ensure_ascii=False),
        "",
        "Feld-Erklaerung:",
        "- subject_pattern.prefix_keywords: Wuerter wie 'Neue Stelle', die vor",
        "  dem Job-Titel im Subject stehen koennen (optional).",
        "- subject_pattern.separator: Regex-Alternation zwischen Title und Company",
        "  im Subject (typisch: 'bei|at|@').",
        "- body_card.url_labels: Label-Strings direkt vor der Job-URL im Body",
        "  (z.B. 'Jobangebot ansehen', 'View job', 'Show job').",
        "- body_card.fields_before_url: Reihenfolge der Felder VOR der URL im",
        "  Body. Erlaubte Werte: 'title', 'company', 'location', 'extra'.",
        "- body_card.separator_lines_allowed: max. Anzahl Leerzeilen/Trenner",
        "  zwischen den Feldern und der URL-Zeile.",
        "- filters.title_blacklist: Phrasen die NIE ein Title sind (z.B.",
        "  Mail-Header wie 'Ihre Jobbenachrichtigung').",
        "- filters.company_blacklist_separators: Trenner-Muster die NIE Company",
        "  sein duerfen (z.B. '----').",
        "",
        "Sample-Mails (Layout aus diesen ableiten):",
    ]
    for i, em in enumerate(train_samples):
        subj = (em.get("subject") or "")[:200]
        body = (em.get("body") or "")[:6000]
        lines.append(f"\n--- Mail {i+1} ---\nSubject: {subj}\nBody:\n{body}\n")
    lines.append(
        "\nNur das JSON zurueckgeben, EXAKT mit den 3 Top-Level-Keys "
        "subject_pattern/body_card/filters. Keine Prose, keine Markdown-Fences."
    )
    if strict:
        lines.append(
            "\nWICHTIG: vorheriger Versuch ist gescheitert. Beachte das "
            "Beispiel-Output-Format EXAKT — KEINE zusaetzlichen Keys, ALLE "
            "drei Top-Level-Felder muessen da sein."
        )
    return "\n".join(lines)


def ai_learn_pattern(user, train_samples: list[dict], platform: str) -> dict:
    """Ruft AI auf, validiert Schema, gibt geparsed dict zurueck.

    Bei JSON-Parse-Fail oder Schema-Fail: 1 Retry mit verschaerfter Prompt.
    Respektiert user.ai_provider/ai_provider_model (kein hardcoded Claude).

    Raises:
        RuntimeError bei finalem Fail.
    """
    from services import ai_provider_client as _aip
    # Use get_client() in prod (returns None if not configured); in tests the
    # `.chat` method is monkey-patched on the class, so a dummy instance is
    # sufficient.
    client = _aip.get_client()
    if client is None:
        # Tests patch chat() on the class — instantiate with placeholder creds
        # so __init__ doesn't reject empty env. Real calls would already have
        # returned a configured client from get_client().
        client = _aip.AIProviderClient(base_url="http://test", token="test")

    last_error = None
    for attempt in (1, 2):
        strict = (attempt == 2)
        prompt = _build_user_prompt(train_samples, platform, strict=strict)
        try:
            result = client.chat(
                user_id=getattr(user, "id", None),
                provider=getattr(user, "ai_provider", None),
                model=getattr(user, "ai_provider_model", None),
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
            )
        except Exception as exc:
            last_error = f"AI-Call failed: {exc}"
            logger.warning(
                "ai_learn_pattern attempt %d: %s", attempt, last_error,
            )
            continue
        # Tests mock chat() to return a dict {"content": "..."}; the real
        # AIProviderClient.chat returns a ChatResponse dataclass. Support both.
        if isinstance(result, dict):
            content = (result.get("content") or "")
        else:
            contents = getattr(result, "content", None) or []
            content = (
                contents[0].text if contents and hasattr(contents[0], "text")
                else ""
            )
        content = (content or "").strip()
        # Strip optional markdown fences
        if content.startswith("```"):
            content = content.split("```", 2)[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.rstrip("`").strip()
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            last_error = f"AI-Output kein valides JSON: {exc}"
            logger.warning(
                "ai_learn_pattern attempt %d: %s", attempt, last_error,
            )
            continue
        # Normalize: dropt unbekannte Felder, fuellt Defaults. Schwache LLMs
        # (Ollama qwen3-coder etc.) halluzinieren oft 'footer' oder benennen
        # body_card.fields_before_url um zu 'fields'. Statt zu rejecten,
        # cleanen wir das auf.
        try:
            parsed = normalize_pattern(parsed)
        except ValueError as exc:
            last_error = f"Normalize-Fehler: {exc}"
            logger.warning(
                "ai_learn_pattern attempt %d: %s", attempt, last_error,
            )
            continue
        errors = validate_pattern_schema(parsed)
        if errors:
            last_error = f"Schema-Fehler: {'; '.join(errors[:3])}"
            logger.warning(
                "ai_learn_pattern attempt %d: %s", attempt, last_error,
            )
            continue
        return parsed
    raise RuntimeError(
        f"ai_learn_pattern failed after 2 attempts: {last_error}"
    )
