"""Optimal starting-lineup solver.

Given a roster (players with a projected point value) and a league's
starting-slot layout (QB, RB, RB, WR, WR, TE, FLEX, D/ST, K, ...), finds the
assignment of players to slots that maximizes total projected points,
respecting which positions are eligible for multi-position slots like FLEX
or SUPERFLEX. This is a linear assignment problem, solved exactly with the
Hungarian algorithm (scipy) rather than a greedy heuristic, so FLEX/SUPERFLEX
decisions come out globally optimal instead of just locally reasonable.
"""
import numpy as np
from scipy.optimize import linear_sum_assignment

# Which core positions are eligible for each slot type. Slot types are the
# normalized vocabulary produced by espn_client / sleeper_client.
SLOT_ELIGIBILITY = {
    "QB": {"QB"},
    "RB": {"RB"},
    "WR": {"WR"},
    "TE": {"TE"},
    "K": {"K"},
    "DEF": {"DEF"},
    "FLEX": {"RB", "WR", "TE"},
    "RB/WR": {"RB", "WR"},
    "WR/TE": {"WR", "TE"},
    "SUPERFLEX": {"QB", "RB", "WR", "TE"},
}

BIG = 1_000_000.0


def optimize_lineup(players, slots):
    """players: list of dicts with at least 'position' and 'points'.
    slots: list of slot-type strings, one entry per starting slot.

    Returns {"slots": slots, "starters": [player-or-None per slot],
             "bench": [...], "warnings": [...]}."""
    n_players = len(players)
    n_slots = len(slots)

    if n_slots == 0:
        return {"slots": [], "starters": [], "bench": list(players), "warnings": ["This league has no starting slots configured."]}
    if n_players == 0:
        return {"slots": slots, "starters": [None] * n_slots, "bench": [], "warnings": ["No roster players were found."]}

    cost = np.full((n_players, n_slots), BIG)
    for i, p in enumerate(players):
        pos = p.get("position")
        pts = p.get("points", 0.0) or 0.0
        for j, slot in enumerate(slots):
            if pos in SLOT_ELIGIBILITY.get(slot, {slot}):
                cost[i, j] = -pts

    row_ind, col_ind = linear_sum_assignment(cost)

    starters = [None] * n_slots
    used = set()
    warnings = []
    for r, c in zip(row_ind, col_ind):
        if cost[r, c] >= BIG:
            warnings.append(f"No eligible roster player for slot '{slots[c]}' — roster may be short at that position.")
            continue
        starters[c] = players[r]
        used.add(r)

    bench = [p for i, p in enumerate(players) if i not in used]
    bench.sort(key=lambda p: p.get("points", 0.0) or 0.0, reverse=True)

    return {"slots": slots, "starters": starters, "bench": bench, "warnings": warnings}
