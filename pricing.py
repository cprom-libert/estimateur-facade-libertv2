# pricing.py
from dataclasses import dataclass
from typing import List, Dict, Tuple


# Prix moyens pour Paris (positionnement pro / haut de gamme)
DB_PRIX = {
    "LOGISTIQUE": {
        "BASE_VIE": {
            "label": "Base vie de chantier",
            "unit": "forfait",
            "pu": 3500.0,
        },
        "AUTORISATION": {
            "label": "Droits de voirie / autorisations",
            "unit": "forfait",
            "pu": 1800.0,
        },
        "ECHAFAUDAGE": {
            "label": "Échafaudage de façade",
            "unit": "m²",
            "pu": 65.0,  # €/m² de façade développée
        },
    },
    "FACADES": {
        "PLATRE_ANCIEN": {
            "label": "Façade plâtre ancien",
            "net": 22.0,               # €/m²
            "fin": 60.0,               # €/m²
            "ratio_reparation": 0.35,  # 35 % de surface réparée (état MOYEN)
            "pu_reparation": 200.0,    # €/m² réparé
        },
        "PIERRE_TAILLE": {
            "label": "Façade pierre de taille",
            "net": 28.0,
            "fin": 80.0,
            "ratio_reparation": 0.15,
            "pu_reparation": 250.0,
        },
        "BRIQUE": {
            "label": "Façade briques",
            "net": 20.0,
            "fin": 50.0,
            "ratio_reparation": 0.22,
            "pu_reparation": 190.0,
        },
        "BETON": {
            "label": "Façade béton",
            "net": 18.0,
            "fin": 50.0,
            "ratio_reparation": 0.25,
            "pu_reparation": 210.0,
        },
        "PAVILLON_ENDUIT": {
            "label": "Façade pavillon enduit",
            "net": 18.0,
            "fin": 45.0,
            "ratio_reparation": 0.20,
            "pu_reparation": 170.0,
        },
    },
    "ZINGUERIE": {
        "BANDEAU": {
            "label": "Habillage de bandeaux en zinc",
            "unit": "ml",
            "pu": 150.0,
        },
        "DESCENTE": {
            "label": "Réfection descente EP",
            "unit": "u",
            "pu": 260.0,
        },
        "GARDES_CORPS": {
            "label": "Révision garde-corps métalliques",
            "unit": "ml",
            "pu": 110.0,
        },
        "APPUIS_PIERRE": {
            "label": "Réfection appuis de fenêtres",
            "unit": "ml",
            "pu": 95.0,
        },
    },
    "TOITURES": {
        "DEBORD_TOIT": {
            "label": "Traitement débords de toit / avancées",
            "unit": "ml",
            "pu": 120.0,
        },
        "ACROTERES": {
            "label": "Réfection acrotères",
            "unit": "ml",
            "pu": 140.0,
        },
    },
    "BOISERIES": {
        "PORTE_ENTREE": {
            "label": "Porte d’entrée bois",
            "unit": "u",
            "pu": 1800.0,
        },
        "PORTE_COCHERE": {
            "label": "Porte cochère bois",
            "unit": "u",
            "pu": 5500.0,
        },
    },
    "COMMERCE": {
        "RDC_RETAIL": {
            "label": "Zone commerciale en RDC (vitrines, enseignes)",
            "unit": "forfait",
            "pu": 3500.0,
        }
    },
}

# Hauteur moyenne par niveau
NIVEAU_HAUTEUR = 3.0  # m / niveau


@dataclass
class Geometry:
    hauteur: float
    surface_facades: float
    perimetre: float
    nb_facades: int


def est_pavillon(building_type: str) -> bool:
    return building_type.upper().startswith("PAVILLON")


def estimate_geometry(building_type: str, niveaux: int, largeur_facade: float) -> Geometry:
    """
    building_type : "IMMEUBLE" ou "PAVILLON"
    niveaux       : nombre de niveaux principaux
    largeur_facade: largeur principale sur rue (m)
    """
    hauteur = max(1, niveaux) * NIVEAU_HAUTEUR

    if est_pavillon(building_type):
        nb_facades = 4
    else:
        nb_facades = 1

    perimetre = largeur_facade * nb_facades
    surface_facades = hauteur * perimetre

    return Geometry(
        hauteur=hauteur,
        surface_facades=surface_facades,
        perimetre=perimetre,
        nb_facades=nb_facades,
    )


def _adjust_ratio_for_state(base_ratio: float, facade_state: str) -> float:
    """
    Ajuste le ratio de réparations selon l’état de la façade.
    facade_state : "BON" / "MOYEN" / "DEGRADE"
    """
    state = facade_state.upper()
    if state == "BON":
        coeff = 0.6   # 60 % du ratio de base
    elif state == "DEGRADE":
        coeff = 1.4   # 140 % du ratio de base
    else:  # MOYEN
        coeff = 1.0

    return base_ratio * coeff


def build_pricing(
    geom: Geometry,
    support_key: str,
    options: Dict,
    facade_state: str,
) -> Tuple[List[Dict], float]:
    """
    options attend par exemple :
    {
        "porte_entree": bool,
        "porte_cochere": bool,
        "has_commerce_rdc": bool,
        "has_bandeaux": bool,
        "has_appuis": bool,
        "has_toiture_debord": bool,
        "has_acroteres": bool,
        "nb_descente_ep": int,
    }
    facade_state : "BON" / "MOYEN" / "DEGRADE"
    """
    lignes: List[Dict] = []
    total = 0.0

    # Fonction interne pour ajouter une ligne
    def add_line(section: str, label: str, qty: float, unit: str, pu: float):
        nonlocal total
        mt = qty * pu
        lignes.append(
            {
                "section": section,
                "designation": label,
                "quantite": round(qty, 2),
                "unite": unit,
                "pu": pu,
                "montant": round(mt, 2),
            }
        )
        total += mt

    # 1. LOGISTIQUE
    base_vie = DB_PRIX["LOGISTIQUE"]["BASE_VIE"]
    autorisation = DB_PRIX["LOGISTIQUE"]["AUTORISATION"]
    echafaudage = DB_PRIX["LOGISTIQUE"]["ECHAFAUDAGE"]

    add_line("LOGISTIQUE", base_vie["label"], 1, base_vie["unit"], base_vie["pu"])
    add_line("LOGISTIQUE", autorisation["label"], 1, autorisation["unit"], autorisation["pu"])
    add_line(
        "LOGISTIQUE",
        echafaudage["label"],
        geom.surface_facades,
        echafaudage["unit"],
        echafaudage["pu"],
    )

    # 2. FAÇADES (nettoyage / réparations / finition)
    facade_prof = DB_PRIX["FACADES"][support_key]
    surface = geom.surface_facades

    base_ratio = facade_prof["ratio_reparation"]
    ratio = _adjust_ratio_for_state(base_ratio, facade_state)
    pu_reparation = facade_prof["pu_reparation"]

    # Nettoyage
    add_line(
        "FAÇADES",
        f"{facade_prof['label']} – Nettoyage",
        surface,
        "m²",
        facade_prof["net"],
    )

    # Réparations (piochage + reconstitution)
    add_line(
        "FAÇADES",
        f"{facade_prof['label']} – Réparations ponctuelles",
        surface * ratio,
        "m²",
        pu_reparation,
    )

    # Finition
    add_line(
        "FAÇADES",
        f"{facade_prof['label']} – Finition peinture",
        surface,
        "m²",
        facade_prof["fin"],
    )

    # 3. BOISERIES / PORTES
    if options.get("porte_entree"):
        porte = DB_PRIX["BOISERIES"]["PORTE_ENTREE"]
        add_line("BOISERIES", porte["label"], 1, porte["unit"], porte["pu"])

    if options.get("porte_cochere"):
        porte = DB_PRIX["BOISERIES"]["PORTE_COCHERE"]
        add_line("BOISERIES", porte["label"], 1, porte["unit"], porte["pu"])

    # 4. COMMERCE RDC
    if options.get("has_commerce_rdc"):
        retail = DB_PRIX["COMMERCE"]["RDC_RETAIL"]
        add_line("COMMERCE", retail["label"], 1, retail["unit"], retail["pu"])

    # 5. ZINGUERIE
    perimetre = geom.perimetre
    z = DB_PRIX["ZINGUERIE"]

    if options.get("has_bandeaux"):
        add_line("ZINGUERIE", z["BANDEAU"]["label"], perimetre, z["BANDEAU"]["unit"], z["BANDEAU"]["pu"])

    if options.get("has_appuis"):
        add_line("ZINGUERIE", z["APPUIS_PIERRE"]["label"], perimetre, z["APPUIS_PIERRE"]["unit"], z["APPUIS_PIERRE"]["pu"])

    nb_desc = int(options.get("nb_descente_ep") or 0)
    if nb_desc > 0:
        add_line("ZINGUERIE", z["DESCENTE"]["label"], nb_desc, z["DESCENTE"]["unit"], z["DESCENTE"]["pu"])

    # 6. TOITURES
    t = DB_PRIX["TOITURES"]
    if options.get("has_toiture_debord"):
        add_line("TOITURES", t["DEBORD_TOIT"]["label"], perimetre, t["DEBORD_TOIT"]["unit"], t["DEBORD_TOIT"]["pu"])

    if options.get("has_acroteres"):
        add_line("TOITURES", t["ACROTERES"]["label"], perimetre, t["ACROTERES"]["unit"], t["ACROTERES"]["pu"])

    return lignes, round(total, 2)
