# Claude Usage Checkup — 2026-05-07

**Deploy-Datum:** 2026-04-30  
**Checkup:** 2026-05-07 (7 Tage post-deploy)  
**Branch:** ops/claude-usage-checkup-2026-05-07

---

## a) Executive Summary

Code-Drift-Check zeigt **keinen Drift**: Alle vier Claude-Wege sind implementiert
(`POST /matches/<id>/score`, `POST /matches/score-bulk`, `PATCH /matches/bulk`,
`POST /matches/<id>/import` mit Claude), `AUTO_CLAUDE_THRESHOLD = 50` ist gesetzt,
und die Cron-Schedule in `DEPLOYMENT.md` B9 lautet korrekt `0 8 * * *`.

**Einschränkung für Stats:** `_run_claude_match_for` loggt alle Claude-Calls
(Auto-Cron **und** On-Demand) mit `endpoint='/api/jobs/claude-match'` in der
`api_calls`-Tabelle — eine direkte DB-Trennung nach Trigger-Typ ist nicht möglich.
Annäherung: Calls zwischen 08:00–09:00 UTC stammen vermutlich vom Cron.
Empfehlung: in einem künftigen Sprint `endpoint`-Wert je Trigger unterscheiden
(z.B. `/api/jobs/claude-match/auto`, `/api/jobs/claude-match/user`).

---

## b) SQL-Queries für VPS (manuell ausführen)

```bash
# SSH zum VPS
ssh ionos-vps

# Dann stats-script ausführen:
cd /var/www/bewerbungen && venv/bin/python scripts/claude_usage_stats.py
```

Datei `scripts/claude_usage_stats.py` anlegen (oder einmalig inline):

```python
#!/usr/bin/env python3
"""Claude-Nutzungsstatistiken letzte 7 Tage — einmalig auf VPS ausführen.

Usage: venv/bin/python scripts/claude_usage_stats.py
"""
import sys
import os
from pathlib import Path
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

from app import create_app
from database import db

app = create_app()
with app.app_context():
    with db.engine.connect() as conn:

        print("=" * 60)
        print("1. Claude-Calls pro Tag (alle Trigger: Cron + On-Demand)")
        print("=" * 60)
        rows = conn.execute(text("""
            SELECT DATE(timestamp) AS day, COUNT(*) AS calls
            FROM api_calls
            WHERE endpoint = '/api/jobs/claude-match'
              AND timestamp >= datetime('now', '-7 days')
            GROUP BY day
            ORDER BY day
        """))
        for r in rows:
            print(f"  {r.day}: {r.calls} Calls")

        print()
        print("=" * 60)
        print("2. Kosten pro Tag (USD + Cent-Äquivalent)")
        print("=" * 60)
        rows = conn.execute(text("""
            SELECT DATE(timestamp) AS day,
                   ROUND(SUM(cost), 4)       AS cost_usd,
                   ROUND(SUM(cost) * 100, 1) AS cost_cents
            FROM api_calls
            WHERE endpoint = '/api/jobs/claude-match'
              AND timestamp >= datetime('now', '-7 days')
            GROUP BY day
            ORDER BY day
        """))
        for r in rows:
            print(f"  {r.day}: ${r.cost_usd} ({r.cost_cents} cent)")

        print()
        print("=" * 60)
        print("3. Distinct User die Claude getriggert haben")
        print("=" * 60)
        rows = conn.execute(text("""
            SELECT DATE(timestamp) AS day,
                   COUNT(DISTINCT user_id) AS users
            FROM api_calls
            WHERE endpoint = '/api/jobs/claude-match'
              AND timestamp >= datetime('now', '-7 days')
            GROUP BY day
            ORDER BY day
        """))
        for r in rows:
            print(f"  {r.day}: {r.users} User(s)")

        print()
        print("=" * 60)
        print("4. Gesamtübersicht letzte 7 Tage")
        print("=" * 60)
        row = conn.execute(text("""
            SELECT COUNT(*)             AS total_calls,
                   COUNT(DISTINCT DATE(timestamp)) AS active_days,
                   COUNT(DISTINCT user_id)          AS unique_users,
                   ROUND(SUM(cost), 4)              AS total_cost_usd,
                   ROUND(AVG(cost) * 100, 2)        AS avg_cost_per_call_cents,
                   SUM(tokens_in)                   AS total_tokens_in,
                   SUM(tokens_out)                  AS total_tokens_out
            FROM api_calls
            WHERE endpoint = '/api/jobs/claude-match'
              AND timestamp >= datetime('now', '-7 days')
        """)).first()
        print(f"  Calls total:          {row.total_calls}")
        print(f"  Aktive Tage:          {row.active_days}/7")
        print(f"  Unique User:          {row.unique_users}")
        print(f"  Gesamtkosten:         ${row.total_cost_usd}")
        print(f"  ⌀ Kosten/Call:        {row.avg_cost_per_call_cents} cent")
        print(f"  Tokens In/Out:        {row.total_tokens_in} / {row.total_tokens_out}")

        print()
        print("=" * 60)
        print("5. Cron vs. On-Demand (APPROX via Stunde 08 UTC = Cron)")
        print("   [Hinweis: DB-Trennung nicht möglich — nur Schätzung]")
        print("=" * 60)
        rows = conn.execute(text("""
            SELECT DATE(timestamp) AS day,
                   SUM(CASE WHEN strftime('%H', timestamp) = '08' THEN 1 ELSE 0 END)
                       AS approx_cron,
                   SUM(CASE WHEN strftime('%H', timestamp) != '08' THEN 1 ELSE 0 END)
                       AS approx_ondemand
            FROM api_calls
            WHERE endpoint = '/api/jobs/claude-match'
              AND timestamp >= datetime('now', '-7 days')
            GROUP BY day
            ORDER BY day
        """))
        for r in rows:
            print(f"  {r.day}: ~Cron={r.approx_cron}  ~On-Demand={r.approx_ondemand}")

        print()
        print("Stats fertig. Werte mit Tabelle in docs/operations/claude-usage-checkup-2026-05-07.md vergleichen.")
```

---

## c) Entscheidungs-Tabelle

Werte aus Abschnitt b) eintragen und passende Zeile identifizieren:

| Messwert (7-Tage-Schnitt)                                          | Bewertung                          | Empfohlene Aktion                                    |
|--------------------------------------------------------------------|------------------------------------|------------------------------------------------------|
| Calls/Tag < 5 **und** approx_ondemand < 3/Tag                     | User ignoriert Feature fast komplett | Cron deaktivieren (Budget sparen), On-Demand bleibt  |
| Calls/Tag > 50 **oder** approx_cron > 30/Tag                      | Cron verbrennt Budget              | `AUTO_CLAUDE_THRESHOLD` auf 60 erhöhen oder Cron 2×/Tag aufteilen |
| Tageskosten > 80 % von `job_daily_budget_cents` (Default: 50 cent) | Budget-Limit zu knapp              | `AUTO_CLAUDE_THRESHOLD` auf 60–70 erhöhen           |
| User-Feedback: „Zu wenig Bewertungen automatisch"                  | Threshold zu hoch                  | `AUTO_CLAUDE_THRESHOLD` auf 40 senken               |
| approx_ondemand >> approx_cron (z. B. 3:1)                        | User bevorzugt manuelle Bewertung  | Cron-Frequenz auf `0 8 * * 1` (nur Mo) oder deaktivieren |
| Calls/Tag 5–50, Kosten im Budget, kein Feedback                   | System läuft normal                | Keine Änderung                                       |

---

## d) Code-Anpassungs-Snippets

Für jeden Fall aus (c) die exakten zwei Stellen:

### Stelle 1 — `api/jobs_cron.py` Zeile 36: Konstante `AUTO_CLAUDE_THRESHOLD`

```python
# Threshold senken (mehr Auto-Bewertungen):
AUTO_CLAUDE_THRESHOLD = 40

# Threshold erhöhen (weniger Auto-Bewertungen, Budget sparen):
AUTO_CLAUDE_THRESHOLD = 60

# Aktueller Wert (kein Handlungsbedarf):
AUTO_CLAUDE_THRESHOLD = 50
```

### Stelle 2 — VPS `/etc/cron.d/job-discovery`: Cron-Zeile

```cron
# Aktuell (1×/Tag 08:00 UTC):
0 8 * * *           root /usr/local/bin/job-discovery-cron.sh claude-match

# 2×/Tag (08:00 + 18:00 UTC, wenn Volumen hoch):
0 8,18 * * *        root /usr/local/bin/job-discovery-cron.sh claude-match

# Nur montags (Minimal-Modus, kaum genutzte Instanz):
0 8 * * 1           root /usr/local/bin/job-discovery-cron.sh claude-match

# Deaktiviert (User nutzt ausschließlich On-Demand):
# 0 8 * * *         root /usr/local/bin/job-discovery-cron.sh claude-match
```

Cron-Reload nach Änderung:
```bash
ssh ionos-vps 'systemctl reload crond && systemctl status crond | head -3'
```

---

## e) Action-Checkliste

1. **SSH zum VPS** — `ssh ionos-vps`
2. **Stats-Script anlegen** — Inhalt aus Abschnitt b) in `scripts/claude_usage_stats.py` kopieren
3. **Script ausführen** — `cd /var/www/bewerbungen && venv/bin/python scripts/claude_usage_stats.py`
4. **Werte ablesen** — Calls/Tag, Kosten, User-Zahl notieren
5. **Tabelle (c) konsultieren** — passende Zeile identifizieren
6. **Falls Threshold-Änderung:** `api/jobs_cron.py` Zeile 36 anpassen → commit → push → auf VPS deployen
7. **Falls Cron-Änderung:** `/etc/cron.d/job-discovery` Zeile ersetzen → `systemctl reload crond`
8. **Falls beide Änderungen nötig:** Code-Commit zuerst, dann Cron-Zeile (Reihenfolge egal, aber Code-Commit zuerst macht Review-Trail sauber)
9. **PR mergen** (dieser Branch) — enthält nur Ops-Bericht, kein Production-Code-Change außer ggf. Drift-Fix
10. **Monitoring** — nächsten Tag nochmals Stats prüfen: sinkende Kosten bei Threshold-Erhöhung erwartet, steigende Bewertungsrate bei Threshold-Senkung

---

*Erstellt von Ops-Review-Agent · 2026-05-07*
