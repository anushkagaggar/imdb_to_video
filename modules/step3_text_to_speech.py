"""
Step 3 — Text-to-Speech Narration via gTTS (Google TTS, free)
Converts the script's full_script into an MP3 voiceover track.
Pads or trims to exactly 120 seconds using pydub + ffmpeg.
"""

import os
import json
import subprocess
from gtts import gTTS
from pydub import AudioSegment
from dotenv import load_dotenv

load_dotenv()

TARGET_DURATION_MS = 120_000   # 2 minutes in milliseconds
AUDIO_OUT          = "assets/audio/narration.mp3"
AUDIO_PADDED       = "assets/audio/narration_final.mp3"


def text_to_speech(script: dict) -> str:
    """
    Convert script full_script to MP3 using gTTS.
    Returns path to the raw narration MP3.
    """
    os.makedirs("assets/audio", exist_ok=True)

    full_text = script.get("full_script", "")
    if not full_text:
        # Fallback: join all segment texts
        full_text = " ".join(s["text"] for s in script.get("segments", []))

    print(f"[Step 3] 🎙️  Converting {len(full_text.split())} words to speech...")

    tts = gTTS(text=full_text, lang="en", slow=False)
    tts.save(AUDIO_OUT)
    print(f"[Step 3] ✅ Raw narration saved → {AUDIO_OUT}")

    return AUDIO_OUT


def adjust_duration(audio_path: str, target_ms: int = TARGET_DURATION_MS) -> str:
    """
    Pad or trim audio to hit exactly target_ms using pydub.
    Returns path to duration-adjusted MP3.
    """
    audio    = AudioSegment.from_mp3(audio_path)
    duration = len(audio)

    print(f"[Step 3] ⏱️  Raw duration: {duration / 1000:.1f}s | Target: {target_ms / 1000:.0f}s")

    if duration < target_ms:
        # Pad with silence
        silence  = AudioSegment.silent(duration=target_ms - duration)
        audio    = audio + silence
        print(f"[Step 3] ➕ Padded {(target_ms - duration) / 1000:.1f}s of silence")
    elif duration > target_ms:
        # Trim to target
        audio = audio[:target_ms]
        print(f"[Step 3] ✂️  Trimmed to {target_ms / 1000:.0f}s")

    audio.export(AUDIO_PADDED, format="mp3", bitrate="128k")
    print(f"[Step 3] 💾 Final narration saved → {AUDIO_PADDED}")
    return AUDIO_PADDED


def generate_per_segment_audio(script: dict) -> list[dict]:
    """
    Optional: generate a separate MP3 per segment for fine-grained timeline control.
    Returns list of {label, path, start_sec, end_sec}.
    """
    os.makedirs("assets/audio/segments", exist_ok=True)
    segment_files = []

    for seg in script.get("segments", []):
        label = seg["label"]
        path  = f"assets/audio/segments/{label.lower()}.mp3"

        tts = gTTS(text=seg["text"], lang="en", slow=False)
        tts.save(path)

        segment_files.append({
            "label":     label,
            "path":      path,
            "start_sec": seg["start_sec"],
            "end_sec":   seg["end_sec"],
            "text":      seg["text"],
        })
        print(f"[Step 3] 🎙️  Segment [{label}] → {path}")

    return segment_files


def get_audio_duration_sec(path: str) -> float:
    """Return duration of an audio file in seconds using ffprobe."""
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ], capture_output=True, text=True)
    return float(result.stdout.strip() or 0)


if __name__ == "__main__":
    with open("assets/script.json") as f:
        script = json.load(f)

    raw_path   = text_to_speech(script)
    final_path = adjust_duration(raw_path)
    duration   = get_audio_duration_sec(final_path)
    print(f"[Step 3] 🎵 Final audio duration: {duration:.1f}s")