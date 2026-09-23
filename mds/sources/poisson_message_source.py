"""Poisson-process message emitter (~λ messages per minute)."""

from __future__ import annotations

import math
import random
from datetime import timedelta
from typing import Optional

from mds.core.clock import Clock, SystemClock
from mds.domain.models import Message
from mds.sources.interfaces import MessageSource


class PoissonMessageSource(MessageSource):
    """
    Emits messages whose inter-arrival times are Exp(λ).

    rate_per_minute ≈ 10 → λ = 10/60 arrivals per second.
    """

    def __init__(
        self,
        rate_per_minute: float = 10.0,
        clock: Clock | None = None,
        rng: random.Random | None = None,
        payload_factory=None,
    ) -> None:
        if rate_per_minute <= 0:
            raise ValueError("rate_per_minute must be positive")
        self._lambda_per_sec = rate_per_minute / 60.0
        self._clock = clock or SystemClock()
        self._rng = rng or random.Random()
        self._payload_factory = payload_factory or (lambda i: {"seq": i})
        self._seq = 0
        self._next_at = self._clock.now()
        self._closed = False
        self._schedule_next()

    def _interarrival(self) -> float:
        # Inverse transform: Exp(λ) → -ln(U)/λ
        u = max(self._rng.random(), 1e-12)
        return -math.log(u) / self._lambda_per_sec

    def _schedule_next(self) -> None:
        self._next_at = self._clock.now() + timedelta(seconds=self._interarrival())

    def receive(self, timeout: Optional[float] = None) -> Optional[Message]:
        if self._closed:
            return None

        now = self._clock.now()
        wait = (self._next_at - now).total_seconds()

        if wait > 0:
            if timeout is not None and wait > timeout:
                self._clock.sleep(timeout)
                return None
            self._clock.sleep(wait)

        msg = Message(payload=self._payload_factory(self._seq), timestamp=self._clock.now())
        self._seq += 1
        self._schedule_next()
        return msg

    def close(self) -> None:
        self._closed = True
