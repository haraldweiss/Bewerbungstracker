"""Smoke-Test-Handler. Schläft x Sekunden, returnt {ok: True}."""
import time
from services.tasks.registry import register


@register('test_noop')
def handle_test_noop(payload: dict, *, progress_cb=None) -> dict:
    duration = float(payload.get('sleep_seconds', 0.1))
    if progress_cb:
        progress_cb(0, 'starting')
    time.sleep(duration)
    if progress_cb:
        progress_cb(100, 'done')
    return {'ok': True, 'slept': duration}
