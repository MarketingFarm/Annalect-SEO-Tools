from bs4 import BeautifulSoup
from typing import List, Dict


def get_paa_results(soup: BeautifulSoup) -> List[Dict]:
    """
    Estrae la sezione "People Also Ask" (domande correlate) dalla SERP di Google.
    - Cerca prima il container jsname="Cpkphb"
    - Fallback su div[role="heading"][aria-level="3"]
    Restituisce lista di dict con chiavi: Keyword, Position, Question.
    Se il container non esiste, restituisce lista vuota.
    """
    # Fallback sui possibili container delle PAA
    html_paa = (
        soup.find("div", jsname="Cpkphb")
        or soup.find("div", {"role": "heading", "aria-level": "3"})
    )
    if html_paa is None:
        return []

    results = []
    position = 1
    # Ogni domanda ha classe "cbphWd"
    for q in html_paa.find_all("div", class_="cbphWd"):
        text = q.get_text(strip=True)
        if not text:
            continue
        # Estraggo la keyword dal <title> della pagina
        full_title = soup.title.get_text()
        keyword = full_title.split(" - ")[0].strip()
        results.append({
            "Keyword":  keyword,
            "Position": position,
            "Question": text
        })
        position += 1

    return results
