#!/usr/bin/env python3
"""Fetch original article images that are still available in the Wayback Machine."""

from __future__ import annotations

import concurrent.futures
import html
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEADLINE = time.monotonic() + 140
AGENT = "BikinLaper-Website-Recovery/1.0 (historical website preservation)"
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}


def fetch(url: str, timeout: int = 14) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), response.headers.get("Content-Type", "")


def original_path(url: str) -> pathlib.Path | None:
    parts = urllib.parse.urlsplit(html.unescape(url))
    if parts.hostname not in {"bikinlaper.com", "www.bikinlaper.com"}:
        return None
    target = ROOT / urllib.parse.unquote(parts.path).lstrip("/")
    if target.suffix.lower() not in EXTENSIONS:
        return None
    return target


def valid_image(payload: bytes, content_type: str) -> bool:
    if len(payload) < 50:
        return False
    signatures = (
        payload.startswith(b"\xff\xd8\xff"),
        payload.startswith(b"\x89PNG\r\n\x1a\n"),
        payload.startswith((b"GIF87a", b"GIF89a")),
        payload.startswith(b"RIFF") and payload[8:12] == b"WEBP",
        b"<svg" in payload[:1024].lower(),
    )
    return any(signatures) or (content_type.lower().startswith("image/") and b"<html" not in payload[:512].lower())


missing: dict[str, pathlib.Path] = {}
pattern = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', re.IGNORECASE)
for page in ROOT.rglob("*.html"):
    source = page.read_text(encoding="utf-8", errors="replace")
    for match in pattern.finditer(source):
        url = html.unescape(match.group(1))
        target = original_path(url)
        if target and not target.is_file():
            missing[url] = target

for payload in (ROOT / "wp-json/wp/v2/posts").rglob("*.json"):
    try:
        record = json.loads(payload.read_text(encoding="utf-8"))
        source = record.get("content", {}).get("rendered", "")
    except Exception:
        continue
    for value in re.findall(r'\bsrc=["\'](https?://(?:www\.)?bikinlaper\.com/[^"\']+)', source, flags=re.IGNORECASE):
        target = original_path(value)
        if target and not target.is_file():
            missing[html.unescape(value)] = target

print(f"Searching the Wayback Machine for {len(missing)} missing original article images.", flush=True)
snapshots: dict[str, str] = {}
index_error = None
params = urllib.parse.urlencode(
    {
        "url": "bikinlaper.com/wp-content/uploads/*",
        "output": "json",
        "filter": ["statuscode:200", "mimetype:image/.*"],
        "collapse": "urlkey",
        "fl": "timestamp,original,mimetype",
        "to": "20251011",
        "limit": "12000",
    },
    doseq=True,
)
try:
    payload, _ = fetch("https://web.archive.org/cdx/search/cdx?" + params, timeout=28)
    records = json.loads(payload)
    wanted = {urllib.parse.unquote(url).lower(): url for url in missing}
    for row in records[1:]:
        timestamp, original = row[:2]
        normalized = urllib.parse.unquote(original).lower()
        requested = wanted.get(normalized)
        if requested:
            snapshots[requested] = f"https://web.archive.org/web/{timestamp}id_/{original}"
    print(f"Wayback index returned {len(snapshots)} exact original-image snapshots.", flush=True)
except Exception as exc:
    index_error = str(exc)
    print(f"Wayback bulk index unavailable: {exc}", flush=True)


def recover(item: tuple[str, pathlib.Path]):
    url, target = item
    if time.monotonic() >= DEADLINE:
        return url, False, "deadline"
    snapshot = snapshots.get(url)
    if not snapshot:
        try:
            api = "https://archive.org/wayback/available?" + urllib.parse.urlencode({"url": url, "timestamp": "20251010"})
            payload, _ = fetch(api, timeout=9)
            record = json.loads(payload).get("archived_snapshots", {}).get("closest", {})
            if str(record.get("status")) != "200" or not record.get("available"):
                return url, False, "not_archived"
            snapshot = record["url"]
            snapshot = re.sub(r"(/web/\d+)(/)", r"\1id_\2", snapshot, count=1)
            snapshot = snapshot.replace("http://web.archive.org/", "https://web.archive.org/", 1)
        except Exception as exc:
            return url, False, str(exc)
    try:
        payload, content_type = fetch(snapshot, timeout=16)
        if not valid_image(payload, content_type):
            return url, False, "invalid_image_payload"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return url, True, str(target.relative_to(ROOT))
    except Exception as exc:
        return url, False, str(exc)


ordered = sorted(missing.items(), key=lambda item: (item[0] not in snapshots, item[0]))
recovered = []
failed = []
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    futures = {pool.submit(recover, item): item[0] for item in ordered}
    for future in concurrent.futures.as_completed(futures):
        try:
            url, success, result = future.result()
        except Exception as exc:
            url, success, result = futures[future], False, str(exc)
        (recovered if success else failed).append({"url": url, "result": result})
        if success:
            print(f"Recovered {result}", flush=True)

report = {
    "requested_original_images": len(missing),
    "indexed_original_images": len(snapshots),
    "recovered_original_images": len(recovered),
    "unavailable_original_images": len(failed),
    "index_error": index_error,
    "recovered": recovered,
    "unavailable": failed,
}
(ROOT / "_recovery/archive-image-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({key: value for key, value in report.items() if key not in {"recovered", "unavailable"}}, ensure_ascii=False), flush=True)
