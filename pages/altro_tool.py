import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO
import random
import time
import logging

# Configura logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lista estesa di User-Agent per rotazione
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...",
    # ... altri UA ...
]

# Proxy placeholder (popolabili con IP:PORT validi)
PROXIES = []

# Paesi e relativi codici Google (in ordine alfabetico)
COUNTRIES = {
    "Australia": "au", "Belgio": "be", "Brasile": "br", "Canada": "ca",
    "Francia": "fr", "Germania": "de", "Giappone": "jp", "Grecia": "gr",
    "India": "in", "Irlanda": "ie", "Italia": "it", "Paesi Bassi": "nl",
    "Polonia": "pl", "Portogallo": "pt", "Repubblica Ceca": "cz",
    "Regno Unito": "uk", "Romania": "ro", "Spagna": "es", "Svezia": "se",
    "Svizzera": "ch", "Ungheria": "hu", "Stati Uniti": "us"
}
ALL_COUNTRIES = sorted(COUNTRIES.keys())


def scrape_google(keyword: str, country_code: str, num: int):
    delay = random.uniform(2, 5)
    logger.info(f"Sleeping {delay:.2f}s before request")
    time.sleep(delay)

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/"
    }

    proxies = None
    if PROXIES:
        proxy = random.choice(PROXIES)
        proxies = {"http": proxy, "https": proxy}
        logger.info(f"Using proxy: {proxy}")

    params = {"q": keyword, "num": num, "hl": "it", "gl": country_code, "pws": 0, "filter": 0}
    logger.info(f"Requesting Google with params: {params}")
    try:
        resp = requests.get(
            "https://www.google.com/search", headers=headers, params=params,
            timeout=10, proxies=proxies
        )
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return [], str(e), None

    status = resp.status_code
    text = resp.text or ""
    snippet = text[:1000]
    logger.info(f"Response status code: {status}")

    if status != 200:
        logger.error(f"Non-OK status code: {status}")
        return [], snippet, status

    if "Our systems have detected unusual traffic" in text:
        logger.error("Captcha page detected")
        return [], snippet, status

    soup = BeautifulSoup(text, "html.parser")
    titles = [h.get_text(strip=True) for h in soup.find_all("h3")]
    urls = [a["href"] for a in soup.find_all("a") if a.find("h3")]

    results = []
    for t, u in zip(titles, urls):
        results.append({"Title": t, "URL": u})
        if len(results) >= num:
            break

    logger.info(f"Parsed {len(results)} results")
    return results, snippet, status


def main():
    st.title("🛠️ Google Scraper Debug")
    st.markdown("Versione debug: mostra snippet risposta e codice status HTTP.")
    col1, col2, col3 = st.columns(3)
    with col1:
        keyword = st.text_input("Keyword", key="keyword")
    with col2:
        country = st.selectbox("Paese", ALL_COUNTRIES,
                               index=ALL_COUNTRIES.index("Italia"), key="country")
    with col3:
        num = st.selectbox("Risultati", list(range(1, 11)), index=9, key="num")

    if st.button("Avvia scraping"):
        if not keyword.strip():
            st.error("Inserisci una keyword.")
            return

        items, snippet, status = scrape_google(keyword, COUNTRIES[country], num)

        if status is None:
            st.error(f"Request error: {snippet}")
            return
        if status != 200:
            st.error(f"HTTP status: {status}")
            st.text_area("Snippet risposta (primi 1000 caratteri)", snippet, height=200)
            return
        if not items:
            st.warning("Nessun risultato trovato o captcha rilevato.")
            st.text_area("Snippet risposta (primi 1000 caratteri)", snippet, height=200)
            return

        df = pd.DataFrame(items)
        st.dataframe(df)
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Risultati")
        buf.seek(0)
        st.download_button("Download XLSX", data=buf, file_name="results.xlsx")

if __name__ == "__main__":
    main()
