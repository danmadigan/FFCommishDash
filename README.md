# Fantasy Football Dashboard

A local Streamlit dashboard for your two ESPN leagues: who's paid, weekly
high scorers, and all-time records (most points in a season, most points
in a week, championships per owner).

## 1. Install

```bash
cd espn-ff-dashboard
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

## 3. Run it

```bash
cp config.example.json config.json
streamlit run app.py
```

The first time it opens, use the **⚙️ Manage leagues** panel in the
sidebar to add each of your two leagues (name, league ID, cookies, and
the year range you want tracked for history) — this fills in the
`config.json` you just copied.

## 4. Using it

- **Payment Tracker** — check off who's paid for the selected season,
  saves locally to `payments/`. Set your buy-in amount to see the pot
  and amount collected.
- **Weekly High Scorers** — this season's weekly winner plus a full
  scoring grid for every team/week.
- **All-Time Records** — click "Load / refresh full history" the first
  time (it pulls every season from ESPN and caches it to `cache/`, so
  later loads are instant). Shows top-10 single-season point totals,
  top-10 single-week point totals, and championship counts per owner.

## Storing this in GitHub

`config.json`, `cache/`, and `payments/` are already listed in
`.gitignore` — they hold your login cookies, cached league data, and
payment status, none of which belong in version control (this applies
even for a private repo). Only `config.example.json` gets committed as
a template.

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
cd espn-ff-dashboard
pip install -r requirements.txt
cp config.example.json config.json   # then re-add your leagues/cookies in the app
streamlit run app.py
```

You'll need to re-enter league cookies each place you run it, since
`config.json` never gets pushed. If you ever want the repo itself to
carry non-secret defaults (like league IDs and year ranges, just not
cookies), that can go in `config.example.json` instead of leaving it
as a blank template.

## Notes

- All data is stored locally in this folder (`cache/` for ESPN pulls,
  `payments/` for who's-paid state, `config.json` for your league
  settings/cookies). Nothing leaves your machine except what you
  explicitly push to GitHub — and the ignored files above are excluded
  from that.
- Championship counts rely on ESPN's `final_standing` field, which is
  only populated once a season is fully complete (so the current season
  won't show a champion until playoffs finish).
- If a season fails to load (e.g. a year before the league existed, or
  ESPN changed team IDs), it's skipped and listed under "seasons failed
  to load" rather than crashing the app.
