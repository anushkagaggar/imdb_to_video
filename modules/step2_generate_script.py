"""
Step 2 — Generate Narration Script via Groq API (free LLM)
Converts raw movie metadata into a timed, 4-segment video script (~300 words / 2 min).
"""

import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL   = "llama3-8b-8192"   # free & fast on Groq


SYSTEM_PROMPT = """
You are a professional cinematic video narrator. Your job is to write compelling,
engaging 2-minute video scripts for movies. Always follow the 4-segment structure.
Output ONLY valid JSON — no markdown, no code fences, no extra text.
""".strip()

SCRIPT_PROMPT_TEMPLATE = """
Write a 2-minute narration script for the movie below.

Movie Data:
- Title: {title} ({year})
- Director: {director}
- Cast: {cast}
- Genres: {genres}
- Tagline: {tagline}
- Overview: {overview}
- Rating: {rating}/10

Rules:
1. Total word count: 280–320 words (≈ 150 wpm × 2 min).
2. Use exactly 4 segments with these labels: HOOK, CONTEXT, PLOT_TEASE, CTA.
3. No spoilers in PLOT_TEASE — build curiosity only.
4. Tone: cinematic, warm, enthusiastic.
5. CTA must mention where to watch if known, else say "streaming now on major platforms".

Return ONLY this JSON structure:
{{
  "title": "{title}",
  "segments": [
    {{"label": "HOOK",       "start_sec": 0,  "end_sec": 10, "text": "..."}},
    {{"label": "CONTEXT",    "start_sec": 10, "end_sec": 30, "text": "..."}},
    {{"label": "PLOT_TEASE", "start_sec": 30, "end_sec": 90, "text": "..."}},
    {{"label": "CTA",        "start_sec": 90, "end_sec": 120,"text": "..."}}
  ],
  "full_script": "complete narration text joined together"
}}
"""


def generate_script(movie_data: dict) -> dict:
    """
    Call Groq LLM to generate a structured 4-segment video script.
    Returns parsed script dict with segments and full_script.
    """
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set in .env")

    client = Groq(api_key=GROQ_API_KEY)

    prompt = SCRIPT_PROMPT_TEMPLATE.format(
        title    = movie_data["title"],
        year     = movie_data["year"],
        director = movie_data["director"],
        cast     = ", ".join(movie_data["cast"]),
        genres   = ", ".join(movie_data["genres"]),
        tagline  = movie_data.get("tagline", ""),
        overview = movie_data["overview"],
        rating   = movie_data["rating"],
    )

    print("[Step 2] 🤖 Calling Groq LLM for script generation...")

    response = client.chat.completions.create(
        model    = GROQ_MODEL,
        messages = [
            {"role": "system",  "content": SYSTEM_PROMPT},
            {"role": "user",    "content": prompt},
        ],
        temperature      = 0.7,
        max_tokens       = 1024,
        response_format  = {"type": "json_object"},
    )

    raw = response.choices[0].message.content
    script = json.loads(raw)

    word_count = len(script.get("full_script", "").split())
    print(f"[Step 2] ✅ Script generated — {word_count} words across "
          f"{len(script['segments'])} segments")

    return script


def save_script(script: dict, path: str = "assets/script.json"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(script, f, indent=2)

    # Also save human-readable markdown
    md_path = path.replace(".json", ".md")
    with open(md_path, "w") as f:
        f.write(f"# {script['title']} — Video Script\n\n")
        for seg in script["segments"]:
            f.write(f"## [{seg['label']}] ({seg['start_sec']}s – {seg['end_sec']}s)\n\n")
            f.write(seg["text"] + "\n\n")

    print(f"[Step 2] 💾 Script saved → {path} + {md_path}")


if __name__ == "__main__":
    with open("assets/movie_data.json") as f:
        movie_data = json.load(f)

    script = generate_script(movie_data)
    save_script(script)
    print(json.dumps(script, indent=2))