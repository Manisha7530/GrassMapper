"""
GrassMapper - Hacktoberfest 2026 Week 1 "Touch Grass" Challenge
Open-source AI powered nearby place recommender.

Tech stack:
  - OpenStreetMap Overpass API: free, open geospatial data
  - Ollama (Gemma 2 / llama3.2): local open-source AI inference
  - Flask: lightweight Python web server
"""

import json
import math
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
# Public Overpass API mirrors — tried in order until one succeeds
OVERPASS_MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
OLLAMA_URL = "http://localhost:11434/api/generate"

# Prefer Gemma 2 for the Hacktoberfest category prize; fall back to llama3.2
PREFERRED_MODELS = ["gemma2:2b", "gemma2", "gemma:2b", "gemma", "llama3.2", "llama3"]

# Place categories to search
PLACE_CATEGORIES = {
    "park":      {"leisure": "park",     "emoji": "🌳"},
    "library":   {"amenity": "library",   "emoji": "📚"},
    "restaurant":{"amenity": "restaurant","emoji": "🍽️"},
    "cafe":      {"amenity": "cafe",      "emoji": "☕"},
    "museum":    {"tourism": "museum",    "emoji": "🏛️"},
    "playground":{"leisure": "playground","emoji": "🎡"},
    "sports":    {"leisure": "sports_centre", "emoji": "⚽"},
    "garden":    {"leisure": "garden",    "emoji": "🌸"},
}

# ──────────────────────────────────────────────
# Helper: pick the best available Ollama model
# ──────────────────────────────────────────────
def get_best_model():
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        if resp.ok:
            available = [m["name"] for m in resp.json().get("models", [])]
            for preferred in PREFERRED_MODELS:
                if any(preferred in m for m in available):
                    return next(m for m in available if preferred in m)
            if available:
                return available[0]
    except Exception:
        pass
    return "llama3.2"


# ──────────────────────────────────────────────
# Helper: Haversine distance (metres)
# ──────────────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ──────────────────────────────────────────────
# Overpass API: fetch nearby places
# ──────────────────────────────────────────────

# Identify this app to Overpass — plain "python-requests" gets 406-blocked
OVERPASS_HEADERS = {
    "User-Agent": "GrassMapper/1.0 (Hacktoberfest 2026; open-source)",
    "Accept": "*/*",
}


# Module-level mirror cache: once a mirror succeeds it's promoted to front,
# cutting subsequent per-category retries from 4 attempts to 1.
_working_mirror: str | None = None


def _post_overpass(query: str) -> tuple[list, str]:
    """Try each mirror in turn; cache and prefer the last working one."""
    global _working_mirror
    last_err = "unknown error"

    # Build trial order: cached winner first, then the rest
    ordered = list(OVERPASS_MIRRORS)
    if _working_mirror and _working_mirror in ordered:
        ordered.remove(_working_mirror)
        ordered.insert(0, _working_mirror)

    for mirror in ordered:
        try:
            print(f"Trying Overpass mirror: {mirror}")
            resp = requests.post(
                mirror,
                data={"data": query},
                headers=OVERPASS_HEADERS,
                timeout=12,
            )
            ct = resp.headers.get("Content-Type", "")
            if resp.status_code != 200 or "html" in ct:
                last_err = f"HTTP {resp.status_code} from {mirror}"
                print(f"  ✗ {mirror}: {last_err}")
                if mirror == _working_mirror:
                    _working_mirror = None  # evict stale cached mirror
                continue
            elements = resp.json().get("elements", [])
            print(f"  ✓ {mirror} → {len(elements)} elements")
            _working_mirror = mirror   # promote this mirror for next call
            return elements, ""
        except requests.exceptions.Timeout:
            last_err = f"timeout on {mirror}"
            print(f"  ✗ {mirror}: timeout")
            if mirror == _working_mirror:
                _working_mirror = None
        except requests.exceptions.ConnectionError:
            last_err = f"connection refused by {mirror}"
            print(f"  ✗ {mirror}: connection error")
            if mirror == _working_mirror:
                _working_mirror = None
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            print(f"  ✗ {mirror}: {last_err}")
    return [], last_err


# ── Per-category Overpass template (much smaller than one giant union) ─────────
def _build_category_query(key: str, value: str, lat: float, lon: float, radius: int) -> str:
    return (
        f'[out:json][timeout:10];\n'
        f'(\n'
        f'  node["{key}"="{value}"](around:{radius},{lat},{lon});\n'
        f'  way["{key}"="{value}"](around:{radius},{lat},{lon});\n'
        f');\n'
        f'out center 15;\n'
    )


def _nominatim_search(lat: float, lon: float, amenity: str, radius: int) -> list:
    """Fallback: Nominatim /search — a different OSM-backed endpoint."""
    deg = radius / 111_000  # rough degrees per metre
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": amenity,
        "format": "jsonv2",
        "limit": 10,
        "viewbox": f"{lon-deg},{lat+deg},{lon+deg},{lat-deg}",
        "bounded": 1,
    }
    headers = {"User-Agent": "GrassMapper/1.0 (Hacktoberfest 2026; open-source)"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.ok and "html" not in r.headers.get("Content-Type", ""):
            return r.json()
    except Exception as e:
        print(f"  Nominatim error for '{amenity}': {e}")
    return []


NOMINATIM_TERMS = {
    "park": "park", "library": "library", "restaurant": "restaurant",
    "cafe": "cafe", "museum": "museum", "playground": "playground",
    "sports": "sports centre", "garden": "garden",
}


def _parse_nominatim(results: list, cat: str, meta: dict,
                     user_lat: float, user_lon: float) -> list:
    places = []
    for r in results:
        name = r.get("display_name", "").split(",")[0].strip()
        if not name:
            continue
        try:
            elat, elon = float(r["lat"]), float(r["lon"])
        except (KeyError, ValueError):
            continue
        places.append({
            "name": name, "category": cat, "emoji": meta["emoji"],
            "distance_m": round(haversine(user_lat, user_lon, elat, elon)),
            "lat": elat, "lon": elon, "tags": {}, "source": "nominatim",
        })
    return places


def fetch_nearby_places(lat: float, lon: float, radius: int = 2000) -> tuple[list, str]:
    """Fetch nearby places using Overpass (per-category) with Nominatim fallback.

    Returns (places_list, error_reason).  error_reason is '' on success.
    """
    all_places: list = []
    overpass_worked = False
    last_error = ""

    # ── Strategy 1: Overpass, one small focused query per category ────────────
    for cat, meta in PLACE_CATEGORIES.items():
        for key, value in meta.items():
            if key == "emoji":
                continue
            query = _build_category_query(key, value, lat, lon, radius)
            elements, err = _post_overpass(query)
            if err:
                last_error = err
            if not elements:
                continue
            overpass_worked = True
            seen: set = set()
            for el in elements:
                tags = el.get("tags", {})
                name = tags.get("name") or tags.get("name:en", "")
                if not name or name in seen:
                    continue
                seen.add(name)
                elat = el.get("lat") or (el.get("center") or {}).get("lat")
                elon = el.get("lon") or (el.get("center") or {}).get("lon")
                if not elat or not elon:
                    continue
                all_places.append({
                    "name": name, "category": cat, "emoji": meta["emoji"],
                    "distance_m": round(haversine(lat, lon, elat, elon)),
                    "lat": elat, "lon": elon,
                    "tags": {k: v for k, v in tags.items() if k in
                             ("opening_hours", "phone", "website", "cuisine", "description")},
                    "source": "overpass",
                })

    # ── Strategy 2: Nominatim fallback ────────────────────────────────────────
    if not overpass_worked:
        print("All Overpass mirrors failed — falling back to Nominatim")
        for cat, meta in PLACE_CATEGORIES.items():
            term = NOMINATIM_TERMS.get(cat, cat)
            results = _nominatim_search(lat, lon, term, radius)
            all_places.extend(_parse_nominatim(results, cat, meta, lat, lon))
        if all_places:
            last_error = ""

    if not all_places:
        return [], last_error or "No places found from any data source."

    # Deduplicate, sort by distance, cap at 20
    seen_names: set = set()
    unique: list = []
    for p in sorted(all_places, key=lambda x: x["distance_m"]):
        if p["name"] not in seen_names:
            seen_names.add(p["name"])
            unique.append(p)
        if len(unique) >= 20:
            break
    return unique, ""


# ──────────────────────────────────────────────
# Ollama: generate AI recommendations
# ──────────────────────────────────────────────
def ask_ai(places: list[dict], user_hint: str = "") -> str:
    model = get_best_model()
    place_list = "\n".join(
        f"- {p['emoji']} {p['name']} ({p['category']}, {p['distance_m']}m away)"
        + (f" — {p['tags']}" if p["tags"] else "")
        for p in places[:12]
    )
    hint_text = f"\nThe user mentioned: \"{user_hint}\"." if user_hint else ""
    prompt = f"""You are a friendly local guide helping someone explore their neighbourhood and spend time outdoors.{hint_text}

Here are nearby places found via OpenStreetMap:
{place_list}

Give a short, warm recommendation (3–5 sentences). Pick the 2–3 best spots, explain why they're worth visiting, and encourage the person to get outside and enjoy them. Be specific and use the place names."""

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        return f"(AI unavailable – is Ollama running? Error: {e})"


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/recommend", methods=["POST"])
def recommend():
    data = request.get_json(force=True)
    lat = data.get("lat")
    lon = data.get("lon")
    hint = data.get("hint", "")
    radius = int(data.get("radius", 2000))

    if lat is None or lon is None:
        return jsonify({"error": "lat/lon required"}), 400

    places, error_reason = fetch_nearby_places(lat, lon, radius)
    if not places:
        return jsonify({
            "places": [],
            "ai_suggestion": (
                f"⚠️ Could not retrieve places: {error_reason}\n\n"
                "The OpenStreetMap Overpass API mirrors may be temporarily overloaded. "
                "Try again in a minute, or increase the search radius."
            ) if error_reason else "No places found nearby. Try increasing the search radius.",
            "error_reason": error_reason,
            "count": 0,
        })

    ai_text = ask_ai(places, hint)
    model_used = get_best_model()

    return jsonify({
        "places": places,
        "ai_suggestion": ai_text,
        "model_used": model_used,
        "count": len(places),
        "error_reason": "",
    })


# ──────────────────────────────────────────────
# Embedded HTML/CSS/JS frontend
# ──────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GrassMapper 🌿 – Touch Grass AI</title>
<style>
  :root {
    --green: #2d7a4f;
    --light-green: #e8f5ee;
    --accent: #f59e0b;
    --bg: #f9fafb;
    --card: #ffffff;
    --text: #1f2937;
    --muted: #6b7280;
    --radius: 12px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }
  header {
    background: var(--green);
    color: white;
    padding: 1.25rem 1.5rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  }
  header h1 { font-size: 1.5rem; font-weight: 700; }
  header p  { font-size: 0.85rem; opacity: 0.85; }
  .badge {
    margin-left: auto;
    background: rgba(255,255,255,0.15);
    padding: 0.3rem 0.75rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    white-space: nowrap;
  }
  main {
    max-width: 820px;
    margin: 2rem auto;
    padding: 0 1rem;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }
  .card {
    background: var(--card);
    border-radius: var(--radius);
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    padding: 1.5rem;
  }
  .card h2 { font-size: 1.1rem; font-weight: 700; margin-bottom: 1rem; }
  .controls {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: flex-end;
  }
  .field { display: flex; flex-direction: column; gap: 0.3rem; flex: 1; min-width: 140px; }
  label { font-size: 0.8rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
  input, select {
    padding: 0.55rem 0.75rem;
    border: 1.5px solid #d1d5db;
    border-radius: 8px;
    font-size: 0.95rem;
    background: white;
    outline: none;
    transition: border-color 0.2s;
  }
  input:focus, select:focus { border-color: var(--green); }
  .btn {
    padding: 0.6rem 1.4rem;
    border: none;
    border-radius: 8px;
    font-size: 0.95rem;
    font-weight: 700;
    cursor: pointer;
    transition: transform 0.1s, opacity 0.2s;
  }
  .btn:active { transform: scale(0.97); }
  .btn-primary { background: var(--green); color: white; }
  .btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
  .btn-secondary { background: var(--light-green); color: var(--green); }
  .status {
    font-size: 0.85rem;
    color: var(--muted);
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .spinner {
    width: 14px; height: 14px;
    border: 2px solid #d1d5db;
    border-top-color: var(--green);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    display: inline-block;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .ai-box {
    background: var(--light-green);
    border-left: 4px solid var(--green);
    border-radius: 0 var(--radius) var(--radius) 0;
    padding: 1rem 1.25rem;
    line-height: 1.6;
    font-size: 0.97rem;
  }
  .model-tag {
    font-size: 0.72rem;
    background: var(--green);
    color: white;
    padding: 0.15rem 0.5rem;
    border-radius: 999px;
    margin-left: 0.5rem;
    vertical-align: middle;
  }
  .places-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 0.75rem;
  }
  .place-card {
    border: 1.5px solid #e5e7eb;
    border-radius: var(--radius);
    padding: 0.85rem 1rem;
    transition: box-shadow 0.2s, border-color 0.2s;
    text-decoration: none;
    color: inherit;
    display: block;
  }
  .place-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    border-color: var(--green);
  }
  .place-card .name { font-weight: 700; font-size: 0.95rem; margin: 0.2rem 0; }
  .place-card .meta { font-size: 0.8rem; color: var(--muted); }
  .place-card .dist {
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--green);
    margin-top: 0.4rem;
  }
  .place-card .tag {
    font-size: 0.72rem;
    background: #f3f4f6;
    color: var(--muted);
    padding: 0.1rem 0.45rem;
    border-radius: 999px;
    display: inline-block;
    margin-top: 0.3rem;
  }
  .empty { text-align: center; padding: 2rem; color: var(--muted); }
  .coords-display {
    font-size: 0.8rem;
    color: var(--muted);
    font-family: monospace;
  }
  footer {
    text-align: center;
    padding: 2rem 1rem;
    font-size: 0.8rem;
    color: var(--muted);
  }
  footer a { color: var(--green); }
</style>
</head>
<body>
<header>
  <div>
    <h1>🌿 GrassMapper</h1>
    <p>Open-source AI finds your next outdoor adventure</p>
  </div>
  <span class="badge">🤖 Powered by Ollama + OSM</span>
</header>

<main>
  <!-- Controls -->
  <div class="card">
    <h2>📍 Find Places Near You</h2>
    <div class="controls">
      <div class="field">
        <label>Search radius</label>
        <select id="radius">
          <option value="500">500 m</option>
          <option value="1000">1 km</option>
          <option value="2000" selected>2 km</option>
          <option value="5000">5 km</option>
        </select>
      </div>
      <div class="field" style="flex:2">
        <label>What are you looking for? (optional)</label>
        <input id="hint" type="text" placeholder="e.g. quiet place to read, somewhere to walk my dog…">
      </div>
      <button class="btn btn-secondary" onclick="getLocation()">📡 Use My Location</button>
      <button class="btn btn-primary" id="searchBtn" onclick="search()" disabled>🔍 Find Places</button>
    </div>
    <div style="margin-top:0.75rem">
      <span id="status" class="status">Click "Use My Location" to start.</span>
      <span id="coordsDisplay" class="coords-display" style="margin-left:1rem"></span>
    </div>
  </div>

  <!-- AI Recommendation -->
  <div class="card" id="aiCard" style="display:none">
    <h2>🤖 AI Recommendation <span id="modelTag" class="model-tag"></span></h2>
    <div class="ai-box" id="aiText"></div>
  </div>

  <!-- Places Grid -->
  <div class="card" id="placesCard" style="display:none">
    <h2 id="placesHeading">Nearby Places</h2>
    <div class="places-grid" id="placesGrid"></div>
  </div>
</main>

<footer>
  Built for <a href="https://dev.to/challenges/hacktoberfest-week1-2026-10-05" target="_blank">Hacktoberfest Week 1 – Touch Grass</a> &nbsp;|&nbsp;
  Places data © <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap contributors</a> &nbsp;|&nbsp;
  AI by <a href="https://ollama.ai" target="_blank">Ollama</a> (local, private)
</footer>

<script>
let userLat = null, userLon = null;

function setStatus(msg, loading = false) {
  const s = document.getElementById('status');
  s.innerHTML = loading ? '<span class="spinner"></span> ' + msg : msg;
}

function getLocation() {
  setStatus('Requesting location…', true);
  if (!navigator.geolocation) {
    setStatus('❌ Geolocation not supported by your browser.');
    return;
  }
  navigator.geolocation.getCurrentPosition(
    pos => {
      userLat = pos.coords.latitude;
      userLon = pos.coords.longitude;
      document.getElementById('coordsDisplay').textContent =
        `lat ${userLat.toFixed(5)}, lon ${userLon.toFixed(5)}`;
      document.getElementById('searchBtn').disabled = false;
      setStatus('✅ Location acquired! Hit "Find Places".');
    },
    err => {
      setStatus('❌ Could not get location: ' + err.message);
    },
    { enableHighAccuracy: true }
  );
}

async function search() {
  if (userLat === null) { alert('Please get your location first.'); return; }
  const btn = document.getElementById('searchBtn');
  btn.disabled = true;
  setStatus('Querying OpenStreetMap & asking AI…', true);

  // Hide previous results
  document.getElementById('aiCard').style.display = 'none';
  document.getElementById('placesCard').style.display = 'none';

  try {
    const res = await fetch('/api/recommend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lat: userLat,
        lon: userLon,
        hint: document.getElementById('hint').value,
        radius: parseInt(document.getElementById('radius').value),
      }),
    });
    const data = await res.json();
    renderResults(data);
    setStatus(`✅ Found ${data.count || 0} places nearby.`);
  } catch (e) {
    setStatus('❌ Error: ' + e.message);
  } finally {
    btn.disabled = false;
  }
}

function renderResults(data) {
  // AI card
  const aiCard = document.getElementById('aiCard');
  if (data.ai_suggestion) {
    document.getElementById('aiText').textContent = data.ai_suggestion;
    document.getElementById('modelTag').textContent = data.model_used || 'AI';
    aiCard.style.display = '';
  }

  // Places grid
  const grid = document.getElementById('placesGrid');
  grid.innerHTML = '';
  const places = data.places || [];
  if (places.length === 0) {
    grid.innerHTML = '<div class="empty">😕 No places found. Try a larger radius.</div>';
  } else {
    document.getElementById('placesHeading').textContent =
      `Nearby Places (${places.length})`;
    places.forEach(p => {
      const mapsUrl = `https://www.openstreetmap.org/?mlat=${p.lat}&mlon=${p.lon}&zoom=17`;
      const card = document.createElement('a');
      card.href = mapsUrl;
      card.target = '_blank';
      card.className = 'place-card';

      const dist = p.distance_m < 1000
        ? p.distance_m + ' m'
        : (p.distance_m / 1000).toFixed(1) + ' km';

      let extras = '';
      if (p.tags.opening_hours) extras += `<span class="tag">⏰ ${p.tags.opening_hours}</span> `;
      if (p.tags.cuisine)       extras += `<span class="tag">🍴 ${p.tags.cuisine}</span>`;

      card.innerHTML = `
        <div style="font-size:1.6rem">${p.emoji}</div>
        <div class="name">${p.name}</div>
        <div class="meta">${p.category}</div>
        <div class="dist">📏 ${dist} away</div>
        ${extras}
      `;
      grid.appendChild(card);
    });
  }
  document.getElementById('placesCard').style.display = '';
}
</script>
</body>
</html>"""


if __name__ == "__main__":
    print("🌿 GrassMapper starting…")
    print("   Open http://localhost:5000 in your browser")
    print("   Make sure Ollama is running: ollama serve")
    app.run(debug=True, port=5000)
