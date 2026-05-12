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


def adjust_duration(audio_path: str) -> str:
    """Pad with silence or trim audio to exactly TARGET_MS. Returns final path."""
    audio    = AudioSegment.from_mp3(audio_path)
    duration = len(audio)

    print(f"[Step 3] Raw duration: {duration / 1000:.1f}s | Target: {TARGET_MS / 1000:.0f}s")

    if duration < TARGET_MS:
        silence = AudioSegment.silent(duration=TARGET_MS - duration)
        audio   = audio + silence
        print(f"[Step 3] Padded {(TARGET_MS - duration) / 1000:.1f}s of silence")
    elif duration > TARGET_MS:
        audio = audio[:TARGET_MS]
        print(f"[Step 3] Trimmed to {TARGET_MS / 1000:.0f}s")

    os.makedirs(os.path.dirname(NARRATION_FINAL), exist_ok=True)
    audio.export(NARRATION_FINAL, format="mp3", bitrate=AUDIO_BITRATE)
    print(f"[Step 3] Final narration -> {NARRATION_FINAL}")
    return NARRATION_FINAL


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