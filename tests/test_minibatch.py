"""Tests for minibatch assembly and policies."""

from datetime import datetime, timedelta

from mds.core.clock import FakeClock
from mds.domain.models import Message, Minibatch
from mds.minibatch.assembler import MinibatchAssembler
from mds.minibatch.policies import MaxCountPolicy, TimeWindowPolicy
from mds.workers.pool import RecordingWorkerPool
from mds.core.job import Job
from tests.mocks import MockMessageSource


def _msg(payload, start: datetime, offset_s: float) -> Message:
    return Message(payload=payload, timestamp=start + timedelta(seconds=offset_s))


def test_time_window_policy():
    start = datetime(2026, 1, 1)
    policy = TimeWindowPolicy(window=timedelta(minutes=5))
    batch = Minibatch(messages=[], opened_at=start)
    assert not policy.should_close(batch, start + timedelta(minutes=4, seconds=59))
    assert policy.should_close(batch, start + timedelta(minutes=5))


def test_assembler_opens_on_first_message_and_closes_after_window():
    start = datetime(2026, 1, 1, 0, 0, 0)
    clock = FakeClock(start)
    ready = []
    source = MockMessageSource()  # unused in sync ingest path

    assembler = MinibatchAssembler(
        source=source,
        on_ready=ready.append,
        policy=TimeWindowPolicy(window=timedelta(minutes=5)),
        clock=clock,
    )

    assembler.ingest(_msg(0, start, 0))
    assembler.ingest(_msg(1, start, 60))
    assembler.ingest(_msg(2, start, 120))
    assert assembler.current is not None
    assert len(ready) == 0

    clock.advance(timedelta(minutes=5))
    closed = assembler.tick()

    assert closed is not None
    assert [m.payload for m in closed.messages] == [0, 1, 2]
    assert closed.opened_at == start
    assert assembler.current is None

    # Next message opens a fresh batch immediately
    assembler.ingest(_msg(3, start, 301))
    assert assembler.current is not None
    assert assembler.current.messages[0].payload == 3


def test_new_minibatch_does_not_wait_for_prior_job():
    """Submitting to the pool returns immediately; next batch can open right away."""
    start = datetime(2026, 1, 1)
    clock = FakeClock(start)
    pool = RecordingWorkerPool()
    submitted_order = []

    def on_ready(batch: Minibatch) -> None:
        submitted_order.append(batch.minibatch_id)
        pool.submit(Job(payload=batch))  # non-blocking relative to processing

    assembler = MinibatchAssembler(
        source=MockMessageSource(),
        on_ready=on_ready,
        policy=TimeWindowPolicy(window=timedelta(minutes=5)),
        clock=clock,
    )

    assembler.ingest(_msg("a", start, 0))
    clock.advance(timedelta(minutes=5))
    first = assembler.tick()
    assert first is not None

    assembler.ingest(_msg("b", start, 301))
    # Window is relative to opened_at (t=301s); clock is already at t=300s.
    clock.advance(timedelta(minutes=5, seconds=2))
    second = assembler.tick()
    assert second is not None

    assert len(pool.submitted) == 2
    assert submitted_order == [first.minibatch_id, second.minibatch_id]
    assert first.minibatch_id != second.minibatch_id


def test_max_count_policy_closes_on_ingest():
    start = datetime(2026, 1, 1)
    clock = FakeClock(start)
    ready = []

    assembler = MinibatchAssembler(
        source=MockMessageSource(),
        on_ready=ready.append,
        policy=MaxCountPolicy(max_messages=2),
        clock=clock,
    )

    assert assembler.ingest(_msg(1, start, 0)) is None
    closed = assembler.ingest(_msg(2, start, 1))
    assert closed is not None
    assert closed.size == 2
    assert len(ready) == 1
