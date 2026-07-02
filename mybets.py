import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime

def mybets():
    date = datetime.now().strftime("%a %d/%m")

    urls = {
        "fulltime": "https://www.mybets.today/soccer-predictions/",
        "over_under": "https://www.mybets.today/soccer-predictions/under-over-2-5-goals-predictions/",
        "btts": "https://www.mybets.today/soccer-predictions/both-teams-to-score-predictions/",
        "dc": "https://www.mybets.today/soccer-predictions/double-chance-predictions/",
        "ht_ft": "https://www.mybets.today/soccer-predictions/ht-ft-predictions/",
        "correct_s": "https://www.mybets.today/soccer-predictions/correct-score-predictions/",
        "handicap": "https://www.mybets.today/soccer-predictions/asian-handicap-predictions/",
        "corners": "https://www.mybets.today/soccer-predictions/corners-predictions/",
    }

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    data = []

    for prediction_type, url in urls.items():
        try:
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")

                matches = soup.select(".linkgames")

                for match in matches:
                    home_team = match.select_one(".homeTeam")
                    away_team = match.select_one(".awayTeam")
                    time_div = match.select_one(".timediv")
                    tip_div = match.select_one(".tipdiv")

                    data.append({
                        "homeTeam": home_team.get_text(strip=True) if home_team else "",
                        "awayTeam": away_team.get_text(strip=True) if away_team else "",
                        "time": f"{date} {time_div.get_text(strip=True) if time_div else ''}",
                        "tip": tip_div.get_text(strip=True) if tip_div else "",
                        "type": prediction_type
                    })

            else:
                print(f"{prediction_type}: HTTP {response.status_code}")

        except Exception as e:
            print(f"{prediction_type}: Error fetching data: {e}")

    data_ = {}

    for match in data:
        key = f"{match['homeTeam']} vs {match['awayTeam']}"

        if key not in data_:
            data_[key] = {
                "homeTeam": match["homeTeam"],
                "awayTeam": match["awayTeam"],
                "date": match["time"],
                "predictions": {}
            }

        data_[key]["predictions"][match["type"]] = match["tip"]

    # Save to file (equivalent to SharedPreferences)
    with open("mybets.json", "w", encoding="utf-8") as f:
        json.dump(data_, f, indent=4, ensure_ascii=False)

    print(f"Saved {len(data_)} matches")

    return data_


print(mybets())