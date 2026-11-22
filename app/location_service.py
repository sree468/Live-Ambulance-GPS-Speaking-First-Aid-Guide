import math
import httpx

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return round(2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)


async def find_nearby_medical_facilities(lat: float, lon: float, radius_meters: int = 8000) -> list[dict]:
    headers = {"User-Agent": "Emergency108AI-StudentProject/1.0"}
    facilities = []

    query = f"""
    [out:json][timeout:10];
    (
      node["amenity"~"hospital|clinic|pharmacy|doctors"](around:{radius_meters},{lat},{lon});
      way["amenity"~"hospital|clinic|pharmacy|doctors"](around:{radius_meters},{lat},{lon});
      node["healthcare"~"hospital|clinic|pharmacy"](around:{radius_meters},{lat},{lon});
    );
    out center 25;
    """

    # 1. Try Overpass mirrors
    for url in OVERPASS_MIRRORS:
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
                resp = await client.post(url, data={"data": query})
                if resp.status_code == 200:
                    data = resp.json()
                    for el in data.get("elements", []):
                        tags = el.get("tags", {})
                        amenity = tags.get("amenity") or tags.get("healthcare") or "Medical Center"
                        name = tags.get("name") or tags.get("operator")
                        if not name:
                            continue
                        f_lat = el.get("lat") or el.get("center", {}).get("lat")
                        f_lon = el.get("lon") or el.get("center", {}).get("lon")
                        if f_lat and f_lon:
                            facilities.append({
                                "name": name,
                                "type": amenity.capitalize(),
                                "lat": f_lat,
                                "lon": f_lon,
                                "distance_km": calculate_distance_km(lat, lon, f_lat, f_lon),
                                "maps_url": f"https://www.google.com/maps/dir/?api=1&destination={f_lat},{f_lon}"
                            })
                    if facilities:
                        break
        except Exception as e:
            print(f"[Overpass Mirror Warning] {url}: {e}")

    # 2. Dynamic Nominatim fallback around user's exact (lat, lon) if Overpass fails
    if not facilities:
        delta = 0.08  # ~8.8 km bounding box around exact user coordinates
        viewbox = f"{lon - delta},{lat + delta},{lon + delta},{lat - delta}"
        for term, label in [("hospital", "Hospital"), ("pharmacy", "Pharmacy")]:
            try:
                params = {
                    "q": term,
                    "format": "json",
                    "bounded": 1,
                    "viewbox": viewbox,
                    "limit": 6,
                }
                async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
                    resp = await client.get(NOMINATIM_URL, params=params)
                    if resp.status_code == 200:
                        for item in resp.json():
                            f_lat, f_lon = float(item["lat"]), float(item["lon"])
                            short_name = item.get("display_name", "").split(",")[0]
                            facilities.append({
                                "name": short_name or f"Nearby {label}",
                                "type": label,
                                "lat": f_lat,
                                "lon": f_lon,
                                "distance_km": calculate_distance_km(lat, lon, f_lat, f_lon),
                                "maps_url": f"https://www.google.com/maps/dir/?api=1&destination={f_lat},{f_lon}"
                            })
            except Exception as e:
                print(f"[Nominatim Warning] {e}")

    # Deduplicate by name and sort by closest distance
    seen = set()
    unique_facilities = []
    for f in sorted(facilities, key=lambda x: x["distance_km"]):
        if f["name"] not in seen:
            seen.add(f["name"])
            unique_facilities.append(f)

    return unique_facilities[:8]