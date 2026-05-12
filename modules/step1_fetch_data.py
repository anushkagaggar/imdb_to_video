"""
Step 1 — Fetch Movie Data from OMDb API
Endpoint: https://www.omdbapi.com/?i=<imdb_id>&apikey=<key>&plot=full
Returns title, year, plot, cast, director, genres, rating, and a direct poster URL.
"""

import json
import requests
from config.settings import OMDB_API_KEY, OMDB_BASE
import os


def fetch_movie_data(imdb_id: str) -> dict:
    """
    Fetch full movie metadata from OMDb in a single API call.
    Returns a clean dict consumed by all downstream pipeline steps.
    """
    resp = requests.get(OMDB_BASE, params={
        "i":      imdb_id,
        "apikey": OMDB_API_KEY,
        "plot":   "full",
    }, timeout=10)
    resp.raise_for_status()

    data = resp.json()

    if data.get("Response") == "False":
        raise ValueError(f"OMDb error for '{imdb_id}': {data.get('Error')}")

    # Cast — OMDb returns a comma-separated string
    cast = [a.strip() for a in data.get("Actors", "").split(",") if a.strip()]

    # Genres — same format
    genres = [g.strip() for g in data.get("Genre", "").split(",") if g.strip()]

    # Rating
    try:
        rating = float(data.get("imdbRating", "0"))
    except ValueError:
        rating = 0.0

    # Poster URL — direct image link from OMDb
    poster_url = data.get("Poster")
    if poster_url == "N/A":
        poster_url = None

    title = data.get("Title", "")
    year  = data.get("Year", "")[:4]

    # YouTube trailer search URL (no API key needed — yt-dlp handles download)
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

    print(f"[Step 1] Fetched: {movie_data['title']} ({movie_data['year']}) — {movie_data['rating']}/10")
    return movie_data


def save_movie_data(movie_data: dict, path: str = "assets/movie_data.json"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(movie_data, f, indent=2)
    print(f"[Step 1] Saved to {path}")


if __name__ == "__main__":
    from config.settings import validate_secrets
    validate_secrets()
    data = fetch_movie_data("tt0111161")
    save_movie_data(data)
    print(json.dumps(data, indent=2))