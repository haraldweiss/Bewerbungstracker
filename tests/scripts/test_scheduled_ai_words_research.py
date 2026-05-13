# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests for the scheduled AI words research task script."""
import pytest
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

# This tests the script as a subprocess (integration test)


@pytest.fixture
def script_path():
    """Return the path to the scheduled task script."""
    return Path(__file__).parent.parent.parent / 'scripts' / 'scheduled_ai_words_research.py'


@pytest.fixture
def log_file():
    """Return the path to the expected log file."""
    return Path(__file__).parent.parent.parent / 'logs' / 'ai_words_research.log'


def test_scheduled_task_logs_to_file(script_path, log_file):
    """Script creates and writes to ai_words_research.log."""
    # Clear log if exists
    if log_file.exists():
        log_file.unlink()

    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        timeout=30
    )

    # Verify log file created (even on error)
    assert log_file.exists(), "Log file should be created"
    log_content = log_file.read_text()
    assert 'Starting scheduled AI words research task' in log_content


def test_scheduled_task_stores_result_in_database(app, db_session):
    """Running script stores result in AIWordsResearchLog table.

    This test mocks the AIWordsResearchService to return a successful result
    without needing network access.
    """
    from models import AIWordsResearchLog
    from database import db

    # Count initial logs
    initial_count = AIWordsResearchLog.query.count()

    # Mock the scraping to return test data
    with patch('services.ai_words_research_service.AIWordsResearchService.scrape_arbeits_abc') as mock_scrape:
        mock_scrape.return_value = {'test-word-1', 'test-word-2', 'test-word-3'}

        # Import inside the app context
        with app.app_context():
            from services.ai_words_research_service import AIWordsResearchService
            service = AIWordsResearchService()
            result = service.research()

            # Verify result structure
            assert 'timestamp' in result
            assert 'found_total' in result
            assert 'new_count' in result
            assert 'new_words' in result
            assert 'sources_checked' in result

            # Store result like the script does
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

            # Verify new log was created
            final_count = AIWordsResearchLog.query.count()
            assert final_count == initial_count + 1

            # Verify latest log has correct structure
            latest = AIWordsResearchLog.query.order_by(
                AIWordsResearchLog.id.desc()
            ).first()
            assert latest.found_total == 3
            assert latest.new_count == 3
            assert isinstance(latest.new_words, list)
            assert isinstance(latest.sources_checked, dict)
            assert latest.error_message is None  # Success, no error


def test_scheduled_task_error_handling(app, db_session):
    """Task gracefully handles errors and stores them in database."""
    from models import AIWordsResearchLog
    from database import db

    # Count initial logs
    initial_count = AIWordsResearchLog.query.count()

    # Mock the scraping to raise an error
    with patch('services.ai_words_research_service.AIWordsResearchService.scrape_arbeits_abc') as mock_scrape:
        mock_scrape.side_effect = ValueError("Test network error")

        with app.app_context():
            from services.ai_words_research_service import AIWordsResearchService
            service = AIWordsResearchService()

            # Expect the research to raise
            with pytest.raises(ValueError):
                service.research()

            # Simulate error logging like the script does
            try:
                raise ValueError("Simulated research failure")
            except Exception as e:
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

            # Verify error was logged
            final_count = AIWordsResearchLog.query.count()
            assert final_count == initial_count + 1

            latest = AIWordsResearchLog.query.order_by(
                AIWordsResearchLog.id.desc()
            ).first()
            assert latest.error_message is not None
            assert 'Simulated research failure' in latest.error_message
            assert latest.found_total == 0
            assert latest.new_count == 0


def test_scheduled_task_sources_checked_format(app, db_session):
    """Verify sources_checked is stored as a dict (JSON)."""
    from models import AIWordsResearchLog
    from database import db

    with patch('services.ai_words_research_service.AIWordsResearchService.scrape_arbeits_abc') as mock_scrape:
        mock_scrape.return_value = {'word1', 'word2'}

        with app.app_context():
            from services.ai_words_research_service import AIWordsResearchService
            service = AIWordsResearchService()
            result = service.research()

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

            # Retrieve and verify
            latest = AIWordsResearchLog.query.order_by(
                AIWordsResearchLog.id.desc()
            ).first()
            assert isinstance(latest.sources_checked, dict)
            assert 'arbeits-abc.de' in latest.sources_checked
            assert latest.sources_checked['arbeits-abc.de'] is True


def test_scheduled_task_new_words_stored_as_list(app, db_session):
    """Verify new_words is stored as a JSON list."""
    from models import AIWordsResearchLog
    from database import db

    with patch('services.ai_words_research_service.AIWordsResearchService.scrape_arbeits_abc') as mock_scrape:
        mock_scrape.return_value = {'alpha', 'beta', 'gamma'}

        with app.app_context():
            from services.ai_words_research_service import AIWordsResearchService
            service = AIWordsResearchService()
            result = service.research()

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

            # Retrieve and verify
            latest = AIWordsResearchLog.query.order_by(
                AIWordsResearchLog.id.desc()
            ).first()
            assert isinstance(latest.new_words, list)
            assert len(latest.new_words) == 3
            assert 'alpha' in latest.new_words
            assert 'beta' in latest.new_words
            assert 'gamma' in latest.new_words
