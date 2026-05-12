"""
config/settings.py — Centralised configuration for the pipeline.
All modules import from here instead of hardcoding values.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
OMDB_API_KEY  = os.getenv("OMDB_API_KEY", "")
GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")

# ── OMDb ──────────────────────────────────────────────────────────────────────
OMDB_BASE     = "https://www.omdbapi.com/"

# ── Groq LLM ─────────────────────────────────────────────────────────────────
GROQ_MODEL        = "llama3-8b-8192"
GROQ_MAX_TOKENS   = 1024
GROQ_TEMPERATURE  = 0.7

# ── Video ─────────────────────────────────────────────────────────────────────
VIDEO_WIDTH       = 1280
VIDEO_HEIGHT      = 720
VIDEO_FPS         = 24
VIDEO_DURATION    = 120          # seconds

# ── Audio ─────────────────────────────────────────────────────────────────────
AUDIO_BITRATE        = "128k"
AUDIO_SAMPLE_RATE    = 44100
BG_MUSIC_VOLUME      = 0.12     # 12% — keeps narration clear
TTS_LANGUAGE         = "en"

# ── Paths ─────────────────────────────────────────────────────────────────────
ASSETS_DIR        = "assets"
IMG_DIR           = "assets/images"
AUDIO_DIR         = "assets/audio"
CLIP_DIR          = "assets/clips"
OUTPUT_DIR        = "assets/output"
MOVIE_DATA_PATH   = "assets/movie_data.json"
SCRIPT_PATH       = "assets/script.json"
NARRATION_RAW     = "assets/audio/narration.mp3"
NARRATION_FINAL   = "assets/audio/narration_final.mp3"
BG_MUSIC_PATH     = "assets/audio/bg_music.mp3"
MANIFEST_PATH     = "assets/visual_manifest.json"

# ── Royalty-free BG music (Chosic — CC licence) ───────────────────────────────
BG_MUSIC_URL = (
    "https://www.chosic.com/wp-content/uploads/"
    "2021/04/purrple-cat-equinox.mp3"
)

# ── Script timing (seconds) ───────────────────────────────────────────────────
SEGMENT_TIMES = {
    "HOOK":       (0,   10),
    "CONTEXT":    (10,  30),
    "PLOT_TEASE": (30,  90),
    "CTA":        (90, 120),
}

# ── Ken Burns zoom speed ──────────────────────────────────────────────────────
ZOOM_SPEED = 0.0003