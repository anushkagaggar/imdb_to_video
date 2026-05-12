"""
Step 4 — Assemble Visuals
Downloads 30-40 movie stills from multiple sources (Bing, DuckDuckGo, OMDb).
Falls back gracefully between sources.
"""

import os
import json
import subprocess
import requests
import re
import time
from urllib.parse import urlparse, quote_plus
from PIL import Image
from config.settings import (
    IMG_DIR,
    CLIP_DIR,
    MANIFEST_PATH,
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
    VIDEO_DURATION,
)

W, H = VIDEO_WIDTH, VIDEO_HEIGHT
TARGET_IMAGES = 35


# ── Image Helpers ────────────────────────────────────────────────────────────

def download_image(url: str, dest: str, timeout: int = 15) -> str | None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}
        r = requests.get(url, timeout=timeout, headers=headers, stream=True)
        r.raise_for_status()
        ct = r.headers.get("content-type", "")
        if "image" not in ct and "octet" not in ct:
            return None
        data = r.content
        if len(data) < 5000:
            return None
        with open(dest, "wb") as f:
            f.write(data)
        img = Image.open(dest)
        img.load()
        if img.width < 300 or img.height < 200:
            os.remove(dest)
            return None
        return dest
    except Exception:
        if os.path.exists(dest):
            os.remove(dest)
        return None


def resize_image(path: str) -> str:
    try:
        img = Image.open(path).convert("RGB")
        ir = img.width / img.height
        tr = W / H
        if ir > tr:
            new_h, new_w = H, int(img.width * H / img.height)
        else:
            new_w, new_h = W, int(img.height * W / img.width)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - W) // 2
        top  = (new_h - H) // 2
        img = img.crop((left, top, left + W, top + H))
        img.save(path, "JPEG", quality=95)
        return path
    except Exception:
        return path


# ── Image Search Methods (multiple fallbacks) ───────────────────────────────

def _bing_image_search(query: str, num: int = 15) -> list[str]:
    """Scrape image URLs from Bing Images — much less restrictive than Google."""
    url = f"https://www.bing.com/images/search?q={quote_plus(query)}&form=HDRSC3&first=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        text = resp.text
        img_urls = []
        # Bing stores original image URLs in murl attribute
        matches = re.findall(r'murl&quot;:&quot;(https?://[^&]+?)&quot;', text)
        for m in matches:
            if any(skip in m.lower() for skip in ["bing.", "microsoft.", "favicon", "icon", "logo", "badge", "pixel"]):
                continue
            if m not in img_urls:
                img_urls.append(m)
            if len(img_urls) >= num:
                break
        return img_urls[:num]
    except Exception as e:
        print(f"[Step 4] Bing search failed for '{query}': {e}")
        return []


def _duckduckgo_image_search(query: str, num: int = 15) -> list[str]:
    """Scrape image URLs from DuckDuckGo — another fallback."""
    # DDG uses a token-based API
    token_url = "https://duckduckgo.com/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    }
    try:
        # Get vqd token
        resp = requests.get(token_url, params={"q": query}, headers=headers, timeout=10)
        vqd_match = re.search(r'vqd=(["\'])([^"\']+)\1', resp.text)
        if not vqd_match:
            vqd_match = re.search(r'vqd=([\d-]+)', resp.text)
        if not vqd_match:
            return []
        vqd = vqd_match.group(2) if vqd_match.lastindex == 2 else vqd_match.group(1)

        api_url = "https://duckduckgo.com/i.js"
        params = {"l": "us-en", "o": "json", "q": query, "vqd": vqd, "f": ",,,,,", "p": "1"}
        resp2 = requests.get(api_url, params=params, headers=headers, timeout=10)
        data = resp2.json()

        img_urls = []
        for result in data.get("results", []):
            img_url = result.get("image", "")
            if img_url and img_url.startswith("http"):
                img_urls.append(img_url)
            if len(img_urls) >= num:
                break
        return img_urls[:num]
    except Exception as e:
        print(f"[Step 4] DuckDuckGo search failed for '{query}': {e}")
        return []


def _google_image_search(query: str, num: int = 10) -> list[str]:
    """Google Images fallback."""
    url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=isch&safe=active"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        text = resp.text
        img_urls = []
        matches = re.findall(r'"(https?://[^"]+\.(?:jpg|jpeg|png|webp)(?:\?[^"]*)?)"', text, re.IGNORECASE)
        for m in matches:
            if any(skip in m.lower() for skip in ["google", "gstatic", "encrypted-tbn", "favicon", "icon", "logo"]):
                continue
            if m not in img_urls:
                img_urls.append(m)
            if len(img_urls) >= num:
                break
        return img_urls[:num]
    except Exception:
        return []


def search_images(query: str, num: int = 15) -> list[str]:
    """Try multiple search engines, return combined unique URLs."""
    all_urls = []
    seen = set()

    # Try Bing first (most reliable)
    print(f"[Step 4] Searching Bing: {query}")
    for url in _bing_image_search(query, num):
        if url not in seen:
            seen.add(url)
            all_urls.append(url)

    # If Bing didn't return enough, try DuckDuckGo
    if len(all_urls) < num:
        print(f"[Step 4] Searching DuckDuckGo: {query}")
        for url in _duckduckgo_image_search(query, num):
            if url not in seen:
                seen.add(url)
                all_urls.append(url)

    # Last resort: Google
    if len(all_urls) < num // 2:
        print(f"[Step 4] Searching Google: {query}")
        for url in _google_image_search(query, num):
            if url not in seen:
                seen.add(url)
                all_urls.append(url)

    return all_urls


# ── Main Scraper ─────────────────────────────────────────────────────────────

def scrape_movie_images(movie_title: str, year: str, count: int = TARGET_IMAGES) -> list[str]:
    queries = [
        f"{movie_title} {year} movie stills HD",
        f"{movie_title} {year} movie scenes",
        f"{movie_title} {year} movie screenshots",
        f"{movie_title} {year} cinematography",
        f"{movie_title} movie wallpaper HD",
        f"{movie_title} {year} film poster",
        f"{movie_title} movie behind the scenes",
    ]

    downloaded = []
    seen_urls = set()
    img_counter = 0

    for query in queries:
        if len(downloaded) >= count:
            break
        urls = search_images(query, num=12)
        for url in urls:
            if len(downloaded) >= count:
                break
            if url in seen_urls:
                continue
            seen_urls.add(url)
            img_counter += 1
            ext = _get_ext(url)
            dest = os.path.join(IMG_DIR, f"still_{img_counter:03d}{ext}")
            result = download_image(url, dest)
            if result:
                try:
                    resize_image(result)
                    downloaded.append(result)
                    print(f"[Step 4] Image {len(downloaded):02d}/{count} -> {os.path.basename(dest)}")
                except Exception:
                    if os.path.exists(dest):
                        os.remove(dest)
        time.sleep(0.5)

    print(f"[Step 4] Total scraped: {len(downloaded)} movie images")
    return downloaded


def _get_ext(url: str) -> str:
    path = urlparse(url).path.lower()
    for ext in [".png", ".webp", ".jpeg", ".jpg"]:
        if ext in path:
            return ext
    return ".jpg"


# ── Trailer download ────────────────────────────────────────────────────────

def download_trailer_via_yt_dlp(movie_title: str, year: str, dest: str = None) -> str | None:
    if dest is None:
        dest = os.path.join(CLIP_DIR, "trailer.mp4")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    query = f"ytsearch1:{movie_title} {year} official trailer"
    cmd = [
        "yt-dlp", "--no-playlist",
        "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]",
        "--merge-output-format", "mp4",
        "-o", dest, "--quiet", "--no-warnings",
        query,
    ]
    try:
        subprocess.run(cmd, check=True, timeout=120)
        print(f"[Step 4] Trailer -> {dest}")
        return dest
    except Exception as e:
        print(f"[Step 4] yt-dlp failed: {e} (pipeline continues with images only)")
        return None


# ── Manifest builder ────────────────────────────────────────────────────────

def build_visual_manifest(movie_data: dict) -> dict:
    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(CLIP_DIR, exist_ok=True)

    # Clean old stills
    for f in os.listdir(IMG_DIR):
        if f.startswith("still_"):
            os.remove(os.path.join(IMG_DIR, f))

    all_images = []

    # 1. OMDb poster first
    if movie_data.get("poster_url"):
        pp = download_image(movie_data["poster_url"], os.path.join(IMG_DIR, "poster.jpg"))
        if pp:
            resize_image(pp)
            all_images.append(pp)

    # 2. Scrape from web
    scraped = scrape_movie_images(movie_data["title"], movie_data["year"], count=TARGET_IMAGES)
    all_images.extend(scraped)

    if not all_images:
        raise RuntimeError("No images found. Check internet connection or try a different movie.")

    # Distribute evenly
    total = len(all_images)
    dur_each = VIDEO_DURATION / total
    assets = []
    for i, img_path in enumerate(all_images):
        start = round(i * dur_each, 2)
        end   = round((i + 1) * dur_each, 2)
        assets.append({"type": "image", "path": img_path, "start_sec": start, "end_sec": end})

    # Try trailer
    trailer = download_trailer_via_yt_dlp(movie_data["title"], movie_data["year"])
    if trailer:
        assets = [a for a in assets if a["end_sec"] <= 90]
        assets.append({"type": "video", "path": trailer, "start_sec": 90, "end_sec": 120})

    manifest = {
        "movie_title":        movie_data["title"],
        "total_duration_sec": VIDEO_DURATION,
        "total_assets":       len(assets),
        "assets":             assets,
    }

    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"[Step 4] Visual manifest ({len(assets)} assets) -> {MANIFEST_PATH}")
    return manifest


if __name__ == "__main__":
    from config.settings import validate_secrets
    validate_secrets()
    with open("assets/movie_data.json") as f:
        movie_data = json.load(f)
    manifest = build_visual_manifest(movie_data)
    print(json.dumps(manifest, indent=2))