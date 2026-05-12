"""
Step 1 — Fetch Movie Data from TMDb API
Uses TMDb v3 with Bearer token auth.
Endpoints:
  /find/{imdb_id}?external_source=imdb_id  -> map IMDb ID to TMDb ID
  /movie/{tmdb_id}                          -> full metadata
  /movie/{tmdb_id}/credits                  -> cast & crew
Returns the same dict shape as the previous OMDb version, so downstream
pipeline steps don't need to change.
"""

import os
import json
import requests
from config.settings import TMDB_BEARER, TMDB_API_KEY, TMDB_BASE, TMDB_IMG_BASE


def _auth_headers():
    """TMDb Bearer auth if available, else fall back to v3 query param."""
    if TMDB_BEARER:
        return {"Authorization": f"Bearer {TMDB_BEARER}", "accept": "application/json"}
    return {"accept": "application/json"}


def _auth_params():
    """Fallback v3 API key param when no Bearer token is set."""
    return {"api_key": TMDB_API_KEY} if TMDB_API_KEY and not TMDB_BEARER else {}


def _get(path, params=None, timeout=20):
    params = dict(params or {})
    params.update(_auth_params())
    url = f"{TMDB_BASE}{path}"
    resp = requests.get(url, headers=_auth_headers(), params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def fetch_movie_data(imdb_id: str) -> dict:
    """
    Fetch full movie metadata from TMDb using the IMDb ID.
    Returns a dict in the same shape used by the rest of the pipeline.
    """
    # 1. Find TMDb ID from IMDb ID
    find_data = _get(f"/find/{imdb_id}", {"external_source": "imdb_id"})
    movie_results = find_data.get("movie_results", [])
    if not movie_results:
        raise ValueError(f"No TMDb match found for IMDb ID '{imdb_id}'")
    tmdb_id = movie_results[0]["id"]

    # 2. Full movie details + credits + videos in one append_to_response call
    movie = _get(f"/movie/{tmdb_id}", {
        "append_to_response": "credits,videos",
        "language": "en-US",
    })

    # ── Map TMDb response to our internal shape ──────────────────────────────
    title    = movie.get("title", "")
    year     = (movie.get("release_date") or "")[:4]
    overview = movie.get("overview", "")
    tagline  = movie.get("tagline", "") or ""
    runtime  = str(movie.get("runtime", 0))
    rating   = round(movie.get("vote_average", 0.0), 1)

    genres = [g["name"] for g in movie.get("genres", [])]

    # Cast — top 5 by 'order'
    credits = movie.get("credits", {})
    cast_list = sorted(credits.get("cast", []), key=lambda c: c.get("order", 999))
    cast = [c["name"] for c in cast_list[:5]]

    # Director
    director = "Unknown"
    for crew in credits.get("crew", []):
        if crew.get("job") == "Director":
            director = crew["name"]
            break

    # Language / Country
    spoken_languages = movie.get("spoken_languages", [])
    language = ", ".join(l.get("english_name", "") for l in spoken_languages)
    countries = movie.get("production_countries", [])
    country = ", ".join(c.get("name", "") for c in countries)

    # Poster + backdrop (full-resolution URLs)
    poster_path   = movie.get("poster_path")
    backdrop_path = movie.get("backdrop_path")
    poster_url    = f"{TMDB_IMG_BASE}/original{poster_path}"   if poster_path   else None
    backdrop_url  = f"{TMDB_IMG_BASE}/original{backdrop_path}" if backdrop_path else None

    # Trailer (first YouTube video tagged Trailer)
    trailer_url = None
    videos = (movie.get("videos") or {}).get("results", [])
    for v in videos:
        if v.get("site") == "YouTube" and v.get("type") == "Trailer":
            trailer_url = f"https://www.youtube.com/watch?v={v['key']}"
            break
    if not trailer_url:
        trailer_url = (
            "https://www.youtube.com/results?search_query="
            + title.replace(" ", "+") + "+" + year + "+official+trailer"
        )

    # Box office (TMDb has revenue, not box-office category strings)
    revenue = movie.get("revenue", 0)
    box_office = f"${revenue:,}" if revenue else "N/A"

    movie_data = {
        "imdb_id":      imdb_id,
        "tmdb_id":      tmdb_id,
        "title":        title,
        "year":         year,
        "tagline":      tagline,
        "overview":     overview,
        "genres":       genres,
        "runtime_min":  runtime,
        "rating":       rating,
        "director":     director,
        "cast":         cast,
        "language":     language,
        "country":      country,
        "awards":       "",            # TMDb doesn't expose awards
        "box_office":   box_office,
        "poster_url":   poster_url,
        "backdrop_url": backdrop_url,
        "trailer_url":  trailer_url,
    }

    print(f"[Step 1] Fetched: {title} ({year}) — {rating}/10 (TMDb #{tmdb_id})")
    return movie_data


def save_movie_data(movie_data: dict, path: str = "assets/movie_data.json"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(movie_data, f, indent=2)
    print(f"[Step 1] Saved to {path}")


if __name__ == "__main__":
    from config.settings import validate_secrets
    validate_secrets()
    data = fetch_movie_data("tt1187043")
    save_movie_data(data)
    print(json.dumps(data, indent=2))