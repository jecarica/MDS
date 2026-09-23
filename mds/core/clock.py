"""Abstractions for clocks (DIP) — injectable for fast deterministic tests."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta


class Clock(ABC):
    """Abstract time source so tests can advance time without sleeping."""

    @abstractmethod
    def now(self) -> datetime:
        ...

    @abstractmethod
    def sleep(self, seconds: float) -> None:
        ...


class SystemClock(Clock):
    """Real wall-clock time."""

    def now(self) -> datetime:
        return datetime.now()

    def sleep(self, seconds: float) -> None:
        import time

        time.sleep(seconds)


class FakeClock(Clock):
    """Deterministic clock for unit tests."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 1, 1, 0, 0, 0)

    def now(self) -> datetime:
        return self._now

    def sleep(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)

    def advance(self, delta: timedelta) -> None:
        self._now += delta
