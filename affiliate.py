"""Affiliate-link configuration.

Turn outbound links (Fiverr, Amazon, etc.) into affiliate links that earn a
commission, without touching any templates. After you sign up for a program,
paste the tracking query string it gives you into AFFILIATE_QS below. Every
matching outbound link on the site then becomes an affiliate link automatically.

Leave a value empty ("") and links to that domain stay exactly as they are, so
nothing is misrepresented until you've actually joined the program.

Examples once you have them (replace with YOUR real values):
    "amazon.com": "tag=yourtag-20"          # Amazon Associates tracking id
    "fiverr.com": "afp=1234567"             # Fiverr affiliate id
"""
from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl

# Fill these in after joining each program. Empty = leave links untouched.
AFFILIATE_QS = {
    "fiverr.com": "",
    "amazon.com": "",
    "kwork.com": "",
    "upwork.com": "",
    "protalentshub.com": "",  # your own platform; usually no tag needed
}


def enabled() -> bool:
    """True once at least one affiliate program is configured, so the site can
    show the required affiliate disclosure only when it actually applies."""
    return any(v.strip() for v in AFFILIATE_QS.values())


def _host(netloc: str) -> str:
    host = (netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def apply(url: str) -> str:
    """Append the configured tracking query string for a URL's domain. Returns
    the URL unchanged when the domain has no affiliate config."""
    if not url or "://" not in url:
        return url
    try:
        parts = urlparse(url)
    except ValueError:
        return url
    host = _host(parts.netloc)
    extra = ""
    for domain, qs in AFFILIATE_QS.items():
        if qs.strip() and (host == domain or host.endswith("." + domain)):
            extra = qs.strip()
            break
    if not extra:
        return url
    merged = dict(parse_qsl(parts.query))
    merged.update(dict(parse_qsl(extra)))
    return urlunparse(parts._replace(query=urlencode(merged)))
