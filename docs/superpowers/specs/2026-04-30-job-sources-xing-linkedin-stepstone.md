# Job-Sources: Xing, LinkedIn, Stepstone Integration

**Date:** 2026-04-30  
**Status:** Design (Ready for Implementation)  
**Approach:** Hybrid RSS + Job-Aggregator-APIs with Strict Deduplication

---

## Overview

Add three new job discovery sources (Xing, LinkedIn, Stepstone) to the Bewerbungstracker job matching pipeline. Each source will fetch from **RSS feeds + Job-Aggregator-APIs in parallel**, deduplicate strictly by URL, and exclude jobs for which applications already exist.

---

## Architecture

### Plugin Pattern (No Breaking Changes)

Extend the existing `JobSourceAdapter` plugin system:

```python
# services/job_sources/__init__.py
registry = {
    "rss": RssAdapter,
    "adzuna": AdzunaAdapter,
    "bundesagentur": BundesagenturAdapter,
    "arbeitnow": ArbeitnowAdapter,
    "xing": XingAdapter,          # NEW
    "linkedin": LinkedInAdapter,   # NEW
    "stepstone": StepstoneAdapter, # NEW
}
```

### Hybrid Fetch Strategy

Each new adapter (XingAdapter, LinkedInAdapter, StepstoneAdapter) implements:

```python
class XingAdapter(JobSourceAdapter):
    def fetch(self) -> list[FetchedJob]:
        # Parallel execution
        rss_jobs = self.fetch_rss()
        agg_jobs = self.fetch_aggregator()
        combined = rss_jobs + agg_jobs
        
        # Deduplicate + filter existing applications
        deduped = self._deduplicate(combined)
        return deduped
    
    def fetch_rss(self) -> list[FetchedJob]:
        """Parse public RSS feed for jobs."""
        # URL from config: self.config["rss_url"]
        # Return FetchedJob[] with title, url, company, location, posted_at
    
    def fetch_aggregator(self) -> list[FetchedJob]:
        """Fetch from Job-Aggregator-API (RapidAPI, etc)."""
        # API config: self.config["aggregator_api"], self.config["aggregator_key"]
        # Query: platform filter (xing, linkedin, stepstone)
        # Return FetchedJob[] with title, url, company, location
```

---

## Deduplication Logic (Strict)

**Phase:** In-adapter, before returning to cron pipeline.

**Strategy:**
1. **In-batch dedup:** Remove exact URL duplicates within current fetch (RSS + Aggregator combined)
2. **DB dedup:** Exclude URLs that already exist in:
   - `RawJob.url` (known jobs)
   - `Application.job_url` (already applied)

**Implementation:**

```python
def _deduplicate(self, jobs: list[FetchedJob]) -> list[FetchedJob]:
    """Strict deduplication: URL-based, excluding existing applications."""
    seen_urls = set()
    existing_urls = self._get_existing_job_urls_from_db()
    
    result = []
    for job in jobs:
        if job.url in seen_urls or job.url in existing_urls:
            continue  # Skip duplicate or already applied
        seen_urls.add(job.url)
        result.append(job)
    
    return result

def _get_existing_job_urls_from_db(self) -> set[str]:
    """Query DB for existing RawJobs + Applications."""
    raw_urls = db.session.query(RawJob.url).all()
    app_urls = db.session.query(Application.job_url).all()
    return set(url[0] for url in raw_urls + app_urls if url[0])
```

---

## Data Flow

No changes to the cron pipeline. The new adapters slot directly into `jobs_cron.py`:

```
/api/cron/tick
  ├─ JobSource.query() → all sources (rss, adzuna, ..., xing, linkedin, stepstone)
  ├─ for source in sources:
  │    adapter = get_adapter(source.type, source.config)
  │    jobs = adapter.fetch()  ← NEW: Hybrid fetch + dedup
  │    └─ Store in RawJob, run prefilter, Claude match, notify user
  └─ Response
```

**Backward compatible:** Existing sources (arbeitnow, adzuna, etc.) unchanged.

---

## Database Schema

**No schema changes required.**

**JobSource table (existing, extended):**
- New rows added via `seed_job_sources.py`:
  - type: "xing" | "linkedin" | "stepstone"
  - config JSON with:
    - `rss_url`: public RSS feed URL
    - `aggregator_api`: "rapidapi" or other
    - `aggregator_key`: API key (env-var reference or encrypted)
    - `location`: filter (e.g., "Germany")
    - `keywords`: optional skill/job-title filters

**Example config:**
```json
{
  "type": "xing",
  "name": "Xing Jobs",
  "enabled": true,
  "config": {
    "rss_url": "https://www.xing.com/jobs/search/feed?keywords=python",
    "aggregator_api": "rapidapi",
    "aggregator_key": "${RAPIDAPI_KEY}",
    "location": "Germany",
    "keywords": ["Python", "Data", "Backend"]
  }
}
```

---

## Implementation Plan (High Level)

1. **Create 3 new adapters** (subagents in parallel):
   - `services/job_sources/xing.py`
   - `services/job_sources/linkedin.py`
   - `services/job_sources/stepstone.py`

2. **Register in `__init__.py`** (1 min change)

3. **Extend `seed_job_sources.py`** to populate 3 new JobSource rows

4. **Write unit tests** (per adapter):
   - RSS fetch + parse
   - Aggregator API fetch
   - Deduplication logic
   - DB integration (exclude existing apps)

5. **Manual test** on VPS cron

6. **Monitor** for dedup rates, fetch failures, cost (if using paid APIs)

---

## API Resources

### RSS Feeds (Free, No Auth)
- **Xing:** Public job RSS available (search parameters in URL)
- **LinkedIn:** Limited (no official RSS, but RSS aggregators exist)
- **Stepstone:** Public RSS feed

### Job-Aggregator-APIs (Secondary)
Options for better coverage:
- **RapidAPI JSearch** — multi-source, requires API key + credits
- **Adzuna API** — already integrated, can extend for xing/linkedin/stepstone filters
- **Custom RSS aggregator** — parse multiple RSS feeds via a single API

**Decision:** Start with public RSS feeds. Use RapidAPI JSearch as fallback/supplement if RSS is insufficient.

---

## Testing Strategy

### Unit Tests
- `test_xing_rss_fetch()` — RSS parsing, FetchedJob mapping
- `test_xing_aggregator_fetch()` — API response handling
- `test_xing_deduplication()` — strict URL dedup logic
- `test_dedup_excludes_existing_applications()` — DB integration

### Integration Tests
- Mock RSS + Mock Aggregator API
- Ensure dedup filters duplicates + existing apps correctly
- Verify `FetchedJob` schema compliance

### Manual Validation
- `python -m pytest tests/services/test_job_sources_xing.py` etc.
- Seed sources, trigger cron tick, inspect `RawJob` table
- Check logs: "Xing RSS: 15 jobs, 3 dedup'd, 12 stored"

---

## Deployment Considerations

1. **Secrets Management:**
   - API keys in environment variables or secrets manager
   - `aggregator_key` in JobSource config references `${ENV_VAR}`

2. **Rate Limiting:**
   - RSS: no limit (HTTP polling)
   - Aggregator APIs: check rate limits, implement backoff if needed

3. **Monitoring:**
   - Log fetch times, dedup rates, error counts
   - Alert if a source fails 5+ times (existing AUTO_DISABLE_FAILURE_COUNT)

4. **Rollout:**
   - Deploy adapters first
   - Seed sources in staging, test 1-2 cron cycles
   - Enable in production after validation

---

## Success Criteria

✅ All 3 sources fetch jobs without errors  
✅ Deduplication rate > 90% (same job not appearing 2x)  
✅ Existing applications excluded from results  
✅ Cron tick time increased by < 5 seconds  
✅ No duplicate jobs in user's "New Matches" UI  
✅ Unit tests pass (>95% coverage for new adapters)
