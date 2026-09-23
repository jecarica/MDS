"""Reusable mocks / fakes for message and file sources."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Sequence

from mds.domain.models import DataFile, Message
from mds.sources.interfaces import FileSource, MessageSource


class MockMessageSource(MessageSource):
    """
    Deterministic queue of messages with optional timestamps.

    If `auto_timestamps` is True and a message has a placeholder time, timestamps
    are assigned sequentially from `start` with `interval`.
    """

    def __init__(
        self,
        messages: Sequence[Message] | None = None,
        payloads: Sequence | None = None,
        start: datetime | None = None,
        interval: timedelta = timedelta(seconds=1),
    ) -> None:
        self._queue: List[Message] = list(messages or [])
        if payloads is not None:
            t0 = start or datetime(2026, 1, 1)
            for i, payload in enumerate(payloads):
                self._queue.append(Message(payload=payload, timestamp=t0 + i * interval))
        self._index = 0
        self.receive_calls = 0
        self.closed = False

    def receive(self, timeout: Optional[float] = None) -> Optional[Message]:
        self.receive_calls += 1
        if self.closed or self._index >= len(self._queue):
            return None
        msg = self._queue[self._index]
        self._index += 1
        return msg

    def close(self) -> None:
        self.closed = True

    def remaining(self) -> int:
        return max(0, len(self._queue) - self._index)


class TimedMockMessageSource(MessageSource):
    """
    Emits pre-scheduled messages only when `clock.now()` reaches their timestamp.
    Ideal for testing time-window minibatch policies with FakeClock.
    """

    def __init__(self, messages: Sequence[Message], clock) -> None:
        self._messages = sorted(messages, key=lambda m: m.timestamp)
        self._clock = clock
        self._index = 0

    def receive(self, timeout: Optional[float] = None) -> Optional[Message]:
        if self._index >= len(self._messages):
            if timeout:
                self._clock.sleep(timeout)
            return None

        next_msg = self._messages[self._index]
        now = self._clock.now()
        wait = (next_msg.timestamp - now).total_seconds()

        if wait > 0:
            if timeout is not None and wait > timeout:
                self._clock.sleep(timeout)
                return None
            self._clock.sleep(wait)

        self._index += 1
        return next_msg


class MockFileSource(FileSource):
    """Returns a fixed list of files (optionally regenerating each gather)."""

    def __init__(self, files: Sequence[DataFile], copy_on_gather: bool = True) -> None:
        self._files = list(files)
        self.gather_calls = 0
        self._copy = copy_on_gather

    def gather(self) -> List[DataFile]:
        self.gather_calls += 1
        if self._copy:
            return list(self._files)
        return self._files


def make_files(sizes_bytes: Sequence[int], prefix: str = "f") -> List[DataFile]:
    return [
        DataFile(name=f"{prefix}{i}", size_bytes=size) for i, size in enumerate(sizes_bytes)
    ]
