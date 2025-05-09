from bs4 import BeautifulSoup
import re
from typing import List, Dict


def get_organic_results(soup: BeautifulSoup, n: int = None) -> List[Dict]:
    """
    Estrae i primi risultati organici dalla SERP di Google.
    - soup: oggetto BeautifulSoup della pagina.
    - n: numero massimo di risultati (default None = tutti).
    Restituisce una lista di dict con chiavi:
    Keyword, Position, Titles, Links, Snippet
    """
    # Google a volte non espone più #rso, usiamo come fallback #rso e poi #search
    html_rso = soup.find("div", id="rso") or soup.find("div", id="search")
    if html_rso is None:
        return []

    # Rimuovi blocchi non organici (Knowledge Panel, PAA, ecc.)
    for cls in ("kno-kp", "mnr-c", "ULSxyf", "mod"):
        dup = html_rso.find("div", class_=cls)
        if dup:
            dup.decompose()

    results = []
    position = 1

    # Cicla sui blocchi organici identificati da div.g
    for block in html_rso.find_all("div", class_="g"):
        # titolo H3 dentro il link principalemente in div.yuRUbf
        h3 = block.select_one("div.yuRUbf > a > h3")
        if not h3:
            continue

        # link del risultato
        a = block.select_one("div.yuRUbf > a[href^='http']")
        href = a["href"] if a else None
        if not href:
            continue

        # testo del titolo normalizzato
        title = h3.get_text(strip=True)
        title = re.sub(r"\s+", " ", title)

        # snippet (div.IsZvec o div.aCOpRe)
        snippet_tag = block.select_one("div.IsZvec, div.aCOpRe")
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""

        # keyword estratta dal <title> della pagina
        full_title = soup.title.get_text()
        keyword = full_title.split(" - ")[0].strip()

        # aggiungi al risultato
        results.append({
            "Keyword": keyword,
            "Position": position,
            "Titles": title,
            "Links": href,
            "Snippet": snippet
        })
        position += 1
        if n and position > n:
            break

    return results
