# Afia app

## Project purpose

Public Afia site. A scheduled GitHub Action rebuilds `feed.json` from the radio API and Sanity, then commits it so GitHub Pages serves the lineup.

## Architecture / layout map

- `index.html` reads `https://slaze.github.io/afia-app/feed.json`
- `scripts/build_feed.py` writes `feed.json`
- `scripts/build_programmes.py` writes `programmes.json` (failure is ignored by the workflow)
- `.github/workflows/feed.yml` runs every 15 minutes

## Inception → now timeline

- Feed publisher calls `https://afia-radio-backend.onrender.com/v1`

## Sessions

### 2026-10-19 — Stop the public feed job timing out on a cold API

- **What changed:** `scripts/build_feed.py` retries the radio API. The on-air call waits up to 90 seconds, three times, and retries HTTP 502/503/504. Later schedule calls stay shorter. `feed.yml` queues one publish job and caps it at 15 minutes. `feed.json` was refreshed (Monday lineup; the committed file was still Sunday 18 Oct).
- **Why:** Render sleeps the API. `urlopen` used a 30-second timeout and no retry, so every cold start failed the workflow before a commit. Checked runs `39265889186` and `39211884192`: `TimeoutError` on `/shows/on-air`.
- **How verified:** `python3 -m py_compile scripts/build_feed.py`. Live run wrote the feed in about 12 seconds while the API was awake. A stubbed `fetch` confirmed three attempts on timeout and no retry on HTTP 404.
- **Current state:** Commit `c1392ce` is on `main`. The cron and a manual run use the retrying script.
- **Next steps:** Confirm the manual run after `c1392ce` goes green.
- **Blockers / risks:** If the API stays down past three 90-second tries, the job still fails. Programme scraping can fail quietly because the workflow runs it with `|| true`.
