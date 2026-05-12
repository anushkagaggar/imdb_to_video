"""
Step 4 — Assemble Visuals
Downloads poster image from OMDb and trailer clip via yt-dlp (both free).
Builds a manifest mapping each visual asset to a timestamp range.
OMDb free tier gives a direct poster URL — no extra API needed.
"""

import os
import json
import subprocess
import requests
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()

OMDB_API_KEY = os.getenv("OMDB_API_KEY")
IMG_DIR      = "assets/images"
CLIP_DIR     = "assets/clips"
W, H         = 1280, 720


# ── Helpers ───────────────────────────────────────────────────────────────────

def download_image(url: str, dest: str) -> str | None:
    """Download an image from URL; return dest path or None on failure."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
        print(f"[Step 4] Downloaded image -> {dest}")
        return dest
    except Exception as e:
        print(f"[Step 4] Failed to download {url}: {e}")
        return None


def resize_image(path: str, width: int = W, height: int = H) -> str:
    """Resize image to video resolution using crop-to-fill."""
    img = Image.open(path).convert("RGB")

    img_ratio    = img.width / img.height
    target_ratio = width / height

    if img_ratio > target_ratio:
        new_h = height
        new_w = int(img.width * height / img.height)
    else:
        new_w = width
        new_h = int(img.height * width / img.width)

    img  = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - width)  // 2
    top  = (new_h - height) // 2
    img  = img.crop((left, top, left + width, top + height))
    img.save(path)
    return path


def create_title_card(movie_data: dict, path: str) -> str:
    """Generate a title card image with movie name, year, rating and director."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img  = Image.new("RGB", (W, H), color=(10, 10, 10))
    draw = ImageDraw.Draw(img)

    for i in range(H):
        draw.line([(0, i), (W, i)], fill=(0, 0, 0))

    title    = movie_data["title"]
    year     = movie_data["year"]
    rating   = movie_data["rating"]
    director = movie_data["director"]

    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except Exception:
        font_large = font_small = ImageFont.load_default()

    # Title
    bbox   = draw.textbbox((0, 0), title, font=font_large)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((W - tw) // 2, H // 2 - th - 30), title, font=font_large, fill=(255, 255, 255))

    # Year, Rating, Director
    sub   = f"{year}  |  IMDb: {rating}/10  |  Dir: {director}"
    bbox2 = draw.textbbox((0, 0), sub, font=font_small)
    sw    = bbox2[2] - bbox2[0]
    draw.text(((W - sw) // 2, H // 2 + 20), sub, font=font_small, fill=(200, 200, 200))

    img.save(path)
    print(f"[Step 4] Title card -> {path}")
    return path


def create_cast_card(movie_data: dict, path: str) -> str:
    """Generate a cast & genre info card."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img  = Image.new("RGB", (W, H), color=(15, 15, 30))
    draw = ImageDraw.Draw(img)

    try:
        font_med   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except Exception:
        font_med = font_small = ImageFont.load_default()

    cast_str  = "Cast: " + ", ".join(movie_data.get("cast", []))
    genre_str = "Genre: " + ", ".join(movie_data.get("genres", []))
    award_str = movie_data.get("awards", "")[:80]

    draw.text((80, 200), cast_str,  font=font_med,   fill=(255, 220, 100))
    draw.text((80, 280), genre_str, font=font_small,  fill=(200, 200, 200))
    if award_str:
        draw.text((80, 340), award_str, font=font_small, fill=(180, 180, 180))

    img.save(path)
    print(f"[Step 4] Cast card -> {path}")
    return path


def download_trailer_via_yt_dlp(trailer_search_url: str,
                                 movie_title: str,
                                 year: str,
                                 dest: str = f"{CLIP_DIR}/trailer.mp4") -> str | None:
    """
    Download trailer from YouTube using yt-dlp.
    Constructs a ytsearch query from the movie title so we get the right video.
    """
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    search_query = f"ytsearch1:{movie_title} {year} official trailer"

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
        "--merge-output-format", "mp4",
        "-o", dest,
        "--quiet",
        "--no-warnings",
        search_query,
    ]
    try:
        subprocess.run(cmd, check=True, timeout=120)
        print(f"[Step 4] Trailer clip -> {dest}")
        return dest
    except Exception as e:
        print(f"[Step 4] yt-dlp failed: {e}  (video will render with images only)")
        return None


def build_visual_manifest(movie_data: dict) -> dict:
    """
    Orchestrate all visual downloads and return a manifest that maps
    each asset to a timeline segment for Step 5.
    Uses only OMDb (poster) + yt-dlp (trailer) — no TMDb required.
    """
    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(CLIP_DIR, exist_ok=True)

    assets = []

    # 1. Title card — HOOK (0–10 s)
    title_card = create_title_card(movie_data, f"{IMG_DIR}/title_card.jpg")
    assets.append({"type": "image", "path": title_card, "start_sec": 0, "end_sec": 10})

    # 2. Movie poster from OMDb — CONTEXT (10–30 s)
    if movie_data.get("poster_url"):
        poster = download_image(movie_data["poster_url"], f"{IMG_DIR}/poster.jpg")
        if poster:
            resize_image(poster)
            assets.append({"type": "image", "path": poster, "start_sec": 10, "end_sec": 30})

    # 3. Cast card (generated locally) — PLOT_TEASE start (30–55 s)
    cast_card = create_cast_card(movie_data, f"{IMG_DIR}/cast_card.jpg")
    assets.append({"type": "image", "path": cast_card, "start_sec": 30, "end_sec": 55})

    # 4. Poster again with different crop — PLOT_TEASE mid (55–90 s)
    if movie_data.get("poster_url"):
        assets.append({"type": "image", "path": f"{IMG_DIR}/poster.jpg",
                        "start_sec": 55, "end_sec": 90})
    else:
        assets.append({"type": "image", "path": title_card, "start_sec": 55, "end_sec": 90})

    # 5. Trailer clip via yt-dlp — CTA (90–120 s)
    trailer = download_trailer_via_yt_dlp(
        trailer_search_url = movie_data.get("trailer_url", ""),
        movie_title        = movie_data["title"],
        year               = movie_data["year"],
    )
    if trailer:
        assets.append({"type": "video", "path": trailer, "start_sec": 90, "end_sec": 120})
    else:
        # Fallback: loop title card for CTA segment
        assets.append({"type": "image", "path": title_card, "start_sec": 90, "end_sec": 120})

    manifest = {
        "movie_title":        movie_data["title"],
        "total_duration_sec": 120,
        "assets":             assets,
    }

    manifest_path = "assets/visual_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"[Step 4] Visual manifest ({len(assets)} assets) -> {manifest_path}")
    return manifest


if __name__ == "__main__":
    with open("assets/movie_data.json") as f:
        movie_data = json.load(f)

    manifest = build_visual_manifest(movie_data)
    print(json.dumps(manifest, indent=2))