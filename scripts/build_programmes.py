#!/usr/bin/env python3
"""Catalogue Afia TV Official programmes from the public YouTube channel."""

import json
import re
import urllib.request
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
                    found.append({"id": video, "title": title})
            else:
                for value in node.values():
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return found[:PER_SECTION]


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
    payload = {"channel": "https://www.youtube.com/@afiatv_official", "sections": merged}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(merged)} sections, {sum(len(row['episodes']) for row in merged)} episodes -> {OUT}")


if __name__ == "__main__":
    main()
