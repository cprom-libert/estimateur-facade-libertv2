import streamlit as st
from typing import Dict, Optional
import smtplib
from email.message import EmailMessage

from apis import get_address_suggestions, fetch_osm_context, build_streetview_embed_url
from pricing import estimate_geometry, build_pricing, NIVEAU_HAUTEUR, Geometry
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
    if "building_dims" not in st.session_state:
        st.session_state.building_dims = None
    if "facade_state" not in st.session_state:
        st.session_state.facade_state = None
    if "points_form" not in st.session_state:
        st.session_state.points_form = None
    if "urgency" not in st.session_state:
        st.session_state.urgency = None
    if "contact" not in st.session_state:
        st.session_state.contact = None


def inject_global_style():
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


def send_notification_email(
    to_email: str,
    prospect_email: str,
    prospect_nom: str,
    addr_label: str,
    geom: Geometry,
    total: float,
    urgency: Dict,
):
    host = st.secrets.get("SMTP_HOST")
    port = st.secrets.get("SMTP_PORT")
    user = st.secrets.get("SMTP_USER")
    password = st.secrets.get("SMTP_PASSWORD")
    use_tls = st.secrets.get("SMTP_USE_TLS", True)

    if not host or not port or not user or not password:
        st.info(
            "L’estimation a été réalisée. L’envoi automatique d’e-mail n’est pas configuré (paramètres SMTP manquants)."
        )
        return

    msg = EmailMessage()
    msg["Subject"] = f"Nouvelle estimation ravalement – {addr_label}"
    msg["From"] = user
    msg["To"] = to_email

    corps = f"""Nouvelle demande d'estimation ravalement

Adresse : {addr_label}
Nom / société : {prospect_nom or 'Non renseigné'}
Email prospect : {prospect_email}
Hauteur estimée : {geom.hauteur:.1f} m
Surface façades : {geom.surface_facades:.1f} m²
Périmètre développé : {geom.perimetre:.1f} ml
Total estimatif HT : {total:,.2f} €

Délai souhaité avant travaux : {urgency['delai_mois']} mois
Projet urgent (< =3 mois) : {"Oui" if urgency.get("urgent") else "Non"}

Vous pouvez recontacter le prospect pour affiner le projet et proposer une visite.
"""
    msg.set_content(corps)

    try:
        with smtplib.SMTP(host, int(port)) as server:
            if use_tls:
                server.starttls()
            server.login(user, password)
            server.send_message(msg)
        st.success("Votre demande a bien été enregistrée. Nous vous recontacterons rapidement.")
    except Exception as e:
        st.warning(f"Estimation réalisée, mais l’envoi de l’e-mail n’a pas abouti ({e}).")


def main():
    st.set_page_config(page_title="Estimateur ravalement – Paris", layout="wide")
    inject_global_style()
    init_state()

    google_api_key = st.secrets.get("GOOGLE_API_KEY")

    ui.render_title()

    step = st.session_state.step
    ui.render_stepper(step)

    # ÉTAPE 0 : adresse
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

                    # Reset des formulaires
                    st.session_state.lignes = []
                    st.session_state.total = 0.0
                    st.session_state.last_geom = None
                    st.session_state.building_dims = None
                    st.session_state.facade_state = None
                    st.session_state.points_form = None
                    st.session_state.urgency = None
                    st.session_state.contact = None

                    st.session_state.step = 1
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # ÉTAPE 1 : dimensions (type, niveaux, hauteur/niveau, largeur)
    if st.session_state.step == 1:
        addr_label = st.session_state.addr_label
        coords = st.session_state.coords or {}
        osm_ctx = st.session_state.osm_ctx or {}

        if not addr_label or not coords:
            st.session_state.step = 0
            st.rerun()

        # Street View pour aider à valider les dimensions
        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        lat = coords["lat"]
        lon = coords["lon"]
        iframe_url = build_streetview_embed_url(lat, lon, google_api_key)
        ui.render_streetview(lat, lon, iframe_url)
        st.markdown('</div>', unsafe_allow_html=True)

        # Formulaire dimensions
        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        building_dims = ui.render_building_dimensions_form(osm_ctx)

        col_next, col_back = st.columns([1, 1])
        with col_next:
            if st.button("Étape suivante : état de la façade", type="primary"):
                st.session_state.building_dims = building_dims
                st.session_state.step = 2
                st.rerun()
        with col_back:
            if st.button("Revenir à l’adresse"):
                st.session_state.step = 0
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # ÉTAPE 2 : état façade / porte
    if st.session_state.step == 2:
        if not st.session_state.building_dims:
            st.session_state.step = 1
            st.rerun()

        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        facade_state = ui.render_facade_state_form()

        col_next, col_back = st.columns([1, 1])
        with col_next:
            if st.button("Étape suivante : points singuliers & urgence", type="primary"):
                st.session_state.facade_state = facade_state
                st.session_state.step = 3
                st.rerun()
        with col_back:
            if st.button("Étape précédente : dimensions"):
                st.session_state.step = 1
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # ÉTAPE 3 : points singuliers + urgence
    if st.session_state.step == 3:
        if not st.session_state.building_dims or not st.session_state.facade_state:
            st.session_state.step = 1
            st.rerun()

        osm_ctx = st.session_state.osm_ctx or {}
        building_dims = st.session_state.building_dims

        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        col_left, col_right = st.columns([1.2, 1])

        with col_left:
            points_form = ui.render_points_singuliers_form(osm_ctx, building_dims)

        with col_right:
            urgency = ui.render_urgency_form()

        col_next, col_back = st.columns([1, 1])
        with col_next:
            if st.button("Étape suivante : coordonnées", type="primary"):
                st.session_state.points_form = points_form
                st.session_state.urgency = urgency
                st.session_state.step = 4
                st.rerun()
        with col_back:
            if st.button("Étape précédente : état de la façade"):
                st.session_state.step = 2
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # ÉTAPE 4 : coordonnées + calcul + rapport + mail
    if st.session_state.step == 4:
        if not (st.session_state.building_dims and st.session_state.facade_state and st.session_state.points_form):
            st.session_state.step = 1
            st.rerun()

        addr_label = st.session_state.addr_label
        building_dims = st.session_state.building_dims
        facade_state = st.session_state.facade_state
        points_form = st.session_state.points_form
        urgency = st.session_state.urgency or {"delai_mois": 6, "urgent": False}

        # Carte coordonnées
        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        contact = ui.render_contact_form()
        st.markdown('</div>', unsafe_allow_html=True)

        # Quand l’email est valide, on calcule et on envoie la notif
        if contact["submitted"]:
            st.session_state.contact = contact

            # Géométrie (on utilise la hauteur par niveau saisie dans building_dims)
            niveaux = building_dims["niveaux"]
            hauteur_par_niveau = building_dims["hauteur_par_niveau"]
            largeur = building_dims["largeur"]
            building_type = building_dims["building_type"]

            # On reconstruit Geometry en utilisant la hauteur ajustée
            hauteur = max(1, niveaux) * hauteur_par_niveau
            nb_facades = 4 if building_type.upper().startswith("PAVILLON") else 1
            perimetre = largeur * nb_facades
            surface_facades = hauteur * perimetre
            geom = Geometry(
                hauteur=hauteur,
                surface_facades=surface_facades,
                perimetre=perimetre,
                nb_facades=nb_facades,
            )

            porte_type = facade_state["porte_type"]
            options = points_form.copy()
            options["porte_entree"] = porte_type == "Porte d’entrée"
            options["porte_cochere"] = porte_type == "Porte cochère"

            lignes, total = build_pricing(
                geom=geom,
                support_key=building_dims["support_key"],
                options=options,
                facade_state=facade_state["etat_facade"],
            )

            st.session_state.lignes = lignes
            st.session_state.total = total
            st.session_state.last_geom = geom

            # Notification par mail à Libert & Cie
            prospect_email = contact["email"]
            prospect_nom = contact["nom"]
            send_notification_email(
                to_email="contact@libertsas.fr",
                prospect_email=prospect_email,
                prospect_nom=prospect_nom,
                addr_label=addr_label,
                geom=geom,
                total=total,
                urgency=urgency,
            )

        # Carte rapport si calcul déjà fait
        if st.session_state.lignes and st.session_state.last_geom is not None:
            st.markdown('<div class="lc-card">', unsafe_allow_html=True)
            ui.render_rapport(
                st.session_state.addr_label,
                st.session_state.last_geom,
                st.session_state.lignes,
                st.session_state.total,
                st.session_state.urgency,
            )
            st.markdown('</div>', unsafe_allow_html=True)

        # Boutons bas de page
        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        col_back, col_new = st.columns([1, 1])
        with col_back:
            if st.button("Retour étapes précédentes"):
                st.session_state.step = 3
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
                st.session_state.building_dims = None
                st.session_state.facade_state = None
                st.session_state.points_form = None
                st.session_state.urgency = None
                st.session_state.contact = None
                st.session_state.addr_query = ""
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
