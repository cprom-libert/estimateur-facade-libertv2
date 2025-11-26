import requests
import math
from typing import List, Dict, Optional


def get_address_suggestions(query: str, limit: int = 5) -> List[Dict]:
    if len(query.strip()) < 3:
        return []

    url = "https://api-adresse.data.gouv.fr/search/"
    params = {"q": query, "limit": limit, "autocomplete": 1}
    resp = requests.get(url, params=params, timeout=5)
    resp.raise_for_status()
    data = resp.json()

    suggestions = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates") or [None, None]
        lon, lat = coords
        if lat and lon:
            suggestions.append(
                {"label": props.get("label"), "lat": lat, "lon": lon}
            )
    return suggestions


def fetch_osm_context(lat: float, lon: float, radius_m: int = 20) -> Dict:
    overpass_url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:25];
    (
      way["building"](around:{radius_m},{lat},{lon});
      relation["building"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    resp = requests.post(overpass_url, data=query.encode("utf-8"), timeout=25)
    resp.raise_for_status()
    data = resp.json()

    levels = None
    has_shop = False

    for el in data.get("elements", []):
        tags = el.get("tags", {})
        if not tags:
            continue

        lvl = tags.get("building:levels") or tags.get("levels")
        if lvl and levels is None:
            try:
                levels = int(lvl)
            except:
                pass

        if tags.get("shop"):
            has_shop = True

    return {"levels": levels, "has_shop": has_shop}


# --- Orientation Street View ---
def _deg_to_rad(deg): return deg * math.pi / 180
def _rad_to_deg(rad): return rad * 180 / math.pi


def _compute_bearing(lat1, lon1, lat2, lon2):
    phi1 = _deg_to_rad(lat1)
    phi2 = _deg_to_rad(lat2)
    dlon = _deg_to_rad(lon2 - lon1)

    y = math.sin(dlon) * math.cos(phi2)
    x = math.cos(phi1)*math.sin(phi2) - math.sin(phi1)*math.cos(phi2)*math.cos(dlon)

    brng = math.atan2(y, x)
    return (_rad_to_deg(brng) + 360) % 360


def _get_smart_heading(lat, lon, api_key):
    if not api_key:
        return None

    meta_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    params = {"location": f"{lat},{lon}", "size": "640x400", "key": api_key}

    try:
        resp = requests.get(meta_url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except:
        return None

    if data.get("status") != "OK":
        return None

    loc = data.get("location") or {}
    cam_lat = loc.get("lat")
    cam_lon = loc.get("lng")
    if not cam_lat or not cam_lon:
        return None

    return _compute_bearing(cam_lat, cam_lon, lat, lon)


def build_streetview_embed_url(lat, lon, api_key, pitch=10, fov=90):
    if not api_key:
        return "https://upload.wikimedia.org/wikipedia/commons/9/9b/Rue_des_Écoles_-_Paris_V_-_2021-07-31_-_1.jpg"

    heading = _get_smart_heading(lat, lon, api_key)

    base = "https://www.google.com/maps/embed/v1/streetview"
    params = f"key={api_key}&location={lat},{lon}&fov={fov}"
    if heading:
        params += f"&heading={heading:.1f}"
    params += f"&pitch={pitch}"

    return f"{base}?{params}"
