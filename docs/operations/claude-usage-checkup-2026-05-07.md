# Claude Usage Checkup — 2026-05-07 (1 Woche post-deploy)

**Datum:** 2026-05-07
**Bezugszeitraum:** 2026-04-30 – 2026-05-07
**Architektur-Ref:** `docs/superpowers/specs/2026-04-30-claude-on-demand-and-bulk-actions.md`

---

## a) Executive Summary

Code-Drift-Check: **kein kritischer Drift.** Alle vier Claude-Wege (Auto-Cron, Single-Score,
Bulk-Score, Import) sind implementiert und stimmen mit Spec und DEPLOYMENT.md überein.
`AUTO_CLAUDE_THRESHOLD = 50` und Cron-Schedule `0 8 * * *` sind korrekt. Einzige dokumentierte
Abweichung: `PREFILTER_DISMISS_THRESHOLD` wurde post-deploy von 15 auf 5 gesenkt — intentioneller
Fix (zu viele Auto-Dismisses bei Adzuna), kommentiert im Code, kein Bug, keine Action nötig.

Da kein direkter VPS-Zugriff möglich ist: Abschnitt b) enthält ein Python-Skript für den
Production-DB-Check, Abschnitt c) die Entscheidungstabelle, Abschnitt e) die Action-Reihenfolge.

---

## b) SQL-Queries für VPS (manuell ausführen)

```bash
# SSH ins VPS, dann:
cd /var/www/bewerbungen

# Skript einmalig anlegen:
cat > scripts/claude_usage_check.py << 'PYEOF'
"""Claude-Usage-Check — 1 Woche post-deploy (2026-05-07).
Ausführen: venv/bin/python scripts/claude_usage_check.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
app = create_app()

with app.app_context():
    from database import db

    print("=" * 60)
    print("1) Claude-Calls letzte 7 Tage (nach Tag)")
    print("=" * 60)
    rows = db.session.execute(db.text("""
        SELECT DATE(timestamp) AS day, COUNT(*) AS calls
        FROM api_calls
        WHERE endpoint = '/api/jobs/claude-match'
          AND timestamp >= datetime('now', '-7 days')
        GROUP BY day ORDER BY day
    """)).fetchall()
    total_calls = 0
    for r in rows:
        print(f"  {r[0]}: {r[1]} Calls")
        total_calls += r[1]
    avg = total_calls / 7 if rows else 0
    print(f"  → Gesamt: {total_calls}, Ø {avg:.1f}/Tag")

    print()
    print("=" * 60)
    print("2) Kosten letzte 7 Tage (nach Tag, in EUR)")
    print("=" * 60)
    rows2 = db.session.execute(db.text("""
        SELECT DATE(timestamp) AS day,
               COUNT(*) AS calls,
               ROUND(SUM(cost), 4) AS cost_eur
        FROM api_calls
        WHERE endpoint = '/api/jobs/claude-match'
          AND timestamp >= datetime('now', '-7 days')
        GROUP BY day ORDER BY day
    """)).fetchall()
    total_cost = 0.0
    for r in rows2:
        print(f"  {r[0]}: {r[1]} Calls, {r[2]} EUR")
        total_cost += float(r[2] or 0)
    print(f"  → 7-Tage-Gesamt: {total_cost:.4f} EUR, Ø {total_cost/7:.4f} EUR/Tag")

    print()
    print("=" * 60)
    print("3) Distinct User die Claude triggerten (nach Tag)")
    print("=" * 60)
    rows3 = db.session.execute(db.text("""
        SELECT DATE(timestamp) AS day, COUNT(DISTINCT user_id) AS users
        FROM api_calls
        WHERE endpoint = '/api/jobs/claude-match'
          AND timestamp >= datetime('now', '-7 days')
        GROUP BY day ORDER BY day
    """)).fetchall()
    for r in rows3:
        print(f"  {r[0]}: {r[1]} User")

    print()
    print("=" * 60)
    print("4) Auto-Cron (~08 UTC) vs. On-Demand — Heuristik nach Tageszeit")
    print("   (Alle Wege loggen auf '/api/jobs/claude-match' — Tageszeit ist")
    print("    beste Annaeherung: 07–09 UTC ≈ Auto-Cron, Rest ≈ On-Demand)")
    print("=" * 60)
    rows4 = db.session.execute(db.text("""
        SELECT
            CASE WHEN strftime('%H', timestamp) BETWEEN '07' AND '09'
                 THEN 'cron-08:00-window (07-09 UTC)'
                 ELSE 'on-demand (ausserhalb 07-09 UTC)'
            END AS call_type,
            COUNT(*) AS calls,
            ROUND(SUM(cost), 4) AS cost_eur
        FROM api_calls
        WHERE endpoint = '/api/jobs/claude-match'
          AND timestamp >= datetime('now', '-7 days')
        GROUP BY call_type
    """)).fetchall()
    for r in rows4:
        print(f"  {r[0]}: {r[1]} Calls, {r[2]} EUR")

    print()
    print("=" * 60)
    print("5) Budget-Auslastung pro User pro Tag (letzte 7 Tage)")
    print("=" * 60)
    rows5 = db.session.execute(db.text("""
        SELECT u.email,
               u.job_daily_budget_cents,
               DATE(ac.timestamp) AS day,
               COUNT(*) AS calls,
               ROUND(SUM(ac.cost) * 100, 1) AS used_cents
        FROM api_calls ac
        JOIN users u ON u.id = ac.user_id
        WHERE ac.endpoint = '/api/jobs/claude-match'
          AND ac.timestamp >= datetime('now', '-7 days')
        GROUP BY u.id, day
        ORDER BY day, u.email
    """)).fetchall()
    for r in rows5:
        budget = int(r[1] or 0)
        used = float(r[4] or 0)
        pct = (used / budget * 100) if budget > 0 else 0
        flag = " ⚠ BUDGET-NAH" if pct > 70 else ""
        print(f"  {r[2]} | {r[0]}: {r[3]} Calls, "
              f"{used:.0f}/{budget} Cent ({pct:.0f}%){flag}")

    print()
    print("Done. Werte oben in Tabelle c) eintragen.")
PYEOF

# Ausführen:
venv/bin/python scripts/claude_usage_check.py
```

---

## c) Entscheidungstabelle

Werte aus den Query-Ergebnissen oben eintragen und passende Zeile wählen:

| Szenario | Messwert (aus Queries) | Empfehlung | Maßnahme |
|----------|------------------------|------------|----------|
| Alles ruhig | Ø < 10 Calls/Tag, On-Demand < 5 Calls/Tag, Budget < 30% | Keine Änderung | PR mergen, nächster Check 2026-06-07 |
| Nur Cron genutzt, kein On-Demand | On-Demand-Anteil = 0 über 7 Tage | UI-Feature-Sichtbarkeit prüfen | "🤖 Bewerten lassen"-Button im Frontend auf Sichtbarkeit testen |
| Kaum Nutzung gesamt | Ø < 3 Calls/Tag | Cron auf 2×/Woche reduzieren | Cron auf `0 8 * * 1,4` ändern (VPS) |
| Hoher Auto-Cron-Anteil | Cron-Window > 70% aller Calls | Threshold erhöhen | `AUTO_CLAUDE_THRESHOLD = 65` in `api/jobs_cron.py:38` |
| Budget mehrfach erschöpft | ≥ 3 Tage mit > 80% Budget-Auslastung | Budget zu eng oder Threshold zu niedrig | Threshold auf 60–70 ODER `job_daily_budget_cents` erhöhen |
| Viele On-Demand-Calls | On-Demand > 30 Calls/Tag | Feature wird aktiv genutzt | Kein Handlungsbedarf; ggf. Cron auf `0 8,18 * * *` für bessere Auto-Basis |
| User-Feedback "zu wenig Auto-Bewertungen" | manuell | Threshold zu hoch | `AUTO_CLAUDE_THRESHOLD = 40` |
| Cron-Kosten > 80% des Tagesbudgets täglich | Budget-Spalte > 80% bei cron-window | Cron deaktivieren oder threshold hoch | Cron kommentieren oder Threshold auf 70+ |

---

## d) Code-Anpassungs-Snippets

Je nach Tabelle c) die passenden Snippets verwenden:

### Snippet 1: `AUTO_CLAUDE_THRESHOLD` in `api/jobs_cron.py:38`

```python
# Senken — mehr Auto-Bewertungen (User sieht zu wenig):
AUTO_CLAUDE_THRESHOLD = 40

# Aktuell (Standard, kein Handlungsbedarf):
AUTO_CLAUDE_THRESHOLD = 50

# Erhöhen — sparsamerer Verbrauch (Budget-Probleme):
AUTO_CLAUDE_THRESHOLD = 65
```

Nach Code-Änderung: `git add api/jobs_cron.py && git commit -m "ops: AUTO_CLAUDE_THRESHOLD anpassen"`, dann auf VPS `git pull && systemctl restart bewerbungen`.

### Snippet 2: Cron-Zeile auf VPS `/etc/cron.d/job-discovery`

```cron
# Aktuell — 1×/Tag 08:00 UTC (Standard):
0 8 * * *           root /usr/local/bin/job-discovery-cron.sh claude-match

# 2×/Tag (08:00 + 18:00 UTC) — bei hohem On-Demand-Bedarf:
0 8,18 * * *        root /usr/local/bin/job-discovery-cron.sh claude-match

# 2×/Woche Mo+Do 08:00 UTC — bei sehr geringer Nutzung:
0 8 * * 1,4         root /usr/local/bin/job-discovery-cron.sh claude-match

# Deaktiviert (auskommentiert) — nur On-Demand:
# 0 8 * * *         root /usr/local/bin/job-discovery-cron.sh claude-match
```

Nach VPS-Änderung: `sudo systemctl reload crond && sudo systemctl status crond | head -3`

---

## e) Action-Checkliste

1. **SSH ins VPS:** `ssh ionos-vps`
2. **Skript anlegen** (einmalig): Inhalt aus Abschnitt b) in `/var/www/bewerbungen/scripts/claude_usage_check.py` einfügen
3. **Queries ausführen:** `cd /var/www/bewerbungen && venv/bin/python scripts/claude_usage_check.py`
4. **Werte notieren:**
   - Ø Calls/Tag (Query 1)
   - 7-Tage-Kosten gesamt (Query 2)
   - Distinct User (Query 3)
   - Cron-Window-Anteil vs. On-Demand (Query 4)
   - Maximale Tages-Budget-Auslastung (Query 5)
5. **Tabelle c) konsultieren** → passendes Szenario wählen
6. **Falls Threshold-Änderung nötig:**
   - Lokal: `api/jobs_cron.py:38` editieren → commit pushen
   - VPS: `git pull origin master && systemctl restart bewerbungen`
7. **Falls Cron-Frequenz-Änderung nötig:**
   - VPS: `sudo nano /etc/cron.d/job-discovery` → Snippet aus d) einfügen
   - `sudo systemctl reload crond`
8. **Falls kein Handlungsbedarf:** PR mergen, nächster Checkup-Termin: **2026-06-07**

---

## Anhang: Drift-Check-Details

| Prüfpunkt | Spec / DEPLOYMENT.md | Code (aktuell) | Status |
|-----------|---------------------|----------------||--------|
| `AUTO_CLAUDE_THRESHOLD` | 50 | 50 (`api/jobs_cron.py:38`) | ✅ OK |
| Cron-Schedule | `0 8 * * *` | dokumentiert in `DEPLOYMENT.md` B9 | ✅ OK |
| `_run_claude_match_for` Helper | vorhanden | `api/jobs_cron.py:254` | ✅ OK |
| `POST /matches/<id>/score` | vorhanden | `api/jobs_user.py:286` | ✅ OK |
| `POST /matches/score-bulk` | vorhanden | `api/jobs_user.py:335` | ✅ OK |
| `PATCH /matches/bulk` | vorhanden | `api/jobs_user.py:402` | ✅ OK |
| Import mit Claude-Call | vorhanden | `api/jobs_user.py:228` | ✅ OK |
| `PREFILTER_DISMISS_THRESHOLD` | 15 (Spec) | **5** (Code) | ⚠️ Intentionell post-deploy geändert: Adzuna liefert breite Ergebnisse → 600+ Auto-Dismisses bei Schwelle 15. Code-Kommentar erklärt Rationale. Kein Bug. |
