from bs4 import BeautifulSoup
import re
from typing import List, Dict


def get_paa_results(soup: BeautifulSoup) -> List[Dict]:
    """
    Estrae la sezione "People Also Ask" (domande correlate) dalla SERP di Google.
    - soup: oggetto BeautifulSoup della pagina.
    Restituisce una lista di dict con chiavi: Keyword, Position, Question.
    Se non trova il container, restituisce lista vuota.
    """
    # Trova il container PAA
    html_paa = soup.find("div", jsname="Cpkphb")
    if html_paa is None:
        return []

    results = []
    position = 1
    # I singoli items delle domande hanno classe 'cbphWd'
    for q in html_paa.find_all("div", class_="cbphWd"):
        text = q.get_text(strip=True)
        if not text:
            continue
        # Estrai keyword dal <title>
        full_title = soup.title.get_text()
        keyword = full_title.split(" - ")[0].strip()
        results.append({
            "Keyword": keyword,
            "Position": position,
            "Question": text
        })
        position += 1

    return results
