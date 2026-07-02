from bs4 import BeautifulSoup
import requests
from datetime import datetime
def correct_score(fixture_date =datetime.now().strftime('%A'), status=True):
    
    url = f"https://onemillionpredictions.com/{fixture_date}-football-predictions/correct-score/"
    html =requests.get(url).text
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
                
    return data