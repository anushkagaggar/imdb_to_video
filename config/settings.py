"""
config/settings.py — Single source of truth for all configuration.

HOW IT WORKS:
  - Reads .env file via load_dotenv() exactly once here.
  - All modules import from this file — no os.getenv() anywhere else.
  - Secrets never appear in source code; only in the .env file.

USAGE in any module:
  from config.settings import TMDB_BEARER, GROQ_API_KEY
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Locate and load the .env file from the project root (one level up from config/)
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

# ── Secrets (sourced exclusively from .env) ───────────────────────────────────
TMDB_BEARER  = os.getenv("TMDB_BEARER", "")    # Long "API Read Access Token" (eyJ...)
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")   # Short v3 key — fallback
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Legacy OMDb key (kept for backward compatibility, not required)
OMDB_API_KEY = os.getenv("OMDB_API_KEY", "")

# ── TMDb endpoints ───────────────────────────────────────────────────────────
TMDB_BASE       = "https://api.themoviedb.org/3"
TMDB_IMG_BASE   = "https://image.tmdb.org/t/p"
TMDB_IMG_SIZE   = "original"   # 'original' = full resolution; alt: w1280, w780

# Legacy OMDb base (not required, kept for reference)
OMDB_BASE = "https://www.omdbapi.com/"

# ── Groq LLM ─────────────────────────────────────────────────────────────────
GROQ_MODEL       = "llama-3.1-8b-instant"
GROQ_MAX_TOKENS  = 1024
GROQ_TEMPERATURE = 0.7

# ── Video ─────────────────────────────────────────────────────────────────────
VIDEO_WIDTH    = 1920
VIDEO_HEIGHT   = 1080
VIDEO_FPS      = 30
VIDEO_DURATION = 120   # seconds

# ── Audio ─────────────────────────────────────────────────────────────────────
AUDIO_BITRATE    = "128k"
AUDIO_SAMPLE_RATE = 44100
BG_MUSIC_VOLUME  = 0.12
TTS_LANGUAGE     = "en"

# ── Paths ─────────────────────────────────────────────────────────────────────
ASSETS_DIR      = "assets"
IMG_DIR         = "assets/images"
AUDIO_DIR       = "assets/audio"
CLIP_DIR        = "assets/clips"
OUTPUT_DIR      = "assets/output"
MOVIE_DATA_PATH = "assets/movie_data.json"
SCRIPT_PATH     = "assets/script.json"
NARRATION_RAW   = "assets/audio/narration.mp3"
NARRATION_FINAL = "assets/audio/narration_final.mp3"
BG_MUSIC_PATH   = "assets/audio/bg_music.mp3"
MANIFEST_PATH   = "assets/visual_manifest.json"

# ── Royalty-free BG music (Chosic — CC licence) ───────────────────────────────
BG_MUSIC_URL = (
    "https://www.chosic.com/wp-content/uploads/"
    "2021/04/purrple-cat-equinox.mp3"
)

# ── Script segment timing (seconds) ──────────────────────────────────────────
SEGMENT_TIMES = {
    "HOOK":       (0,   10),
    "CONTEXT":    (10,  30),
    "PLOT_TEASE": (30,  90),
    "CTA":        (90, 120),
}

# ── Ken Burns zoom speed ──────────────────────────────────────────────────────
ZOOM_SPEED = 0.0003


def validate_secrets():
    """
    Call once at startup. Raises clearly if any required key is missing.
    """
    missing = []
    if not TMDB_BEARER and not TMDB_API_KEY:
        missing.append("TMDB_BEARER (or TMDB_API_KEY)")
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if missing:
        raise EnvironmentError(
            f"\n\nMissing required keys in your .env file: {', '.join(missing)}\n"
            f"  -> .env location expected at: {_ENV_PATH}\n"
            f"  -> Add these lines to your .env:\n"
            f"     TMDB_BEARER=eyJ...your_token...\n"
            f"     GROQ_API_KEY=gsk_...\n"
        )