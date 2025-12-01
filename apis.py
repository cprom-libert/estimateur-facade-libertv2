import math
from typing import Dict, Optional

import requests


def fetch_osm_context(lat: float, lon: float) -> Dict:
    """
    Récupère quelques infos OSM pour affiner les ordres de grandeur :
    - nombre de niveaux si disponible
    - dimensions approximatives via la bounding box
    Si OSM ne répond pas, on retourne des valeurs par défaut.
    """
    ctx: Dict = {
        "levels": 5,
        "front_length_m": 15.0,
        "depth_m": 12.0,
        "is_haussmann_suspected": False,
        "has_cour": False,
        "facade_cour_m": None,
    }

    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "format": "jsonv2",
            "lat": str(lat),
            "lon": str(lon),
            "zoom": "18",
            "polygon_geojson": "0",
            "addressdetails": "1",
            "extratags": "1",
        }
        headers = {
            "User-Agent": "LibertFacadeEstimator/1.0 (contact@libertsas.fr)"
        }
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        data = resp.json()

        # Niveaux
        extratags = data.get("extratags", {}) or {}
        levels = extratags.get("building:levels")
        if levels:
            try:
                ctx["levels"] = max(1, min(int(levels), 15))
            except Exception:
                pass

        # Bounding box -> front_length / depth approximatifs
        bbox = data.get("boundingbox")
        if bbox and len(bbox) == 4:
            south, north, west, east = map(float, bbox)
            lat_mid = (south + north) / 2.0

            # Approximations mètres/° (suffisant pour un estimateur)
            lat_m = 111_132.0
            lon_m = 111_320.0 * max(
                0.1, abs(math.cos(lat_mid * math.pi / 180.0))
            )

            height_m = abs(north - south) * lat_m
            width_m = abs(east - west) * lon_m

            front = max(width_m, 5.0)
            depth = max(height_m, 5.0)

            # On suppose la façade la plus longue côté rue
            ctx["front_length_m"] = float(front)
            ctx["depth_m"] = float(depth)

        # Heuristique rapide Haussmann (juste pour info, pas vital au pricing)
        address = data.get("address", {}) or {}
        city = (address.get("city") or address.get("town") or "").lower()
        if "paris" in city and ctx["levels"] >= 5:
            ctx["is_haussmann_suspected"] = True

    except Exception:
        # On garde les valeurs par défaut
        pass

    return ctx


def build_streetview_embed_url(lat: float, lon: float, api_key: Optional[str]) -> str:
    """
    Construit l'URL d'embed Street View pour Google Maps Embed API.

    - On utilise la position (lat, lon) du géocodage Google.
    - On NE fixe PAS de heading : Google oriente la caméra vers le point
      le plus cohérent (meilleure chance de viser la façade).
    - fov élargi pour mieux voir le bâtiment.
    """
    if not api_key:
        return ""

    return (
        "https://www.google.com/maps/embed/v1/streetview"
        f"?key={api_key}"
        f"&location={lat:.6f},{lon:.6f}"
        "&fov=80"
    )
