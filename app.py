import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from espn_client import fetch_league_data, fetch_multi_year
from espn_client import get_team_roster_and_slots as espn_roster_and_slots
from lineup_optimizer import optimize_lineup
from rankings import build_rankings_index, match_player, parse_rankings_csv
from sleeper_client import fetch_players_db
from sleeper_client import get_team_roster_and_slots as sleeper_roster_and_slots
from storage import load_payments, save_payments

st.set_page_config(page_title="Fantasy Football Dashboard", layout="wide", page_icon="🏈")

CONFIG_PATH = Path("config.json")
RANKINGS_PATH = Path("rankings") / "latest.csv"
RANKINGS_PATH.parent.mkdir(exist_ok=True)


def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
    else:
        cfg = {"leagues": [], "buy_in": 50}
    for lg in cfg.get("leagues", []):
        lg.setdefault("platform", "espn")
    return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


config = load_config()

st.sidebar.title("🏈 Fantasy Football")

with st.sidebar.expander("⚙️ Manage leagues", expanded=not config["leagues"]):
    st.caption(
        "ESPN private leagues need the `espn_s2`/`SWID` cookies (see README). "
        "Sleeper leagues just need the league ID and your Sleeper username — no cookies needed."
    )
    for i, lg in enumerate(config["leagues"]):
        tag = "ESPN" if lg["platform"] == "espn" else "Sleeper"
        col1, col2 = st.columns([4, 1])
        col1.text(f"• [{tag}] {lg['name']}")
        if col2.button("🗑️", key=f"remove_league_{i}", help=f"Remove {lg['name']}"):
            config["leagues"].pop(i)
            save_config(config)
            st.session_state.pop("optimizer_data", None)
            st.rerun()

    platform = st.selectbox("Platform", ["ESPN", "Sleeper"], key="new_platform")

    with st.form("add_league", clear_on_submit=True):
        name = st.text_input("League name")
        if platform == "ESPN":
            league_id = st.text_input("League ID")
            espn_s2 = st.text_input("espn_s2 cookie", type="password")
            swid = st.text_input("SWID cookie", type="password")
            c1, c2, c3 = st.columns(3)
            start_year = c1.number_input("First season to track", min_value=2010, max_value=2035, value=2019)
            current_year = c2.number_input("Current season", min_value=2010, max_value=2035, value=2026)
            my_team_id = c3.number_input(
                "Your team ID", min_value=1, value=1, help="Found in your team's URL, e.g. ...&teamId=N"
            )
        else:
            sleeper_league_id = st.text_input(
                "Sleeper league ID", help="The number in your league's URL on sleeper.com"
            )
            sleeper_username = st.text_input("Your Sleeper username")

        submitted = st.form_submit_button("Add league")
        if submitted and name:
            if platform == "ESPN" and league_id:
                config["leagues"].append(
                    {
                        "platform": "espn",
                        "name": name,
                        "league_id": int(league_id),
                        "espn_s2": espn_s2,
                        "swid": swid,
                        "start_year": int(start_year),
                        "current_year": int(current_year),
                        "my_team_id": int(my_team_id),
                    }
                )
                save_config(config)
                st.success(f"Added {name}.")
                st.rerun()
            elif platform == "Sleeper" and sleeper_league_id and sleeper_username:
                config["leagues"].append(
                    {
                        "platform": "sleeper",
                        "name": name,
                        "sleeper_league_id": sleeper_league_id.strip(),
                        "sleeper_username": sleeper_username.strip(),
                    }
                )
                save_config(config)
                st.success(f"Added {name}.")
                st.rerun()
            else:
                st.error("Fill in all fields for the selected platform.")

if not config["leagues"]:
    st.title("Fantasy Football Dashboard")
    st.info("Add a league in the sidebar to get started.")
    st.stop()


# ====================================================================== #
# Commissioner — payments / weekly scores / records (ESPN leagues)       #
# ====================================================================== #
def render_commissioner(config):
    espn_leagues = [lg for lg in config["leagues"] if lg["platform"] == "espn"]
    if not espn_leagues:
        st.title("Commissioner")
        st.info("This tab covers ESPN leagues. Add one in the sidebar, or switch to 🎯 Lineup Optimizer.")
        return

    league_names = [lg["name"] for lg in espn_leagues]
    selected_name = st.sidebar.selectbox("Select league", league_names)
    league_cfg = next(lg for lg in espn_leagues if lg["name"] == selected_name)

    years = list(range(league_cfg["start_year"], league_cfg["current_year"] + 1))
    selected_year = st.sidebar.selectbox("Season", sorted(years, reverse=True))

    refresh = st.sidebar.button("🔄 Refresh this season from ESPN")

    st.title(f"🏈 {selected_name} — {selected_year}")

    tab_payments, tab_weekly, tab_records = st.tabs(
        ["💰 Payment Tracker", "📊 Weekly High Scorers", "🏆 All-Time Records"]
    )

    try:
        season_data = fetch_league_data(
            league_cfg["league_id"],
            selected_year,
            league_cfg["espn_s2"],
            league_cfg["swid"],
            force_refresh=refresh,
        )
    except Exception as e:
        st.error(f"Couldn't fetch data from ESPN for {selected_year}: {e}")
        return

    teams = season_data["teams"]

    # ------------------------------------------------------------ Payments
    with tab_payments:
        st.subheader("Who's Paid")

        buy_in = st.number_input(
            "Buy-in amount ($)", min_value=0, value=config.get("buy_in", 50), step=5, key="buyin"
        )
        if buy_in != config.get("buy_in"):
            config["buy_in"] = buy_in
            save_config(config)

        payments = load_payments(league_cfg["league_id"], selected_year)

        rows = []
        for t in teams:
            tid = str(t["team_id"])
            paid = payments.get(tid, {}).get("paid", False)
            rows.append({"team_id": tid, "Owner": t["owner"], "Team": t["team_name"], "Paid": paid})

        df = pd.DataFrame(rows)
        edited = st.data_editor(
            df,
            column_config={"Paid": st.column_config.CheckboxColumn("Paid?"), "team_id": None},
            hide_index=True,
            use_container_width=True,
            key="payment_editor",
        )

        if st.button("💾 Save payment status"):
            for _, row in edited.iterrows():
                payments[row["team_id"]] = {"paid": bool(row["Paid"]), "owner": row["Owner"]}
            save_payments(league_cfg["league_id"], selected_year, payments)
            st.success("Saved.")

        paid_count = int(edited["Paid"].sum())
        total = len(edited)
        m1, m2, m3 = st.columns(3)
        m1.metric("Paid", f"{paid_count} / {total}")
        m2.metric("Pot", f"${buy_in * total}")
        m3.metric("Collected", f"${buy_in * paid_count}")

    # -------------------------------------------------------------- Weekly
    with tab_weekly:
        st.subheader(f"Weekly High Scorers — {selected_year}")

        week_records = {}
        for t in teams:
            for w in t["weekly_scores"]:
                week_records.setdefault(w["week"], []).append(
                    {"Owner": t["owner"], "Team": t["team_name"], "Points": w["points"]}
                )

        summary_rows = []
        for wk in sorted(week_records.keys()):
            best = max(week_records[wk], key=lambda x: x["Points"])
            summary_rows.append(
                {"Week": wk, "High Scorer": best["Owner"], "Team": best["Team"], "Points": best["Points"]}
            )

        if summary_rows:
            st.dataframe(pd.DataFrame(summary_rows), hide_index=True, use_container_width=True)
        else:
            st.info("No weekly scores yet for this season.")

        st.divider()
        st.subheader("Full weekly scoring grid")
        grid_rows = []
        for t in teams:
            row = {"Owner": t["owner"], "Team": t["team_name"]}
            for w in t["weekly_scores"]:
                row[f"Wk {w['week']}"] = w["points"]
            grid_rows.append(row)
        if grid_rows:
            st.dataframe(pd.DataFrame(grid_rows), hide_index=True, use_container_width=True)

    # ------------------------------------------------------------- Records
    with tab_records:
        st.subheader("All-Time Records")
        st.caption(
            f"Pulled across every season from {league_cfg['start_year']} to "
            f"{league_cfg['current_year']}. First load fetches each season from ESPN "
            "and caches it locally, so it's slow once and fast after."
        )

        history_key = f"history_{league_cfg['league_id']}"

        if st.button("📥 Load / refresh full history"):
            st.session_state[history_key] = fetch_multi_year(
                league_cfg["league_id"], years, league_cfg["espn_s2"], league_cfg["swid"], force_refresh=True
            )

        if history_key not in st.session_state:
            st.session_state[history_key] = fetch_multi_year(
                league_cfg["league_id"], years, league_cfg["espn_s2"], league_cfg["swid"], force_refresh=False
            )

        history = st.session_state[history_key]

        best_season, best_week, championships = [], [], {}

        for yr, yr_data in history.items():
            if not yr_data or "error" in yr_data:
                continue
            for t in yr_data["teams"]:
                best_season.append({"Year": yr, "Owner": t["owner"], "Team": t["team_name"], "Points": t["season_points"]})
                for w in t["weekly_scores"]:
                    best_week.append(
                        {"Year": yr, "Week": w["week"], "Owner": t["owner"], "Team": t["team_name"], "Points": w["points"]}
                    )
                if t.get("final_standing") == 1:
                    championships[t["owner"]] = championships.get(t["owner"], 0) + 1

        errors = {yr: d["error"] for yr, d in history.items() if isinstance(d, dict) and "error" in d}
        if errors:
            with st.expander(f"⚠️ {len(errors)} season(s) failed to load"):
                for yr, err in errors.items():
                    st.text(f"{yr}: {err}")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Most Points in a Season**")
            if best_season:
                top = sorted(best_season, key=lambda x: x["Points"], reverse=True)[:10]
                st.dataframe(pd.DataFrame(top), hide_index=True, use_container_width=True)
        with col2:
            st.markdown("**Most Points in a Week**")
            if best_week:
                top = sorted(best_week, key=lambda x: x["Points"], reverse=True)[:10]
                st.dataframe(pd.DataFrame(top), hide_index=True, use_container_width=True)

        st.markdown("**Championships Won**")
        if championships:
            champ_df = pd.DataFrame(
                sorted(championships.items(), key=lambda x: x[1], reverse=True), columns=["Owner", "Championships"]
            )
            st.dataframe(champ_df, hide_index=True, use_container_width=True)
        else:
            st.info(
                "No championships detected yet. This reads ESPN's `final_standing` "
                "field, which only populates once a season is fully complete."
            )


# ====================================================================== #
# Lineup Optimizer — all teams, both platforms                           #
# ====================================================================== #
def _compute_league_lineup(lg, rankings_index, sleeper_players_db):
    if lg["platform"] == "espn":
        players, slots = espn_roster_and_slots(
            lg["league_id"], lg["current_year"], lg["espn_s2"], lg["swid"], lg["my_team_id"]
        )
    else:
        players, slots = sleeper_roster_and_slots(
            lg["sleeper_league_id"], lg["sleeper_username"], players_db=sleeper_players_db
        )

    enriched = []
    unmatched = []
    for p in players:
        match = match_player(p["name"], p["position"], p.get("nfl_team", ""), rankings_index)
        pts = match["points"] if match else 0.0
        enriched.append({**p, "points": pts})
        if match is None:
            unmatched.append(f"{p['name']} ({p['position']})")

    return {"result": optimize_lineup(enriched, slots), "unmatched": unmatched}


def render_optimizer(config):
    st.title("🎯 Lineup Optimizer")
    st.caption(
        "Upload this week's rankings/projections and get the highest-scoring legal "
        "lineup for every team below, computed exactly against each league's real "
        "roster slots (including FLEX/SUPERFLEX eligibility) via optimal assignment — "
        "not a greedy guess."
    )
    st.caption(
        "Note: every team's lineup is optimized off the single 'Points' projection in "
        "your rankings file, not each league's own scoring rules — accurate if your "
        "rankings already reflect PPR/standard/custom scoring close to your leagues', "
        "otherwise treat it as a strong starting point rather than gospel."
    )

    uploaded = st.file_uploader(
        "Upload rankings CSV (PlayerName, Position, Team, Points, OverallRank, PositionRank)",
        type=["csv"],
    )
    if uploaded is not None:
        RANKINGS_PATH.write_bytes(uploaded.getvalue())
        st.success(f"Saved {uploaded.name} as this week's rankings.")
        st.session_state.pop("optimizer_data", None)

    if not RANKINGS_PATH.exists():
        st.info("Upload a rankings CSV to get started.")
        return

    rankings_rows = parse_rankings_csv(str(RANKINGS_PATH))
    rankings_index = build_rankings_index(rankings_rows)
    mtime = datetime.fromtimestamp(RANKINGS_PATH.stat().st_mtime)
    st.caption(f"Using rankings uploaded {mtime:%b %d, %Y %I:%M %p} — {len(rankings_rows)} players loaded.")

    # Rosters are only re-fetched on an explicit click (or the first time this
    # tab is used this session) — not on every rerun — since this tab now
    # lives alongside the Commissioner tab and any interaction there (e.g. a
    # payment checkbox) would otherwise also trigger live ESPN/Sleeper calls.
    refresh_clicked = st.button("🔄 Load / refresh lineups", type="primary")
    if refresh_clicked or "optimizer_data" not in st.session_state:
        sleeper_players_db = None
        data, errors = {}, {}
        for lg in config["leagues"]:
            try:
                if lg["platform"] == "sleeper" and sleeper_players_db is None:
                    with st.spinner("Loading Sleeper player database..."):
                        sleeper_players_db = fetch_players_db()
                data[lg["name"]] = _compute_league_lineup(lg, rankings_index, sleeper_players_db)
            except Exception as e:
                errors[lg["name"]] = str(e)
        st.session_state["optimizer_data"] = {"data": data, "errors": errors}

    cached = st.session_state["optimizer_data"]

    for i, lg in enumerate(config["leagues"]):
        icon = "🟦" if lg["platform"] == "espn" else "🟩"
        with st.expander(f"{icon} {lg['name']}", expanded=True, key=f"league_expander_{i}"):
            if lg["name"] in cached["errors"]:
                st.error(f"Couldn't load this team's roster: {cached['errors'][lg['name']]}")
                continue

            info = cached["data"].get(lg["name"])
            if info is None:
                st.warning("No roster players found — double-check this league's settings in Manage leagues.")
                continue

            result = info["result"]
            unmatched = info["unmatched"]

            starter_rows = []
            total = 0.0
            for slot, player in zip(result["slots"], result["starters"]):
                if player is None:
                    starter_rows.append({"Slot": slot, "Player": "—", "Pos": "", "NFL Team": "", "Proj Pts": ""})
                    continue
                pts = player.get("points", 0.0) or 0.0
                starter_rows.append(
                    {
                        "Slot": slot,
                        "Player": player["name"],
                        "Pos": player["position"],
                        "NFL Team": player.get("nfl_team", ""),
                        "Proj Pts": round(pts, 1),
                    }
                )
                total += pts

            st.markdown(f"**Optimal starters** — projected total: **{total:.1f} pts**")
            st.dataframe(
                pd.DataFrame(starter_rows), hide_index=True, use_container_width=True, key=f"starters_df_{i}"
            )

            bench_rows = [
                {
                    "Player": p["name"],
                    "Pos": p["position"],
                    "NFL Team": p.get("nfl_team", ""),
                    "Proj Pts": round(p.get("points", 0.0) or 0.0, 1),
                }
                for p in result["bench"]
            ]
            if bench_rows:
                with st.expander("Bench", key=f"bench_expander_{i}"):
                    st.dataframe(
                        pd.DataFrame(bench_rows), hide_index=True, use_container_width=True, key=f"bench_df_{i}"
                    )

            for w in result["warnings"]:
                st.warning(w)
            if unmatched:
                st.caption("⚠️ Not found in rankings, scored as 0 pts: " + ", ".join(sorted(unmatched)))


tab_commissioner, tab_optimizer = st.tabs(["🏛️ Commissioner", "🎯 Lineup Optimizer"])

with tab_commissioner:
    render_commissioner(config)

with tab_optimizer:
    render_optimizer(config)
