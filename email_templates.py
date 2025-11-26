def html_mail_prospect(
    prospect_nom: str,
    prospect_email: str,
    telephone: str,
    note: str,
    addr_label: str,
    hauteur: float,
    surface: float,
    delai_mois: int,
    urgent: bool,
    total: float,
    logo_url: str | None = None,
):
    """Retourne un HTML premium pour le prospect, avec logo si fourni."""

    urgent_txt = "Oui" if urgent else "Non"
    telephone_txt = telephone if telephone else "-"
    note_txt = note if note else "-"

    # Bloc logo conditionnel
    if logo_url:
        logo_block = f"""
        <tr>
          <td style="padding:16px 22px 4px;">
            <img src="{logo_url}"
                 alt="Libert &amp; Cie"
                 style="height:40px;border-radius:8px;display:block;margin-bottom:6px;object-fit:contain;" />
          </td>
        </tr>
        """
    else:
        logo_block = ""

    return f"""
<!DOCTYPE html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <title>Votre estimation de ravalement – Libert &amp; Cie</title>
  </head>
  <body style="margin:0;padding:0;background-color:#f5f2ee;font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;">
    <table role="presentation" width="100%" style="background-color:#f5f2ee;padding:24px 8px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" style="max-width:620px;background-color:#ffffff;border-radius:16px;border:1px solid #e5e0d8;box-shadow:0 8px 22px rgba(0,0,0,0.06);overflow:hidden;">

            {logo_block}

            <tr>
              <td style="padding:12px 22px 6px;">
                <div style="font-size:14px;color:#6b7280;margin-bottom:6px;">
                  <span style="font-weight:700;color:#1e2a3b;">Libert &amp; Cie</span><br />
                  <span>Peinture &amp; Ravalement – Paris</span>
                </div>
                <h1 style="margin:0;font-size:20px;color:#1e2a3b;">Votre estimation de ravalement</h1>
              </td>
            </tr>

            <tr>
              <td style="padding:0 22px 12px;font-size:14px;color:#374151;">
                <p>Bonjour {prospect_nom},</p>
                <p>Merci pour votre demande d’estimation de ravalement.</p>
                <p>Voici un récapitulatif :</p>
              </td>
            </tr>

            <tr>
              <td style="padding:0 22px;">
                <div style="border-radius:12px;border:1px solid #e5e7eb;padding:10px 12px;background-color:#f9fafb;margin-bottom:10px;">
                  <p style="margin:0 0 4px;font-weight:600;color:#111827;">Adresse du bâtiment</p>
                  <p style="margin:0;color:#374151;">{addr_label}</p>
                </div>

                <div style="border-radius:12px;border:1px solid #e5e7eb;padding:10px 12px;background-color:#f9fafb;margin-bottom:10px;">
                  <p style="margin:0 0 4px;font-weight:600;color:#111827;">Caractéristiques estimées</p>
                  <p style="margin:0;color:#374151;">
                    • Hauteur : {hauteur:.1f} m<br />
                    • Surface de façades : {surface:.1f} m²
                  </p>
                </div>

                <div style="border-radius:12px;border:1px solid #e5e7eb;padding:10px 12px;background-color:#f9fafb;margin-bottom:10px;">
                  <p style="margin:0 0 4px;font-weight:600;color:#111827;">Vos préférences</p>
                  <p style="margin:0;color:#374151;">
                    • Délai souhaité : {delai_mois} mois<br />
                    • Urgent (≤ 3 mois) : {urgent_txt}
                  </p>
                </div>

                <div style="border-radius:12px;border:1px solid #e5e7eb;padding:10px 12px;background-color:#f9fafb;">
                  <p style="margin:0 0 4px;font-weight:600;color:#111827;">Vos coordonnées</p>
                  <p style="margin:0;color:#374151;">
                    • Nom : {prospect_nom}<br />
                    • Email : {prospect_email}<br />
                    • Téléphone : {telephone_txt}<br />
                    • Précisions : {note_txt}
                  </p>
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:14px 22px;">
                <div style="border-radius:14px;background:linear-gradient(135deg,#f97316,#c56a3a);padding:14px;color:white;">
                  <p style="margin:0;font-size:13px;">Montant indicatif (HT)</p>
                  <p style="margin:4px 0 0;font-size:20px;font-weight:700;">{total:,.2f} €</p>
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:0 22px 16px;font-size:13px;color:#4b5563;">
                <p>
                  Cette estimation est une première approche. Une visite sur place permettra
                  de valider le périmètre et d’établir un devis précis.
                </p>
                <p>
                  Nous revenons vers vous très prochainement.
                </p>
                <p>Cordialement,<br><br>
                  <strong>Libert &amp; Cie</strong><br />
                  contact@libertsas.fr<br />
                  15 rue Brézin, 75014 Paris
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def text_mail_prospect(
    prospect_nom: str,
    prospect_email: str,
    telephone: str,
    note: str,
    addr_label: str,
    hauteur: float,
    surface: float,
    delai_mois: int,
    urgent: bool,
    total: float,
):
    """Version texte brut (fallback)."""

    urgent_txt = "Oui" if urgent else "Non"

    return f"""
Bonjour {prospect_nom},

Merci pour votre demande d’estimation de ravalement.

Adresse :
- {addr_label}

Caractéristiques :
- Hauteur : {hauteur:.1f} m
- Surface : {surface:.1f} m²

Préférences :
- Délai souhaité : {delai_mois} mois
- Urgent (≤3 mois) : {urgent_txt}

Vos coordonnées :
- Email : {prospect_email}
- Téléphone : {telephone or "-"}
- Précisions : {note or "-"}

Montant estimatif :
- {total:,.2f} € HT

Une visite sur place est nécessaire pour confirmer l’estimation.

Libert & Cie
contact@libertsas.fr
15 rue Brézin, 75014 Paris
"""
