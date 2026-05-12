"""
main.py — IMDb-to-Video Pipeline Orchestrator
Loads all secrets once via config.settings at startup.
Run: python main.py --imdb tt0111161
"""

import os
import sys
import time
import argparse
from pathlib import Path

# ── Add project root to Python path so "from config.settings import ..." works ──
sys.path.insert(0, str(Path(__file__).parent))

# ── Import config first — this is the ONLY place load_dotenv() is called ──────
from config.settings import validate_secrets

from modules.step1_fetch_data       import fetch_movie_data, save_movie_data
from modules.step2_generate_script  import generate_script, save_script
from modules.step3_text_to_speech   import text_to_speech, adjust_duration
from modules.step4_assemble_visuals import build_visual_manifest
from modules.step5_render_video     import render_video
from config.settings                import OUTPUT_DIR


BANNER = """
╔══════════════════════════════════════════════════════╗
║         IMDb -> 2-Minute Video Pipeline             ║
║     OMDb  •  Groq LLM  •  gTTS  •  FFmpeg          ║
╚══════════════════════════════════════════════════════╝
"""


def run_pipeline(imdb_id: str):
    print(BANNER)

    # Validate secrets once — raises clearly if .env keys are missing
    validate_secrets()

    total_start = time.time()
    title_slug  = imdb_id

    # ── Step 1 ────────────────────────────────────────────────────────────────
    print("\n" + "─" * 54)
    print("  STEP 1 / 5  —  Fetch Movie Data from OMDb")
    print("─" * 54)
    t          = time.time()
    movie_data = fetch_movie_data(imdb_id)
    save_movie_data(movie_data, "assets/movie_data.json")
    title_slug = movie_data["title"].replace(" ", "_").lower()
    print(f"  Done in {time.time() - t:.1f}s\n")

    # ── Step 2 ────────────────────────────────────────────────────────────────
    print("─" * 54)
    print("  STEP 2 / 5  —  Generate Script via Groq LLM")
    print("─" * 54)
    t      = time.time()
    script = generate_script(movie_data)
    save_script(script, "assets/script.json")
    print(f"  Done in {time.time() - t:.1f}s\n")

    # ── Step 3 ────────────────────────────────────────────────────────────────
    print("─" * 54)
    print("  STEP 3 / 5  —  Text-to-Speech (gTTS)")
    print("─" * 54)
    t           = time.time()
    raw_audio   = text_to_speech(script)
    final_audio = adjust_duration(raw_audio)
    print(f"  Done in {time.time() - t:.1f}s\n")

    # ── Step 4 ────────────────────────────────────────────────────────────────
    print("─" * 54)
    print("  STEP 4 / 5  —  Assemble Visuals (OMDb poster + yt-dlp)")
    print("─" * 54)
    t        = time.time()
    manifest = build_visual_manifest(movie_data)
    print(f"  Done in {time.time() - t:.1f}s\n")

    # ── Step 5 ────────────────────────────────────────────────────────────────
    print("─" * 54)
    print("  STEP 5 / 5  —  Render Final Video (FFmpeg)")
    print("─" * 54)
    t           = time.time()
    output_path = f"{OUTPUT_DIR}/{title_slug}_2min.mp4"
    render_video(
        manifest       = manifest,
        narration_path = final_audio,
        output_path    = output_path,
    )
    print(f"  Done in {time.time() - t:.1f}s\n")

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = time.time() - total_start
    size_mb = os.path.getsize(output_path) / (1024 * 1024)

    print("=" * 54)
    print(f"  PIPELINE COMPLETE in {elapsed:.0f}s")
    print(f"  Movie  : {movie_data['title']} ({movie_data['year']})")
    print(f"  Output : {output_path}")
    print(f"  Size   : {size_mb:.1f} MB  |  Duration: 2 min 00 sec")
    print("=" * 54)

    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a 2-minute video from an IMDb ID."
    )
    parser.add_argument(
        "--imdb", required=True,
        help="IMDb ID, e.g. tt0111161 (The Shawshank Redemption)",
    )
    args = parser.parse_args()
    run_pipeline(imdb_id=args.imdb)