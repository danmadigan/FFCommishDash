"""Sleeper Fantasy Football data fetching.

Sleeper's read API is public and needs no login/cookies — just a league ID
(found in the league's URL in the Sleeper app/site, e.g.
sleeper.com/leagues/<league_id>) and the Sleeper username of the team owner
whose roster we want.
"""
import json
import time
from pathlib import Path

import requests

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)
PLAYERS_CACHE = CACHE_DIR / "sleeper_players.json"
PLAYERS_CACHE_TTL = 24 * 3600  # the full player DB changes rarely; refresh daily

BASE_URL = "https://api.sleeper.app/v1"

# Sleeper's roster_positions vocabulary -> the normalized slot vocabulary
# used by lineup_optimizer.SLOT_ELIGIBILITY.
SLOT_MAP = {
    "QB": "QB",
    "RB": "RB",
    "WR": "WR",
    "TE": "TE",
    "K": "K",
    "DEF": "DEF",
    "FLEX": "FLEX",
    "SUPER_FLEX": "SUPERFLEX",
    "REC_FLEX": "WR/TE",
    "WRRB_FLEX": "RB/WR",
}
EXCLUDE_SLOTS = {"BN", "IR", "TAXI"}


def _get(url):
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_players_db(force_refresh=False):
    """The full Sleeper player directory (~5MB). Cached to disk since it's
    the same for every league and rarely changes."""
    if PLAYERS_CACHE.exists() and not force_refresh:
        age = time.time() - PLAYERS_CACHE.stat().st_mtime
        if age < PLAYERS_CACHE_TTL:
            with open(PLAYERS_CACHE) as f:
                return json.load(f)

    data = _get(f"{BASE_URL}/players/nfl")
    with open(PLAYERS_CACHE, "w") as f:
        json.dump(data, f)
    return data


def fetch_league(league_id):
    return _get(f"{BASE_URL}/league/{league_id}")


def fetch_rosters(league_id):
    return _get(f"{BASE_URL}/league/{league_id}/rosters")


def fetch_users(league_id):
    return _get(f"{BASE_URL}/league/{league_id}/users")


def get_team_roster_and_slots(league_id, sleeper_username, players_db=None):
    """Returns (players, slots) for the roster owned by `sleeper_username`
    in the given Sleeper league.

    players: list of dicts {name, position, nfl_team, injury_status}
    slots: list of normalized slot-type strings, one per starting slot
    """
    league = fetch_league(league_id)
    if not league:
        raise ValueError(f"Sleeper league '{league_id}' not found.")

    users = fetch_users(league_id)
    rosters = fetch_rosters(league_id)
    players_db = players_db if players_db is not None else fetch_players_db()

    user = next(
        (
            u
            for u in users
            if (u.get("display_name") or "").lower() == sleeper_username.lower()
            or (u.get("username") or "").lower() == sleeper_username.lower()
        ),
        None,
    )
    if user is None:
        raise ValueError(f"No user named '{sleeper_username}' found in this Sleeper league.")

    roster = next((r for r in rosters if r.get("owner_id") == user["user_id"]), None)
    if roster is None:
        raise ValueError(f"'{sleeper_username}' has no roster in this Sleeper league.")

    players = []
    for pid in roster.get("players") or []:
        info = players_db.get(pid)
        if not info:
            continue
        pos = info.get("position")
        if pos == "DEF":
            name = info.get("team") or pid
        else:
            name = info.get("full_name") or f"{info.get('first_name', '')} {info.get('last_name', '')}".strip()
        players.append(
            {
                "name": name,
                "position": pos,
                "nfl_team": info.get("team"),
                "injury_status": info.get("injury_status") or "",
            }
        )

    slots = []
    for slot in league.get("roster_positions") or []:
        if slot in EXCLUDE_SLOTS:
            continue
        mapped = SLOT_MAP.get(slot)
        if mapped:
            slots.append(mapped)

    return players, slots
