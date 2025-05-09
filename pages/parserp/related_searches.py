from bs4 import BeautifulSoup
import re
from typing import List, Dict

def get_related_searches(soup: BeautifulSoup) -> List[Dict]:
    """
    Estrae le ricerche correlate dalla SERP di Google.
    - Prima cerca <div id="botstuff">, altrimenti fallback su <div class="kno-ftr">.
    - Rimuove blocchi non pertinenti.
    Restituisce una lista di dict con chiavi: Keyword, Query, Link.
    """
    # Trova il container principale (botstuff o kno-ftr)
    html_bot = soup.find("div", id="botstuff") or soup.find("div", class_="kno-ftr")
    if html_bot is None:
        return []

    # Se esiste una sotto-sezione card-section, usala; altrimenti usa html_bot
    card = html_bot.find("div", class_="card-section") or html_bot

    # Pulisci eventuali blocchi non pertinenti
    for cls in ("mnr-c", "lgJJud"):
        bad = card.find("div", class_=cls)
        if bad:
            bad.decompose()

    results = []
    # Cicla su ogni link
    for a in card.find_all("a", href=True):
        text = a.get_text(strip=True)
        # Normalizza spazi
        text = re.sub(r"\s+", " ", text)
        if not text:
            continue

        # Keyword estratta dal <title> della pagina
        full_title = soup.title.get_text()
        keyword = full_title.split(" - ")[0].strip()

        results.append({
            "Keyword": keyword,
            "Query": text,
            "Link": a["href"]
        })

    return results
