import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0"
})
def correct_score(fixture_date =datetime.now().strftime('%A')):
    
    url = f"https://onemillionpredictions.com/{fixture_date}-football-predictions/correct-score/"
    html =session.get(url).text
    soup =BeautifulSoup(html,"html.parser")
    tables = soup.find_all("tbody")
    data = []
    for table in tables:
        trs = table.find_all("tr", attrs={"data-row_id": True})
        for tr in trs:
            rightArea =tr.find("p",class_="fulldatetime")
            if rightArea:
                # then get the tds
                tds =tr.find_all("td")
                
                teamNames =list(tds[1].stripped_strings)
                homeTeam =teamNames[0]
                awayTeam =teamNames[1]

                
                correct_scores =tds[2].text.strip()
                
                data.append({
                    "homeTeam":homeTeam,
                    "awayTeam":awayTeam,
                    "correct_score":correct_scores
                    
                })
    date = datetime.now().strftime("%a_%d_%b")
    with open(f"{date}_onemillion.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
                
   
def statarea():
    url ="https://www.statarea.com/predictions"
    html =session.get(url).text
    soup =BeautifulSoup(html, "html.parser")


    match_rows =soup.find_all("div",class_="match")
    date_ =soup.find("div",class_="datacotainerheader").text.strip().split(" ")
    date =date_[-1]
    data =[]
    if match_rows:
        for match in match_rows:
            if match.find("div",class_="matchrow"):
                time =match.find("div", class_="date").text.strip()
                if time:
                    teamNames =match.find_all("div", class_="name")
                    homeTeam =teamNames[0].text.strip()
                    awayTeam =teamNames[1].text.strip()
                
                    tip =match.find("div",class_="tip").find('div',class_='value').text.strip()
            detailsRow =match.find("div",class_="inforow")
            if detailsRow:
                cols =detailsRow.select("div.coefbox:has(div.value)")

                if cols:
                    
                    over_2_5 =int(cols[7].text.strip())
                    under_2_5 =100-over_2_5
                    
                    btts =int(cols[9].text.strip())
                    noBtts=int(cols[10].text.strip())
                    # calculate over and unders
                    over_under_prediction ="over" if over_2_5 >under_2_5  else "under"
                    btts_prediction ="Yes" if btts >noBtts else "No"
                    data.append(
                        {"homeTeam":homeTeam,
                        "awayTeam":awayTeam,
                        "tip":tip,
                        "over_under":over_under_prediction,
                        "btts":btts_prediction}
                    )
    date = datetime.now().strftime("%a_%d_%b")
    with open(f"{date}_statarea.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    
    

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
            response = session.get(url, headers=headers, timeout=30)

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
    date = datetime.now().strftime("%a_%d_%b")
    # Save to file (equivalent to SharedPreferences)
    with open(f"{date}_mybets.json", "w", encoding="utf-8") as f:
        json.dump(data_, f, indent=4, ensure_ascii=False)
    
statarea()
mybets()
correct_score()
