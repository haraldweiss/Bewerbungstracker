# Changelog — Bewerbungstracker

Historische Session-Handoffs, ursprünglich in `AGENTS.md §7`. Ab 2026-06-19 werden neue Einträge hier statt in AGENTS.md dokumentiert.

### 2026-07-19 — Code-Review: Lern-Integrität + Session-Rollback (Nacharbeit zum Dismiss-500-Fix)

**Anlass:** Code-Review der Commits `4c20d2a`/`7e63eea`/`c85e180`
(Learner-flush-Umstellung) und ihrer Aufrufer.

**Gefundene + gefixte Fehler:**
1. **Re-Dismiss-Doppelzählung (Lern-Integrität):** `update_match` rief den
   Learner in allen drei Pfaden (quick_action, PATCH, Bulk) bei **jedem**
   Request mit `status='dismissed'` auf — auch wenn das Match längst
   dismissed war (Doppelklick, erneutes Verwerfen aus der Dismissed-Ansicht;
   das Frontend sendet `status` bei jedem PATCH mit). Jedes Mal wurde
   `samples_dismissed += 1` gezählt und der Centroid driftete erneut
   Richtung desselben Job-Vektors. Fix: Learner nur bei echtem
   Status-Übergang (`old_status != new_status`).
2. **`scripts/rebuild_user_centroids.py`:** fehlendes
   `db.session.rollback()` im Fehlerfall — nach dem ersten fehlgeschlagenen
   Match blieb die Session in einer abgebrochenen Transaktion (Postgres:
   PendingRollbackError-Kaskade für alle Folge-Matches) bzw. wurde dirty
   State vom nächsten `commit()` mitpersistiert.
3. **`learner.py` `get_learn_profile_stats`:** direktes `json.loads` ohne
   Typfilter → TypeError-Crash in `sorted(-x[1])` bei malformed
   `reason_counts` (z.B. String-Werte aus Legacy-Daten) → 500 auf
   `GET /api/jobs/learn-profile`. Fix: `_load_reason_counts()`
   wiederverwendet (filtert nicht-int Werte); zusätzlich
   `(or 0)`-Defensive für `samples_*` in `compute_score_adjustment` und
   `get_learn_profile_stats`, konsistent zum Rest der Datei.

**Bekannt, NICHT gefixt (braucht Design-Entscheidung/Schema):**
`feedback_bridge.maybe_bridge_to_feedback` triggert den Learner bei jeder
Notes-Änderung erneut auf ein bereits 'imported' Match → `samples_imported`-
und `reason_counts`-Inflation (die ganze Reason-Liste wird pro Lauf erneut
hochgezählt). Saubere Lösung bräuchte ein "bereits gelernt"-Tracking am
JobMatch (Schema-Änderung) oder einen Delta-Pfad nur für Reasons.

**Verifiziert:** 6 neue Regressionstests, alle vorher RED gegen den alten
Code bestätigt, mit Fix GREEN. Volle Suite lokal:
`pytest tests/ -q` → **855 passed, 2 skipped, 1 xfailed**.
Postgres-Verhalten per Review abgesichert, nicht live getestet.

**Deploy-Status: ERLEDIGT (2026-07-19, Fallback-Disziplin nach AGENTS.md §2).**
Code via rsync nach `/home/opc/bewerbungstracker` (kein Git-Checkout dort,
Tag daher explizit), Image `localhost/bewerbungen:7b42ea4` via
`deploy/container/build.sh 7b42ea4` gebaut, alle fünf Container via
`IMAGE_TAG=7b42ea4 deploy/container/setup-oracle-vm.sh rebuild` neu erstellt
(Volume `bewerbungen_data` erhalten, ai-provider NICHT angefasst → kein
Token-Sync nötig). Verifikation auf der VM: Worker-DB-URI =
`sqlite:////app/data/bewerbungstracker.db` (§3.5 ✅), Fix im Image
gegreppt (`was_dismissed` in /app/api/jobs_user.py, `rollback()` in
/app/scripts/rebuild_user_centroids.py), `GET /` → 200,
`GET /api/jobs/learn-profile` mit frischem JWT → **200** (übt genau den
gefixten stats-Pfad, read-only), Gunicorn-Log fehlerfrei.
Rollback bei Problemen: `IMAGE_TAG=c85e180 deploy/container/setup-oracle-vm.sh rebuild`.

### 2026-07-16 — Verwerfen/Import warf HTTP 500 (doppelter DB-Commit im Learner)

**Problem:** `update_centroid_for_feedback` (services/job_matching/learner.py)
machte ein **eigenes** `db.session.commit()`, während alle Aufrufer
(API-Routen in api/jobs_user.py, feedback_bridge.py) danach **noch ein
zweites** `commit()` ausführten. Der doppelte Commit führte im
Produktions-Request zu einer `InvalidRequestError`/abgebrochenen
Transaction → **HTTP 500 beim Verwerfen (Single, Bulk, Quick-Action) und
beim Importieren**.

**Fix + Commits (master):**
- `4c20d2a` — learner.py: `commit()` → `flush()` (kein eigenes Commit
  mehr; der Aufrufer ist für das Persistieren zuständig).
- `7e63eea` — api/jobs_user.py: Learner-Aufruf jeweils **vor** das eine
  `db.session.commit()` geschoben (quick_action-, normaler PATCH- und
  import-Pfad), sonst wird das UserLearnProfile nicht mehr persistiert.
- `c85e180` — scripts/rebuild_user_centroids.py: eigenes `commit()` pro
  Match ergänzt (war zuvor auf das Commit im Learner angewiesen).

**Verifiziert gegen echte Produktions-DB (SQLite, Container
localhost/bewerbungen:c85e180):** PATCH /api/jobs/matches/<id> (status
dismissed, quick_action company_rejected) → 200; PATCH
/api/jobs/matches/bulk (status dismissed) → 200. Keine Errors/Exceptions in
den App-Logs. `pytest tests/api tests/integration` lokal: 258 passed.

**Deploy-Status: ERLEDIGT.** Image `localhost/bewerbungen:c85e180` auf
Oracle-VM gebaut (aus /home/opc/bewerbungstracker), alle fünf
Bewerbungstracker-Container via
`IMAGE_TAG=c85e180 deploy/container/setup-oracle-vm.sh rebuild` neu erstellt
(Volume bewerbungen_data erhalten).

### 2026-07-15 — Bewertungs-Fallback nach OpenRouter-Freikontingent repariert (durch Codex)

**Problem:** Job-Bewertungen schlugen mit HTTP 500 fehl, obwohl die Provider-Auswahl
Modelle anzeigte. OpenRouter war erreichbar, hatte aber sein Tageslimit für Free-Modelle
erreicht (HTTP 429). Der automatische Matching-Fallback probierte danach Ollama mit dem
veralteten Modell `gemma4:12b`; auf keinem der konfigurierten Ollama-Endpunkte war dieses
Modell installiert. Dadurch konnte der Provider-Service keinen Fallback ausführen.

**Fix + Commit:**
- `6652141` — `services/job_matching/claude_utils.py`: Default für
  `MATCH_OLLAMA_FALLBACK_MODEL` auf das installierte
  `mistral-nemo-cc:latest` geändert.
- `deploy/container/setup-oracle-vm.sh`, `deploy/container/setup-vps.sh` und
  `README.md`: Fallback-Konfiguration als explizite, überschreibbare Umgebungsvariablen
  dokumentiert.
- `tests/services/test_match_eval_retry.py`: Regressionstest prüft den tatsächlich an
  Ollama übergebenen Modellnamen. `tests/services/test_ai_provider_client.py` setzt die
  vollständige Timeout-Konfiguration im gemockten Client.

**Deploy-Status: ERLEDIGT.** `/etc/bewerbungen/bewerbungen.env` enthält nun
`MATCH_FALLBACK_ENABLED=true` und
`MATCH_OLLAMA_FALLBACK_MODEL=mistral-nemo-cc:latest`. Image
`localhost/bewerbungen:6652141` wurde auf der Oracle-VM mit
`deploy/container/build.sh 6652141` gebaut und alle fünf Bewerbungstracker-Container
über `IMAGE_TAG=6652141 deploy/container/setup-oracle-vm.sh rebuild` neu erstellt.

**Verifikation:**
- RED: `venv/bin/pytest tests/services/test_match_eval_retry.py::test_constants_defaults -q`
  schlug vor der Änderung erwartungsgemäß wegen `gemma4:12b` fehl.
- GREEN: relevanter Provider-/Bewertungsbereich
  `venv/bin/pytest tests/services/test_match_eval_retry.py tests/services/test_ai_provider_client.py tests/api/test_openrouter_provider.py tests/api/test_model_validation.py tests/api/test_jobs_user.py -q`
  → **87 passed**.
- Produktion: Alle fünf Container laufen auf `localhost/bewerbungen:6652141`; interne
  und öffentliche App-Smokes liefern HTTP 200. App und Worker haben den AI-Provider-Service
  im Prozess-Environment. Ein nicht personenbezogener direkter Ollama-Test mit
  `mistral-nemo-cc:latest` lieferte eine Antwort über `via=ollama`.
- Die vollständige Suite war nicht grün: ein unabhängiger RSS-Fixture-Test
  (`tests/services/test_job_sources_rss.py::test_rss_adapter_parses_two_jobs`) scheitert,
  weil `example.com` in dieser Umgebung auf eine von der SSRF-Sperre abgelehnte Adresse
  aufgelöst wird. Der Provider-spezifische Bereich ist grün.

### 2026-07-15 — Job-Discovery-Cron wiederhergestellt (durch Codex)

**Problem:** Alle Nicht-E-Mail-Quellen standen seit dem 12. Juni beim letzten Crawl. Der
laufende Cron-Container führte die Jobs zwar stündlich aus, erreichte die App aber nicht:
`APP_INTERNAL_URL` zeigte noch auf die alte, flüchtige Docker-IP `172.17.0.1:5000`.
Nach Korrektur auf den Docker-Service-Namen wurde außerdem der zweite Fehler sichtbar:
Alle Cron-`curl`-Aufrufe übergaben `X-Cron-Token` ohne den für HTTP nötigen Doppelpunkt,
wodurch die App sie mit 403 ablehnte.

**Fix:**
- Produktion: `/etc/bewerbungen/bewerbungen.env` auf
  `APP_INTERNAL_URL=http://bewerbungen-app:5000` korrigiert und alle fünf Container über
  `IMAGE_TAG=37b357a deploy/container/setup-oracle-vm.sh rebuild` neu erstellt.
- `deploy/container/crontab`: Alle Pipeline-Aufrufe senden jetzt den gültigen Header
  `X-Cron-Token: ${JOB_CRON_TOKEN}`.
- `tests/test_crontab.py`: Regressionstest verhindert künftig Cron-Zeilen mit einem
  ungültigen Authentifizierungsheader.
- `README.md`: Docker-Hinweis zur stabilen internen App-Adresse ergänzt.

**Lokale Verifikation:** RED: `venv/bin/pytest tests/test_crontab.py -q` → erwarteter
Fehlschlag vor dem Fix. GREEN:
`venv/bin/pytest tests/test_crontab.py tests/services/test_cron_auth.py tests/api/test_jobs_cron.py -q`
→ 25 passed.

**Deploy-Status: ERLEDIGT.** Image `localhost/bewerbungen:16537d0` wurde auf der
Oracle-VM gebaut und alle fünf Container über `setup-oracle-vm.sh rebuild` neu erstellt.
Alle laufen auf diesem Tag; interne Cron→App- und öffentliche HTTP-Smokes liefern 200.
Ein manuell über den normalen Cron-Pfad gestarteter Crawl-Task wurde `done`
(`source_id=14`, 9 neue Jobs, 27 Matches, keine Fehler). Die überfälligen Quellen werden
ab jetzt wieder round-robin im regulären Stundenrhythmus abgearbeitet.

### 2026-07-06 (2) — OpenRouter-Modellauswahl repariert + Oracle-VM-Deploy (durch Codex)

**Ausgangslage:** Die Backup-KI-Auswahl zeigte `OpenRouter`, aber das Modell-Dropdown blieb bei `⚠️ Models nicht verfügbar`. Der zentrale `ai-provider-service` meldete OpenRouter bereits als `configured=True` und lieferte 27 Modelle; der Bewerbungstracker-Proxy blockte aber `/api/providers/openrouter/models`, weil `openrouter` lokal noch nicht in den Provider-Allowlists stand.

**Fix + Commit:**
- `4468d7b` — `api/providers.py`: `openrouter` als gültiger Provider für Models, Primary und Backup zugelassen.
- `4468d7b` — `api/profile.py`: Pro-Task-Modell-Overrides akzeptieren `openrouter`.
- `4468d7b` — `index.html`: OpenRouter in der Hauptprovider-Liste und Anzeigenamensmap ergänzt.
- `4468d7b` — `tests/api/test_openrouter_provider.py`, `tests/test_frontend_model_selection.py`: Regressionstests für Models-Proxy, Backup-Settings, Pro-Task-Override und Frontend-Aufnahme.

**Deploy-Status:** Erledigt. Produktion läuft auf Oracle VM mit allen 5 Bewerbungstracker-Containern auf `localhost/bewerbungen:4468d7b` (`app`, `worker`, `cron`, `email-service`, `imap-proxy`). `origin/master` enthält den Fix-Commit.

**Verifikation:**
- Lokal: `venv/bin/pytest tests/api/test_openrouter_provider.py` → RED vor Fix (3x 400), danach GREEN.
- Lokal: `venv/bin/pytest tests/api/test_openrouter_provider.py tests/api/test_model_validation.py tests/api/test_feature_models.py tests/test_frontend_model_selection.py` → 23 passed.
- Lokal: Inline-Script-Syntaxcheck für `index.html` → `inline scripts ok: 3`.
- Vor Deploy auf Produktion bestätigt: `ai-provider-service` liefert für `openrouter` 27 Modelle und meldet `configured=True`, `system=True`.
- Image auf Oracle VM gebaut: `localhost/bewerbungen:4468d7b`.
- Alle 5 Container via `IMAGE_TAG=4468d7b deploy/container/setup-oracle-vm.sh rebuild` neu erstellt.
- Oracle VM: alle 5 Container laufen mit Image `localhost/bewerbungen:4468d7b`.
- VM-App-Smoke: `http://127.0.0.1:5000/` → 200.
- Public Smoke: `https://bewerbungen.wolfinisoftware.de/` → 200.
- IMAP-Proxy: `http://127.0.0.1:8765/ping` → 200.
- Email-Service: `http://127.0.0.1:8766/api/status` → 200.
- Ursprünglicher Fehlerpfad: `GET /api/providers/openrouter/models` über die Bewerbungstracker-App → HTTP 200, `model_count=27`, `free_count=27`, Default `cognitivecomputations/dolphin-mistral-24b-venice-edition:free`.

### 2026-07-06 — Free/Paid-Modellauswahl konsolidiert + Oracle-VM-Deploy (durch Codex)

**Ausgangslage:** Die AI-Provider-UI zeigte opencode-Free-Modelle bereits an, behandelte Free/Paid aber an mehreren Stellen leicht unterschiedlich. Die Pro-Task-Dropdown-Logik hatte zusätzlich einen JS-Namensfehler (`currentOv` gesetzt, danach `current` gelesen), wodurch einzelne Override-Dropdowns beim Nachladen stolpern konnten.

**Fix + Commit:**
- `db833e2` — `index.html`: gemeinsamer Free/Paid-Helfer für Standard-Modell, Backup-KI und Pro-Task-Dropdowns; `free_models` aus der API wird genutzt, `-free` bleibt Fallback; opencode-Paid-Modelle werden ohne eigenen Key ausgeblendet; sichtbare Defaults werden robust ausgewählt; `currentOv/current`-Bug behoben. Neuer Regressionstest in `tests/test_frontend_model_selection.py`.

**Deploy-Status:** Erledigt. Produktion läuft auf Oracle VM mit allen 5 Bewerbungstracker-Containern auf `localhost/bewerbungen:db833e2` (`app`, `worker`, `cron`, `email-service`, `imap-proxy`). `origin/master` enthält den Fix-Commit.

**Verifikation:**
- Lokal: `venv/bin/pytest tests/test_frontend_model_selection.py tests/services/test_ai_provider_client.py::test_get_models_raw_returns_full_response_with_free_models tests/services/test_ai_provider_client.py::test_get_models_still_returns_only_list tests/api/test_model_validation.py` → 11 passed.
- Lokal: Inline-Script-Syntaxcheck für `index.html` → `inline scripts ok: 3`.
- Image auf Oracle VM gebaut: `localhost/bewerbungen:db833e2`.
- Alle 5 Container via `IMAGE_TAG=db833e2 deploy/container/setup-oracle-vm.sh rebuild` neu erstellt.
- Oracle VM: alle 5 Container laufen mit Image `localhost/bewerbungen:db833e2`.
- VM-App-Smoke: `http://127.0.0.1:5000/` → 200.
- Public Smoke: `https://bewerbungen.wolfinisoftware.de/` → 200.
- IMAP-Proxy: `http://127.0.0.1:8765/ping` → 200.
- Email-Service: `http://127.0.0.1:8766/api/status` → 200 (`/health` existiert dort nicht und liefert erwartbar 404).
- App + Worker DB-URI: beide `sqlite:////app/data/bewerbungstracker.db`.
- Laufender App-Container enthält den neuen Frontend-Code (`modelTierBuckets`, opencode-Free-Modus-Hinweis); App-Logs zeigen nur normale Starts/GETs.

### 2026-07-04 — Admin-Dashboard-Healthchecks repariert + Oracle-VM-Deploy (durch Codex)

**Ausgangslage:** `4a3f1fe` enthielt bereits den IMAP-Proxy-Fix (`do_GET` für `/` und `/ping`) und wurde initial deployed. Danach war der Admin-Status-Overview beim IMAP-Proxy grün, meldete aber weiterhin `ai_provider` als Fehler, weil `api/admin.py` hart `http://ai-provider:8767/health` nutzte. Der laufende `ai-provider` ist auf der Oracle-VM zwar healthy, hängt aber nicht im `bewerbungen-net`; die produktive App nutzt stattdessen die konfigurierte `AI_PROVIDER_SERVICE_URL`.

**Fix + Commits:**
- `06e5460` — `imap_proxy.py`: `GET /` und `GET /ping` liefern Healthcheck-JSON statt HTTP 501.
- `4a3f1fe` — Changelog-Dokumentation zum IMAP-Proxy-Fix.
- `751e97c` — `api/admin.py`: Admin-Status-Overview nutzt für den AI-Provider `AI_PROVIDER_SERVICE_URL` + `/health`, mit Fallback auf den bisherigen Docker-DNS-Namen. Neuer Regressionstest in `tests/api/test_admin_status_overview.py`.

**Deploy-Status:** Erledigt. Produktion läuft auf Oracle VM mit allen 5 Bewerbungstracker-Containern auf `localhost/bewerbungen:751e97c` (`app`, `worker`, `cron`, `email-service`, `imap-proxy`). `origin/master` enthält die Fix-Commits.

**Verifikation:**
- `venv/bin/pytest tests/api/test_admin_status_overview.py -q` → RED vor Fix, danach `1 passed`.
- `venv/bin/pytest tests/test_admin_workflow.py tests/api/test_admin_url_cleanup.py tests/test_security_headers.py -q` → 35 passed.
- Image auf Oracle VM gebaut: `localhost/bewerbungen:751e97c`.
- Alle 5 Container via `deploy/container/setup-oracle-vm.sh rebuild` neu erstellt.
- Oracle VM: alle 5 Container laufen mit Image `localhost/bewerbungen:751e97c`.
- Worker-DB-URI-Check ohne Geheimnis-Ausgabe: erwarteter absoluter SQLite-Pfad bestätigt.
- VM-App-Smoke: `http://127.0.0.1:5000/` → 200.
- Public Health: `https://bewerbungen.wolfinisoftware.de/` → 200.
- IMAP-Proxy: `http://127.0.0.1:8765/ping` → `status=ok`.
- Admin Status-Overview im App-Container mit geladener `/app/.env`: `imap_proxy=ok`, `ai_provider=ok`.

### 2026-07-03 (3) — CDN JS-Libraries vendored, PDF-Export repariert (durch pi)

**Problem:** Der PDF-Export über `exportPDF()` funktionierte trotz korrektem CSP-Fix (`4c83c86`) nicht. Der Service Worker (`service-worker.js`) interceptete alle GET-Requests, inkl. Cross-Origin-CDN-Anfragen, und cachete sie. Aufgrund eines MIME-Type-Konflikts (`text/html` statt `application/javascript`) blockierte der Browser alle vier CDNJS-Skripte (`jsPDF`, `jspdf-autotable`, `pdf.js`, `mammoth`).

**Root Cause:** Der Service Worker (`service-worker.js`) hat einen `fetch`-EventListener, der GET-Requests für statische Assets (erkennbar an Endungen wie `.js`, `.css`, etc.) cache-first bedient. CDNJS lieferte korrektes `application/javascript` an curl, aber der Chromium-Browser erhielt `text/html` — vermutlich durch den SW-Cache-Mechanismus. Dadurch blockte der Browser alle externen Skripte.

**Fix (dieser Commit):**
- Alle CDNJS-Libraries lokal in `components/vendor/` hinterlegt (jsPDF, AutoTable, pdf.js, mammoth)
- `index.html`: `<script src="https://cdnjs.cloudflare.com/...">` → `<script src="/components/vendor/...">`
- `index.html`: `pdfjsLib.GlobalWorkerOptions.workerSrc` zeigt jetzt auf `/components/vendor/pdf.worker.min.js`
- `app.py` CSP: `https://cdnjs.cloudflare.com` aus `script-src` und `worker-src` entfernt (wird nicht mehr benötigt)
- `tests/test_security_headers.py`: Test angepasst

**Verifikation:**
- `venv/bin/pytest tests/test_security_headers.py` → PASSED
- Playwright-Browser: `window.jspdf` ist nach Page-Load definiert ✅
- PDF-Export-Button erzeugt PDF ohne Fehler

**Dokumentation:**
- AGENTS.md §3.4.1 aktualisiert: „Browser assets — all vendored (no CDN)"

### 2026-07-03 (2) — Kalenderparser: Termine mit Firmenprefix werden jetzt erkannt (durch pi/opencode)

**Problem:** Interview-Termine in Bewerbungs-Notizen wurden nicht erkannt, wenn vor dem Datum ein Firmenname stand (z.B. "Pfeifer & Langen IT-Solutions KG - Interview Termin am 26. Mai 2026 um 16:30") oder wenn die Uhrzeit ohne "Uhr"-Suffix notiert war ("26. Mai 2026 um 16:30").

**Root Cause:** Zwei Regex-Bugs in `services/calendar_parser.py`:
1. `_RE_DATE_GERMAN_MONTH` und `_RE_DATE_FLEX_TIME` erwarteten `\s*Uhr?` als erforderliches Ende → ohne "Uhr" kein Match
2. Beide Patterns erlaubten keinen Prefix vor dem Datum → Firmennamen vor dem Datum blockierten den Match

**Fix + Commit:**
- `86d296f` — `services/calendar_parser.py`: 
  - `_RE_DATE_GERMAN_MONTH`: `.*?` Prefix + `(?:\s*Uhr?)?` optionales Suffix
  - `_RE_DATE_FLEX_TIME`: `.*?` Prefix + `(?:\s*Uhr?)?` optionales Suffix

**Deploy-Status:** Erledigt. Produktion läuft auf Oracle VM mit allen 5 Bewerbungstracker-Containern auf `localhost/bewerbungen:20260703-084027`.

**Verifikation:**
- `venv/bin/pytest tests/test_calendar_parser.py tests/test_calendar_endpoint.py` → 16 passed (lokal)
- Image auf Oracle VM gebaut: `localhost/bewerbungen:20260703-084027`.
- Alle 5 Container via `deploy/container/setup-oracle-vm.sh rebuild` neu erstellt.
- VM-App-Smoke: `http://127.0.0.1:5000/` → 200.
- VM-Test: `parse_interview_event("Pfeifer & Langen IT-Solutions KG - Interview Termin am 26. Mai 2026 um 16:30")` → `2026-05-26 16:30:00+02:00` ✅
- VM-Test: `parse_interview_event("26. Mai 2026 um 16:30")` → `2026-05-26 16:30:00+02:00` ✅
- VM-Test: `parse_interview_event("2.6.2026 um 11:00")` → `2026-06-02 11:00:00+02:00` ✅

### 2026-07-03 — PDF-Export durch CSP repariert + Oracle-VM-Deploy (durch Codex)

**Problem:** Der clientseitige PDF-Export der Bewerbungsübersicht funktionierte nach dem Security-Header-Commit vom 2026-06-26 nicht mehr. `index.html` lädt `jsPDF`, `jspdf-autotable`, `pdf.js` und `mammoth` von `cdnjs.cloudflare.com`, aber die produktive CSP erlaubte in `script-src` nur `'self'`. Dadurch wurden die Browser-Libraries blockiert, bevor `exportPDF()` arbeiten konnte. Der serverseitige Anschreiben-PDF-Renderer war nicht die Ursache: die letzten 10 gespeicherten Anschreiben ließen sich im Produktivcontainer ohne Inhaltsausgabe erfolgreich zu PDF-Bytes rendern.

**Fix + Commit:**
- `4c83c86` — `app.py`: CSP erlaubt jetzt `https://cdnjs.cloudflare.com` in `script-src`; `worker-src` erlaubt `'self' blob: https://cdnjs.cloudflare.com`, damit der `pdf.js` Worker ebenfalls funktioniert. Regressionstest in `tests/test_security_headers.py`.

**Deploy-Status:** Erledigt. Produktion läuft auf Oracle VM mit allen 5 Bewerbungstracker-Containern auf `localhost/bewerbungen:4c83c86` (`app`, `worker`, `cron`, `email-service`, `imap-proxy`). `origin/master` enthält den Fix-Commit.

**Verifikation:**
- `venv/bin/pytest tests/test_security_headers.py tests/api/test_cover_letters.py::test_export_pdf_success tests/api/test_cover_letters.py::test_export_import_error_returns_503` → 3 passed.
- Image auf Oracle VM gebaut: `localhost/bewerbungen:4c83c86`.
- Alle 5 Container via `deploy/container/setup-oracle-vm.sh rebuild` neu erstellt.
- Oracle VM: alle 5 Container laufen mit Image `localhost/bewerbungen:4c83c86`.
- Worker-DB-URI: `sqlite:////app/data/bewerbungstracker.db`.
- VM-App-Smoke: `http://127.0.0.1:5000/` → 200.
- Public Health: `https://bewerbungen.wolfinisoftware.de/` → 200.
- Public CSP enthält `https://cdnjs.cloudflare.com` und `worker-src 'self' blob: https://cdnjs.cloudflare.com`.
- App-/Worker-Logs nach Start ohne Fehler.

### 2026-07-02 — Jobvorschlags-Zähler nach Reject-Filter korrigiert + Oracle-VM-Deploy (durch Codex)

**Problem:** Die Jobvorschlagsliste konnte "3 offene" anzeigen, obwohl alle sichtbaren Vorschläge bearbeitet waren. Ursache war ein Zähler-/Listen-Drift in `GET /api/jobs/matches`: `total` wurde vor dem normalisierten Firmen-Reject-Postfilter berechnet. Vorschläge wie `Signal Iduna Group AG` wurden dadurch nachträglich aus `matches` entfernt, blieben aber im `total`.

**Fix + Commit:**
- `7aab588` — `api/jobs_user.py`: Wenn der normalisierte Reject-Filter aktiv ist, wird die finale gefilterte Ergebnismenge vor Count und Pagination gebildet. Regressionstest in `tests/api/test_jobs_user.py` für drei vollständig ausgefilterte Firmen-Suffix-Treffer.

**Deploy-Status:** Erledigt. Produktion läuft auf Oracle VM mit allen 5 Bewerbungstracker-Containern auf `localhost/bewerbungen:7aab588` (`app`, `worker`, `cron`, `email-service`, `imap-proxy`). `origin/master` enthält den Fix-Commit.

**Verifikation:**
- `venv/bin/pytest tests/api/test_jobs_user.py -q` → 51 passed.
- Oracle VM: alle 5 Container laufen mit Image `localhost/bewerbungen:7aab588`.
- Worker-DB-URI: `sqlite:////app/data/bewerbungstracker.db`.
- VM-App-Smoke: `http://127.0.0.1:5000/` → 200.
- Public Health: `https://bewerbungen.wolfinisoftware.de/` → 200.

### 2026-07-01 — Kalenderansicht stabilisiert + Oracle-VM-Deploy (durch Codex)

**Ausgangslage:** Die Kalenderansicht zeigte nur "Lade Termine …" bzw. einzelne Termine mit falschem Jahr. Der erste Parser-Fix war zwar als Live-Hotfix in App/Worker sichtbar, aber noch nicht als Image dauerhaft deployed.

**Fixes + Commits:**
- `cbc15b8` — `services/calendar_parser.py`: deutsche Monatsnamen (`3. Juli 2026`) und flexible Uhrzeiten ohne Minuten (`11 Uhr`) werden erkannt. Danach Image `localhost/bewerbungen:cbc15b8` gebaut und alle 5 Container via `deploy/container/setup-oracle-vm.sh rebuild` neu erstellt, damit der Live-Hotfix nicht beim nächsten Recreate verschwindet.
- `1953a5c` — `/api/applications/upcoming`: falsches Feld `parsed.meeting_passcode` → `parsed.passcode`. Vorher warf jeder erkannte Termin mit Passcode einen 500er, wodurch die Kalenderliste hängen blieb. Regressionstest in `tests/test_calendar_endpoint.py`.
- `0f4d0d5` — `index.html`: `loadCalendarEvents()` war versehentlich innerhalb des offenen `loadDeletedEntries()`-Blocks gelandet. Dadurch wurde im Browser kein `/api/applications/upcoming`-Request ausgelöst und die UI blieb bei "Lade Termine …". Neuer Jest-Strukturtest `frontend/js/calendar-view-structure.test.js`.
- `83a3d11` — jahreslose Termine wie `10.6. um 09:30` werden in Kalender/ICS nicht mehr gegen das aktuelle Datum aufgelöst, sondern gegen den Kontext der Quelle: Email-Timestamp oder `Application.applied_date`/`created_at`. Der BOCHUM-Eintrag `41dc1f5a-5643-46dd-b7a8-03eb1988c792` wurde dadurch von `2027-06-10` auf `2026-06-10` korrigiert.

**Deploy-Status:** Erledigt. Produktion läuft auf Oracle VM mit allen 5 Bewerbungstracker-Containern auf `localhost/bewerbungen:83a3d11` (`app`, `worker`, `cron`, `email-service`, `imap-proxy`). `origin/master` ist auf `83a3d11` gepusht.

**Verifikation:**
- `venv/bin/pytest tests/test_calendar_parser.py tests/test_calendar_endpoint.py tests/test_calendar_ics.py -q` → 19 passed.
- `npm test -- frontend/js/calendar-view-structure.test.js --runInBand` → 1 passed.
- Prod-Smoke: `/api/applications/upcoming` → 200, 5 Termine.
- Prod-Smoke BOCHUM: Kalenderliste und ICS liefern beide `2026-06-10T09:30:00+02:00`.
- Public Health: `https://bewerbungen.wolfinisoftware.de/` → 200.

### 2026-06-26 — Feedback-Learning verbessert (durch Codex)

- Adaptive Job-Score-Anpassung balanciert stark ungleiche `imported`/`dismissed`-Samples, damit viele Ablehnungen gute Import-Signale nicht vollständig überrollen.
- Wiederholte strukturierte Feedback-Gründe wirken konservativ auf spätere Scores; `wrong_seniority` senkt passende Seniority-Muster, `missing_skills` wirkt als kleine Zusatzbremse.
- Quick-Actions und Bulk-Dismisses aktualisieren jetzt ebenfalls das `UserLearnProfile`, sofern Job-Embeddings vorhanden sind.
- Tests stabilisiert: Source-/Cron-Tests patchen den SSRF-Guard lokal, damit `example.com`-DNS in der lokalen Umgebung nicht die eigentliche Endpoint-Logik verdeckt.
- Verifikation: `venv/bin/pytest tests/services/test_learner.py tests/services/test_prefilter_learner.py tests/api/test_quick_actions_endpoint.py tests/api/test_jobs_user.py tests/integration/test_learning_e2e.py -v` → 70 passed; `venv/bin/pytest tests/api/test_jobs_cron.py -v` → 20 passed.

### 2026-06-26 — CV-leere-Matches Guard + Auto-Reaktivierung bei CV-Upload (durch pi/Claude Code)

**Problem:** Wenn ein User noch keinen Lebenslauf (CV) hinterlegt hatte, wurden Matches trotzdem ans Bewertungs-LLM geschickt. Das Modell antwortete mit Metatext wie `"CV empty - cannot assess required skills"` in `missing_skills`, der im UI 1:1 als "⚠ Fehlt im CV:" angezeigt wurde — verwirrend und semantisch falsch. Zudem erhielten diese Matches einen Score (meist 0) und fielen damit dauerhaft aus der Bewertungs-Queue (`match_score IS NULL`-Filter), sodass sie nie neu bewertet wurden, selbst wenn der User später einen CV anlegte.

**Lösung (zwei Teile):**
1. **Guard in `_run_claude_match_for`** (`services/job_matching/claude_utils.py`): Bei leerem `cv_summary` wird der Match **nicht** ans LLM geschickt. Stattdessen:
   - `match_score` bleibt `NULL` → Match bleibt in der Queue
   - `match_reasoning` = klarer Hinweis: "Noch kein Lebenslauf hinterlegt – wird automatisch bewertet, sobald du einen Lebenslauf (CV) anlegst."
   - `missing_skills = []` (kein Metatext als "Skill")
   - `eval_attempts` **nicht** erhöht → Match fällt auch nach vielen Ticks nicht aus der Queue
   
2. **Auto-Reaktivierung beim CV-Upload** (`api/profile.py:update_cv` + `reset_empty_cv_matches` in `claude_utils.py`): Wenn ein User einen CV speichert, werden **alle** seine Matches, die die "CV empty"-Signatur in `missing_skills` tragen (z.B. "CV empty - cannot assess required skills"), auf `match_score=NULL` zurückgesetzt. Der nächste Cron-Lauf bewertet sie dann mit dem echten CV sauber neu.

**Geänderte Dateien (4):**
- `services/job_matching/claude_utils.py` — +`NO_CV_REASONING` Konstante, Guard in `_run_claude_match_for`, neue Funktion `reset_empty_cv_matches(user_id)`.
- `api/profile.py` — Import + Aufruf von `reset_empty_cv_matches(user.id)` in `update_cv`, Response-Feld `reactivated_matches`.
- `tests/api/test_jobs_cron.py` — 4 neue Tests: Guard-Logik (leerer CV → kein LLM-Call, `eval_attempts` nicht erhöht), `reset_empty_cv_matches` (reaktiviert Signatur-Matches, ignoriert echte Skills).
- `CHANGELOG.md` — dieser Eintrag.

**Verifikation:** `pytest tests/api/test_jobs_cron.py` (20/20 passed, inkl. 4 neue). Breitere Suite: 376/377 passed (1 pre-existing failure in `test_ai_provider_client.py`, unabhängig).

### 2026-06-23 — URL-Normalisierung beim Speichern von RawJobs + Deploy (durch pi/Claude Code)

**Problem:** Der "Original"-Link bei Job-Vorschlägen führte oft auf tote Seiten (HTTP 500) — Tracking-Links von StepStone/LinkedIn/Indeed waren abgelaufen.

**Lösung:** Neue Funktion  in  ohne Netzwerk-Calls:
  - **LinkedIn:**  → 
  - **StepStone:** Magic-Link → öffentliche Anzeigen-URL aus 
  - **Alle:** Tracking-Parameter entfernt (, , , …)
  - Fehlschlag sicher: unbekanntes Format → Original-URL bleibt erhalten

**Geänderte Dateien (3):**
  - : +  (synthetische Normalisierung)
  - :  → 
  - :  beim RawJob-Erzeugen

**Deployed:** Image  auf oracle-vm, alle 5 Container recreatet, Funktion verifiziert.
**Git:**  auf , gepusht.

### 2026-06-23 — Prod-Fix: StepStone-Tracking-URL + fehlende Company bei Match #3640 (durch pi/Claude Code)

**Symptom:** Letzter Job-Vorschlag (Match #3640 / RawJob #3209 — "IT Security Operation Koordinator (m/w/d)") hatte eine StepStone-Tracking-URL (`click.stepstone.de/f/a/...`) statt der echten Stellenanzeige. Company-Feld war leer (`None`). Beim Öffnen/Import kam HTTP 500.

**Fix (Production-DB auf Oracle VM, kein Code-Commit):**
- `RawJob #3209.url` aktualisiert: `click.stepstone.de/f/a/...` → `https://www.stepstone.de/stellenangebote--IT-Security-Operation-Koordinator-m-w-d-Neuss-Pierburg-GmbH--13966783-inline.html`
- `RawJob #3209.company` gesetzt: `None` → `Pierburg GmbH`

**Verifikation:** Match #3640: status=new, score=75.0, Company=Pierburg GmbH, URL=stepstone.de/stellenangebote--IT-Security-...

### 2026-06-05 — Quick-Reasons-UI Phase 1: Tasks 4-9 implementiert (durch opencode)
- **Task 4** ✅ — `services/job_matching/quick_actions.py` + 11 Unit-Tests. `apply_quick_action()` mit 4 Aktionen (company_rejected, already_applied, job_unavailable, wrong_job_type). Idempotent, ProtectedStatuses gegen Downgrade. QuickActionError -> 400.
- **Task 5** ✅ — PATCH `/api/jobs/matches/<id>` versteht `quick_action` + `job_type`. Setzt status='dismissed' implizit, ignoriert user-feedback_text bei quick_action. 6 Integration-Tests.
- **Task 6** ✅ — `/api/profile/job-discovery` GET+PATCH für `job_type_blacklist`. Validierung via `VALID_JOB_TYPES`. 6 Tests.
- **Task 7** ✅ — Frontend: 4 Quick-Action-Buttons im Dismiss-Modal, AI-Reasons in `<details>` zugeklappt. Mobile-Responsive.
- **Task 8** ✅ — Frontend: 3 Job-Typ-Checkboxes im Profil-Tab. Load/Save via loadJobDiscoveryFilters/saveJobDiscoveryFilters.
- **Task 9** ✅ — `pytest tests/services/ tests/api/` → 298 passed, 0 failed. Keine Regression.
- Deployed to IONOS VPS.
- **Nächste Schritte:** —
### 2026-06-05 — Weekly Summary mit dynamischen Inhalten
- **email_service.py:** `check_and_send_summary()` erzeugt jetzt eine HTML-E-Mail mit:
  - Gesamtstatistik (Bewerbungen, Status-Verteilung)
  - Wochen-Werte (neue, Absagen, Gespräche, Zusagen)
  - Neue/Vorworfene Job-Vorschläge
  - Letzte Aktivitäten (10 neueste Status-Änderungen)
  - Korrekter Link zur App (`APP_URL` statt `localhost:8080`)
- **DB-Pfad-Fix:** `_get_main_db_path()` parsed `sqlite:////abs/path` korrekt (fehlender führender `/`)
- **SMTP-Encryption-Fix:** Encryption-Key wird in Config persistiert, überlebt Container-Neustarts
- **email_config.db** liegt jetzt auf dem schreibbaren Volume (`/app/data/`)
- **SMTP-Konfiguration** aktualisiert (IONOS-Passwort neu gesetzt)
- Deployed to IONOS VPS (Container-Image neugebaut + Email-Service restarted)
### 2026-06-05 — Weekly Summary Fix: baked-in .env override root cause
- **Root Cause:** `docker-entrypoint.sh` sourced `/app/.env` nach Quadlet-Env-Init → baked-in `DATABASE_URL=sqlite:///bewerbungstracker.db` überschrieb Quadlets `sqlite:////app/data/instance/...`
- **Fix:** `.env` zu `.dockerignore` hinzugefügt + `/var/www/bewerbungen/.env` auf VPS gelöscht + Image neugebaut + alle Container restarted
- Alle Container haben jetzt korrekte `DATABASE_URL` im Prozess-Env (via `/proc/<pid>/environ` verifiziert)
- **Lehre:** Baked-in `.env` im Image ist gefährlich wenn es env-Vars setzt die Quadlet vorgibt. `docker-entrypoint.sh` sollte entweder kein `.env` sourcen oder nur für lokale Dev-Umgebung.
### 2026-06-05 — Auto-Reject-Analyse + Quick-Win-Fixes
- **Analyse Prod-DB:** 1.786/1.891 JobMatches dismissed (94 %), aber `company_already_rejected` traf nur 7×. Den 138 manuellen User-Texten standen 12+ Fälle „X hat schon abgesagt" gegenüber → zwei Lücken identifiziert: (a) Suffix-Mismatch („Signal Iduna" vs. „Signal Iduna Group AG"), (b) Status `ghosting` nicht in Reject-Set.
- **Fix 1 — Company-Normalisierung:** Neuer Helper `services/email_import_utils.py::normalize_company()` (Rechtsformen-Strip GmbH/AG/KG/SE/Ltd/Inc + „Group/Holding/International" + Trailing-Klammern). `get_rejected_companies_lower()` liefert normalisiertes Set. Alle 4 Vergleichsstellen umgestellt (cron_prefilter, email_import, cron_indeed_email_import, api/jobs_user). Inline-Duplikat in cron_prefilter entfernt.
- **Fix 2 — Status-Set:** `'ghosting'` zum Reject-Set ergänzt (`_REJECTING_STATUSES`). Konsistent mit `feedback_bridge.py::_TERMINAL_STATES`-Mapping ghosting → rejected_after_apply. Prod-DB: 9 ghosting-Apps werden ab jetzt für Auto-Reject genutzt.
- **AGENTS.md §3.6:** Neue Regel — `/loop` bei Polling/wiederkehrenden Tasks (Claude Code) statt Sleep-Schleifen. opencode-Pendant aktuell unbekannt.
- **Tests:** 17 neue Tests (`tests/services/test_email_import_utils.py`) — Normalisierung + DB-Integration (Status-Set, Window, soft-deleted). 17/17 passed. Breiter Sweep `tests/services/ tests/api/` → 490 passed (7 Fehler durch lokal fehlendes jsonschema, unabhängig).
- NICHT deployed to IONOS. Backwards-kompatibel — alte Daten bleiben in DB, neuer Prefilter greift ab Deploy.

### 2026-06-06 — opencode: Body-Phrasen-Scan + Keyword-Blacklist + Fuzzy-Dup + Postfix-Mails
Alle Backlog-Items aus dem vorherigen Handoff wurden in dieser Session implementiert und deployed:
- **Body-Phrasen-Scan:** `scan_body_reject()` in `email_import_utils.py` erkennt 13 Phrasen ("werden keine Bewerbungen mehr angenommen", "Bewerbungsfrist abgelaufen" etc.) → auto-dismiss mit `feedback_text='body_phrase_rejected'`
- **User-Keyword-Blacklist:** Neue DB-Spalte `job_keyword_blacklist` + API (GET/PATCH `/profile/job-discovery/filters`) + Frontend-Textarea + Cron-Check
- **Cross-Portal-Fuzzy-Duplicate:** `SequenceMatcher` (threshold 0.85) für Titel-Ähnlichkeit + normalisierte Company über verschiedene Portale hinweg
- Image neugebaut + alle 5 Container restarted ✓

### 2026-06-01 — README-Links gefixt, .serena/ ignoriert, AGENTS-Hash korrigiert
- README English: fehlende Job-Discovery/DEPLOYMENT.md/Technology Bullets ergänzt
- README: 4 broken Deployment-Links korrigiert (`docs/DEPLOYMENT/DEPLOYMENT_*.md` → `DEPLOYMENT_*.md` im Root bzw. `docs/DEPLOYMENT_PRODUCTION.md`)
- AGENTS.md: Commit-Hash `a573167` → `816cd7c` korrigiert
- `.gitignore`: `.serena/` hinzugefügt
- Getestet: kein Code angefasst, README-Links manuell verifiziert
- NICHT deployed to IONOS

### 2026-06-01 — Containerisierung deployed + Fixes (3 Runden)
1. **Erster Deploy:** Alle 5 Container auf VPS, App HTTP 200 ✓
2. **Bugfix Runde 1:** `Exec` überschreibt CMD, nicht ENTRYPOINT → nur Rollenname
3. **Bugfix Runde 2:** `.env` überschrieb `AI_PROVIDER_SERVICE_URL` mit `127.0.0.1` → Container-Env via Quadlet ging verloren. Fix: `.env` korrigiert + Image neugebaut
4. **Bugfix Runde 3:** `host.containers.internal` resolvt auf `bewerbungen-net` Gateway (10.89.1.1), nicht zum `podman`-Bridge (10.88.0.1) wo ai-provider lauscht. Fix: `http://10.88.0.1:8767`
5. **SELinux:** `:Z` → `:z` für Shared-Volume-Zugriff (app+worker+imap+email+cron)
6. **Netzwerk:** Custom `bewerbungen-net` damit Container-DNS funktioniert
7. **supercronic PID-1 Bug:** Kein `exec` in cron-Rolle

### 2026-06-01 — Email/IMAP-Container: BIND_HOST-Fix
- IMAP-Proxy und Email-Service banden an `127.0.0.1` → nach DNAT (host→container) kamen Pakete auf eth0 an, Service hörte nur auf lo → Connection Refused
- Fix: `BIND_HOST=0.0.0.0` per env-var, überschreibt config.json + Default
- `imap_proxy.py`: zusätzlich `os.getenv('BIND_HOST')` in load_config → gewinnt immer
- `email_service.py`: `HOST = os.getenv('BIND_HOST', '127.0.0.1')`
- GETESTET: IMAP 400, Email 404 (korrekt — Services laufen und antworten)
- DEPLOYED to IONOS VPS

### 2026-06-01 — Containerisierung: Dockerfile + 5 Podman Quadlets
- Dockerfile: single-stage python:3.12-slim, multi-role (app/worker/imap-proxy/email-service/cron)
- 5 Quadlet `.container` files passend zum ai-provider-service-Pattern
- Cron-Container mit supercronic + crontab (alle 5 Stages + indeed-email-import + backup)
- `.dockerignore` aktualisiert (imap_proxy/email_service nicht mehr exkludiert)
- `deploy/container/setup-vps.sh` für Einmal-Setup auf dem VPS
- GETESTET: `podman build` + alle 5 Container laufen auf dem VPS, App antwortet HTTP 200, API HTTP 401 (korrekt)
- DEPLOYED TO IONOS VPS (Podman Quadlets, Rocky Linux 9.8)
- **Wichtig bei Podman-Updates:** supercronic hat einen PID-1-Bug — docker-entrypoint.sh verwendet nicht `exec` für die cron-Rolle

### 2026-06-02 — Ollama-Modelle + opencode.ai als zentraler Provider
- **Bug: AI Provider zeigte "Keine Models verfügbar"** — 3 Ursachen:
  1. App-Container auf `bewerbungen-net` (10.89.x.x), AI-Provider hatte nur Pasta-Netzwerk → unterschiedliche Netze, `10.88.0.1:8767` unerreichbar
  2. `OLLAMA_URL=http://host.containers.internal:11434` → DNS löst auf dem Host/Container nicht auf
  3. Container-Image hatte baked-in `.env` mit veralteter `AI_PROVIDER_SERVICE_URL` → Eintrypoint `source .env` überschrieb `EnvironmentFile`
- Fixes (VPS, rootless Podman):
  - `Network=bewerbungen-net` zum ai-provider Quadlet hinzugefügt
  - `AI_PROVIDER_SERVICE_URL=http://ai-provider:8767` (DNS auf Bridge)
  - `OLLAMA_URL=http://10.89.0.1:11434` (Host-Bridge-IP, SSH-Tunnel auf `0.0.0.0`)
  - Volume-Mount `/etc/bewerbungen/bewerbungen.env:/app/.env:Z` + chmod 644
- **Feature: opencode.ai als zentraler Provider** (`api/providers.py`, `index.html`):
  - `'opencode'` in `VALID_PROVIDERS` + `USER_PROVIDERS`
  - Config-UI mit API-Key + optionalem Endpoint im Frontend
  - Backup-KI (Fallback) zeigt opencode automatisch (filtert `configured=true`)
- **ai-provider-service (Image neugebaut):**
  - `config.py`: `OPENCODE_API_KEY` env var
  - `opencode.py`: Fallback auf `Config.OPENCODE_API_KEY`
   - Registry: `system: True`, `requires: []`, `UNGATED_PROVIDERS+=opencode`
- **Free-Model-Gating** (`opencode.py`, `dispatcher.py`):
  - `FREE_MODELS = frozenset({'deepseek-v4-flash-free'})`
  - `_require_paid()`: ohne eigenen User-Key sind nur Free-Modelle nutzbar
  - Paid-Modelle → ValueError "erfordert eigenen opencode.ai API-Key"
  - ValueError propagiert direkt → kein Fallback/Queue (fix in `dispatcher.py`)
- **Daily-Limit für Free-Modelle** (`config.py`, `dispatcher.py`):
  - `FREE_MODEL_DAILY_LIMIT=500` (Default, via env konfigurierbar)
  - `FREE_MODEL_ADMIN_RESERVE=100` (davon reserviert für Admin `harald`)
  - `FREE_MODEL_ADMIN_UID=harald`
  - Zählt via `UsageEvent`-DB (nur `status=success`)
  - Nicht-Admin-User werden bei `limit - reserve` gestoppt
  - Budget-Überschreitung = RuntimeError (kein ValueError) → löst Fallback/Queue aus
- **Modell-Liste gecached** (`opencode.py`): `get_models()` schreibt `.models_cache_opencode.json` mit 24h TTL → einmal täglich aktualisiert
- **Hotfix** (`api/profile.py:234`): `VALID_PROVIDERS` hatte eigenes Set ohne `opencode` → `cover_letter: unbekannter Provider opencode` beim Speichern von Pro-Task-Overrides
- Deployed to IONOS VPS (beide Images neugebaut + Container restarted)
- Getestet: App→AI-Provider kommuniziert, Ollama 15 Models, Opencode 45 Models (deepseek-v4-flash etc.)

### 2026-06-01 — Learned-Patterns-Table zeigt Custom-Plattformen
- Bug: `loadLearnedPatterns()` in `index.html:4089` hatte Plattformen hardcodiert auf `['indeed', 'linkedin', 'xing']` — Patterns für Custom-Plattformen (via PlatformProfileRow) wurden nie angezeigt
- Fix: iteriert jetzt über alle Einträge der API-Antwort + Built-in-Defaults, sortiert nach Name
- Feature: Training-Toasts zeigen jetzt die Quellen-Plattform an (z.B. `🧠 STEPSTONE: 30%…`)
- Nur JS-Änderungen in `index.html` (35 insertions, 13 deletions)
- Getestet: `pytest tests/api/test_pattern_learner_api.py` (12/12 passed)
- NICHT deployed to IONOS

### 2026-06-06 — ai-provider-service Memory-Layer verfügbar (kein Code-Change hier)

**Was sich ändert:** Der Gateway (`ai-provider-service`) stellt seit gestern (PR [#14](https://github.com/haraldweiss/ai-provider-service/pull/14) + Phase 1.5/2, deployed auf VPS) eine Markdown-Memory-Schicht bereit. **Bewerbungstracker schreibt aktuell NICHT** dorthin — der Eintrag ist nur informativ, damit künftige Erweiterungen wissen dass das da ist.

**Was Bewerbungstracker tun könnte** (wenn Bedarf entsteht):
- `POST https://ai-provider-service.wolfinisoftware.de/memory/events` mit `{"user_id":"<...>", "app":"bewerbungstracker", "event_type":"application_created", "payload":{"company":"...", "position":"...", "platform":"..."}}` bei jedem neu erkannten Job
- `POST .../memory/notes` mit freien Markdown-Notizen wenn semi-strukturiert reicht
- `GET .../memory/search?q=<keyword>&user_id=<...>` zur FTS5-Suche über vergangene Jobs/Notizen (porter+unicode61)
- Vault per WebDAV unter `/ai-provider/memory/dav/?user_id=<...>` direkt in Obsidian öffnen

**Auth:** Bearer-Token (gleicher `SERVICE_TOKEN` den die App schon fürs Gateway nutzt). User-Scoping ist hart — Apps können nur auf den eigenen `user_id` schreiben außer der Token ist Admin.

**Rate-Limits seit Phase 1.5:** 60 POST/min, 120 GET/min, 5 vault-exports/min pro User — bei Bulk-Import einfach drosseln.

**Caveat:** Audit läuft automatisch beim Gateway (jeder `/chat`-Call landet in `memory_notes` mit `kind=audit`, `app=<X-Origin-App>`). Bewerbungstracker schickt schon `X-Origin-App: bewerbungstracker` — das taucht also als App-Label im audit-Vault auf. Kein Action erforderlich, nur wissen dass es so ist.

**Sibling-Repo:** [`ai-provider-service` AGENTS.md §7](https://github.com/haraldweiss/ai-provider-service/blob/main/AGENTS.md) hat den vollständigen Status. Spec/Plan: `docs/superpowers/{specs,plans}/2026-06-05-markdown-memory-*.md` im Gateway-Repo.

### 2026-06-12 — Fix: Docker-Volume-Split zwischen APP und WORKER (durch opencode)

**Root Cause:** APP- und WORKER-Container nutzten unterschiedliche Docker-Volumes:
- APP: `bewerbungen_data` (underscore, neu seit 06:31 UTC)
- WORKER: `bewerbungen-data` (hyphen, alt)
- EMAIL-SERVICE + IMAP-PROXY: `/opt/bewerbungen-data` (Host-Bind-Mount, dritte Kopie)
- CRON: kein Volume-Mount (benign, curl-only)

**Auswirkung:** Seit APP-Neustart ~06:31 UTC waren neu erstellte Tasks (6 Stück) für den WORKER unsichtbar → keine Pipeline-Verarbeitung (crawl/prefilter/claude-match/notify) seit 06:27. Email-Import lief noch bis 06:25-06:27 weil da alle Container dasselbe Volume teilten.

**Fix:**
1. `docker stop/rm bewerbungen-worker` → neuer Container mit `-v bewerbungen_data:/app/data:z`
2. `docker stop/rm bewerbungen-email-service` → neuer Container mit `-v bewerbungen_data:/app/data:z`
3. `docker stop/rm bewerbungen-imap-proxy` → neuer Container mit `-v bewerbungen_data:/app/data:z`
4. Altes Volume `bewerbungen-data` (hyphen) gelöscht
5. `deploy/container/crontab`: `Authorization: Bearer` → `X-Cron-Token` (Header matcht `require_cron_token`)

**Verifikation:** 2233 Tasks done, 0 queued, 0 running. Worker verarbeitet wieder.

**⚠ Lehre für künftige Container-Neustarts:** Bei `docker run` und Neu-Erzeugung von Containern aufpassen dass Volume-Namen identisch sind (keine Tippfehler underscore vs hyphen).

**Dokumentation:** `deploy/container/setup-oracle-vm.sh` neu erstellt — Single-Source-of-Truth für alle `docker run`-Befehle auf der Oracle VM. Commands: `setup`, `start`, `stop`, `restart`, `rebuild`, `status`, `volume-info`, `migrate`, `logs`.

### 2026-06-12 — Frontend: Import-Funktionen speicherten nur in localStorage → Refactored (durch opencode, Commit `a584dd4`)

**Root Cause:** 7 manuelle Import-Funktionen (`importScriptEmail`, `importAllScriptEmails`, `importSingleImapEmail`, `importEmlItem`, `importAllEmlEmails`, `importTextItem`, `importAllTextEmails`) in `index.html` haben Bewerbungen nur in `state.bewerbungen` + `localStorage` geschrieben, **nicht** per API auf dem Server.

**Auswirkung:** `loadFromStorage()` lädt Bewerbungen primär vom Server (`GET /api/applications`). Beim nächsten Seitenaufruf überschreibt der Server-Response den lokalen State — die manuell importierte Bewerbung war weg.

`importImapEmail` (der neuere IMAP-Pfad) machte es bereits korrekt mit `POST /api/applications` + `_mapBackendToDB()`.

**Refactoring:**
- Neue gemeinsame Funktion `_importSingleApplication(parsed, notes, sourceOverride)` — einmalige API-Logik für alle 7 Konsumenten
- `apiData` aus `parseEmailToApplication()`-Feldern gebaut (backend-Feldnamen: `company`, `position`, `status`, `applied_date`, …)
- `POST /api/applications` via `fetchAPI()`
- Response via `_mapBackendToDB(created)` in lokalen State eingefügt
- `importAll*`-Schleifen von `forEach` (async ohne await) auf `for…of` + `await` umgestellt
- Jeder Konsument ruft `_importSingleApplication` + `renderAll()` + source-spezifisches Rendering

**Betroffene Datei:** `index.html` (ca. +70 Zeilen netto).
**Deployed auf Oracle VM:** `index.html` per `docker cp` ins Container, Commit `a584dd4`, gepusht zu `github.com:haraldweiss/Bewerbungstracker`.

### 2026-06-12 — Fix: `</script>` im Template-Literal + leere Position bei Import (durch opencode)

**Problem 1:** `index.html:8080` enthielt `</script>` innerhalb eines JavaScript-Template-Literals (`...\`...<script src="..."></script>...\``). Der HTML-Parser beendete den äußeren `<script>`-Block vorzeitig → alle Funktionen danach (inkl. `_importSingleApplication`) wurden nie definiert → Seite zeigte JavaScript-Roh-Text.

**Fix:** `</script>` → `<\/script>` im Template-Literal (JS-escaped, HTML-Parser sieht es nicht).

**Problem 2:** Bei Absage-Mails wie "Deine Bewerbung / ControlExpert" extrahierte `parseEmailToApplication()` keine Position aus dem Subject → `POST /api/applications` gab 400 ("position required").

**Fix:** `_importSingleApplication` setzt `'(Keine Position)'` als Fallback wenn `parsed.position` leer ist.
**Deployed auf Oracle VM + gepusht (Commit `cd76de7`).**

### 2026-06-12 — Fix: BIND_HOST + Port-Publishing für email-service und imap-proxy (durch opencode)

**Root Cause:** Bei der Container-Neuerstellung (Volume-Fix) wurden `-p 127.0.0.1:8765:8765` / `-p 127.0.0.1:8766:8766` vergessen. Zudem fehlte `-e BIND_HOST=0.0.0.0`, wodurch die Dienste nur container-intern auf `127.0.0.1` lauschten.

**Auswirkung:** Apache auf dem Host konnte die Dienste nicht über `127.0.0.1:8765/8766` erreichen → "Email Service nicht erreichbar" im Frontend.

**Fix:**
- `-p 127.0.0.1:8765:8765` und `-p 127.0.0.1:8766:8766` zu `docker run` hinzugefügt
- `-e BIND_HOST=0.0.0.0` gesetzt (lauscht auf allen Interfaces)
- `setup-oracle-vm.sh` aktualisiert (Commit `1b96543`)

### 2026-06-12 — Fix: Service Worker Cache (v60→v61) + ai-provider unhealthy (durch opencode)

- **Service Worker:** `service-worker.js` cache auf v61 gebumpt, da die alte v60 die `index.html` mit dem Import-Fix cached hatte → Browser zeigte alte Version ohne API-Call.
- **ai-provider:** `OLLAMA_URLS` enthielt toten Endpoint `http://172.17.0.1:11434` → health-check hing → Provider als "unhealthy" markiert. Fix: nur noch `http://172.17.0.1:11435` (aktiver Ollama-Port). Container neugebaut mit korrigierten Env-Vars.

### 2026-06-12 — Browser-Use lokal aufgesetzt (MCP-Tool) (durch opencode)

**Problem:** `browser-use-mcp.py` lief via SSH auf Oracle VM, wo Ollama nur CPU hat (75s+ pro LLM-Call) → MCP-Timeout (30s).

**Fix:**
- Lokales venv (`/tmp/browser-use-env`) mit Playwright + browser-use installiert
- `browser-use-mcp.py` rewritten: läuft jetzt lokal mit GPU-Playwright (kein Ollama nötig für page-titles/content)
- Fallback: wenn lokal fehlschlägt → SSH mit opencode free über ai-provider
- Config in `~/.config/opencode/opencode.jsonc` aktualisiert

**Verifikation:** Seite geladen, Title + Buttons extrahiert in <3s (GPU).
**Nicht committed** — betrifft nur lokale MCP-Config + venv.

### 2026-06-12 — ÜBERGABE an opencode: technische Fehlbewertungen neu bewerten + Ollama-Fallback (Plan fertig, NICHT implementiert)

**Auftrag (User):** Verworfene JobMatches, deren KI-Begründung einen technischen Fehler zeigt ("Tunnel offline" / "ungültiges JSON von Provider"), sollen automatisch neu bewertet werden. Erweiterung: wenn das Free-Modell versagt, auf ein lokales **Ollama-Modell** zurückfallen.

**Was diese Session (Claude Code) fertig hat:**
- **Prod-Analyse** (Oracle VM, s.u.): 9 dismissed Matches mit `match_reasoning = "Bewertung fehlgeschlagen (ungültiges JSON von Provider)."`, Score 0, alle User `harald`. Ursache: Free-Modell `opencode/deepseek-v4-flash-free` liefert HTTP 200 + Prosa statt JSON; Backup-Provider war **dasselbe** Free-Modell → effektiv kein Fallback.
- **Spec** committed `765dec9` → `docs/superpowers/specs/2026-06-12-technical-failure-reeval-design.md`
- **Plan** committed `def16f1` → `docs/superpowers/plans/2026-06-12-technical-failure-reeval.md` (9 Tasks, TDD, vollständiger Code in jedem Step — opencode kann Task-für-Task abarbeiten).
- **Manuelle Prod-Daten-Änderung bereits gemacht:** 8 der 9 Matches auf `status='new'` zurückgesetzt (Score/Reasoning/notified geleert). IDs: `2451,2453,2473,2502,2554,2721,3057,3060`. Backup-JSON auf der VM: `/tmp/match_reeval_backup_20260612_041847.json`. Der 9. (Match `3053`) hat echtes `feedback_reasons=["wrong_seniority"]` → bewusst NICHT angefasst. **Diese 8 brauchen `eval_attempts=1`** (Plan Task 9 Step 4), sonst greift der neue Retry-Zweig sie nicht (prefilter < 50, Reasoning schon geleert).

**Was lokal NICHT committed / offen ist:** Nichts uncommitted im Tree (nur Spec+Plan, beide committed). **Code ist noch NICHT implementiert** — opencode startet bei Plan-Task 1.

**Wo genau weitermachen:** Plan Task 1 → Task 9 der Reihe nach. Branch `claude/hungry-euclid-56f7fd` (Worktree). NICHT zu `master` gemergt, NICHT deployed.

**⚠ Routing-Hinweis (§2/§3.2):** Der Kern liegt in `services/job_matching/claude_utils.py` = Claude-Code-Care-Gebiet (Anthropic/Cost-Tracking). opencode: `cost_tracker.record_call(...)`-Logik im Erfolgsfall **exakt** erhalten, **keinen** `anthropic.Anthropic(...)` direkt instanziieren (§3.2), AI-Calls nur über `ai_provider_client`. Bei Unsicherheit den Care-Pfad zurück an Claude Code geben.

**⚠ Infrastruktur-Korrektur:** Prod läuft auf der **Oracle VM**, nicht IONOS. Zugang: `ssh oracle-vm` (User `opc`), Container via **docker** (nicht podman). DB im Container `bewerbungen-app`: `/app/data/bewerbungstracker.db` (WAL, `busy_timeout` nutzen). Cron-Container `bewerbungen-cron` hat `JOB_CRON_TOKEN`+`APP_INTERNAL_URL` für manuelle Stage-Trigger. (Memory/AGENTS referenzieren noch IONOS — veraltet für dieses Deployment.)

**⚠ Provider-Status zum Handoff-Zeitpunkt:** Ollama-Tunnel **down** (`404 … http://172.17.0.1:11435/api/chat`), `opencode` + `claude` gesund. Der Smoke-Test (Plan Task 9 Step 5) braucht einen gesunden Provider — Ollama-Fallback erst sinnvoll testbar, wenn der Tunnel wieder steht.

**Verifikation vor Deploy:** `pytest tests/services/ tests/api/` grün; Alembic-Migration `c1d2e3f4a5b6` (down_revision `b0c1d2e3f4a5` = aktueller HEAD). Env-Defaults: `MATCH_FALLBACK_ENABLED=true`, `MATCH_OLLAMA_FALLBACK_MODEL=gemma4:12b`, `MATCH_MAX_EVAL_ATTEMPTS=5`.

### 2026-06-12 — Implementierung technische Fehlbewertung-Neubewertung + Ollama-Fallback (durch opencode)

**Tasks 1–8 vollständig implementiert (Plan Tasks 1–8), Task 9 (Deploy) noch ausstehend.**

**Commits** (7, auf Branch `claude/hungry-euclid-56f7fd`):
1. `7f193bb` — feat: JobMatch.eval_attempts Spalte für technische Retry-Logik
2. `e9bef20` — feat: MatchResult.failed unterscheidet technischen Fehler von echtem Score 0
3. `0c6de8f` — feat: Backoff-Kurve + Inhalts-Fehler-Erkennung + Match-Fallback-Konstanten
4. `0ecbb63` — feat: Ollama-Fallback-Kette + technische Fehlerklassifizierung im Match-Pfad
5. `8f2ea98` — feat: lokaler Match-Pfad schreibt keinen Fake-Score 0 mehr
6. `415f4eb` — feat: Retry-Zweig zieht technische Fehlschläge unabhängig vom prefilter-Gate
7. `41dab40` — feat: Einmal-Cleanup-Script für technische Fehlbewertungen im Altbestand

**Was implementiert wurde:**
- **Alembic-Migration** `c1d2e3f4a5b6` → `job_matches.eval_attempts` (Integer, default 0)
- **MatchResult.failed** Flag in `claude_matcher.py` — unterscheidet technischen Fehler von echtem Score 0
- **4 Env-Vars/Konstanten** in `claude_utils.py`: `MATCH_MAX_EVAL_ATTEMPTS=5`, `MATCH_FALLBACK_ENABLED=true`, `MATCH_OLLAMA_FALLBACK_MODEL=gemma4:12b`, `PERMANENT_FAIL_REASONING`
- **Backoff-Helper** `_retry_backoff_hours` (1,2,4,8,12h gekappt)
- **Content-Failure-Erkennung** `_result_is_content_failure` (failed-Flag + Reasoning-Heuristik)
- **Ollama-Fallback-Kette** in `_run_match_via_service`: Service-seitiger Fallback + eigener Ollama-Call bei Prosa
- **Content-Failure-Handling** in beiden Pfaden (Service + Local): kein Fake-Score 0, eval_attempts++ bei Prosa, PERMANENT_FAIL_REASONING ab 5. Versuch
- **`_run_claude_match_for` Guard** bei `eval_attempts >= 5`
- **Retry-Zweig** in `cron_claude_match.py`: zieht technische Fehlschläge (`eval_attempts 1–4`) unabhängig vom prefilter-Gate, mit Backoff per `updated_at`
- **Einmal-Cleanup-Script** `scripts/reeval_technical_failures.py` (Dry-run Default, `--apply` mit JSON-Backup)
- **14 neue Tests** (12 in `test_match_eval_retry.py`, 2 in `test_reeval_script.py`)

**Noch zu tun (Task 9 — Deploy + Daten-Reconciliation, siehe Plan für Details):**
1. Branch zu `master` mergen
2. Migration auf Oracle VM anwenden: `docker exec bewerbungen-app alembic upgrade head`
3. Spalte verifizieren
4. Cleanup-Script Dry-run + Apply: `python3 scripts/reeval_technical_failures.py --apply`
5. 8 bereits zurückgesetzte Matches `eval_attempts=1` setzen (IDs: 2451,2453,2473,2502,2554,2721,3057,3060)
6. Smoke via cron-Trigger: `docker exec bewerbungen-cron curl -X POST ...`

**Verifikation:** `pytest tests/services/test_match_eval_retry.py tests/services/test_reeval_script.py` → 14/14 passed. `pytest tests/services/ tests/api/test_jobs_cron.py tests/api/test_jobs_user.py` → 363 passed (7 failures in test_pattern_learner.py sind pre-existing AI-Key-abhängige Tests).

**⚠ MagicMock-Kompatibilität:** `_result_is_content_failure` prüft `isinstance(failed, bool)` — verhindert False Positives bei Tests die `MagicMock` statt `MatchResult` verwenden (Hotfix in diesem Commit).

### 2026-06-12 — opencode als System-Provider + Free-Tier + Browser-Use MCP + ai-provider Fixes (durch opencode)

**Browser-Use MCP rewritten:**
- Alte Agent-Variante (Ollama + browser-use, zu langsam, 75s Timeout) ersetzt durch **8 deterministische Tools** (navigate/click/fill/select/extract/screenshot/html/close)
- Stateful Session (ein Event-Loop über gesamte MCP-Lifetime)
- Kein LLM nötig – schnelle Playwright-Operationen (<3s pro Schritt)
- `opencode.jsonc` zeigt auf `/Library/WebServer/Documents/wolfinisoftware/scripts/browser-use-mcp.py`

**ai-provider-service (Hotfixes per SSH auf Oracle VM):**
1. **`Config`-Import fehlte** in `providers_api.py:42` → NameError → `/providers` gab 500 → alle Provider "nicht verfügbar"
2. **`opencode` war `system: False`** → Model-Endpoint blockierte (400 "nicht konfiguriert") für User ohne eigene opencode-Konfig, obwohl globaler `OPENCODE_API_KEY` existiert
3. **`opencode` in PROVIDER_REGISTRY** → `system: True`, `requires: []`, `optional: ['api_key','api_endpoint']`
4. **`_load_config` in dispatcher.py** → opencode-Check VOR system-Branch (sonst totes Code wegen system:True)
5. **`Config`-Import fehlte** in dispatcher.py → `name 'Config' is not defined` bei Chat-Calls
6. **`free_models` zum API-Response** hinzugefügt (statt Suffix-Raten im Frontend)

**Bewerbungstracker Backend Fixes (`api/providers.py`):**
1. **`allowed` fehlte im list_providers-Response** → Frontend filtert seit v62 mit `p.configured && p.allowed`, `allowed` war `undefined` → alle Provider rausgefiltert
2. **`free_models` fehlte im models-Proxy** → App-Proxy gibt jetzt `free_models` aus ai-provider-Response durch
3. **opencode-Prüfung** beim Settings-Save: `provider == 'opencode'` überspringt Config-Check (system provider mit Free-Tier)

**Frontend (`index.html`):**
1. Provider-Filter überall: `p.configured && p.allowed` (Backup, Override, Comparison-Modal)
2. `free_models` aus API-Response statt `endsWith('-free')`-Suffix
3. Paid-Modelle ausgeblendet wenn kein eigener opencode API-Key
4. Konfig-Formular: API-Key optional (Free-Modus ohne Key), Hinweise für Free/Paid
5. Service Worker v61→v62

**Wichtig bei Container-Neustart der Oracle VM:**
- ai-provider-service Änderungen sind per `sed`/`docker cp` im laufenden Container gemacht – **überleben keinen Image-Neubau**. Für dauerhaften Fix müssen `providers_api.py`, `dispatcher.py`, `providers/__init__.py`, `providers/opencode.py` und `health_tracker.py` im ai-provider-service Repo committed und Image neugebaut werden.
- Bewerbungstracker Änderungen sind committed und gepusht (s.u.).

**Nächste Schritte:**
- ai-provider-service Image neubauen mit den 6 Hotfixes
- `setup-oracle-vm.sh` ggf. aktualisieren

### 2026-06-12 — Review-Fixes der opencode-Session + ai-provider-Hotfixes persistiert (durch Claude Code)

**Review der opencode-Commits (a040252 u.a.) — 2 echte Probleme gefixt, Commit `582b765`:**
- `services/ai_provider_client.py`: neue öffentliche `get_models_raw()` (volles Dict inkl. `free_models`). `api/providers.py` griff vorher mit `client._get(...)` direkt auf den privaten HTTP-Helper zu (§3.1-Bruch) → jetzt `get_models_raw()`. `get_models()` unverändert.
- `index.html`: `_opencodeUserConfigured`-Cache nach erfolgreichem Speichern einer opencode-Config invalidiert — sonst blieben Paid-Modelle bis Reload versteckt.
- `service-worker.js`: v62→v63 (Frontend-Änderung → SW-Cache-Bump).
- 2 neue Tests in `tests/services/test_ai_provider_client.py`. `pytest tests/api tests/services` → 546 passed (7 pre-existing test_pattern_learner-Failures, lokal fehlendes `jsonschema`).
- Branch `claude/naughty-turing-5e5603`, NICHT zu master gemergt, NICHT deployed.

**ai-provider-service SSH-Hotfixes persistiert → [PR #21](https://github.com/haraldweiss/ai-provider-service/pull/21):**
- Vollständiger `.py`-Abgleich Container↔`origin/main`: nur 3 Dateien differierten (`api/providers_api.py`, `dispatcher.py`, `providers/__init__.py`); `config.py`/`opencode.py`/`health_tracker.py` auf main bereits korrekt/identisch. Der Handoff oben listete 5 Dateien — `config.py` war schon committed, daher hier präziser.
- **Kern-Bug auf main:** `Config.OPENCODE_API_KEY` wurde referenziert **ohne** `from config import Config` → NameError auf jedem opencode-Pfad. Plus opencode noch `system: False`.
- Fix übernimmt die produktiv laufende Container-Version 1:1 + Test auf neuen System-Provider-Vertrag aktualisiert. `pytest tests/` → 205 passed.
- **⚠ Image NICHT vor Merge neubauen** — `main` hat den Fix erst nach Merge; ein Rebuild aus aktuellem `main` würde Prod regredieren (Container läuft nur via SSH-Hotfix). Reihenfolge: **PR #21 mergen → dann Image neubauen.**

<!-- Example:
### 2026-05-27 — services/ extraction landed
- 924 lines out of api/, 797 into services/
- claude_utils.py and email_import_utils.py created
- Test mock paths updated in tests/api/test_jobs_cron.py and test_jobs_user.py
- NOT deployed to IONOS — needs manual deploy via DEPLOYMENT_IONOS.md
-->

### 2026-06-13 — Fix: Worker fehlte `DATABASE_URL` → Job-/Email-Import stumm `queued` (durch Claude Code)

**Symptom:** Indeed/IMAP-Job-Import in den Einstellungen nahm den Klick an (`POST /api/jobs/sources/<id>/import-from-email` → 202), aber der Task wurde NIE verarbeitet — `task_queue.status='queued'` für immer (`started_at=NULL`). Rückfall der Failure-Klasse vom 2026-06-12 Volume-Split (oben), diesmal via Env statt Volume.

**Root Cause:** `start_worker()` in `deploy/container/setup-oracle-vm.sh` mountete — anders als `start_app()` — KEINE `.env`, sondern reichte nur `-e ENCRYPTION_KEY` durch. → Worker ohne `DATABASE_URL` → Fallback auf relativen Default `sqlite:///bewerbungstracker.db` (= `/app/bewerbungstracker.db`, leere DB) statt `/app/data/bewerbungstracker.db`. Die API enqueued in die echte DB, der Worker pollte die leere → `pick_next_task()` lieferte immer `None`. Regression beim Container-Recreate am 2026-06-12. Diagnose: im Worker-App-Context lieferte `SELECT … WHERE status='queued'` 0 Zeilen vs. 3 in der echten DB; Worker-URI war `sqlite:///bewerbungstracker.db`.

**Fix — [PR #29](https://github.com/haraldweiss/Bewerbungstracker/pull/29) gemerged → master `d4c2890`:**
- `setup-oracle-vm.sh` `start_worker()`: mountet jetzt dieselbe `.env` wie die App (erbt `DATABASE_URL`+`ENCRYPTION_KEY`), fragiles manuelles ENCRYPTION_KEY-grep entfernt. Siehe neue Hard Rule §3.5.
- `database.py:_set_sqlite_pragmas`: `busy_timeout=10000` jetzt VOR `journal_mode=WAL` — sonst failt die WAL-Pragma sofort mit „database is locked" bei Multi-Writer-Contention (das crash-loopte den Worker-Subprozess `worker.py:139 create_app→create_all` am 06-12 beim Start).

**Deploy-Status: ERLEDIGT — running == committed (2026-06-13).**
- Zwischenstand (historisch): der `.env`-Fix lief zuerst als Incident-Recreate via ad-hoc `docker run` live (die 2 hängenden `email_import`-Tasks liefen sofort auf `done`), während der Pragma-Fix noch im alten Image `35e4215` fehlte.
- **Abschluss:** Image aus master `0f7b22b` neu gebaut + alle 5 Container über `setup-oracle-vm.sh rebuild` neu erstellt → laufend == committed, Worker wieder über das Skript (nicht mehr der manuelle Recreate). Verifiziert: alle 5 auf `localhost/bewerbungen:0f7b22b`, Worker-`DATABASE_URL=sqlite:////app/data/bewerbungstracker.db`, **0 Lock-Crashes** beim Start (Pragma-Härtung greift), App `/` 200, public https 200, `test_noop`-Task → `done`.

**Build-Mechanik (oracle-vm hat KEINEN dauerhaften Checkout):** `git archive <sha> | ssh oracle-vm 'tar -x -C /tmp/bwt-build'` → `cd /tmp/bwt-build && ./deploy/container/build.sh <sha>` (expliziter Tag-Arg, da Archive kein `.git` hat) → `IMAGE_TAG=<sha> deploy/container/setup-oracle-vm.sh rebuild`. **Rollback:** altes Image `35e4215` bleibt → `IMAGE_TAG=35e4215 setup-oracle-vm.sh rebuild`.

### 2026-06-13 — Add: Original-Stellenlink beim Übernehmen (Tracker-Auflösung) + Backfill (durch Claude Code)

**Problem:** „📥 Übernehmen" (`POST /matches/<id>/import`) kopierte `raw_job.url` 1:1 in `Application.link`. Bei E-Mail-Quellen ist das ein Klick-Tracking-Redirect (StepStone `click.stepstone.de/f/a/…`, LinkedIn `comm/jobs/view/…`, Indeed `cts.indeed.com/…`), nicht der echte Stellenlink.

**Lösung (PRs [#32](https://github.com/haraldweiss/Bewerbungstracker/pull/32) + [#33](https://github.com/haraldweiss/Bewerbungstracker/pull/33), gemerged → master `228a33e`):**
- Neues Modul `services/job_sources/url_resolver.py` → `resolve_original_url(url)` (best-effort, 10 Unit-Tests):
  - **LinkedIn**: `comm/jobs/view/<id>` → kanonisch `linkedin.com/jobs/view/<id>/` (reiner String, kein Netz).
  - **StepStone/Indeed**: Redirect folgen — **HEAD, dann GET mit Browser-UA** (StepStone-SendGrid timeoutet auf HEAD), nur Final-URL auf erwarteter Domain (SSRF-Guard, analog `email_jobs._resolve_indeed_tracker`).
  - **Generisch**: nur Tracking-Params (utm_*, trackingId) strippen, kein Netz.
  - Fehler / fremde Domain → Eingabe-Link bleibt (nie schlechter als der Tracker).
- `import_match` löst vor `Application.link` + „Original-Link"-Notiz auf.
- `scripts/backfill_application_links.py` zieht Bestand nach (`--check`, `--limit`, `--sleep`).

**Grenze StepStone:** Der öffentliche Posting-Link ist aus dem E-Mail-Tracker NICHT rekonstruierbar — die Kette endet bei einem personalisierten `www.stepstone.de/v2/magiclink/exchange?magicLink=<JWT>` (kann ablaufen). Das ist trotzdem besser als der opake `click.`-Tracker (echte Domain, browser-klickbar).

**Deployed:** Image `228a33e`, alle 5 Container neu erstellt, App/public 200, Resolver im Container verifiziert. **Backfill gelaufen:** 25 LinkedIn (→ saubere `jobs/view`) + 9 StepStone (→ Magic-Link) = 34 Bewerbungen bereinigt, 0 `click.`/`comm`-Tracker übrig.

### 2026-06-22 — 503 beim Match-Scoring gefixt + Ollama-Modell-Umstellung + Bulk-Scoring angestoßen (durch pi/Claude Code)

**Problem:** Klick auf "🤖 Bewerten lassen" (`POST /api/jobs/matches/{id}/score`) gab 503 zurück. Root Cause (via SSH auf Oracle VM, Docker-Logs + Traceback-Analyse):
- User-Konfiguration nutzte `opencode` / `opencode-deepseek-v4-flash-free`
- DeepSeek-Free lieferte unparsbares JSON zurück → Summarize-Retry → 2 AI-Provider-Calls pro Match
- Gesamtzeit > 60s → Gunicorn-Worker-Timeout → Worker stirbt → Apache 503
- ai-provider-service hatte ebenfalls Worker-Timeouts (120s) mit qwen3.6 (23 GB, zu langsam)

**Fix (Runtime-Konfig, kein Code-Commit):**
- **Modell umgestellt:** User `harald.weiss@wolfinisoftware.de` → `ai_provider=ollama`, `ai_model=mistral-nemo:12b-instruct-2407-q5_K_M` (vorher: `opencode`/`opencode-deepseek-v4-flash-free`)
- **Gunicorn-Timeout erhöht:** `GUNICORN_TIMEOUT=180` in `/etc/bewerbungen/bewerbungen.env` (vorher: default 60s)
- **Worker neugestartet** (`docker restart bewerbungen-worker`)
- **Bulk-Scoring** für 64 neue Matches angestoßen (Task-ID `3d5ea8a5`, läuft im Hintergrund)

**Verifikation:** Test-Score Match #592 → HTTP 200, `match_score: 87.0`, `provider_used: ollama`, `model_used: mistral-nemo:12b-instruct-2407-q5_K_M`.

**WordPress wolfinisoftware.de (gleiche Oracle VM):**
- **Kritisch:** File-Ownership `root:root` → `apache:apache` + `FS_METHOD=direct` → Auto-Updates repariert
- **Empfohlen:** System-Cron eingerichtet (`*/15 * * * * curl -s https://wolfinisoftware.de/wp-cron.php`) → verspätete Cron-Events behoben
- **Empfohlen:** Stale WP-Super-Cache-Config aus `wp-config.php` entfernt (Plugin nicht mehr installiert, Redis-Cache läuft als Object Cache)

### 2026-07-04 — Fix: IMAP proxy server missing do_GET method

**Problem:** Admin dashboard IMAP-Proxy status section showed HTTP Error 501: Unsupported method ('GET')

**Root Cause:** The IMAP proxy server in imap_proxy.py was missing the do_GET method in the ProxyHandler class. The admin dashboard makes GET requests to check proxy status, but the server only supported POST (for IMAP/POP3 operations) and OPTIONS (for CORS preflight).

**Fix:** Added do_GET method to ProxyHandler class that includes:
- Same IP validation as do_POST method for security
- /ping endpoint for health checks (same as existing POST handling)
- Status endpoint providing proxy information and available endpoints
- CORS headers support for frontend requests
- Proper error handling for invalid paths/ips

**Impact:**
- Admin dashboard now shows IMAP-Proxy as HEALTHY instead of erroring
- Proxy status endpoint returns detailed information including version and supported endpoints
- Health monitoring via /ping endpoint operational
- All existing IMAP/POP3 functionality preserved via POST requests

**Verification:** Admin dashboard IMAP-Proxy status now shows healthy status instead of 501 error.

---
