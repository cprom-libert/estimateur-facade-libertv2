# app.py
import streamlit as st
from typing import Dict, List, Optional

from apis import fetch_osm_context, build_streetview_embed_url
from pricing import Geometry, build_pricing
import ui
from email_utils import send_estimation_email


st.set_page_config(
    page_title="Estimateur ravalement – Libert & Cie",
    layout="wide",
    page_icon="📐",
)

ui.init_css()

GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", None)
SMTP_CONF = {
    "host": st.secrets.get("SMTP_HOST", ""),
    "port": int(st.secrets.get("SMTP_PORT", 587)),
    "user": st.secrets.get("SMTP_USER", ""),
    "password": st.secrets.get("SMTP_PASSWORD", ""),
    "use_tls": True,
}


def init_state() -> None:
    defaults = {
        "step": 0,
        "addr_label": None,
        "coords": None,
        "osm_ctx": None,
        "building_dims": None,
        "facade_state": None,
        "contact": None,
        "zone_choice": "rue",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def generate_pdf_estimation(
    addr_label: str,
    geom: Geometry,
    lignes: List[Dict],
    total: float,
    facade_state: Dict,
    dims: Dict,
    zone_choice: str,
    contact: Dict,
    osm_ctx: Dict,
) -> Optional[bytes]:
    try:
        from fpdf import FPDF
    except ImportError:
        st.info("Module 'fpdf2' non installé : le PDF ne sera pas généré.")
        return None

    def safe(text: str) -> str:
        if text is None:
            text = ""
        repl = {
            "–": "-", "—": "-", "•": "-", "·": "-",
            "²": "2", "³": "3",
            "°": " deg",
            "€": "EUR",
            "’": "'", "‘": "'", "“": '"', "”": '"',
            "«": '"', "»": '"',
            "…": "...",
            "é": "e", "è": "e", "ê": "e", "ë": "e",
            "à": "a", "â": "a",
            "ù": "u", "û": "u",
            "î": "i", "ï": "i",
            "ô": "o", "ö": "o",
            "ç": "c",
        }
        for k, v in repl.items():
            text = text.replace(k, v)
        return text.encode("latin-1", "replace").decode("latin-1")

    def fmt_eur(v: float) -> str:
        return f"{v:,.2f} EUR HT".replace(",", " ").replace(".", ",")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)

    pdf.cell(190, 8, safe("Estimation de ravalement - Libert & Cie"), ln=1)
    pdf.set_font("Helvetica", "", 11)
    pdf.ln(2)

    nom = contact.get("nom") or ""
    email = contact.get("email") or ""
    tel = contact.get("tel") or ""
    delai_mois = contact.get("delai_mois")
    urgent_txt = "Oui" if contact.get("urgent") else "Non"

    pdf.multi_cell(190, 6, safe(f"Adresse du chantier : {addr_label}"))
    if nom:
        pdf.multi_cell(190, 6, safe(f"Contact : {nom}"))
    if email:
        pdf.multi_cell(190, 6, safe(f"E-mail : {email}"))
    if tel:
        pdf.multi_cell(190, 6, safe(f"Téléphone : {tel}"))
    pdf.multi_cell(190, 6, safe(f"Délai souhaité avant travaux : {delai_mois} mois (Urgent : {urgent_txt})"))

    pdf.ln(3)
    pdf.multi_cell(
        190,
        6,
        safe(f"Zone de ravalement estimée : {zone_choice.replace('+', ' + ')}"),
    )
    pdf.multi_cell(190, 6, safe(f"Surface estimée de façades : {geom.surface_facades:.1f} m2"))
    pdf.multi_cell(190, 6, safe(f"Hauteur estimée : {geom.hauteur:.1f} m"))

    etat_facade = facade_state.get("etat_facade", "moyen")
    support_key = facade_state.get("support_key", "").replace("_", " ").title()
    pdf.ln(3)
    pdf.multi_cell(190, 6, safe(f"État de façade renseigné : {etat_facade}"))
    pdf.multi_cell(190, 6, safe(f"Support principal : {support_key}"))

    has_shops = dims.get("has_shops", False)
    shops_config = dims.get("shops_config", "aucune")
    if has_shops:
        mapping = {
            "une_boutique_toute_longueur": "Une boutique presque sur toute la longueur (hors porte/porte cochère)",
            "deux_boutiques": "Deux boutiques principales",
            "autre_configuration": "Configuration mixte boutiques / logements",
        }
        txt_shop = mapping.get(shops_config, shops_config)
        pdf.ln(3)
        pdf.multi_cell(190, 6, safe(f"Boutiques en rez-de-chaussée : {txt_shop}"))

    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(190, 7, safe(f"Montant estimatif indicatif : {fmt_eur(total)}"))
    pdf.set_font("Helvetica", "", 9)
    pdf.ln(2)
    pdf.multi_cell(
        190,
        5,
        safe(
            "Cette estimation reste indicative et devra etre confirmee apres visite sur place "
            "(les autorisations et delais administratifs ne sont pas integres dans le calcul)."
        ),
    )

    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(190, 7, safe("Détail estimatif par grandes familles de postes"), ln=1)
    pdf.set_font("Helvetica", "", 9)

    # Regroupement par familles
    familles_labels = {
        "INSTALLATION": "Installation de chantier",
        "PROTECTION": "Protections",
        "ECHAUFAUDAGE": "Échafaudage",
        "RAVALEMENT": "Travaux de ravalement et maçonneries",
        "ZINGUERIE": "Zinguerie, garde-corps et éléments métalliques",
        "PEINTURE": "Peinture menuiseries / chiens-assis",
        "NETTOYAGE": "Nettoyage et fin de chantier",
    }

    fam_totaux: Dict[str, float] = {k: 0.0 for k in familles_labels.keys()}
    famille_lignes: Dict[str, List[Dict]] = {k: [] for k in familles_labels.keys()}

    for l in lignes:
        fam = l.get("famille", "")
        if fam in fam_totaux:
            montant = float(l.get("montant", 0.0) or 0.0)
            fam_totaux[fam] += montant
            famille_lignes[fam].append(l)

    for fam_code, fam_label in familles_labels.items():
        montant_fam = fam_totaux.get(fam_code, 0.0)
        if montant_fam <= 0:
            continue

        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(190, 6, safe(f"{fam_label} – {fmt_eur(montant_fam)}"))
        pdf.set_font("Helvetica", "", 9)

        for l in famille_lignes[fam_code]:
            q = l["quantite"]
            u = l["unite"]
            m = l["montant"]
            txt = f"- {l['designation']} ({q} {u}) : {m:.2f} EUR HT"
            pdf.multi_cell(190, 4, safe(txt))

    pdf.ln(8)
    pdf.set_font("Helvetica", "", 8)
    pdf.multi_cell(
        190,
        4,
        safe(
            "Document indicatif etabli par Libert & Cie. Il ne vaut pas devis ferme. "
            "Un devis detaille sera remis apres visite sur place."
        ),
    )

    raw = pdf.output(dest="S")
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, bytearray):
        return bytes(raw)
    if isinstance(raw, str):
        return raw.encode("latin-1", "replace")
    try:
        return bytes(raw)
    except Exception:
        return None


def main() -> None:
    init_state()

    st.markdown(
        "<h2 style='margin-bottom:0.5rem; color:#0B2239;'>Estimateur de ravalement – Libert &amp; Cie</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:#555; margin-bottom:1.5rem;'>Un ordre de grandeur indicatif pour votre ravalement, "
        "à confirmer après visite sur place.</p>",
        unsafe_allow_html=True,
    )

    step = st.session_state.step

    # Étape 0 – Adresse
    if step == 0:
        ok = ui.render_address_step()
        if ok:
            coords = st.session_state.coords
            if coords:
                st.session_state.osm_ctx = fetch_osm_context(coords["lat"], coords["lon"])
            st.session_state.step = 1
            st.rerun()
        return

    coords = st.session_state.get("coords")
    if not coords:
        st.session_state.step = 0
        st.rerun()
        return

    # Étape 1 – Dimensions + zone (rue / cour / rue+cour)
    if step == 1:
        osm_ctx = st.session_state.osm_ctx or {}
        dims = ui.render_map_and_form(GOOGLE_API_KEY, ui.render_building_dimensions_form, osm_ctx)
        if dims is None:
            return

        st.markdown('<div class="lc-card">', unsafe_allow_html=True)
        zone_default = "rue+cour" if osm_ctx.get("has_cour") else "rue"
        zone_labels = {
            "rue": "Façade sur rue",
            "cour": "Façade sur cour",
            "rue+cour": "Rue + cour",
        }
        zone_choice = st.radio(
            "Zone de ravalement à inclure dans l’estimation",
            options=["rue", "cour", "rue+cour"],
            index=["rue", "cour", "rue+cour"].index(zone_default),
            format_func=lambda z: zone_labels[z],
        )
        st.markdown("</div>", unsafe_allow_html=True)

        col_next, col_back = st.columns([1, 1])
        with col_next:
            if st.button("Étape suivante : état de la façade", type="primary"):
                st.session_state.building_dims = dims
                st.session_state.zone_choice = zone_choice
                st.session_state.step = 2
                st.rerun()
        with col_back:
            if st.button("Retour"):
                st.session_state.step = 0
                st.rerun()
        return

    # Étape 2 – État / points singuliers
    if step == 2:
        osm_ctx = st.session_state.osm_ctx or {}
        facade_state = ui.render_map_and_form(GOOGLE_API_KEY, ui.render_facade_state_form, osm_ctx)
        if facade_state is None:
            return

        col_next, col_back = st.columns([1, 1])
        with col_next:
            if st.button("Étape suivante : vos coordonnées", type="primary"):
                st.session_state.facade_state = facade_state
                st.session_state.step = 3
                st.rerun()
        with col_back:
            if st.button("Retour"):
                st.session_state.step = 1
                st.rerun()
        return

    # Étape 3 – Coordonnées + déclenchement du calcul
    if step == 3:
        contact = ui.render_map_and_form(GOOGLE_API_KEY, ui.render_contact_form)
        if contact is None:
            return

        disabled = not contact.get("email") or not contact.get("nom")
        if st.button("Calculer l’estimation et recevoir le PDF", type="primary", disabled=disabled):
            st.session_state.contact = contact
            st.session_state.step = 4
            st.rerun()
        if st.button("Retour à l’étape précédente"):
            st.session_state.step = 2
            st.rerun()
        return

    # Étape 4 – Calcul, affichage, email, PDF
    if step == 4:
        coords = st.session_state.coords
        osm_ctx = st.session_state.osm_ctx or {}
        dims = st.session_state.building_dims or {}
        facade_state = st.session_state.facade_state or {}
        contact = st.session_state.contact or {}
        zone_choice = st.session_state.get("zone_choice", "rue")

        niveaux = dims.get("niveaux", 5)
        hpn = dims.get("hauteur_par_niveau", 3.0)
        hauteur = niveaux * hpn

        largeur_rue = dims.get("largeur", 15.0)
        largeur_cour = osm_ctx.get("facade_cour_m") or largeur_rue
        profondeur = dims.get("profondeur") or osm_ctx.get("depth_m") or largeur_rue

        building_type = dims.get("building_type", "IMMEUBLE")
        has_pignon = bool(dims.get("has_pignon", False))

        if building_type == "PAVILLON":
            if zone_choice == "rue":
                perimetre = largeur_rue
                nb_facades = 1
            elif zone_choice == "cour":
                perimetre = largeur_cour
                nb_facades = 1
            else:
                perimetre = 2 * (largeur_rue + profondeur)
                nb_facades = 4
        else:
            if zone_choice == "rue":
                perimetre = largeur_rue + (profondeur if has_pignon else 0)
                nb_facades = 1 + (1 if has_pignon else 0)
            elif zone_choice == "cour":
                perimetre = largeur_cour + (profondeur if has_pignon else 0)
                nb_facades = 1 + (1 if has_pignon else 0)
            else:
                base = largeur_rue + largeur_cour
                perimetre = base + (profondeur if has_pignon else 0)
                nb_facades = 2 + (1 if has_pignon else 0)

        surface = hauteur * perimetre
        geom = Geometry(
            hauteur=float(hauteur),
            surface_facades=float(surface),
            perimetre=float(perimetre),
            nb_facades=int(nb_facades),
        )

        options: Dict = {}
        options["is_haussmann"] = bool(osm_ctx.get("is_haussmann_suspected", False))
        options["niveaux"] = niveaux

        options["nb_fenetres_petites"] = facade_state.get("nb_fenetres_petites", 0)
        options["nb_fenetres_grandes"] = facade_state.get("nb_fenetres_grandes", 0)
        options["traiter_chiens_assis"] = facade_state.get("traiter_chiens_assis", False)
        options["nb_chiens_assis"] = facade_state.get("nb_chiens_assis", 0)

        garde_corps_niveau = facade_state.get("garde_corps_niveau", "moyen")
        if garde_corps_niveau == "peu":
            ml_gc = perimetre * 0.2
        elif garde_corps_niveau == "beaucoup":
            ml_gc = perimetre * 0.8
        else:
            ml_gc = perimetre * 0.5
        options["ml_garde_corps_fer_forge"] = ml_gc

        # Pas d’invention sur les autres points
        options["surface_reprises_lourdes_detectee"] = 0.0
        options["surface_reprises_enduit_detectee"] = 0.0
        options["ml_microfissures"] = 0.0
        options["ml_fissures_ouvertes"] = 0.0
        options["ml_descente_ep"] = 0.0
        options["ml_bandeaux"] = 0.0
        options["ml_zinguerie"] = 0.0
        options["nb_grilles_aeration"] = 0
        options["ml_grillage_protection"] = 0.0
        options["ml_grillage_galva"] = 0.0

        lignes, total_ht = build_pricing(
            geom=geom,
            support_key=facade_state.get("support_key", "ENDUIT_CIMENT"),
            options=options,
            etat_facade=facade_state.get("etat_facade", "moyen"),
        )

        st.success("Estimation calculée (indicative, à confirmer après visite sur place).")

        col_map, col_res = st.columns([1, 1.3])

        with col_map:
            iframe = build_streetview_embed_url(coords["lat"], coords["lon"], GOOGLE_API_KEY)
            st.markdown('<div class="lc-card">', unsafe_allow_html=True)
            st.markdown(f"<b>Adresse :</b><br>{st.session_state.addr_label}", unsafe_allow_html=True)
            st.markdown(
                f'<iframe src="{iframe}" width="100%" height="300" style="border:0;border-radius:14px;" allowfullscreen loading="lazy"></iframe>',
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)

        with col_res:
            st.markdown('<div class="lc-card">', unsafe_allow_html=True)
            total_txt = f"{total_ht:,.2f} € HT".replace(",", " ").replace(".", ",")
            st.markdown("<b>Montant estimatif indicatif :</b>", unsafe_allow_html=True)
            st.markdown(
                f"<p style='font-size:1.4rem; font-weight:700; color:#0B2239;'>{total_txt}</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<p style='font-size:0.9rem; color:#555;'>Ce montant reste indicatif et devra être confirmé après visite sur place.</p>",
                unsafe_allow_html=True,
            )

            st.markdown("<b>Grandes familles de postes :</b>", unsafe_allow_html=True)
            fam_labels = {
                "INSTALLATION": "Installation de chantier",
                "PROTECTION": "Protections",
                "ECHAUFAUDAGE": "Échafaudage",
                "RAVALEMENT": "Ravalement / maçonneries",
                "ZINGUERIE": "Zinguerie / garde-corps",
                "PEINTURE": "Peinture menuiseries / chiens-assis",
                "NETTOYAGE": "Nettoyage / fin de chantier",
            }
            fam_totaux = {k: 0.0 for k in fam_labels.keys()}
            for l in lignes:
                fam = l.get("famille", "")
                if fam in fam_totaux:
                    fam_totaux[fam] += float(l.get("montant", 0.0) or 0.0)

            for code, label in fam_labels.items():
                montant = fam_totaux.get(code, 0.0)
                if montant <= 0:
                    continue
                txt = f"{label} : {montant:,.2f} € HT".replace(",", " ").replace(".", ",")
                st.markdown(f"- {txt}")
            st.markdown("</div>", unsafe_allow_html=True)

        pdf_bytes = generate_pdf_estimation(
            addr_label=st.session_state.addr_label,
            geom=geom,
            lignes=lignes,
            total=total_ht,
            facade_state=facade_state,
            dims=dims,
            zone_choice=zone_choice,
            contact=contact,
            osm_ctx=osm_ctx,
        )

        if SMTP_CONF["host"] and SMTP_CONF["user"] and contact.get("email"):
            try:
                send_estimation_email(
                    smtp_conf=SMTP_CONF,
                    contact=contact,
                    addr_label=st.session_state.addr_label,
                    total_ht=total_ht,
                    pdf_bytes=pdf_bytes,
                )
                st.info("L’estimation a été envoyée par e-mail (copie à contact@libertsas.fr).")
            except Exception as e:
                st.warning(f"Erreur lors de l’envoi de l’e-mail : {e}")
        else:
            st.info("Configuration SMTP incomplète : l’envoi automatique par e-mail n’est pas actif.")

        if pdf_bytes:
            st.download_button(
                "Télécharger le PDF",
                data=pdf_bytes,
                file_name="Estimation_Libert.pdf",
                mime="application/pdf",
                type="secondary",
            )

        if st.button("Faire une nouvelle estimation"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            init_state()
            st.rerun()


if __name__ == "__main__":
    main()
