# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
from services.job_sources.base import JobSourceAdapter, FetchedJob
from services.job_sources.rss import RssAdapter
from services.job_sources.adzuna import AdzunaAdapter
from services.job_sources.bundesagentur import BundesagenturAdapter
from services.job_sources.arbeitnow import ArbeitnowAdapter
from services.job_sources.xing import XingAdapter
from services.job_sources.linkedin import LinkedInAdapter
from services.job_sources.stepstone import StepstoneAdapter
from services.job_sources.email_jobs import IndeedEmailAdapter


# Alle bekannten Source-Typen. `*_email`-Typen werden generisch via
# EmailJobsAdapter + PlatformProfile dispatched (siehe get_adapter()).
_VALID_TYPES = {
    "rss",
    "adzuna",
    "bundesagentur",
    "arbeitnow",
    "xing",
    "linkedin",
    "stepstone",
    "indeed_email",
    "linkedin_email",
    "xing_email",
}


def get_adapter(source_type: str, config: dict, **kwargs) -> JobSourceAdapter:
    """Instantiates a JobSource adapter for the given type.

    kwargs sind optional und werden an Adapter weitergereicht, die zusätzlichen
    Kontext brauchen (z.B. EmailJobsAdapter braucht ``user=...`` für die
    IMAP-Credentials).

    `*_email`-Typen werden generisch auf den EmailJobsAdapter mit dem passenden
    PlatformProfile gemappt (z.B. `linkedin_email` → PROFILES["linkedin"]).
    """
    # Generischer Dispatch für alle Email-basierten Sources.
    if source_type.endswith("_email"):
        from services.job_sources.email_jobs import EmailJobsAdapter, get_profile
        platform = source_type[: -len("_email")]
        try:
            profile = get_profile(platform)
        except KeyError:
            raise ValueError(f"Unbekannte Email-Plattform: {platform}")
        return EmailJobsAdapter(
            config=config,
            user=kwargs.get("user"),
            platform_profile=profile,
        )

    registry = {
        "rss": RssAdapter,
        "adzuna": AdzunaAdapter,
        "bundesagentur": BundesagenturAdapter,
        "arbeitnow": ArbeitnowAdapter,
        "xing": XingAdapter,
        "linkedin": LinkedInAdapter,
        "stepstone": StepstoneAdapter,
    }
    cls = registry.get(source_type)
    if not cls:
        raise ValueError(f"Unbekannter Source-Type: {source_type}")
    return cls(config)
