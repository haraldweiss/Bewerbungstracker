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
from typing import Any

try:
    from jsonschema import Draft7Validator
except ImportError:
    Draft7Validator = None


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
