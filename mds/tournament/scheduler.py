"""
Weekly game-night seating scheduler

Constraints
-----------
- N participants, T tables, G seats per table (capacity C = T * G each round).
- Every round all T tables are used (requires N >= C, or we pad with byes carefully —
  here we require N >= C and rotate who sits out when N > C).
- Each table produces one winner.
- Goal (1): produce an overall tournament champion via successive winner brackets.
- Goal (2): among non-champions / losers, maximize diversity of co-players.

Approach (heuristic, extensible)
--------------------------------
1. **Swiss-style diversity rounds**: repeatedly seat active/non-eliminated players
   maximizing new pairwise meetings (greedy: least-recently-paired).
2. **Elimination ladder**: winners from a full "championship slate" of tables feed
   a knockout until one champion remains. Losers re-enter diversity seating until
   the champion is crowned.

The `SeatingStrategy` ABC allows swapping the pairing heuristic (OCP).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class Player:
    player_id: int
    name: str


@dataclass
class TableAssignment:
    table_index: int
    players: List[Player]
    winner: Optional[Player] = None


@dataclass
class Round:
    round_index: int
    tables: List[TableAssignment]
    sit_outs: List[Player] = field(default_factory=list)
    kind: str = "diversity"  # or "championship"


@dataclass
class TournamentResult:
    rounds: List[Round]
    champion: Optional[Player]
    pairwise_meetings: Dict[Tuple[int, int], int]

    def unique_partners(self, player_id: int) -> int:
        partners: Set[int] = set()
        for (a, b), count in self.pairwise_meetings.items():
            if count <= 0:
                continue
            if a == player_id:
                partners.add(b)
            elif b == player_id:
                partners.add(a)
        return len(partners)


class SeatingStrategy(ABC):
    """How to assign players to tables for one round."""

    @abstractmethod
    def seat(
        self,
        players: List[Player],
        tables: int,
        seats_per_table: int,
        meeting_counts: Dict[Tuple[int, int], int],
    ) -> Tuple[List[TableAssignment], List[Player]]:
        """Return (table assignments, sit-outs). All tables must be filled."""


def _pair_key(a: int, b: int) -> Tuple[int, int]:
    return (a, b) if a < b else (b, a)


class GreedyDiversitySeating(SeatingStrategy):
    """
    Fill tables greedily: pick the unused player who adds the least prior
    meeting-weight with the current table, preferring never-met partners.
    """

    def seat(
        self,
        players: List[Player],
        tables: int,
        seats_per_table: int,
        meeting_counts: Dict[Tuple[int, int], int],
    ) -> Tuple[List[TableAssignment], List[Player]]:
        capacity = tables * seats_per_table
        if len(players) < capacity:
            raise ValueError(
                f"Need at least {capacity} players to fill {tables} tables of {seats_per_table}"
            )

        # Rotate sit-outs: those with most unique partners so far sit out first
        # (approximation: fewest meetings sit out last → they keep playing).
        ordered = sorted(
            players,
            key=lambda p: sum(
                meeting_counts.get(_pair_key(p.player_id, o.player_id), 0) for o in players
            ),
        )
        active = ordered[:capacity]
        sit_outs = ordered[capacity:]

        remaining = list(active)
        assignments: List[TableAssignment] = []

        for t in range(tables):
            table: List[Player] = []
            # Seed with the player who has the fewest total meetings.
            remaining.sort(
                key=lambda p: sum(
                    meeting_counts.get(_pair_key(p.player_id, o.player_id), 0) for o in remaining
                )
            )
            table.append(remaining.pop(0))

            while len(table) < seats_per_table:
                def cost(candidate: Player) -> Tuple[int, int]:
                    weight = sum(
                        meeting_counts.get(_pair_key(candidate.player_id, m.player_id), 0)
                        for m in table
                    )
                    # secondary: prefer lower id for determinism
                    return (weight, candidate.player_id)

                remaining.sort(key=cost)
                table.append(remaining.pop(0))

            assignments.append(TableAssignment(table_index=t, players=table))

        return assignments, sit_outs


class GameNightScheduler:
    """
    Builds a full schedule that (1) crowns a champion and (2) diversifies seating.

    Winner selection is injected (`pick_winner`) so simulations/tests stay
    deterministic without modelling skill.
    """

    def __init__(
        self,
        n_participants: int,
        tables: int,
        seats_per_table: int,
        seating: SeatingStrategy | None = None,
        pick_winner=None,
        max_diversity_rounds: int = 20,
    ) -> None:
        if n_participants < 1 or tables < 1 or seats_per_table < 2:
            raise ValueError("Invalid tournament parameters")
        self.n = n_participants
        self.tables = tables
        self.g = seats_per_table
        self.capacity = tables * seats_per_table
        if n_participants < self.capacity:
            raise ValueError(
                f"N={n_participants} cannot fill T*G={self.capacity} seats each round"
            )
        self._seating = seating or GreedyDiversitySeating()
        self._pick_winner = pick_winner or (lambda players: players[0])
        self._max_diversity = max_diversity_rounds
        self.players = [Player(i, f"P{i}") for i in range(n_participants)]

    def run(self) -> TournamentResult:
        meetings: Dict[Tuple[int, int], int] = {}
        rounds: List[Round] = []
        round_idx = 0

        # Phase A — diversity rounds for the full field
        for _ in range(self._max_diversity):
            tables, sit_outs = self._seating.seat(
                self.players, self.tables, self.g, meetings
            )
            self._play_tables(tables, meetings)
            rounds.append(Round(round_idx, tables, sit_outs, kind="diversity"))
            round_idx += 1

        # Phase B — championship: keep winners until one remains
        contenders = list(self.players)
        while len(contenders) > 1:
            # If too many contenders, fill leftover seats with lowest-meeting losers
            # so all tables stay used.
            pool = list(contenders)
            if len(pool) < self.capacity:
                extras = [p for p in self.players if p not in pool]
                extras.sort(
                    key=lambda p: sum(
                        meetings.get(_pair_key(p.player_id, o.player_id), 0) for o in pool
                    )
                )
                pool.extend(extras[: self.capacity - len(pool)])

            tables, sit_outs = self._seating.seat(pool, self.tables, self.g, meetings)
            winners = self._play_tables(tables, meetings)
            rounds.append(Round(round_idx, tables, sit_outs, kind="championship"))
            round_idx += 1

            # Contenders for next championship slate = winners who were already contenders
            contender_ids = {p.player_id for p in contenders}
            contenders = [w for w in winners if w.player_id in contender_ids]
            if not contenders:
                contenders = winners[:1]
            if len(contenders) == 1:
                break
            # Prevent infinite loops on awkward sizes
            if round_idx > self._max_diversity + 50:
                break

        champion = contenders[0] if contenders else None
        return TournamentResult(rounds=rounds, champion=champion, pairwise_meetings=meetings)

    def _play_tables(
        self,
        tables: List[TableAssignment],
        meetings: Dict[Tuple[int, int], int],
    ) -> List[Player]:
        winners: List[Player] = []
        for assignment in tables:
            for a, b in combinations(assignment.players, 2):
                key = _pair_key(a.player_id, b.player_id)
                meetings[key] = meetings.get(key, 0) + 1
            winner = self._pick_winner(assignment.players)
            assignment.winner = winner
            winners.append(winner)
        return winners
