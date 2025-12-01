from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class Geometry:
    hauteur: float          # hauteur totale de façade (m)
    surface_facades: float  # surface totale de façades traitées (m²)
    perimetre: float        # périmètre utile pour linéaires (m)
    nb_facades: int         # nombre de façades traitées


def build_pricing(
    geom: Geometry,
    support_key: str,
    options: Dict,
    etat_facade: str,
) -> Tuple[List[Dict,], float]:
    """
    Estimation détaillée poste par poste.
    - Tous les prix sont en TTC.
    - Le système de ravalement dépend du support et du choix client :
      * Façade enduite/béton : PEINTURE ou ENDUIT_SANS_PEINTURE
      * Façade pierre/brique : système chaux (sans peinture pliolite)
    """

    lignes: List[Dict] = []
    total_ttc: float = 0.0

    surface = max(geom.surface_facades, 0.0)
    perimetre = max(geom.perimetre, 0.0)
    niveaux = max(int(options.get("niveaux", 5)), 1)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def add_line(
        famille: str,
        designation: str,
        quantite: float,
        unite: str,
        pu_ttc: float,
        help_text: str,
    ) -> None:
        nonlocal total_ttc, lignes
        q = float(quantite or 0.0)
        if q <= 0 or pu_ttc <= 0:
            return
        mt = q * pu_ttc
        lignes.append(
            {
                "famille": famille,
                "designation": designation,
                "quantite": round(q, 2),
                "unite": unite,
                "pu_ttc": pu_ttc,
                "montant": mt,
                "help": help_text,
            }
        )
        total_ttc += mt

    def ratio_piochage(etat: str, support: str) -> float:
        etat = (etat or "moyen").lower()
        base = {
            "bon": 0.05,
            "moyen": 0.15,
            "degrade": 0.35,
            "dégradé": 0.35,
        }.get(etat, 0.15)

        support = (support or "").upper()
        # pierre / brique : un peu moins de piochage en proportion
        if "PIERRE" in support or "BRIQUE" in support:
            base *= 0.7
        return base

    # Type de façade et solution choisie
    support = (support_key or "").upper()
    is_pierre_brique = "PIERRE" in support or "BRIQUE" in support or "MOELLON" in support
    is_enduit_beton = "ENDUIT" in support or "BETON" in support or "BÉTON" in support

    solution = (options.get("solution_ravalement") or "PEINTURE").upper()
    # PEINTURE ou ENDUIT_SANS_PEINTURE

    # Ratio de surface concernée par piochage / reprises (par défaut)
    r_pioch = ratio_piochage(etat_facade, support_key)
    surf_pioch = surface * r_pioch

    # ------------------------------------------------------------------
    # INSTALLATION
    # ------------------------------------------------------------------
    add_line(
        "INSTALLATION",
        "Autorisations administratives (occupation du domaine public)",
        1,
        "forfait",
        700.0,
        "Demandes d'autorisations en mairie pour installer échafaudage et chantier sur rue.",
    )
    add_line(
        "INSTALLATION",
        "Cantonnement et installation de chantier",
        1,
        "forfait",
        650.0,
        "Mise en place de la base de vie du chantier : clôtures, signalisation, zone de stockage.",
    )

    # ------------------------------------------------------------------
    # PRÉPARATION (commune à tous les systèmes)
    # ------------------------------------------------------------------
    add_line(
        "PREPARATION",
        "Échafaudage de façade",
        surface,
        "m²",
        39.0,
        "Structure temporaire permettant de travailler en hauteur sur toute la façade en sécurité.",
    )

    add_line(
        "PREPARATION",
        "Nettoyage de façade haute pression",
        surface,
        "m²",
        14.0,
        "Nettoyage à l'eau sous pression pour enlever salissures, mousses et poussières avant travaux.",
    )

    # ------------------------------------------------------------------
    # RAVALEMENT : choix du système selon support + souhait client
    # ------------------------------------------------------------------
    # 1) Façade pierre / brique → système chaux, sans peinture pliolite
    if is_pierre_brique:
        if surf_pioch > 0:
            add_line(
                "PREPARATION",
                "Piochage des enduits dégradés et évacuation des gravats",
                surf_pioch,
                "m²",
                95.0,
                "Dépose manuelle des enduits qui sonnent creux ou se décollent, évacuation en décharge.",
            )
            add_line(
                "PREPARATION",
                "Pose d'armature (toile de renfort) sur zones fragilisées",
                surf_pioch,
                "m²",
                30.0,
                "Trame de renfort sur zones fissurées avant enduit à la chaux.",
            )
            add_line(
                "RAVALEMENT",
                "Enduit de façade à la chaux",
                surf_pioch,
                "m²",
                170.0,
                "Enduit traditionnel à la chaux pour reprendre les zones dégradées sur façades en pierre ou brique.",
            )
        # Pas de peinture pliolite ici.

    # 2) Façade enduit / béton
    elif is_enduit_beton:
        # a) Option peinture (classique)
        if solution == "PEINTURE":
            if surf_pioch > 0:
                add_line(
                    "PREPARATION",
                    "Piochage des enduits dégradés et évacuation des gravats",
                    surf_pioch,
                    "m²",
                    95.0,
                    "Dépose des zones d'enduit qui n'adhèrent plus avant reprise.",
                )
                add_line(
                    "PREPARATION",
                    "Pose d'armature (toile de renfort) sur zones fragilisées",
                    surf_pioch,
                    "m²",
                    30.0,
                    "Trame de renfort pour stabiliser les zones reprises.",
                )
                if r_pioch >= 0.2:
                    add_line(
                        "RAVALEMENT",
                        "Enduit monocouche de façade sur zones reprises",
                        surf_pioch,
                        "m²",
                        75.0,
                        "Enduit monocouche projeté sur les parties fortement dégradées avant peinture.",
                    )

            add_line(
                "PEINTURE",
                "Impression de façade (sous-couche fixante)",
                surface,
                "m²",
                19.0,
                "Sous-couche pour homogénéiser le support et améliorer l'adhérence de la peinture.",
            )
            add_line(
                "PEINTURE",
                "Peinture de façade pliolite (2 couches)",
                surface,
                "m²",
                46.0,
                "Peinture de façade résistante aux intempéries, appliquée en deux couches.",
            )

        # b) Option sans peinture : on repart sur un enduit complet
        elif solution == "ENDUIT_SANS_PEINTURE":
            # On considère un piochage quasi complet
            surf_pioch_full = surface
            add_line(
                "PREPARATION",
                "Piochage integral des enduits existants et évacuation des gravats",
                surf_pioch_full,
                "m²",
                95.0,
                "Dépose complète de l'ancien enduit pour repartir sur un support sain.",
            )
            add_line(
                "PREPARATION",
                "Pose d'armature (toile de renfort) sur l'ensemble de la façade",
                surf_pioch_full,
                "m²",
                30.0,
                "Trame de renfort sur l'ensemble de la façade avant enduit.",
            )
            add_line(
                "RAVALEMENT",
                "Enduit monocouche de façade (teinté, sans peinture)",
                surface,
                "m²",
                75.0,
                "Enduit monocouche projeté sur toute la façade, teinté dans la masse, sans peinture de finition.",
            )

    # 3) Autres cas → traitement peinture standard
    else:
        if surf_pioch > 0 and r_pioch >= 0.25:
            add_line(
                "PREPARATION",
                "Piochage des zones dégradées et évacuation des gravats",
                surf_pioch,
                "m²",
                95.0,
                "Dépose des zones d'enduit ou de peinture qui n'adhèrent plus avant reprise.",
            )
            add_line(
                "PREPARATION",
                "Pose d'armature (toile de renfort) sur zones reprises",
                surf_pioch,
                "m²",
                30.0,
                "Trame de renfort pour stabiliser les zones reprises.",
            )
        add_line(
            "PEINTURE",
            "Impression de façade (sous-couche fixante)",
            surface,
            "m²",
            19.0,
            "Sous-couche pour homogénéiser le support et améliorer l'adhérence de la peinture.",
        )
        add_line(
            "PEINTURE",
            "Peinture de façade pliolite (2 couches)",
            surface,
            "m²",
            46.0,
            "Peinture de façade résistante aux intempéries, appliquée en deux couches.",
        )

    # ------------------------------------------------------------------
    # OUVERTURES / MENUISERIES / GARDE-CORPS
    # ------------------------------------------------------------------
    # Seules les grandes fenêtres sont prises en compte
    nb_fenetres_grandes = int(options.get("nb_fenetres_grandes", 0))
    # surface boiseries approximative : 1,5 m² par grande fenêtre
    surf_boiseries = nb_fenetres_grandes * 1.5

    if surf_boiseries > 0:
        add_line(
            "FINITIONS",
            "Protection des menuiseries (films et rubans adhésifs)",
            surf_boiseries,
            "m²",
            4.0,
            "Protection des fenêtres et portes par adhésif ou film plastique avant travaux.",
        )
        add_line(
            "PEINTURE",
            "Peinture des boiseries (volets, encadrements)",
            surf_boiseries,
            "m²",
            38.0,
            "Préparation et peinture des éléments en bois visibles en façade.",
        )

    ml_gc = float(options.get("ml_garde_corps_fer_forge", 0.0) or 0.0)
    add_line(
        "PEINTURE",
        "Peinture des garde-corps métalliques",
        ml_gc,
        "ml",
        42.0,
        "Décapage léger, antirouille et peinture des garde-corps en métal.",
    )

    ml_ferr = ml_gc * 0.3
    add_line(
        "PEINTURE",
        "Rénovation de ferronneries anciennes complexes",
        ml_ferr,
        "ml",
        66.0,
        "Traitement anticorrosion et peinture des éléments en ferronnerie décorative ancienne.",
    )

    # ------------------------------------------------------------------
    # ZINGUERIE
    # ------------------------------------------------------------------
    ml_couvertine = float(options.get("ml_couvertine", 0.0) or 0.0)
    add_line(
        "ZINGUERIE",
        "Fourniture et pose de couvertines",
        ml_couvertine,
        "ml",
        150.0,
        "Profilés zinc ou alu protégeant le dessus des murs et acrotères contre les infiltrations.",
    )

    ml_bandeaux = float(options.get("ml_bandeaux", 0.0) or 0.0)
    add_line(
        "ZINGUERIE",
        "Habillage zinc des bandeaux et corniches",
        ml_bandeaux,
        "ml",
        178.0,
        "Habillage des bandeaux / corniches en zinc pour les protéger durablement.",
    )

    ml_descente = float(options.get("ml_descente_ep", 0.0) or 0.0)
    add_line(
        "ZINGUERIE",
        "Remplacement / reprise des descentes d'eaux pluviales",
        ml_descente,
        "ml",
        165.0,
        "Reprise des tuyaux d'évacuation d'eau de pluie le long de la façade.",
    )

    # ------------------------------------------------------------------
    # CHIENS-ASSIS & NETTOYAGE
    # ------------------------------------------------------------------
    if options.get("traiter_chiens_assis"):
        nb_chiens = int(options.get("nb_chiens_assis", 0))
        add_line(
            "FINITIONS",
            "Rénovation de chiens-assis (lucarnes en toiture)",
            nb_chiens,
            "u",
            280.0,
            "Rénovation des petites lucarnes en toiture (bardage, peinture et étanchéité périphérique).",
        )

        surface_par_etage = surface / float(niveaux)
        add_line(
            "PREPARATION",
            "Complément d'échafaudage pour accès chiens-assis",
            surface_par_etage,
            "m²",
            39.0,
            "Surépaisseur d'échafaudage nécessaire pour accéder aux chiens-assis.",
        )

    add_line(
        "FINITIONS",
        "Nettoyage complet de fin de chantier",
        1,
        "forfait",
        350.0,
        "Remise en état des abords : retrait des protections, gravats et nettoyage du trottoir.",
    )

    return lignes, total_ttc
