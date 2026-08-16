import requests
from bs4 import BeautifulSoup, NavigableString
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json


# ============================================================
# GET YESTERDAY'S MATCH RESULTS
# ============================================================

url = "https://www.livescore.cz/?d=-1"

response = requests.get(
    url,
    timeout=30
)

response.raise_for_status()

soup = BeautifulSoup(
    response.text,
    "html.parser"
)


# ============================================================
# REMOVE ONLY UNNECESSARY TAGS
#
# IMPORTANT:
# DO NOT REMOVE <img>
# because some matches have an <img> before their <a>
# ============================================================

for tag in soup.find_all(["h4", "span"]):
    tag.decompose()


# ============================================================
# EXTRACT MATCHES
# ============================================================

matches = []

for a in soup.select("a.fin, a.sched, a.live"):

    teams = None

    # --------------------------------------------------------
    # LOOK BACKWARD THROUGH SIBLINGS
    # --------------------------------------------------------
    #
    # This handles cases such as:
    #
    # "Team A - Team B"
    # <img>
    # <a></a>
    #
    # and also:
    #
    # "Team A - Team B"
    # <a></a>
    #
    # --------------------------------------------------------

    for sibling in reversed(list(a.previous_siblings)):

        # Plain text
        if isinstance(sibling, NavigableString):

            text = sibling.strip()

            if " - " in text:
                teams = text
                break

        # Ignore tags such as img, br, etc.
        else:

            # If this is an img, don't discard the match.
            if sibling.name == "img":
                continue

            # Sometimes the team text can be inside a tag.
            text = sibling.get_text(
                " ",
                strip=True
            )

            if " - " in text:
                teams = text
                break


    # --------------------------------------------------------
    # IF TEAM TEXT WAS NOT FOUND
    # --------------------------------------------------------

    if not teams:
        continue


    # --------------------------------------------------------
    # CLEAN TEAM TEXT
    # --------------------------------------------------------

    teams = " ".join(
        teams.split()
    )


    # --------------------------------------------------------
    # SPLIT HOME / AWAY
    # --------------------------------------------------------

    if " - " not in teams:
        continue

    home_team, away_team = teams.split(
        " - ",
        1
    )

    home_team = home_team.strip()
    away_team = away_team.strip()


    # --------------------------------------------------------
    # GET MATCH URL
    # --------------------------------------------------------

    href = a.get(
        "href",
        ""
    )


    # --------------------------------------------------------
    # GET MATCH ID
    # --------------------------------------------------------

    parts = href.split("/")

    match_id = (
        parts[2]
        if len(parts) > 2
        else None
    )


    # --------------------------------------------------------
    # GET RESULT
    # --------------------------------------------------------

    result = a.get_text(
        strip=True
    )


    # --------------------------------------------------------
    # GET IMAGE INFORMATION IF PRESENT
    # --------------------------------------------------------
    #
    # We don't use the image to ignore anything.
    # This just records whether an image exists.
    #
    # --------------------------------------------------------

    image = a.find_previous("img")

    image_src = None

    if image:
        image_src = image.get(
            "src"
        )


    # --------------------------------------------------------
    # ADD MATCH
    # --------------------------------------------------------

    matches.append({
        "match_id": match_id,
        "home_team": home_team,
        "away_team": away_team,
        "result": result,

    })


# ============================================================
# UGANDA DATE
# ============================================================

uganda_now = datetime.now(
    ZoneInfo("Africa/Kampala")
)


# ?d=-1 means yesterday

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


