# ui.py
from typing import Dict, List
import streamlit as st
import pandas as pd
from pricing import Geometry


def render_title():
    st.title("Estimateur ravalement – Paris")
    st.caption("Estimation rapide à partir de l’adresse et d’une vue Street View.")


def render_address_block(
    suggestions: List[Dict],
) -> Dict:
    """
    Affiche la saisie + les suggestions dans le même bloc.
    Retourne un dict avec la sélection courante.
    """
    st.subheader("Adresse du bâtiment")

    col = st.container()
    with col:
        query = st.text_input("Adresse", key="addr_query")

        selected = None
        selected_obj: Dict | None = None

        if len(query.strip()) >= 3 and suggestions:
            labels = [s["label"] for s in suggestions]
            selected = st.radio(
                "Suggestions",
                labels,
                index=0,
                label_visibility="collapsed",
                key="addr_choice",
            )
            selected_obj = next((s for s in suggestions if s["label"] == selected), None)

    return {
        "query": query,
        "selected_label": selected,
        "selected_obj": selected_obj,
    }


def render_streetview(lat: float, lon: float, iframe_url: str):
    st.subheader("Vue Street View")
    if "google.com/maps/embed" in iframe_url:
        st.markdown(
            f"""
            <iframe
                width="100%"
                height="450"
                frameborder="0"
                style="border:0"
                src="{iframe_url}"
                allowfullscreen>
            </iframe>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.image(iframe_url, use_column_width=True, caption="Vue générique (pas de clé Google Maps configurée).")


def render_building_form(osm_ctx: Dict) -> Dict:
    st.subheader("Caractéristiques du bâtiment")

    col1, col2 = st.columns(2)

    with col1:
        building_type = st.selectbox(
            "Type de bâtiment",
            ["IMMEUBLE", "PAVILLON"],
            index=0,
            key="building_type",
        )

        support_label_to_key = {
            "Plâtre ancien": "PLATRE_ANCIEN",
            "Pierre de taille": "PIERRE_TAILLE",
            "Briques": "BRIQUE",
            "Béton": "BETON",
            "Pavillon enduit": "PAVILLON_ENDUIT",
        }
        support_label = st.selectbox(
            "Support principal",
            list(support_label_to_key.keys()),
            index=0,
            key="support_label",
        )
        support_key = support_label_to_key[support_label]

        default_levels = osm_ctx.get("levels") or 5
        niveaux = st.number_input(
            "Nombre de niveaux hors combles",
            min_value=1,
            max_value=20,
            value=int(default_levels),
            step=1,
            key="niveaux",
        )

        # Nouvel élément : état de la façade
        etat_label = st.selectbox(
            "État de la façade",
            ["Bon", "Moyen", "Dégradé"],
            index=1,
            key="etat_facade_label",
        )
        # Normalisation en code interne
        if etat_label == "Bon":
            etat_facade = "BON"
        elif etat_label == "Dégradé":
            etat_facade = "DEGRADE"
        else:
            etat_facade = "MOYEN"

    with col2:
        largeur = st.number_input(
            "Largeur façade principale (m)",
            min_value=3.0,
            max_value=80.0,
            value=15.0,
            step=0.5,
            key="largeur",
        )

        porte_type = st.selectbox(
            "Porte principale",
            ["Aucune", "Porte d’entrée", "Porte cochère"],
            index=0,
            key="porte_type",
        )

    return {
        "building_type": building_type,
        "support_key": support_key,
        "niveaux": niveaux,
        "largeur": largeur,
        "porte_type": porte_type,
        "etat_facade": etat_facade,
    }


def render_points_singuliers_form(osm_ctx: Dict) -> Dict:
    st.subheader("Points singuliers façade")

    default_commerce = bool(osm_ctx.get("has_shop"))
    c1, c2 = st.columns(2)

    with c1:
        has_commerce_rdc = st.checkbox(
            "Boutique / commerce en RDC",
            value=default_commerce,
            key="has_commerce_rdc",
        )
        has_bandeaux = st.checkbox(
            "Bandeaux saillants à traiter",
            value=False,
            key="has_bandeaux",
        )
        has_appuis = st.checkbox(
            "Appuis de fenêtres à reprendre",
            value=True,
            key="has_appuis",
        )

    with c2:
        has_toiture_debord = st.checkbox(
            "Débords de toit / avancées",
            value=False,
            key="has_toiture_debord",
        )
        has_acroteres = st.checkbox(
            "Acrotères à traiter",
            value=False,
            key="has_acroteres",
        )
        nb_descente_ep = st.number_input(
            "Nombre de descentes EP",
            min_value=0,
            max_value=20,
            value=2,
            step=1,
            key="nb_descente_ep",
        )

    return {
        "has_commerce_rdc": has_commerce_rdc,
        "has_bandeaux": has_bandeaux,
        "has_appuis": has_appuis,
        "has_toiture_debord": has_toiture_debord,
        "has_acroteres": has_acroteres,
        "nb_descente_ep": int(nb_descente_ep),
    }


def render_rapport_header(addr_label: str, geom: Geometry):
    st.markdown(f"### Rapport d’estimation – {addr_label}")
    st.markdown(
        f"- Hauteur estimée : **{geom.hauteur:.1f} m**  \n"
        f"- Surface totale de façades : **{geom.surface_facades:.1f} m²**  \n"
        f"- Périmètre développé : **{geom.perimetre:.1f} ml**  \n"
        f"- Nombre de façades considérées : **{geom.nb_facades}**"
    )


def render_pricing_table(lignes: List[Dict], total: float):
    if not lignes:
        st.info("Aucune ligne calculée.")
        return

    df = pd.DataFrame(lignes)
    df_display = df[["section", "designation", "quantite", "unite", "pu", "montant"]]

    st.subheader("Détail estimatif (HT)")
    st.dataframe(df_display, use_container_width=True)

    st.markdown(
        f"""
        <div style="text-align:right;font-size:1.3rem;font-weight:bold;margin-top:1rem;">
            TOTAL ESTIMATIF : {total:,.2f} € HT
        </div>
        """,
        unsafe_allow_html=True,
    )
