"""
Step 4 — Assemble Visuals
Downloads poster from OMDb and trailer via yt-dlp (both free, no extra keys).
Generates title card and cast card locally using Pillow.
Builds a manifest mapping each visual asset to a timestamp range.
"""

import os
import json
import subprocess
import requests
from PIL import Image, ImageDraw, ImageFont
from config.settings import (
    OMDB_API_KEY,
    IMG_DIR,
    CLIP_DIR,
    MANIFEST_PATH,
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
)

W, H = VIDEO_WIDTH, VIDEO_HEIGHT


# ── Image helpers ─────────────────────────────────────────────────────────────

def download_image(url: str, dest: str) -> str | None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
        print(f"[Step 4] Downloaded image -> {dest}")
        return dest
    except Exception as e:
        print(f"[Step 4] Image download failed: {e}")
        return None


def resize_image(path: str) -> str:
    """Crop-to-fill resize to video resolution."""
    img = Image.open(path).convert("RGB")
    ir  = img.width / img.height
    tr  = W / H
    if ir > tr:
        new_h, new_w = H, int(img.width * H / img.height)
    else:
        new_w, new_h = W, int(img.height * W / img.width)
    img  = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - W) // 2
    top  = (new_h - H) // 2
    img  = img.crop((left, top, left + W, top + H))
    img.save(path)
    return path


def _load_fonts():
    try:
        bold  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        med   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except Exception:
        bold = med = small = ImageFont.load_default()
    return bold, med, small


def create_title_card(movie_data: dict, path: str) -> str:
    """Dark card with title, year, rating, director."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img  = Image.new("RGB", (W, H), (10, 10, 10))
    draw = ImageDraw.Draw(img)
    font_large, _, font_small = _load_fonts()

    title = movie_data["title"]
    sub   = f"{movie_data['year']}  |  IMDb: {movie_data['rating']}/10  |  Dir: {movie_data['director']}"

    bbox = draw.textbbox((0, 0), title, font=font_large)
    tw   = bbox[2] - bbox[0]
    th   = bbox[3] - bbox[1]
    draw.text(((W - tw) // 2, H // 2 - th - 30), title, font=font_large, fill=(255, 255, 255))

    bbox2 = draw.textbbox((0, 0), sub, font=font_small)
    sw    = bbox2[2] - bbox2[0]
    draw.text(((W - sw) // 2, H // 2 + 20), sub, font=font_small, fill=(200, 200, 200))

    img.save(path)
    print(f"[Step 4] Title card -> {path}")
    return path


def create_cast_card(movie_data: dict, path: str) -> str:
    """Dark card showing cast, genres, awards."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img  = Image.new("RGB", (W, H), (15, 15, 30))
    draw = ImageDraw.Draw(img)
    _, font_med, font_small = _load_fonts()

    draw.text((80, 200), "Cast: "  + ", ".join(movie_data.get("cast",   [])), font=font_med,   fill=(255, 220, 100))
    draw.text((80, 280), "Genre: " + ", ".join(movie_data.get("genres", [])), font=font_small, fill=(200, 200, 200))
    awards = movie_data.get("awards", "")[:80]
    if awards:
        draw.text((80, 340), awards, font=font_small, fill=(180, 180, 180))

    img.save(path)
    print(f"[Step 4] Cast card -> {path}")
    return path


# ── Trailer download ──────────────────────────────────────────────────────────

def download_trailer_via_yt_dlp(movie_title: str, year: str,
                                  dest: str = None) -> str | None:
    """Download best matching trailer from YouTube via yt-dlp (no API key)."""
    if dest is None:
        dest = os.path.join(CLIP_DIR, "trailer.mp4")
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    query = f"ytsearch1:{movie_title} {year} official trailer"
    cmd   = [
        "yt-dlp", "--no-playlist",
        "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
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


# ── Manifest builder ──────────────────────────────────────────────────────────

def build_visual_manifest(movie_data: dict) -> dict:
    """
    Download / generate all visuals and return a timestamped manifest for Step 5.
    No API keys beyond OMDB_API_KEY (already in config.settings).
    """
    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(CLIP_DIR, exist_ok=True)

    assets = []

    # 1. Title card — HOOK (0–10 s)
    tc = create_title_card(movie_data, os.path.join(IMG_DIR, "title_card.jpg"))
    assets.append({"type": "image", "path": tc, "start_sec": 0, "end_sec": 10})

    # 2. OMDb poster — CONTEXT (10–30 s)
    poster_path = None
    if movie_data.get("poster_url"):
        poster_path = download_image(movie_data["poster_url"], os.path.join(IMG_DIR, "poster.jpg"))
        if poster_path:
            resize_image(poster_path)
            assets.append({"type": "image", "path": poster_path, "start_sec": 10, "end_sec": 30})

    # 3. Cast card — PLOT_TEASE start (30–55 s)
    cc = create_cast_card(movie_data, os.path.join(IMG_DIR, "cast_card.jpg"))
    assets.append({"type": "image", "path": cc, "start_sec": 30, "end_sec": 55})

    # 4. Poster again — PLOT_TEASE mid (55–90 s)
    fallback = poster_path or tc
    assets.append({"type": "image", "path": fallback, "start_sec": 55, "end_sec": 90})

    # 5. Trailer clip — CTA (90–120 s)
    trailer = download_trailer_via_yt_dlp(movie_data["title"], movie_data["year"])
    if trailer:
        assets.append({"type": "video", "path": trailer, "start_sec": 90, "end_sec": 120})
    else:
        assets.append({"type": "image", "path": tc, "start_sec": 90, "end_sec": 120})

    manifest = {
        "movie_title":        movie_data["title"],
        "total_duration_sec": 120,
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