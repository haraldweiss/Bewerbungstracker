# Email-Jobs-Import für LinkedIn & Xing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** LinkedIn- und Xing-Job-Empfehlungs-Mails parallel zum bestehenden Indeed-Email-Import als Job-Vorschläge in den Tracker bringen.

**Architecture:** Zwei Phasen. Phase 1 mergt den bestehenden Indeed-Email-Feature-Branch (`claude/thirsty-elion-684a7f`) in master — VPS läuft den Code schon via scp-Deploy (bit-für-bit identisch). Phase 2 refactoriert `indeed_email.py` zu generischem `email_jobs.py` mit `PlatformProfile`-Dataclass und drei Profilen (Indeed/LinkedIn/Xing) — eine Adapter-Klasse, drei Datenkonfigurationen.

**Tech Stack:** Python 3.12 + Flask + SQLAlchemy, Vanilla JS Frontend, IMAP4_SSL (imaplib), ai-provider-service (Ollama + Claude Fallback), pytest.

**Spec:** [2026-05-19-email-jobs-linkedin-xing-design.md](../specs/2026-05-19-email-jobs-linkedin-xing-design.md)

---

## Phase 1 — Indeed-Email-Branch in master mergen

### Task 1: Vor-Merge-Backup & Branch vorbereiten

**Files:**
- Lokal: working-tree clean halten
- VPS: DB-Backup `bewerbungstracker.db.bak.pre-indeed-email-merge`

- [ ] **Step 1: VPS-DB-Backup erstellen**

```bash
ssh ionos-vps 'cd /var/www/bewerbungen && cp bewerbungstracker.db bewerbungstracker.db.bak.pre-indeed-email-merge-2026-05-19 && ls -la bewerbungstracker.db.bak.pre-indeed-email-merge-2026-05-19'
```

Expected: Datei existiert mit aktuellem Zeitstempel.

- [ ] **Step 2: Lokal frischer Merge-Branch von master**

```bash
git checkout master
git pull origin master
git checkout -b merge/indeed-email-to-master
```

Expected: Branch erstellt, working-tree clean.

- [ ] **Step 3: Branch-Diff-Größe bestätigen**

```bash
git diff --stat master..claude/thirsty-elion-684a7f | tail -3
```

Expected: ~3940 LOC über 14 Files (siehe Spec Phase 1).

### Task 2: Merge mit Konfliktauflösung

**Files:**
- Modify (Konflikte erwartet): `index.html`, `api/jobs_user.py`, `api/profile.py`, `service-worker.js`, `imap_proxy.py`

**Konfliktauflösungs-Regel:** beide Seiten **vereinen**, niemals eine wählen.

- [ ] **Step 1: Merge starten (no-ff)**

```bash
git merge --no-ff claude/thirsty-elion-684a7f -m "merge(jobs): Indeed-Email-Import Feature-Branch in master

Bringt indeed_email-Adapter, Mail-Connector-UI, IMAP-Proxy-Fixes,
Apps-Script-Backend-Proxy in die Mainline. Code lief seit 2026-05-17
nur via scp-Deploy auf VPS — diese Merge konsolidiert."
```

Expected: Konfliktmeldungen für 5 Files, Merge pausiert.

- [ ] **Step 2: Konflikt in `service-worker.js` lösen**

Beide Seiten haben `CACHE_NAME` hochgezählt. Den höheren Wert wählen.

```bash
git status | grep "both modified"
cat service-worker.js | head -5
# Datei editieren: CACHE_NAME auf das höhere Increment der beiden Seiten setzen
git add service-worker.js
```

- [ ] **Step 3: Konflikt in `imap_proxy.py` lösen**

Master-Seite hat UID-Fix (commit c0e4e9e), Branch-Seite hat folder-quoting + X-GM-RAW. **Beide brauchen wir**.

Pro Konfliktblock:
- Master-Code (UID-Parsing-Fix) drin lassen
- Branch-Code (folder-quoting/X-GM-RAW) zusätzlich einfügen
- Markers `<<<<<<<`, `=======`, `>>>>>>>` entfernen

```bash
git diff imap_proxy.py | head -50
# Konflikte manuell auflösen, beide Seiten behalten
git add imap_proxy.py
```

- [ ] **Step 4: Konflikt in `api/profile.py` lösen**

Master hat SMTP-Encrypted-Credential-Fix (commits 2965be1, 0da7be5). Branch hat IMAP-Mini-API. Beide vereinen.

```bash
git diff api/profile.py | head -80
git add api/profile.py
```

- [ ] **Step 5: Konflikt in `api/jobs_user.py` lösen**

Master hat Origin-Filter (ea08cbf), Unbewertet-Filter (1f027fe), Filter "Nur mit Grund" (202ac0a), Grund-Anzeige (764d906). Branch hat die `import-from-email`-Endpoints. Vollständig vereinen.

```bash
git diff api/jobs_user.py | head -100
git add api/jobs_user.py
```

- [ ] **Step 6: Konflikt in `index.html` lösen**

Größter Konflikt. Master hat SMTP-Status-Badges, Push-Notification-Fix, Settings-Profile-Load-Fix. Branch hat Mail-Connector-UI, Folder-Picker, Indeed-Import-UI mit Approval-Dialog. Vereinen.

```bash
git diff index.html | wc -l
git add index.html
```

- [ ] **Step 7: Merge abschließen**

```bash
git status  # alles als "all conflicts fixed"
git commit --no-edit  # Merge-Message aus Step 1
git log --oneline -5
```

Expected: Merge-Commit ist Head, mit 30 Commits History dahinter.

### Task 3: Test-Verifikation & Smoke-Test

**Files:** keine Änderungen — nur Lesen.

- [ ] **Step 1: pytest komplett laufen lassen**

```bash
cd /Library/WebServer/Documents/Bewerbungstracker/.claude/worktrees/confident-mendeleev-17fcde
python -m pytest tests/ -x --tb=short 2>&1 | tail -30
```

Expected: alle Tests grün (~220 Bestand + 36 Indeed-Branch-Tests). Bei Fail: Output lesen, Konflikt-Auflösung war wahrscheinlich nicht vollständig.

- [ ] **Step 2: Flask Smoke-Test lokal**

```bash
# Flask starten (Hintergrund)
python -c "from app import app; print('OK' if app else 'FAIL')"
```

Expected: `OK` — App-Import läuft ohne Exception.

- [ ] **Step 3: Smoke-Test der neuen Endpoints (Route-Registration)**

```bash
python -c "from app import app; print([r.rule for r in app.url_map.iter_rules() if 'email' in r.rule])"
```

Expected: Liste enthält `/api/jobs/sources/<int:source_id>/import-from-email` und `/api/jobs/sources/<int:source_id>/import-from-email/approve`.

### Task 4: Push, Deploy, VPS-Cleanup

**Files:**
- VPS Working-Tree: bisher `M`-modified Files werden nach `git pull` clean

- [ ] **Step 1: Branch in origin/master mergen**

```bash
git checkout master
git merge --ff-only merge/indeed-email-to-master
git push origin master
```

Expected: Push grün, master ist auf neuem Merge-Commit.

- [ ] **Step 2: VPS-Pull vorbereiten — modifizierte Files entfernen**

Auf VPS sind die Files identisch zum Branch — aber als modified/untracked markiert. Sie blockieren `git pull`. Lösung: alle 9 modifizierten Files auf VPS auf HEAD zurücksetzen (sie kommen ja inhaltsgleich via Merge zurück), und `indeed_email.py` löschen (wird via Merge wiederhergestellt).

```bash
ssh ionos-vps 'cd /var/www/bewerbungen && git stash push -m "pre-indeed-merge-pull-2026-05-19" -- api/jobs_cron.py api/jobs_user.py api/profile.py email_service.py imap_proxy.py index.html service-worker.js services/ai_provider_client.py services/job_sources/__init__.py && rm -f services/job_sources/indeed_email.py && git status --short | head -10'
```

Expected: 9 Files gestasht, `indeed_email.py` gelöscht, working-tree clean (oder nur untracked Reste die nichts mit dem Merge zu tun haben).

- [ ] **Step 3: VPS git pull**

```bash
ssh ionos-vps 'cd /var/www/bewerbungen && git pull origin master 2>&1 | tail -20'
```

Expected: Pull bringt Merge-Commit + 30 darunter, Files werden geupdatet.

- [ ] **Step 4: Sanity-Check auf VPS**

```bash
ssh ionos-vps 'cd /var/www/bewerbungen && git rev-parse HEAD && git status --short | head -5 && diff <(cat services/job_sources/indeed_email.py | md5sum) <(echo "<expected hash>") 2>/dev/null || md5sum services/job_sources/indeed_email.py'
```

Expected: HEAD = master-Head-SHA, working-tree clean (nur Reliquien-Untracked-Files), `indeed_email.py` ist da.

- [ ] **Step 5: Stash auflösen (wenn 0 Diff)**

```bash
ssh ionos-vps 'cd /var/www/bewerbungen && git stash list | head -3'
# Wenn der stash existiert und Inhalt = Branch (was wir verifiziert haben), dann droppen:
ssh ionos-vps 'cd /var/www/bewerbungen && git stash drop stash@{0}'
```

Expected: Stash dropped — Inhalt war ja redundant.

- [ ] **Step 6: Gunicorn/Service-Restart**

```bash
ssh ionos-vps 'systemctl restart bewerbungstracker || systemctl restart gunicorn-bewerbungen || service bewerbungen restart 2>&1' 
```

Expected: Service restartet, kein Fehler.

- [ ] **Step 7: Production-Smoke-Test**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://bewerbungstracker.wolfinisoftware.de/api/health || curl -s -o /dev/null -w "%{http_code}\n" https://bewerbungstracker.wolfinisoftware.de/
```

Expected: 200 oder 401 (200 für Public-Endpoints, 401 wenn Auth required).

### Task 5: Phase-1-Commit-Mark im Memory

**Files:**
- `/Users/haraldweiss/.claude/projects/-Library-WebServer-Documents-Bewerbungstracker/memory/project_indeed_email_import_live.md`

- [ ] **Step 1: Memory-Update — Git-Status klarstellen**

Den Block "⚠️ **Git-Status (2026-05-19 verifiziert)**" anpassen auf:
"✅ **Git-Status (2026-05-19 gemergt):** Branch `claude/thirsty-elion-684a7f` in master gemergt, VPS auf gleichem SHA. Working-tree clean."

```bash
# Edit-Tool auf project_indeed_email_import_live.md
```

---

## Phase 2 — Generischer Refactor + LinkedIn/Xing-Profile

### Task 6: TDD-Setup — Test-Skelett für PlatformProfile

**Files:**
- Create: `tests/services/test_email_jobs.py` (wird aus `test_indeed_email.py` umbenannt in Task 7 — hier nur die *neuen* Tests für PlatformProfile-Dataclass)

- [ ] **Step 1: Test für PlatformProfile-Dataclass-Konstruktion schreiben**

```python
# tests/services/test_email_jobs_profiles.py (neu)
"""Unit-Tests für PlatformProfile-Dataclass und PROFILES-Registry."""
import re
import pytest
from services.job_sources.email_jobs import PlatformProfile, PROFILES


def test_profile_indeed_exists():
    assert "indeed" in PROFILES
    p = PROFILES["indeed"]
    assert p.name == "indeed"
    assert p.source_label == "Indeed"
    assert p.from_filter.startswith("from:indeed")


def test_profile_linkedin_exists():
    assert "linkedin" in PROFILES
    p = PROFILES["linkedin"]
    assert p.name == "linkedin"
    assert p.source_label == "LinkedIn"
    assert "linkedin.com" in p.from_filter
    assert p.digest_threshold == 3


def test_profile_xing_exists():
    assert "xing" in PROFILES
    p = PROFILES["xing"]
    assert p.name == "xing"
    assert p.source_label == "XING"
    assert "xing.com" in p.from_filter


def test_profile_linkedin_url_pattern_matches_jobs_view():
    p = PROFILES["linkedin"]
    assert p.url_pattern.search("Schau dir https://www.linkedin.com/jobs/view/3812345678/ an")
    assert p.url_pattern.search("https://linkedin.com/comm/jobs/view/3812345678?refId=abc")


def test_profile_xing_url_pattern_matches_jobs():
    p = PROFILES["xing"]
    assert p.url_pattern.search("https://www.xing.com/jobs/python-dev-12345")
    assert p.url_pattern.search("https://xing.com/app/jobs/details/abc-123")


def test_profile_is_frozen():
    """Dataclass frozen=True — versehentliches Überschreiben unterbunden."""
    p = PROFILES["indeed"]
    with pytest.raises((AttributeError, TypeError)):
        p.name = "modified"
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen (ImportError)**

```bash
python -m pytest tests/services/test_email_jobs_profiles.py -v 2>&1 | tail -10
```

Expected: FAIL mit `ModuleNotFoundError: No module named 'services.job_sources.email_jobs'`.

- [ ] **Step 3: Commit**

```bash
git add tests/services/test_email_jobs_profiles.py
git commit -m "test(email-jobs): PlatformProfile-Dataclass + PROFILES-Registry-Tests (failing)"
```

### Task 7: Rename indeed_email.py → email_jobs.py + PlatformProfile-Skelett

**Files:**
- Rename: `services/job_sources/indeed_email.py` → `services/job_sources/email_jobs.py`
- Modify: `services/job_sources/email_jobs.py` (Dataclass + PROFILES["indeed"] hinzu)

- [ ] **Step 1: git mv durchführen**

```bash
git mv services/job_sources/indeed_email.py services/job_sources/email_jobs.py
```

Expected: Datei umbenannt, git erkennt es als rename (History bleibt).

- [ ] **Step 2: PlatformProfile-Dataclass + PROFILES["indeed"] am Anfang der Datei einfügen**

Direkt nach den bestehenden Imports und vor `_SUBJECT_PATTERNS` einfügen:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformProfile:
    """Plattform-spezifische Daten für den EmailJobsAdapter.

    Nur Daten, keine Logik. Profile werden in `PROFILES`-Dict registriert
    und vom Adapter via `EmailJobsAdapter(config, user, profile=...)`
    injected.
    """
    name: str
    source_label: str
    from_filter: str                  # X-GM-RAW Hinweis "from:linkedin"
    from_whitelist: tuple[str, ...]   # Domain-Regex für Plain-IMAP-Fallback
    url_pattern: re.Pattern
    subject_patterns: tuple[re.Pattern, ...]
    body_title_re: re.Pattern
    body_company_re: re.Pattern
    body_location_re: re.Pattern
    digest_threshold: int = 3
    ai_hint: str = ""
```

Dann unterhalb von `_BODY_LOCATION_RE` (das letzte bestehende Indeed-Modul-Regex) das `PROFILES`-Dict einfügen:

```python
PROFILES: dict[str, PlatformProfile] = {
    "indeed": PlatformProfile(
        name="indeed",
        source_label="Indeed",
        from_filter="from:indeed",
        from_whitelist=(
            r"@(?:[a-z0-9.-]+\.)?indeed\.(?:de|com|co\.uk|fr|it|es)$",
        ),
        url_pattern=_INDEED_URL_RE,
        subject_patterns=tuple(_SUBJECT_PATTERNS),
        body_title_re=_BODY_TITLE_RE,
        body_company_re=_BODY_COMPANY_RE,
        body_location_re=_BODY_LOCATION_RE,
        digest_threshold=3,
        ai_hint=(
            "Indeed-Jobempfehlung. Click-Tracker-URLs cts.indeed.com/v3 "
            "bleiben als external_id (kein Auto-Follow)."
        ),
    ),
}
```

- [ ] **Step 3: Test laufen lassen — `indeed` muss passen, `linkedin`/`xing` weiter fehlschlagen**

```bash
python -m pytest tests/services/test_email_jobs_profiles.py -v 2>&1 | tail -15
```

Expected: `test_profile_indeed_exists` PASSED, `test_profile_linkedin_exists` FAILED.

- [ ] **Step 4: Commit**

```bash
git add services/job_sources/email_jobs.py
git commit -m "refactor(email-jobs): rename indeed_email.py → email_jobs.py + PlatformProfile-Dataclass

Indeed wird ein Plattform-Profil von dreien. Logik unverändert,
nur Daten extrahiert in PROFILES['indeed']."
```

### Task 8: LinkedIn-Profil hinzu

**Files:**
- Modify: `services/job_sources/email_jobs.py:PROFILES`

- [ ] **Step 1: PROFILES["linkedin"] einfügen**

In `PROFILES`-Dict (nach `"indeed": ...`) einfügen:

```python
    "linkedin": PlatformProfile(
        name="linkedin",
        source_label="LinkedIn",
        from_filter="from:linkedin.com",
        from_whitelist=(
            r"@(?:[a-z0-9.-]+\.)?linkedin\.com$",
        ),
        url_pattern=re.compile(
            r"https?://(?:www\.)?linkedin\.com/(?:jobs/view|comm/jobs/view)/\d+[^\s)<>\"'\\]*",
            re.IGNORECASE,
        ),
        subject_patterns=(
            re.compile(
                r"(?:New job|Neue Stelle|Job alert)\s*:?\s*"
                r"(?P<title>.+?)\s+(?:at|bei|@)\s+(?P<company>.+?)"
                r"(?:\s*[-–|]\s*LinkedIn.*)?$",
                re.IGNORECASE,
            ),
        ),
        body_title_re=re.compile(
            r"(?:Position|Job\s*Title|Jobtitel|Stelle)\s*[:\-]\s*([^\n\r]+)",
            re.IGNORECASE,
        ),
        body_company_re=re.compile(
            r"(?:Company|Firma|Unternehmen|Employer)\s*[:\-]\s*([^\n\r]+)",
            re.IGNORECASE,
        ),
        body_location_re=re.compile(
            r"(?:Location|Standort|Ort|Place)\s*[:\-]\s*([^\n\r]+)",
            re.IGNORECASE,
        ),
        digest_threshold=3,
        ai_hint=(
            "LinkedIn-Jobempfehlungs-Digest. Jede Job-Card hat einen "
            "linkedin.com/jobs/view/<ID>-Link. "
            "Extrahiere {title, company, location, url} pro Job als JSON-Array."
        ),
    ),
```

- [ ] **Step 2: Tests grün**

```bash
python -m pytest tests/services/test_email_jobs_profiles.py::test_profile_linkedin_exists tests/services/test_email_jobs_profiles.py::test_profile_linkedin_url_pattern_matches_jobs_view -v
```

Expected: PASS für beide.

- [ ] **Step 3: Commit**

```bash
git add services/job_sources/email_jobs.py
git commit -m "feat(email-jobs): LinkedIn-Plattform-Profil"
```

### Task 9: Xing-Profil hinzu

**Files:**
- Modify: `services/job_sources/email_jobs.py:PROFILES`

- [ ] **Step 1: PROFILES["xing"] einfügen**

```python
    "xing": PlatformProfile(
        name="xing",
        source_label="XING",
        from_filter="from:xing.com",
        from_whitelist=(
            r"@(?:[a-z0-9.-]+\.)?xing\.com$",
        ),
        url_pattern=re.compile(
            r"https?://(?:www\.)?xing\.com/(?:jobs|app/jobs)/[^\s)<>\"'\\]+",
            re.IGNORECASE,
        ),
        subject_patterns=(
            re.compile(
                r"(?:Neue\s+(?:Stelle|Jobempfehlung)|New\s+job|Stellenangebot)"
                r"\s*:?\s*(?P<title>.+?)\s+(?:bei|at|@)\s+(?P<company>.+?)"
                r"(?:\s*[-–|]\s*XING.*)?$",
                re.IGNORECASE,
            ),
        ),
        body_title_re=re.compile(
            r"(?:Stelle|Position|Jobtitel|Job\s*Title)\s*[:\-]\s*([^\n\r]+)",
            re.IGNORECASE,
        ),
        body_company_re=re.compile(
            r"(?:Firma|Unternehmen|Company|Arbeitgeber|Employer)\s*[:\-]\s*([^\n\r]+)",
            re.IGNORECASE,
        ),
        body_location_re=re.compile(
            r"(?:Ort|Standort|Location|Place)\s*[:\-]\s*([^\n\r]+)",
            re.IGNORECASE,
        ),
        digest_threshold=3,
        ai_hint=(
            "XING-Jobempfehlungs-Digest (deutsch). Jede Job-Card hat einen "
            "xing.com/jobs/<slug>-Link. "
            "Extrahiere {title, company, location, url} pro Job als JSON-Array."
        ),
    ),
```

- [ ] **Step 2: Tests grün**

```bash
python -m pytest tests/services/test_email_jobs_profiles.py -v
```

Expected: alle 6 Tests PASS.

- [ ] **Step 3: Commit**

```bash
git add services/job_sources/email_jobs.py
git commit -m "feat(email-jobs): XING-Plattform-Profil"
```

### Task 10: EmailJobsAdapter — generische Adapter-Klasse

**Files:**
- Modify: `services/job_sources/email_jobs.py` (Klasse `IndeedEmailAdapter` umbenennen + parametrisieren)
- Create: `tests/services/test_email_jobs_adapter.py`

- [ ] **Step 1: Test für generischen Adapter mit profile-Parameter**

```python
# tests/services/test_email_jobs_adapter.py
"""Unit-Tests für EmailJobsAdapter mit verschiedenen Profilen."""
from unittest.mock import MagicMock
from services.job_sources.email_jobs import EmailJobsAdapter, PROFILES


def test_adapter_accepts_profile_indeed():
    adapter = EmailJobsAdapter(
        config={"folder": "INBOX", "lookback_days": 30},
        user=MagicMock(),
        platform_profile=PROFILES["indeed"],
    )
    assert adapter.profile.name == "indeed"


def test_adapter_accepts_profile_linkedin():
    adapter = EmailJobsAdapter(
        config={"folder": "INBOX", "lookback_days": 30},
        user=MagicMock(),
        platform_profile=PROFILES["linkedin"],
    )
    assert adapter.profile.name == "linkedin"


def test_adapter_parses_single_linkedin_job_subject():
    adapter = EmailJobsAdapter(
        config={}, user=MagicMock(), platform_profile=PROFILES["linkedin"],
    )
    email_dict = {
        "subject": "Neue Stelle: Senior Python Developer bei Acme GmbH",
        "from": "jobs-noreply@linkedin.com",
        "body": "Schau dir https://www.linkedin.com/jobs/view/3812345678/ an",
        "date": "2026-05-19T10:00:00",
        "message_id": "<abc@linkedin.com>",
    }
    jobs = adapter.parse_emails([email_dict])
    assert len(jobs) == 1
    assert jobs[0].title == "Senior Python Developer"
    assert jobs[0].company == "Acme GmbH"
    assert "linkedin.com/jobs/view/3812345678" in jobs[0].url


def test_adapter_digest_triggers_ai_fallback(monkeypatch):
    """≥3 LinkedIn-URLs im Body → sofort AI-Fallback (kein Subject-Regex)."""
    adapter = EmailJobsAdapter(
        config={}, user=MagicMock(), platform_profile=PROFILES["linkedin"],
    )
    ai_called = {"count": 0, "hint": None}

    def fake_ai(em):
        ai_called["count"] += 1
        ai_called["hint"] = adapter.profile.ai_hint
        return [
            type("FetchedJob", (), {
                "title": "A", "company": "X", "location": "DE",
                "url": "https://linkedin.com/jobs/view/1", "platform": "linkedin",
                "posted_at": None, "external_id": "linkedin:1", "raw": {}
            })()
        ]

    monkeypatch.setattr(adapter, "_ai_fallback_digest", fake_ai)
    email_dict = {
        "subject": "Jobs you may be interested in",
        "from": "jobs-noreply@linkedin.com",
        "body": (
            "1. https://linkedin.com/jobs/view/1 "
            "2. https://linkedin.com/jobs/view/2 "
            "3. https://linkedin.com/jobs/view/3"
        ),
        "date": "2026-05-19T10:00:00",
    }
    adapter.parse_emails([email_dict])
    assert ai_called["count"] == 1
    assert "LinkedIn" in ai_called["hint"]


def test_adapter_from_whitelist_blocks_wrong_domain():
    """Email mit xing.com From wird bei LinkedIn-Profil NICHT akzeptiert."""
    adapter = EmailJobsAdapter(
        config={}, user=MagicMock(), platform_profile=PROFILES["linkedin"],
    )
    email_dict = {
        "subject": "Neue Stelle bei Acme",
        "from": "jobs@xing.com",
        "body": "https://linkedin.com/jobs/view/3812345678/",
        "date": "2026-05-19T10:00:00",
    }
    jobs = adapter.parse_emails([email_dict])
    # Erwartung: From-Whitelist-Mismatch → Mail wird skipped
    assert jobs == []
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

```bash
python -m pytest tests/services/test_email_jobs_adapter.py -v 2>&1 | tail -15
```

Expected: 5 FAILs — `EmailJobsAdapter` existiert noch nicht oder akzeptiert kein `platform_profile`-kwarg.

- [ ] **Step 3: `IndeedEmailAdapter` → `EmailJobsAdapter` umbenennen + parametrisieren**

In `services/job_sources/email_jobs.py`:
- Klassen-Name: `IndeedEmailAdapter` → `EmailJobsAdapter`
- `__init__` Signatur: `__init__(self, config, user=None, platform_profile=None)`. Im Body: `self.profile = platform_profile or PROFILES["indeed"]` (Indeed als Default für Rückwärtskompatibilität).
- Im gesamten File alle Verwendungen von Modul-Level-Regex (`_SUBJECT_PATTERNS`, `_INDEED_URL_RE`, `_BODY_TITLE_RE`, `_BODY_COMPANY_RE`, `_BODY_LOCATION_RE`) durch `self.profile.subject_patterns`, `self.profile.url_pattern`, `self.profile.body_title_re`, etc. ersetzen.
- `from_whitelist`-Check vor dem Parsen einbauen (in `_parse_email`):
  ```python
  from_addr = em.get("from", "").lower()
  if not any(re.search(pat, from_addr) for pat in self.profile.from_whitelist):
      return None
  ```
- Multi-URL-Digest-Erkennung in `_parse_email`:
  ```python
  urls = set(self.profile.url_pattern.findall(em.get("body", "")))
  if len(urls) >= self.profile.digest_threshold:
      return self._ai_fallback_digest(em)
  ```
- `_ai_fallback` umbenennen zu `_ai_fallback_digest`, Prompt nutzt `self.profile.ai_hint`. Erwartet JSON-Array als Output, gibt Liste von FetchedJobs zurück (nicht nur ein Job).

- [ ] **Step 4: Tests grün**

```bash
python -m pytest tests/services/test_email_jobs_adapter.py -v
```

Expected: alle 5 PASS.

- [ ] **Step 5: Bestehende Indeed-Tests müssen weiter grün sein**

```bash
python -m pytest tests/services/test_indeed_email.py -v 2>&1 | tail -10
```

Expected: alle 19 Bestand-Tests PASS (Adapter mit Default-Profil verhält sich identisch wie früher).

- [ ] **Step 6: Commit**

```bash
git add services/job_sources/email_jobs.py tests/services/test_email_jobs_adapter.py
git commit -m "refactor(email-jobs): IndeedEmailAdapter → generischer EmailJobsAdapter

- platform_profile als Constructor-Parameter (Default PROFILES['indeed']
  für Rückwärtskompatibilität)
- From-Whitelist-Check pro Mail
- Multi-URL-Digest-Erkennung → _ai_fallback_digest mit JSON-Array-Output
- Modul-Level-Regex durch self.profile.* ersetzt"
```

### Task 11: Registry-Anpassung — linkedin_email / xing_email

**Files:**
- Modify: `services/job_sources/__init__.py`
- Create: `tests/services/test_email_jobs_registry.py`

- [ ] **Step 1: Test für Registry**

```python
# tests/services/test_email_jobs_registry.py
"""Tests für services.job_sources.__init__.get_adapter mit _email-Typen."""
from unittest.mock import MagicMock
from services.job_sources import get_adapter, _VALID_TYPES
from services.job_sources.email_jobs import EmailJobsAdapter, PROFILES


def test_valid_types_contains_all_email_variants():
    assert "indeed_email" in _VALID_TYPES
    assert "linkedin_email" in _VALID_TYPES
    assert "xing_email" in _VALID_TYPES


def test_get_adapter_indeed_email_returns_email_jobs_adapter():
    adapter = get_adapter(
        "indeed_email", config={"folder": "INBOX"}, user=MagicMock(),
    )
    assert isinstance(adapter, EmailJobsAdapter)
    assert adapter.profile is PROFILES["indeed"]


def test_get_adapter_linkedin_email_returns_email_jobs_adapter():
    adapter = get_adapter(
        "linkedin_email", config={"folder": "INBOX"}, user=MagicMock(),
    )
    assert isinstance(adapter, EmailJobsAdapter)
    assert adapter.profile is PROFILES["linkedin"]


def test_get_adapter_xing_email_returns_email_jobs_adapter():
    adapter = get_adapter(
        "xing_email", config={"folder": "INBOX"}, user=MagicMock(),
    )
    assert isinstance(adapter, EmailJobsAdapter)
    assert adapter.profile is PROFILES["xing"]
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

```bash
python -m pytest tests/services/test_email_jobs_registry.py -v 2>&1 | tail -10
```

Expected: FAIL — `linkedin_email`/`xing_email` nicht in `_VALID_TYPES`, oder Import-Fehler weil `IndeedEmailAdapter` nicht mehr existiert.

- [ ] **Step 3: `services/job_sources/__init__.py` anpassen**

- `_VALID_TYPES`-Set erweitern: `+ {"linkedin_email", "xing_email"}` (indeed_email bleibt drin).
- Import-Statement ändern: `from services.job_sources.indeed_email import IndeedEmailAdapter` → `from services.job_sources.email_jobs import EmailJobsAdapter, PROFILES`.
- In `get_adapter(source_type, config, **kwargs)`:
  ```python
  if source_type.endswith("_email"):
      platform = source_type.removesuffix("_email")
      if platform not in PROFILES:
          raise ValueError(f"Unknown email platform: {platform}")
      return EmailJobsAdapter(
          config=config,
          user=kwargs.get("user"),
          platform_profile=PROFILES[platform],
      )
  ```

- [ ] **Step 4: Registry-Tests grün**

```bash
python -m pytest tests/services/test_email_jobs_registry.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Indeed-API-Tests müssen weiter grün sein (Rückwärtskompatibilität)**

```bash
python -m pytest tests/api/test_indeed_email_import.py -v 2>&1 | tail -10
```

Expected: alle 17 Tests PASS — Endpoint-Verhalten identisch.

- [ ] **Step 6: Commit**

```bash
git add services/job_sources/__init__.py tests/services/test_email_jobs_registry.py
git commit -m "feat(email-jobs): Registry für linkedin_email/xing_email Source-Typen

get_adapter() mapped alle *_email-Typen auf EmailJobsAdapter mit
entsprechendem PlatformProfile. indeed_email weiter rückwärtskompatibel."
```

### Task 12: Cron-Endpoint iteriert über alle drei _email-Typen

**Files:**
- Modify: `api/jobs_cron.py` (Funktion `indeed_email_import_all` umbenennen + Filter erweitern)

- [ ] **Step 1: Test für Multi-Type-Cron**

In `tests/api/test_indeed_email_import.py` (oder neuer `tests/api/test_email_jobs_cron.py`) Test ergänzen:

```python
def test_cron_endpoint_iterates_all_three_email_types(client, db_session, monkeypatch):
    """Cron-Endpoint /api/jobs/indeed-email-import-all verarbeitet
    indeed_email, linkedin_email, xing_email gleichzeitig."""
    from models import User, JobSource
    user = User(email="u@x.de", password_hash="x")
    db_session.add(user); db_session.commit()
    db_session.add_all([
        JobSource(user_id=user.id, type="indeed_email",   name="Indeed",   config={}, enabled=True),
        JobSource(user_id=user.id, type="linkedin_email", name="LinkedIn", config={}, enabled=True),
        JobSource(user_id=user.id, type="xing_email",     name="Xing",     config={}, enabled=True),
    ])
    db_session.commit()

    seen_types = []
    def fake_adapter_fetch(self):
        seen_types.append(self.profile.name)
        return []
    monkeypatch.setattr(
        "services.job_sources.email_jobs.EmailJobsAdapter.fetch",
        fake_adapter_fetch,
    )

    resp = client.post(
        "/api/jobs/indeed-email-import-all",
        headers={"X-Cron-Token": "test-token"},
    )
    assert resp.status_code == 200
    assert set(seen_types) == {"indeed", "linkedin", "xing"}
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

```bash
python -m pytest tests/api/test_indeed_email_import.py::test_cron_endpoint_iterates_all_three_email_types -v 2>&1 | tail -10
```

Expected: FAIL — entweder Cron-Filter findet nur `indeed_email` oder die anderen Source-Typen werden nicht akzeptiert.

- [ ] **Step 3: `api/jobs_cron.py` anpassen**

Den bestehenden Endpoint `indeed-email-import-all` finden. SQL-Filter erweitern:

```python
# vorher:
sources = JobSource.query.filter(JobSource.type == "indeed_email", JobSource.enabled == True).all()
# nachher:
EMAIL_SOURCE_TYPES = ("indeed_email", "linkedin_email", "xing_email")
sources = JobSource.query.filter(
    JobSource.type.in_(EMAIL_SOURCE_TYPES),
    JobSource.enabled == True,
).all()
```

Auch in `_select_due_source` (wenn dort `indeed_email` ausgeschlossen wird) den Exclude erweitern auf alle drei.

Log-Output pro Plattform:
```python
logger.info("Email-Jobs-Import: type=%s sources=%d jobs=%d",
            source.type, 1, len(jobs))
```

- [ ] **Step 4: Test grün**

```bash
python -m pytest tests/api/test_indeed_email_import.py::test_cron_endpoint_iterates_all_three_email_types -v
```

Expected: PASS.

- [ ] **Step 5: Bestehende Cron-Tests müssen grün bleiben**

```bash
python -m pytest tests/api/test_indeed_email_import.py -v 2>&1 | tail -10
```

Expected: alle ≥17 Tests PASS.

- [ ] **Step 6: Commit**

```bash
git add api/jobs_cron.py tests/api/test_indeed_email_import.py
git commit -m "feat(jobs-cron): email-import-all iteriert über indeed/linkedin/xing

URL-Pfad /api/jobs/indeed-email-import-all bleibt aus historischen
Gründen (VPS-Cron-Zeile unverändert), der Code iteriert aber über
alle drei _email-Source-Typen."
```

### Task 13: Bulk-Email-Endpoint für UI-Mehrfach-Anlage

**Files:**
- Modify: `api/jobs_user.py` (neuer Endpoint `POST /api/jobs/sources/bulk-email`)
- Modify: `tests/api/test_indeed_email_import.py` (oder neu)

- [ ] **Step 1: Test für Bulk-Endpoint**

```python
def test_bulk_email_creates_three_sources(client_authed, db_session):
    """POST /api/jobs/sources/bulk-email mit 3 Plattformen legt 3 Sources an."""
    resp = client_authed.post(
        "/api/jobs/sources/bulk-email",
        json={
            "platforms": ["indeed", "linkedin", "xing"],
            "folder": "[Google Mail]/Alle Nachrichten",
            "lookback_days": 30,
            "limit": 100,
        },
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert len(data["sources"]) == 3
    types = {s["type"] for s in data["sources"]}
    assert types == {"indeed_email", "linkedin_email", "xing_email"}


def test_bulk_email_rejects_empty_platforms(client_authed):
    resp = client_authed.post(
        "/api/jobs/sources/bulk-email",
        json={"platforms": [], "folder": "INBOX"},
    )
    assert resp.status_code == 400
    assert "platforms" in resp.get_json()["error"].lower()


def test_bulk_email_rejects_unknown_platform(client_authed):
    resp = client_authed.post(
        "/api/jobs/sources/bulk-email",
        json={"platforms": ["facebook"], "folder": "INBOX"},
    )
    assert resp.status_code == 400


def test_bulk_email_only_one_platform_allowed(client_authed):
    """Auch eine einzelne Plattform ist OK — legt 1 Source an."""
    resp = client_authed.post(
        "/api/jobs/sources/bulk-email",
        json={"platforms": ["linkedin"], "folder": "INBOX"},
    )
    assert resp.status_code == 201
    assert len(resp.get_json()["sources"]) == 1
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

```bash
python -m pytest tests/api/test_indeed_email_import.py -k "bulk" -v 2>&1 | tail -15
```

Expected: 4 FAILs (Endpoint 404).

- [ ] **Step 3: Endpoint implementieren**

In `api/jobs_user.py` neuen Endpoint hinzufügen:

```python
@jobs_user_bp.post('/sources/bulk-email')
@jwt_required()
def bulk_email_sources():
    """Legt 1–3 Email-Job-Sources auf einen Schlag an.

    Body: {
        platforms: ["indeed", "linkedin", "xing"]  # ≥1, valid keys
        folder: str,  # Default "[Google Mail]/Alle Nachrichten"
        lookback_days: int,  # Default 30
        limit: int,  # Default 100
    }
    """
    from services.job_sources.email_jobs import PROFILES
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    platforms = data.get("platforms") or []
    if not isinstance(platforms, list) or not platforms:
        return jsonify({"error": "platforms muss eine nicht-leere Liste sein"}), 400
    unknown = [p for p in platforms if p not in PROFILES]
    if unknown:
        return jsonify({"error": f"Unbekannte Plattform(en): {unknown}"}), 400

    folder = data.get("folder") or "[Google Mail]/Alle Nachrichten"
    lookback_days = int(data.get("lookback_days") or 30)
    limit = int(data.get("limit") or 100)

    config = {"folder": folder, "lookback_days": lookback_days, "limit": limit}

    created = []
    for platform in platforms:
        source_type = f"{platform}_email"
        # Idempotent: gleiche User+Type → nicht doppeln
        existing = JobSource.query.filter_by(
            user_id=user_id, type=source_type
        ).first()
        if existing:
            continue
        src = JobSource(
            user_id=user_id,
            type=source_type,
            name=f"{PROFILES[platform].source_label} Email",
            config=config,
            enabled=True,
        )
        db.session.add(src)
        db.session.flush()
        created.append(src)
    db.session.commit()
    return jsonify({"sources": [s.to_dict() for s in created]}), 201
```

- [ ] **Step 4: Tests grün**

```bash
python -m pytest tests/api/test_indeed_email_import.py -k "bulk" -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add api/jobs_user.py tests/api/test_indeed_email_import.py
git commit -m "feat(jobs): POST /api/jobs/sources/bulk-email für Mehrfach-Anlage

Legt 1–3 Email-Job-Sources (indeed/linkedin/xing) idempotent an,
mit gemeinsamem Folder/Lookback/Limit."
```

### Task 14: UI — Mehrfach-Setup im Job-Source-Anlage-Flow

**Files:**
- Modify: `index.html` (Source-Anlage-Modal)
- Modify: `service-worker.js` (CACHE_NAME bumpen)

- [ ] **Step 1: `index.html` — neuer Dropdown-Eintrag**

Im Job-Source-Anlage-Dropdown (suchen nach `<option value="indeed">`) hinzufügen:

```html
<option value="bulk_email">📬 Job-Mails (Mehrfach-Auswahl)</option>
```

- [ ] **Step 2: Mehrfach-Setup-Formular im Modal**

Nach dem bestehenden Indeed-Email-Setup-Block einen neuen Block einfügen, der bei `type === "bulk_email"` sichtbar wird:

```html
<div id="bulk-email-setup" style="display:none">
  <h4>📬 Job-Mail-Plattformen</h4>
  <p class="hint">Wähle, welche Job-Empfehlungs-Mails importiert werden sollen. Pro Plattform wird eine eigene Job-Source angelegt.</p>
  <label><input type="checkbox" id="bulk-platform-indeed" checked> 🔍 Indeed</label><br>
  <label><input type="checkbox" id="bulk-platform-linkedin" checked> 💼 LinkedIn</label><br>
  <label><input type="checkbox" id="bulk-platform-xing" checked> 📌 XING</label><br>
  <hr>
  <label>IMAP-Folder:
    <input type="text" id="bulk-folder" value="[Google Mail]/Alle Nachrichten" style="width:100%">
  </label><br>
  <label>Lookback (Tage):
    <input type="number" id="bulk-lookback" value="30" min="1" max="365">
  </label><br>
  <label>Limit pro Plattform:
    <input type="number" id="bulk-limit" value="100" min="10" max="500">
  </label>
</div>
```

- [ ] **Step 3: JS-Handler für Sichtbarkeit + POST**

Im JS-Block der Source-Anlage:

```javascript
// Sichtbarkeit bei Typ-Wechsel
document.getElementById('source-type-select').addEventListener('change', (e) => {
  document.getElementById('bulk-email-setup').style.display =
    e.target.value === 'bulk_email' ? 'block' : 'none';
  // ... andere setup-divs hide
});

// Submit-Handler erweitern
async function submitJobSource() {
  const type = document.getElementById('source-type-select').value;
  if (type === 'bulk_email') {
    const platforms = [];
    if (document.getElementById('bulk-platform-indeed').checked) platforms.push('indeed');
    if (document.getElementById('bulk-platform-linkedin').checked) platforms.push('linkedin');
    if (document.getElementById('bulk-platform-xing').checked) platforms.push('xing');
    if (platforms.length === 0) {
      alert('Bitte mindestens eine Plattform auswählen');
      return;
    }
    const resp = await Auth.fetch('/api/jobs/sources/bulk-email', {
      method: 'POST',
      body: JSON.stringify({
        platforms,
        folder: document.getElementById('bulk-folder').value,
        lookback_days: parseInt(document.getElementById('bulk-lookback').value),
        limit: parseInt(document.getElementById('bulk-limit').value),
      }),
    });
    if (resp.sources) {
      showToast(`${resp.sources.length} Job-Mail-Quelle(n) angelegt`);
      closeSourceModal();
      loadJobSources();
    } else {
      alert(resp.error || 'Anlage fehlgeschlagen');
    }
    return;
  }
  // ... bestehender Code für andere Types
}
```

- [ ] **Step 4: Plattform-Icons in Sources-Liste**

In der `renderJobSources()`-Funktion bzw. wo Sources gelistet werden:

```javascript
const PLATFORM_ICONS = {
  indeed_email: '🔍',
  linkedin_email: '💼',
  xing_email: '📌',
};
// im Template: <span class="platform-icon">${PLATFORM_ICONS[source.type] || '📋'}</span>
```

- [ ] **Step 5: `service-worker.js` CACHE_NAME bumpen**

Aktuellen Wert lesen, um 1 erhöhen:

```bash
grep "CACHE_NAME" service-worker.js
```

```javascript
// vorher: const CACHE_NAME = 'bewerbungstracker-v123';
// nachher: const CACHE_NAME = 'bewerbungstracker-v124';
```

- [ ] **Step 6: Manueller UI-Smoke-Test**

Flask lokal starten, im Browser:
1. Login.
2. Job-Sources-Verwaltung öffnen.
3. „Neue Quelle" → Typ: „📬 Job-Mails (Mehrfach-Auswahl)" wählen.
4. Plattformen alle 3 angehakt lassen.
5. Anlegen klicken.
6. Erwartung: 3 neue Sources in Liste mit den richtigen Icons.

- [ ] **Step 7: Commit**

```bash
git add index.html service-worker.js
git commit -m "feat(jobs-ui): Mehrfach-Setup für Job-Mail-Quellen (Indeed/LinkedIn/Xing)

Neuer Source-Typ 'bulk_email' im Anlage-Dropdown legt via
POST /api/jobs/sources/bulk-email 1–3 Sources auf einen Schlag an,
mit gemeinsamem Folder/Lookback/Limit. Plattform-Icons in Sources-Liste."
```

### Task 15: Bestand-Tests umbenennen + finale Test-Suite

**Files:**
- Rename: `tests/services/test_indeed_email.py` → `tests/services/test_email_jobs.py`

- [ ] **Step 1: git mv des Test-Files**

```bash
git mv tests/services/test_indeed_email.py tests/services/test_email_jobs.py
```

- [ ] **Step 2: Imports im File anpassen**

In `tests/services/test_email_jobs.py`:
```python
# vorher:
from services.job_sources.indeed_email import IndeedEmailAdapter
# nachher:
from services.job_sources.email_jobs import EmailJobsAdapter, PROFILES
```

Klassennamen umbenennen: `TestIndeedEmailAdapter` → `TestEmailJobsAdapterIndeedProfile`. Adapter-Construktor-Aufrufe `IndeedEmailAdapter(config, user)` → `EmailJobsAdapter(config, user=user, platform_profile=PROFILES["indeed"])`.

- [ ] **Step 3: Test-Run**

```bash
python -m pytest tests/services/test_email_jobs.py -v 2>&1 | tail -15
```

Expected: alle 19 Tests PASS.

- [ ] **Step 4: Komplette Test-Suite**

```bash
python -m pytest tests/ --tb=short 2>&1 | tail -20
```

Expected: alle Tests PASS (Bestand + Phase-2-Neue).

- [ ] **Step 5: Commit**

```bash
git add tests/services/test_email_jobs.py
git commit -m "test(email-jobs): test_indeed_email.py → test_email_jobs.py

Bestand-Tests testen jetzt EmailJobsAdapter mit PROFILES['indeed'] —
Verhalten 1:1 identisch zu IndeedEmailAdapter."
```

### Task 16: Deploy + Memory aktualisieren

**Files:**
- VPS: `git pull` + Service-Restart
- Memory: `project_indeed_email_import_live.md` → `project_email_jobs_import_live.md`

- [ ] **Step 1: Push**

```bash
git checkout master
git merge --ff-only merge/indeed-email-to-master  # falls Phase 2 noch im merge-Branch
# Bzw: alle Phase-2-Commits sind direkt auf master gelandet, dann nur:
git push origin master
```

- [ ] **Step 2: VPS-Pull**

```bash
ssh ionos-vps 'cd /var/www/bewerbungen && git pull origin master 2>&1 | tail -10'
```

Expected: Pull bringt die Phase-2-Commits, keine Konflikte.

- [ ] **Step 3: Service-Restart**

```bash
ssh ionos-vps 'systemctl restart bewerbungstracker 2>&1 || systemctl restart gunicorn-bewerbungen 2>&1'
```

- [ ] **Step 4: Production-Smoke-Tests**

```bash
# Health-Check
curl -s -o /dev/null -w "%{http_code}\n" https://bewerbungstracker.wolfinisoftware.de/
# Cron-Endpoint sollte 401 ohne Token geben
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://bewerbungstracker.wolfinisoftware.de/api/jobs/indeed-email-import-all
```

Expected: 200/401 — Service läuft.

- [ ] **Step 5: Memory-Update — File umbenennen + Inhalt aktualisieren**

```bash
# Auf dem Mac:
mv ~/.claude/projects/-Library-WebServer-Documents-Bewerbungstracker/memory/project_indeed_email_import_live.md \
   ~/.claude/projects/-Library-WebServer-Documents-Bewerbungstracker/memory/project_email_jobs_import_live.md
```

Inhalt anpassen:
- Title: "Email-Jobs-Import live (Indeed/LinkedIn/Xing)"
- Frontmatter `name:` und `description:` aktualisieren
- Architektur-Section auf `EmailJobsAdapter + PROFILES` ausweiten
- Cron-Section bleibt (URL-Pfad unverändert)
- Setup-Section auf Bulk-Email-UI ausweiten

- [ ] **Step 6: MEMORY.md-Index aktualisieren**

In `~/.claude/projects/-Library-WebServer-Documents-Bewerbungstracker/memory/MEMORY.md`:
```diff
- [Indeed-Email-Import live (2026-05-17)](project_indeed_email_import_live.md) — ...
+ [Email-Jobs-Import live (2026-05-19)](project_email_jobs_import_live.md) — Indeed/LinkedIn/Xing via generischem EmailJobsAdapter + PlatformProfile-Dict
```

- [ ] **Step 7: Final-Commit & Push**

```bash
git push origin master  # falls schon nicht geschehen
```

---

## Out of Scope

- Stepstone-Mail-Import (separate Iteration)
- HTML-Body-Parsing mit BeautifulSoup (Plain-Text + AI reicht)
- Auto-Follow Tracking-Redirect-URLs
- Bestehende RSS/JSearch-Adapter `linkedin.py`/`xing.py` (unangetastet)

## Verifikation am Schluss

- [ ] Alle Tests grün lokal: `python -m pytest tests/ -q`
- [ ] VPS HEAD = origin/master HEAD
- [ ] VPS working-tree clean (`git status` zeigt nichts modifiziertes)
- [ ] Cron-Zeile aktiv: `ssh ionos-vps 'grep email /etc/cron.d/job-discovery'`
- [ ] UI-Smoke: Bulk-Email-Setup legt 3 Sources an, jede importierbar
- [ ] Memory: `project_email_jobs_import_live.md` reflektiert neuen Zustand
