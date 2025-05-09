from bs4 import BeautifulSoup
import pandas as pd
import re

def get_organic_results(soup: BeautifulSoup, n: int = None) -> list[dict]:
    """
    Estrae i risultati organici dalla SERP (contenitore #rso).
    Se non trova il contenitore ritorna lista vuota.
    """
    html_organic_results = soup.find("div", {"id": "rso"})
    if html_organic_results is None:
        return []

    # Rimuovi eventuali blocchi non organici
    for cls in ("kno-kp", "mnr-c", "ULSxyf", "mod"):
        dup = html_organic_results.find("div", class_=cls)
        if dup:
            dup.decompose()

    div_obj = {
        "Keyword": [],
        "Position": [],
        "Titles": [],
        "Links": []
    }

    position = 1
    for organic_result in html_organic_results.find_all("div", class_="g"):
        h3 = organic_result.find("h3")
        if not h3:
            continue

        title = h3.get_text(strip=True)
        title = re.sub(r"\s+", " ", title)

        link_tag = organic_result.find("a", href=True)
        href = link_tag["href"] if link_tag else None
        if not href or not href.startswith("http"):
            continue

        div_obj["Keyword"].append(soup.title.get_text().split(" - ")[0].strip())
        div_obj["Position"].append(position)
        div_obj["Titles"].append(title)
        div_obj["Links"].append(href)
        position += 1
        if n and position > n:
            break

    # Costruisci lista di dict
    results = [
        {"Keyword": k, "Position": p, "Titles": t, "Links": u}
        for k, p, t, u in zip(
            div_obj["Keyword"],
            div_obj["Position"],
            div_obj["Titles"],
            div_obj["Links"],
        )
    ]
    return results
