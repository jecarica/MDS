# MDS — Message & File Processing System

OOP model of a dual-pipeline data processing system:

1. **Streaming messages** arrive ~Poisson(10/min). Minibatches open on the first message, collect for **5 minutes**, then go to a **10-thread** worker pool. Forming the next minibatch does **not** wait for the previous job to finish.
2. **Nightly files** (~100, exponential sizes) are packed into **~10 MB buckets** before the same worker pool. The bucketing algorithm is a swappable **Strategy**.

Designed for extension and maintainability (SOLID).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Run tests

```bash
pytest tests/ -v
```

Mocks for sources live in `tests/mocks.py` (`MockMessageSource`, `TimedMockMessageSource`, `MockFileSource`).

## Quick start

```python
from datetime import timedelta

from mds.bucketing import FirstFitDecreasingStrategy, NextFitStrategy
from mds.minibatch import TimeWindowPolicy
from mds.sources import NightlyFileSource, PoissonMessageSource
from mds.system import ProcessingSystem

system = ProcessingSystem(
    message_source=PoissonMessageSource(rate_per_minute=10.0),
    file_source=NightlyFileSource(file_count=100),
    minibatch_policy=TimeWindowPolicy(window=timedelta(minutes=5)),
    bucketing_strategy=FirstFitDecreasingStrategy(),  # or NextFitStrategy()
)

system.start_message_pipeline()
system.process_nightly_files()   # gather → bucket → submit
# ...
system.shutdown()
```

Inject a custom `WorkerPool`, `Clock`, or job handler via `ProcessingSystem(...)` for production wiring or tests (`FakeClock`, `RecordingWorkerPool`).

## Package layout

```
mds/
  domain/       Message, Minibatch, DataFile, FileBucket
  sources/      MessageSource / FileSource + Poisson & nightly emitters
  minibatch/    Assembler + open/close policies (time window, max count, …)
  bucketing/    BucketingStrategy + FirstFitDecreasing / NextFit
  workers/      ThreadWorkerPool (10 threads) + test double
  system/       ProcessingSystem orchestrator
  tournament/   Bonus: weekly game-night seating scheduler
  core/         Clock, Job
tests/
  mocks.py
  test_*.py
```

## Design notes (SOLID)

| Principle | Application |
|-----------|-------------|
| **S**ingle responsibility | Sources emit; assemblers batch; pool executes; system only wires |
| **O**pen/closed | New policies/strategies without editing assemblers |
| **L**iskov | Any `MessageSource` / `FileSource` / strategy is interchangeable |
| **I**nterface segregation | Small ports (`receive`, `gather`, `pack`, `submit`) |
| **D**ependency inversion | Orchestrator depends on abstractions, not Poisson/nightly concretes |

**Non-blocking minibatches:** `MinibatchAssembler` calls `on_ready` which only *submits* a `Job` to the pool. The assembler never waits on futures, so the next window can open immediately.

**Swappable bucketing:** implement `BucketingStrategy.pack(files, capacity_bytes)` and pass it in (or set `file_assembler.strategy = ...` at runtime).

## Bonus — game-night tournament

`mds.tournament.GameNightScheduler` builds a schedule for **N** players, **T** tables, **G** seats/table:

- every round uses all tables (sit-outs when `N > T·G`);
- greedy diversity seating maximizes new co-players;
- championship phase narrows winners until one champion remains.

```python
from mds.tournament import GameNightScheduler

result = GameNightScheduler(
    n_participants=12,
    tables=3,
    seats_per_table=4,
    max_diversity_rounds=5,
).run()

print(result.champion, len(result.rounds))
```

Seating heuristics implement `SeatingStrategy` and can be replaced independently of the tournament loop.
