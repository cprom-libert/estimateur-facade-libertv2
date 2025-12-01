# ui.py
import streamlit as st
from typing import Dict, Any, List
from apis import get_address_suggestions, build_streetview_embed_url

LIBERT_PRIMARY = "#0B2239"
LIBERT_ACCENT = "#E3B35A"


def init_css() -> None:
    st.markdown(
        f"""
        <style>
        .lc-card {{
            background-color: #ffffff;
            border-radius: 18px;
            padding: 18px 20px;
            box-shadow: 0 8px 20px rgba(0,0,0,0.06);
            margin-bottom: 18px;
        }}
        .lc-title {{
            font-size: 1.3rem;
            font-weight: 600;
            color: {LIBERT_PRIMARY};
            margin-bottom: 0.4rem;
        }}
        .lc-subtitle {{
            font-size: 0.95rem;
            color: #555;
            margin-bottom: 1rem;
        }}
        .stButton>button {{
            border-radius: 999px;
            padding: 0.5rem 1.4rem;
            font-weight: 600;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_address_step() -> bool:
    st.markdown('<div class="lc-card">', unsafe_allow_html=True)
    st.markdown('<div class="lc-title">1. Adresse du bâtiment</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='lc-subtitle'>Saisissez l’adresse du bâtiment. Nous pré-remplissons les informations techniques.</div>",
        unsafe_allow_html=True,
    )

    query = st.text_input("Adresse (rue, code postal, ville)", value=st.session_state.get("addr_query", ""))
    st.session_state.addr_query = query

    suggestions = []
    chosen = None
    if query and len(query) >= 3:
        suggestions = get_address_suggestions(query)

    labels = [s["label"] for s in suggestions]
    if labels:
        idx = st.selectbox(
            "Résultats trouvés",
            options=list(range(len(labels))),
            format_func=lambda i: labels[i],
        )
        chosen = suggestions[idx]

    ok = False
    if chosen:
        if st.button("Valider cette adresse", type="primary"):
            st.session_state.addr_label = chosen["label"]
            st.session_state.coords = {"lat": chosen["lat"], "lon": chosen["lon"]}
            ok = True

    st.markdown("</div>", unsafe_allow_html=True)
    return ok


def render_map_and_form(google_api_key: str | None, content_func, *args, **kwargs):
    """
    Affiche la carte / Street View à gauche (ou au-dessus sur mobile),
    et le contenu du formulaire à droite.
    """
    coords = st.session_state.get("coords")
    if not coords:
        st.warning("Veuillez d’abord sélectionner une adresse.")
        return None

    addr_label = st.session_state.get("addr_label", "")
    lat, lon = coords["lat"], coords["lon"]
    iframe = build_streetview_embed_url(lat, lon, google_api_key)

    col_map, col_form = st.columns([1, 1.3])

    with col_map:
        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        st.markdown(f"<b>Adresse sélectionnée :</b><br>{addr_label}", unsafe_allow_html=True)
        st.markdown(
            f'<iframe src="{iframe}" width="100%" height="320" style="border:0;border-radius:14px;" allowfullscreen loading="lazy"></iframe>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_form:
        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        out = content_func(*args, **kwargs)
        st.markdown("</div>", unsafe_allow_html=True)

    return out


def render_building_dimensions_form(osm_ctx: Dict) -> Dict:
    st.markdown('<div class="lc-title">2. Dimensions principales</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='lc-subtitle'>Ces éléments servent à estimer la surface de façades et l’échafaudage.</div>",
        unsafe_allow_html=True,
    )

    building_type_default = osm_ctx.get("building_type", "IMMEUBLE")
    building_type = st.selectbox(
        "Type de bâtiment",
        options=["IMMEUBLE", "PAVILLON"],
        index=0 if building_type_default == "IMMEUBLE" else 1,
    )

    levels_osm = osm_ctx.get("levels_osm")
    niveaux_default = int(levels_osm) if levels_osm else 5
    niveaux = st.number_input(
        "Nombre de niveaux (R+...)", min_value=1, max_value=12, value=niveaux_default, step=1
    )

    hauteur_par_niveau = st.number_input(
        "Hauteur moyenne par niveau (m)",
        min_value=2.5,
        max_value=4.0,
        value=3.0 if building_type == "IMMEUBLE" else 2.8,
        step=0.1,
    )

    largeur_rue_default = osm_ctx.get("facade_rue_m") or 15.0
    largeur = st.number_input(
        "Largeur de la façade principale (m)",
        min_value=3.0,
        max_value=80.0,
        value=float(round(largeur_rue_default, 1)),
        step=0.5,
    )

    profondeur_default = osm_ctx.get("depth_m") or largeur
    profondeur = st.number_input(
        "Profondeur estimée du bâtiment (m)",
        min_value=3.0,
        max_value=80.0,
        value=float(round(profondeur_default, 1)),
        step=0.5,
        help="Utilisé pour un éventuel pignon ou un pavillon complet.",
    )

    has_pignon = st.checkbox("Un pignon latéral est également à traiter", value=False)

    st.markdown("### Boutiques en rez-de-chaussée")
    has_shops = st.checkbox("Il y a des boutiques / vitrines sur le rez-de-chaussée", value=False)
    shops_config = "aucune"
    if has_shops:
        shops_config = st.radio(
            "Configuration des boutiques",
            options=["une_boutique_toute_longueur", "deux_boutiques", "autre_configuration"],
            format_func=lambda v: {
                "une_boutique_toute_longueur": "Une boutique sur (presque) toute la longueur",
                "deux_boutiques": "Deux boutiques principales",
                "autre_configuration": "Autre configuration (mixte boutiques / logements)",
            }[v],
        )

    return {
        "building_type": building_type,
        "niveaux": int(niveaux),
        "hauteur_par_niveau": float(hauteur_par_niveau),
        "largeur": float(largeur),
        "profondeur": float(profondeur),
        "has_pignon": bool(has_pignon),
        "has_shops": bool(has_shops),
        "shops_config": shops_config,
    }


def render_facade_state_form(osm_ctx: Dict) -> Dict:
    st.markdown('<div class="lc-title">3. État de la façade et éléments visibles</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='lc-subtitle'>Quelques questions pour adapter l’estimation à la réalité du bâtiment.</div>",
        unsafe_allow_html=True,
    )

    etat_facade = st.radio(
        "État global de la façade",
        options=["bon", "moyen", "degrade"],
        index=1,
        format_func=lambda v: {"bon": "Bon état", "moyen": "État moyen", "degrade": "Dégradé"}[v],
    )

    support_key = st.selectbox(
        "Support principal",
        options=[
            "ENDUIT_CIMENT",
            "ENDUIT_PLATRE",
            "BETON_PEINT",
            "MONOCOUCHE",
            "CREPI",
            "PIERRE_TAILLE",
            "PIERRE_APPARENTE",
            "BRIQUE_PLEINE",
            "BRIQUE_APPARENTE",
        ],
        format_func=lambda v: v.replace("_", " ").title(),
    )

    st.markdown("### Ouvertures")
    nb_fenetres_petites = st.slider(
        "Nombre de petites fenêtres visibles",
        min_value=0,
        max_value=80,
        value=10,
        step=1,
    )
    nb_fenetres_grandes = st.slider(
        "Nombre de grandes fenêtres / portes-fenêtres",
        min_value=0,
        max_value=40,
        value=4,
        step=1,
    )

    st.markdown("### Garde-corps et balcons")
    garde_corps_niveau = st.selectbox(
        "Présence de garde-corps / balcons",
        options=["peu", "moyen", "beaucoup"],
        format_func=lambda v: {"peu": "Peu", "moyen": "Moyen", "beaucoup": "Beaucoup"}[v],
    )

    st.markdown("### Chiens-assis / lucarnes")
    traiter_chiens_assis = st.checkbox("Inclure les chiens-assis / lucarnes dans l’estimation", value=False)
    nb_chiens_assis = 0
    if traiter_chiens_assis:
        nb_chiens_assis = st.number_input(
            "Nombre de chiens-assis / lucarnes",
            min_value=1,
            max_value=20,
            value=2,
            step=1,
        )

    return {
        "etat_facade": etat_facade,
        "support_key": support_key,
        "nb_fenetres_petites": int(nb_fenetres_petites),
        "nb_fenetres_grandes": int(nb_fenetres_grandes),
        "garde_corps_niveau": garde_corps_niveau,
        "traiter_chiens_assis": bool(traiter_chiens_assis),
        "nb_chiens_assis": int(nb_chiens_assis),
    }


def render_contact_form() -> Dict:
    st.markdown('<div class="lc-title">4. Vos coordonnées</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='lc-subtitle'>Nous envoyons l’estimation détaillée par mail. Vous pouvez ensuite être rappelé.</div>",
        unsafe_allow_html=True,
    )

    nom = st.text_input("Nom / Société")
    email = st.text_input("Adresse e-mail")
    tel = st.text_input("Téléphone (optionnel)")
    delai_mois = st.slider(
        "Délai souhaité avant travaux",
        min_value=3,
        max_value=24,
        value=6,
        step=1,
    )
    urgent = delai_mois <= 3

    return {
        "nom": nom,
        "email": email,
        "tel": tel,
        "delai_mois": int(delai_mois),
        "urgent": bool(urgent),
    }
