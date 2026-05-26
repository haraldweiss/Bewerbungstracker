"""Lädt alle Handler-Module → triggert Registrierung via @register."""
from services.tasks.handlers import test_noop  # noqa: F401
from services.tasks.handlers import email_import  # noqa: F401
from services.tasks.handlers import claude_match_bulk  # noqa: F401
