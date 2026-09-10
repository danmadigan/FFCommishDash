# Fantasy Football Dashboard

A Streamlit dashboard for your fantasy football leagues, across both ESPN
and Sleeper:

- **League Dashboard** (ESPN leagues) — who's paid, weekly high scorers,
  and all-time records (most points in a season, most points in a week,
  championships per owner).
- **Lineup Optimizer** (every league, any platform) — upload a rankings/
  projections CSV and get the highest-scoring *legal* starting lineup for
  each of your teams, computed exactly against that league's real roster
  slots (FLEX/SUPERFLEX included) via optimal assignment, not a greedy
  guess.

## 1. Install

```bash
pip install -r requirements.txt
```

(If you're on the same Mac Mini setup you use for StreamBot, `python -m
streamlit run app.py` is the reliable launch command if the plain
`streamlit` command errors out.)

## 2. Get your espn_s2 and SWID cookies (private leagues)

1. In a browser, log into https://fantasy.espn.com and open your league.
2. Open dev tools (F12 or Cmd+Opt+I) → **Application** (Chrome) or
   **Storage** (Firefox) tab → **Cookies** → `https://fantasy.espn.com`.
3. Copy the values for `espn_s2` (a long string) and `SWID` (looks like
   `{XXXXXXXX-XXXX-...}`, include the curly braces).
4. Your **League ID** is the number in the URL when viewing your league,
   e.g. `.../league?leagueId=123456`.

These cookies don't expire quickly, but if the app suddenly can't
authenticate, re-grab them the same way.

You'll also want **your team ID** for the Lineup Optimizer (it needs to
know which roster in the league is yours) — it's the number in your
team's URL when you're viewing it, e.g. `...&teamId=4`.

## 3. Sleeper leagues need no cookies

Sleeper's league data is public, so there's nothing to authenticate:

1. Your **league ID** is the number in the league's URL, e.g.
   `sleeper.com/leagues/123456789/...`.
2. Your **Sleeper username** (or display name) identifies which roster in
   that league is yours.

## 4. Run it

```bash
cp config.example.json config.json
streamlit run app.py
```

The first time it opens, use the **⚙️ Manage leagues** panel in the
sidebar to add each of your five teams — pick ESPN or Sleeper per league,
then fill in that platform's fields (league ID/cookies/team ID for ESPN;
league ID/username for Sleeper) — this fills in the `config.json` you
just copied.

## 5. Using it

**📊 League Dashboard** (ESPN leagues only — this tab's data comes from
ESPN's season-history API, which Sleeper doesn't expose the same way):

- **Payment Tracker** — check off who's paid for the selected season,
  saves locally to `payments/`. Set your buy-in amount to see the pot
  and amount collected.
- **Weekly High Scorers** — this season's weekly winner plus a full
  scoring grid for every team/week.
- **All-Time Records** — click "Load / refresh full history" the first
  time (it pulls every season from ESPN and caches it to `cache/`, so
  later loads are instant). Shows top-10 single-season point totals,
  top-10 single-week point totals, and championship counts per owner.

**🎯 Lineup Optimizer** (every league you've added, ESPN and Sleeper
alike):

1. Upload a rankings/projections CSV with columns `PlayerName, Position,
   Team, Points, OverallRank, PositionRank` (the export most ranking
   sites/tools produce). It's saved to `rankings/latest.csv` so you don't
   have to re-upload every time you open the app that week.
2. Each of your teams gets its own card showing the optimal starting
   lineup — the combination of your actual rostered players that
   maximizes total projected points, legal against that league's real
   slot layout (including who's eligible for FLEX/SUPERFLEX) — plus the
   bench, sorted by points.
3. Any rostered player the app couldn't find in your rankings file is
   flagged and scored as 0 (it still shows up, just deprioritized) —
   usually a spelling difference or a very deep bench/practice-squad
   player your rankings file doesn't cover.

Rosters are fetched live from ESPN/Sleeper each time you open this tab
(not cached), so it always reflects your current roster — but the
*points* driving the recommendation are only as good as the rankings CSV
you uploaded. One caveat worth knowing: every league is scored off that
same CSV's flat `Points` column, not that league's individual scoring
rules (PPR vs. standard, TE premium, custom bonuses, etc.) — accurate if
your rankings already reflect scoring close to your leagues', otherwise
treat the recommendation as a strong starting point rather than gospel.

## Storing this in GitHub

`config.json`, `cache/`, `payments/`, and `rankings/` are already listed
in `.gitignore` — they hold your login cookies, cached league data,
payment status, and uploaded rankings, none of which belong in version
control (this applies even for a private repo). Only
`config.example.json` gets committed as a template.

```bash
git init
git add .
git commit -m "Fantasy football dashboard"
git remote add origin <your-repo-url>
git push -u origin main
```

On a new machine, cloning and running is just:

```bash
git clone <your-repo-url>
cd FFCommishDash
pip install -r requirements.txt
cp config.example.json config.json   # then re-add your leagues in the app
streamlit run app.py
```

You'll need to re-enter league credentials each place you run it, since
`config.json` never gets pushed. If you ever want the repo itself to
carry non-secret defaults (like league IDs and year ranges, just not
cookies), that can go in `config.example.json` instead of leaving it
as a blank template.

## Making it accessible from anywhere

Everything above runs the app locally (`localhost:8501`), reachable only
from that machine. Since you'll mostly use this from a desktop/laptop but
still want it reachable elsewhere, the easiest free option is **Streamlit
Community Cloud**:

1. Push this repo to GitHub (steps above).
2. At [share.streamlit.io](https://share.streamlit.io), sign in and pick
   this repo/branch and `app.py` as the entry point, then deploy.
3. **Add your leagues via Secrets, not the sidebar form.** Streamlit
   Cloud's local disk is wiped on every restart/redeploy, so anything
   saved through **⚙️ Manage leagues** (which just writes `config.json`)
   would vanish the next time the app restarts. Instead, on the deployed
   app go to **Settings → Secrets** and paste in a `[[leagues]]` block —
   see `.streamlit/secrets.toml.example` in this repo for the exact
   format (copy it, fill in your real league IDs/cookies/usernames, paste
   the whole thing into the Secrets box). The app detects secrets
   automatically: once a `leagues` key is present, **⚙️ Manage leagues**
   switches to a read-only summary and points back here instead of
   showing the add/remove form, since edits made through the app itself
   still wouldn't survive a restart.
4. To change your leagues later, edit them in **Settings → Secrets**
   again and reboot the app from the Streamlit Cloud dashboard.
5. You get a permanent `https://<your-app>.streamlit.app` URL you can
   open from any browser, phone included.

You can test this exact flow locally before deploying: copy
`.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` (already
gitignored), fill in real values, and run the app normally — it'll pick
up secrets the same way Streamlit Cloud does. With no `secrets.toml`
present (the default), the app behaves exactly as described above:
`config.json` plus the editable sidebar form.

Any other host that runs a long-lived Python process (a spare machine
with port-forwarding/Tailscale, Railway, Render, Fly.io, etc.) works the
same way — the app itself has no server-side dependencies beyond what's
in `requirements.txt`. Non-Streamlit hosts won't have `st.secrets`, so
they'd fall back to the `config.json` flow unless you wire up that
host's equivalent (an environment variable holding the same TOML, etc.).

## Notes

- All data is stored locally in this folder (`cache/` for ESPN/Sleeper
  pulls, `payments/` for who's-paid state, `rankings/` for your uploaded
  projections, `config.json` for your league settings/credentials).
  Nothing leaves your machine except what you explicitly push to GitHub
  or deploy — and the ignored files above are excluded from that.
- Championship counts rely on ESPN's `final_standing` field, which is
  only populated once a season is fully complete (so the current season
  won't show a champion until playoffs finish).
- If a season fails to load (e.g. a year before the league existed, or
  ESPN changed team IDs), it's skipped and listed under "seasons failed
  to load" rather than crashing the app.
- Player-name matching between your rankings CSV and each platform's
  roster is automatic (it normalizes punctuation/suffixes and reconciles
  team-code differences like `JAC`/`JAX` or `LA`/`LAR`), with a fuzzy
  fallback for near-misses. Defenses are matched by NFL team, not name,
  since every platform labels them differently.
