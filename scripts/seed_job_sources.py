"""Seed-Skript: legt 3 globale Default-Quellen an, falls nicht vorhanden.

Idempotent — re-runs überschreiben nichts.

Usage:
    python scripts/seed_job_sources.py
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database import db
from models import JobSource


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
        "config": {
            "rss_url": os.getenv("STEPSTONE_RSS_URL", ""),
            "aggregator_key": os.getenv("RAPIDAPI_KEY", ""),
            "query": "developer",
            "location": "Germany",
        },
    },
]


def main():
    app = create_app()
    with app.app_context():
        for d in DEFAULTS:
            existing = JobSource.query.filter_by(name=d["name"], user_id=None).first()
            if existing:
                print(f"= {d['name']} (existiert bereits)")
                continue
            src = JobSource(
                user_id=None, name=d["name"], type=d["type"],
                enabled=True, crawl_interval_min=60,
            )
            src.config = d["config"]
            db.session.add(src)
            print(f"+ {d['name']}")
        db.session.commit()
        print("✓ Seed abgeschlossen.")


if __name__ == '__main__':
    main()
