from services.job_sources.base import JobSourceAdapter, FetchedJob
from services.job_sources.rss import RssAdapter
from services.job_sources.adzuna import AdzunaAdapter
from services.job_sources.bundesagentur import BundesagenturAdapter
from services.job_sources.arbeitnow import ArbeitnowAdapter
from services.job_sources.xing import XingAdapter
from services.job_sources.linkedin import LinkedInAdapter
from services.job_sources.stepstone import StepstoneAdapter


def get_adapter(source_type: str, config: dict) -> JobSourceAdapter:
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
