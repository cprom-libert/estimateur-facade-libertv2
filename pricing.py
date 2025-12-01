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
    Construit l'estimation détaillée poste par poste.
    Retourne (lignes, total_ttc).

    - Tous les prix sont en TTC.
    - On reste dans la moyenne du marché parisien.
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
        # pierre / brique : on piochage souvent moins
        if "PIERRE" in support or "BRIQUE" in support:
            base *= 0.5
        return base

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
    # PRÉPARATION
    # ------------------------------------------------------------------
    # Échafaudage sur toute la surface traitée
    add_line(
        "PREPARATION",
        "Échafaudage de façade",
        surface,
        "m²",
        39.0,
        "Structure temporaire permettant de travailler en hauteur sur toute la façade en sécurité.",
    )

    # Nettoyage haute pression
    add_line(
        "PREPARATION",
        "Nettoyage de façade haute pression",
        surface,
        "m²",
        14.0,
        "Nettoyage à l'eau sous pression pour enlever salissures, mousses et poussières avant travaux.",
    )

    # Piochage + armature sur une partie de la surface
    r_pioch = ratio_piochage(etat_facade, support_key)
    surf_pioch = surface * r_pioch

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
        "Pose d'une trame de renfort pour stabiliser les supports fissurés avant enduit.",
    )

    # ------------------------------------------------------------------
    # RAVALEMENT (ENDUITS)
    # ------------------------------------------------------------------
    support = (support_key or "").upper()
    if surf_pioch > 0:
        if "PIERRE" in support or "MOELLON" in support or "CHAUX" in support:
            add_line(
                "RAVALEMENT",
                "Enduit de façade à la chaux",
                surf_pioch,
                "m²",
                170.0,
                "Enduit traditionnel à la chaux adapté aux façades anciennes (pierre, moellons).",
            )
        else:
            add_line(
                "RAVALEMENT",
                "Enduit monocouche de façade",
                surf_pioch,
                "m²",
                75.0,
                "Enduit monocouche projeté servant à la fois de protection et de finition décorative.",
            )

    # ------------------------------------------------------------------
    # PEINTURE FAÇADE
    # ------------------------------------------------------------------
    # Impression + peinture pliolite sur toute la surface
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
        # Protection menuiseries
        add_line(
            "FINITIONS",
            "Protection des menuiseries (films et rubans adhésifs)",
            surf_boiseries,
            "m²",
            4.0,
            "Protection des fenêtres et portes par adhésif ou film plastique avant peinture.",
        )
        # Peinture boiseries
        add_line(
            "PEINTURE",
            "Peinture des boiseries (volets, encadrements)",
            surf_boiseries,
            "m²",
            38.0,
            "Préparation et peinture des éléments en bois visibles en façade.",
        )

    # Garde-corps
    ml_gc = float(options.get("ml_garde_corps_fer_forge", 0.0) or 0.0)
    add_line(
        "PEINTURE",
        "Peinture des garde-corps métalliques",
        ml_gc,
        "ml",
        42.0,
        "Décapage léger, antirouille et peinture des garde-corps en métal.",
    )

    # Ferronnerie ancienne : on considère qu'environ 30 % des garde-corps sont plus complexes
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
    # ZINGUERIE (optionnelle pour l'instant, valeurs souvent à 0)
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

        # Complément d'échafaudage équivalent à un étage pour accéder aux chiens-assis
        surface_par_etage = surface / float(niveaux)
        add_line(
            "PREPARATION",
            "Complément d'échafaudage pour accès chiens-assis",
            surface_par_etage,
            "m²",
            39.0,
            "Surépaisseur d'échafaudage nécessaire pour accéder aux chiens-assis.",
        )

    # Nettoyage fin de chantier
    add_line(
        "FINITIONS",
        "Nettoyage complet de fin de chantier",
        1,
        "forfait",
        350.0,
        "Remise en état des abords : retrait des protections, gravats et nettoyage du trottoir.",
    )

    return lignes, total_ttc
