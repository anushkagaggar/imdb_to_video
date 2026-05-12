"""
Step 4 — Assemble Visuals (TMDb-powered)
Pulls actual movie stills from TMDb's /movie/{id}/images endpoint.

Image categories from TMDb:
  - backdrops  : landscape stills from the actual movie (10-40 per film)
  - posters    : movie posters in many languages
  - logos      : movie logos (skipped)

All images served from image.tmdb.org — global CDN, NOT geo-blocked.
Target: 120 images (1 per second for 2-minute video).
"""

import os
import json
import subprocess
import requests
import shutil
from PIL import Image, ImageStat, ImageFilter
from config.settings import (
    TMDB_BEARER,
    TMDB_API_KEY,
    TMDB_BASE,
    TMDB_IMG_BASE,
    IMG_DIR,
    CLIP_DIR,
    MANIFEST_PATH,
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
    VIDEO_DURATION,
)

W, H = VIDEO_WIDTH, VIDEO_HEIGHT
TARGET_IMAGES = VIDEO_DURATION  # 1 image per second


# ── TMDb helpers ─────────────────────────────────────────────────────────────

def _auth_headers():
    if TMDB_BEARER:
        return {"Authorization": f"Bearer {TMDB_BEARER}", "accept": "application/json"}
    return {"accept": "application/json"}

def _auth_params():
    return {"api_key": TMDB_API_KEY} if TMDB_API_KEY and not TMDB_BEARER else {}


def fetch_tmdb_images(tmdb_id):
    """
    Get all images for a movie from TMDb.
    Returns dict with 'backdrops' and 'posters' lists of full URLs (no language filter).
    """
    url = f"{TMDB_BASE}/movie/{tmdb_id}/images"
    params = dict(_auth_params())
    # include_image_language=null returns images without language tag (most stills)
    params["include_image_language"] = "en,hi,null"
    resp = requests.get(url, headers=_auth_headers(), params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    backdrops = []
    for img in data.get("backdrops", []):
        if img.get("file_path"):
            # Sort by vote_average — best images first
            backdrops.append({
                "url":  f"{TMDB_IMG_BASE}/original{img['file_path']}",
                "vote": img.get("vote_average", 0),
                "w":    img.get("width", 0),
                "h":    img.get("height", 0),
            })
    backdrops.sort(key=lambda x: x["vote"], reverse=True)

    posters = []
    for img in data.get("posters", []):
        if img.get("file_path"):
            posters.append({
                "url":  f"{TMDB_IMG_BASE}/original{img['file_path']}",
                "vote": img.get("vote_average", 0),
                "w":    img.get("width", 0),
                "h":    img.get("height", 0),
            })
    posters.sort(key=lambda x: x["vote"], reverse=True)

    print(f"[Step 4] TMDb returned {len(backdrops)} backdrops + {len(posters)} posters")
    return backdrops, posters


# ── Image quality filters ────────────────────────────────────────────────────

def passes_quality(path, min_w=400, min_h=300):
    """All TMDb images are curated, so we only need light filtering."""
    try:
        img = Image.open(path)
        img.load()
        img = img.convert("RGB")
        if img.width < min_w or img.height < min_h:
            return False
        # Reject mostly-uniform (very unlikely from TMDb but cheap to check)
        stat = ImageStat.Stat(img.resize((100, 100)))
        if sum(stat.stddev) / 3 < 10:
            return False
        return True
    except Exception:
        return False


# ── Image download & resize ──────────────────────────────────────────────────

def download_image(url, dest, timeout=25):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        if len(r.content) < 5000:
            return None
        with open(dest, "wb") as f:
            f.write(r.content)
        return dest
    except Exception as e:
        if os.path.exists(dest):
            os.remove(dest)
        return None


def resize_to_1080p(path):
    """Crop-to-fill resize to exact 1920x1080 + sharpen."""
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


# ── Trailer download ────────────────────────────────────────────────────────

def download_trailer(title, year, trailer_url=None, dest=None):
    if dest is None:
        dest = os.path.join(CLIP_DIR, "trailer.mp4")
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    # Prefer direct YouTube URL from TMDb (more reliable than search)
    target = trailer_url if (trailer_url and "watch?v=" in trailer_url) else f"ytsearch1:{title} {year} official trailer"

    cmd = [
        "yt-dlp", "--no-playlist",
        "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]",
        "--merge-output-format", "mp4",
        "-o", dest, "--quiet", "--no-warnings",
        target,
    ]
    try:
        subprocess.run(cmd, check=True, timeout=120)
        print(f"[Step 4] Trailer -> {dest}")
        return dest
    except Exception as e:
        print(f"[Step 4] Trailer download failed: {e}")
        return None


# ── Main manifest builder ────────────────────────────────────────────────────

def build_visual_manifest(movie_data, apify_html=None):
    """
    Build visual manifest using TMDb images.
    Returns manifest dict and writes JSON to disk.
    """
    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(CLIP_DIR, exist_ok=True)

    # Clean old assets
    for f in os.listdir(IMG_DIR):
        path = os.path.join(IMG_DIR, f)
        if os.path.isfile(path):
            os.remove(path)

    tmdb_id = movie_data.get("tmdb_id")
    if not tmdb_id:
        raise RuntimeError("No tmdb_id in movie_data. Re-run Step 1 with TMDb.")

    # Fetch image list from TMDb
    backdrops, posters = fetch_tmdb_images(tmdb_id)

    if not backdrops and not posters:
        raise RuntimeError(f"TMDb has no images for movie {tmdb_id}")

    # Build download queue: backdrops first (landscape, fit video aspect), then posters
    download_queue = [b["url"] for b in backdrops] + [p["url"] for p in posters]
    print(f"[Step 4] Will download up to {len(download_queue)} candidate images")

    # Download with quality check
    good_images = []
    counter = 0
    for url in download_queue:
        if len(good_images) >= TARGET_IMAGES:
            break
        counter += 1
        dest = os.path.join(IMG_DIR, f"still_{counter:04d}.jpg")
        result = download_image(url, dest)
        if not result:
            continue
        if not passes_quality(result):
            os.remove(result)
            continue
        resize_to_1080p(result)
        good_images.append(result)
        if len(good_images) % 10 == 0:
            print(f"[Step 4] Downloaded {len(good_images)}/{TARGET_IMAGES} images...")

    if not good_images:
        raise RuntimeError("All TMDb images failed download/quality checks.")

    print(f"[Step 4] {len(good_images)} unique quality images from TMDb")

    # Cycle through to fill 120 slots — each unique image appears ~3-4 times
    if len(good_images) < TARGET_IMAGES:
        print(f"[Step 4] Cycling {len(good_images)} images to fill {TARGET_IMAGES} slots...")
        originals = good_images.copy()
        idx = 0
        dup_n = len(good_images)
        while len(good_images) < TARGET_IMAGES:
            src = originals[idx % len(originals)]
            dup_n += 1
            dest = os.path.join(IMG_DIR, f"dup_{dup_n:04d}.jpg")
            shutil.copy2(src, dest)
            good_images.append(dest)
            idx += 1

    # Build manifest: 1 image = 1 second
    assets = []
    for i, img_path in enumerate(good_images[:VIDEO_DURATION]):
        assets.append({
            "type": "image",
            "path": img_path,
            "start_sec": i,
            "end_sec": i + 1,
        })

    # Optional: download trailer and replace last 30s
    trailer = download_trailer(
        movie_data["title"], movie_data["year"],
        trailer_url=movie_data.get("trailer_url"),
    )
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