from services.job_sources.base import JobSourceAdapter, FetchedJob
from services.job_sources.rss import RssAdapter
# Adzuna, Bundesagentur, Arbeitnow folgen in Tasks 11-13


def get_adapter(source_type: str, config: dict) -> JobSourceAdapter:
    registry = {
        "rss": RssAdapter,
        # 'adzuna': AdzunaAdapter,
        # 'bundesagentur': BundesagenturAdapter,
        # 'arbeitnow': ArbeitnowAdapter,
    }
    cls = registry.get(source_type)
    if not cls:
        raise ValueError(f"Unbekannter Source-Type: {source_type}")
    return cls(config)
