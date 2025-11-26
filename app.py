import streamlit as st
from typing import Dict, Optional
import smtplib
from email.message import EmailMessage

from apis import (
    get_address_suggestions,
    fetch_osm_context,
    build_streetview_embed_url,
)
from pricing import estimate_geometry, build_pricing, NIVEAU_HAUTEUR, Geometry
import ui


# ----------------------------------------------------------------
#                 INITIALISATION & STYLES
# ----------------------------------------------------------------

def init_state():
    defaults = {
        "step": 0,
        "addr_label": None,
        "coords": None,
        "osm_ctx": {},
        "lignes": [],
        "total": 0.0,
        "last_geom": None,
        "building_dims": None,
        "facade_state": None,
        "points_form": None,
        "urgency": None,
        "contact": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def inject_global_style():
    st.markdown(
        """
        <style>
        :root {
            --lc-primary:#1e2a3b;
            --lc-accent:#c56a3a;
            --lc-bg:#f5f2ee;
        }
        html, body, [class*="css"]  {
            font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
        }
        body { background-color: var(--lc-bg); }
        .main .block-container {
            max-width: 1100px;
            padding-top: 1.2rem;
            padding-bottom: 4rem;
        }
        .lc-card {
            background:#ffffff;
            border-radius:18px;
            padding:20px 22px;
            box-shadow:0 12px 30px rgba(0,0,0,0.06);
            border:1px solid rgba(0,0,0,0.04);
            margin-bottom:18px;
        }
        .lc-chip {
            display:inline-flex;
            align-items:center;
            padding:4px 12px;
            border-radius:999px;
            background:rgba(197,106,58,0.07);
            font-size:0.8rem;
            color:rgba(0,0,0,0.7);
            margin-right:6px;
        }
        .lc-stepper {
            display:flex;
            gap:10px;
            margin-bottom:20px;
            flex-wrap:wrap;
        }
        .lc-step {
            flex:1;
            min-width:120px;
            padding:8px 12px;
            border-radius:999px;
            background:rgba(0,0,0,0.03);
            display:flex;
            align-items:center;
            justify-content:center;
            font-size:0.85rem;
            color:rgba(0,0,0,0.55);
        }
        .lc-step.lc-step-active {
            background:var(--lc-primary);
            color:#ffffff;
            font-weight:600;
        }
        button[kind="primary"] {
            border-radius:999px !important;
            padding:0.4rem 1.4rem !important;
            font-weight:500 !important;
            background-color:var(--lc-accent) !important;
            border-color:var(--lc-accent) !important;
            color:#ffffff !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------
#                 ENVOI D’EMAIL (prospect + interne)
# ----------------------------------------------------------------

def send_notification_email(
    to_email: str,
    prospect_email: str,
    prospect_nom: str,
    addr_label: str,
    geom: Geometry,
    total: float,
    urgency: Dict,
):
    """ Envoie 2 mails : interne + prospect """

    host = st.secrets.get("SMTP_HOST")
    port = st.secrets.get("SMTP_PORT")
    user = st.secrets.get("SMTP_USER")
    password = st.secrets.get("SMTP_PASSWORD")
    use_tls = st.secrets.get("SMTP_USE_TLS", True)

    if not all([host, port, user, password]):
        st.info("Paramètres SMTP manquants : e-mails non envoyés.")
        return

    # ---------- MAIL INTERNE ----------
    msg_admin = EmailMessage()
    msg_admin["Subject"] = f"Nouvelle estimation ravalement – {addr_label}"
    msg_admin["From"] = user
    msg_admin["To"] = to_email

    corps_admin = f"""
Nouvelle estimation de ravalement

Adresse : {addr_label}
Nom / Société : {prospect_nom or 'Non renseigné'}
Email prospect : {prospect_email}

Hauteur estimée : {geom.hauteur:.1f} m
Surface façades : {geom.surface_facades:.1f} m²
Périmètre développé : {geom.perimetre:.1f} ml

Total estimatif HT : {total:,.2f} €

Délai souhaité : {urgency['delai_mois']} mois
Projet urgent : {"Oui" if urgency.get("urgent") else "Non"}
"""
    msg_admin.set_content(corps_admin)

    # ---------- MAIL PROSPECT ----------
    msg_client = EmailMessage()
    msg_client["Subject"] = "Votre estimation de ravalement – Libert & Cie"
    msg_client["From"] = user
    msg_client["To"] = prospect_email

    corps_client = f"""
Bonjour {prospect_nom or ''},

Merci pour votre demande d'estimation de ravalement.

Voici un récapitulatif :
• Adresse : {addr_label}
• Hauteur estimée : {geom.hauteur:.1f} m
• Surface de façades : {geom.surface_facades:.1f} m²
• Délai souhaité : {urgency["delai_mois"]} mois

Montant indicatif :
→ {total:,.2f} € HT

Cette estimation est une première approche et sera affinée après visite sur place.

Nous revenons rapidement vers vous.

Libert & Cie
contact@libertsas.fr
"""
    msg_client.set_content(corps_client)

    # ---------- ENVOI ----------
    try:
        with smtplib.SMTP(host, int(port)) as server:
            if use_tls:
                server.starttls()
            server.login(user, password)
            server.send_message(msg_admin)
            server.send_message(msg_client)

        st.success("Votre estimation et votre email ont bien été envoyés.")
    except Exception as e:
        st.warning(f"Estimation réalisée mais e-mail non envoyé ({e}).")


# ----------------------------------------------------------------
#                            MAIN
# ----------------------------------------------------------------

def main():
    st.set_page_config(page_title="Estimateur ravalement", layout="wide")
    inject_global_style()
    init_state()

    google_api_key = st.secrets.get("GOOGLE_API_KEY")

    ui.render_title()
    ui.render_stepper(st.session_state.step)

    step = st.session_state.step

    # ---------------------------------------------------
    # ÉTAPE 0 — Adresse
    # ---------------------------------------------------
    if step == 0:
        st.markdown('<div class="lc-card">', unsafe_allow_html=True)

        query_state = st.session_state.get("addr_query", "")
        suggestions = []
        if len(query_state.strip()) >= 3:
            suggestions = get_address_suggestions(query_state)

        addr_block = ui.render_address_block(suggestions)

        if st.button("Analyser le bâtiment", type="primary"):
            selected = addr_block["selected_obj"]
            if not selected:
                st.error("Sélectionnez d’abord une adresse.")
            else:
                lat, lon = selected["lat"], selected["lon"]
                st.session_state.addr_label = selected["label"]
                st.session_state.coords = {"lat": lat, "lon": lon}

                try:
                    st.session_state.osm_ctx = fetch_osm_context(lat, lon)
                except:
                    st.session_state.osm_ctx = {}

                st.session_state.step = 1
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # ---------------------------------------------------
    # ÉTAPE 1 — Dimensions
    # ---------------------------------------------------
    if step == 1:
        addr_label = st.session_state.addr_label
        coords = st.session_state.coords

        if not coords:
            st.session_state.step = 0
            st.rerun()

        lat, lon = coords["lat"], coords["lon"]
        osm_ctx = st.session_state.osm_ctx

        # Street View
        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        iframe = build_streetview_embed_url(lat, lon, google_api_key)
        ui.render_streetview(lat, lon, iframe)
        st.markdown('</div>', unsafe_allow_html=True)

        # Formulaire
        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        dims = ui.render_building_dimensions_form(osm_ctx)

        col_next, col_back = st.columns([1, 1])
        with col_next:
            if st.button("Étape suivante : État de la façade", type="primary"):
                st.session_state.building_dims = dims
                st.session_state.step = 2
                st.rerun()

        with col_back:
            if st.button("Retour"):
                st.session_state.step = 0
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # ---------------------------------------------------
    # ÉTAPE 2 — État façade
    # ---------------------------------------------------
    if step == 2:
        if not st.session_state.building_dims:
            st.session_state.step = 1
            st.rerun()

        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        facade_state = ui.render_facade_state_form()

        col_next, col_back = st.columns([1, 1])
        with col_next:
            if st.button("Étape suivante : Détails & urgence", type="primary"):
                st.session_state.facade_state = facade_state
                st.session_state.step = 3
                st.rerun()
        with col_back:
            if st.button("Retour"):
                st.session_state.step = 1
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # ---------------------------------------------------
    # ÉTAPE 3 — Points singuliers + urgence
    # ---------------------------------------------------
    if step == 3:
        dims = st.session_state.building_dims
        facade_state = st.session_state.facade_state
        osm_ctx = st.session_state.osm_ctx

        if not dims or not facade_state:
            st.session_state.step = 1
            st.rerun()

        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        col_l, col_r = st.columns([1.2, 1])

        with col_l:
            points = ui.render_points_singuliers_form(osm_ctx, dims)

        with col_r:
            urgency = ui.render_urgency_form()

        col_next, col_back = st.columns([1, 1])
        with col_next:
            if st.button("Étape suivante : Coordonnées", type="primary"):
                st.session_state.points_form = points
                st.session_state.urgency = urgency
                st.session_state.step = 4
                st.rerun()
        with col_back:
            if st.button("Retour"):
                st.session_state.step = 2
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # ---------------------------------------------------
    # ÉTAPE 4 — Coordonnées + Calcul + Rapport
    # ---------------------------------------------------
    if step == 4:
        dims = st.session_state.building_dims
        facade_state = st.session_state.facade_state
        points_form = st.session_state.points_form
        addr_label = st.session_state.addr_label
        urgency = st.session_state.urgency

        if not (dims and facade_state and points_form):
            st.session_state.step = 1
            st.rerun()

        # Formulaire coordonnées
        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        contact = ui.render_contact_form()
        st.markdown('</div>', unsafe_allow_html=True)

        if contact["submitted"]:
            st.session_state.contact = contact

            # --- Géométrie ---
            niveaux = dims["niveaux"]
            hpn = dims["hauteur_par_niveau"]
            largeur = dims["largeur"]

            hauteur = niveaux * hpn
            nb_facades = 4 if dims["building_type"] == "PAVILLON" else 1
            perimetre = largeur * nb_facades
            surface = hauteur * perimetre

            geom = Geometry(
                hauteur=hauteur,
                surface_facades=surface,
                perimetre=perimetre,
                nb_facades=nb_facades,
            )

            st.session_state.last_geom = geom

            options = points_form.copy()
            options["porte_entree"] = facade_state["porte_type"] == "Porte d’entrée"
            options["porte_cochere"] = facade_state["porte_type"] == "Porte cochère"

            lignes, total = build_pricing(
                geom,
                dims["support_key"],
                options,
                facade_state["etat_facade"],
            )

            st.session_state.lignes = lignes
            st.session_state.total = total

            # Envoi du mail
            send_notification_email(
                to_email="contact@libertsas.fr",
                prospect_email=contact["email"],
                prospect_nom=contact["nom"],
                addr_label=addr_label,
                geom=geom,
                total=total,
                urgency=urgency,
            )

        # --- RAPPORT ---
        if st.session_state.lignes:
            st.markdown('<div class="lc-card">', unsafe_allow_html=True)
            ui.render_rapport(
                addr_label,
                st.session_state.last_geom,
                st.session_state.lignes,
                st.session_state.total,
                st.session_state.urgency,
            )
            st.markdown('</div>', unsafe_allow_html=True)

        # Boutons
        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Modifier les étapes précédentes"):
                st.session_state.step = 3
                st.rerun()

        with col2:
            if st.button("Nouvelle estimation"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)



if __name__ == "__main__":
    main()
