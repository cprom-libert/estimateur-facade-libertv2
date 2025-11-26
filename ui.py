from typing import Dict, List, Optional
import streamlit as st
import pandas as pd
from pricing import Geometry


# ---------- TITRE + STEPPER ----------

def render_title():
    st.markdown(
        """
        <h1 style="margin-bottom:0.2rem;">Estimation de ravalement de façade</h1>
        <p style="color:rgba(0,0,0,0.60);font-size:0.95rem;margin-bottom:1.2rem;">
            Obtenez un ordre de grandeur du budget de votre ravalement en 5 étapes simples.
        </p>
        """,
        unsafe_allow_html=True,
    )


def render_stepper(step: int):
    # 0 = Adresse, 1 = Dimensions, 2 = État, 3 = Points singuliers + urgence, 4 = Coordonnées
    st.markdown(
        f"""
        <div class="lc-stepper">
            <div class="lc-step {'lc-step-active' if step == 0 else ''}">
                <span>1. Adresse</span>
            </div>
            <div class="lc-step {'lc-step-active' if step == 1 else ''}">
                <span>2. Taille de la façade</span>
            </div>
            <div class="lc-step {'lc-step-active' if step == 2 else ''}">
                <span>3. État de la façade</span>
            </div>
            <div class="lc-step {'lc-step-active' if step == 3 else ''}">
                <span>4. Détails & urgence</span>
            </div>
            <div class="lc-step {'lc-step-active' if step == 4 else ''}">
                <span>5. Coordonnées & estimation</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------- ÉTAPE 0 : ADRESSE ----------

def render_address_block(suggestions: List[Dict]) -> Dict:
    st.markdown("#### 1. Adresse du bâtiment")
    st.caption("Commencez par indiquer l’adresse de l’immeuble à ravaler.")

    query = st.text_input(
        "Adresse",
        key="addr_query",
        placeholder="Ex. 15 rue Brézin, 75014 Paris",
    )

    selected_label: Optional[str] = None
    selected_obj: Optional[Dict] = None

    if len(query.strip()) >= 3 and suggestions:
        st.caption("Suggestions (cliquez pour sélectionner)")
        labels = [s["label"] for s in suggestions]
        selected_label = st.radio(
            "",
            labels,
            index=0,
            key="addr_choice",
        )
        selected_obj = next((s for s in suggestions if s["label"] == selected_label), None)
    elif len(query.strip()) >= 3 and not suggestions:
        st.caption("Aucune adresse trouvée pour cette saisie.")

    return {
        "query": query,
        "selected_label": selected_label,
        "selected_obj": selected_obj,
    }


def render_streetview(lat: float, lon: float, iframe_url: str):
    st.markdown("#### Vue Street View")
    st.caption("Vérifiez que la façade affichée correspond bien à votre bâtiment.")

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


# ---------- ÉTAPE 1 : DIMENSIONS ----------

def render_building_dimensions_form(osm_ctx: Dict) -> Dict:
    st.markdown("#### 2. Taille de la façade")
    st.caption(
        "Indiquez le type de bâtiment, le nombre d’étages et la largeur approximative sur rue. "
        "Une estimation suffit, pas besoin d’être au centimètre près."
    )

    default_levels = osm_ctx.get("levels") or 5

    type_label = st.selectbox(
        "Quel type de bâtiment ?",
        ["Immeuble sur rue", "Maison individuelle"],
        index=0,
        key="building_type_label",
    )
    # Valeur interne pour le calcul
    building_type = "IMMEUBLE" if type_label.startswith("Immeuble") else "PAVILLON"

    support_label_to_key = {
        "Façade enduite (plâtre / crépi)": "PLATRE_ANCIEN",
        "Façade en pierre de taille": "PIERRE_TAILLE",
        "Façade en briques": "BRIQUE",
        "Façade en béton": "BETON",
        "Maison enduite": "PAVILLON_ENDUIT",
    }
    support_label = st.selectbox(
        "Type principal de façade",
        list(support_label_to_key.keys()),
        index=0,
        key="support_label",
    )
    support_key = support_label_to_key[support_label]

    niveaux = st.number_input(
        "Nombre d’étages au-dessus du rez-de-chaussée",
        min_value=1,
        max_value=20,
        value=int(default_levels),
        step=1,
        key="niveaux",
    )

    hauteur_par_niveau = st.number_input(
        "Hauteur moyenne par étage (m)",
        min_value=2.5,
        max_value=4.0,
        value=3.0,
        step=0.1,
        key="hauteur_par_niveau",
    )

    largeur = st.number_input(
        "Largeur de la façade sur rue (m)",
        min_value=3.0,
        max_value=80.0,
        value=15.0,
        step=0.5,
        key="largeur",
    )

    hauteur_estimee = niveaux * hauteur_par_niveau
    st.caption(f"Hauteur totale estimée : environ {hauteur_estimee:.1f} m.")

    return {
        "building_type": building_type,          # interne (IMMEUBLE / PAVILLON)
        "support_key": support_key,
        "niveaux": niveaux,
        "largeur": largeur,
        "hauteur_par_niveau": hauteur_par_niveau,
    }


# ---------- ÉTAPE 2 : ÉTAT FAÇADE ----------

def render_facade_state_form() -> Dict:
    st.markdown("#### 3. État de la façade")
    st.caption(
        "Indiquez l’état général visible depuis la rue. Cela nous permet d’ajuster la part de reprises et réparations."
    )

    etat_label = st.selectbox(
        "Comment décririez-vous l’état de la façade ?",
        ["Plutôt propre", "Quelques défauts", "Très abîmée"],
        index=1,
        key="etat_facade_label",
    )

    if etat_label == "Plutôt propre":
        etat_facade = "BON"
    elif etat_label == "Très abîmée":
        etat_facade = "DEGRADE"
    else:
        etat_facade = "MOYEN"

    porte_type = st.selectbox(
        "Entrée principale côté rue",
        ["Pas de porte particulière", "Porte d’entrée", "Grande porte cochère"],
        index=0,
        key="porte_type_label",
    )

    if porte_type == "Porte d’entrée":
        porte_internal = "Porte d’entrée"
    elif porte_type == "Grande porte cochère":
        porte_internal = "Porte cochère"
    else:
        porte_internal = "Aucune"

    return {
        "etat_facade": etat_facade,
        "etat_facade_label": etat_label,
        "porte_type": porte_internal,
    }


# ---------- ÉTAPE 3 : POINTS SINGULIERS + URGENCE ----------

def render_points_singuliers_form(osm_ctx: Dict, building_dims: Dict) -> Dict:
    st.markdown("#### 4. Détails visibles depuis la rue")
    st.caption(
        "Cochez les éléments qui semblent présents sur la façade. "
        "N’hésitez pas à regarder la vue Street View en parallèle."
    )

    default_commerce = bool(osm_ctx.get("has_shop"))
    largeur = float(building_dims.get("largeur") or 0.0)
    niveaux = int(building_dims.get("niveaux") or 1)

    default_lg_gc = round(0.5 * largeur * niveaux, 1) if largeur > 0 else 0.0
    default_nb_desc = max(1, int(round(largeur / 6))) if largeur > 0 else 2

    col1, col2 = st.columns(2)

    with col1:
        has_commerce_rdc = st.checkbox(
            "Il y a une boutique / vitrine au rez-de-chaussée",
            value=default_commerce,
            key="has_commerce_rdc",
        )
        has_bandeaux = st.checkbox(
            "Il y a des bandeaux ou corniches décoratives à reprendre",
            value=False,
            key="has_bandeaux",
        )
        has_appuis = st.checkbox(
            "Les bords de fenêtres sont à reprendre",
            value=True,
            key="has_appuis",
        )
        has_gardes_corps = st.checkbox(
            "Il y a des garde-corps (barreaux) sur les fenêtres / balcons",
            value=True if building_dims.get("building_type") == "IMMEUBLE" else False,
            key="has_gardes_corps",
        )

    with col2:
        has_toiture_debord = st.checkbox(
            "Il y a des avancées de toit / débords visibles",
            value=True if building_dims.get("building_type") == "PAVILLON" else False,
            key="has_toiture_debord",
        )
        has_acroteres = st.checkbox(
            "En tête de façade, il y a un acrotère (muret ou relevé)",
            value=False,
            key="has_acroteres",
        )
        nb_descente_ep = st.number_input(
            "Nombre de descentes d’eaux pluviales visibles (tuyaux verticaux)",
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
        "Ces informations permettent d’intégrer les éléments visibles depuis la rue "
        "(garde-corps, descentes, bandeaux…)."
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


def render_urgency_form() -> Dict:
    st.markdown("#### Délai souhaité pour les travaux")
    st.caption("Indiquez en combien de mois vous aimeriez idéalement démarrer le chantier.")

    delai_mois = st.slider(
        "Quand souhaiteriez-vous réaliser les travaux ?",
        min_value=1,
        max_value=36,
        value=6,
        step=1,
        key="delai_mois",
    )

    urgent = delai_mois <= 3

    if urgent:
        st.caption("Projet à court terme : nous vous recontacterons rapidement.")
    else:
        st.caption("Projet à moyen terme : cette estimation vous aide à vous projeter.")

    return {
        "delai_mois": int(delai_mois),
        "urgent": urgent,
    }


# ---------- ÉTAPE 4 : COORDONNÉES ----------

def render_contact_form() -> Dict:
    st.markdown("#### 5. Vos coordonnées")
    st.caption(
        "Nous utilisons ces informations pour vous envoyer le récapitulatif et, si vous le souhaitez, "
        "vous rappeler pour affiner le projet."
    )

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


# ---------- RAPPORT ----------

def render_rapport_header(addr_label: str, geom: Geometry, urgency: Dict | None = None):
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

    chips_html = (
        f'<div class="lc-chip">Hauteur estimée : {geom.hauteur:.1f} m</div>'
        f'<div class="lc-chip">Surface approximative de façades : {geom.surface_facades:.1f} m²</div>'
        f'<div class="lc-chip">Périmètre développé : {geom.perimetre:.1f} ml</div>'
    )

    if urgency:
        chips_html += f'<div class="lc-chip">Délai souhaité : {urgency["delai_mois"]} mois</div>'

    st.markdown(
        f"""
        <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;margin-bottom:10px;">
            {chips_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_pricing_table(lignes: List[Dict], total: float):
    if not lignes:
        st.info("Aucune ligne calculée.")
        return

    df = pd.DataFrame(lignes)

    # Harmonisation des sections + ordre
    df["section"] = df["section"].replace(
        {
            "Installation": "Installation de chantier",
            "Façades": "Façades",
            "Boiseries": "Boiseries / menuiseries",
            "Zinguerie": "Éléments métalliques",
            "COMMERCE": "Rez-de-chaussée commercial",
            "TOITURES": "Parties hautes / tête de façade",
        }
    )

    order_map = {
        "Installation de chantier": 1,
        "Façades": 2,
        "Boiseries / menuiseries": 3,
        "Rez-de-chaussée commercial": 4,
        "Éléments métalliques": 5,
        "Parties hautes / tête de façade": 6,
    }
    df["section_order"] = df["section"].map(order_map).fillna(99)
    df = df.sort_values(["section_order", "section"])

    df_display = df[["section", "designation", "quantite", "unite", "pu", "montant"]]

    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown(
        f"""
        <div style="text-align:right;font-size:1.1rem;font-weight:600;margin-top:0.8rem;">
            Total indicatif : {total:,.2f} € HT
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_rapport(addr_label: str, geom: Geometry, lignes: List[Dict], total: float, urgency: Dict | None = None):
    render_rapport_header(addr_label, geom, urgency)

    if not lignes:
        st.info("Aucune ligne calculée pour cette estimation.")
        return

    # Synthèse simple pour l’utilisateur
    st.markdown("#### Estimation globale")

    if total <= 20000:
        complexite = "Chantier plutôt simple"
    elif total <= 60000:
        complexite = "Chantier de complexité standard"
    else:
        complexite = "Chantier important / complexe"

    st.markdown(
        f"""
        <div style="padding:12px 16px;border-radius:14px;background:#f5f2ee;
                    border:1px solid rgba(0,0,0,0.05);margin-bottom:10px;">
            <p style="margin:0 0 4px 0;font-size:0.95rem;">
                Montant indicatif du ravalement (hors taxes) :
            </p>
            <p style="margin:0;font-size:1.4rem;font-weight:600;">
                {total:,.0f} € HT
            </p>
            <p style="margin:6px 0 0 0;font-size:0.9rem;color:rgba(0,0,0,0.65);">
                {complexite}. Cette estimation est basée sur les informations que vous avez saisies en ligne
                et devra être confirmée après une visite sur place.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Détail technique dans un expander
    with st.expander("Afficher le détail par poste (optionnel)", expanded=False):
        st.markdown("##### Détail estimatif par poste")
        render_pricing_table(lignes, total)
