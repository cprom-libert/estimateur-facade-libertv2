import streamlit as st
from typing import Any, Callable, Dict, Optional

from apis import build_streetview_embed_url


def init_css() -> None:
    """Applique un style sobre (inspiration Apple) à l'app."""
    st.markdown(
        """
        <style>
        .lc-card {
            background: #ffffff;
            border-radius: 16px;
            padding: 1.2rem 1.4rem;
            box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
            margin-bottom: 1rem;
        }
        .lc-bandeau-prix {
            position: sticky;
            bottom: 0;
            z-index: 999;
            background: #0B2239;
            color: #ffffff;
            padding: 0.7rem 1.2rem;
            border-radius: 12px;
            margin-top: 0.8rem;
        }
        .lc-bandeau-prix small {
            color: #cbd5f5;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------
# Étape 0 : adresse
# ----------------------------------------------------------------------
def render_address_step() -> bool:
    """
    Étape adresse : l'utilisateur saisit l'adresse.
    Geocoding à réaliser côté apis.py (geocode_address).
    Ici, on se contente de demander l'adresse et on laisse apis/geocoding existant
    remplir st.session_state.coords et st.session_state.addr_label si besoin.
    """
    st.markdown('<div class="lc-card">', unsafe_allow_html=True)
    st.subheader("Adresse du chantier")

    addr = st.text_input(
        "Adresse",
        value=st.session_state.get("addr_label", "") or "",
        placeholder="Ex. : 15 rue Brézin, 75014 Paris",
    )

    st.markdown(
        "<p style='font-size:0.9rem;color:#555;'>"
        "Saisissez l'adresse du bâtiment à ravaler. "
        "L'étape suivante vous permettra de préciser les dimensions de la façade."
        "</p>",
        unsafe_allow_html=True,
    )

    ok = False
    if st.button("Valider l'adresse et continuer", type="primary"):
        addr = (addr or "").strip()
        if not addr:
            st.error("Merci de renseigner une adresse.")
        else:
            # On stocke simplement l'adresse saisie.
            st.session_state.addr_label = addr
            # Les coordonnées (lat/lon) doivent être définies côté apis/geocoding.
            # Si ce n'est pas fait, l'affichage Street View utilisera les infos disponibles.
            ok = True

    st.markdown("</div>", unsafe_allow_html=True)
    return ok


# ----------------------------------------------------------------------
# Wrapper : carte + formulaire sur desktop
# ----------------------------------------------------------------------
def render_map_and_form(
    google_api_key: Optional[str],
    form_func: Callable[..., Any],
    osm_ctx: Optional[Dict] = None,
    **form_kwargs: Any,
) -> Any:
    """
    Affiche la Street View à gauche (si possible) et le formulaire à droite.
    Sur mobile, les colonnes s'empilent naturellement.
    """
    coords = st.session_state.get("coords")

    col_map, col_form = st.columns([1, 1.2])

    with col_map:
        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        st.markdown("**Votre façade**", unsafe_allow_html=True)

        if coords and google_api_key:
            iframe = build_streetview_embed_url(coords["lat"], coords["lon"], google_api_key)
            st.markdown(
                f'<iframe src="{iframe}" width="100%" height="320" '
                f'style="border:0;border-radius:14px;" allowfullscreen loading="lazy"></iframe>',
                unsafe_allow_html=True,
            )
        else:
            st.info("La vue Street View apparaîtra ici après la géolocalisation de l'adresse.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_form:
        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        out = form_func(osm_ctx or {}, **form_kwargs)
        st.markdown("</div>", unsafe_allow_html=True)

    return out


# ----------------------------------------------------------------------
# Étape 1 : dimensions du bâtiment
# ----------------------------------------------------------------------
def render_building_dimensions_form(osm_ctx: Dict) -> Optional[Dict]:
    """
    Formulaire des dimensions principales.
    """
    st.subheader("Dimensions de la façade")

    building_type = st.radio(
        "Type de bâtiment",
        options=["IMMEUBLE", "PAVILLON"],
        index=0,
        format_func=lambda x: "Immeuble" if x == "IMMEUBLE" else "Pavillon / maison",
    )

    col_niv, col_hpn = st.columns(2)
    with col_niv:
        niveaux = st.number_input(
            "Nombre de niveaux (étages)",
            min_value=1,
            max_value=15,
            value=int(osm_ctx.get("levels", 5) or 5),
            step=1,
        )
    with col_hpn:
        hauteur_par_niveau = st.number_input(
            "Hauteur moyenne par niveau (m)",
            min_value=2.5,
            max_value=4.0,
            value=3.0,
            step=0.1,
        )

    largeur = st.number_input(
        "Largeur de la façade principale (sur rue) en mètres",
        min_value=1.0,
        max_value=200.0,
        value=float(osm_ctx.get("front_length_m", 15.0) or 15.0),
        step=0.5,
        help="Longueur approximative de la façade côté rue.",
    )

    profondeur = st.number_input(
        "Profondeur approximative du bâtiment (m)",
        min_value=5.0,
        max_value=80.0,
        value=float(osm_ctx.get("depth_m", 12.0) or 12.0),
        step=0.5,
        help="Utilisé pour un éventuel pignon ou un pavillon complet.",
    )

    has_pignon = st.checkbox(
        "Inclure une façade latérale (pignon) dans le ravalement",
        value=False,
        help="Cochez si une façade latérale donnant sur l'extérieur doit aussi être ravallée.",
    )

    dims = {
        "building_type": building_type,
        "niveaux": int(niveaux),
        "hauteur_par_niveau": float(hauteur_par_niveau),
        "largeur": float(largeur),
        "profondeur": float(profondeur),
        "has_pignon": bool(has_pignon),
    }

    return dims


# ----------------------------------------------------------------------
# Étape 2 : état de façade, ouvertures, garde-corps, chiens-assis
# ----------------------------------------------------------------------
def render_facade_state_form(osm_ctx: Dict) -> Optional[Dict]:
    st.subheader("État de la façade et éléments particuliers")

    etat_facade = st.radio(
        "État général de la façade",
        options=["bon", "moyen", "dégradé"],
        index=1,
        format_func=lambda x: x.capitalize(),
        help="Permet d'estimer la part de préparation (piochage, reprises...).",
    )

    support_key = st.selectbox(
        "Type de support principal",
        options=[
            "ENDUIT_CIMENT",
            "ENDUIT_PLATRE",
            "BETON",
            "BRIQUE",
            "PIERRE",
        ],
        index=0,
        format_func=lambda x: {
            "ENDUIT_CIMENT": "Enduit ciment (façade récente)",
            "ENDUIT_PLATRE": "Enduit plâtre (façade ancienne)",
            "BETON": "Béton peint",
            "BRIQUE": "Brique",
            "PIERRE": "Pierre / moellons",
        }.get(x, x),
    )

    st.markdown("### Ouvertures et garde-corps")

    nb_fenetres_grandes = st.number_input(
        "Nombre approximatif de grandes fenêtres donnant sur la façade",
        min_value=0,
        max_value=200,
        value=10,
        step=1,
        help="Seules les grandes fenêtres sont prises en compte (hors petites ouvertures techniques).",
    )

    garde_corps_niveau = st.radio(
        "Présence de garde-corps / balcons",
        options=["peu", "moyen", "beaucoup"],
        index=1,
        format_func=lambda x: {
            "peu": "Peu de garde-corps",
            "moyen": "Quelques garde-corps",
            "beaucoup": "Beaucoup de garde-corps",
        }[x],
    )

    st.markdown("### Toiture et chiens-assis")

    traiter_chiens_assis = st.checkbox(
        "Inclure les chiens-assis (lucarnes en toiture)",
        value=False,
    )
    nb_chiens_assis = 0
    if traiter_chiens_assis:
        nb_chiens_assis = st.number_input(
            "Nombre approximatif de chiens-assis à traiter",
            min_value=1,
            max_value=50,
            value=2,
            step=1,
        )

    facade_state = {
        "etat_facade": etat_facade,
        "support_key": support_key,
        "nb_fenetres_grandes": int(nb_fenetres_grandes),
        "garde_corps_niveau": garde_corps_niveau,
        "traiter_chiens_assis": bool(traiter_chiens_assis),
        "nb_chiens_assis": int(nb_chiens_assis),
    }

    return facade_state


# ----------------------------------------------------------------------
# Étape 3 : coordonnées client
# ----------------------------------------------------------------------
def render_contact_form(osm_ctx: Dict = None) -> Optional[Dict]:
    st.subheader("Vos coordonnées")

    col1, col2 = st.columns(2)
    with col1:
        nom = st.text_input("Nom / Prénom", value=st.session_state.get("contact_nom", ""))
    with col2:
        email = st.text_input("Adresse e-mail", value=st.session_state.get("contact_email", ""))

    tel = st.text_input("Téléphone (facultatif)", value=st.session_state.get("contact_tel", ""))

    delai_mois = st.number_input(
        "Délai souhaité avant travaux (en mois)",
        min_value=1,
        max_value=36,
        value=6,
        step=1,
    )
    urgent = delai_mois <= 3

    contact = {
        "nom": nom.strip(),
        "email": email.strip(),
        "tel": tel.strip(),
        "delai_mois": int(delai_mois),
        "urgent": bool(urgent),
    }

    # On ne valide pas ici : c'est géré dans app.py (bouton désactivé si pas d'email / nom)
    return contact


# ----------------------------------------------------------------------
# Affichage bandeau prix (preview)
# ----------------------------------------------------------------------
def render_price_banner(total_ttc: Optional[float], label: str) -> None:
    """
    Bandeau bas de page avec le prix estimatif.
    """
    if total_ttc is None:
        return

    txt = f"{total_ttc:,.0f} € TTC".replace(",", " ").replace(".", ",")
    st.markdown(
        f"""
        <div class="lc-bandeau-prix">
            <div><b>{label}</b> : {txt}</div>
            <small>Montant indicatif à confirmer après visite sur place.</small>
        </div>
        """,
        unsafe_allow_html=True,
    )
