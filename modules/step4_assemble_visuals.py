"""
Step 4 — Assemble Visuals
Downloads poster + backdrop images from TMDb and trailer clips via yt-dlp (free).
Builds a manifest mapping each visual asset to a timestamp range.
"""

import os
import json
import subprocess
import requests
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY  = os.getenv("TMDB_API_KEY")
TMDB_IMG_BASE = "https://image.tmdb.org/t/p/w1280"
IMG_DIR       = "assets/images"
CLIP_DIR      = "assets/clips"
W, H          = 1280, 720


# ── Helpers ───────────────────────────────────────────────────────────────────

def download_image(url: str, dest: str) -> str | None:
    """Download an image from URL; return dest path or None on failure."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
        print(f"[Step 4] 📷 Downloaded → {dest}")
        return dest
    except Exception as e:
        print(f"[Step 4] ⚠️  Failed to download {url}: {e}")
        return None


def resize_image(path: str, width: int = W, height: int = H) -> str:
    """Resize image to video resolution (crop-to-fill)."""
    img = Image.open(path).convert("RGB")

    # Crop-to-fill: scale so shortest side fits, then centre-crop
    img_ratio    = img.width / img.height
    target_ratio = width / height

    if img_ratio > target_ratio:
        new_h = height
        new_w = int(img.width * height / img.height)
    else:
        new_w = width
        new_h = int(img.height * width / img.width)

    img    = img.resize((new_w, new_h), Image.LANCZOS)
    left   = (new_w - width)  // 2
    top    = (new_h - height) // 2
    img    = img.crop((left, top, left + width, top + height))
    img.save(path)
    return path


def create_title_card(movie_data: dict, path: str) -> str:
    """Generate a title card image with movie name, year, and rating."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img  = Image.new("RGB", (W, H), color=(10, 10, 10))
    draw = ImageDraw.Draw(img)

    # Dark overlay gradient effect via rectangles
    for i in range(H):
        alpha = int(180 * (1 - i / H))
        draw.line([(0, i), (W, i)], fill=(0, 0, 0))

    # Title text (centred)
    title   = movie_data["title"]
    year    = movie_data["year"]
    rating  = movie_data["rating"]
    director = movie_data["director"]

    try:
        font_large  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        font_small  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except Exception:
        font_large = font_medium = font_small = ImageFont.load_default()

    # Title
    bbox   = draw.textbbox((0, 0), title, font=font_large)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((W - tw) // 2, H // 2 - th - 30), title, font=font_large, fill=(255, 255, 255))

    # Year & Rating
    sub = f"{year}  •  ⭐ {rating}/10  •  Dir: {director}"
    bbox2 = draw.textbbox((0, 0), sub, font=font_small)
    sw    = bbox2[2] - bbox2[0]
    draw.text(((W - sw) // 2, H // 2 + 20), sub, font=font_small, fill=(200, 200, 200))

    img.save(path)
    print(f"[Step 4] 🎨 Title card → {path}")
    return path


def fetch_additional_stills(tmdb_id: int, count: int = 4) -> list[str]:
    """Download extra backdrop stills from TMDb images endpoint."""
    url    = f"https://api.themoviedb.org/3/movie/{tmdb_id}/images"
    resp   = requests.get(url, params={"api_key": TMDB_API_KEY}, timeout=10)
    paths  = []

    if resp.ok:
        backdrops = resp.json().get("backdrops", [])[:count]
        for i, b in enumerate(backdrops):
            img_url  = f"{TMDB_IMG_BASE}{b['file_path']}"
            dest     = f"{IMG_DIR}/still_{i+1}.jpg"
            result   = download_image(img_url, dest)
            if result:
                resize_image(result)
                paths.append(result)

    return paths


def download_trailer_clip(trailer_url: str, dest: str = f"{CLIP_DIR}/trailer.mp4") -> str | None:
    """Download trailer from YouTube using yt-dlp (free, no API key needed)."""
    if not trailer_url:
        print("[Step 4] ⚠️  No trailer URL available; skipping clip download.")
        return None

    os.makedirs(os.path.dirname(dest), exist_ok=True)

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
        "--merge-output-format", "mp4",
        "-o", dest,
        "--quiet",
        "--no-warnings",
        trailer_url,
    ]
    try:
        subprocess.run(cmd, check=True, timeout=120)
        print(f"[Step 4] 🎬 Trailer clip → {dest}")
        return dest
    except Exception as e:
        print(f"[Step 4] ⚠️  yt-dlp failed: {e}")
        return None


def build_visual_manifest(movie_data: dict) -> dict:
    """
    Orchestrate all visual downloads and return a manifest that maps
    each asset to a timeline segment for Step 5.
    """
    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(CLIP_DIR, exist_ok=True)

    assets = []

    # 1. Title card (0–10 s — HOOK)
    title_card = create_title_card(movie_data, f"{IMG_DIR}/title_card.jpg")
    assets.append({"type": "image", "path": title_card,    "start_sec": 0,  "end_sec": 10})

    # 2. Poster (10–30 s — CONTEXT)
    if movie_data.get("poster_url"):
        poster = download_image(movie_data["poster_url"], f"{IMG_DIR}/poster.jpg")
        if poster:
            resize_image(poster)
            assets.append({"type": "image", "path": poster, "start_sec": 10, "end_sec": 30})

    # 3. Backdrop (30–50 s — start of PLOT_TEASE)
    if movie_data.get("backdrop_url"):
        backdrop = download_image(movie_data["backdrop_url"], f"{IMG_DIR}/backdrop.jpg")
        if backdrop:
            resize_image(backdrop)
            assets.append({"type": "image", "path": backdrop, "start_sec": 30, "end_sec": 50})

    # 4. Additional stills (50–90 s)
    stills = fetch_additional_stills(movie_data["tmdb_id"], count=4)
    slice_len = 10
    for i, still in enumerate(stills):
        start = 50 + i * slice_len
        assets.append({"type": "image", "path": still,
                        "start_sec": start, "end_sec": min(start + slice_len, 90)})

    # 5. Trailer clip (90–120 s — CTA)
    trailer = download_trailer_clip(movie_data.get("trailer_url"))
    if trailer:
        assets.append({"type": "video", "path": trailer, "start_sec": 90, "end_sec": 120})
    else:
        # Fallback: reuse poster for CTA segment
        if movie_data.get("poster_url"):
            assets.append({"type": "image", "path": f"{IMG_DIR}/poster.jpg",
                           "start_sec": 90, "end_sec": 120})

    manifest = {
        "movie_title": movie_data["title"],
        "total_duration_sec": 120,
        "assets": assets,
    }

    manifest_path = "assets/visual_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"[Step 4] 📋 Visual manifest ({len(assets)} assets) → {manifest_path}")
    return manifest


if __name__ == "__main__":
    with open("assets/movie_data.json") as f:
        movie_data = json.load(f)

    manifest = build_visual_manifest(movie_data)
    print(json.dumps(manifest, indent=2))