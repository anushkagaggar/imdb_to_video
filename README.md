# IMDb to 2-Minute Video Pipeline

Automatically generate a polished 2-minute movie promo video from any IMDb ID.
Uses only **free APIs** — fully accessible in India.

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
│   ├── step1_fetch_data.py        <- OMDb API — movie metadata + poster URL
│   ├── step2_generate_script.py   <- Groq LLM — narration script
│   ├── step3_text_to_speech.py    <- gTTS — voiceover MP3
│   ├── step4_assemble_visuals.py  <- OMDb poster + yt-dlp trailer
│   └── step5_render_video.py      <- FFmpeg — final MP4
│
└── assets/                        <- Auto-created at runtime
    ├── movie_data.json
    ├── script.json
    ├── script.md
    ├── visual_manifest.json
    ├── images/
    ├── audio/
    ├── clips/
    └── output/                    <- Your final video lands here
```

---

## Free APIs Used

| Service     | Purpose                              | Free Tier                    |
|-------------|--------------------------------------|------------------------------|
| OMDb API    | Movie metadata + poster URL          | 1,000 requests/day           |
| Groq API    | LLM script generation (Llama 3)      | 14,400 requests/day          |
| gTTS        | Google Text-to-Speech voiceover      | Unlimited (no key needed)    |
| yt-dlp      | YouTube trailer download             | No API key needed            |
| FFmpeg      | Video rendering + encoding           | Open source                  |
| Chosic      | Royalty-free background music (CC)   | Free download                |

---

## Setup

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Install FFmpeg
```bash
# Ubuntu / Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows — https://ffmpeg.org/download.html
```

### 3. Get your free API keys

**OMDb API Key** (free, works in India):
1. Go to https://www.omdbapi.com/apikey.aspx
2. Select the FREE plan (1,000 daily requests)
3. Enter your email and click Submit
4. Check your email and click the activation link
5. Your key arrives in the same email — paste it in `.env`

> Your key: already provided as `8d603e91`

**Groq API Key** (free):
1. Sign up at https://console.groq.com
2. Go to API Keys → Create New Key
3. Paste it in `.env`

### 4. Configure environment
```bash
cp .env.example .env
# .env already has OMDB_API_KEY=8d603e91 — just add your GROQ key
```

---

## Usage

```bash
# Basic — provide any IMDb ID
python main.py --imdb tt0111161

# Re-run without re-downloading cached assets
python main.py --imdb tt0111161 --skip-download
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
   |
   v
[Step 1] OMDb API -> movie_data.json
   |      Title, cast, director, plot, genres, rating, poster URL
   |      Single API call — no TMDb needed
   |
   v
[Step 2] Groq LLM (Llama 3) -> script.json + script.md
   |      4-segment timed script (~300 words / 2 min)
   |      HOOK (0-10s) -> CONTEXT (10-30s) -> PLOT_TEASE (30-90s) -> CTA (90-120s)
   |
   v
[Step 3] gTTS -> narration_final.mp3
   |      Voiceover padded/trimmed to exactly 120 seconds
   |
   v
[Step 4] OMDb poster + generated cards + yt-dlp trailer -> visual_manifest.json
   |      Title card, poster, cast card, trailer clip — all timestamped
   |
   v
[Step 5] FFmpeg -> {title}_2min.mp4
          Ken Burns zoom on images + narration + BG music
          1280x720, H.264, exactly 2 minutes
```

---

## Output Files

| File                              | Description              |
|-----------------------------------|--------------------------|
| assets/movie_data.json            | Raw OMDb metadata        |
| assets/script.json                | Timed narration script   |
| assets/script.md                  | Human-readable script    |
| assets/audio/narration_final.mp3  | 2-min voiceover          |
| assets/visual_manifest.json       | Asset to timestamp map   |
| assets/output/{title}_2min.mp4    | **Final video**          |

---

## Troubleshooting

| Problem                        | Fix                                                        |
|--------------------------------|------------------------------------------------------------|
| `OMDB_API_KEY not set`         | Copy `.env.example` to `.env`                             |
| `OMDb error: Movie not found`  | Check the IMDb ID starts with `tt`                        |
| Poster is black / missing      | OMDb occasionally returns N/A; title card used as fallback |
| `yt-dlp failed`                | Trailer region-locked; video still renders without clip    |
| `FFmpeg not found`             | Run `sudo apt install ffmpeg`                              |
| Script too short               | Re-run Step 2; Groq output varies slightly per call        |

---

## Licence

MIT — free to use, modify, distribute.
Background music licensed under Creative Commons (Chosic).
Movie data provided by OMDb API — not for commercial redistribution.