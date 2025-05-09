from bs4 import BeautifulSoup
import re
from typing import List, Dict


def get_inline_shopping(soup: BeautifulSoup, n: int = None) -> List[Dict]:
    """
    Estrae i prodotti Shopping inline (PLA) dalla SERP di Google.
    - soup: oggetto BeautifulSoup della pagina.
    - n: numero massimo di risultati (default None = tutti).
    Restituisce una lista di dict con chiavi:
    Keyword, Position, Titles, Merchant, Price, Value, Link
    """
    # Alcuni layout chiamano il container 'div.GM2Fxb' o 'div.sZyCDf'
    html_inline = soup.find("div", class_="cu-container") \
               or soup.find("div", class_="GM2Fxb") \
               or soup.find("div", class_="sZyCDf")
    if html_inline is None:
        return []

    results = []
    position = 1

    # Blocchi PLA possono avere classi mnr-c o pla-unit
    for block in html_inline.find_all("div", class_["mnr-c", "pla-unit"]):
        title_tag    = block.find("a", class_="plantl pla-unit-title-link")
        merchant_tag = block.find("div", class_="LbUacb")
        price_tag    = block.find("div", class_="e10twf T4OwTb")
        link_tag     = block.find("a", class_="plantl", href=True)

        if not (title_tag and merchant_tag and price_tag and link_tag):
            continue

        # Pulizia testi
        title    = re.sub(r"\s+", " ", title_tag.get_text(strip=True))
        merchant = re.sub(r"\s+", " ", merchant_tag.get_text(strip=True))
        price    = re.sub(r"\s+", " ", price_tag.get_text(strip=True))

        # Estrai valore numerico
        only_value  = price.replace(",", ".")
        value_comma = re.sub(r"[^\d\.]", "", only_value)
        value       = value_comma.replace(".", ",")

        # Keyword dal <title>
        full_title = soup.title.get_text()
        keyword    = full_title.split(" - ")[0].strip()

        results.append({
            "Keyword":  keyword,
            "Position": position,
            "Titles":   title,
            "Merchant": merchant,
            "Price":    price,
            "Value":    value,
            "Link":     link_tag["href"]
        })

        position += 1
        if n and position > n:
            break

    return results
