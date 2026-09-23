"""Integration-style tests for ProcessingSystem + worker pool."""

from datetime import datetime, timedelta

from mds.core.clock import FakeClock
from mds.core.job import Job
from mds.domain.models import Message, Minibatch, FileBucket
from mds.minibatch.policies import TimeWindowPolicy
from mds.system.processing_system import ProcessingSystem
from mds.workers.pool import RecordingWorkerPool, ThreadWorkerPool
from tests.mocks import MockFileSource, MockMessageSource, make_files

MB = 1024 * 1024


def test_processing_system_submits_minibatches_and_buckets():
    start = datetime(2026, 1, 1)
    clock = FakeClock(start)
    msg_src = MockMessageSource()
    file_src = MockFileSource(make_files([4 * MB, 4 * MB, 3 * MB]))
    pool = RecordingWorkerPool()

    system = ProcessingSystem(
        message_source=msg_src,
        file_source=file_src,
        worker_pool=pool,
        minibatch_policy=TimeWindowPolicy(window=timedelta(minutes=5)),
        clock=clock,
    )

    system.minibatch_assembler.ingest(Message(payload="x", timestamp=start))
    clock.advance(timedelta(minutes=5))
    system.minibatch_assembler.tick()

    system.process_nightly_files()

    payloads = [j.payload for j in pool.submitted]
    assert any(isinstance(p, Minibatch) for p in payloads)
    assert any(isinstance(p, FileBucket) for p in payloads)


def test_thread_worker_pool_processes_jobs():
    results = []

    def handler(payload):
        results.append(payload)
        return payload

    pool = ThreadWorkerPool(handler=handler, max_workers=10)
    futures = [pool.submit(Job(payload=i)) for i in range(5)]
    for f in futures:
        f.result(timeout=2)
    pool.shutdown(wait=True)
    assert sorted(results) == [0, 1, 2, 3, 4]
