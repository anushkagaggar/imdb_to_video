"""
Step 4 — Assemble Visuals
Downloads 20-30 movie stills/images from the web + OMDb poster.
Generates title card, cast card, rating card, and quote cards locally using Pillow.
Builds a manifest mapping each visual asset to a timestamp range (~4-6s per image).
"""

import os
import json
import subprocess
import requests
import re
import time
from urllib.parse import urlparse, quote_plus
from PIL import Image, ImageDraw, ImageFont
from config.settings import (
    OMDB_API_KEY,
    IMG_DIR,
    CLIP_DIR,
    MANIFEST_PATH,
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
    VIDEO_DURATION,
)

W, H = VIDEO_WIDTH, VIDEO_HEIGHT
TARGET_IMAGES = 25


# ── Font Helpers ─────────────────────────────────────────────────────────────

def _load_fonts():
    font_paths_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Arial.ttf",
    ]
    font_paths_reg = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    fp_bold = next((f for f in font_paths_bold if os.path.exists(f)), None)
    fp_reg  = next((f for f in font_paths_reg  if os.path.exists(f)), None)

    try:
        bold  = ImageFont.truetype(fp_bold, 64)  if fp_bold else ImageFont.load_default()
        med   = ImageFont.truetype(fp_bold, 40)  if fp_bold else ImageFont.load_default()
        small = ImageFont.truetype(fp_reg or fp_bold, 28) if (fp_reg or fp_bold) else ImageFont.load_default()
        big   = ImageFont.truetype(fp_bold, 80)  if fp_bold else ImageFont.load_default()
    except Exception:
        bold = med = small = big = ImageFont.load_default()
    return bold, med, small, big


# ── Image Helpers ────────────────────────────────────────────────────────────

def download_image(url: str, dest: str, timeout: int = 15) -> str | None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
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
        img.verify()
        return dest
    except Exception:
        if os.path.exists(dest):
            os.remove(dest)
        return None


def resize_image(path: str) -> str:
    try:
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
        img.save(path, quality=95)
        return path
    except Exception:
        return path


# ── Card Generators ──────────────────────────────────────────────────────────

def _gradient_bg(color1=(10, 10, 40), color2=(30, 5, 20)):
    img = Image.new("RGB", (W, H), color1)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        r = int(color1[0] + (color2[0] - color1[0]) * y / H)
        g = int(color1[1] + (color2[1] - color1[1]) * y / H)
        b = int(color1[2] + (color2[2] - color1[2]) * y / H)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    return img


def _draw_centered_text(draw, text, y, font, fill, max_width=None):
    if max_width is None:
        max_width = W - 160
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width:
            if current:
                lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(((W - tw) // 2, y), line, font=font, fill=fill)
        y += th + 8
    return y


def create_title_card(movie_data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = _gradient_bg((5, 5, 30), (20, 5, 15))
    draw = ImageDraw.Draw(img)
    bold, med, small, big = _load_fonts()
    y = H // 2 - 100
    y = _draw_centered_text(draw, movie_data["title"], y, bold, (255, 255, 255))
    sub = f"{movie_data['year']}  |  IMDb {movie_data['rating']}/10  |  {movie_data['director']}"
    y = _draw_centered_text(draw, sub, y + 20, small, (200, 200, 200))
    genres = " | ".join(movie_data.get("genres", []))
    _draw_centered_text(draw, genres, y + 15, small, (150, 180, 220))
    img.save(path, quality=95)
    print(f"[Step 4] Title card -> {path}")
    return path


def create_cast_card(movie_data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = _gradient_bg((15, 10, 30), (10, 15, 25))
    draw = ImageDraw.Draw(img)
    bold, med, small, _ = _load_fonts()
    y = 150
    _draw_centered_text(draw, "STARRING", y, med, (255, 200, 80))
    y = 220
    for actor in movie_data.get("cast", [])[:5]:
        y = _draw_centered_text(draw, actor, y, small, (220, 220, 220))
        y += 5
    y += 30
    genres = "Genre: " + ", ".join(movie_data.get("genres", []))
    _draw_centered_text(draw, genres, y, small, (180, 180, 200))
    awards = movie_data.get("awards", "")
    if awards and awards != "N/A":
        y += 50
        _draw_centered_text(draw, awards[:80], y, small, (255, 215, 0))
    img.save(path, quality=95)
    print(f"[Step 4] Cast card -> {path}")
    return path


def create_rating_card(movie_data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = _gradient_bg((5, 15, 30), (15, 5, 20))
    draw = ImageDraw.Draw(img)
    bold, med, small, big = _load_fonts()
    _draw_centered_text(draw, "IMDb RATING", H // 2 - 120, med, (200, 200, 200))
    _draw_centered_text(draw, f"★ {movie_data['rating']}/10", H // 2 - 40, big, (255, 215, 0))
    _draw_centered_text(draw, movie_data["title"], H // 2 + 80, bold, (255, 255, 255))
    img.save(path, quality=95)
    print(f"[Step 4] Rating card -> {path}")
    return path


def create_quote_card(text, label, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = _gradient_bg((10, 10, 25), (25, 10, 15))
    draw = ImageDraw.Draw(img)
    bold, med, small, _ = _load_fonts()
    words = text.split()[:20]
    short = " ".join(words)
    if len(text.split()) > 20:
        short += "..."
    y = H // 2 - 80
    _draw_centered_text(draw, f'"{short}"', y, med, (230, 230, 230))
    img.save(path, quality=95)
    return path


def create_cta_card(movie_data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = _gradient_bg((20, 5, 10), (5, 10, 30))
    draw = ImageDraw.Draw(img)
    bold, med, small, big = _load_fonts()
    _draw_centered_text(draw, "WATCH NOW", H // 2 - 80, big, (255, 80, 80))
    _draw_centered_text(draw, movie_data["title"], H // 2 + 40, bold, (255, 255, 255))
    _draw_centered_text(draw, "Streaming on major platforms", H // 2 + 120, small, (180, 180, 200))
    img.save(path, quality=95)
    print(f"[Step 4] CTA card -> {path}")
    return path


# ── Web Image Scraping ───────────────────────────────────────────────────────

def scrape_movie_images(movie_title, year, count=20):
    queries = [
        f"{movie_title} {year} movie stills",
        f"{movie_title} {year} movie scenes",
        f"{movie_title} {year} movie screenshots HD",
        f"{movie_title} {year} cinematography",
        f"{movie_title} {year} film behind the scenes",
    ]
    downloaded = []
    seen_urls = set()
    img_counter = 0

    for query in queries:
        if len(downloaded) >= count:
            break
        urls = _google_image_search(query, num=8)
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
                except Exception:
                    if os.path.exists(dest):
                        os.remove(dest)
        time.sleep(0.3)

    print(f"[Step 4] Downloaded {len(downloaded)} movie images from web")
    return downloaded


def _google_image_search(query, num=10):
    url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=isch&safe=active"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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
            if any(skip in m.lower() for skip in ["google", "gstatic", "encrypted-tbn", "favicon"]):
                continue
            if m not in img_urls:
                img_urls.append(m)
            if len(img_urls) >= num:
                break
        return img_urls[:num]
    except Exception as e:
        print(f"[Step 4] Image search failed for '{query}': {e}")
        return []


def _get_ext(url):
    path = urlparse(url).path.lower()
    for ext in [".png", ".webp", ".jpeg", ".jpg"]:
        if ext in path:
            return ext
    return ".jpg"


# ── Trailer download ────────────────────────────────────────────────────────

def download_trailer_via_yt_dlp(movie_title, year, dest=None):
    if dest is None:
        dest = os.path.join(CLIP_DIR, "trailer.mp4")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    query = f"ytsearch1:{movie_title} {year} official trailer"
    cmd = [
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


# ── Manifest builder ────────────────────────────────────────────────────────

def build_visual_manifest(movie_data):
    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(CLIP_DIR, exist_ok=True)

    all_images = []

    # 1. Title card (opening)
    tc = create_title_card(movie_data, os.path.join(IMG_DIR, "title_card.jpg"))
    all_images.append(tc)

    # 2. OMDb poster
    if movie_data.get("poster_url"):
        pp = download_image(movie_data["poster_url"], os.path.join(IMG_DIR, "poster.jpg"))
        if pp:
            resize_image(pp)
            all_images.append(pp)

    # 3. Cast card
    cc = create_cast_card(movie_data, os.path.join(IMG_DIR, "cast_card.jpg"))
    all_images.append(cc)

    # 4. Rating card
    rc = create_rating_card(movie_data, os.path.join(IMG_DIR, "rating_card.jpg"))
    all_images.append(rc)

    # 5. Scrape movie images from the web (the big improvement)
    scraped = scrape_movie_images(movie_data["title"], movie_data["year"], count=20)
    all_images.extend(scraped)

    # 6. Quote cards from script
    script_path = "assets/script.json"
    if os.path.exists(script_path):
        try:
            with open(script_path) as f:
                script = json.load(f)
            for i, seg in enumerate(script.get("segments", [])):
                qp = os.path.join(IMG_DIR, f"quote_{i}.jpg")
                create_quote_card(seg["text"], seg["label"], qp)
                all_images.append(qp)
        except Exception:
            pass

    # 7. CTA card (closing)
    cta = create_cta_card(movie_data, os.path.join(IMG_DIR, "cta_card.jpg"))
    all_images.append(cta)

    # Distribute evenly across 120 seconds
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