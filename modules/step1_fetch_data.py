"""
Step 1 — Fetch Movie Data from TMDb API (free)
Accepts an IMDb ID (e.g. tt0111161) and returns structured movie metadata.
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE    = "https://api.themoviedb.org/3"
TMDB_IMG     = "https://image.tmdb.org/t/p/w780"


def fetch_movie_data(imdb_id: str) -> dict:
    """
    Given an IMDb ID, fetch full movie metadata from TMDb.
    Returns a clean dict ready for downstream pipeline steps.
    """
    if not TMDB_API_KEY:
        raise ValueError("TMDB_API_KEY not set in .env")

    # ── 1. Resolve IMDb ID → TMDb movie object ──────────────────────────────
    find_url = f"{TMDB_BASE}/find/{imdb_id}"
    resp = requests.get(find_url, params={
        "api_key":           TMDB_API_KEY,
        "external_source":   "imdb_id",
    }, timeout=10)
    resp.raise_for_status()

    results = resp.json().get("movie_results", [])
    if not results:
        raise ValueError(f"No TMDb movie found for IMDb ID: {imdb_id}")

    tmdb_id = results[0]["id"]

    # ── 2. Full movie details ────────────────────────────────────────────────
    detail_url = f"{TMDB_BASE}/movie/{tmdb_id}"
    detail = requests.get(detail_url, params={
        "api_key":            TMDB_API_KEY,
        "append_to_response": "credits,videos",
    }, timeout=10).json()

    # ── 3. Extract cast & director ───────────────────────────────────────────
    cast     = detail.get("credits", {}).get("cast", [])
    crew     = detail.get("credits", {}).get("crew", [])
    top_cast = [c["name"] for c in cast[:5]]
    director = next((c["name"] for c in crew if c["job"] == "Director"), "Unknown")

    # ── 4. Trailer YouTube key ───────────────────────────────────────────────
    videos    = detail.get("videos", {}).get("results", [])
    trailer   = next(
        (v for v in videos if v["type"] == "Trailer" and v["site"] == "YouTube"),
        None,
    )
    trailer_url = f"https://www.youtube.com/watch?v={trailer['key']}" if trailer else None

    # ── 5. Poster URL ────────────────────────────────────────────────────────
    poster_path = detail.get("poster_path")
    poster_url  = f"{TMDB_IMG}{poster_path}" if poster_path else None

    # ── 6. Backdrop / stills ─────────────────────────────────────────────────
    backdrop_path = detail.get("backdrop_path")
    backdrop_url  = f"{TMDB_IMG}{backdrop_path}" if backdrop_path else None

    # ── 7. Assemble clean payload ────────────────────────────────────────────
    movie_data = {
        "imdb_id":       imdb_id,
        "tmdb_id":       tmdb_id,
        "title":         detail.get("title", "Unknown Title"),
        "year":          (detail.get("release_date") or "")[:4],
        "tagline":       detail.get("tagline", ""),
        "overview":      detail.get("overview", ""),
        "genres":        [g["name"] for g in detail.get("genres", [])],
        "runtime_min":   detail.get("runtime", 0),
        "rating":        round(detail.get("vote_average", 0), 1),
        "director":      director,
        "cast":          top_cast,
        "poster_url":    poster_url,
        "backdrop_url":  backdrop_url,
        "trailer_url":   trailer_url,
    }

    print(f"[Step 1] ✅ Fetched: {movie_data['title']} ({movie_data['year']})")
    return movie_data


def save_movie_data(movie_data: dict, path: str = "assets/movie_data.json"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(movie_data, f, indent=2)
    print(f"[Step 1] 💾 Saved to {path}")


if __name__ == "__main__":
    # Quick test — The Shawshank Redemption
    data = fetch_movie_data("tt0111161")
    save_movie_data(data)
    print(json.dumps(data, indent=2))