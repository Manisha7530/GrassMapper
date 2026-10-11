"""Quick end-to-end smoke test for GrassMapper's fetch_nearby_places."""
import sys
sys.path.insert(0, ".")
import app as grassmapper

print("Mirrors:", grassmapper.OVERPASS_MIRRORS)
places, error = grassmapper.fetch_nearby_places(28.64080, 77.03487, radius=5000)
print(f"\nfetch_nearby_places returned {len(places)} place(s), error='{error}':")
for p in places:
    print(f"  {p['emoji']} {p['name']}  ({p['category']}, {p['distance_m']}m) [{p.get('source','?')}]")
if not places:
    print(f"  (no results — reason: {error or 'unknown'})")
