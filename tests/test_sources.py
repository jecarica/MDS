"""Tests for message sources and mocks."""

from datetime import datetime, timedelta
import random

from mds.core.clock import FakeClock
from mds.sources.poisson_message_source import PoissonMessageSource
from tests.mocks import MockMessageSource, TimedMockMessageSource
from mds.domain.models import Message


def test_mock_message_source_from_payloads():
    src = MockMessageSource(payloads=["a", "b", "c"])
    assert src.receive().payload == "a"
    assert src.receive().payload == "b"
    assert src.receive().payload == "c"
    assert src.receive() is None
    assert src.receive_calls == 4


def test_mock_message_source_close():
    src = MockMessageSource(payloads=[1])
    src.close()
    assert src.receive() is None


def test_timed_mock_respects_clock():
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
    msgs = [
        Message(payload=1, timestamp=datetime(2026, 1, 1, 12, 0, 5)),
        Message(payload=2, timestamp=datetime(2026, 1, 1, 12, 0, 10)),
    ]
    src = TimedMockMessageSource(msgs, clock)

    assert src.receive(timeout=1.0) is None
    assert clock.now() == datetime(2026, 1, 1, 12, 0, 1)

    m1 = src.receive(timeout=10.0)
    assert m1.payload == 1
    assert clock.now() == datetime(2026, 1, 1, 12, 0, 5)


def test_poisson_source_emits_with_fake_clock():
    clock = FakeClock()
    rng = random.Random(42)
    src = PoissonMessageSource(rate_per_minute=60.0, clock=clock, rng=rng)  # ~1/sec

    messages = []
    deadline = clock.now() + timedelta(seconds=5)
    while clock.now() < deadline and len(messages) < 20:
        msg = src.receive(timeout=1.0)
        if msg:
            messages.append(msg)

    assert len(messages) >= 1
    assert all(m.timestamp >= messages[0].timestamp for m in messages)
