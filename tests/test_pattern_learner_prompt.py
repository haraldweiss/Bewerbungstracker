# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the AI-prompt construction in pattern_learner.

Bug background: the prompt used to leak LinkedIn-specific phrases as
"example values", which small AI models would copy 1:1 instead of
inferring from the actual mail samples. All 4 patterns in prod (Indeed,
LinkedIn, XING) had `url_labels = ["Jobangebot ansehen", "View job"]`
— literally the example. These tests ensure the prompt no longer leaks.
"""
from services.job_sources.pattern_learner import _build_user_prompt, _EXAMPLE_OUTPUT


def _sample_mails(n=3):
    return [
        {"subject": f"Test Stelle {i}", "body": f"Body {i} https://example.com/job/{i}"}
        for i in range(n)
    ]


def test_prompt_does_not_leak_linkedin_url_labels():
    """The example output must not contain concrete LinkedIn URL-label phrases
    that the AI might copy verbatim."""
    prompt = _build_user_prompt(_sample_mails(), platform="indeed")
    # These specific German+English LinkedIn phrases were being copied verbatim.
    forbidden = ["Jobangebot ansehen", "View job", "Show job"]
    for phrase in forbidden:
        assert phrase not in prompt, (
            f"Prompt leaks {phrase!r} as example — AI copies these directly. "
            f"Use placeholder values like '<EXTRAHIERE_AUS_MAIL>' instead."
        )


def test_prompt_does_not_leak_linkedin_title_blacklist():
    """The title_blacklist example must not contain real LinkedIn header phrases."""
    prompt = _build_user_prompt(_sample_mails(), platform="indeed")
    forbidden = ["Ihre Jobbenachrichtigung", "Top-Jobs"]
    for phrase in forbidden:
        assert phrase not in prompt, (
            f"Prompt leaks {phrase!r} as title_blacklist example — "
            f"AI copies it as title_blacklist for non-LinkedIn platforms."
        )


def test_example_output_uses_obvious_placeholders():
    """_EXAMPLE_OUTPUT.body_card.url_labels should contain a marker that
    cannot occur in real mails (so it's obviously a placeholder)."""
    labels = _EXAMPLE_OUTPUT["body_card"]["url_labels"]
    # The marker should be clearly placeholder-like.
    # Recommended convention: angle-bracketed UPPER-SNAKE-CASE
    # (e.g. "<EXTRAHIERE_AUS_MAIL>")
    assert all(
        ("<" in lbl and ">" in lbl) for lbl in labels
    ), (
        f"url_labels example values should be obvious placeholders "
        f"(e.g. '<LABEL_FROM_MAIL>'), got {labels!r}"
    )


def test_example_output_title_blacklist_uses_placeholders():
    blacklist = _EXAMPLE_OUTPUT["filters"]["title_blacklist"]
    assert all(("<" in b and ">" in b) for b in blacklist), (
        f"title_blacklist example should be placeholders, got {blacklist!r}"
    )


def test_prompt_explicitly_warns_against_copying_placeholders():
    """The prompt must contain a clear warning that placeholder values must
    NOT be copied directly into the output."""
    prompt = _build_user_prompt(_sample_mails(), platform="indeed")
    # Look for a warning-style instruction.
    lower = prompt.lower()
    assert "platzhalter" in lower or "placeholder" in lower or "ersetze" in lower, (
        "Prompt must explicitly tell the AI to replace placeholder values "
        "with real ones extracted from the mails."
    )


def test_field_explanation_no_concrete_linkedin_examples():
    """The 'Feld-Erklaerung' section in the prompt must not name specific
    LinkedIn phrases as examples."""
    prompt = _build_user_prompt(_sample_mails(), platform="indeed")
    # The old field explanation said "z.B. 'Jobangebot ansehen', 'View job', 'Show job'".
    # That's another leak vector.
    assert "Jobangebot ansehen" not in prompt
    assert "View job" not in prompt
