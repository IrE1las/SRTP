"""Request-local simulation clock. Free simulation keeps the real clock."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import time as _time

_epoch = ContextVar('simulation_epoch', default=None)
_offset = _time.time() - _time.monotonic()


def time():
    value = _epoch.get()
    return _time.time() if value is None else value


def monotonic():
    value = _epoch.get()
    # Use the virtual epoch directly, avoiding a lossy large-offset round trip.
    return _time.monotonic() if value is None else value


def iso():
    return datetime.fromtimestamp(time(), timezone.utc).isoformat()


@contextmanager
def at(value):
    if isinstance(value, datetime):
        value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        value = value.timestamp()
    token = _epoch.set(float(value))
    try:
        yield
    finally:
        _epoch.reset(token)
