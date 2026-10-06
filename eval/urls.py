import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Query parameters that only track where a click came from. Two URLs that differ
# only in these point at the same page.
TRACKING_PARAMS = re.compile(r"^(utm_.+|srsltid|gclid|fbclid|msclkid|mc_cid|mc_eid|ref_src)$")


# Treats URLs that point at the same page as one: scheme, www., case of host,
# trailing slash, fragment and tracking parameters are ignored.
def normalise_url(raw: str) -> str:
    parsed = urlparse(raw)
    host = parsed.netloc.lower().removeprefix("www.")
    query = urlencode([(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if not TRACKING_PARAMS.match(k)])
    path = parsed.path.rstrip("/")
    return urlunparse(("https", host, path, "", query, ""))


def is_well_formed(raw: str) -> bool:
    try:
        parsed = urlparse(raw)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and "." in (parsed.hostname or "")
