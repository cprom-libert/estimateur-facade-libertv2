# apis.py
import requests
from typing import List, Dict, Optional


def get_address_suggestions(query: str, limit: int = 5) -> List[Dict]:
    """
    API Adresse (data.gouv) – suggestions + coordonnées.
    Retourne une liste de dicts {label, lat, lon}.
    """
    if len(query.strip()) < 3:
        return []

    url = "https://api-adresse.data.gouv.fr/search/"
    params = {"q": query, "limit": limit, "autocomplete": 1}
    resp = requests.get(url, params=params, timeout=5)
    resp.raise_for_status()
    data = resp.json()

    suggestions: List[Dict] = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates") or [None, None]
        lon, lat = coords[0], coords[1]
        if lat is None or lon is None:
            continue
        suggestions.append(
            {
                "label": props.get("label"),
                "lat": lat,
                "lon": lon,
            }
        )

    return suggestions


def fetch_osm_context(lat: float, lon: float, radius_m: int = 20) -> Dict:
    """
    Interroge Overpass pour récupérer le bâtiment proche, niveaux et présence de commerce.
    """
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
    roof_levels = None
    has_shop = False

    for el in data.get("elements", []):
        tags = el.get("tags", {})
        if not tags:
            continue

        lvl = tags.get("building:levels") or tags.get("levels")
        if lvl and levels is None:
            try:
                levels = int(lvl)
            except ValueError:
                pass

        rlvl = tags.get("roof:levels")
        if rlvl and roof_levels is None:
            try:
                roof_levels = int(rlvl)
            except ValueError:
                pass

        shop_tag = tags.get("shop") or tags.get("building:use")
        if shop_tag:
            has_shop = True

    return {
        "levels": levels,
        "roof_levels": roof_levels,
        "has_shop": has_shop,
    }


def build_streetview_embed_url(
    lat: float,
    lon: float,
    google_api_key: Optional[str],
    heading: Optional[float] = None,
    pitch: float = 10.0,
    fov: int = 90,
) -> str:
    """
    URL d'iframe Google Street View (API Embed).
    L’utilisateur peut se déplacer librement dans la vue.
    """
    if not google_api_key:
        # Image générique si pas de clé
        return (
            "https://upload.wikimedia.org/wikipedia/commons/9/9b/"
            "Rue_des_Écoles_-_Paris_V_%28FR75%29_-_2021-07-31_-_1.jpg"
        )

    base = "https://www.google.com/maps/embed/v1/streetview"
    params = f"key={google_api_key}&location={lat},{lon}&fov={fov}"
    if heading is not None:
        params += f"&heading={heading}"
    if pitch is not None:
        params += f"&pitch={pitch}"
    return f"{base}?{params}"
