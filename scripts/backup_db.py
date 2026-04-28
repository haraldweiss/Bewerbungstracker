#!/usr/bin/env python3
"""
Bewerbungstracker DB Backup.

Macht atomare Online-Backups der SQLite-Datenbanken (mit der SQLite-Backup-API,
NICHT mit cp – das wäre bei parallelen Writes inkonsistent), komprimiert sie
und rotiert ältere Backups raus.

Standard-Lauf via systemd timer `bewerbungen-backup.timer` (täglich).

Konfiguration über Env-Vars:
    BACKUP_DIR      Zielverzeichnis (default: /var/backups/bewerbungen)
    RETENTION_DAYS  Wie viele Tage rückwärts behalten (default: 30)
    DB_PATHS        Komma-separiert; default sind die beiden Production-DBs
"""
import gzip
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

DEFAULT_DBS = [
    "/var/www/bewerbungen/instance/bewerbungstracker.db",
    "/var/www/bewerbungen/email_config.db",
]


def backup_one(src: Path, dst_dir: Path, ts: str) -> Path:
    """SQLite-Backup mit Online-API + gzip. Liefert den finalen .gz-Pfad."""
    out_db = dst_dir / f"{src.stem}_{ts}.db"
    out_gz = out_db.with_suffix(".db.gz")

    # Online-Backup: atomar, kein Lock-Konflikt mit laufendem gunicorn-Worker.
    with sqlite3.connect(str(src)) as src_conn, sqlite3.connect(str(out_db)) as dst_conn:
        src_conn.backup(dst_conn)

    # Komprimieren (chunkweise, damit auch große DBs im RAM nicht explodieren).
    with open(out_db, "rb") as fin, gzip.open(out_gz, "wb", compresslevel=6) as fout:
        shutil.copyfileobj(fin, fout, length=1024 * 1024)
    out_db.unlink()
    return out_gz


def rotate(dst_dir: Path, retention_days: int) -> int:
    """Löscht *.db.gz älter als retention_days. Returns: Anzahl gelöschter Files."""
    cutoff = time.time() - retention_days * 86400
    removed = 0
    for old in dst_dir.glob("*.db.gz"):
        if old.stat().st_mtime < cutoff:
            old.unlink()
            removed += 1
    return removed


def main() -> int:
    backup_dir = Path(os.environ.get("BACKUP_DIR", "/var/backups/bewerbungen"))
    retention_days = int(os.environ.get("RETENTION_DAYS", "30"))
    db_paths = [
        Path(p.strip())
        for p in os.environ.get("DB_PATHS", ",".join(DEFAULT_DBS)).split(",")
        if p.strip()
    ]

    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d_%H-%M-%S")

    success = 0
    failed = 0
    for src in db_paths:
        if not src.exists():
            print(f"[skip] {src} existiert nicht")
            continue
        try:
            out_gz = backup_one(src, backup_dir, ts)
            size_kb = out_gz.stat().st_size / 1024
            print(f"[ok]   {src} → {out_gz} ({size_kb:.1f} KB)")
            success += 1
        except Exception as e:
            print(f"[fail] {src}: {e}", file=sys.stderr)
            failed += 1

    rotated = rotate(backup_dir, retention_days)
    if rotated:
        print(f"[rot]  {rotated} alte Backups (>{retention_days}d) entfernt")

    summary_total = sum(p.stat().st_size for p in backup_dir.glob("*.db.gz"))
    print(f"[sum]  {success} backup(s), {failed} failed, "
          f"{len(list(backup_dir.glob('*.db.gz')))} files in {backup_dir}, "
          f"{summary_total / 1024 / 1024:.1f} MB total")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
