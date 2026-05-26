"""Lädt alle Handler-Module → triggert Registrierung via @register."""
from services.tasks.handlers import test_noop  # noqa: F401
from services.tasks.handlers import email_import  # noqa: F401
from services.tasks.handlers import claude_match_bulk  # noqa: F401
from services.tasks.handlers import pattern_learner_train  # noqa: F401
from services.tasks.handlers import cron_crawl_source  # noqa: F401
from services.tasks.handlers import cron_prefilter  # noqa: F401
from services.tasks.handlers import cron_claude_match  # noqa: F401
from services.tasks.handlers import cron_notify  # noqa: F401
from services.tasks.handlers import cron_cleanup  # noqa: F401
from services.tasks.handlers import cron_url_health_check  # noqa: F401
