"""Task-Handler Registry. Handler werden via @register('type') registriert."""
from __future__ import annotations
from typing import Callable

HANDLERS: dict[str, Callable] = {}


def register(task_type: str):
    def decorator(fn: Callable) -> Callable:
        HANDLERS[task_type] = fn
        return fn
    return decorator


def get_handler(task_type: str) -> Callable:
    if task_type not in HANDLERS:
        raise KeyError(f"No handler registered for task type {task_type!r}")
    return HANDLERS[task_type]
