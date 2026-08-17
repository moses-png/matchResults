import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json


# ============================================================
# GET YESTERDAY'S MATCH RESULTS
# ============================================================

html = requests.get(
    "https://www.livescore.cz/?d=-1",
    timeout=30
)

html.raise_for_status()

soup = BeautifulSoup(
    html.text,
    "html.parser"
)


# ============================================================
# REMOVE UNNECESSARY TAGS
# ============================================================

for tag in soup.find_all(
    ["h4", "span"]
):
    tag.decompose()


# ============================================================
# EXTRACT MATCHES
# ============================================================

matches = []

for a in soup.select(
    "a.fin, a.sched, a.live"
):

    # Walk backwards through the siblings, collecting every
    # text fragment we pass, and skipping over any tags
    # (like <img> logos/cards) that may sit between fragments.
    #
    # This matters because the "home - away" text is sometimes
    # split into TWO separate text nodes with an <img> in
    # between, e.g.:
    #   "Sevilla" <img> " - Rayo Vallecano " <a>...</a>
    # A naive single-sibling lookup only grabs one half of
    # that and silently produces a broken/empty team name.
    #
    # We stop at a <br> (match boundary) or another <a> tag
    # (previous match's result link) so we never bleed into
    # the previous match's text.
    parts_text = []
    sib = a.previous_sibling

    while sib is not None:
        if getattr(sib, "name", None) in ("br", "a"):
            break
        if isinstance(sib, str):
            parts_text.append(sib)
        sib = sib.previous_sibling

    teams = "".join(reversed(parts_text)).strip()

    if " - " not in teams:
        continue

    home_team, away_team = teams.split(
        " - ",
        1
    )

    href = a.get(
        "href",
        ""
    )

    parts = href.split("/")

    match_id = (
        parts[2]
        if len(parts) > 2
        else None
    )

    matches.append({
        "match_id": match_id,
        "home_team": home_team,
        "away_team": away_team,
        "result": a.get_text(
            strip=True
        )
    })


# ============================================================
# UGANDA DATE
# ============================================================

uganda_now = datetime.now(
    ZoneInfo("Africa/Kampala")
)

# Since ?d=-1 is yesterday,
# save the file using yesterday's date.

yesterday = (
    uganda_now
    - timedelta(days=1)
)

date = yesterday.strftime(
    "%a_%d_%b"
)


# ============================================================
# SAVE JSON
# ============================================================

filename = f"{date}.json"

with open(
    filename,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        matches,
        f,
        indent=4,
        ensure_ascii=False
    )

