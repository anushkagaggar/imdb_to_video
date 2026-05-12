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
    Adjust audio to fit target duration:
    - If audio is LONGER than target: speed up slightly using atempo
    - If audio is SHORTER: speed up very slightly (1.0x) — do NOT slow down
      Instead, just use it as-is. The video will have some image-only time at the end.
    - If within 10s tolerance: keep as-is
    """
    audio_info = MP3(audio_path)
    current_duration = audio_info.info.length
    print(f"[Step 3] Audio duration: {current_duration:.1f}s (target: {target_duration}s)")

    os.makedirs(os.path.dirname(NARRATION_FINAL), exist_ok=True)

    # If audio is shorter than target — DO NOT slow it down
    # Just copy as-is. Better to have natural-speed voice + some quiet at end
    # than a sluggish slowed-down narration
    if current_duration <= target_duration:
        if target_duration - current_duration < 10:
            print(f"[Step 3] Audio is {target_duration - current_duration:.1f}s short — keeping natural speed")
        else:
            print(f"[Step 3] Audio is {target_duration - current_duration:.1f}s short — keeping natural speed (script may need more words)")
        subprocess.run([FFMPEG, "-y", "-i", audio_path, "-c", "copy", NARRATION_FINAL],
                       capture_output=True, check=True)
        print(f"[Step 3] Final narration -> {NARRATION_FINAL}")
        return NARRATION_FINAL

    # If audio is LONGER than target — speed it up
    speed = current_duration / target_duration
    print(f"[Step 3] Audio is {current_duration - target_duration:.1f}s too long — speeding up {speed:.2f}x")

    if speed > 2.0:
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
        print(f"[Step 3] Tempo adjust failed, copying raw audio instead")
        subprocess.run([FFMPEG, "-y", "-i", audio_path, "-c", "copy", NARRATION_FINAL],
                       capture_output=True)
        return NARRATION_FINAL

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