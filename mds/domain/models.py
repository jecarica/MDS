"""Domain models for the processing system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional
from uuid import uuid4


@dataclass(frozen=True)
class Message:
    """A single inbound message from a data source."""

    payload: Any
    timestamp: datetime
    message_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class DataFile:
    """A file gathered for nightly processing."""

    name: str
    size_bytes: int
    content: Optional[bytes] = None
    file_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")


@dataclass
class Minibatch:
    """A time-window collection of messages ready for processing."""

    messages: List[Message]
    opened_at: datetime
    closed_at: Optional[datetime] = None
    minibatch_id: str = field(default_factory=lambda: str(uuid4()))

    @property
    def size(self) -> int:
        return len(self.messages)


@dataclass
class FileBucket:
    """A packed collection of files sized for efficient worker processing."""

    files: List[DataFile]
    capacity_bytes: int
    bucket_id: str = field(default_factory=lambda: str(uuid4()))

    @property
    def used_bytes(self) -> int:
        return sum(f.size_bytes for f in self.files)

    @property
    def remaining_bytes(self) -> int:
        return self.capacity_bytes - self.used_bytes
