"""Seed-Skript: legt globale Default-Quellen an + optional update env-Felder.

Default (ohne Flag): legt fehlende Sources an, lässt bestehende unverändert.

Mit ``--update-env-fields``: aktualisiert in bestehenden Sources nur die
env-var-getriebenen Felder (rss_url, aggregator_key). User-Anpassungen an
``query``, ``location``, ``tags`` etc. bleiben erhalten.

Usage:
    python scripts/seed_job_sources.py
    python scripts/seed_job_sources.py --update-env-fields
"""
import argparse
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database import db
from models import JobSource

# Felder, die aus env-vars befüllt werden — nur diese sind beim
# --update-env-fields-Modus überschreibbar (User-Customizations
# wie query/location/tags bleiben unangetastet).
ENV_DRIVEN_FIELDS = {"rss_url", "aggregator_key"}


DEFAULTS = [
    {
        "name": "Bundesagentur — Frontend Entwickler Berlin",
        "type": "bundesagentur",
        "config": {"was": "Frontend Entwickler", "wo": "10115", "umkreis": 50},
    },
    {
        "name": "Bundesagentur — Backend Entwickler Berlin",
        "type": "bundesagentur",
        "config": {"was": "Backend Entwickler", "wo": "10115", "umkreis": 50},
    },
    {
        "name": "Arbeitnow — Remote Tech",
        "type": "arbeitnow",
        "config": {"tags": ["javascript", "python", "remote"]},
    },
    {
        "name": "Xing — Python Berlin",
        "type": "xing",
        # 180 min = JSearch Free-Tier-friendly (~ 8 calls/Tag pro Source)
        "crawl_interval_min": 180,
        "config": {
            "rss_url": os.getenv("XING_RSS_URL", ""),
            "aggregator_key": os.getenv("RAPIDAPI_KEY", ""),
            "query": "python developer",
            "location": "Germany",
        },
    },
    {
        "name": "LinkedIn — Engineering Berlin",
        "type": "linkedin",
        "crawl_interval_min": 180,
        "config": {
            "rss_url": os.getenv("LINKEDIN_RSS_URL", ""),
            "aggregator_key": os.getenv("RAPIDAPI_KEY", ""),
            "query": "software engineer",
            "location": "Germany",
        },
    },
    {
        "name": "Stepstone — Tech Berlin",
        "type": "stepstone",
        "crawl_interval_min": 180,
        "config": {
            "rss_url": os.getenv("STEPSTONE_RSS_URL", ""),
            "aggregator_key": os.getenv("RAPIDAPI_KEY", ""),
            "query": "developer",
            "location": "Germany",
        },
    },
]


def _update_env_fields(existing: JobSource, default_config: dict) -> list[str]:
    """Patcht env-getriebene Felder von existing.config aus default_config.

    Gibt Liste der geänderten Feld-Namen zurück (für Logging). Andere Felder
    in existing.config bleiben unverändert.
    """
    cfg = existing.config
    changed = []
    for field in ENV_DRIVEN_FIELDS:
        new_val = default_config.get(field)
        if new_val is None:
            continue
        if cfg.get(field) != new_val:
            cfg[field] = new_val
            changed.append(field)
    if changed:
        existing.config = cfg  # triggert _config_json setter
    return changed


def main(update_env_fields: bool = False):
    app = create_app()
    with app.app_context():
        for d in DEFAULTS:
            existing = JobSource.query.filter_by(name=d["name"], user_id=None).first()
            if existing:
                if update_env_fields:
                    changed = _update_env_fields(existing, d["config"])
                    if changed:
                        print(f"~ {d['name']} (updated: {', '.join(changed)})")
                    else:
                        print(f"= {d['name']} (keine env-Änderung)")
                else:
                    print(f"= {d['name']} (existiert bereits)")
                continue
            src = JobSource(
                user_id=None, name=d["name"], type=d["type"],
                enabled=True,
                crawl_interval_min=d.get("crawl_interval_min", 60),
            )
            src.config = d["config"]
            db.session.add(src)
            print(f"+ {d['name']} (interval={src.crawl_interval_min}min)")
        db.session.commit()
        print("✓ Seed abgeschlossen.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument(
        "--update-env-fields",
        action="store_true",
        help="Bei bestehenden Sources rss_url + aggregator_key aus env-vars updaten",
    )
    args = parser.parse_args()
    main(update_env_fields=args.update_env_fields)
