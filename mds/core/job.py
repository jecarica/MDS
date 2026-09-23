"""Work unit submitted to a worker pool."""

from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar
from uuid import uuid4

T = TypeVar("T")

JobHandler = Callable[[Any], Any]


class Job(Generic[T]):
    """Unit of work submitted to a worker pool."""

    def __init__(self, payload: T, job_id: str | None = None) -> None:
        self.payload = payload
        self.job_id = job_id or str(uuid4())
