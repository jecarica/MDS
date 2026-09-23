"""Minibatch open/close policies (OCP — swap without changing assembler)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta

from mds.domain.models import Minibatch


class MinibatchPolicy(ABC):
    """Decides when a minibatch should be closed."""

    @abstractmethod
    def should_close(self, batch: Minibatch, now: datetime) -> bool:
        ...


class TimeWindowPolicy(MinibatchPolicy):
    """
    Close the batch `window` after the first message that opened it.

    Matches the requirement: trigger on first message, collect for next N minutes.
    """

    def __init__(self, window: timedelta = timedelta(minutes=5)) -> None:
        if window.total_seconds() <= 0:
            raise ValueError("window must be positive")
        self.window = window

    def should_close(self, batch: Minibatch, now: datetime) -> bool:
        return now >= batch.opened_at + self.window


class MaxCountPolicy(MinibatchPolicy):
    """Optional alternate policy — close when batch reaches a message count."""

    def __init__(self, max_messages: int) -> None:
        if max_messages < 1:
            raise ValueError("max_messages must be >= 1")
        self.max_messages = max_messages

    def should_close(self, batch: Minibatch, now: datetime) -> bool:
        return batch.size >= self.max_messages


class CompositePolicy(MinibatchPolicy):
    """Close when *any* of the child policies says so."""

    def __init__(self, *policies: MinibatchPolicy) -> None:
        if not policies:
            raise ValueError("at least one policy required")
        self._policies = policies

    def should_close(self, batch: Minibatch, now: datetime) -> bool:
        return any(p.should_close(batch, now) for p in self._policies)
