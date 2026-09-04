"""Optional integrations for publishable deck HTML."""

from typing import Optional

from .errors import DeckToolError
from .project import normalize_google_analytics_id


def google_analytics_fragment(measurement_id: Optional[str]) -> str:
    """Build the Google tag for a validated GA4 measurement ID."""
    measurement_id = normalize_google_analytics_id(measurement_id)
    if measurement_id is None:
        return ""
    return f"""<script async src="https://www.googletagmanager.com/gtag/js?id={measurement_id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{measurement_id}');
</script>"""


def inject_google_analytics(html: str, measurement_id: Optional[str]) -> str:
    """Insert an optional Google tag immediately before the closing head tag."""
    fragment = google_analytics_fragment(measurement_id)
    if not fragment:
        return html
    if "</head>" not in html:
        raise DeckToolError("cannot add analytics: deck template has no </head>")
    return html.replace("</head>", f"{fragment}\n</head>", 1)
