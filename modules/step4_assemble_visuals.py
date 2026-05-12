"""
Step 4 — Assemble Visuals (TMDb, movie-only)
Pulls backdrops + posters strictly from the target movie via TMDb.
Each image displays for 6 seconds → 20 unique images for a 2-minute video.
"""

import os
import json
import subprocess
import requests
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
SECONDS_PER_IMAGE = 6
TARGET_IMAGES     = VIDEO_DURATION // SECONDS_PER_IMAGE  # 120 / 6 = 20


# ── TMDb helpers ─────────────────────────────────────────────────────────────

def _auth_headers():
    if TMDB_BEARER:
        return {"Authorization": f"Bearer {TMDB_BEARER}", "accept": "application/json"}
    return {"accept": "application/json"}

def _auth_params():
    return {"api_key": TMDB_API_KEY} if TMDB_API_KEY and not TMDB_BEARER else {}


def fetch_movie_images(tmdb_id):
    """Get all backdrops + posters for THIS movie only — no cast/director crossovers."""
    url = f"{TMDB_BASE}/movie/{tmdb_id}/images"
    params = dict(_auth_params())
    # All language variants of stills/posters for THIS movie
    params["include_image_language"] = "en,hi,ja,fr,es,de,it,null"

    resp = requests.get(url, headers=_auth_headers(), params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    backdrops = []
    for img in data.get("backdrops", []):
        if img.get("file_path"):
            backdrops.append({
                "url":  f"{TMDB_IMG_BASE}/original{img['file_path']}",
                "vote": img.get("vote_average", 0),
            })
    backdrops.sort(key=lambda x: x["vote"], reverse=True)

    posters = []
    for img in data.get("posters", []):
        if img.get("file_path"):
            posters.append({
                "url":  f"{TMDB_IMG_BASE}/original{img['file_path']}",
                "vote": img.get("vote_average", 0),
            })
    posters.sort(key=lambda x: x["vote"], reverse=True)

    print(f"[Step 4] TMDb has {len(backdrops)} backdrops + {len(posters)} posters for this movie")
    return backdrops, posters


# ── Quality filter ───────────────────────────────────────────────────────────

def passes_quality(path, min_w=300, min_h=200):
    try:
        img = Image.open(path)
        img.load()
        img = img.convert("RGB")
        if img.width < min_w or img.height < min_h:
            return False
        stat = ImageStat.Stat(img.resize((100, 100)))
        if sum(stat.stddev) / 3 < 8:
            return False
        return True
    except Exception:
        return False


# ── Download + resize ────────────────────────────────────────────────────────

def download_image(url, dest, timeout=25):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        r = requests.get(url, timeout=timeout)
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


# ── Trailer ──────────────────────────────────────────────────────────────────

def download_trailer(title, year, trailer_url=None, dest=None):
    if dest is None:
        dest = os.path.join(CLIP_DIR, "trailer.mp4")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    target = trailer_url if (trailer_url and "watch?v=" in trailer_url) \
             else f"ytsearch1:{title} {year} official trailer"
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
        print(f"[Step 4] Trailer failed: {e}")
        return None


# ── Manifest builder ────────────────────────────────────────────────────────

def build_visual_manifest(movie_data, apify_html=None):
    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(CLIP_DIR, exist_ok=True)

    # Clean
    for f in os.listdir(IMG_DIR):
        p = os.path.join(IMG_DIR, f)
        if os.path.isfile(p):
            os.remove(p)

    tmdb_id = movie_data.get("tmdb_id")
    if not tmdb_id:
        raise RuntimeError("No tmdb_id in movie_data. Re-run Step 1.")

    backdrops, posters = fetch_movie_images(tmdb_id)

    # Priority: backdrops (landscape, match video aspect) first, then posters
    queue = [b["url"] for b in backdrops] + [p["url"] for p in posters]

    if not queue:
        raise RuntimeError(f"TMDb has no images for this movie.")

    # Download top images until we have TARGET_IMAGES quality picks
    good_images = []
    counter = 0
    for url in queue:
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

    if not good_images:
        raise RuntimeError("All TMDb images failed download/quality checks.")

    print(f"[Step 4] {len(good_images)} unique movie-only images selected")

    # Build manifest — 6 seconds per image
    assets = []
    for i, img_path in enumerate(good_images):
        start = i * SECONDS_PER_IMAGE
        end   = (i + 1) * SECONDS_PER_IMAGE
        if start >= VIDEO_DURATION:
            break
        end = min(end, VIDEO_DURATION)
        assets.append({
            "type": "image",
            "path": img_path,
            "start_sec": start,
            "end_sec": end,
        })

    # If we have fewer than TARGET_IMAGES unique, extend last image to fill
    if assets and assets[-1]["end_sec"] < VIDEO_DURATION:
        assets[-1]["end_sec"] = VIDEO_DURATION

    # Try trailer (replaces last 30s if available)
    trailer = download_trailer(
        movie_data["title"], movie_data["year"],
        trailer_url=movie_data.get("trailer_url"),
    )
    if trailer:
        assets = [a for a in assets if a["end_sec"] <= 90]
        if assets and assets[-1]["end_sec"] < 90:
            assets[-1]["end_sec"] = 90
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

    print(f"[Step 4] Manifest: {len(assets)} assets ({SECONDS_PER_IMAGE}s each) -> {MANIFEST_PATH}")
    return manifest


if __name__ == "__main__":
    from config.settings import validate_secrets
    validate_secrets()
    with open("assets/movie_data.json") as f:
        movie_data = json.load(f)
    manifest = build_visual_manifest(movie_data)
    print(json.dumps(manifest, indent=2))