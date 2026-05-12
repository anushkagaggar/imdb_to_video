# IMDb to 2-Minute Video Pipeline

Automatically generate a polished 1080p 2-minute movie promo video from any IMDb ID.
Uses free APIs and ffmpeg — fully reproducible.

---

## Project Structure

```
imdb_to_video/
│
├── main.py                        <- Run this
├── requirements.txt
├── .env.example                   <- Copy to .env and fill keys
│
├── config/
│   ├── __init__.py
│   └── settings.py                <- All constants in one place
│
├── modules/
│   ├── __init__.py
│   ├── utils.py                   <- Shared helpers
│   ├── step1_fetch_data.py        <- TMDb API — movie metadata + image URLs
│   ├── step2_generate_script.py   <- Groq LLM — narration script
│   ├── step3_text_to_speech.py    <- gTTS — voiceover MP3
│   ├── step4_assemble_visuals.py  <- TMDb backdrops/posters + optional trailer
│   └── step5_render_video.py      <- FFmpeg — final 1080p MP4
│
└── assets/                        <- Auto-created at runtime
    ├── movie_data.json
    ├── script.json
    ├── script.md
    ├── visual_manifest.json
    ├── images/
    ├── audio/
    ├── clips/
    └── output/                    <- Final video lands here
```

---

## APIs & Tools Used

| Service     | Purpose                                       | Free Tier                    |
|-------------|-----------------------------------------------|------------------------------|
| TMDb API    | Movie metadata + curated backdrops & posters  | Unlimited (auth required)    |
| Groq API    | LLM script generation (Llama 3.1)             | 14,400 requests/day          |
| gTTS        | Google Text-to-Speech voiceover               | Unlimited (no key needed)    |
| yt-dlp      | Optional YouTube trailer download             | No API key needed            |
| FFmpeg      | Video rendering + encoding (via imageio)      | Open source, bundled via pip |
| Chosic      | Royalty-free background music (CC)            | Optional                     |

### Why TMDb (not IMDb / OMDb)?

- **IMDb** has no public images API and aggressively rate-limits scraping.
- **OMDb** provides only the main poster — no stills or backdrops.
- **TMDb** exposes a free, well-documented `/movie/{id}/images` endpoint that returns 15+ curated backdrops and 25+ posters per popular film, served from a global CDN. TMDb is the industry-standard movie metadata source used by Plex, Jellyfin, Letterboxd, and most film tooling.

---

## Setup

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

This installs `imageio-ffmpeg` which bundles a portable FFmpeg binary — no system install required. The pipeline auto-detects and uses it.

### 2. Get your free API keys

**TMDb API Key**
1. Sign up at https://www.themoviedb.org/signup
2. Go to https://www.themoviedb.org/settings/api → Request API key → "Developer" → fill the form
3. Copy your **API Read Access Token** (the long `eyJ...` token) and paste it as `TMDB_BEARER` in `.env`

> TMDb API access may require a VPN in some regions during signup.

**Groq API Key**
1. Sign up at https://console.groq.com
2. Go to API Keys → Create New Key
3. Paste it as `GROQ_API_KEY` in `.env`

### 3. Configure environment
```bash
cp .env.example .env
# Then edit .env and add your TMDB_BEARER and GROQ_API_KEY values
```

---

## Usage

```bash
python main.py --imdb tt1187043
```

### Finding an IMDb ID
Go to any IMDb movie page — the ID is in the URL:
```
https://www.imdb.com/title/tt0111161/
                              ^^^^^^^^^
                         This is the IMDb ID
```

### Example IMDb IDs
| Movie                       | IMDb ID    |
|-----------------------------|------------|
| The Shawshank Redemption    | tt0111161  |
| The Dark Knight             | tt0468569  |
| Inception                   | tt1375666  |
| Interstellar                | tt0816692  |
| Oppenheimer                 | tt15398776 |
| 3 Idiots                    | tt1187043  |
| Dangal                      | tt5074352  |

---

## Pipeline Steps

```
IMDb ID
   │
   ▼
[Step 1] TMDb API ─► movie_data.json
   │      Maps imdb_id ─► tmdb_id, then fetches:
   │      title, cast, director, plot, genres, rating, poster, backdrop, trailer URL
   │
   ▼
[Step 2] Groq LLM (Llama 3.1) ─► script.json + script.md
   │      4-segment timed script (HOOK ─► CONTEXT ─► PLOT_TEASE ─► CTA)
   │
   ▼
[Step 3] gTTS ─► narration_final.mp3
   │      Voiceover at natural speed (no slowdown)
   │
   ▼
[Step 4] TMDb /movie/{id}/images ─► visual_manifest.json
   │      Downloads ~20 unique backdrops + posters, resized to 1080p
   │      Each image displays for 6 seconds (20 × 6 = 120 seconds)
   │      Quality-filtered (rejects undersized / low-detail images)
   │
   ▼
[Step 5] FFmpeg ─► {title}_2min.mp4
          Ken Burns zoom + narration + optional BG music
          1920x1080 @ 30fps, H.264 high profile, exactly 120 seconds
```

---

## Design Decisions

### Image strategy: 20 images × 6 seconds each
After testing alternatives, this gives the cleanest viewing experience. Faster cuts (1 image/second) feel like a slideshow; longer holds (12+ seconds) feel static. With TMDb returning ~15 backdrops + ~30 posters per popular film, 20 unique images is achievable without duplication for most movies.

### Duration enforcement
The pipeline strictly produces 120-second videos. If the narration script is shorter than 120 seconds (gTTS is variable), the final image freezes via FFmpeg's `tpad=stop_mode=clone` filter and audio is padded with silence using `apad`. If narration runs long, it's sped up slightly via `atempo` (never slowed down — that sounds unnatural).

### Optional trailer integration
The pipeline includes optional YouTube trailer download via yt-dlp to enhance the final 30 seconds. Due to YouTube's bot detection in 2026, this requires the latest yt-dlp version and may fail in some regions. **The pipeline gracefully falls back to image-only rendering when trailer download fails** — the video still produces a complete, exactly-120-second output.

To enable: `pip install --upgrade --pre yt-dlp` and re-run. If your region or network blocks YouTube downloads, simply leave it disabled.

---

## Output Files

| File                              | Description              |
|-----------------------------------|--------------------------|
| assets/movie_data.json            | TMDb metadata            |
| assets/script.json                | Timed narration script   |
| assets/script.md                  | Human-readable script    |
| assets/audio/narration_final.mp3  | 2-min voiceover          |
| assets/visual_manifest.json       | Asset-to-timestamp map   |
| assets/images/still_*.jpg         | Downloaded movie stills  |
| **assets/output/{title}_2min.mp4**| **Final 1080p video**    |

---

## Troubleshooting

| Problem                              | Fix                                                                |
|--------------------------------------|--------------------------------------------------------------------|
| `TMDB_BEARER not set`                | Copy `.env.example` to `.env` and add your Read Access Token       |
| `No TMDb match found for IMDb ID`    | Verify the ID starts with `tt` and exists on IMDb                  |
| TMDb API request times out           | TMDb may be geo-restricted; try a VPN (Proton / Cloudflare WARP)   |
| `yt-dlp failed: HTTP 403`            | YouTube bot detection; pipeline continues without trailer          |
| `BG music download failed: 403`      | Chosic URL changed; pipeline continues without background music    |
| `FFmpeg not found`                   | Run `pip install --upgrade imageio[ffmpeg]`                        |
| Script generates fewer than 280 words| Re-run Step 2; Groq output length varies per call                  |
| Video output shorter than 120 s      | Re-run; the `tpad` + `-t 120` should always produce exactly 2 min  |

---

## Licence

MIT — free to use, modify, distribute.
Movie data and images provided by [The Movie Database (TMDb)](https://www.themoviedb.org).
This product uses the TMDb API but is not endorsed or certified by TMDb.