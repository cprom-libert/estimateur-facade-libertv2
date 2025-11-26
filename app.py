import streamlit as st
from typing import Dict, Optional, List
import smtplib
from io import BytesIO
from email.message import EmailMessage

from apis import (
    get_address_suggestions,
    fetch_osm_context,
    build_streetview_embed_url,
)
from pricing import estimate_geometry, build_pricing, NIVEAU_HAUTEUR, Geometry
import ui
from email_templates import html_mail_prospect, text_mail_prospect


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
        "pdf_bytes": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def inject_global_style():
    dark = st.session_state.get("dark_mode", False)

    if dark:
        bg = "#0f172a"
        primary = "#e5e7eb"
        accent = "#f97316"
        card_bg = "#020617"
        text_muted = "rgba(249,250,251,0.75)"
        border_col = "rgba(148,163,184,0.4)"
    else:
        bg = "#f5f2ee"
        primary = "#1e2a3b"
        accent = "#c56a3a"
        card_bg = "#ffffff"
        text_muted = "rgba(0,0,0,0.60)"
        border_col = "rgba(0,0,0,0.04)"

    st.markdown(
        f"""
        <style>
        :root {{
            --lc-primary:{primary};
            --lc-accent:{accent};
            --lc-bg:{bg};
        }}
        html, body, [class*="css"]  {{
            font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
        }}
        body {{
            background-color: var(--lc-bg);
        }}
        .main .block-container {{
            max-width: 1100px;
            padding-top: 1.0rem;
            padding-bottom: 4rem;
        }}
        .lc-card {{
            background:{card_bg};
            border-radius:18px;
            padding:20px 22px;
            box-shadow:0 12px 30px rgba(0,0,0,0.06);
            border:1px solid {border_col};
            margin-bottom:18px;
        }}
        .lc-chip {{
            display:inline-flex;
            align-items:center;
            padding:4px 12px;
            border-radius:999px;
            background:rgba(197,106,58,0.07);
            font-size:0.8rem;
            color:{text_muted};
            margin-right:6px;
        }}
        .lc-stepper {{
            display:flex;
            gap:10px;
            margin-bottom:20px;
            flex-wrap:wrap;
        }}
        .lc-step {{
            flex:1;
            min-width:120px;
            padding:8px 12px;
            border-radius:999px;
            background:rgba(0,0,0,0.06);
            display:flex;
            align-items:center;
            justify-content:center;
            font-size:0.85rem;
            color:{text_muted};
        }}
        .lc-step.lc-step-active {{
            background:var(--lc-primary);
            color:#ffffff;
            font-weight:600;
        }}
        button[kind="primary"] {{
            border-radius:999px !important;
            padding:0.4rem 1.4rem !important;
            font-weight:500 !important;
            background-color:var(--lc-accent) !important;
            border-color:var(--lc-accent) !important;
            color:#ffffff !important;
        }}

        @media (max-width: 768px) {{
            .main .block-container {{
                padding-left:0.6rem;
                padding-right:0.6rem;
            }}
            .lc-card {{
                padding:16px 14px;
                border-radius:14px;
            }}
            .lc-stepper {{
                flex-direction:column;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------
#              GÉNÉRATION DU PDF (prospect + interne)
# ----------------------------------------------------------------

from io import BytesIO

def generate_pdf_estimation(
    addr_label: str,
    geom: Geometry,
    lignes: list[dict],
    total: float,
    urgency: Dict,
    contact: Dict,
) -> bytes | None:
    """
    Génère un PDF récapitulatif.
    On simplifie au maximum le texte (ASCII simple, pas de caractères spéciaux).
    En cas d'erreur fpdf, on retourne None pour ne pas planter l'app.
    """
    try:
        from fpdf import FPDF, FPDFException
    except ImportError:
        st.info("Module 'fpdf2' non installé : le PDF ne sera pas généré.")
        return None

    # Fonction utilitaire : texte compatible ASCII/latin-1, très simple
    def safe(text: str) -> str:
        if text is None:
            text = ""
        # Remplacements des caractères problématiques
        repl = {
            "–": "-",
            "—": "-",
            "•": "-",
            "²": "2",
            "°": " deg",
            "€": "EUR",
            "’": "'",
            "“": '"',
            "”": '"',
            "«": '"',
            "»": '"',
            "…": "...",
            "é": "e",
            "è": "e",
            "ê": "e",
            "à": "a",
            "ù": "u",
            "ç": "c",
            "ô": "o",
            "î": "i",
        }
        for k, v in repl.items():
            text = text.replace(k, v)
        # On limite à latin-1 pour être sûr
        return text.encode("latin-1", "replace").decode("latin-1")

    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)

        titre = safe("Estimation de ravalement - Libert & Cie")
        pdf.cell(190, 8, titre, ln=1)

        pdf.set_font("Helvetica", "", 11)
        pdf.ln(2)

        # En-tête informations client
        addr_txt = safe(f"Adresse : {addr_label}")
        nom_txt = safe(f"Nom : {contact.get('nom','')}")
        email_txt = safe(f"Email : {contact.get('email','')}")
        tel_val = contact.get("tel")
        tel_txt = safe(f"Telephone : {tel_val}") if tel_val else None

        pdf.multi_cell(190, 6, addr_txt)
        pdf.multi_cell(190, 6, nom_txt)
        pdf.multi_cell(190, 6, email_txt)
        if tel_txt:
            pdf.multi_cell(190, 6, tel_txt)

        pdf.ln(3)
        pdf.multi_cell(190, 6, safe(f"Hauteur estimee : {geom.hauteur:.1f} m"))
        pdf.multi_cell(190, 6, safe(f"Surface de facade : {geom.surface_facades:.1f} m2"))
        pdf.multi_cell(
            190, 6, safe(f"Delai souhaite : {urgency.get('delai_mois', '-') } mois")
        )

        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(190, 7, safe(f"Montant indicatif : {total:.2f} EUR HT"))

        pdf.set_font("Helvetica", "", 10)
        pdf.ln(2)
        pdf.multi_cell(
            190,
            5,
            safe(
                "Cette estimation est donnee a titre indicatif et devra etre confirmee apres visite sur place."
            ),
        )

        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(190, 7, safe("Detail par poste (indicatif)"), ln=1)
        pdf.set_font("Helvetica", "", 9)

        for l in lignes:
            lib = safe(str(l["designation"]))
            q = l["quantite"]
            u = l["unite"]
            m = l["montant"]
            ligne_txt = safe(f"- {lib} : {q} {u} - {m:.2f} EUR HT")
            pdf.multi_cell(190, 5, ligne_txt)

        # Sortie en bytes
        pdf_str = pdf.output(dest="S")
        if isinstance(pdf_str, bytes):
            pdf_bytes = pdf_str
        else:
            pdf_bytes = pdf_str.encode("latin-1", "replace")

        return pdf_bytes

    except FPDFException as e:
        st.warning("Impossible de generer le PDF (limitation technique fpdf). L'estimation reste disponible par email.")
        return None
    except Exception as e:
        st.warning(f"Erreur lors de la generation du PDF : {e}")
        return None



# ----------------------------------------------------------------
#            ENVOI D’EMAIL (HTML + PDF, prospect + interne)
# ----------------------------------------------------------------

def send_notification_email(
    to_email: str,
    prospect_email: str,
    prospect_nom: str,
    addr_label: str,
    geom: Geometry,
    total: float,
    urgency: Dict,
    contact: Dict,
    pdf_bytes: Optional[bytes] = None,
):
    """
    Envoie :
      • un mail HTML premium au prospect (avec logo si LOGO_URL présent),
      • une copie BCC à to_email (ex : contact@libertsas.fr),
      • un mail interne séparé à to_email,
      • attache le PDF d’estimation aux deux mails si disponible.
    """

    host = st.secrets.get("SMTP_HOST")
    port = st.secrets.get("SMTP_PORT")
    user = st.secrets.get("SMTP_USER")
    password = st.secrets.get("SMTP_PASSWORD")
    use_tls = st.secrets.get("SMTP_USE_TLS", True)
    logo_url = st.secrets.get("LOGO_URL", None)

    if not all([host, port, user, password]):
        st.info("Paramètres SMTP incomplets : e-mail non envoyé.")
        return

    telephone = contact.get("tel", "")
    note = contact.get("note", "")

    # -------- MAIL PROSPECT (HTML + texte) --------
    html_prospect = html_mail_prospect(
        prospect_nom=prospect_nom,
        prospect_email=prospect_email,
        telephone=telephone,
        note=note,
        addr_label=addr_label,
        hauteur=geom.hauteur,
        surface=geom.surface_facades,
        delai_mois=urgency["delai_mois"],
        urgent=urgency.get("urgent", False),
        total=total,
        logo_url=logo_url,
    )

    text_prospect = text_mail_prospect(
        prospect_nom=prospect_nom,
        prospect_email=prospect_email,
        telephone=telephone,
        note=note,
        addr_label=addr_label,
        hauteur=geom.hauteur,
        surface=geom.surface_facades,
        delai_mois=urgency["delai_mois"],
        urgent=urgency.get("urgent", False),
        total=total,
    )

    msg_client = EmailMessage()
    msg_client["Subject"] = "Votre estimation de ravalement – Libert & Cie"
    msg_client["From"] = user
    msg_client["To"] = prospect_email
    msg_client["Bcc"] = to_email  # copie silencieuse

    msg_client.set_content(text_prospect)
    msg_client.add_alternative(html_prospect, subtype="html")

    if pdf_bytes is not None:
        msg_client.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename="estimation_ravalement.pdf",
        )

    # -------- MAIL INTERNE --------
    msg_admin = EmailMessage()
    msg_admin["Subject"] = f"[INTERNE] Nouvelle estimation – {addr_label}"
    msg_admin["From"] = user
    msg_admin["To"] = to_email

    admin_txt = f"""
Nouvelle estimation

Nom : {prospect_nom}
Email : {prospect_email}
Tel : {telephone or "-"}

Adresse : {addr_label}
Hauteur : {geom.hauteur:.1f} m
Surface : {geom.surface_facades:.1f} m²

Urgence : {"Oui" if urgency.get("urgent") else "Non"}
Délai : {urgency["delai_mois"]} mois

Total indicatif : {total:,.2f} € HT

Note client :
{note or "-"}
"""
    msg_admin.set_content(admin_txt)

    if pdf_bytes is not None:
        msg_admin.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename="estimation_ravalement.pdf",
        )

    # -------- ENVOI SMTP --------
    try:
        with smtplib.SMTP(host, int(port)) as server:
            if use_tls:
                server.starttls()
            server.login(user, password)
            server.send_message(msg_client)
            server.send_message(msg_admin)

        st.success("Votre estimation vous a été envoyée par e-mail.")
    except Exception as e:
        st.error(f"Erreur lors de l’envoi de l’e-mail : {e}")


# ----------------------------------------------------------------
#                            MAIN
# ----------------------------------------------------------------

def main():
    st.set_page_config(page_title="Estimateur ravalement", layout="wide")
    init_state()

    top_col1, top_col2 = st.columns([4, 1])
    with top_col2:
        dark_default = st.session_state.get("dark_mode", False)
        st.session_state.dark_mode = st.toggle("Mode sombre", value=dark_default)

    inject_global_style()

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
            try:
                suggestions = get_address_suggestions(query_state)
            except Exception as e:
                st.error(f"Erreur de recherche d’adresse : {e}")

        addr_block = ui.render_address_block(suggestions)

        if st.button("Analyser le bâtiment", type="primary"):
            selected = addr_block["selected_obj"]
            if not selected:
                st.error("Sélectionnez d’abord une adresse dans la liste.")
            else:
                lat, lon = selected["lat"], selected["lon"]
                st.session_state.addr_label = selected["label"]
                st.session_state.coords = {"lat": lat, "lon": lon}

                try:
                    st.session_state.osm_ctx = fetch_osm_context(lat, lon)
                except Exception:
                    st.session_state.osm_ctx = {}

                # reset des éléments de calcul
                st.session_state.lignes = []
                st.session_state.total = 0.0
                st.session_state.last_geom = None
                st.session_state.building_dims = None
                st.session_state.facade_state = None
                st.session_state.points_form = None
                st.session_state.urgency = None
                st.session_state.contact = None
                st.session_state.pdf_bytes = None

                st.session_state.step = 1
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # ---------------------------------------------------
    # ÉTAPE 1 — Dimensions
    # ---------------------------------------------------
    if step == 1:
        addr_label = st.session_state.addr_label
        coords = st.session_state.coords

        if not coords or not addr_label:
            st.session_state.step = 0
            st.rerun()

        lat, lon = coords["lat"], coords["lon"]
        osm_ctx = st.session_state.osm_ctx

        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        iframe = build_streetview_embed_url(lat, lon, google_api_key)
        ui.render_streetview(lat, lon, iframe)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        dims = ui.render_building_dimensions_form(osm_ctx)

        col_next, col_back = st.columns([1, 1])
        with col_next:
            if st.button("Étape suivante : état de la façade", type="primary"):
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
            if st.button("Étape suivante : détails & urgence", type="primary"):
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
            if st.button("Étape suivante : coordonnées", type="primary"):
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
    # ÉTAPE 4 — Coordonnées + Calcul + Rapport + PDF + Emails
    # ---------------------------------------------------
    if step == 4:
        dims = st.session_state.building_dims
        facade_state = st.session_state.facade_state
        points_form = st.session_state.points_form
        addr_label = st.session_state.addr_label
        urgency = st.session_state.urgency

        if not (dims and facade_state and points_form and addr_label and urgency):
            st.session_state.step = 1
            st.rerun()

        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        contact = ui.render_contact_form()
        st.markdown('</div>', unsafe_allow_html=True)

        # Calcul + email si formulaire valide
        if contact["submitted"]:
            st.session_state.contact = contact

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
                geom=geom,
                support_key=dims["support_key"],
                options=options,
                facade_state=facade_state["etat_facade"],
            )

            st.session_state.lignes = lignes
            st.session_state.total = total

            pdf_bytes = generate_pdf_estimation(
                addr_label=addr_label,
                geom=geom,
                lignes=lignes,
                total=total,
                urgency=urgency,
                contact=contact,
            )
            st.session_state.pdf_bytes = pdf_bytes

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
                contact=contact,
                pdf_bytes=pdf_bytes,
            )

        # Affichage du rapport + bouton PDF
        if st.session_state.lignes and st.session_state.last_geom is not None:
            st.markdown('<div class="lc-card">', unsafe_allow_html=True)
            ui.render_rapport(
                st.session_state.addr_label,
                st.session_state.last_geom,
                st.session_state.lignes,
                st.session_state.total,
                st.session_state.urgency,
            )

            pdf_bytes = st.session_state.get("pdf_bytes")
            if pdf_bytes is not None:
                st.download_button(
                    label="Télécharger mon estimation en PDF",
                    data=pdf_bytes,
                    file_name="estimation_ravalement.pdf",
                    mime="application/pdf",
                )
            st.markdown('</div>', unsafe_allow_html=True)

        # Boutons bas de page
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
