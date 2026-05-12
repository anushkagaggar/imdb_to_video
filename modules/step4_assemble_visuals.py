"""
Step 4 — Assemble Visuals (TMDb-powered, multi-source)
Pulls movie stills from multiple TMDb endpoints to maximize unique images:

  1. /movie/{id}/images        — backdrops + posters (movie itself)
  2. /movie/{id}/credits       — cast list (for cast photos)
  3. /person/{id}/images       — actor profile photos
  4. /person/{id}/movie_credits — actor's other movies for related backdrops

Target: 120 unique images for a 2-minute video (1 image / second).
"""

import os
import json
import subprocess
import requests
import shutil
import random
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
TARGET_IMAGES = VIDEO_DURATION  # 120


# ── TMDb helpers ─────────────────────────────────────────────────────────────

def _auth_headers():
    if TMDB_BEARER:
        return {"Authorization": f"Bearer {TMDB_BEARER}", "accept": "application/json"}
    return {"accept": "application/json"}

def _auth_params():
    return {"api_key": TMDB_API_KEY} if TMDB_API_KEY and not TMDB_BEARER else {}

def _tmdb_get(path, params=None):
    params = dict(params or {})
    params.update(_auth_params())
    url = f"{TMDB_BASE}{path}"
    try:
        resp = requests.get(url, headers=_auth_headers(), params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[Step 4] TMDb {path} failed: {e}")
        return {}


# ── Image source: movie itself ───────────────────────────────────────────────

def fetch_movie_images(tmdb_id):
    """Get all backdrops + posters for the movie itself."""
    data = _tmdb_get(f"/movie/{tmdb_id}/images", {
        "include_image_language": "en,hi,ja,fr,es,de,it,null"
    })

    backdrops = []
    for img in data.get("backdrops", []):
        if img.get("file_path"):
            backdrops.append({
                "url":  f"{TMDB_IMG_BASE}/original{img['file_path']}",
                "vote": img.get("vote_average", 0),
                "category": "movie_backdrop",
            })
    backdrops.sort(key=lambda x: x["vote"], reverse=True)

    posters = []
    for img in data.get("posters", []):
        if img.get("file_path"):
            posters.append({
                "url":  f"{TMDB_IMG_BASE}/original{img['file_path']}",
                "vote": img.get("vote_average", 0),
                "category": "movie_poster",
            })
    posters.sort(key=lambda x: x["vote"], reverse=True)

    print(f"[Step 4] Movie: {len(backdrops)} backdrops + {len(posters)} posters")
    return backdrops, posters


# ── Image source: cast actors ────────────────────────────────────────────────

def fetch_cast_images(tmdb_id, max_actors=8):
    """
    Get profile photos of the top cast members.
    Also get backdrops from each actor's other movies for visual variety.
    """
    credits = _tmdb_get(f"/movie/{tmdb_id}/credits")
    cast_list = sorted(credits.get("cast", []), key=lambda c: c.get("order", 999))[:max_actors]

    all_images = []

    for actor in cast_list:
        person_id = actor.get("id")
        if not person_id:
            continue

        # Actor profile photos
        person_imgs = _tmdb_get(f"/person/{person_id}/images")
        profiles = person_imgs.get("profiles", [])

        for img in profiles[:5]:  # top 5 photos per actor
            if img.get("file_path"):
                all_images.append({
                    "url":  f"{TMDB_IMG_BASE}/original{img['file_path']}",
                    "vote": img.get("vote_average", 0),
                    "category": f"cast_{actor.get('name', 'actor')[:20]}",
                })

    print(f"[Step 4] Cast: {len(all_images)} actor photos from {len(cast_list)} actors")
    return all_images


# ── Image source: director's filmography ─────────────────────────────────────

def fetch_director_filmography_images(tmdb_id, max_movies=4):
    """
    Get backdrops from other movies by the same director.
    These share visual style with the target movie.
    """
    credits = _tmdb_get(f"/movie/{tmdb_id}/credits")

    director_id = None
    for crew in credits.get("crew", []):
        if crew.get("job") == "Director":
            director_id = crew.get("id")
            break

    if not director_id:
        return []

    # Get director's other movies
    person_credits = _tmdb_get(f"/person/{director_id}/movie_credits")
    other_movies = person_credits.get("crew", [])
    director_movies = [m for m in other_movies if m.get("job") == "Director"]
    director_movies = sorted(director_movies, key=lambda m: m.get("vote_average", 0), reverse=True)

    all_images = []
    for movie in director_movies[:max_movies]:
        m_id = movie.get("id")
        if not m_id or m_id == tmdb_id:
            continue
        imgs = _tmdb_get(f"/movie/{m_id}/images", {"include_image_language": "en,null"})
        for img in imgs.get("backdrops", [])[:6]:  # top 6 per related movie
            if img.get("file_path"):
                all_images.append({
                    "url":  f"{TMDB_IMG_BASE}/original{img['file_path']}",
                    "vote": img.get("vote_average", 0),
                    "category": f"director_{movie.get('title', '')[:25]}",
                })

    print(f"[Step 4] Director's other films: {len(all_images)} backdrops")
    return all_images


# ── Quality filter (lenient — TMDb images are curated) ───────────────────────

def passes_quality(path, min_w=200, min_h=200):
    """TMDb images are curated; we mainly need to reject tiny thumbnails."""
    try:
        img = Image.open(path)
        img.load()
        img = img.convert("RGB")
        if img.width < min_w or img.height < min_h:
            return False
        # Reject mostly-uniform images
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


# ── Trailer download ────────────────────────────────────────────────────────

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

    for f in os.listdir(IMG_DIR):
        p = os.path.join(IMG_DIR, f)
        if os.path.isfile(p):
            os.remove(p)

    tmdb_id = movie_data.get("tmdb_id")
    if not tmdb_id:
        raise RuntimeError("No tmdb_id in movie_data. Re-run Step 1.")

    # ── Gather images from ALL sources ────────────────────────────────────────
    print("[Step 4] Gathering images from multiple TMDb endpoints...")

    backdrops, posters = fetch_movie_images(tmdb_id)
    cast_images       = fetch_cast_images(tmdb_id, max_actors=8)
    director_images   = fetch_director_filmography_images(tmdb_id, max_movies=4)

    # Build download queue (priority order: movie backdrops > posters > cast > director)
    queue = []
    queue.extend([img["url"] for img in backdrops])
    queue.extend([img["url"] for img in posters])
    queue.extend([img["url"] for img in cast_images])
    queue.extend([img["url"] for img in director_images])

    # Deduplicate URLs while preserving order
    seen = set()
    unique_queue = []
    for url in queue:
        if url not in seen:
            seen.add(url)
            unique_queue.append(url)

    print(f"[Step 4] Total unique candidates: {len(unique_queue)}")

    # ── Download + filter ─────────────────────────────────────────────────────
    good_images = []
    counter = 0
    for url in unique_queue:
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
        if len(good_images) % 15 == 0:
            print(f"[Step 4] Downloaded {len(good_images)}/{TARGET_IMAGES} unique images...")

    if not good_images:
        raise RuntimeError("No images passed download/quality checks.")

    print(f"[Step 4] {len(good_images)} unique quality images collected")

    # ── Fill remaining slots with shuffled duplicates if needed ───────────────
    if len(good_images) < TARGET_IMAGES:
        print(f"[Step 4] Cycling {len(good_images)} images (shuffled) to fill {TARGET_IMAGES} slots")
        originals = good_images.copy()
        # Shuffle for variety — duplicates won't be consecutive
        shuffled_pool = []
        cycles_needed = (TARGET_IMAGES // len(originals)) + 1
        for _ in range(cycles_needed):
            cycle = originals.copy()
            random.shuffle(cycle)
            shuffled_pool.extend(cycle)

        dup_n = len(good_images)
        idx = 0
        while len(good_images) < TARGET_IMAGES:
            src = shuffled_pool[idx]
            dup_n += 1
            dest = os.path.join(IMG_DIR, f"dup_{dup_n:04d}.jpg")
            shutil.copy2(src, dest)
            good_images.append(dest)
            idx += 1

    # ── Build manifest: 1 image = 1 second ────────────────────────────────────
    assets = []
    for i, img_path in enumerate(good_images[:VIDEO_DURATION]):
        assets.append({
            "type": "image",
            "path": img_path,
            "start_sec": i,
            "end_sec": i + 1,
        })

    # ── Optional: trailer replaces last 30s ───────────────────────────────────
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