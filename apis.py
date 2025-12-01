# apis.py
import requests
from typing import List, Dict, Optional
from math import radians, sin, cos, sqrt, atan2

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance en mètres entre deux points lat/lon (haversine)."""
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def get_address_suggestions(query: str, limit: int = 5) -> List[Dict]:
    """Suggestions d’adresses via Nominatim."""
    if not query or len(query.strip()) < 3:
        return []

    headers = {"User-Agent": "LibertEstimation/1.0"}
    params = {
        "q": query,
        "format": "json",
        "limit": limit,
        "addressdetails": 1,
        "countrycodes": "fr",
    }

    try:
        r = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=5)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    out: List[Dict] = []
    for d in data:
        try:
            out.append(
                {
                    "label": d.get("display_name", ""),
                    "lat": float(d["lat"]),
                    "lon": float(d["lon"]),
                }
            )
        except Exception:
            continue

    return out


def fetch_osm_context(lat: float, lon: float) -> Dict:
    """
    Contexte minimal depuis OSM :
      - building_type : IMMEUBLE / PAVILLON
      - facade_rue_m  : plus grand segment
      - facade_cour_m : second plus grand segment
      - depth_m       : moyenne des autres segments
      - levels_osm    : niveaux si renseigné
      - has_cour      : True si façade cour significative
    """
    query = f"""
    [out:json][timeout:10];
    (
      way["building"](around:50,{lat},{lon});
    );
    out geom;
    """

    headers = {"User-Agent": "LibertEstimation/1.0"}

    def _minimal() -> Dict:
        return {
            "building_type": "IMMEUBLE",
            "facade_rue_m": None,
            "facade_cour_m": None,
            "depth_m": None,
            "levels_osm": None,
            "has_cour": False,
            "is_haussmann_suspected": False,
        }

    try:
        r = requests.post(OVERPASS_URL, data={"data": query}, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return _minimal()

    ways = [e for e in data.get("elements", []) if e.get("type") == "way" and "geometry" in e]
    if not ways:
        return _minimal()

    way = ways[0]
    geom = way["geometry"]
    tags = way.get("tags", {})

    coords = [(p["lat"], p["lon"]) for p in geom]
    if len(coords) < 3:
        return _minimal()
    if coords[0] != coords[-1]:
        coords.append(coords[0])

    segments = []
    for i in range(len(coords) - 1):
        lat1, lon1 = coords[i]
        lat2, lon2 = coords[i + 1]
        d = _dist_m(lat1, lon1, lat2, lon2)
        segments.append({"length": d, "p1": coords[i], "p2": coords[i + 1]})

    if not segments:
        return _minimal()

    segs_sorted = sorted(segments, key=lambda s: s["length"], reverse=True)
    seg_rue = segs_sorted[0]
    seg_cour = segs_sorted[1] if len(segs_sorted) > 1 else None

    facade_rue_m = seg_rue["length"]
    facade_cour_m = seg_cour["length"] if seg_cour else None

    others = [s["length"] for s in segs_sorted[2:]]
    depth_m = sum(others) / len(others) if others else facade_rue_m

    building_tag = tags.get("building", "")
    if building_tag in ("house", "detached", "semidetached_house"):
        building_type = "PAVILLON"
    else:
        building_type = "IMMEUBLE"

    levels_osm = None
    if "building:levels" in tags:
        try:
            levels_osm = int(tags["building:levels"])
        except Exception:
            levels_osm = None

    has_cour = bool(facade_cour_m and facade_cour_m > 0.4 * facade_rue_m)

    is_haussmann_suspected = (
        tags.get("building") == "apartments"
        and levels_osm is not None
        and 4 <= levels_osm <= 7
        and facade_rue_m > 10
    )

    return {
        "building_type": building_type,
        "facade_rue_m": facade_rue_m,
        "facade_cour_m": facade_cour_m,
        "depth_m": depth_m,
        "levels_osm": levels_osm,
        "has_cour": has_cour,
        "is_haussmann_suspected": is_haussmann_suspected,
    }


def build_streetview_embed_url(
    lat: float,
    lon: float,
    api_key: Optional[str] = None,
    heading: float = 0.0,
) -> str:
    """URL d’embed Street View (ou simple carte si pas de clé)."""
    if not api_key:
        return f"https://www.google.com/maps?q={lat},{lon}&z=19&output=embed"

    return (
        "https://www.google.com/maps/embed/v1/streetview"
        f"?key={api_key}&location={lat},{lon}&heading={heading}&pitch=0&fov=90"
    )
