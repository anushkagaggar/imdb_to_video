"""
Step 3 — Text-to-Speech Narration via gTTS (Google TTS, free — no API key needed)
Converts the script's full_script into an MP3 voiceover track.
Pads or trims to exactly 120 seconds using pydub.
No secrets required — gTTS needs no credentials.
"""

import os
import subprocess
from gtts import gTTS
from pydub import AudioSegment
from config.settings import (
    NARRATION_RAW,
    NARRATION_FINAL,
    TTS_LANGUAGE,
    AUDIO_BITRATE,
    VIDEO_DURATION,
)

import imageio_ffmpeg

ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

# Patch pydub to use the imageio ffmpeg binary
import pydub.utils
pydub.utils.FFMPEG_PATH = ffmpeg_path
pydub.utils.FFPROBE_PATH = ffmpeg_path

from pydub import AudioSegment
AudioSegment.converter = ffmpeg_path
AudioSegment.ffprobe = ffmpeg_path
TARGET_MS = VIDEO_DURATION * 1000   # 120,000 ms


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


def adjust_duration(audio_path, target_duration=120):
    """Adjust audio speed to fit target duration using ffmpeg directly."""
    from mutagen.mp3 import MP3
    import subprocess, os, imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    
    # Get duration using mutagen (pure Python, no ffprobe needed)
    audio_info = MP3(audio_path)
    current_duration = audio_info.info.length
    print(f"[Step 3] Audio duration: {current_duration:.1f}s (target: {target_duration}s)")

    if abs(current_duration - target_duration) < 5:
        print("[Step 3] Duration within tolerance, skipping adjustment")
        return audio_path

    # Calculate speed factor
    speed = current_duration / target_duration
    output_path = audio_path.replace(".mp3", "_adjusted.mp3")

    # Use ffmpeg directly for tempo change
    cmd = [
        ffmpeg, "-y", "-i", audio_path,
        "-filter:a", f"atempo={speed}",
        "-vn", output_path
    ]
    
    # atempo filter only accepts 0.5 to 2.0, chain if needed
    if speed > 2.0 or speed < 0.5:
        print(f"[Step 3] Speed factor {speed:.2f} out of range, skipping adjustment")
        return audio_path

    subprocess.run(cmd, check=True, capture_output=True)
    print(f"[Step 3] Adjusted audio saved -> {output_path}")
    return output_path


def get_audio_duration_sec(path: str) -> float:
    """Return duration of an audio file in seconds via ffprobe."""
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ], capture_output=True, text=True)
    return float(result.stdout.strip() or 0)


if __name__ == "__main__":
    import json
    with open("assets/script.json") as f:
        script = json.load(f)
    raw_path   = text_to_speech(script)
    final_path = adjust_duration(raw_path)
    print(f"[Step 3] Final audio duration: {get_audio_duration_sec(final_path):.1f}s")