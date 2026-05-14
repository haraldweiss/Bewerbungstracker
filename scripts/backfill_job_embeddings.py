#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Backfill JobEmbedding für alle existierenden RawJobs ohne Embedding.

Usage:
    python scripts/backfill_job_embeddings.py              # alle
    python scripts/backfill_job_embeddings.py --limit 100  # nur 100
    python scripts/backfill_job_embeddings.py --check      # nur zählen
"""

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from database import db
from models import RawJob, JobEmbedding
from services.job_matching.embedder import embed_raw_job


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--check', action='store_true', help='Nur zählen, nicht embeddem')
    parser.add_argument('--sleep', type=float, default=0.1,
                        help='Sekunden zwischen Embeds (Rate-Limit)')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        q = (RawJob.query
             .outerjoin(JobEmbedding, JobEmbedding.raw_job_id == RawJob.id)
             .filter(JobEmbedding.raw_job_id.is_(None)))
        total = q.count()
        print(f'Pending: {total} RawJobs ohne Embedding')
        if args.check:
            return

        if args.limit:
            q = q.limit(args.limit)

        done = 0
        failed = 0
        for raw in q.all():
            ok = embed_raw_job(raw)
            if ok:
                done += 1
            else:
                failed += 1
                print(f'  FAIL raw_job_id={raw.id} (Ollama down?)')
                if failed > 5:
                    print('Too many failures, aborting')
                    break
            if done % 10 == 0 and done > 0:
                print(f'  ... {done} done')
            time.sleep(args.sleep)

        print(f'Done: {done} embedded, {failed} failed')


if __name__ == '__main__':
    main()
