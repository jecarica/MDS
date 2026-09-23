"""Tests for domain models."""

import pytest

from mds.domain.models import DataFile, FileBucket, Message, Minibatch
from datetime import datetime


def test_data_file_rejects_negative_size():
    with pytest.raises(ValueError):
        DataFile(name="bad", size_bytes=-1)


def test_file_bucket_used_and_remaining():
    files = [
        DataFile(name="a", size_bytes=3_000_000),
        DataFile(name="b", size_bytes=2_000_000),
    ]
    bucket = FileBucket(files=files, capacity_bytes=10_000_000)
    assert bucket.used_bytes == 5_000_000
    assert bucket.remaining_bytes == 5_000_000


def test_minibatch_size():
    now = datetime(2026, 1, 1)
    batch = Minibatch(
        messages=[Message(payload=1, timestamp=now), Message(payload=2, timestamp=now)],
        opened_at=now,
    )
    assert batch.size == 2
