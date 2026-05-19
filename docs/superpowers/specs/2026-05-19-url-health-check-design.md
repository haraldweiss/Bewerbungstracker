# URL-Health-Check + Admin-Cleanup — Design + Plan

**Datum:** 2026-05-19
**Status:** in implementation

## Ziel

Job-URLs in `RawJob` periodisch prüfen. Bei 404/410 (permanent weg)
sofort + bei 3× Connection-Fail-in-Folge: `crawl_status='marked_for_deletion'`.
Admin reviewt die Liste in Settings → eigene Karte → ✗ Löschen / ↶ Behalten.

## Architektur

### Datenmodell (Alembic-Migration)

`RawJob`-Tabelle bekommt 3 neue Spalten:
```python
url_last_checked_at  = db.Column(db.DateTime, nullable=True)
url_check_failures   = db.Column(db.Integer, nullable=False, default=0)
url_check_status     = db.Column(db.String(32), nullable=True)
# Werte: 'ok' | '404' | '410' | '5xx' | 'timeout' | 'connection_error' | 'invalid_url'
```
`crawl_status` bekommt neuen erlaubten Wert `'marked_for_deletion'`
(zusätzlich zu existing `active`/`archived`).

### URL-Checker (`services/url_health_check.py`)

```python
def check_url(url: str, timeout: int = 5) -> tuple[str, int | None]:
    """HEAD-Request mit Redirect-Follow.

    Returns: (status_label, http_code)
      - ('ok',          2xx/3xx)
      - ('404',         404)
      - ('410',         410)
      - ('5xx',         5xx-Code)
      - ('timeout',     None)        — requests.Timeout
      - ('connection_error', None)   — DNS/Connection refused
      - ('invalid_url', None)        — Malformed URL
    """

def update_raw_job_health(raw_job, url_check_result) -> bool:
    """Mutiert raw_job in-place. Returns True wenn marked_for_deletion gesetzt.

    Logik:
      - 'ok'              → failures = 0, status = 'ok', NICHT mark
      - '404' | '410'     → SOFORT mark + crawl_status = 'marked_for_deletion'
      - andere Fails      → failures += 1; bei failures >= 3 → mark
    """
```

**SSRF-Schutz:** `services/ssrf_guard.is_url_safe_for_rss()` bereits
vorhanden. Wir nutzen es um sicherzustellen dass URLs nicht auf
private/lokale IPs zeigen.

**Tracker-URL-Auflösung:** Indeed-Tracker (`cts.indeed.com/v3/<base64>`)
werden bei HEAD-Redirects automatisch durchaufgelöst (max 3 Redirects).
Den finalen Statuscode werten wir. Bei Tracker selbst kaputt → 'ok' weil
der Redirect 30x antwortet bevor er kaputt geht.

### Cron-Endpoint (`api/jobs_cron.py`)

```python
@jobs_cron_bp.post('/url-health-check')
@require_cron_token
def url_health_check():
    """Batch-Check: aelteste-zuletzt-gepruefte ZUERST, max 100 pro Run."""
    # SELECT RawJob WHERE crawl_status='active'
    #   AND created_at > now-30d
    #   AND (url_last_checked_at IS NULL OR url_last_checked_at < now-1d)
    # ORDER BY COALESCE(url_last_checked_at, '1970') ASC LIMIT 100
    # Per-Domain-Throttle: max 1/2s pro Host (sleep zwischen Requests)
```

**Cron-Schedule** (in `/etc/cron.d/job-discovery`):
```cron
# Stage 7: URL-Health-Check (taeglich 04:00 UTC)
0 4 * * *           root /usr/local/bin/job-discovery-cron.sh url-health-check
```

### Admin-Endpoints (`api/admin.py`)

Bestehender `@admin_required`-Decorator wird genutzt.

```python
GET  /api/admin/url-cleanup-candidates
     → {candidates: [{id, url, title, company, url_check_status,
                      url_check_failures, url_last_checked_at,
                      crawl_status, source_id}, ...]}

POST /api/admin/url-cleanup/<int:raw_job_id>/delete
     → hard-delete RawJob + JobMatches + JobEmbeddings (CASCADE)

POST /api/admin/url-cleanup/<int:raw_job_id>/keep
     → url_check_failures = 0, crawl_status = 'active'

POST /api/admin/url-cleanup/bulk-delete
     Body: {ids: [int, ...]}
     → mass-delete
```

### Admin-UI (`index.html`)

Neue Karte in **Settings → Bewerbungen & Jobs** (nur sichtbar für Admins):

```
🧹 Cleanup-Kandidaten (N)
─────────────────────────
URL                          Fehler   Geprueft   Aktion
indeed.com/viewjob?jk=abc    404      vor 2h     [✗ Löschen] [↶ Behalten]
linkedin.com/jobs/view/4xx   timeout×3 vor 6h    [✗ Löschen] [↶ Behalten]
...

[🗑️ Alle Löschen]  [🔄 Aktualisieren]
```

Sichtbarkeit-Toggle via `user.is_admin === true` (siehe existing pattern).

## Implementation-Plan (7 Tasks)

1. **Migration + Model:** 3 neue RawJob-Spalten + crawl_status-Wert
2. **url_health_check Service:** `check_url` + `update_raw_job_health` + Unit-Tests
3. **Cron-Endpoint:** `POST /api/jobs/url-health-check` + per-domain-throttle + Integration-Test
4. **VPS-Cron-Datei:** `/etc/cron.d/job-discovery` Stage 7 ergänzen
5. **Admin-Endpoints:** 4 Endpoints in `api/admin.py` + Tests
6. **Admin-UI:** Karte in Settings → Bewerbungen & Jobs + service-worker v44
7. **Deploy via Skript + Memory-Update**

## Risiken

| Risiko | Mitigation |
|---|---|
| HEAD-Requests auf User-URLs → SSRF | ssrf_guard.is_url_safe_for_rss() vor jedem Check |
| Tracker-URL gibt 30x → wir folgen Redirect → kaputter Endpoint trotzdem nicht erkannt | requests.head(url, allow_redirects=True, timeout=5) — gibt finalen Statuscode zurück |
| Zu aggressive Checks → IP-Block durch indeed/linkedin | Per-Host-Throttle: 2s zwischen Requests pro Domain |
| Cron-Run hängt zu lange | LIMIT 100 pro Run, gunicorn-timeout 180s ist Hard-Cap |
| Admin löscht versehentlich | Confirm-Dialog vor Delete + Hard-Delete (kein Undo, dafür war's ja eh Müll) |
| Pre-existing JobMatch verwaisen nach Delete | CASCADE auf Foreign-Key oder explizites Delete von JobMatch+JobEmbedding vor RawJob |

## Out of Scope

- HTML-Content-Check ("This job is no longer available"-Strings)
- Multi-User-Cleanup (admin-only reicht für Single-User-Setup)
- Auto-Delete ohne Admin-Approval
- E-Mail-Benachrichtigung bei neuen Kandidaten
