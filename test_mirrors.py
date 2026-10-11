"""Direct mirror connectivity test — run standalone, no app import needed."""
import requests

HEADERS = {
    "User-Agent": "GrassMapper/1.0 (Hacktoberfest 2026; open-source)",
    "Accept": "*/*",
}

# Minimal valid query: a handful of cafes near New Delhi (same coords as test_overpass.py)
MINIMAL_QUERY = '[out:json][timeout:10];node["amenity"="cafe"](around:500,28.6408,77.0348);out 3;'

mirrors = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

print("Testing Overpass mirrors with a minimal query…\n")
for url in mirrors:
    try:
        r = requests.post(url, data={"data": MINIMAL_QUERY}, headers=HEADERS, timeout=15)
        print(f"[{r.status_code}] {url}")
        if r.status_code == 200:
            j = r.json()
            print(f"  → elements returned: {len(j.get('elements', []))}")
        else:
            print(f"  → response body: {r.text[:200]}")
    except Exception as e:
        print(f"[ERR] {url}  {type(e).__name__}: {e}")
