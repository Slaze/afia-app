#!/usr/bin/env python3
"""Catalogue Afia TV Official programmes from the public YouTube channel."""

import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

CHANNEL = "https://www.youtube.com/@afiatv_official/playlists"
OUT = Path(__file__).resolve().parents[1] / "programmes.json"
PER_SECTION = 18


def post(key, version, payload):
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        f"https://www.youtube.com/youtubei/v1/browse?prettyPrint=false&key={key}",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        return json.load(response)


def page():
    request = urllib.request.Request(CHANNEL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=40) as response:
        html = response.read().decode("utf-8", "replace")
    key = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html).group(1)
    version = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', html).group(1)
    match = re.search(r"var ytInitialData = (\{.*?\});</script>", html)
    data = json.loads(match.group(1))
    tabs = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]
    selected = next(tab["tabRenderer"] for tab in tabs if tab.get("tabRenderer", {}).get("selected"))
    items = selected["content"]["sectionListRenderer"]["contents"][0]["itemSectionRenderer"]["contents"][0]["gridRenderer"]["items"]
    sections = []
    for item in items:
        lock = item.get("lockupViewModel") or {}
        title = ((lock.get("metadata") or {}).get("lockupMetadataViewModel") or {}).get("title", {}).get("content")
        playlist = lock.get("contentId")
        if title and playlist:
            sections.append({"title": title, "id": playlist})
    return key, version, sections


def plain_number(text):
    raw = str(text or "").lower().replace(",", "").replace("views", "").replace("view", "").strip()
    mult = 1
    if raw.endswith("k"):
        mult = 1000
        raw = raw[:-1]
    elif raw.endswith("m"):
        mult = 1000000
        raw = raw[:-1]
    try:
        return int(float(raw) * mult)
    except ValueError:
        return 0


def age_days(text):
    match = re.search(r"(\d+)\s+(second|minute|hour|day|week|month|year)", str(text or "").lower())
    if not match:
        return None
    count = int(match.group(1))
    unit = match.group(2)
    scale = {"second": 0, "minute": 0, "hour": 0, "day": count, "week": count * 7, "month": count * 30, "year": count * 365}
    return scale[unit]


def row_bits(lock):
    meta = ((lock.get("metadata") or {}).get("lockupMetadataViewModel") or {}).get("metadata") or {}
    parts = []
    for row in (meta.get("contentMetadataViewModel") or {}).get("metadataRows") or []:
        for part in row.get("metadataParts") or []:
            text = ((part.get("text") or {}).get("content")) or ""
            if text:
                parts.append(text)
    views = 0
    days = None
    for text in parts:
        if "view" in text.lower():
            views = plain_number(text)
        if days is None:
            days = age_days(text)
    return views, days


def episodes(key, version, playlist):
    data = post(key, version, {
        "context": {"client": {"clientName": "WEB", "clientVersion": version, "hl": "en", "gl": "NG"}},
        "browseId": "VL" + playlist,
    })
    found = []

    def walk(node):
        if isinstance(node, dict):
            lock = node.get("lockupViewModel")
            if lock and lock.get("contentType") == "LOCKUP_CONTENT_TYPE_VIDEO":
                title = ((lock.get("metadata") or {}).get("lockupMetadataViewModel") or {}).get("title", {}).get("content")
                video = lock.get("contentId")
                if title and video and not any(row["id"] == video for row in found):
                    views, days = row_bits(lock)
                    found.append({"id": video, "title": title, "views": views, "likes": 0, "days": days})
            else:
                for value in node.values():
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return found[:PER_SECTION]


def player_stats(version, video_id):
    body = json.dumps({
        "context": {"client": {"clientName": "WEB", "clientVersion": version, "hl": "en", "gl": "NG"}},
        "videoId": video_id,
    }).encode()
    request = urllib.request.Request(
        "https://www.youtube.com/youtubei/v1/player?prettyPrint=false",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        data = json.load(response)
    micro = (data.get("microformat") or {}).get("playerMicroformatRenderer") or {}
    published = micro.get("publishDate") or ""
    days = None
    if published:
        try:
            when = datetime.fromisoformat(published)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            days = max(0, (datetime.now(timezone.utc) - when).days)
        except ValueError:
            days = None
    return {
        "views": int(micro.get("viewCount") or 0),
        "likes": int(str(micro.get("likeCount") or "0").split()[0] or 0),
        "days": days,
        "published": published if days is not None else "",
    }


def clip_comment(text):
    if isinstance(text, dict):
        text = text.get("content") or ""
    line = re.sub(r"\s+", " ", str(text or "")).strip()
    if line.startswith("{") or len(line) < 2:
        return ""
    return line[:140]


def existing_comments(version, video_id):
    context = {"client": {"clientName": "WEB", "clientVersion": version, "hl": "en", "gl": "NG"}}

    def pull(payload):
        body = json.dumps(payload).encode()
        request = urllib.request.Request(
            "https://www.youtube.com/youtubei/v1/next?prettyPrint=false",
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.load(response)

    page_data = pull({"context": context, "videoId": video_id})
    panels = page_data.get("engagementPanels") or []
    token = ""
    for panel in panels:
        renderer = panel.get("engagementPanelSectionListRenderer") or {}
        if renderer.get("panelIdentifier") != "engagement-panel-comments-section":
            continue
        try:
            token = renderer["content"]["sectionListRenderer"]["contents"][0]["itemSectionRenderer"]["contents"][0]["continuationItemRenderer"]["continuationEndpoint"]["continuationCommand"]["token"]
        except (KeyError, IndexError, TypeError):
            token = ""
    if not token:
        return []
    more = pull({"context": context, "continuation": token})
    found = []

    def walk(node):
        if isinstance(node, dict):
            entity = node.get("commentEntityPayload")
            if entity:
                props = entity.get("properties") or {}
                author = entity.get("author") or {}
                text = clip_comment(props.get("content"))
                name = str(author.get("displayName") or "").lstrip("@").strip()[:28]
                if text and name and props.get("replyLevel") in (None, 0, "0"):
                    found.append({"name": name, "text": text})
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(more)
    unique = []
    seen = set()
    for row in found:
        if row["text"] in seen:
            continue
        seen.add(row["text"])
        unique.append(row)
        if len(unique) == 8:
            break
    return unique


def attach_comments(version, sections):
    ids = []
    for section in sections:
        for row in section["episodes"]:
            if row["id"] not in ids:
                ids.append(row["id"])
    found = {}

    def one(video_id):
        try:
            return video_id, existing_comments(version, video_id)
        except Exception:
            return video_id, []

    with ThreadPoolExecutor(max_workers=6) as pool:
        for video_id, lines in pool.map(one, ids):
            found[video_id] = lines
    for section in sections:
        for row in section["episodes"]:
            row["chat"] = found.get(row["id"]) or []
    return sum(1 for lines in found.values() if lines)


def enrich(version, sections):
    ids = []
    for section in sections:
        for row in section["episodes"]:
            if row["id"] not in ids:
                ids.append(row["id"])
    found = {}

    def one(video_id):
        try:
            return video_id, player_stats(version, video_id)
        except Exception:
            return video_id, None

    with ThreadPoolExecutor(max_workers=6) as pool:
        for video_id, stats in pool.map(one, ids):
            if stats:
                found[video_id] = stats
    for section in sections:
        for row in section["episodes"]:
            stats = found.get(row["id"])
            if not stats:
                continue
            if stats["views"]:
                row["views"] = stats["views"]
            row["likes"] = stats["likes"]
            if stats["days"] is not None:
                row["days"] = stats["days"]
            if stats.get("published"):
                row["published"] = stats["published"]
    return len(found)


def rank(sections):
    unique = []
    seen = set()
    for section in sections:
        for row in section["episodes"]:
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            unique.append({
                "id": row["id"],
                "title": row["title"],
                "section": section["title"],
                "views": row.get("views") or 0,
                "likes": row.get("likes") or 0,
                "days": row.get("days"),
            })

    def card(row):
        item = {"id": row["id"], "title": row["title"], "section": row["section"], "views": row["views"], "likes": row["likes"]}
        return item

    played = sorted(unique, key=lambda row: row["views"], reverse=True)[:8]
    liked = sorted(unique, key=lambda row: row["likes"], reverse=True)[:8]

    def heat(row):
        days = row["days"] if isinstance(row["days"], int) else 400
        return row["views"] / max(days, 1)

    fresh = [row for row in unique if isinstance(row["days"], int) and row["days"] <= 45]
    pool = fresh if len(fresh) >= 4 else unique
    trending = sorted(pool, key=heat, reverse=True)[:8]
    return {
        "mostPlayed": [card(row) for row in played if row["views"]],
        "mostLiked": [card(row) for row in liked if row["likes"]],
        "trending": [card(row) for row in trending if row["views"]],
    }


def main():
    key, version, sections = page()
    merged = []
    seen = set()
    for section in sections:
        title = section["title"].strip()
        key_name = title.casefold()
        if key_name in seen:
            continue
        seen.add(key_name)
        try:
            rows = episodes(key, version, section["id"])
        except Exception:
            rows = []
        if rows:
            merged.append({"title": title, "id": section["id"], "episodes": rows})
    counted = enrich(version, merged)
    with_chat = attach_comments(version, merged)
    stats = rank(merged)
    for section in merged:
        for row in section["episodes"]:
            row.pop("days", None)
    payload = {
        "channel": "https://www.youtube.com/@afiatv_official",
        "stats": stats,
        "sections": merged,
    }
    print(f"stats from {counted} episodes, comments on {with_chat}")
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(merged)} sections, {sum(len(row['episodes']) for row in merged)} episodes -> {OUT}")


if __name__ == "__main__":
    main()
