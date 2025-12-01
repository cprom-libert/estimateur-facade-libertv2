import smtplib
from email.message import EmailMessage
from typing import Dict, Optional


def send_estimation_email(
    smtp_conf: Dict,
    contact: Dict,
    addr_label: str,
    total_ttc: float,
    pdf_bytes: Optional[bytes],
) -> None:
    """
    Envoie l'e-mail d'estimation au prospect, avec le PDF en PJ,
    et une copie à contact@libertsas.fr.
    """
    nom = contact.get("nom") or ""
    email = contact.get("email") or ""
    tel = contact.get("tel") or ""
    delai_mois = contact.get("delai_mois")
    urgent = contact.get("urgent", False)

    if not email:
        return

    total_txt = f"{total_ttc:,.0f} € TTC".replace(",", " ").replace(".", ",")

    sujet = "Votre estimation de ravalement – Libert & Cie"
    expediteur = smtp_conf.get("user") or "contact@libertsas.fr"
    destinataires = [email, "contact@libertsas.fr"]

    # Corps HTML
    urgent_txt = "Oui" if urgent else "Non"
    tel_txt = f"<p>Téléphone : {tel}</p>" if tel else ""

    html_body = f"""
    <html>
      <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color:#111827;">
        <div style="max-width:600px;margin:0 auto;padding:24px 16px;">
          <div style="text-align:center;margin-bottom:24px;">
            <img src="https://www.libertsas.fr/wp-content/uploads/2023/04/cropped-logo-libert-1.png"
                 alt="Libert & Cie" style="max-height:60px;">
          </div>
          <h2 style="font-size:20px;margin-bottom:8px;">Bonjour {nom or "Madame, Monsieur"},</h2>
          <p style="font-size:14px;line-height:1.5;">
            Merci pour votre demande d'estimation de ravalement de façade.
          </p>
          <p style="font-size:14px;line-height:1.5;">
            Pour le bâtiment situé au <b>{addr_label}</b>, le montant estimatif des travaux est de&nbsp;:
          </p>
          <p style="font-size:18px;font-weight:700;margin:8px 0 4px 0;">
            {total_txt}
          </p>
          <p style="font-size:12px;color:#6B7280;margin:0 0 16px 0;">
            Ce montant est indicatif et sera affiné après une visite sur place.
          </p>

          <h3 style="font-size:16px;margin-bottom:8px;">Récapitulatif de votre demande</h3>
          <p style="font-size:14px;line-height:1.5;">
            Adresse du chantier : <b>{addr_label}</b><br>
            Délai souhaité avant travaux : <b>{delai_mois} mois</b><br>
            Projet urgent (≤ 3 mois) : <b>{urgent_txt}</b>
          </p>
          {tel_txt}

          <p style="font-size:14px;line-height:1.5;margin-top:16px;">
            Vous trouverez ci-joint un document PDF récapitulant les grandes familles de travaux
            et les postes estimés.
          </p>

          <p style="font-size:14px;line-height:1.5;margin-top:16px;">
            Nous restons à votre disposition pour organiser une visite et établir un devis détaillé.
          </p>

          <p style="font-size:14px;margin-top:24px;">
            Bien cordialement,<br>
            <b>Libert &amp; Cie</b><br>
            15 rue Brézin, 75014 Paris<br>
            contact@libertsas.fr
          </p>
        </div>
      </body>
    </html>
    """

    msg = EmailMessage()
    msg["Subject"] = sujet
    msg["From"] = expediteur
    msg["To"] = ", ".join(destinataires)
    msg.set_content(
        f"Bonjour {nom or 'Madame, Monsieur'},\n\n"
        f"Vous trouverez ci-joint l'estimation de ravalement pour : {addr_label}.\n"
        f"Montant estimatif : {total_txt}.\n\n"
        f"Bien cordialement,\nLibert & Cie"
    )
    msg.add_alternative(html_body, subtype="html")

    # Pièce jointe PDF
    if pdf_bytes:
        msg.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename="Estimation_Libert.pdf",
        )

    host = smtp_conf.get("host")
    port = int(smtp_conf.get("port", 587))
    user = smtp_conf.get("user")
    password = smtp_conf.get("password")
    use_tls = bool(smtp_conf.get("use_tls", True))

    if not host or not user or not password:
        return

    if use_tls:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP_SSL(host, port) as server:
            server.login(user, password)
            server.send_message(msg)
