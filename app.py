# app.py
import streamlit as st
from typing import Dict

from apis import get_address_suggestions, fetch_osm_context, build_streetview_embed_url
from pricing import estimate_geometry, build_pricing
import ui


def init_state():
    if "step" not in st.session_state:
        st.session_state.step = 0
    if "addr_label" not in st.session_state:
        st.session_state.addr_label = None
    if "coords" not in st.session_state:
        st.session_state.coords = None
    if "osm_ctx" not in st.session_state:
        st.session_state.osm_ctx = {}
    if "lignes" not in st.session_state:
        st.session_state.lignes = []
    if "total" not in st.session_state:
        st.session_state.total = 0.0
    if "last_geom" not in st.session_state:
        st.session_state.last_geom = None
    if "form_building" not in st.session_state:
        st.session_state.form_building = None
    if "form_points" not in st.session_state:
        st.session_state.form_points = None
    if "contact" not in st.session_state:
        st.session_state.contact = None


def inject_global_style():
    # Palette inspirée de Libert & Cie : fond légèrement chaud, bleu profond + accent terracotta.
    st.markdown(
        """
        <style>
        :root {
            --lc-primary: #1e2a3b;
            --lc-accent: #c56a3a;
            --lc-bg: #f5f2ee;
        }

        html, body, [class*="css"]  {
            font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
        }

        body {
            background-color: var(--lc-bg);
        }

        .main .block-container {
            max-width: 1100px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }

        .lc-card {
            background: #ffffff;
            border-radius: 18px;
            padding: 20px 22px;
            box-shadow: 0 12px 30px rgba(0,0,0,0.06);
            border: 1px solid rgba(0,0,0,0.04);
            margin-bottom: 18px;
        }

        .lc-chip {
            display: inline-flex;
            align-items: center;
            padding: 4px 12px;
            border-radius: 999px;
            background: rgba(197,106,58,0.07);
            font-size: 0.8rem;
            color: rgba(0,0,0,0.7);
            margin-right: 6px;
        }

        .lc-stepper {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }

        .lc-step {
            flex: 1;
            min-width: 120px;
            padding: 8px 12px;
            border-radius: 999px;
            background: rgba(0,0,0,0.03);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.85rem;
            color: rgba(0,0,0,0.55);
        }

        .lc-step.lc-step-active {
            background: var(--lc-primary);
            color: #ffffff;
            font-weight: 600;
        }

        .lc-step span {
            margin-left: 6px;
        }

        button[kind="primary"] {
            border-radius: 999px !important;
            padding: 0.4rem 1.4rem !important;
            font-weight: 500 !important;
            background-color: var(--lc-accent) !important;
            border-color: var(--lc-accent) !important;
            color: #ffffff !important;
        }

        button[kind="primary"]:hover {
            filter: brightness(1.03);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main():
    st.set_page_config(page_title="Estimateur ravalement – Paris", layout="wide")
    inject_global_style()
    init_state()

    google_api_key = st.secrets.get("GOOGLE_API_KEY")

    ui.render_title()

    step = st.session_state.step
    ui.render_stepper(step)

    # ÉTAPE 0 : recherche adresse
    if step == 0:
        query = st.session_state.get("addr_query", "")
        suggestions = []
        if len(query.strip()) >= 3:
            try:
                suggestions = get_address_suggestions(query)
            except Exception as e:
                st.error(f"Erreur lors de la recherche d’adresse : {e}")

        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        addr_block = ui.render_address_block(suggestions)

        col_btn = st.columns([1, 1, 2])[0]
        with col_btn:
            if st.button("Analyser le bâtiment", type="primary"):
                selected_obj = addr_block["selected_obj"]
                if not selected_obj:
                    st.error("Merci de sélectionner une adresse dans la liste.")
                else:
                    lat = selected_obj["lat"]
                    lon = selected_obj["lon"]
                    addr_label = selected_obj["label"]

                    # Contexte OSM
                    osm_ctx: Dict = {}
                    try:
                        osm_ctx = fetch_osm_context(lat, lon)
                    except Exception as e:
                        st.warning(f"Impossible de récupérer les données OSM : {e}")
                        osm_ctx = {}

                    st.session_state.addr_label = addr_label
                    st.session_state.coords = {"lat": lat, "lon": lon}
                    st.session_state.osm_ctx = osm_ctx
                    st.session_state.lignes = []
                    st.session_state.total = 0.0
                    st.session_state.last_geom = None
                    st.session_state.form_building = None
                    st.session_state.form_points = None
                    st.session_state.contact = None
                    st.session_state.step = 1
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # ÉTAPE 1 : vue Street View + réglages bâtiment/points singuliers
    if st.session_state.step == 1:
        addr_label = st.session_state.addr_label
        coords = st.session_state.coords or {}
        osm_ctx = st.session_state.osm_ctx or {}

        if not addr_label or not coords:
            st.session_state.step = 0
            st.rerun()

        lat = coords["lat"]
        lon = coords["lon"]

        # Carte : Street View
        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        iframe_url = build_streetview_embed_url(lat, lon, google_api_key)
        ui.render_streetview(lat, lon, iframe_url)
        st.markdown('</div>', unsafe_allow_html=True)

        # Carte : paramètres bâtiment + points singuliers
        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        col_left, col_right = st.columns([1.2, 1])

        with col_left:
            building_form = ui.render_building_form(osm_ctx)

        with col_right:
            points_form = ui.render_points_singuliers_form(osm_ctx, building_form)

        col_btn_next, col_btn_new = st.columns([1, 1])

        with col_btn_next:
            # On ne calcule pas encore ici, on passe à l’étape coordonnées
            if st.button("Étape suivante : coordonnées", type="primary"):
                st.session_state.form_building = building_form
                st.session_state.form_points = points_form
                st.session_state.step = 2
                st.rerun()

        with col_btn_new:
            if st.button("Nouvelle adresse"):
                st.session_state.step = 0
                st.session_state.addr_label = None
                st.session_state.coords = None
                st.session_state.osm_ctx = {}
                st.session_state.lignes = []
                st.session_state.total = 0.0
                st.session_state.last_geom = None
                st.session_state.form_building = None
                st.session_state.form_points = None
                st.session_state.contact = None
                st.session_state.addr_query = ""
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # ÉTAPE 2 : coordonnées + calcul + rapport
    if st.session_state.step == 2:
        addr_label = st.session_state.addr_label
        coords = st.session_state.coords or {}
        if not addr_label or not coords or not st.session_state.form_building or not st.session_state.form_points:
            # Sécurité : si on arrive ici sans données, on revient à l’étape 0
            st.session_state.step = 0
            st.rerun()

        building_form = st.session_state.form_building
        points_form = st.session_state.form_points

        # Carte coordonnées
        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        contact = ui.render_contact_form()
        st.markdown('</div>', unsafe_allow_html=True)

        # Quand l’email est validé, on calcule et on affiche le rapport
        if contact["submitted"]:
            st.session_state.contact = contact

            geom = estimate_geometry(
                building_type=building_form["building_type"],
                niveaux=building_form["niveaux"],
                largeur_facade=building_form["largeur"],
            )

            porte_type = building_form["porte_type"]
            options = points_form.copy()
            options["porte_entree"] = porte_type == "Porte d’entrée"
            options["porte_cochere"] = porte_type == "Porte cochère"

            lignes, total = build_pricing(
                geom=geom,
                support_key=building_form["support_key"],
                options=options,
                facade_state=building_form["etat_facade"],
            )

            st.session_state.lignes = lignes
            st.session_state.total = total
            st.session_state.last_geom = geom

        # Carte rapport si calcul déjà fait
        if st.session_state.lignes and st.session_state.last_geom is not None:
            st.markdown('<div class="lc-card">', unsafe_allow_html=True)
            ui.render_rapport(
                st.session_state.addr_label,
                st.session_state.last_geom,
                st.session_state.lignes,
                st.session_state.total,
            )
            st.markdown('</div>', unsafe_allow_html=True)

        # Boutons bas de page
        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        col_back, col_new = st.columns([1, 1])
        with col_back:
            if st.button("Retour étape bâtiment"):
                st.session_state.step = 1
                st.rerun()
        with col_new:
            if st.button("Nouvelle adresse"):
                st.session_state.step = 0
                st.session_state.addr_label = None
                st.session_state.coords = None
                st.session_state.osm_ctx = {}
                st.session_state.lignes = []
                st.session_state.total = 0.0
                st.session_state.last_geom = None
                st.session_state.form_building = None
                st.session_state.form_points = None
                st.session_state.contact = None
                st.session_state.addr_query = ""
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
