# ui.py
from typing import Dict, List
import streamlit as st
import pandas as pd
from pricing import Geometry


def render_title():
    st.markdown(
        """
        <h1 style="margin-bottom:0.2rem;">Estimateur ravalement</h1>
        <p style="color:rgba(0,0,0,0.55);font-size:0.95rem;margin-bottom:1.2rem;">
            Estimation rapide et structurée de votre ravalement à partir d’une adresse et de quelques paramètres.
        </p>
        """,
        unsafe_allow_html=True,
    )


def render_stepper(step: int):
    # step : 0 = Adresse, 1 = Bâtiment, 2 = Coordonnées & estimation
    st.markdown(
        f"""
        <div class="lc-stepper">
            <div class="lc-step {'lc-step-active' if step == 0 else ''}">
                <span>1. Adresse</span>
            </div>
            <div class="lc-step {'lc-step-active' if step == 1 else ''}">
                <span>2. Bâtiment</span>
            </div>
            <div class="lc-step {'lc-step-active' if step == 2 else ''}">
                <span>3. Coordonnées & estimation</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_address_block(
    suggestions: List[Dict],
) -> Dict:
    st.markdown("#### Adresse du bâtiment")

    query = st.text_input("Saisissez l’adresse", key="addr_query", placeholder="Ex. 15 rue Brézin, 75014 Paris")

    selected = None
    selected_obj: Dict | None = None

    if len(query.strip()) >= 3 and suggestions:
        st.caption("Suggestions")
        labels = [s["label"] for s in suggestions]
        selected = st.radio(
            "",
            labels,
            index=0,
            key="addr_choice",
        )
        selected_obj = next((s for s in suggestions if s["label"] == selected), None)
    elif len(query.strip()) >= 3 and not suggestions:
        st.caption("Aucune adresse trouvée pour cette saisie.")

    return {
        "query": query,
        "selected_label": selected,
        "selected_obj": selected_obj,
    }


def render_streetview(lat: float, lon: float, iframe_url: str):
    st.markdown("#### Vue Street View")

    st.caption("Vérifiez que la façade affichée correspond bien à l’adresse saisie.")
    if "google.com/maps/embed" in iframe_url:
        st.markdown(
            f"""
            <iframe
                width="100%"
                height="430"
                frameborder="0"
                style="border-radius:18px;border:0;"
                src="{iframe_url}"
                allowfullscreen
            ></iframe>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.image(
            iframe_url,
            use_column_width=True,
            caption="Vue générique (clé Google Maps absente ou non autorisée).",
        )


def render_building_form(osm_ctx: Dict) -> Dict:
    st.markdown("#### Bâtiment")

    default_levels = osm_ctx.get("levels") or 5

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

    niveaux = st.number_input(
        "Nombre de niveaux hors combles",
        min_value=1,
        max_value=20,
        value=int(default_levels),
        step=1,
        key="niveaux",
    )

    etat_label = st.selectbox(
        "État de la façade",
        ["Bon", "Moyen", "Dégradé"],
        index=1,
        key="etat_facade_label",
        help="Bon : façade peu marquée. Dégradé : nombreux éclats, fissures, cloques.",
    )
    if etat_label == "Bon":
        etat_facade = "BON"
    elif etat_label == "Dégradé":
        etat_facade = "DEGRADE"
    else:
        etat_facade = "MOYEN"

    largeur = st.number_input(
        "Largeur de la façade principale (m)",
        min_value=3.0,
        max_value=80.0,
        value=15.0,
        step=0.5,
        key="largeur",
    )

    porte_type = st.selectbox(
        "Porte principale sur rue",
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


def render_points_singuliers_form(osm_ctx: Dict, building_form: Dict) -> Dict:
    st.markdown("#### Points singuliers de façade")

    default_commerce = bool(osm_ctx.get("has_shop"))
    largeur = float(building_form.get("largeur") or 0.0)
    niveaux = int(building_form.get("niveaux") or 1)

    default_lg_gc = round(0.5 * largeur * niveaux, 1) if largeur > 0 else 0.0
    default_nb_desc = max(1, int(round(largeur / 6))) if largeur > 0 else 2

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
        has_gardes_corps = st.checkbox(
            "Garde-corps métalliques sur façade",
            value=True if building_form.get("building_type") == "IMMEUBLE" else False,
            key="has_gardes_corps",
        )

    with c2:
        has_toiture_debord = st.checkbox(
            "Débords de toit / avancées",
            value=True if building_form.get("building_type") == "PAVILLON" else False,
            key="has_toiture_debord",
        )
        has_acroteres = st.checkbox(
            "Acrotères en tête de façade",
            value=False,
            key="has_acroteres",
        )
        nb_descente_ep = st.number_input(
            "Nombre de descentes EP",
            min_value=0,
            max_value=20,
            value=default_nb_desc,
            step=1,
            key="nb_descente_ep",
        )

    lg_gardes_corps = 0.0
    if has_gardes_corps:
        lg_gardes_corps = st.number_input(
            "Longueur approximative de garde-corps (ml)",
            min_value=0.0,
            max_value=500.0,
            value=default_lg_gc,
            step=1.0,
            key="lg_gardes_corps",
        )

    st.caption(
        "Les valeurs sont préremplies à partir de la largeur et du nombre de niveaux. "
        "Ajustez si nécessaire en regardant Street View."
    )

    return {
        "has_commerce_rdc": has_commerce_rdc,
        "has_bandeaux": has_bandeaux,
        "has_appuis": has_appuis,
        "has_toiture_debord": has_toiture_debord,
        "has_acroteres": has_acroteres,
        "nb_descente_ep": int(nb_descente_ep),
        "has_gardes_corps": has_gardes_corps,
        "lg_gardes_corps": float(lg_gardes_corps),
    }


def render_contact_form() -> Dict:
    st.markdown("#### Vos coordonnées")

    st.caption("L’estimation s’affichera après validation de ces informations.")

    with st.form(key="contact_form"):
        nom = st.text_input("Nom / société")
        email = st.text_input("Adresse e-mail *")
        tel = st.text_input("Téléphone (optionnel)")
        note = st.text_area(
            "Précisions sur votre projet (optionnel)",
            height=80,
        )
        submitted = st.form_submit_button("Obtenir mon estimation")

    email_valid = bool(email and "@" in email)

    if submitted and not email_valid:
        st.warning("Merci de renseigner une adresse e-mail valide.")

    return {
        "submitted": submitted and email_valid,
        "raw_submitted": submitted,
        "email_valid": email_valid,
        "email": email,
        "nom": nom,
        "tel": tel,
        "note": note,
    }


def render_rapport_header(addr_label: str, geom: Geometry):
    st.markdown(
        f"""
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.8rem;">
          <div>
            <h3 style="margin-bottom:0.2rem;">Rapport d’estimation</h3>
            <p style="margin:0;color:rgba(0,0,0,0.65);font-size:0.9rem;">{addr_label}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;margin-bottom:10px;">
            <div class="lc-chip">Hauteur estimée : {geom.hauteur:.1f} m</div>
            <div class="lc-chip">Surface façades : {geom.surface_facades:.1f} m²</div>
            <div class="lc-chip">Périmètre : {geom.perimetre:.1f} ml</div>
            <div class="lc-chip">Façades prises en compte : {geom.nb_facades}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_pricing_table(lignes: List[Dict], total: float):
    if not lignes:
        st.info("Aucune ligne calculée.")
        return

    df = pd.DataFrame(lignes)
    df_display = df[["section", "designation", "quantite", "unite", "pu", "montant"]]

    df_display["section_order"] = df_display["section"].map(
        {
            "LOGISTIQUE": 1,
            "FAÇADES": 2,
            "BOISERIES": 3,
            "COMMERCE": 4,
            "ZINGUERIE": 5,
            "TOITURES": 6,
        }
    ).fillna(99)
    df_display = df_display.sort_values(["section_order", "section"])

    st.markdown("#### Détail estimatif (HT)")
    st.dataframe(
        df_display.drop(columns=["section_order"]),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown(
        f"""
        <div style="text-align:right;font-size:1.25rem;font-weight:600;margin-top:1rem;">
            TOTAL ESTIMATIF : {total:,.2f} € HT
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_rapport(addr_label: str, geom: Geometry, lignes: List[Dict], total: float):
    render_rapport_header(addr_label, geom)
    render_pricing_table(lignes, total)
