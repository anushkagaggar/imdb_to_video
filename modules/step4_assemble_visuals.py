"""
Step 4 — Assemble Visuals (Fully Automated)
Works for ANY movie, from ANY region (including India).

Image sources (in order):
1. OMDb poster (always available)
2. Google Images via Bing scraping (movie title + stills/scenes queries)
3. Quality filtering: rejects blank, blurry, wrong-aspect, too-small images

Target: 120 images (1 per second for 2-minute video)
"""

import os
import json
import subprocess
import requests
import re
import time
import shutil
import hashlib
from urllib.parse import quote_plus, urlparse
from PIL import Image, ImageStat, ImageFilter, ImageDraw, ImageFont
from config.settings import (
    IMG_DIR,
    CLIP_DIR,
    MANIFEST_PATH,
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
    VIDEO_DURATION,
)

W, H = VIDEO_WIDTH, VIDEO_HEIGHT
TARGET_IMAGES = VIDEO_DURATION  # 1 image per second = 120 images

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


# ══════════════════════════════════════════════════════════════════════════════
#  IMAGE QUALITY FILTERS
# ══════════════════════════════════════════════════════════════════════════════

def is_blank_or_solid(img, threshold=20.0):
    """Reject mostly-uniform-color images."""
    stat = ImageStat.Stat(img.resize((100, 100)))  # downscale for speed
    return sum(stat.stddev) / len(stat.stddev) < threshold

def has_enough_detail(img, threshold=30.0):
    """Reject blurry/featureless images via edge detection."""
    gray = img.convert("L").resize((200, 200))
    edges = gray.filter(ImageFilter.FIND_EDGES)
    return ImageStat.Stat(edges).var[0] >= threshold

def is_good_aspect(img):
    """Reject extremely tall/narrow images."""
    r = img.width / img.height
    return 0.5 <= r <= 3.0

def passes_quality(path, min_w=350, min_h=250):
    """Full quality check pipeline. Returns True if image is usable."""
    try:
        img = Image.open(path)
        img.load()
        img = img.convert("RGB")
        if img.width < min_w or img.height < min_h:
            return False
        if not is_good_aspect(img):
            return False
        if is_blank_or_solid(img):
            return False
        if not has_enough_detail(img):
            return False
        return True
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  IMAGE DOWNLOAD & RESIZE
# ══════════════════════════════════════════════════════════════════════════════

def download_image(url, dest, timeout=20):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        r = requests.get(url, timeout=timeout, headers=HEADERS)
        r.raise_for_status()
        if len(r.content) < 3000:
            return None
        with open(dest, "wb") as f:
            f.write(r.content)
        return dest
    except Exception:
        if os.path.exists(dest):
            os.remove(dest)
        return None


def resize_to_1080p(path):
    """Crop-to-fill resize to exact 1920x1080, then sharpen."""
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
        img = img.filter(ImageFilter.SHARPEN)
        img.save(path, "JPEG", quality=95)
        return path
    except Exception:
        return path


# ══════════════════════════════════════════════════════════════════════════════
#  IMAGE SEARCH — MULTI-ENGINE (Bing primary, DuckDuckGo fallback)
# ══════════════════════════════════════════════════════════════════════════════

def _bing_image_search(query, num=20):
    """Bing Image Search — reliable from India."""
    url = f"https://www.bing.com/images/search?q={quote_plus(query)}&form=HDRSC3&first=1&count={num}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        # Bing embeds original URLs in murl parameter
        matches = re.findall(r'murl&quot;:&quot;(https?://[^&]+?)&quot;', resp.text)
        results = []
        skip = {"bing.", "microsoft.", "favicon", "icon", "logo", "badge", "pixel",
                "transparent", "placeholder", "avatar", "emoji", "social", "share"}
        for m in matches:
            if any(s in m.lower() for s in skip):
                continue
            if m not in results:
                results.append(m)
            if len(results) >= num:
                break
        return results
    except Exception as e:
        print(f"[Step 4] Bing failed for '{query}': {e}")
        return []


def _bing_page2(query, num=20):
    """Bing page 2 for more results."""
    url = f"https://www.bing.com/images/search?q={quote_plus(query)}&form=HDRSC3&first=35&count={num}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        matches = re.findall(r'murl&quot;:&quot;(https?://[^&]+?)&quot;', resp.text)
        results = []
        skip = {"bing.", "microsoft.", "favicon", "icon", "logo", "badge", "pixel",
                "transparent", "placeholder", "avatar", "emoji", "social", "share"}
        for m in matches:
            if any(s in m.lower() for s in skip):
                continue
            if m not in results:
                results.append(m)
            if len(results) >= num:
                break
        return results
    except Exception:
        return []


def search_movie_images(title, year, num=20):
    """Search Bing for movie stills with multiple queries."""
    all_urls = []
    seen = set()

    urls = _bing_image_search(f'"{title}" {year} movie stills HD', num)
    for u in urls:
        if u not in seen:
            seen.add(u)
            all_urls.append(u)

    if len(all_urls) < num:
        urls = _bing_image_search(f'"{title}" {year} movie scenes screenshots', num)
        for u in urls:
            if u not in seen:
                seen.add(u)
                all_urls.append(u)

    return all_urls


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN IMAGE PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def collect_movie_images(movie_data, target=TARGET_IMAGES):
    """
    Fully automated image collection for any movie.
    Returns list of file paths to quality-checked, 1080p-resized images.
    """
    title = movie_data["title"]
    year  = movie_data["year"]
    cast  = movie_data.get("cast", [])

    # Build diverse search queries for maximum coverage
    queries = [
        f'"{title}" {year} movie stills',
        f'"{title}" {year} movie scenes HD',
        f'"{title}" {year} movie screenshots',
        f'"{title}" {year} film cinematography',
        f'"{title}" movie wallpaper HD 1080',
        f'"{title}" {year} movie poster',
        f'"{title}" {year} behind the scenes',
        f'"{title}" {year} movie frames',
        f'"{title}" movie iconic moments',
    ]
    # Add cast-specific queries for actor shots from the movie
    for actor in cast[:3]:
        queries.append(f'{actor} "{title}" {year} movie still')

    all_urls = []
    seen_urls = set()

    for query in queries:
        if len(all_urls) >= target * 2:  # get 2x candidates for filtering
            break

        print(f"[Step 4] Searching: {query[:60]}...")
        urls = _bing_image_search(query, num=20)

        # Also get page 2 for first 3 queries
        if queries.index(query) < 3:
            urls += _bing_page2(query, num=15)

        for url in urls:
            if url not in seen_urls:
                seen_urls.add(url)
                all_urls.append(url)

        time.sleep(0.3)

    print(f"[Step 4] Found {len(all_urls)} candidate URLs, downloading & filtering...")

    # Download, quality-filter, and resize
    good_images = []
    counter = 0

    # Always start with OMDb poster if available
    if movie_data.get("poster_url"):
        poster_dest = os.path.join(IMG_DIR, "poster.jpg")
        result = download_image(movie_data["poster_url"], poster_dest)
        if result and passes_quality(result):
            resize_to_1080p(result)
            good_images.append(result)
            print(f"[Step 4] OMDb poster -> {os.path.basename(result)}")

    for url in all_urls:
        if len(good_images) >= target:
            break

        counter += 1
        ext = ".jpg"
        for e in [".png", ".webp", ".jpeg"]:
            if e in urlparse(url).path.lower():
                ext = e
                break
        dest = os.path.join(IMG_DIR, f"still_{counter:04d}{ext}")
        result = download_image(url, dest)

        if not result:
            continue

        if not passes_quality(result):
            os.remove(result)
            continue

        resize_to_1080p(result)
        good_images.append(result)

        if len(good_images) % 10 == 0:
            print(f"[Step 4] Quality images: {len(good_images)}/{target}")

    print(f"[Step 4] Got {len(good_images)} quality-verified images")
    return good_images


# ══════════════════════════════════════════════════════════════════════════════
#  TRAILER DOWNLOAD
# ══════════════════════════════════════════════════════════════════════════════

def download_trailer(title, year, dest=None):
    if dest is None:
        dest = os.path.join(CLIP_DIR, "trailer.mp4")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    cmd = [
        "yt-dlp", "--no-playlist",
        "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]",
        "--merge-output-format", "mp4",
        "-o", dest, "--quiet", "--no-warnings",
        f"ytsearch1:{title} {year} official trailer",
    ]
    try:
        subprocess.run(cmd, check=True, timeout=120)
        print(f"[Step 4] Trailer downloaded -> {dest}")
        return dest
    except Exception as e:
        print(f"[Step 4] Trailer download failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  MANIFEST BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def build_visual_manifest(movie_data, apify_html=None):
    """
    Fully automated manifest builder.
    Works for any movie, any region.
    """
    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(CLIP_DIR, exist_ok=True)

    # Clean old stills
    for f in os.listdir(IMG_DIR):
        if f.startswith("still_") or f == "poster.jpg":
            os.remove(os.path.join(IMG_DIR, f))

    # Collect images
    images = collect_movie_images(movie_data, target=TARGET_IMAGES)

    if not images:
        raise RuntimeError("Failed to collect any usable images. Check internet connection.")

    # Duplicate to fill 120 slots if we got fewer
    if len(images) < TARGET_IMAGES:
        print(f"[Step 4] Cycling {len(images)} images to fill {TARGET_IMAGES} slots...")
        original = images.copy()
        idx = 0
        dup_n = len(images)
        while len(images) < TARGET_IMAGES:
            src = original[idx % len(original)]
            dup_n += 1
            dest = os.path.join(IMG_DIR, f"dup_{dup_n:04d}.jpg")
            shutil.copy2(src, dest)
            images.append(dest)
            idx += 1

    print(f"[Step 4] Final: {len(images)} frames @ 1 fps = {len(images)}s video")

    # Build manifest: 1 image = 1 second
    assets = []
    for i, img_path in enumerate(images[:VIDEO_DURATION]):
        assets.append({
            "type": "image",
            "path": img_path,
            "start_sec": i,
            "end_sec": i + 1,
        })

    # Try trailer (replace last 30s if available)
    trailer = download_trailer(movie_data["title"], movie_data["year"])
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

    print(f"[Step 4] Manifest: {len(assets)} assets -> {MANIFEST_PATH}")
    return manifest


if __name__ == "__main__":
    from config.settings import validate_secrets
    validate_secrets()
    with open("assets/movie_data.json") as f:
        movie_data = json.load(f)
    manifest = build_visual_manifest(movie_data)
    print(json.dumps(manifest, indent=2))