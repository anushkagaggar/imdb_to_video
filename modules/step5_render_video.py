"""
Step 5 — Render & Export Final Video
Composites narration + visuals + background music into a 1280x720 MP4.
Uses FFmpeg for all encoding. No secrets required.
"""

import os
import json
import subprocess
import urllib.request
from config.settings import (
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
    VIDEO_FPS,
    VIDEO_DURATION,
    OUTPUT_DIR,
    BG_MUSIC_PATH,
    BG_MUSIC_URL,
    BG_MUSIC_VOLUME,
    AUDIO_BITRATE,
    ZOOM_SPEED,
)

W, H = VIDEO_WIDTH, VIDEO_HEIGHT


# ── Helpers ───────────────────────────────────────────────────────────────────

def probe_duration(path: str) -> float:
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


def download_bg_music() -> str | None:
    if os.path.exists(BG_MUSIC_PATH):
        print(f"[Step 5] BG music cached -> {BG_MUSIC_PATH}")
        return BG_MUSIC_PATH
    try:
        os.makedirs(os.path.dirname(BG_MUSIC_PATH), exist_ok=True)
        print("[Step 5] Downloading royalty-free background music...")
        urllib.request.urlretrieve(BG_MUSIC_URL, BG_MUSIC_PATH)
        print(f"[Step 5] BG music -> {BG_MUSIC_PATH}")
        return BG_MUSIC_PATH
    except Exception as e:
        print(f"[Step 5] BG music download failed: {e} (continuing without music)")
        return None


def build_ffmpeg_filter(manifest: dict) -> tuple[list[str], str]:
    """
    Build FFmpeg filtergraph:
    - Ken Burns zoom-pan on each image segment
    - Scale video clips to target resolution
    - Concatenate all segments into one 120-second stream
    """
    assets       = manifest["assets"]
    input_args   = []
    filter_parts = []
    video_labels = []

    for asset in assets:
        path     = asset["path"]
        start    = asset["start_sec"]
        end      = asset["end_sec"]
        duration = end - start

        if not os.path.exists(path):
            print(f"[Step 5] Missing asset: {path} — skipping")
            continue

        input_args += ["-i", path]
        idx = len(video_labels)

        if asset["type"] == "image":
            filt = (
                f"[{idx}:v]"
                f"loop=loop=-1:size=1:start=0,"
                f"trim=duration={duration},"
                f"scale={W * 2}:{H * 2},"
                f"zoompan=z='min(zoom+{ZOOM_SPEED},1.5)'"
                f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={duration * VIDEO_FPS}:s={W}x{H}:fps={VIDEO_FPS},"
                f"setpts=PTS-STARTPTS"
                f"[v{idx}]"
            )
        else:
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
        raise RuntimeError("No valid visual assets found.")

    n = len(video_labels)
    filter_parts.append(
        "".join(video_labels) + f"concat=n={n}:v=1:a=0[vout]"
    )

    return input_args, ";".join(filter_parts)


def render_video(manifest: dict, narration_path: str, output_path: str) -> str:
    """
    Full render: visuals + narration + optional BG music -> H.264 MP4.
    All config values come from config.settings — no hardcoding.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    bg_music       = download_bg_music()
    visual_inputs, filter_complex = build_ffmpeg_filter(manifest)
    narr_idx       = len(visual_inputs) // 2   # number of -i flags already used

    audio_inputs  = ["-i", narration_path]
    audio_filter  = f"[{narr_idx}:a]volume=1.0[narr]"

    if bg_music and os.path.exists(bg_music):
        audio_inputs += ["-i", bg_music]
        bg_idx        = narr_idx + 1
        audio_filter += (
            f";[{bg_idx}:a]"
            f"atrim=duration={VIDEO_DURATION},"
            f"aloop=loop=-1:size=44100*{VIDEO_DURATION},"
            f"volume={BG_MUSIC_VOLUME}[bg]"
            f";[narr][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
    else:
        audio_filter += ";[narr]acopy[aout]"

    full_filter = filter_complex + ";" + audio_filter

    cmd = [
        "ffmpeg", "-y",
        *visual_inputs,
        *audio_inputs,
        "-filter_complex", full_filter,
        "-map", "[vout]",
        "-map", "[aout]",
        "-t", str(VIDEO_DURATION),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", AUDIO_BITRATE,
        "-movflags", "+faststart",
        "-r", str(VIDEO_FPS),
        output_path,
    ]

    print(f"[Step 5] Rendering -> {output_path} ...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[Step 5] FFmpeg error:\n{result.stderr[-3000:]}")
        raise RuntimeError("FFmpeg render failed.")

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    dur     = probe_duration(output_path)
    print(f"[Step 5] Done -> {output_path} | {dur:.1f}s | {size_mb:.1f} MB")
    return output_path


if __name__ == "__main__":
    with open("assets/visual_manifest.json") as f:
        manifest = json.load(f)
    title = manifest["movie_title"].replace(" ", "_").lower()
    render_video(
        manifest       = manifest,
        narration_path = "assets/audio/narration_final.mp3",
        output_path    = f"{OUTPUT_DIR}/{title}_2min.mp4",
    )