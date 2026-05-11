# 🎬 IMDb → 2-Minute Video Pipeline

Automatically generate a polished 2-minute movie promo video from any IMDb URL — using only **free APIs**.

---

## 🗂️ Project Structure

```
imdb_to_video/
│
├── main.py                        # ← Run this
├── requirements.txt
├── .env.example                   # Copy to .env and fill keys
│
├── config/
│   ├── __init__.py
│   └── settings.py                # All constants in one place
│
├── modules/
│   ├── __init__.py
│   ├── utils.py                   # Shared helpers
│   ├── step1_fetch_data.py        # TMDb API — movie metadata
│   ├── step2_generate_script.py   # Groq LLM — narration script
│   ├── step3_text_to_speech.py    # gTTS — voiceover MP3
│   ├── step4_assemble_visuals.py  # TMDb images + yt-dlp trailer
│   └── step5_render_video.py      # FFmpeg — final MP4
│
└── assets/                        # Auto-created at runtime
    ├── movie_data.json
    ├── script.json
    ├── script.md
    ├── visual_manifest.json
    ├── images/
    ├── audio/
    ├── clips/
    └── output/                    # ← Your final video lands here
```

---

## ⚙️ Free APIs Used

| Service | Purpose | Free Tier |
|---|---|---|
| **TMDb API** | Movie metadata, posters, stills | Unlimited (with key) |
| **Groq API** | LLM script generation (Llama 3) | 14,400 req/day free |
| **gTTS** | Google Text-to-Speech | Unlimited (no key) |
| **yt-dlp** | YouTube trailer download | No API needed |
| **FFmpeg** | Video rendering | Open source |
| **Chosic** | Royalty-free background music | CC licensed |

---

## 🚀 Setup

### 1. Clone & install dependencies
```bash
git clone <your-repo>
cd imdb_to_video
pip install -r requirements.txt
```

### 2. Install FFmpeg (if not installed)
```bash
# Ubuntu / Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows — download from https://ffmpeg.org/download.html
```

### 3. Get your free API keys

**TMDb API Key** (free):
1. Sign up at https://www.themoviedb.org/signup
2. Go to Settings → API → Create (Developer)
3. Copy your API Key (v3 auth)

**Groq API Key** (free):
1. Sign up at https://console.groq.com
2. Go to API Keys → Create New Key
3. Copy the key

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env and paste your keys
```

---

## ▶️ Usage

```bash
# Basic usage — provide any IMDb ID
python main.py --imdb tt0111161

# Skip re-downloading cached assets (faster re-runs)
python main.py --imdb tt0111161 --skip-download
```

### Finding an IMDb ID
Go to any movie on IMDb — the ID is in the URL:
```
https://www.imdb.com/title/tt0111161/
                              ↑
                         This is the IMDb ID
```

### Example IMDb IDs
| Movie | IMDb ID |
|---|---|
| The Shawshank Redemption | tt0111161 |
| The Dark Knight | tt0468569 |
| Inception | tt1375666 |
| Interstellar | tt0816692 |
| Oppenheimer | tt15398776 |

---

## 🎞️ Pipeline Steps

```
IMDb ID
   │
   ▼
[Step 1] TMDb API → movie_data.json
   │      Title, cast, director, synopsis, poster, trailer URL
   │
   ▼
[Step 2] Groq LLM → script.json + script.md
   │      4-segment timed script (~300 words / 2 min)
   │      HOOK → CONTEXT → PLOT_TEASE → CTA
   │
   ▼
[Step 3] gTTS → narration_final.mp3
   │      Voiceover padded/trimmed to exactly 120 seconds
   │
   ▼
[Step 4] TMDb Images + yt-dlp → visual_manifest.json
   │      Poster, backdrop, stills, trailer clip — all timestamped
   │
   ▼
[Step 5] FFmpeg → {title}_2min.mp4
          Ken Burns zoom on images + narration + BG music
          1280×720, H.264, 2 minutes exactly
```

---

## 📦 Output Files

| File | Description |
|---|---|
| `assets/movie_data.json` | Raw TMDb metadata |
| `assets/script.json` | Timed narration script |
| `assets/script.md` | Human-readable script |
| `assets/audio/narration_final.mp3` | 2-min voiceover |
| `assets/visual_manifest.json` | Asset → timestamp map |
| `assets/output/{title}_2min.mp4` | **Final video** |

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---|---|
| `TMDB_API_KEY not set` | Copy `.env.example` → `.env` and add keys |
| `No movie found for IMDb ID` | Check the IMDb ID is correct (starts with `tt`) |
| `yt-dlp failed` | Trailer may be region-locked; video still renders without it |
| `FFmpeg not found` | Install via `sudo apt install ffmpeg` |
| Script word count too low | Re-run Step 2; Groq may occasionally return shorter output |

---

## 📄 Licence

MIT — free to use, modify, and distribute.
Background music licensed under Creative Commons (Chosic).
Movie data © TMDb — not for commercial redistribution.