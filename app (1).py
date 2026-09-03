import json
from pathlib import Path

import pandas as pd
import streamlit as st

from espn_client import fetch_league_data, fetch_multi_year
from storage import load_payments, save_payments

st.set_page_config(page_title="Fantasy Football Dashboard", layout="wide", page_icon="🏈")

CONFIG_PATH = Path("config.json")


def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {"leagues": [], "buy_in": 50}


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


config = load_config()

st.sidebar.title("🏈 Leagues")

with st.sidebar.expander("⚙️ Manage leagues", expanded=not config["leagues"]):
    st.caption(
        "Private leagues need the `espn_s2` and `SWID` cookies from your "
        "browser while logged into ESPN Fantasy (see README for how to grab them)."
    )
    for lg in config["leagues"]:
        st.text(f"• {lg['name']} (ID {lg['league_id']})")

    with st.form("add_league", clear_on_submit=True):
        name = st.text_input("League name")
        league_id = st.text_input("League ID")
        espn_s2 = st.text_input("espn_s2 cookie", type="password")
        swid = st.text_input("SWID cookie", type="password")
        c1, c2 = st.columns(2)
        start_year = c1.number_input("First season to track", min_value=2010, max_value=2035, value=2019)
        current_year = c2.number_input("Current season", min_value=2010, max_value=2035, value=2026)
        submitted = st.form_submit_button("Add league")
        if submitted and name and league_id:
            config["leagues"].append(
                {
                    "name": name,
                    "league_id": int(league_id),
                    "espn_s2": espn_s2,
                    "swid": swid,
                    "start_year": int(start_year),
                    "current_year": int(current_year),
                }
            )
            save_config(config)
            st.success(f"Added {name}.")
            st.rerun()

if not config["leagues"]:
    st.title("Fantasy Football Dashboard")
    st.info("Add a league in the sidebar to get started.")
    st.stop()

league_names = [lg["name"] for lg in config["leagues"]]
selected_name = st.sidebar.selectbox("Select league", league_names)
league_cfg = next(lg for lg in config["leagues"] if lg["name"] == selected_name)

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
    st.stop()

teams = season_data["teams"]

# ---------------------------------------------------------------- Payments
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

# ---------------------------------------------------------------- Weekly
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

# ---------------------------------------------------------------- Records
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
