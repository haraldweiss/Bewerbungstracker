# SPDX-License-Identifier: AGPL-3.0-or-later
# (c) 2026 Harald Weiss
"""AI-gesteuerter Pattern-Lerner für Email-Job-Adapter.

Pipeline: fetch_sample_mails -> ai_learn_pattern -> compile_pattern ->
validate_pattern. Bei Hit-Rate >= Schwelle wird das Pattern als neue Row
in `learned_email_patterns` gespeichert (alte deaktiviert).
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass
from typing import Any

try:
    from jsonschema import Draft7Validator
except ImportError:
    Draft7Validator = None


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
