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


def get_adapter(source_type: str, config: dict, **kwargs) -> JobSourceAdapter:
    """Instantiates a JobSource adapter for the given type.

    kwargs sind optional und werden an Adapter weitergereicht, die zusätzlichen
    Kontext brauchen (z.B. IndeedEmailAdapter braucht ``user=...`` für die
    IMAP-Credentials).
    """
    registry = {
        "rss": RssAdapter,
        "adzuna": AdzunaAdapter,
        "bundesagentur": BundesagenturAdapter,
        "arbeitnow": ArbeitnowAdapter,
        "xing": XingAdapter,
        "linkedin": LinkedInAdapter,
        "stepstone": StepstoneAdapter,
        "indeed_email": IndeedEmailAdapter,
    }
    cls = registry.get(source_type)
    if not cls:
        raise ValueError(f"Unbekannter Source-Type: {source_type}")
    if source_type == "indeed_email":
        return cls(config, user=kwargs.get('user'))
    return cls(config)
