#!/usr/bin/env python3
"""Einmalige Migration: bestehende `users.ai_provider_config` (Bewerbungstracker)
in den ai-provider-service rüberkopieren.

Was es tut:
- Iteriert alle User mit nicht-leerem `ai_provider_config`.
- Für jeden konfigurierten Provider (openai/mammouth/custom):
  - Dekryptiert den `api_key_encrypted` mit dem User-DEK (falls möglich).
  - POSTed die Config an `/configs/<user.id>/<provider>`.
- Zählt Erfolge, Skips, Fehler.

Voraussetzungen:
- Service muss erreichbar sein (AI_PROVIDER_SERVICE_URL + AI_PROVIDER_SERVICE_TOKEN).
- DEK-Cache muss gefüllt sein (User muss aktiv eingeloggt sein) — sonst werden
  diese User geskippt und in der Ausgabe gemeldet.

Aufruf:
    cd /var/www/bewerbungen
    ./venv/bin/python scripts/migrate_provider_configs_to_service.py
    # oder mit --dry-run um nur zu sehen was passieren würde:
    ./venv/bin/python scripts/migrate_provider_configs_to_service.py --dry-run
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Repo-Root in sys.path damit `from app import ...` funktioniert
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from database import db
from models import User
from services.encryption_service import EncryptionService
from services.key_cache import get_key_cache
from services import ai_provider_client

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def migrate_user(user: User, client, dry_run: bool = False) -> dict:
    """Migriert die Provider-Configs eines Users."""
    if not user.ai_provider_config:
        return {'status': 'no_config'}

    try:
        config = json.loads(user.ai_provider_config)
    except json.JSONDecodeError:
        return {'status': 'invalid_json'}

    if not config:
        return {'status': 'empty_config'}

    dek = get_key_cache().get(user.id)
    needs_dek = any('api_key_encrypted' in (v or {}) for v in config.values())

    if needs_dek and not dek:
        return {'status': 'no_dek_in_cache', 'providers': list(config.keys())}

    results = {}
    for provider_id, provider_cfg in config.items():
        if provider_id not in ('openai', 'mammouth', 'custom'):
            results[provider_id] = 'skip_unknown_provider'
            continue

        # API-Key dekryptieren falls vorhanden
        cfg_for_service = {}
        for key, value in (provider_cfg or {}).items():
            if key == 'api_key_encrypted' and value:
                try:
                    cfg_for_service['api_key'] = EncryptionService.decrypt_data(value, dek)
                except Exception as e:
                    results[provider_id] = f'decrypt_failed: {e}'
                    break
            elif key in ('api_endpoint', 'organization_id', 'name'):
                cfg_for_service[key] = value
        else:
            if dry_run:
                results[provider_id] = f'would_migrate ({", ".join(cfg_for_service.keys())})'
            else:
                try:
                    client.save_config(
                        user_id=user.id, provider_id=provider_id,
                        config=cfg_for_service,
                        fallback_provider=None,
                        queue_when_unavailable=True,
                    )
                    results[provider_id] = 'migrated'
                except Exception as e:
                    results[provider_id] = f'service_error: {e}'

    return {'status': 'processed', 'providers': results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Nur zeigen was passieren würde')
    parser.add_argument('--user-id', help='Nur diesen User migrieren')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if not ai_provider_client.is_enabled():
            logger.error('AI_PROVIDER_SERVICE_URL/TOKEN nicht gesetzt — Migration unmöglich.')
            sys.exit(1)

        client = ai_provider_client.get_client()

        # Health-Check
        try:
            providers = client.list_providers()
            logger.info(f'Service erreichbar, {len(providers)} Provider verfügbar')
        except Exception as e:
            logger.error(f'Service nicht erreichbar: {e}')
            sys.exit(1)

        query = User.query.filter(User.ai_provider_config.isnot(None))
        if args.user_id:
            query = query.filter(User.id == args.user_id)
        users = query.all()

        logger.info(f'{"DRY-RUN: " if args.dry_run else ""}Migrate {len(users)} User(s)')
        logger.info('---')

        stats = {'no_config': 0, 'empty_config': 0, 'invalid_json': 0,
                 'no_dek_in_cache': 0, 'processed': 0,
                 'migrated_providers': 0, 'failed_providers': 0}

        for user in users:
            res = migrate_user(user, client, dry_run=args.dry_run)
            status = res.get('status', 'unknown')
            stats[status] = stats.get(status, 0) + 1

            if status == 'processed':
                provider_results = res.get('providers') or {}
                for pid, outcome in provider_results.items():
                    if outcome in ('migrated',) or outcome.startswith('would_migrate'):
                        stats['migrated_providers'] += 1
                        logger.info(f'  ✓ {user.email} {pid} → {outcome}')
                    else:
                        stats['failed_providers'] += 1
                        logger.warning(f'  ✗ {user.email} {pid} → {outcome}')
            elif status == 'no_dek_in_cache':
                logger.warning(f'  ⊘ {user.email}: DEK nicht im Cache (nicht eingeloggt) — skipped {res.get("providers")}')

        logger.info('---')
        logger.info('Statistik:')
        for k, v in stats.items():
            logger.info(f'  {k}: {v}')

        if args.dry_run:
            logger.info('DRY-RUN — keine Änderungen wurden vorgenommen.')


if __name__ == '__main__':
    main()
