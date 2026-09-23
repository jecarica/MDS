"""File bucket assembler — depends on BucketingStrategy abstraction (DIP)."""

from __future__ import annotations

from typing import Callable, List

from mds.bucketing.strategies import (
    DEFAULT_BUCKET_CAPACITY,
    BucketingStrategy,
    FirstFitDecreasingStrategy,
)
from mds.domain.models import DataFile, FileBucket
from mds.sources.interfaces import FileSource


class FileBucketAssembler:
    """
    Gathers files from a FileSource and packs them via an injectable strategy.
    Changing packing behaviour means swapping the strategy only.
    """

    def __init__(
        self,
        source: FileSource,
        on_ready: Callable[[FileBucket], None],
        strategy: BucketingStrategy | None = None,
        capacity_bytes: int = DEFAULT_BUCKET_CAPACITY,
    ) -> None:
        self._source = source
        self._on_ready = on_ready
        self._strategy = strategy or FirstFitDecreasingStrategy()
        self._capacity = capacity_bytes
        self.last_buckets: List[FileBucket] = []

    @property
    def strategy(self) -> BucketingStrategy:
        return self._strategy

    @strategy.setter
    def strategy(self, value: BucketingStrategy) -> None:
        self._strategy = value

    def run_once(self) -> List[FileBucket]:
        files: List[DataFile] = self._source.gather()
        buckets = self._strategy.pack(files, self._capacity)
        self.last_buckets = buckets
        for bucket in buckets:
            self._on_ready(bucket)
        return buckets
