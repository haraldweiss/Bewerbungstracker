#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Scheduled task: Weekly AI words research.

Runs the AIWordsResearchService, stores results in database, and reports errors.
Exit code 0 on success, 1 on error. Logs all activity to disk and database.
"""
import sys
import logging
import json
from datetime import datetime
from pathlib import Path

# Add project root to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask
from database import db
from models import AIWordsResearchLog
from services.ai_words_research_service import AIWordsResearchService

# Configure logging to both file and console
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'ai_words_research.log'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


def run_research_task():
    """Run research and store results in database.

    Returns:
        int: 0 on success, 1 on error
    """
    logger.info('=== Starting scheduled AI words research task ===')

    # Initialize Flask app context (needed for database operations)
    app = Flask(__name__)
    # Use environment config or defaults
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        'sqlite:///bewerbungen.db'  # Default for local testing
    )
    db.init_app(app)

    try:
        with app.app_context():
            service = AIWordsResearchService()
            logger.info('Initialized AIWordsResearchService')

            # Run the research
            result = service.research()
            logger.info('Research completed: %s', result)

            # Store result in database
            log_entry = AIWordsResearchLog(
                timestamp=datetime.fromisoformat(result['timestamp']),
                found_total=result['found_total'],
                new_count=result['new_count'],
                new_words=result['new_words'],
                sources_checked={'arbeits-abc.de': True},
                error_message=None,
            )
            db.session.add(log_entry)
            db.session.commit()
            logger.info('Stored research log: id=%d, found=%d, new=%d',
                       log_entry.id, log_entry.found_total, log_entry.new_count)

            logger.info('=== Research task completed successfully ===')
            return 0

    except Exception as e:
        logger.exception('Research task failed: %s', e)

        # Try to store error in database (may fail if db not accessible)
        try:
            with app.app_context():
                log_entry = AIWordsResearchLog(
                    timestamp=datetime.utcnow(),
                    found_total=0,
                    new_count=0,
                    new_words=[],
                    sources_checked={'arbeits-abc.de': False},
                    error_message=str(e),
                )
                db.session.add(log_entry)
                db.session.commit()
                logger.info('Stored error log: id=%d', log_entry.id)
        except Exception as db_error:
            logger.error('Failed to store error in database: %s', db_error)

        logger.info('=== Research task failed ===')
        return 1


if __name__ == '__main__':
    exit_code = run_research_task()
    sys.exit(exit_code)
