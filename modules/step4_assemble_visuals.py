"""
Step 4 — Assemble Visuals
Scrapes movie stills directly from IMDb media gallery (m.media-amazon.com).
Gets 30-40 high-resolution images guaranteed to be from the actual movie.
Applies quality filtering: rejects blurry, too-small, blank images.
"""

import os
import json
import subprocess
import requests
import re
import time
import numpy as np
from urllib.parse import quote_plus
from PIL import Image, ImageStat, ImageFilter
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


# ── Image Quality Filters ────────────────────────────────────────────────────

def is_blank_image(img: Image.Image, threshold: float = 15.0) -> bool:
    """Reject images that are mostly a single color (blank/placeholder)."""
    stat = ImageStat.Stat(img)
    # Low stddev across channels = mostly uniform color = blank
    avg_stddev = sum(stat.stddev) / len(stat.stddev)
    return avg_stddev < threshold


def is_blurry_image(img: Image.Image, threshold: float = 50.0) -> bool:
    """Reject blurry images using variance of Laplacian."""
    gray = img.convert("L")
    # Apply Laplacian-like edge detection
    edges = gray.filter(ImageFilter.FIND_EDGES)
    stat = ImageStat.Stat(edges)
    # Low variance = blurry
    variance = stat.var[0]
    return variance < threshold


def is_good_quality(path: str, min_width: int = 400, min_height: int = 300) -> bool:
    """Check if image passes all quality filters."""
    try:
        img = Image.open(path).convert("RGB")
        # Size check
        if img.width < min_width or img.height < min_height:
            return False
        # Blank check
        if is_blank_image(img):
            return False
        # Blur check
        if is_blurry_image(img):
            return False
        # Aspect ratio check — reject very tall/narrow images (portraits, banners)
        aspect = img.width / img.height
        if aspect < 0.5 or aspect > 3.0:
            return False
        return True
    except Exception:
        return False


# ── Image Download & Resize ──────────────────────────────────────────────────

def download_image(url: str, dest: str, timeout: int = 15) -> str | None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}
        r = requests.get(url, timeout=timeout, headers=headers)
        r.raise_for_status()
        ct = r.headers.get("content-type", "")
        if "image" not in ct and "octet" not in ct:
            return None
        data = r.content
        if len(data) < 5000:
            return None
        with open(dest, "wb") as f:
            f.write(data)
        return dest
    except Exception:
        if os.path.exists(dest):
            os.remove(dest)
        return None


def resize_image(path: str) -> str:
    """Crop-to-fill resize to 1080p, using high quality LANCZOS."""
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
        # Slight sharpen after resize to counteract LANCZOS softening
        img = img.filter(ImageFilter.SHARPEN)
        img.save(path, "JPEG", quality=95)
        return path
    except Exception:
        return path


# ── IMDb Gallery Scraper ─────────────────────────────────────────────────────

def scrape_imdb_gallery(imdb_id: str, count: int = 40) -> list[str]:
    """
    Scrape the IMDb media gallery page for a movie.
    Extracts m.media-amazon.com image codes and generates HD URLs.
    """
    gallery_url = f"https://www.imdb.com/title/{imdb_id}/mediaindex"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    print(f"[Step 4] Scraping IMDb gallery: {gallery_url}")

    try:
        resp = requests.get(gallery_url, headers=headers, timeout=20)
        resp.raise_for_status()
        html = resp.text

        # Extract all unique image codes from m.media-amazon.com URLs
        # Pattern: /images/M/{CODE}._V1_{params}_.jpg
        codes = re.findall(
            r'src="https://m\.media-amazon\.com/images/M/(MV5B[^"]+?)(?:\._V1_[^"]+)"',
            html
        )

        # Deduplicate while preserving order
        seen = set()
        unique_codes = []
        for code in codes:
            # Normalize: strip any existing _V1_ suffix
            base = re.sub(r'\._V1_.*$', '', code)
            if base not in seen:
                seen.add(base)
                unique_codes.append(base)

        print(f"[Step 4] Found {len(unique_codes)} unique images in IMDb gallery")

        # Generate high-resolution URLs (1920px wide for 1080p video)
        hd_urls = []
        for code in unique_codes[:count]:
            url = f"https://m.media-amazon.com/images/M/{code}._V1_QL75_UX1920_.jpg"
            hd_urls.append(url)

        return hd_urls

    except Exception as e:
        print(f"[Step 4] IMDb gallery scrape failed: {e}")
        return []


def download_and_filter_images(urls: list[str], count: int = TARGET_IMAGES) -> list[str]:
    """Download images, apply quality filtering, resize to 1080p."""
    downloaded = []
    img_counter = 0

    for url in urls:
        if len(downloaded) >= count:
            break

        img_counter += 1
        dest = os.path.join(IMG_DIR, f"still_{img_counter:03d}.jpg")
        result = download_image(url, dest)

        if not result:
            continue

        # Quality filter BEFORE resize
        if not is_good_quality(result):
            os.remove(result)
            print(f"[Step 4] Rejected (quality) -> {os.path.basename(dest)}")
            continue

        # Resize to exact 1080p
        resize_image(result)
        downloaded.append(result)
        print(f"[Step 4] Image {len(downloaded):02d}/{count} -> {os.path.basename(dest)}")

    return downloaded


# ── Fallback: Bing Image Search ──────────────────────────────────────────────

def bing_image_search(query: str, num: int = 15) -> list[str]:
    """Fallback: scrape from Bing if IMDb gallery fails."""
    url = f"https://www.bing.com/images/search?q={quote_plus(query)}&form=HDRSC3&first=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        matches = re.findall(r'murl&quot;:&quot;(https?://[^&]+?)&quot;', resp.text)
        img_urls = []
        for m in matches:
            if any(skip in m.lower() for skip in ["bing.", "microsoft.", "favicon", "icon", "logo"]):
                continue
            if m not in img_urls:
                img_urls.append(m)
            if len(img_urls) >= num:
                break
        return img_urls
    except Exception:
        return []


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

    # 1. Primary: IMDb gallery (guaranteed accurate movie images)
    imdb_id = movie_data.get("imdb_id", "")
    if imdb_id:
        imdb_urls = scrape_imdb_gallery(imdb_id, count=45)
        if imdb_urls:
            all_images = download_and_filter_images(imdb_urls, count=TARGET_IMAGES)

    # 2. Fallback: OMDb poster + Bing search
    if len(all_images) < 10:
        print(f"[Step 4] IMDb gallery yielded {len(all_images)} images, trying Bing fallback...")
        if movie_data.get("poster_url"):
            pp = download_image(movie_data["poster_url"], os.path.join(IMG_DIR, "poster.jpg"))
            if pp and is_good_quality(pp):
                resize_image(pp)
                all_images.insert(0, pp)

        queries = [
            f"{movie_data['title']} {movie_data['year']} movie stills HD",
            f"{movie_data['title']} {movie_data['year']} movie scenes",
            f"{movie_data['title']} movie wallpaper 1080p",
        ]
        img_counter = len(all_images)
        for query in queries:
            if len(all_images) >= TARGET_IMAGES:
                break
            urls = bing_image_search(query, num=15)
            for url in urls:
                if len(all_images) >= TARGET_IMAGES:
                    break
                img_counter += 1
                dest = os.path.join(IMG_DIR, f"still_{img_counter:03d}.jpg")
                result = download_image(url, dest)
                if result and is_good_quality(result):
                    resize_image(result)
                    all_images.append(result)
                elif result:
                    os.remove(result)

    if not all_images:
        raise RuntimeError("No images found. Check internet connection or try a different movie.")

    print(f"[Step 4] Final image count: {len(all_images)}")

    # Distribute evenly across video duration
    total = len(all_images)
    dur_each = VIDEO_DURATION / total
    assets = []
    for i, img_path in enumerate(all_images):
        start = round(i * dur_each, 2)
        end   = round((i + 1) * dur_each, 2)
        assets.append({"type": "image", "path": img_path, "start_sec": start, "end_sec": end})

    # Try trailer — replace last 30s if available
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