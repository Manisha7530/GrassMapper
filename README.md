# 🌿 GrassMapper — Touch Grass AI

> **Hacktoberfest 2026 | Week 1 — "Touch Grass" Challenge**  
> Built for [DEV Hacktoberfest Open-Source AI Challenge: Week 1](https://dev.to/challenges/hacktoberfest-week1-2026-10-05)

**GrassMapper** uses your device location and open-source AI to recommend nearby parks, libraries, restaurants, cafes, museums, playgrounds, and more — nudging you away from the screen and into the world.

---

## ✨ Features

- 📍 **Browser Geolocation** — detects where you are right now
- 🗺️ **OpenStreetMap Overpass API** — free, open, real-time place data (no Google Maps key needed)
- 🤖 **Local AI Recommendations** — runs Gemma 2 / llama3.2 via Ollama entirely on your machine
- 🔒 **100% Private** — your location never leaves your computer; AI runs locally
- ⚡ **Zero Cloud Cost** — no API keys, no paid services

---

## 🛠️ Tech Stack

| Layer | Technology | Why Open-Source? |
|---|---|---|
| **AI Inference** | [Ollama](https://ollama.ai) + Gemma 2 / llama3.2 | Runs locally; no data sent to external AI APIs |
| **Place Data** | [OpenStreetMap](https://openstreetmap.org) Overpass API | Free, community-owned, no API key |
| **Backend** | Python + Flask | Lightweight, open-source |
| **Frontend** | HTML/CSS/JS (vanilla) | No framework lock-in |
| **Geolocation** | Browser Geolocation API | Standard, privacy-respecting |

---

## 🚀 Quick Start

### Prerequisites

1. **Python 3.10+**
2. **[Ollama](https://ollama.ai)** installed and running

### Install & Run

```bash
# 1. Clone / enter the project
cd Hacktoberfest_week_1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start Ollama with an open model (pick one):
ollama pull gemma2:2b   # ~1.6 GB, recommended for Gemma category prize
# or: ollama pull llama3.2  # already available

ollama serve            # keep this running in a separate terminal

# 4. Start the app
python app.py

# 5. Open your browser
#    → http://localhost:5000
```

### Usage

1. Click **"📡 Use My Location"** — your browser will ask for permission
2. Optionally type what you're looking for (e.g. "quiet place to read")
3. Choose a search radius (500 m → 5 km)
4. Click **"🔍 Find Places"**
5. Read the AI's personalized recommendation and pick your adventure!

---

## 🌍 Why Open-Source AI Matters Here

This app does something closed AI models can't easily do:

- **Privacy by design** — your GPS coordinates go to OpenStreetMap (an open project) and your local Ollama instance. Nothing reaches OpenAI, Google, or any commercial AI cloud.
- **Works with no internet for AI** — once Ollama has the model, the AI recommendation works offline (only the OSM query needs network).
- **Swappable models** — swap Gemma 2 for Llama 3, Mistral, or any Ollama-compatible model in one line. Closed APIs lock you into one vendor.
- **Zero inference cost** — runs free forever on your own hardware.

---

## 🏆 Prize Categories Entered

- **Overall** — "Touch Grass" theme ✅
- **Best Use of Gemma** — uses `gemma2:2b` via Ollama ✅

---

## 📸 Screenshots

*(Add after first run)*

---

## 📄 License

MIT License — see [LICENSE](LICENSE)
