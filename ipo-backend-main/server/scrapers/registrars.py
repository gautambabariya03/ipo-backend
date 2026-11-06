"""
Registrar -> official allotment-check page mapping.

Maqsad: CLOSED IPO ka "CHECK ALLOTMENT" button hamesha us IPO ke ASLI registrar
ki official site khole — kabhi BSE/NSE ki generic page nahi.
"""
import re

# (keywords, display name, official allotment page)
REGISTRARS = [
    (("kfintech", "kfin tech", "kfin technologies", "karvy"), "KFintech", "https://ipostatus.kfintech.com/"),
    (("mufg", "link intime", "linkintime", "mpms"), "MUFG Intime (Link Intime)", "https://in.mpms.mufg.com/Initial_Offer/public-issues.html"),
    (("bigshare",), "Bigshare Services", "https://ipo.bigshareonline.com/IPO_Status.html"),
    (("cameo",), "Cameo Corporate Services", "https://ipo.cameoindia.com/"),
    (("skyline",), "Skyline Financial Services", "https://www.skylinerta.com/ipo.php"),
    (("purva",), "Purva Sharegistry", "https://www.purvashare.com/investor-service/ipo-query"),
    (("maashitla",), "Maashitla Management Services", "https://maashitla.com/allotment-status/public-issues"),
    (("integrated registry", "integratedindia"), "Integrated Registry Management", "https://ipo.integratedindia.in/"),
]

# In domains ko kabhi "registrar" nahi maanna (ye exchanges ki generic pages hain)
EXCHANGE_DOMAINS = ("bseindia.com", "nseindia.com")


def is_exchange_url(url):
    return bool(url) and any(d in url.lower() for d in EXCHANGE_DOMAINS)


def identify_registrar(text):
    """Kisi bhi text/URL se registrar pehchano. Returns (display_name, official_url) ya (None, None)."""
    if not text:
        return None, None
    low = str(text).lower()
    if is_exchange_url(low):
        return None, None
    for keywords, name, url in REGISTRARS:
        if any(k in low for k in keywords):
            return name, url
    return None, None


def find_registrar_in_text(page_text):
    """Page text me 'registrar' ke aas-paas ka hissa dekh ke registrar pehchano."""
    if not page_text:
        return None, None
    for m in re.finditer(r"registrar[^\n]{0,160}", page_text, flags=re.IGNORECASE):
        name, url = identify_registrar(m.group(0))
        if name:
            return name, url
    return None, None
