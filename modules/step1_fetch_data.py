"""
Step 1 — Fetch Movie Data from OMDb API (free, works in India)
Endpoint: https://www.omdbapi.com/?i=<imdb_id>&apikey=<key>&plot=full
One call returns everything: title, year, plot, cast, director, genre, rating, poster URL.
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

OMDB_API_KEY = os.getenv("OMDB_API_KEY")
OMDB_BASE    = "https://www.omdbapi.com/"


def fetch_movie_data(imdb_id: str) -> dict:
    """
    Given an IMDb ID, fetch full movie metadata from OMDb in a single API call.
    Returns a clean dict ready for all downstream pipeline steps.
    """
    if not OMDB_API_KEY:
        raise ValueError("OMDB_API_KEY not set in .env")

    # Single request — OMDb returns everything in one shot
    resp = requests.get(OMDB_BASE, params={
        "i":      imdb_id,
        "apikey": OMDB_API_KEY,
        "plot":   "full",
    }, timeout=10)
    resp.raise_for_status()

    data = resp.json()

    if data.get("Response") == "False":
        raise ValueError(f"OMDb error for '{imdb_id}': {data.get('Error')}")

    # Parse cast (comma-separated string -> list)
    cast_raw = data.get("Actors", "")
    cast     = [a.strip() for a in cast_raw.split(",") if a.strip()]

    # Parse genres
    genres_raw = data.get("Genre", "")
    genres     = [g.strip() for g in genres_raw.split(",") if g.strip()]

    # IMDb rating
    try:
        rating = float(data.get("imdbRating", "0"))
    except ValueError:
        rating = 0.0

    # Poster — OMDb returns a direct image URL in the free tier
    poster_url = data.get("Poster")
    if poster_url == "N/A":
        poster_url = None

    # Build YouTube trailer search URL (no extra API needed)
    title       = data.get("Title", "")
    year        = data.get("Year", "")[:4]
    trailer_url = (
        "https://www.youtube.com/results?search_query="
        + title.replace(" ", "+") + "+" + year + "+official+trailer"
    )

    movie_data = {
        "imdb_id":      imdb_id,
        "title":        title,
        "year":         year,
        "tagline":      "",
        "overview":     data.get("Plot", ""),
        "genres":       genres,
        "runtime_min":  data.get("Runtime", "0 min").replace(" min", ""),
        "rating":       rating,
        "director":     data.get("Director", "Unknown"),
        "cast":         cast[:5],
        "language":     data.get("Language", ""),
        "country":      data.get("Country", ""),
        "awards":       data.get("Awards", ""),
        "box_office":   data.get("BoxOffice", "N/A"),
        "poster_url":   poster_url,
        "backdrop_url": None,
        "trailer_url":  trailer_url,
    }

    print(f"[Step 1] Fetched: {movie_data['title']} ({movie_data['year']}) - {movie_data['rating']}/10")
    return movie_data


def save_movie_data(movie_data: dict, path: str = "assets/movie_data.json"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(movie_data, f, indent=2)
    print(f"[Step 1] Saved to {path}")


if __name__ == "__main__":
    data = fetch_movie_data("tt0111161")
    save_movie_data(data)
    print(json.dumps(data, indent=2))