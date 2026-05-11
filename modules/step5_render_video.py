"""
Step 5 — Render & Export Final Video
Composites narration + visuals + background music into a 1280×720 MP4.
Uses moviepy for timeline assembly and ffmpeg for final encoding.
"""

import os
import json
import subprocess
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

W, H    = 1280, 720
FPS     = 24
OUT_DIR = "assets/output"
BG_MUSIC_URL = (
    "https://www.chosic.com/wp-content/uploads/2021/04/"
    "purrple-cat-equinox.mp3"
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def download_bg_music(dest: str = "assets/audio/bg_music.mp3") -> str | None:
    """Download a free royalty-free music track."""
    if os.path.exists(dest):
        print(f"[Step 5] 🎵 BG music already cached → {dest}")
        return dest
    try:
        print("[Step 5] 🎵 Downloading royalty-free background music...")
        urllib.request.urlretrieve(BG_MUSIC_URL, dest)
        print(f"[Step 5] ✅ BG music → {dest}")
        return dest
    except Exception as e:
        print(f"[Step 5] ⚠️  Could not download BG music: {e}")
        return None


def probe_duration(path: str) -> float:
    """Return media duration in seconds via ffprobe."""
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ], capture_output=True, text=True, timeout=15)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def build_ffmpeg_filter(manifest: dict) -> tuple[list[str], str]:
    """
    Build an FFmpeg filtergraph that:
      - Scales each image/video to 1280×720 with Ken Burns zoom-pan
      - Concatenates all visual segments into one 120-second stream
    Returns (input_args, filter_complex_str).
    """
    assets        = manifest["assets"]
    input_args    = []
    filter_parts  = []
    video_labels  = []

    for i, asset in enumerate(assets):
        path      = asset["path"]
        start     = asset["start_sec"]
        end       = asset["end_sec"]
        duration  = end - start

        if not os.path.exists(path):
            print(f"[Step 5] ⚠️  Missing asset: {path} — skipping")
            continue

        input_args += ["-i", path]
        idx = len(video_labels)   # index among valid inputs

        if asset["type"] == "image":
            # Loop the image for `duration` seconds, apply gentle Ken Burns zoom
            zoom_speed = 0.0003
            filt = (
                f"[{idx}:v]"
                f"loop=loop=-1:size=1:start=0,"
                f"trim=duration={duration},"
                f"scale={W*2}:{H*2},"
                f"zoompan=z='min(zoom+{zoom_speed},1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={duration * FPS}:s={W}x{H}:fps={FPS},"
                f"setpts=PTS-STARTPTS"
                f"[v{idx}]"
            )
        else:
            # Video clip: trim, scale, drop audio
            filt = (
                f"[{idx}:v]"
                f"trim=start=0:end={duration},"
                f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,"
                f"setpts=PTS-STARTPTS"
                f"[v{idx}]"
            )

        filter_parts.append(filt)
        video_labels.append(f"[v{idx}]")

    if not video_labels:
        raise RuntimeError("No valid visual assets found for rendering.")

    # Concatenate all labelled segments
    concat_inputs = "".join(video_labels)
    n             = len(video_labels)
    filter_parts.append(
        f"{concat_inputs}concat=n={n}:v=1:a=0[vout]"
    )

    return input_args, ";".join(filter_parts)


def render_video(manifest: dict, narration_path: str, output_path: str) -> str:
    """
    Full render pipeline:
      1. Build filtergraph for visuals
      2. Add narration audio
      3. Mix in background music at low volume
      4. Encode to H.264 MP4
    """
    os.makedirs(OUT_DIR, exist_ok=True)

    bg_music = download_bg_music()

    print("[Step 5] 🎬 Building FFmpeg render command...")

    visual_inputs, filter_complex = build_ffmpeg_filter(manifest)

    # Audio inputs
    audio_inputs = ["-i", narration_path]
    narration_idx = len(visual_inputs) // 2   # each -i path is 2 tokens

    audio_filter = f"[{narration_idx}:a]volume=1.0[narr]"

    if bg_music and os.path.exists(bg_music):
        audio_inputs += ["-i", bg_music]
        bg_idx = narration_idx + 1
        audio_filter += (
            f";[{bg_idx}:a]"
            f"atrim=duration=120,aloop=loop=-1:size=44100*120,"
            f"volume=0.12[bg]"
            f";[narr][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
        audio_out = "[aout]"
    else:
        audio_filter += ";[narr]acopy[aout]"
        audio_out = "[aout]"

    full_filter = filter_complex + ";" + audio_filter

    cmd = [
        "ffmpeg", "-y",
        *visual_inputs,
        *audio_inputs,
        "-filter_complex", full_filter,
        "-map", "[vout]",
        "-map", audio_out,
        "-t", "120",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-r", str(FPS),
        output_path,
    ]

    print(f"[Step 5] ⚙️  Rendering to {output_path} ...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("[Step 5] ❌ FFmpeg error:")
        print(result.stderr[-3000:])
        raise RuntimeError("FFmpeg render failed.")

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    dur     = probe_duration(output_path)
    print(f"[Step 5] ✅ Video rendered → {output_path}")
    print(f"[Step 5]    Duration: {dur:.1f}s | Size: {size_mb:.1f} MB")

    return output_path


if __name__ == "__main__":
    with open("assets/visual_manifest.json") as f:
        manifest = json.load(f)

    title   = manifest["movie_title"].replace(" ", "_").lower()
    out     = f"{OUT_DIR}/{title}_2min.mp4"

    render_video(
        manifest       = manifest,
        narration_path = "assets/audio/narration_final.mp3",
        output_path    = out,
    )
    print(f"\n🎉 Done! Your 2-minute video: {out}")