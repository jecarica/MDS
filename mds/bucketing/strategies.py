"""Bucketing strategy abstraction (Strategy + OCP)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from mds.domain.models import DataFile, FileBucket

MB = 1024 * 1024
DEFAULT_BUCKET_CAPACITY = 10 * MB


class BucketingStrategy(ABC):
    """Packs files into buckets. Concrete algorithms are interchangeable."""

    @abstractmethod
    def pack(self, files: List[DataFile], capacity_bytes: int) -> List[FileBucket]:
        ...


class FirstFitDecreasingStrategy(BucketingStrategy):
    """
    Sort files largest-first, place each into the first bucket that fits.
    Simple and good enough; swap freely for NextFit / BestFit / etc.
    """

    def pack(self, files: List[DataFile], capacity_bytes: int) -> List[FileBucket]:
        if capacity_bytes <= 0:
            raise ValueError("capacity_bytes must be positive")

        ordered = sorted(files, key=lambda f: f.size_bytes, reverse=True)
        buckets: List[FileBucket] = []

        for f in ordered:
            if f.size_bytes > capacity_bytes:
                # Oversized file gets its own overflowing bucket (explicit, not silent drop).
                buckets.append(FileBucket(files=[f], capacity_bytes=capacity_bytes))
                continue

            placed = False
            for bucket in buckets:
                if bucket.remaining_bytes >= f.size_bytes:
                    bucket.files.append(f)
                    placed = True
                    break
            if not placed:
                buckets.append(FileBucket(files=[f], capacity_bytes=capacity_bytes))

        return buckets


class NextFitStrategy(BucketingStrategy):
    """Fill current bucket; open a new one when the file does not fit."""

    def pack(self, files: List[DataFile], capacity_bytes: int) -> List[FileBucket]:
        if capacity_bytes <= 0:
            raise ValueError("capacity_bytes must be positive")

        buckets: List[FileBucket] = []
        current: FileBucket | None = None

        for f in files:
            if f.size_bytes > capacity_bytes:
                buckets.append(FileBucket(files=[f], capacity_bytes=capacity_bytes))
                current = None
                continue

            if current is None or current.remaining_bytes < f.size_bytes:
                current = FileBucket(files=[f], capacity_bytes=capacity_bytes)
                buckets.append(current)
            else:
                current.files.append(f)

        return buckets
