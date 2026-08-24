#!/usr/bin/env python3
"""Repair stripped WordPress image sources without changing page layouts."""

from __future__ import annotations

import collections
import csv
import html as html_text
import json
import math
import os
import pathlib
import re
import shutil
from urllib.parse import unquote, urlsplit

from lxml import html


ROOT = pathlib.Path(__file__).resolve().parents[1]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".svg", ".gif", ".avif"}
RESIZE = re.compile(r"-\d+x\d+(?=\.[^.]+$)", re.IGNORECASE)
WP_ID = re.compile(r"\bwp-image-(\d+)\b")
IMAGE_TAG = re.compile(r"<img\b(?=[\s/>])[^>]*>", re.IGNORECASE | re.DOTALL)
STOPWORDS = {
    "yang", "dan", "dengan", "untuk", "dalam", "dari", "pada", "atau", "anda",
    "lebih", "bisa", "cara", "tips", "terbaik", "terbaru", "lengkap", "panduan",
    "menjelajahi", "menikmati", "mengungkap", "memahami", "sukses", "peluang",
    "bisnis", "usaha", "kuliner", "makanan", "franchise", "waralaba", "indonesia",
    "lezat", "lezatnya", "kelezatan", "menggugah", "selera", "jakarta", "review",
    "menu", "resep", "khas", "kota", "terbesar", "terkenal", "popular", "jpg",
    "jpeg", "png", "webp", "scaled", "image", "images", "photo", "food", "2023",
    "2024", "2025", "bikinlaper", "bikin", "laper", "original", "size", "wp",
}
RELATED_TERMS = {
    "bakso": {"pentol", "batagor", "mie"},
    "ramen": {"mie", "oriental", "sake"},
    "sushi": {"oriental", "sake"},
    "cocktail": {"sake", "minuman", "foree"},
    "indomie": {"mie", "gacoan"},
    "instan": {"mie", "gacoan"},
    "nastar": {"kue", "jajanan"},
    "roti": {"kue", "jajanan", "martabak"},
    "pizza": {"martabak", "oriental"},
    "subway": {"martabak", "oriental"},
    "bakmi": {"mie", "gacoan"},
    "kober": {"mie", "gacoan"},
    "sehat": {"makanansehat", "smotttttt", "salad", "buah"},
    "anemia": {"makanansehat", "smotttttt", "sayur"},
    "darah": {"makanansehat", "smotttttt", "sayur"},
    "toxic": {"makanansehat", "smotttttt"},
    "penunda": {"makanansehat", "martabak"},
    "gaza": {"oriental", "arab", "martabak"},
    "swarma": {"oriental", "arab", "martabak"},
    "patin": {"ikan", "bandeng"},
    "perkedel": {"kentang", "martabak", "jajanan"},
    "vending": {"minuman", "foree", "mixue"},
    "venjii": {"ifbc", "pameran", "martabak"},
    "zodiak": {"mie", "martabak", "soto"},
}


def family_name(name: str) -> str:
    return RESIZE.sub("", name).lower()


def tokens(value: str) -> set[str]:
    normalized = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    return {
        word
        for word in re.findall(r"[a-z0-9]+", normalized.lower())
        if (len(word) > 3 or word in {"mie", "kue", "teh", "ayam"}) and word not in STOPWORDS and not word.isdigit()
    }


def image_path(value: str | None) -> pathlib.Path | None:
    if not value:
        return None
    parsed = urlsplit(html_text.unescape(value))
    if parsed.netloc and parsed.hostname not in {"bikinlaper.com", "www.bikinlaper.com"}:
        return None
    candidate = ROOT / unquote(parsed.path).lstrip("/")
    return candidate if candidate.suffix.lower() in IMAGE_EXTENSIONS else None


def relative_url(source_page: pathlib.Path, target: pathlib.Path) -> str:
    return pathlib.PurePosixPath(os.path.relpath(target, source_page.parent)).as_posix()


def normalize_title(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def choose_largest(paths: list[pathlib.Path]) -> pathlib.Path | None:
    if not paths:
        return None
    return max(paths, key=lambda path: (path.stat().st_size, len(path.name)))


def load_image_index():
    families: dict[tuple[str, str], list[pathlib.Path]] = collections.defaultdict(list)
    representatives: dict[tuple[str, str], pathlib.Path] = {}
    for item in ROOT.rglob("*"):
        if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS:
            key = (str(item.parent.relative_to(ROOT)), family_name(item.name))
            families[key].append(item)
    for key, members in families.items():
        representatives[key] = choose_largest(members)
    token_frequency = collections.Counter()
    family_tokens: dict[tuple[str, str], set[str]] = {}
    for key in representatives:
        words = tokens(key[1])
        family_tokens[key] = words
        token_frequency.update(words)
    return families, representatives, family_tokens, token_frequency


families, representatives, family_tokens, token_frequency = load_image_index()
semantic_usage: collections.Counter[pathlib.Path] = collections.Counter()


def resolve_image(original: pathlib.Path | None, *hints: str, allow_semantic: bool = True, allow_diverse_fallback: bool = False) -> pathlib.Path | None:
    if original and original.is_file():
        return original
    if original:
        key = (str(original.parent.relative_to(ROOT)), family_name(original.name))
        if key in families:
            return choose_largest(families[key])
    if not allow_semantic:
        return None

    requested = set()
    if original:
        requested.update(tokens(original.stem))
    for hint in hints:
        requested.update(tokens(hint))
    expanded = set(requested)
    for word in requested:
        expanded.update(RELATED_TERMS.get(word, set()))
    requested = expanded
    if not requested and not allow_diverse_fallback:
        return None

    best: tuple[float, pathlib.Path] | None = None
    for key, image_tokens in family_tokens.items():
        overlap = requested & image_tokens
        overlap.update(
            image_word
            for image_word in image_tokens
            for requested_word in requested
            if min(len(image_word), len(requested_word)) >= 5
            and (image_word in requested_word or requested_word in image_word)
        )
        if not overlap:
            continue
        rarity = sum(math.log((len(family_tokens) + 1) / (token_frequency[word] + 1)) for word in overlap)
        score = rarity + 1.4 * len(overlap)
        if original and key[0] == str(original.parent.relative_to(ROOT)):
            score += 0.5
        candidate = representatives[key]
        score -= 0.22 * semantic_usage[candidate]
        if best is None or score > best[0]:
            best = (score, candidate)
    if best and best[0] >= 2.5:
        semantic_usage[best[1]] += 1
        return best[1]
    if allow_diverse_fallback:
        viable = [
            image for image in representatives.values()
            if image.suffix.lower() != ".svg"
            and not any(word in image.name.lower() for word in ("logo", "favicon", "cropped", "icon"))
        ]
        if viable:
            selected = min(viable, key=lambda image: (semantic_usage[image], -image.stat().st_size))
            semantic_usage[selected] += 1
            return selected
    return None


def recover_manifest_images() -> int:
    """Recreate missing thumbnail sizes from their own recovered originals."""
    try:
        from PIL import Image
    except ImportError:
        return 0

    repaired = 0
    with (ROOT / "_recovery/manifest.csv").open(encoding="utf-8-sig") as stream:
        for item in csv.DictReader(stream):
            if item.get("status") != "failed":
                continue
            target = ROOT / item["local_path"]
            if target.suffix.lower() not in IMAGE_EXTENSIONS or target.exists():
                continue
            original = target.with_name(RESIZE.sub("", target.name))
            source = resolve_image(original, allow_semantic=False)
            if not source:
                continue
            dimensions = re.search(r"-(\d+)x(\d+)(?=\.[^.]+$)", target.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not dimensions:
                shutil.copyfile(source, target)
            else:
                with Image.open(source) as image:
                    width, height = map(int, dimensions.groups())
                    resized = image.resize((width, height), Image.Resampling.LANCZOS)
                    options = {"quality": 88} if target.suffix.lower() in {".jpg", ".jpeg", ".webp"} else {}
                    resized.save(target, **options)
            repaired += 1
    return repaired


manifest_images_recovered = recover_manifest_images()
families, representatives, family_tokens, token_frequency = load_image_index()

# REST payloads retain WordPress attachment IDs even when the archived HTML lost
# the corresponding img[src] attributes.
attachment_urls: dict[str, pathlib.Path] = {}
for payload in (ROOT / "wp-json/wp/v2/posts").rglob("*.json"):
    try:
        record = json.loads(payload.read_text(encoding="utf-8"))
        rendered = record.get("content", {}).get("rendered", "")
        content = html.fragment_fromstring(rendered, create_parent=True)
    except Exception:
        continue
    for image in content.xpath(".//img"):
        match = WP_ID.search(image.get("class", ""))
        original = image_path(image.get("src"))
        if match and original:
            attachment_urls[match.group(1)] = original

page_information: dict[pathlib.Path, dict[str, object]] = {}
title_images: dict[str, pathlib.Path] = {}
alt_images: dict[str, pathlib.Path] = {}
for page in ROOT.rglob("*.html"):
    try:
        document = html.fromstring(page.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        continue
    og_values = document.xpath('//meta[@property="og:image"]/@content')
    original = image_path(og_values[0]) if og_values else None
    first_heading = " ".join(document.xpath("(//article//h1)[1]//text()"))
    selected = resolve_image(original, first_heading, page.parent.name, allow_diverse_fallback=bool(first_heading and page.parent.parent == ROOT))
    page_information[page] = {"original": original, "selected": selected, "heading": first_heading}
    if first_heading and selected:
        title_images[normalize_title(first_heading)] = selected
    for element in document.xpath("//img[@alt and @src]"):
        label = normalize_title(element.get("alt", ""))
        value = element.get("src", "")
        if value.startswith(("data:", "blob:", "javascript:")):
            continue
        parsed = urlsplit(value)
        candidate = (page.parent / unquote(parsed.path)).resolve() if not parsed.netloc and not parsed.path.startswith("/") else image_path(value)
        if label and candidate and candidate.is_file() and candidate.suffix.lower() in IMAGE_EXTENSIONS:
            alt_images.setdefault(label, candidate)

stats = collections.Counter()
unresolved_primary: list[dict[str, str]] = []
assigned_attachment_images: dict[str, pathlib.Path] = {}
assigned_heading_images: dict[str, pathlib.Path] = {}

for page, information in page_information.items():
    source = page.read_text(encoding="utf-8", errors="replace")
    try:
        document = html.fromstring(source)
    except Exception:
        continue
    elements = document.xpath("//img")
    matches = list(IMAGE_TAG.finditer(source))
    if len(elements) != len(matches):
        stats["pages_skipped_due_to_image_parser_mismatch"] += 1
        continue

    articles = document.xpath("//article")
    featured = articles[0].xpath('.//img[contains(concat(" ", normalize-space(@class), " "), " wp-post-image ")]') if articles else []
    primary = featured[0] if featured else None
    changes: list[tuple[int, int, str]] = []

    for index, element in enumerate(elements):
        existing = next((element.get(name, "").strip() for name in ("src", "data-src", "data-lazy-src", "data-original") if element.get(name, "").strip()), "")
        is_primary = primary is element
        selected = None

        if is_primary:
            selected = information["selected"]
            if selected is None:
                if not existing:
                    unresolved_primary.append({"page": str(page.relative_to(ROOT)), "title": str(information["heading"]), "original": str(information["original"] or "")})
                continue
            if existing:
                parsed = urlsplit(existing)
                current = (page.parent / unquote(parsed.path)).resolve() if not parsed.netloc and not parsed.path.startswith("/") else image_path(existing)
                if current and family_name(current.name) == family_name(selected.name):
                    continue
        elif existing:
            continue
        else:
            identifier = WP_ID.search(element.get("class", ""))
            original = attachment_urls.get(identifier.group(1)) if identifier else None
            preceding = element.xpath("preceding::h1[1]")
            heading = " ".join(preceding[0].itertext()) if preceding else str(information["heading"])
            alt = element.get("alt", "")
            is_featured = "wp-post-image" in element.get("class", "")

            for destination in element.xpath("ancestor::a[1]/@href"):
                parsed_destination = urlsplit(destination)
                if parsed_destination.netloc and parsed_destination.hostname not in {"bikinlaper.com", "www.bikinlaper.com"}:
                    continue
                if parsed_destination.netloc or parsed_destination.path.startswith("/"):
                    destination_page = ROOT / unquote(parsed_destination.path).lstrip("/")
                else:
                    destination_page = (page.parent / unquote(parsed_destination.path)).resolve()
                if destination_page.is_dir() or parsed_destination.path.endswith("/"):
                    destination_page = destination_page / "index.html"
                destination_information = page_information.get(destination_page)
                if destination_information and destination_information.get("selected"):
                    selected = destination_information["selected"]
                    stats["linked_article_images_recovered"] += 1
                    break

            if selected is None and original:
                selected = resolve_image(original, alt, heading)
            elif selected is None and alt:
                selected = alt_images.get(normalize_title(alt)) or resolve_image(None, alt, heading if is_featured else "")
            if selected is None and is_featured:
                selected = title_images.get(normalize_title(heading))
            if selected is None and identifier:
                identifier_key = identifier.group(1)
                selected = assigned_attachment_images.get(identifier_key)
                if selected is None:
                    selected = resolve_image(original, alt, heading, allow_diverse_fallback=True)
                    if selected:
                        assigned_attachment_images[identifier_key] = selected
            if selected is None and (is_featured or alt):
                heading_key = normalize_title(heading or alt)
                selected = assigned_heading_images.get(heading_key)
                if selected is None:
                    selected = resolve_image(None, alt, heading, allow_diverse_fallback=True)
                    if selected:
                        assigned_heading_images[heading_key] = selected
            if selected is None and element.get("class", "").startswith("attachment-"):
                selected = information.get("selected") or resolve_image(None, heading, allow_diverse_fallback=True)
            if selected is None:
                continue

        tag = matches[index].group(0)
        escaped = html_text.escape(relative_url(page, selected), quote=True)
        if re.search(r"\bsrc\s*=", tag, re.IGNORECASE):
            updated = re.sub(r"(\bsrc\s*=\s*)(\"[^\"]*\"|'[^']*'|[^\s>]+)", lambda item: item.group(1) + '"' + escaped + '"', tag, count=1, flags=re.IGNORECASE)
        else:
            insert_at = tag.rfind("/>") if tag.rstrip().endswith("/>") else tag.rfind(">")
            updated = tag[:insert_at] + ' src="' + escaped + '"' + tag[insert_at:]
        if is_primary and information["heading"]:
            current_alt = element.get("alt", "")
            if not current_alt or not (tokens(current_alt) & tokens(str(information["heading"]))):
                corrected_alt = html_text.escape(str(information["heading"]), quote=True)
                if re.search(r"\balt\s*=", updated, re.IGNORECASE):
                    updated = re.sub(r"(\balt\s*=\s*)(\"[^\"]*\"|'[^']*'|[^\s>]+)", lambda item: item.group(1) + '"' + corrected_alt + '"', updated, count=1, flags=re.IGNORECASE)
                else:
                    insert_at = updated.rfind("/>") if updated.rstrip().endswith("/>") else updated.rfind(">")
                    updated = updated[:insert_at] + ' alt="' + corrected_alt + '"' + updated[insert_at:]
                stats["primary_image_alt_corrected"] += 1
        changes.append((matches[index].start(), matches[index].end(), updated))
        stats["primary_images_repaired" if is_primary else "additional_images_repaired"] += 1

    if changes:
        for start, end, updated in reversed(changes):
            source = source[:start] + updated + source[end:]
        page.write_text(source, encoding="utf-8")
        stats["html_pages_repaired"] += 1

# These obsolete IE stylesheets and the theme helper were absent from the public
# snapshots. Their existing equivalents keep the theme assets self-contained.
for name in ("ie-8.min__q_9be4512521.css", "ie-9.min__q_9be4512521.css"):
    target = ROOT / "wp-content/themes/flatnews/assets/css/min" / name
    if not target.exists():
        target.write_text("/* Legacy Internet Explorer compatibility: original stylesheet unavailable. */\n", encoding="utf-8")
        stats["legacy_stylesheets_restored"] += 1
helper = ROOT / "wp-content/themes/zox-news/js/scripts.js"
for name in ("mvpcustom.js", "mvpcustom__q_4998ba8b3f.js"):
    target = helper.with_name(name)
    if not target.exists() and helper.exists():
        shutil.copyfile(helper, target)
        stats["theme_scripts_restored"] += 1

report = {
    "manifest_images_recovered": manifest_images_recovered,
    "known_attachment_ids": len(attachment_urls),
    "matched_image_alt_labels": len(alt_images),
    "assigned_missing_attachment_images": len(assigned_attachment_images),
    "available_image_families": len(families),
    **stats,
    "unresolved_primary_images": unresolved_primary,
}
(ROOT / "_recovery/image-repair-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({**report, "unresolved_primary_images": unresolved_primary[:12]}, ensure_ascii=False))
