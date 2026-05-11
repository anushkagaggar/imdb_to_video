"""
modules/utils.py — Shared utility functions used across pipeline steps.
"""

import os
import json
import subprocess
import requests
from pathlib import Path


def ensure_dirs(*paths: str):
    """Create directories if they don't exist."""
    for path in paths:
        os.makedirs(path, exist_ok=True)


def save_json(data: dict, path: str):
    """Save a dict as pretty-printed JSON."""
    ensure_dirs(str(Path(path).parent))
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_json(path: str) -> dict:
    """Load JSON file and return dict."""
    with open(path) as f:
        return json.load(f)


def download_file(url: str, dest: str, timeout: int = 30) -> str | None:
    """
    Download a file from URL to dest.
    Returns dest on success, None on failure.
    """
    ensure_dirs(str(Path(dest).parent))
    try:
        r = requests.get(url, timeout=timeout, stream=True)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return dest
    except Exception as e:
        print(f"[utils] ⚠️  download_file failed ({url}): {e}")
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


def probe_video_size(path: str) -> tuple[int, int]:
    """Return (width, height) of a video file via ffprobe."""
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0",
        path,
    ], capture_output=True, text=True, timeout=15)
    try:
        w, h = result.stdout.strip().split(",")
        return int(w), int(h)
    except Exception:
        return 1280, 720


def ffmpeg_run(cmd: list[str], label: str = "ffmpeg") -> bool:
    """
    Run an FFmpeg command.
    Prints stderr on failure. Returns True on success.
    """
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[{label}] ❌ FFmpeg error:\n{result.stderr[-2000:]}")
        return False
    return True


def slugify(text: str) -> str:
    """Convert text to a safe filename slug."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in text.lower()).strip("_")


def pretty_size(path: str) -> str:
    """Return human-readable file size string."""
    size = os.path.getsize(path)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"