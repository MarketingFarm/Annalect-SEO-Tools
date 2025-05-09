# pages/parserp/organic_results.py

from bs4 import BeautifulSoup
import re

def get_organic_results(soup: BeautifulSoup, n: int = None) -> list[dict]:
    """
    Estrae i primi risultati organici dalla SERP di Google.
    - soup: oggetto BeautifulSoup della pagina.
    - n: numero massimo di risultati (default None = tutti).
    Restituisce una lista di dict con chiavi:
    Keyword, Position, Titles, Links
    """

    # Trova il contenitore principale
    html_rso = soup.find("div", id="rso")
    if html_rso is None:
        return []

    # Rimuovi blocchi non organici
    for cls in ("kno-kp", "mnr-c", "ULSxyf", "mod"):
        dup = html_rso.find("div", class_=cls)
        if dup:
            dup.decompose()

    results = []
    position = 1

    # Cicla sui blocchi 'g'
    for block in html_rso.find_all("div", class_="g"):
        h3 = block.find("h3")
        if not h3:
            continue

        # Titolo pulito
        title = h3.get_text(strip=True)
        title = re.sub(r"\s+", " ", title)

        # URL (primo <a> con href valido)
        a = block.find("a", href=True)
        href = a["href"] if a and a["href"].startswith("http") else None
        if not href:
            continue

        # Keyword estratta dal <title>
        full_title = soup.title.get_text()
        keyword = full_title.split("-")[0].strip()

        results.append({
            "Keyword": keyword,
            "Position": position,
            "Titles": title,
            "Links": href
        })
        position += 1
        if n and position > n:
            break

    return results
