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
    ["h4", "span", "img"]
):
    tag.decompose()


# ============================================================
# EXTRACT MATCHES
# ============================================================

matches = []

for a in soup.select(
    "a.fin, a.sched, a.live"
):

    teams = a.previous_sibling

    if not teams:
        continue

    teams = teams.strip()

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
