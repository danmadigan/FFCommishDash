"""ESPN Fantasy Football data fetching with local JSON caching.

Uses the `espn_api` package to talk to private ESPN leagues via the
espn_s2 / SWID cookies. Each season's pull is cached to disk so the
dashboard doesn't have to hit ESPN every time you open it.
"""
import json
from pathlib import Path

from espn_api.football import League

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)


def _cache_path(league_id, year):
    return CACHE_DIR / f"league_{league_id}_{year}.json"


def fetch_league_data(league_id, year, espn_s2, swid, force_refresh=False):
    """Fetch (or load cached) data for one league/season.

    Returns a plain-dict summary: teams, owners, wins/losses, final
    standing, season point total, and week-by-week scores.
    """
    cache_file = _cache_path(league_id, year)
    if cache_file.exists() and not force_refresh:
        with open(cache_file, "r") as f:
            return json.load(f)

    league = League(league_id=int(league_id), year=int(year), espn_s2=espn_s2, swid=swid)

    teams_data = []
    for team in league.teams:
        owner_name = team.team_name
        if getattr(team, "owners", None):
            o = team.owners[0]
            if isinstance(o, dict):
                first = o.get("firstName", "")
                last = o.get("lastName", "")
                combined = f"{first} {last}".strip()
                if combined:
                    owner_name = combined
            elif isinstance(o, str) and o.strip():
                owner_name = o.strip()

        weekly_scores = []
        for week_num, score in enumerate(getattr(team, "scores", []) or [], start=1):
            if score and score > 0:
                weekly_scores.append({"week": week_num, "points": round(float(score), 2)})

        season_points = round(sum(w["points"] for w in weekly_scores), 2)

        teams_data.append(
            {
                "team_id": team.team_id,
                "team_name": team.team_name,
                "owner": owner_name,
                "wins": getattr(team, "wins", None),
                "losses": getattr(team, "losses", None),
                "ties": getattr(team, "ties", 0),
                "final_standing": getattr(team, "final_standing", None),
                "season_points": season_points,
                "weekly_scores": weekly_scores,
            }
        )

    league_name = ""
    try:
        league_name = league.settings.name
    except Exception:
        pass

    data = {
        "league_id": league_id,
        "year": year,
        "league_name": league_name,
        "current_week": getattr(league, "current_week", None),
        "teams": teams_data,
    }

    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2)

    return data


def fetch_multi_year(league_id, years, espn_s2, swid, force_refresh=False):
    """Fetch every season in `years`, skipping ones that error out
    (e.g. a year before the league existed) without killing the app."""
    all_years = {}
    for year in years:
        try:
            all_years[year] = fetch_league_data(league_id, year, espn_s2, swid, force_refresh)
        except Exception as e:
            all_years[year] = {"error": str(e)}
    return all_years
