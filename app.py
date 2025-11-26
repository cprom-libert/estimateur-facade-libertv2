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


def main():
    st.set_page_config(page_title="Estimateur ravalement – Paris", layout="wide")
    init_state()

    google_api_key = st.secrets.get("GOOGLE_API_KEY")

    ui.render_title()

    step = st.session_state.step

    # ÉTAPE 0 : recherche adresse
    if step == 0:
        query = st.session_state.get("addr_query", "")
        suggestions = []
        if len(query.strip()) >= 3:
            suggestions = get_address_suggestions(query)

        addr_block = ui.render_address_block(suggestions)

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
                st.session_state.step = 1
                st.rerun()

    # ÉTAPE 1 : rapport
    if st.session_state.step == 1:
        addr_label = st.session_state.addr_label
        coords = st.session_state.coords or {}
        osm_ctx = st.session_state.osm_ctx or {}

        if not addr_label or not coords:
            st.session_state.step = 0
            st.rerun()

        lat = coords["lat"]
        lon = coords["lon"]

        # Street View interactif
        iframe_url = build_streetview_embed_url(lat, lon, google_api_key)
        ui.render_streetview(lat, lon, iframe_url)

        # Formulaires bâtiment + points singuliers
        building_form = ui.render_building_form(osm_ctx)
        points_form = ui.render_points_singuliers_form(osm_ctx)

        if st.button("Calculer l’estimation", type="primary"):
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

            ui.render_rapport_header(addr_label, geom)
            ui.render_pricing_table(lignes, total)

        # Si on a déjà un calcul en mémoire, on l’affiche
        if st.session_state.lignes:
            geom = estimate_geometry(
                building_type=building_form["building_type"],
                niveaux=building_form["niveaux"],
                largeur_facade=building_form["largeur"],
            )
            ui.render_rapport_header(addr_label, geom)
            ui.render_pricing_table(st.session_state.lignes, st.session_state.total)

        if st.button("Nouvelle adresse"):
            st.session_state.step = 0
            st.session_state.addr_label = None
            st.session_state.coords = None
            st.session_state.osm_ctx = {}
            st.session_state.lignes = []
            st.session_state.total = 0.0
            st.session_state.addr_query = ""
            st.rerun()


if __name__ == "__main__":
    main()
