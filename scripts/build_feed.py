#!/usr/bin/env python3
"""Publish the public Afia lineup, stories, and episodes."""
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

RADIO = "https://afia-radio-backend.onrender.com/v1"
SANITY = "https://p9qytxax.apicdn.sanity.io/v2021-06-07/data/query/production"
STREAMS = ["https://stream.afia993.com/stream"]
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "feed.json"
NEWS = '*[_type=="news" && !(_id in path("drafts.**"))] | order(publishedAt desc)[0...8]{title,description,publishedAt,category,"slug":slug.current}'
VIDEOS = '*[_type=="videos" && !(_id in path("drafts.**"))] | order(publishedAt desc)[0...12]{title,description,publishedAt,embedUrl,"thumbnail":thumbnail.asset->url}'


def get(url):
    request = urllib.request.Request(url, headers={"User-Agent": "AfiaFeed/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def sanity(query):
    return get(SANITY + "?query=" + urllib.parse.quote(query)).get("result") or []


def check(url):
    request = urllib.request.Request(url, headers={"User-Agent": "AfiaFeed/1.0", "Icy-MetaData": "1"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            response.read(16)
            return {"url": url, "status": response.status, "type": response.headers.get("content-type")}
    except Exception as error:
        status = getattr(error, "code", None)
        return {"url": url, "status": status or 0, "error": type(error).__name__}


def main():
    now = datetime.now(ZoneInfo("Africa/Lagos"))
    on_air = get(RADIO + "/shows/on-air")
    week = []
    for offset in range(7):
        date = now + timedelta(days=offset)
        name = date.strftime("%A").upper()
        rows = get(RADIO + "/shows/schedule/" + name)
        rows = sorted(rows, key=lambda row: str(row.get("startTime") or ""))
        week.append({"label": date.strftime("%A %-d %b"), "rows": rows})
    payload = {
        "updatedAt": datetime.now(ZoneInfo("Africa/Lagos")).isoformat(),
        "onAir": on_air,
        "today": week[0]["rows"],
        "week": week,
        "news": sanity(NEWS),
        "episodes": sanity(VIDEOS),
        "streams": STREAMS,
        "streamChecks": [check(url) for url in STREAMS],
    }
    previous = {}
    if OUT.exists():
        previous = json.loads(OUT.read_text())
    watched = ("onAir", "today", "week", "news", "episodes", "streams", "streamChecks")
    if {key: previous.get(key) for key in watched} == {key: payload[key] for key in watched}:
        print("feed unchanged")
        return
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print("feed written", OUT, "shows", sum(len(day["rows"]) for day in week), "stories", len(payload["news"]))


if __name__ == "__main__":
    main()
