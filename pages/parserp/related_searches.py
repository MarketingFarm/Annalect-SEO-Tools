from bs4 import BeautifulSoup
import re
from typing import List, Dict


def get_related_searches(soup: BeautifulSoup) -> List[Dict]:
    """
    Estrae le ricerche correlate dalla parte bassa della SERP di Google.
    - soup: oggetto BeautifulSoup della pagina.
    Restituisce una lista di dict con chiavi: Keyword, Query, Link.
    Se il container non esiste, restituisce lista vuota.
    """
    # Trova il container principale delle correlazioni
    html_bot = soup.find("div", id="botstuff")
    if html_bot is None:
        return []

    # Se esiste una sezione "card-section" all'interno
    card = html_bot.find("div", class_="card-section") or html_bot

    # Rimuovi blocchi non pertinenti, se presenti
    for cls in ("mnr-c", "lgJJud"):
        bad = card.find("div", class_=cls)
        if bad:
            bad.decompose()

    results = []
    # Cicla sui link
    for a in card.find_all("a", href=True):
        text = a.get_text(strip=True)
        text = re.sub(r"\s+", " ", text)
        if not text:
            continue

        # Keyword dal <title>
        full_title = soup.title.get_text()
        keyword = full_title.split(" - ")[0].strip()

        results.append({
            "Keyword": keyword,
            "Query": text,
            "Link": a["href"]
        })

    return results
