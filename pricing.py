# pricing.py
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class Geometry:
    hauteur: float
    surface_facades: float
    perimetre: float
    nb_facades: int


BASE_FINISH_PRICES: Dict[str, float] = {
    "D3": 80.0,
    "SILOXANE": 90.0,
    "MINERAL": 105.0,
}

ETAT_COEFFS: Dict[str, float] = {
    "bon": 0.95,
    "moyen": 1.00,
    "degrade": 1.15,
}

PARIS_COEFF = 1.20
HAUSSMANN_COEFF = 1.20

PRIX_ECHAFAUD_M2 = 40.0

PRIX_POINTS: Dict[str, float] = {
    "fenetre_petite": 55.0,
    "fenetre_grande": 85.0,
    "garde_corps_simple_ml": 50.0,
    "garde_corps_fer_forge_ml": 70.0,
    "garde_corps_balcon_ml": 95.0,
    "descente_ep_ml": 35.0,
    "bandeau_ml": 45.0,
    "zinguerie_ml": 75.0,
    "grille_aeration_u": 15.0,
    "grillage_protection_ml": 25.0,
    "grillage_galva_ml": 70.0,
    "microfissure_ml": 10.0,
    "fissure_ouverte_ml": 20.0,
    "reprise_enduit_m2": 25.0,
    "reprise_lourde_m2": 45.0,
    "chien_assis_u": 320.0,
}


def infer_finition_from_support(support_key: str, etat_facade: str) -> str:
    s = (support_key or "").upper()
    etat_norm = (etat_facade or "moyen").lower()

    supports_enduit = {
        "ENDUIT_CIMENT",
        "ENDUIT_PLATRE",
        "BETON_PEINT",
        "MONOCOUCHE",
        "CREPI",
        "ENDUIT_MORTIER",
    }
    supports_mineral = {
        "PIERRE_TAILLE",
        "PIERRE_APPARENTE",
        "BRIQUE_PLEINE",
        "BRIQUE_APPARENTE",
    }

    if s in supports_enduit:
        if etat_norm == "degrade":
            return "SILOXANE"
        return "D3"

    if s in supports_mineral:
        if etat_norm == "degrade":
            return "MINERAL"
        return "SILOXANE"

    return "D3"


def compute_m2_price(
    support_key: str,
    etat_facade: str,
    is_haussmann: bool,
) -> Tuple[str, float]:
    finition = infer_finition_from_support(support_key, etat_facade)
    base = BASE_FINISH_PRICES.get(finition, BASE_FINISH_PRICES["D3"])

    etat_norm = (etat_facade or "moyen").lower()
    if etat_norm not in ETAT_COEFFS:
        etat_norm = "moyen"
    coef_etat = ETAT_COEFFS[etat_norm]

    coef_paris = PARIS_COEFF
    coef_hauss = HAUSSMANN_COEFF if is_haussmann else 1.0

    prix_m2 = base * coef_etat * coef_paris * coef_hauss
    return finition, prix_m2


def build_pricing(
    geom: Geometry,
    support_key: str,
    options: Dict,
    etat_facade: str,
) -> Tuple[List[Dict], float]:
    """
    Renvoie (lignes, total_ht).
    Chaque ligne contient :
      code, designation, quantite, unite, pu, montant, famille
    Familles utilisées :
      INSTALLATION, PROTECTION, ECHAUFAUDAGE, RAVALEMENT,
      ZINGUERIE, PEINTURE, NETTOYAGE
    """
    lignes: List[Dict] = []
    total = 0.0

    is_haussmann = bool(options.get("is_haussmann", False))
    traiter_chiens_assis = bool(options.get("traiter_chiens_assis", False))
    nb_chiens_assis = int(options.get("nb_chiens_assis", 0) or 0)
    niveaux = int(options.get("niveaux", 1) or 1)
    if niveaux < 1:
        niveaux = 1

    finition, prix_m2 = compute_m2_price(
        support_key=support_key,
        etat_facade=etat_facade,
        is_haussmann=is_haussmann,
    )

    # 1) Ravalement (support + peinture)
    montant_raval = geom.surface_facades * prix_m2
    lignes.append(
        {
            "code": "RAVAL",
            "designation": f"Travaux de ravalement (préparation + revêtement {finition})",
            "quantite": round(geom.surface_facades, 1),
            "unite": "m2",
            "pu": round(prix_m2, 2),
            "montant": round(montant_raval, 2),
            "famille": "RAVALEMENT",
        }
    )
    total += montant_raval

    # 2) Échafaudage (avec étage supplémentaire si chiens-assis)
    surface_base_echaf = geom.surface_facades
    if traiter_chiens_assis and nb_chiens_assis > 0:
        surface_extra = surface_base_echaf / niveaux
    else:
        surface_extra = 0.0

    surface_totale_echaf = surface_base_echaf + surface_extra
    montant_echaf = surface_totale_echaf * PRIX_ECHAFAUD_M2

    designation_echaf = "Échafaudage de façade"
    if surface_extra > 0:
        designation_echaf += " (avec un étage supplémentaire pour chiens-assis)"

    lignes.append(
        {
            "code": "ECHAF",
            "designation": designation_echaf,
            "quantite": round(surface_totale_echaf, 1),
            "unite": "m2",
            "pu": round(PRIX_ECHAFAUD_M2, 2),
            "montant": round(montant_echaf, 2),
            "famille": "ECHAUFAUDAGE",
        }
    )
    total += montant_echaf

    # 3) Maçonneries / fissures (tout en RAVALEMENT)
    surface_reprise_lourde = float(options.get("surface_reprises_lourdes_detectee", 0.0) or 0.0)
    surface_min = 0.08 * geom.surface_facades
    surface_reprise_lourde = max(surface_reprise_lourde, surface_min)

    if surface_reprise_lourde > 0:
        pu = PRIX_POINTS["reprise_lourde_m2"]
        m = surface_reprise_lourde * pu
        lignes.append(
            {
                "code": "MAC_RL",
                "designation": "Reprises lourdes d’enduit (piquage + réenduit)",
                "quantite": round(surface_reprise_lourde, 1),
                "unite": "m2",
                "pu": round(pu, 2),
                "montant": round(m, 2),
                "famille": "RAVALEMENT",
            }
        )
        total += m

    surface_reprise_enduit = float(options.get("surface_reprises_enduit_detectee", 0.0) or 0.0)
    if surface_reprise_enduit > 0:
        pu = PRIX_POINTS["reprise_enduit_m2"]
        m = surface_reprise_enduit * pu
        lignes.append(
            {
                "code": "MAC_RE",
                "designation": "Reprises ponctuelles d’enduit",
                "quantite": round(surface_reprise_enduit, 1),
                "unite": "m2",
                "pu": round(pu, 2),
                "montant": round(m, 2),
                "famille": "RAVALEMENT",
            }
        )
        total += m

    ml_micro = float(options.get("ml_microfissures", 0.0) or 0.0)
    if ml_micro > 0:
        pu = PRIX_POINTS["microfissure_ml"]
        m = ml_micro * pu
        lignes.append(
            {
                "code": "MAC_MICRO",
                "designation": "Traitement des microfissures (≤ 2 mm)",
                "quantite": round(ml_micro, 1),
                "unite": "ml",
                "pu": round(pu, 2),
                "montant": round(m, 2),
                "famille": "RAVALEMENT",
            }
        )
        total += m

    ml_fiss = float(options.get("ml_fissures_ouvertes", 0.0) or 0.0)
    if ml_fiss > 0:
        pu = PRIX_POINTS["fissure_ouverte_ml"]
        m = ml_fiss * pu
        lignes.append(
            {
                "code": "MAC_FISS",
                "designation": "Traitement des fissures ouvertes (> 2 mm)",
                "quantite": round(ml_fiss, 1),
                "unite": "ml",
                "pu": round(pu, 2),
                "montant": round(m, 2),
                "famille": "RAVALEMENT",
            }
        )
        total += m

    # 4) Fenêtres / peinture menuiseries
    nb_fen_p = int(options.get("nb_fenetres_petites", 0) or 0)
    if nb_fen_p > 0:
        pu = PRIX_POINTS["fenetre_petite"]
        m = nb_fen_p * pu
        lignes.append(
            {
                "code": "FEN_P",
                "designation": "Fenêtres petites (préparation + peinture)",
                "quantite": nb_fen_p,
                "unite": "u",
                "pu": round(pu, 2),
                "montant": round(m, 2),
                "famille": "PEINTURE",
            }
        )
        total += m

    nb_fen_g = int(options.get("nb_fenetres_grandes", 0) or 0)
    if nb_fen_g > 0:
        pu = PRIX_POINTS["fenetre_grande"]
        m = nb_fen_g * pu
        lignes.append(
            {
                "code": "FEN_G",
                "designation": "Fenêtres grandes / portes-fenêtres (préparation + peinture)",
                "quantite": nb_fen_g,
                "unite": "u",
                "pu": round(pu, 2),
                "montant": round(m, 2),
                "famille": "PEINTURE",
            }
        )
        total += m

    # 5) Garde-corps / zinguerie
    ml_gc_fer = float(options.get("ml_garde_corps_fer_forge", 0.0) or 0.0)
    if ml_gc_fer > 0:
        pu = PRIX_POINTS["garde_corps_fer_forge_ml"]
        m = ml_gc_fer * pu
        lignes.append(
            {
                "code": "GC_FER",
                "designation": "Garde-corps fer forgé",
                "quantite": round(ml_gc_fer, 1),
                "unite": "ml",
                "pu": round(pu, 2),
                "montant": round(m, 2),
                "famille": "ZINGUERIE",
            }
        )
        total += m

    ml_gc_balcon = float(options.get("ml_garde_corps_balcon", 0.0) or 0.0)
    if ml_gc_balcon > 0:
        pu = PRIX_POINTS["garde_corps_balcon_ml"]
        m = ml_gc_balcon * pu
        lignes.append(
            {
                "code": "GC_BALC",
                "designation": "Balcons avec garde-corps",
                "quantite": round(ml_gc_balcon, 1),
                "unite": "ml",
                "pu": round(pu, 2),
                "montant": round(m, 2),
                "famille": "ZINGUERIE",
            }
        )
        total += m

    ml_dep = float(options.get("ml_descente_ep", 0.0) or 0.0)
    if ml_dep > 0:
        pu = PRIX_POINTS["descente_ep_ml"]
        m = ml_dep * pu
        lignes.append(
            {
                "code": "DEP",
                "designation": "Descentes d’eaux pluviales",
                "quantite": round(ml_dep, 1),
                "unite": "ml",
                "pu": round(pu, 2),
                "montant": round(m, 2),
                "famille": "ZINGUERIE",
            }
        )
        total += m

    ml_bandeaux = float(options.get("ml_bandeaux", 0.0) or 0.0)
    if ml_bandeaux > 0:
        pu = PRIX_POINTS["bandeau_ml"]
        m = ml_bandeaux * pu
        lignes.append(
            {
                "code": "BAND",
                "designation": "Bandeaux / corniches",
                "quantite": round(ml_bandeaux, 1),
                "unite": "ml",
                "pu": round(pu, 2),
                "montant": round(m, 2),
                "famille": "ZINGUERIE",
            }
        )
        total += m

    ml_zing = float(options.get("ml_zinguerie", 0.0) or 0.0)
    if ml_zing > 0:
        pu = PRIX_POINTS["zinguerie_ml"]
        m = ml_zing * pu
        lignes.append(
            {
                "code": "ZINC",
                "designation": "Éléments de zinguerie (tablettes, couvertines…)",
                "quantite": round(ml_zing, 1),
                "unite": "ml",
                "pu": round(pu, 2),
                "montant": round(m, 2),
                "famille": "ZINGUERIE",
            }
        )
        total += m

    nb_grilles = int(options.get("nb_grilles_aeration", 0) or 0)
    if nb_grilles > 0:
        pu = PRIX_POINTS["grille_aeration_u"]
        m = nb_grilles * pu
        lignes.append(
            {
                "code": "GRIL",
                "designation": "Grilles d’aération / ventilation",
                "quantite": nb_grilles,
                "unite": "u",
                "pu": round(pu, 2),
                "montant": round(m, 2),
                "famille": "RAVALEMENT",
            }
        )
        total += m

    ml_grillage_prot = float(options.get("ml_grillage_protection", 0.0) or 0.0)
    if ml_grillage_prot > 0:
        pu = PRIX_POINTS["grillage_protection_ml"]
        m = ml_grillage_prot * pu
        lignes.append(
            {
                "code": "GRILL_PROT",
                "designation": "Grillage de protection (pied d’immeuble)",
                "quantite": round(ml_grillage_prot, 1),
                "unite": "ml",
                "pu": round(pu, 2),
                "montant": round(m, 2),
                "famille": "INSTALLATION",
            }
        )
        total += m

    ml_grillage_galva = float(options.get("ml_grillage_galva", 0.0) or 0.0)
    if ml_grillage_galva > 0:
        pu = PRIX_POINTS["grillage_galva_ml"]
        m = ml_grillage_galva * pu
        lignes.append(
            {
                "code": "GRILL_GALV",
                "designation": "Garde-corps grillagés galvanisés",
                "quantite": round(ml_grillage_galva, 1),
                "unite": "ml",
                "pu": round(pu, 2),
                "montant": round(m, 2),
                "famille": "ZINGUERIE",
            }
        )
        total += m

    # 6) Chiens-assis (peinture et reprises locales)
    if traiter_chiens_assis and nb_chiens_assis > 0:
        pu = PRIX_POINTS["chien_assis_u"]
        m = nb_chiens_assis * pu
        lignes.append(
            {
                "code": "CHIENS_ASSIS",
                "designation": "Chiens-assis / lucarnes (préparation + peinture)",
                "quantite": nb_chiens_assis,
                "unite": "u",
                "pu": round(pu, 2),
                "montant": round(m, 2),
                "famille": "PEINTURE",
            }
        )
        total += m

    # 7) Nettoyage forfaitaire
    montant_nettoyage = total * 0.01
    lignes.append(
        {
            "code": "NETTOYAGE",
            "designation": "Nettoyage final et repli de chantier",
            "quantite": 1,
            "unite": "forfait",
            "pu": round(montant_nettoyage, 2),
            "montant": round(montant_nettoyage, 2),
            "famille": "NETTOYAGE",
        }
    )
    total += montant_nettoyage

    return lignes, round(total, 2)
