"""Assembles minibatches without blocking on worker completion (SRP)."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Callable, List, Optional

from mds.core.clock import Clock, SystemClock
from mds.domain.models import Message, Minibatch
from mds.minibatch.policies import MinibatchPolicy, TimeWindowPolicy
from mds.sources.interfaces import MessageSource


class MinibatchAssembler:
    """
    Opens a minibatch on the first message, keeps collecting until the policy
    says close, then hands the batch to `on_ready` and immediately starts the
    next batch.

    ``on_ready`` must be non-blocking (e.g. submit to a worker pool). The
    assembler never waits for job completion before opening the next batch.
    """

    def __init__(
        self,
        source: MessageSource,
        on_ready: Callable[[Minibatch], None],
        policy: MinibatchPolicy | None = None,
        clock: Clock | None = None,
        poll_interval: float = 0.05,
    ) -> None:
        self._source = source
        self._on_ready = on_ready
        self._policy = policy or TimeWindowPolicy()
        self._clock = clock or SystemClock()
        self._poll_interval = poll_interval
        self._current: Optional[Minibatch] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.completed_batches: List[Minibatch] = []

    # --- synchronous API (preferred in tests) ---

    def ingest(self, message: Message) -> Optional[Minibatch]:
        """Accept one message; return a closed batch if the policy fires after ingest."""
        closed = None
        with self._lock:
            if self._current is None:
                self._current = Minibatch(messages=[message], opened_at=message.timestamp)
            else:
                self._current.messages.append(message)
            if self._policy.should_close(self._current, self._clock.now()):
                closed = self._detach_locked(self._clock.now())
        if closed is not None:
            self._emit(closed)
        return closed

    def tick(self) -> Optional[Minibatch]:
        """
        Check whether the open batch should close at the current clock time.
        Useful with FakeClock after advancing time without new messages.
        """
        with self._lock:
            if self._current is None:
                return None
            if not self._policy.should_close(self._current, self._clock.now()):
                return None
            closed = self._detach_locked(self._clock.now())
        self._emit(closed)
        return closed

    def pump_once(self) -> Optional[Minibatch]:
        """Pull one message from the source (if any), then evaluate close policy."""
        msg = self._source.receive(timeout=self._poll_interval)
        closed = None
        if msg is not None:
            closed = self.ingest(msg)
        maybe = self.tick()
        return closed or maybe

    def flush(self) -> Optional[Minibatch]:
        """Force-close the open batch (e.g. on shutdown)."""
        with self._lock:
            if self._current is None:
                return None
            closed = self._detach_locked(self._clock.now())
        self._emit(closed)
        return closed

    # --- threaded runner for live sources ---

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="minibatch-assembler", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        while not self._stop.is_set():
            self.pump_once()

    def _detach_locked(self, now: datetime) -> Minibatch:
        batch = self._current
        assert batch is not None
        batch.closed_at = now
        self._current = None
        return batch

    def _emit(self, batch: Minibatch) -> None:
        self.completed_batches.append(batch)
        self._on_ready(batch)

    @property
    def current(self) -> Optional[Minibatch]:
        with self._lock:
            return self._current
