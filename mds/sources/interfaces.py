"""Data source abstractions (ISP / DIP)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, List, Optional

from mds.domain.models import DataFile, Message


class MessageSource(ABC):
    """Produces inbound messages. Implementations may be live or mocked."""

    @abstractmethod
    def receive(self, timeout: Optional[float] = None) -> Optional[Message]:
        """Return next message, or None if none available within timeout."""

    def close(self) -> None:
        """Release resources. Default no-op."""


class IterableMessageSource(MessageSource):
    """Adapter: wrap an iterator as a MessageSource."""

    def __init__(self, messages: Iterator[Message]) -> None:
        self._messages = messages
        self._exhausted = False

    def receive(self, timeout: Optional[float] = None) -> Optional[Message]:
        if self._exhausted:
            return None
        try:
            return next(self._messages)
        except StopIteration:
            self._exhausted = True
            return None


class FileSource(ABC):
    """Produces files for batch processing (e.g. nightly gather)."""

    @abstractmethod
    def gather(self) -> List[DataFile]:
        """Collect the current set of files ready for processing."""
