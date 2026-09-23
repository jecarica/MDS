"""Nightly file gatherer with exponentially distributed sizes."""

from __future__ import annotations

import math
import random
from typing import List

from mds.domain.models import DataFile
from mds.sources.interfaces import FileSource

MB = 1024 * 1024


class NightlyFileSource(FileSource):
    """
    Gathers a fixed count of files whose sizes follow Exp(mean).

    Default: 100 files, mean size 2 MB (so many fit under a 10 MB bucket).
    """

    def __init__(
        self,
        file_count: int = 100,
        mean_size_bytes: float = 2 * MB,
        rng: random.Random | None = None,
        name_prefix: str = "nightly",
    ) -> None:
        if file_count < 0:
            raise ValueError("file_count must be non-negative")
        if mean_size_bytes <= 0:
            raise ValueError("mean_size_bytes must be positive")
        self._file_count = file_count
        self._mean_size = mean_size_bytes
        self._rng = rng or random.Random()
        self._name_prefix = name_prefix

    def _sample_size(self) -> int:
        u = max(self._rng.random(), 1e-12)
        size = int(-math.log(u) * self._mean_size)
        return max(size, 1)

    def gather(self) -> List[DataFile]:
        files: List[DataFile] = []
        for i in range(self._file_count):
            size = self._sample_size()
            files.append(
                DataFile(
                    name=f"{self._name_prefix}_{i:03d}.dat",
                    size_bytes=size,
                    content=b"\0" * min(size, 64),  # stub content for mocks
                )
            )
        return files
