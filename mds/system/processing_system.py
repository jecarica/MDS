"""Top-level orchestrator composing message + file pipelines (SRP for wiring)."""

from __future__ import annotations

from typing import Any, Callable, Optional

from mds.bucketing.assembler import FileBucketAssembler
from mds.bucketing.strategies import DEFAULT_BUCKET_CAPACITY, BucketingStrategy
from mds.core.clock import Clock, SystemClock
from mds.core.job import Job
from mds.domain.models import FileBucket, Minibatch
from mds.minibatch.assembler import MinibatchAssembler
from mds.minibatch.policies import MinibatchPolicy, TimeWindowPolicy
from mds.sources.interfaces import FileSource, MessageSource
from mds.workers.pool import ThreadWorkerPool, WorkerPool


def default_minibatch_handler(batch: Minibatch) -> Any:
    return {"type": "minibatch", "id": batch.minibatch_id, "count": batch.size}


def default_bucket_handler(bucket: FileBucket) -> Any:
    return {
        "type": "bucket",
        "id": bucket.bucket_id,
        "files": len(bucket.files),
        "used_bytes": bucket.used_bytes,
    }


class ProcessingSystem:
    """
    Runs message minibatching and nightly file bucketing in parallel.

    Both pipelines submit to the same worker pool; minibatch creation never waits
    for prior job completion.
    """

    def __init__(
        self,
        message_source: MessageSource,
        file_source: FileSource,
        worker_pool: WorkerPool | None = None,
        minibatch_policy: MinibatchPolicy | None = None,
        bucketing_strategy: BucketingStrategy | None = None,
        bucket_capacity_bytes: int = DEFAULT_BUCKET_CAPACITY,
        clock: Clock | None = None,
        job_handler: Optional[Callable[[Any], Any]] = None,
    ) -> None:
        self._clock = clock or SystemClock()
        handler = job_handler or self._dispatch
        self._pool = worker_pool or ThreadWorkerPool(handler=handler, max_workers=10)

        self._minibatch_assembler = MinibatchAssembler(
            source=message_source,
            on_ready=self._submit_minibatch,
            policy=minibatch_policy or TimeWindowPolicy(),
            clock=self._clock,
        )
        self._file_assembler = FileBucketAssembler(
            source=file_source,
            on_ready=self._submit_bucket,
            strategy=bucketing_strategy,
            capacity_bytes=bucket_capacity_bytes,
        )

    def _dispatch(self, payload: Any) -> Any:
        if isinstance(payload, Minibatch):
            return default_minibatch_handler(payload)
        if isinstance(payload, FileBucket):
            return default_bucket_handler(payload)
        return payload

    def _submit_minibatch(self, batch: Minibatch) -> None:
        # Non-blocking submit — assembler continues immediately.
        self._pool.submit(Job(payload=batch))

    def _submit_bucket(self, bucket: FileBucket) -> None:
        self._pool.submit(Job(payload=bucket))

    def start_message_pipeline(self) -> None:
        self._minibatch_assembler.start()

    def stop_message_pipeline(self, flush: bool = True) -> None:
        self._minibatch_assembler.stop()
        if flush:
            self._minibatch_assembler.flush()

    def process_nightly_files(self) -> None:
        """Gather + bucket + submit once (nightly job)."""
        self._file_assembler.run_once()

    def shutdown(self, wait: bool = True) -> None:
        self.stop_message_pipeline(flush=True)
        self._pool.shutdown(wait=wait)

    @property
    def worker_pool(self) -> WorkerPool:
        return self._pool

    @property
    def minibatch_assembler(self) -> MinibatchAssembler:
        return self._minibatch_assembler

    @property
    def file_assembler(self) -> FileBucketAssembler:
        return self._file_assembler
