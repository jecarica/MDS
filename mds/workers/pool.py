"""Worker pool abstractions and thread-pool implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, List, Optional

from mds.core.job import Job, JobHandler


class WorkerPool(ABC):
    """Submit jobs for asynchronous processing (ISP — submit / shutdown only)."""

    @abstractmethod
    def submit(self, job: Job) -> Future:
        ...

    @abstractmethod
    def shutdown(self, wait: bool = True) -> None:
        ...


class ThreadWorkerPool(WorkerPool):
    """Fixed-size thread pool (default 10 workers as specified)."""

    def __init__(self, handler: JobHandler, max_workers: int = 10) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        self._handler = handler
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="mds-worker")
        self._futures: List[Future] = []
        self._closed = False

    def submit(self, job: Job) -> Future:
        if self._closed:
            raise RuntimeError("WorkerPool is shut down")
        future = self._executor.submit(self._handler, job.payload)
        self._futures.append(future)
        return future

    def shutdown(self, wait: bool = True) -> None:
        self._closed = True
        self._executor.shutdown(wait=wait)

    @property
    def pending_count(self) -> int:
        return sum(1 for f in self._futures if not f.done())


class RecordingWorkerPool(WorkerPool):
    """Test double: records submitted jobs instead of executing them."""

    def __init__(self, handler: Optional[JobHandler] = None) -> None:
        self.submitted: List[Job] = []
        self._handler = handler
        self._results: List[Any] = []

    def submit(self, job: Job) -> Future:
        self.submitted.append(job)
        future: Future = Future()
        try:
            result = self._handler(job.payload) if self._handler else None
            self._results.append(result)
            future.set_result(result)
        except Exception as exc:  # noqa: BLE001 — surface to caller via Future
            future.set_exception(exc)
        return future

    def shutdown(self, wait: bool = True) -> None:
        return None
