"""Parsing and matching for uploaded weekly rankings/projections CSVs.

Expected columns (matches the standard ESPN-style projections export):
PlayerName, Position, Team, Points, OverallRank, PositionRank

Matching player rosters (from ESPN/Sleeper) against these rankings is the
hard part: names are spelled slightly differently across sources, and
defenses are listed by city name instead of an NFL team code. This module
normalizes names/teams/positions so a roster player and a rankings row can
be compared reliably.
"""
import csv
import difflib
import io
import re

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

# Reconcile the handful of NFL team codes that differ between ESPN, Sleeper,
# and rankings exports (e.g. Rams: LA vs LAR, Jaguars: JAC vs JAX).
TEAM_ALIASES = {
    "JAC": "JAX",
    "LA": "LAR",
    "WSH": "WAS",
    "OAK": "LV",
    "LVR": "LV",
    "STL": "LAR",
    "SD": "LAC",
}


def normalize_team(code):
    if not code:
        return ""
    code = code.strip().upper()
    return TEAM_ALIASES.get(code, code)


def normalize_position(pos):
    pos = (pos or "").strip().upper()
    if pos in ("D/ST", "DST", "DEF"):
        return "DEF"
    return pos


def normalize_name(name):
    name = (name or "").lower()
    name = name.replace(".", "").replace("'", "").replace("-", " ")
    name = re.sub(r"[^a-z0-9 ]", "", name)
    parts = [p for p in name.split() if p not in SUFFIXES]
    return " ".join(parts).strip()


def parse_rankings_csv(file_obj):
    """Parse an uploaded rankings CSV (file-like object or path) into a
    list of dicts: name, position, team, points, overall_rank, position_rank."""
    if hasattr(file_obj, "read"):
        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8-sig")
        handle = io.StringIO(content)
    else:
        handle = open(file_obj, "r", encoding="utf-8-sig")

    try:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            try:
                points = float(row.get("Points") or 0)
            except ValueError:
                points = 0.0
            name = (row.get("PlayerName") or "").strip()
            if not name:
                continue
            rows.append(
                {
                    "name": name,
                    "position": normalize_position(row.get("Position")),
                    "team": normalize_team(row.get("Team")),
                    "points": points,
                    "overall_rank": row.get("OverallRank"),
                    "position_rank": row.get("PositionRank"),
                }
            )
        return rows
    finally:
        handle.close()


def build_rankings_index(rows):
    """Index rankings rows for fast lookup: by normalized player name, and
    separately by (team) for defenses, which are matched by team, not name."""
    by_name = {}
    by_def_team = {}
    for row in rows:
        if row["position"] == "DEF":
            by_def_team[row["team"]] = row
            continue
        key = normalize_name(row["name"])
        existing = by_name.get(key)
        if existing is None or row["points"] > existing["points"]:
            by_name[key] = row
    return {"by_name": by_name, "by_def_team": by_def_team}


def match_player(name, position, team, index):
    """Look up a roster player in a rankings index. Returns the matching
    rankings row, or None if no confident match was found."""
    position = normalize_position(position)
    team = normalize_team(team)

    if position == "DEF":
        return index["by_def_team"].get(team)

    key = normalize_name(name)
    row = index["by_name"].get(key)
    if row is not None:
        return row

    # Fallback: fuzzy-match against same-position candidates (handles minor
    # spelling/formatting differences between sources).
    candidates = [n for n, r in index["by_name"].items() if r["position"] == position]
    close = difflib.get_close_matches(key, candidates, n=1, cutoff=0.87)
    if close:
        return index["by_name"][close[0]]
    return None
