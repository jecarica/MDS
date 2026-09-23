"""Tests for file bucketing strategies and assembler."""

import random

from mds.bucketing.assembler import FileBucketAssembler
from mds.bucketing.strategies import (
    DEFAULT_BUCKET_CAPACITY,
    FirstFitDecreasingStrategy,
    NextFitStrategy,
)
from mds.sources.nightly_file_source import NightlyFileSource
from tests.mocks import MockFileSource, make_files

MB = 1024 * 1024


def test_first_fit_decreasing_packs_under_capacity():
    files = make_files([4 * MB, 4 * MB, 3 * MB, 3 * MB, 2 * MB])
    buckets = FirstFitDecreasingStrategy().pack(files, capacity_bytes=10 * MB)

    assert all(b.used_bytes <= b.capacity_bytes or len(b.files) == 1 for b in buckets)
    packed = sum(len(b.files) for b in buckets)
    assert packed == len(files)
    # 4+4+2 and 3+3 fit → ideally 2 buckets
    assert len(buckets) == 2


def test_next_fit_is_swappable():
    files = make_files([6 * MB, 6 * MB, 3 * MB])
    ffd = FirstFitDecreasingStrategy().pack(files, 10 * MB)
    nxt = NextFitStrategy().pack(files, 10 * MB)
    # Both valid; NextFit may use more buckets depending on order
    assert sum(len(b.files) for b in ffd) == 3
    assert sum(len(b.files) for b in nxt) == 3


def test_oversized_file_gets_own_bucket():
    files = make_files([12 * MB, 1 * MB])
    buckets = FirstFitDecreasingStrategy().pack(files, 10 * MB)
    assert any(b.used_bytes == 12 * MB for b in buckets)


def test_file_bucket_assembler_uses_strategy_and_callback():
    files = make_files([3 * MB, 3 * MB, 3 * MB, 3 * MB])
    source = MockFileSource(files)
    ready = []

    assembler = FileBucketAssembler(
        source=source,
        on_ready=ready.append,
        strategy=FirstFitDecreasingStrategy(),
        capacity_bytes=10 * MB,
    )
    buckets = assembler.run_once()

    assert source.gather_calls == 1
    assert buckets == ready
    assert all(b.used_bytes <= 10 * MB for b in buckets)


def test_strategy_can_be_replaced_at_runtime():
    files = make_files([5 * MB, 5 * MB, 5 * MB])
    source = MockFileSource(files)
    assembler = FileBucketAssembler(
        source=source,
        on_ready=lambda _: None,
        strategy=FirstFitDecreasingStrategy(),
        capacity_bytes=10 * MB,
    )
    assembler.strategy = NextFitStrategy()
    assert isinstance(assembler.strategy, NextFitStrategy)
    buckets = assembler.run_once()
    assert sum(len(b.files) for b in buckets) == 3


def test_nightly_file_source_exponential_sizes():
    src = NightlyFileSource(file_count=100, mean_size_bytes=2 * MB, rng=random.Random(0))
    files = src.gather()
    assert len(files) == 100
    assert all(f.size_bytes >= 1 for f in files)
    mean = sum(f.size_bytes for f in files) / len(files)
    # rough sanity: mean of Exp(2MB) samples should be in a broad band
    assert 0.5 * MB < mean < 5 * MB


def test_default_bucket_capacity_is_10mb():
    assert DEFAULT_BUCKET_CAPACITY == 10 * MB
