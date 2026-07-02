from bs4 import BeautifulSoup
import requests
def statarea():
    url ="https://www.statarea.com/predictions"
    html =requests.get(url).text
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
                    

    return data


print(statarea())