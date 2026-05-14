# Feature-Spec: Status "unbewertet" für Jobvorschläge

**Date:** 2026-05-14  
**Scope:** Add new JobMatch status `unbewertet` for pending job evaluations  
**Affected Files:** models.py, api/jobs_user.py, tests/, frontend

## Anforderung

Nutzer möchte:
- Jobvorschläge als "unbewertet" markieren können
- Diese sofort sichtbar und filterbar machen
- Workflow: `new` (nie angesehen) → `unbewertet` (angesehen aber noch nicht entschieden) → `dismissed`/`imported`

## Design

### Status-Modell

**Aktuell:**
- `new` = noch nicht angesehen
- `seen` = angesehen
- `dismissed` = verworfen
- `imported` = als Application übernommen

**Neu:**
- `new` = noch nicht angesehen (wie bisher)
- `unbewertet` = bewusst als "noch nicht entschieden" gekennzeichnet
- `seen` = entfernen (redundant mit `unbewertet`)
- `dismissed` = verworfen
- `imported` = als Application übernommen

### Übergänge

```
new → unbewertet → dismissed / imported
```

### API-Änderungen

- `GET /api/jobs/matches?status=unbewertet` — zeigt unbewertete Jobs
- `PATCH /api/jobs/matches/{id}` — akzeptiert `status='unbewertet'`
- `POST /api/jobs/matches/bulk` — aktualisiert Status in Batch
- Validierung: erlaubt nur `'unbewertet'`, `'dismissed'`, `'new'` (nicht `'seen'`)

### Datenbankmigrationen

- JobMatch.status Default bleibt `'new'`
- Alte `'seen'` Einträge werden zu `'unbewertet'` migriert
- Keine Daten-Verlust

### Frontend-Verhalten

- Default-Filter: `['new', 'unbewertet']` (zeigt alle unbewerteten)
- Filteroption explizit als "Unbewertete" anzeigen
- UI-Label: "Unbewertet" für neue UX

## Implementierung

1. **models.py:** JobMatch-Kommentar aktualisieren, keine DB-Änderung nötig (status VARCHAR)
2. **api/jobs_user.py:** Status-Validierung bei `PATCH` und Bulk anpassen
3. **Migration:** seen → unbewertet konvertieren (optional, mit Data-Cleanup)
4. **Tests:** Status-Übergänge testen
5. **Frontend:** Filter-UI aktualisieren

## Rollback

Falls erforderlich: `'unbewertet'` → `'new'` zurückkonvertieren via Migration.
