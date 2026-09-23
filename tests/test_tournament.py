"""Tests for the bonus game-night tournament scheduler."""

from mds.tournament.scheduler import GameNightScheduler, GreedyDiversitySeating


def test_scheduler_fills_all_tables_each_round():
    # N=12, T=3, G=4 → full house every round
    sched = GameNightScheduler(
        n_participants=12,
        tables=3,
        seats_per_table=4,
        max_diversity_rounds=3,
        pick_winner=lambda players: players[0],
    )
    result = sched.run()

    assert result.champion is not None
    for rnd in result.rounds:
        assert len(rnd.tables) == 3
        for table in rnd.tables:
            assert len(table.players) == 4
            assert table.winner is not None


def test_scheduler_with_sit_outs_still_uses_all_tables():
    sched = GameNightScheduler(
        n_participants=16,
        tables=3,
        seats_per_table=4,  # capacity 12, 4 sit out
        max_diversity_rounds=2,
        pick_winner=lambda players: max(players, key=lambda p: p.player_id),
    )
    result = sched.run()
    diversity = [r for r in result.rounds if r.kind == "diversity"]
    assert diversity
    for rnd in diversity:
        assert len(rnd.tables) == 3
        assert len(rnd.sit_outs) == 4
    for rnd in result.rounds:
        assert len(rnd.tables) == 3  # all tables used in every phase


def test_diversity_increases_unique_partners():
    sched = GameNightScheduler(
        n_participants=12,
        tables=3,
        seats_per_table=4,
        seating=GreedyDiversitySeating(),
        max_diversity_rounds=5,
        pick_winner=lambda players: players[0],
    )
    result = sched.run()
    # After several rounds, average unique partners should be > G-1 (single table)
    avg = sum(result.unique_partners(p.player_id) for p in sched.players) / len(sched.players)
    assert avg > 3


def test_rejects_too_few_players():
    import pytest

    with pytest.raises(ValueError):
        GameNightScheduler(n_participants=5, tables=2, seats_per_table=4)
