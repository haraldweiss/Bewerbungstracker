import pytest
from services.tasks.registry import register, HANDLERS, get_handler


def test_register_decorator_adds_to_registry():
    @register('foo')
    def handler(payload, *, progress_cb=None):
        return {'ok': True}
    assert HANDLERS['foo'] is handler
    assert get_handler('foo') is handler


def test_get_handler_unknown_type_raises():
    with pytest.raises(KeyError):
        get_handler('nonexistent_xyz')
