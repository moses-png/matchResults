import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json

html = requests.get('m.net')

soup = BeautifulSoup(html.text, "html.parser")

for tag in soup.find_all(["h4", "span", "img"]):
    tag.decompose()

matches = []

for a in soup.select("a.fin, a.sched, a.live"):
    teams = a.previous_sibling

    if not teams:
        continue

    teams = teams.strip()

    if " - " not in teams:
        continue

    home_team, away_team = teams.split(" - ", 1)

    href = a.get("href", "")
    parts = href.split("/")
    match_id = parts[2] if len(parts) > 2 else None

    matches.append({
        "match_id": match_id,
        "home_team": home_team,
        "away_team": away_team,
        "result": a.get_text(strip=True)
    })


dt = datetime.now()
date = dt.strftime('%a_%d_%b')

with open(f"{date}.json", "w", encoding="utf-8") as f:
    json.dump(matches, f, indent=4)