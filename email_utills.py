# email_utils.py
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Dict, Optional


def build_prospect_email_html(contact: Dict, addr_label: str, total_ht: float) -> str:
    nom = contact.get("nom") or "Madame, Monsieur"
    email = contact.get("email") or ""
    delai_mois = contact.get("delai_mois")
    urgent_txt = "Oui" if contact.get("urgent") else "Non"
    total_txt = f"{total_ht:,.2f} € HT".replace(",", " ").replace(".", ",")

    return f"""
<!DOCTYPE html>
<html lang="fr">
  <body style="font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background-color:#f5f5f7; padding:24px;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:640px; margin:0 auto; background-color:#ffffff; border-radius:18px; overflow:hidden;">
      <tr>
        <td style="background-color:#0B2239; padding:18px 24px; color:#ffffff;">
          <div style="font-size:20px; font-weight:600;">Libert &amp; Cie</div>
          <div style="font-size:13px; opacity:0.9;">Estimation de ravalement</div>
        </td>
      </tr>
      <tr>
        <td style="padding:24px;">
          <p>Bonjour {nom},</p>
          <p>Merci pour votre demande d’estimation de ravalement.</p>

          <p style="margin-top:16px; margin-bottom:4px; font-weight:600;">Récapitulatif :</p>
          <ul style="padding-left:18px; margin-top:4px; margin-bottom:16px; font-size:14px;">
            <li><b>Adresse :</b> {addr_label}</li>
            <li><b>Adresse e-mail :</b> {email}</li>
            <li><b>Délai souhaité avant travaux :</b> {delai_mois} mois</li>
            <li><b>Caractère urgent (≤ 3 mois) :</b> {urgent_txt}</li>
          </ul>

          <p style="margin-top:16px; font-weight:600;">Montant estimatif indicatif :</p>
          <p style="font-size:18px; font-weight:700; color:#0B2239; margin-top:4px; margin-bottom:16px;">
            {total_txt}
          </p>

          <p style="font-size:14px; line-height:1.5;">
            Cette estimation reste indicative et devra être confirmée après visite sur place.
            Nous vous contacterons pour échanger sur votre projet et ajuster la proposition si besoin.
          </p>

          <p style="margin-top:18px; font-size:14px;">
            Vous trouverez en pièce jointe un document PDF reprenant les informations clés et le détail des postes.
          </p>

          <p style="margin-top:24px; margin-bottom:4px;">Bien cordialement,</p>
          <p style="margin-top:0;">
            <b>Libert &amp; Cie</b><br/>
            15 rue Brézin, 75014 Paris<br/>
            contact@libertsas.fr – 01 40 44 69 44
          </p>
        </td>
      </tr>
    </table>
  </body>
</html>
    """


def send_estimation_email(
    smtp_conf: Dict,
    contact: Dict,
    addr_label: str,
    total_ht: float,
    pdf_bytes: Optional[bytes],
) -> None:
    """Envoi au prospect + copie contact@libertsas.fr."""
    to_email = contact.get("email")
    if not to_email:
        return

    from_email = smtp_conf["user"]
    copy_email = "contact@libertsas.fr"

    msg = MIMEMultipart()
    msg["Subject"] = "Votre estimation de ravalement – Libert & Cie"
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Cc"] = copy_email

    html = build_prospect_email_html(contact, addr_label, total_ht)
    msg.attach(MIMEText(html, "html", "utf-8"))

    if pdf_bytes:
        part = MIMEApplication(pdf_bytes, _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename="Estimation_Libert.pdf")
        msg.attach(part)

    recipients = [to_email, copy_email]

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_conf["host"], smtp_conf["port"]) as server:
        if smtp_conf.get("use_tls", True):
            server.starttls(context=context)
        server.login(smtp_conf["user"], smtp_conf["password"])
        server.sendmail(from_email, recipients, msg.as_string())
