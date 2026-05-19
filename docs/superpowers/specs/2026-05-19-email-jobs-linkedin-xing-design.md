# Email-Jobs-Import für LinkedIn & Xing — Design

**Datum:** 2026-05-19
**Author:** Harald Weiss (mit Claude Opus 4.7)
**Status:** Draft — wartet auf User-Review

## Ziel

LinkedIn- und Xing-Job-Empfehlungs-Mails parallel zum bestehenden
Indeed-Email-Import als Job-Vorschläge in den Tracker bringen, ohne
Bestand zu brechen.

## Ausgangslage

- **Indeed-Email-Import existiert** als Feature-Branch
  `claude/thirsty-elion-684a7f` mit 30 Commits / ~3.940 LOC, **ist aber
  nicht in master gemergt**. Memory beschreibt das Feature als "live auf
  VPS seit 2026-05-17" — vor Merge per SSH verifizieren.
- Frontend (`index.html`) hat in der Source-Anlage bereits Dropdown-Einträge
  für `linkedin` und `xing` — aber als RSS/JSearch-Aggregator-Adapter,
  nicht als Mail-Import.
- Die bestehenden RSS/JSearch-Adapter (`services/job_sources/linkedin.py`,
  `xing.py`) bleiben unverändert.

## Zwei-Phasen-Plan

### Phase 1 — Indeed-Branch in master mergen

`claude/thirsty-elion-684a7f` → `master`. Bringt:

- `services/job_sources/indeed_email.py` (~497 LOC) + Tests (~696 LOC)
- Endpoints `POST /api/jobs/sources/<id>/import-from-email[/approve]`
- Mail-Connector-UI inkl. Folder-Picker
- IMAP-Proxy-Fixes (Python 3.12 `ssl_context=`, folder-quoting,
  bracket-folder-Whitelist, X-GM-RAW)
- Apps-Script-Backend-Proxy (CORS-Umgehung) + 1h Response-Cache

**Vor-Merge-Check:**
1. Per `ssh ionos-vps`: läuft `indeed_email`-Code wirklich? Welcher SHA?
2. `/etc/cron.d/job-discovery` zeigt `25 * * * * indeed-email-import-all`.
3. DB-Backup `bewerbungstracker.db.bak.pre-indeed-email-merge`.

**Merge:**
- Lokal Branch `merge/indeed-email-to-master` von master.
- `git merge --no-ff claude/thirsty-elion-684a7f`.
- Erwartete Konfliktstellen:
  - `index.html` (Smtp-Status-Badges in master vs. Mail-Connector-UI in Branch)
  - `api/jobs_user.py` (Origin-Filter / Unbewertet-Filter in master)
  - `api/profile.py` (SMTP-Encrypted-Credential-Fix in master vs. IMAP-Mini-API)
  - `service-worker.js` (CACHE_NAME-Bumps — max-Wert nehmen)
  - `imap_proxy.py` (UID-Fix in master vs. folder-quoting/X-GM-RAW)
- **Konfliktauflösungs-Regel: beide Seiten vereinen, niemals eine wählen.**
  Indeed-Branch-Patches sind alle bug-orientiert oder additiv.

**Verifikation:**
- `pytest tests/` — Indeed-Branch-Tests (36) + Master-Tests grün.
- Smoke-Test: `/api/jobs/sources` listet, `/api/jobs/sources/<id>/import-from-email`
  antwortet (auch "no IMAP credentials" ist OK).
- UI-Sichtprobe: Source-Anlage zeigt `indeed`/`linkedin`/`xing`.

**Done:** Master enthält `indeed_email.py`, alle Endpoints, Tests grün,
VPS-SHA = master-SHA.

### Phase 2 — Generischer Refactor + LinkedIn/Xing-Profile

**Datei-Umbenennung:** `git mv services/job_sources/indeed_email.py
services/job_sources/email_jobs.py`.

**Klassen-Struktur:**

```python
class EmailJobsAdapter(JobSourceAdapter):
    """Generischer Mail-Import-Adapter, plattform-agnostisch."""
    AI_FALLBACK_BUDGET = 10  # pro Source-Lauf, also pro Plattform

    def __init__(self, config, user=None, platform_profile=None):
        super().__init__(config)
        self.user = user
        self.profile = platform_profile
        self._ai_calls_used = 0

    def fetch(self): ...
    def parse_emails(self, emails): ...
    def _parse_email(self, em): ...   # nutzt self.profile.subject_patterns etc.
    def _ai_fallback(self, em): ...   # nutzt self.profile.ai_hint
```

```python
@dataclass(frozen=True)
class PlatformProfile:
    name: str
    source_label: str
    from_filter: str                  # X-GM-RAW Hinweis
    from_whitelist: list[str]         # Domain-Regex für Plain-IMAP
    url_pattern: re.Pattern
    subject_patterns: list[re.Pattern]
    body_title_re: re.Pattern
    body_company_re: re.Pattern
    body_location_re: re.Pattern
    digest_threshold: int = 3
    ai_hint: str = ""
```

```python
PROFILES: dict[str, PlatformProfile] = {
    "indeed":   PlatformProfile(...),   # 1:1 portiert aus Phase 1
    "linkedin": PlatformProfile(...),   # neu
    "xing":     PlatformProfile(...),   # neu
}
```

**Plattform-Profile (konkret):**

*Indeed* (Bestand, portiert):
- `from_filter='from:indeed'`
- `from_whitelist=[r'@(?:[a-z0-9.-]+\.)?indeed\.(?:de|com|co\.uk|fr|it|es)$']`
- `url_pattern=https?://(?:[a-z0-9\-.]+\.)?indeed\.(?:de|com|...)/...`
- Subject/Body-Regex bestehend übernommen.

*LinkedIn* (neu):
- `from_filter='from:linkedin.com'`
- `from_whitelist=[r'@(?:[a-z0-9.-]+\.)?linkedin\.com$']`
- `url_pattern=https?://(?:www\.)?linkedin\.com/(?:jobs/view|comm/jobs/view)/\d+...`
- Subject (Single-Job): `(?:New job|Neue Stelle)\s*:?\s*(?P<title>.+?)\s+(?:at|bei|@)\s+(?P<company>.+)$`
- Body-Felder: `Position/Job Title/Jobtitel/Stelle`, `Company/Firma/...`, `Location/Standort/Ort`
- AI-Hint: "LinkedIn-Jobempfehlungs-Digest. Jede Job-Card hat einen
  linkedin.com/jobs/view/<ID>-Link. Extrahiere {title, company, location, url}."

*Xing* (neu):
- `from_filter='from:xing.com'`
- `from_whitelist=[r'@(?:[a-z0-9.-]+\.)?xing\.com$']`
- `url_pattern=https?://(?:www\.)?xing\.com/(?:jobs|app/jobs)/...`
- Subject: `(?:Neue\s+(?:Stelle|Jobempfehlung)|New\s+job)\s*:?\s*(?P<title>.+?)\s+(?:bei|at|@)\s+(?P<company>.+)$`
- Body-Felder: deutsche + englische Varianten
- AI-Hint: deutsch, analog LinkedIn.

**Tracking-URLs** (`email.linkedin.com/...`, `r.email.xing.com/...`):
- Werden 1:1 als `external_id` behalten, **kein Auto-Redirect-Follow**.
- Plattform-Präfix im `external_id` (`linkedin:<url>`, `xing:<url>`)
  verhindert Dedup-Kollisionen zwischen Plattformen mit identischen
  Tracking-Hashes.

**Multi-URL/Digest-Erkennung** (alle Profile):
```python
urls = set(profile.url_pattern.findall(body))
if len(urls) >= profile.digest_threshold:
    return self._ai_fallback(em)  # JSON-Array Output erwartet
# sonst Single-Job-Pfad via Subject + Body-Felder
```

**Registry-Anpassung** (`services/job_sources/__init__.py`):
- `_VALID_TYPES += ("linkedin_email", "xing_email")`.
- `get_adapter(source_type, config, user)`:
  - `if source_type.endswith("_email")`:
    `platform = source_type.removesuffix("_email")`,
    `return EmailJobsAdapter(config, user, PROFILES[platform])`.
- Bestehende Aufrufe für `indeed_email` bleiben funktional identisch.

**Folder-Whitelist** (Anti-Injection): aktueller Indeed-Regex (erlaubt
Gmail-Bracket-Folder) gilt unverändert für alle drei.

**Cron** (`api/jobs_cron.py`):
- Heute: `_select_due_source` schließt `type='indeed_email'` aus
  (manueller Pfad).
- Nach Refactor: schließt `type IN ('indeed_email','linkedin_email','xing_email')`
  aus.
- `indeed-email-import-all`-Endpoint iteriert jetzt über alle drei
  Source-Typen. **URL-Pfad bleibt identisch** (`/api/jobs/indeed-email-import-all`)
  damit VPS-Cron-Zeile unverändert bleibt.
- Cron-Output: pro Plattform Log-Zeile + Sammelzeile.

**Per-Plattform AI-Budget:** 10 Calls pro Source-Lauf (also pro
Plattform). In Summe theoretisch 30 pro Cron-Run, praktisch deutlich
weniger weil Single-Job-Mails ohne AI gehen.

**Apps-Script-Modus (Privacy-Mode):** der bestehende Indeed-Apps-Script-Pfad
(`POST .../import-from-email` mit `{script_url}` oder `{emails: [...]}`)
ist plattform-agnostisch (`EmailJobsAdapter.parse_emails(list)`).
LinkedIn/Xing können denselben Pfad nutzen, sobald der User in seinem
Apps-Script einen Plattform-Filter ergänzt (`GmailApp.search('from:linkedin
newer_than:30d')`). Wir liefern Beispiel-Apps-Scripts in `docs/` mit, kein
neuer Endpoint nötig.

### UI-Setup-Flow

**Neuer Source-Typ in Job-Source-Anlage:**

- Dropdown bekommt zusätzlich "**Job-Mails (Mehrfach-Auswahl)**".
- Auswahl öffnet Setup-Formular:
  - **Plattformen** (Checkboxen, ≥1 Pflicht): ☐ Indeed, ☐ LinkedIn, ☐ Xing
  - **Folder** (geteilt): Default `[Google Mail]/Alle Nachrichten` —
    via Folder-Picker des Mail-Connectors
  - **Lookback** (geteilt): Default 30 Tage
  - **Limit pro Plattform**: Default 100
- "Anlegen" POSTet `POST /api/jobs/sources/bulk-email` → legt 1–3
  `JobSource`-Rows an (eine pro angehakter Plattform), alle mit gleichem
  Folder/Lookback/Limit.
- Bestehende Einzel-Anlage `indeed_email` über die alte Dropdown bleibt
  erhalten (Power-User-Pfad).

**Sources-Liste:**
- Drei separate Zeilen (Indeed/LinkedIn/Xing), jede mit eigenem
  "Importieren"-Button (wie heute Indeed).
- Plattform-Icon links (📌 Xing / 💼 LinkedIn / 🔍 Indeed),
  Status-Badge "zuletzt importiert vor X Min".
- Kein Sammel-Button — Cron läuft stündlich automatisch.

**Approval-Dialog:** unverändert, zeigt Plattform-Name pro geblocktem
Job (welche Plattform die Mail kam).

### Folder-Strategie

- Default für alle drei: `[Google Mail]/Alle Nachrichten` (Gmail-Default).
- Auf Gmail-IMAP wird X-GM-RAW genutzt: `from:linkedin newer_than:30d` /
  `from:xing newer_than:30d`. Keine Gmail-Filterregel/Label nötig.
- Bei Non-Gmail-IMAP-Servern Fallback auf Standard-IMAP
  `SEARCH FROM "linkedin"` (heute schon bei Indeed implementiert).

## Datenmigration

- **Keine Schema-Änderungen.** `JobSource.type` ist ein freier String.
- Bestand: `indeed_email`-Sources auf VPS laufen nach Refactor durch
  denselben `EmailJobsAdapter` mit `PROFILES["indeed"]` — identisches
  Verhalten.
- Keine Backfills, keine Alembic-Migration, kein Re-Encrypt.

## Tests

**Bestand portiert:**
- `tests/services/test_indeed_email.py` → `tests/services/test_email_jobs.py`
  (Klassennamen angepasst, Cases unverändert — testen jetzt
  `EmailJobsAdapter` mit `PROFILES["indeed"]`).

**Neu:**
- `tests/services/test_email_jobs_linkedin.py` (5–7 Tests):
  - Single-Job-Subject-Parsing (Recruiter-Mail)
  - Digest-Erkennung (≥3 LinkedIn-URLs → AI-Fallback mocked)
  - From-Whitelist (xing.com-Mail wird *nicht* als LinkedIn akzeptiert)
  - URL-Pattern matcht `/jobs/view/<id>` und `/comm/jobs/view/<id>`
  - Tracking-URL `email.linkedin.com/...` bleibt external_id (kein Follow)
- `tests/services/test_email_jobs_xing.py` (analog, 5–7 Tests)
- `tests/api/test_email_jobs_import.py` (4–6 Integration-Tests):
  - `POST /api/jobs/sources/bulk-email` legt 3 Sources an
  - `import-from-email` funktioniert für `linkedin_email`/`xing_email`
  - Cron-Endpoint iteriert über alle drei Typen
  - bulk-email lehnt leere Plattform-Liste ab

**Test-Fixtures:** 2–3 reale anonymisierte Beispiel-Mails pro Plattform
(Subject + plaintext Body). Beschaffung nach Phase 1 via einmaligem
IMAP-Dump aus Userpostfach. **Nicht eingecheckt** — als
`tests/fixtures/email_jobs/*.txt.gitignored` oder direkt inline im
Test-Code mit redaktierten Werten.

## Risiken & Mitigation

| Risiko | Mitigation |
|---|---|
| LinkedIn-Mail-Layout-Drift bricht Regex | Digest-Fallback auf AI (Ollama) — fängt Layout-Wechsel ab |
| AI-Budget eskaliert bei Spam | Pre-Filter via `from_whitelist` *vor* AI-Call |
| Tracking-Redirect-URLs verschmutzen Dedup | Plattform-Präfix im `external_id` (`linkedin:<hash>`) |
| Phase-1-Merge-Konflikte | Strict "vereinen statt wählen", danach pytest + Smoke-Test |
| VPS-Stand vs. Master-Stand auseinander | Vor-Merge SSH-Check + DB-Backup vor Deploy |
| Indeed-Bestand bricht durch Refactor | `PROFILES["indeed"]` portiert Bestand-Regexen 1:1, Bestands-Tests bleiben grün |

## Done-Definition

**Phase 1:**
- Master enthält `services/job_sources/indeed_email.py` + alle
  Endpoints + Tests grün.
- VPS läuft auf gleichem SHA wie master.
- Memory `project_indeed_email_import_live.md` bleibt unverändert
  gültig.

**Phase 2:**
- `services/job_sources/email_jobs.py` mit drei Profilen, alte Datei
  entfernt.
- LinkedIn + Xing Source-Typen in `_VALID_TYPES`.
- `bulk-email`-Endpoint + UI-Mehrfach-Setup live.
- Cron-Endpoint iteriert über alle drei.
- Alle Tests grün (Bestand + neu).
- Memory aktualisiert: `project_indeed_email_import_live.md` →
  `project_email_jobs_import_live.md` (Indeed/LinkedIn/Xing).

## Out of Scope

- Stepstone-Mails (nicht in dieser Iteration).
- HTML-Body-Parsing mit BeautifulSoup (Plain-Text + AI-Fallback reicht).
- Reply-to-Recruiter-Flow (nur Job-Empfehlungs-Mails, keine
  Recruiter-Direct-Messages).
- Auto-Follow von Tracking-Redirect-URLs (Datenschutz/Tracking-Avoidance).
- Bestehende RSS/JSearch-Adapter `linkedin.py`/`xing.py` werden nicht
  angefasst — bleiben als alternative Job-Source-Typen.

## Verwandte Specs

- [2026-05-17 Indeed Email Import](./2026-05-17-indeed-email-import-design.md)
  (im Indeed-Feature-Branch, wird mit Phase 1 in master verfügbar)
- [2026-04-30 Job Sources Xing/LinkedIn/Stepstone (RSS/JSearch)](./2026-04-30-job-sources-xing-linkedin-stepstone.md)
  — beschreibt die *anderen* (RSS/Aggregator) LinkedIn/Xing-Adapter,
  die unangetastet bleiben.
