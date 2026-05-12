"""
Step 3 — Text-to-Speech Narration via gTTS
Converts the script's full_script into an MP3 voiceover track.
Uses mutagen + ffmpeg (via imageio_ffmpeg) — NO pydub dependency.
"""

import os
import subprocess
from gtts import gTTS
from mutagen.mp3 import MP3
import imageio_ffmpeg

from config.settings import (
    NARRATION_RAW,
    NARRATION_FINAL,
    TTS_LANGUAGE,
    AUDIO_BITRATE,
    VIDEO_DURATION,
)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def text_to_speech(script: dict) -> str:
    """Convert script full_script to MP3 using gTTS. Returns raw audio path."""
    os.makedirs(os.path.dirname(NARRATION_RAW), exist_ok=True)

    full_text = script.get("full_script", "")
    if not full_text:
        full_text = " ".join(s["text"] for s in script.get("segments", []))

    print(f"[Step 3] Converting {len(full_text.split())} words to speech...")

    tts = gTTS(text=full_text, lang=TTS_LANGUAGE, slow=False)
    tts.save(NARRATION_RAW)
    print(f"[Step 3] Raw narration saved -> {NARRATION_RAW}")
    return NARRATION_RAW


def adjust_duration(audio_path: str, target_duration: int = VIDEO_DURATION) -> str:
    """
    Adjust audio to match target duration using ffmpeg atempo filter.
    - If audio is shorter: slow down slightly (NOT pad with silence)
    - If audio is longer: speed up slightly
    - If within 5s tolerance: leave as-is
    Returns path to final audio file.
    """
    audio_info = MP3(audio_path)
    current_duration = audio_info.info.length
    print(f"[Step 3] Audio duration: {current_duration:.1f}s (target: {target_duration}s)")

    os.makedirs(os.path.dirname(NARRATION_FINAL), exist_ok=True)

    if abs(current_duration - target_duration) < 5:
        print("[Step 3] Duration within tolerance, copying as final")
        # Just copy the file
        subprocess.run([FFMPEG, "-y", "-i", audio_path, "-c", "copy", NARRATION_FINAL],
                       capture_output=True, check=True)
        return NARRATION_FINAL

    # Calculate tempo factor: >1 = speed up, <1 = slow down
    speed = current_duration / target_duration

    # atempo filter accepts 0.5 to 100.0 — chain for extreme values
    if speed < 0.5:
        print(f"[Step 3] Speed factor {speed:.2f} too extreme, padding instead")
        # Pad with silence using ffmpeg
        pad_duration = target_duration - current_duration
        cmd = [
            FFMPEG, "-y", "-i", audio_path,
            "-af", f"apad=pad_dur={pad_duration}",
            "-t", str(target_duration),
            NARRATION_FINAL,
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        print(f"[Step 3] Padded to {target_duration}s -> {NARRATION_FINAL}")
        return NARRATION_FINAL

    if speed > 2.0:
        # Chain multiple atempo filters
        filters = []
        remaining = speed
        while remaining > 2.0:
            filters.append("atempo=2.0")
            remaining /= 2.0
        filters.append(f"atempo={remaining:.4f}")
        filter_str = ",".join(filters)
    else:
        filter_str = f"atempo={speed:.4f}"

    cmd = [
        FFMPEG, "-y", "-i", audio_path,
        "-filter:a", filter_str,
        "-vn",
        NARRATION_FINAL,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[Step 3] FFmpeg tempo adjust failed: {result.stderr[-500:]}")
        print("[Step 3] Falling back to copy")
        subprocess.run([FFMPEG, "-y", "-i", audio_path, "-c", "copy", NARRATION_FINAL],
                       capture_output=True)
        return NARRATION_FINAL

    # Verify output
    try:
        final_info = MP3(NARRATION_FINAL)
        print(f"[Step 3] Adjusted: {current_duration:.1f}s -> {final_info.info.length:.1f}s")
    except Exception:
        pass

    print(f"[Step 3] Final narration -> {NARRATION_FINAL}")
    return NARRATION_FINAL


if __name__ == "__main__":
    import json
    with open("assets/script.json") as f:
        script = json.load(f)
    raw_path   = text_to_speech(script)
    final_path = adjust_duration(raw_path)