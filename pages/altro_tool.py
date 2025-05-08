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
    # Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...",
    # aggiungi altri UA reali qui
]

# Proxy placeholder (popolabili con IP:PORT)
PROXIES = []

# Paesi e relativi codici Google
COUNTRIES = { ... }
ALL_COUNTRIES = sorted(COUNTRIES.keys())


def scrape_google(keyword: str, country_code: str, num: int):
    # Pre-request debug
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
    logger.info(f"Request URL: https://www.google.com/search")
    logger.info(f"Request headers: {headers}")
    logger.info(f"Request params: {params}")

    resp = requests.get("https://www.google.com/search", headers=headers, params=params, timeout=10, proxies=proxies)
    logger.info(f"Response status code: {resp.status_code}")

    # Esci su errori HTTP
    if resp.status_code != 200:
        logger.error(f"Non-OK status code: {resp.status_code}")
        raise Exception(f"HTTP {resp.status_code}")

    text = resp.text
    # Display snippet for debug
    snippet = text[:1000]
    logger.debug(f"Response snippet: {snippet}")

    # Controllo captcha
    if "Our systems have detected unusual traffic" in text:
        logger.error("Captcha page detected")
        raise Exception("Captcha rilevato: blocco Google.")

    soup = BeautifulSoup(text, "html.parser")
    titles = [h.get_text(strip=True) for h in soup.find_all("h3")]
    urls = [a["href"] for a in soup.find_all("a") if a.find("h3")]

    results = []
    for t, u in zip(titles, urls):
        results.append({"Title": t, "URL": u})
        if len(results) >= num:
            break

    logger.info(f"Parsed {len(results)} results")
    return results, snippet, resp.status_code


def main():
    st.title("🛠️ Google Scraper Debug")
    st.markdown("Versione debug: mostra snippet risposta e codice status HTTP.")
    col1, col2, col3 = st.columns(3)
    with col1:
        keyword = st.text_input("Keyword", key="keyword")
    with col2:
        country = st.selectbox("Paese", ALL_COUNTRIES, index=ALL_COUNTRIES.index("Italia"), key="country")
    with col3:
        num = st.selectbox("Risultati", list(range(1, 11)), index=9, key="num")

    if st.button("Avvia scraping"):
        if not keyword.strip():
            st.error("Inserisci una keyword.")
            return

        try:
            items, snippet, status = scrape_google(keyword, COUNTRIES[country], num)
        except Exception as e:
            st.error(f"Errore: {e}")
            st.write(f"HTTP status: {status if 'status' in locals() else 'n/a'}")
            st.text_area("Snippet risposta (primi 1000 caratteri)", snippet if 'snippet' in locals() else "", height=200)
            return

        if not items:
            st.warning("Nessun risultato trovato.")
        else:
            df = pd.DataFrame(items)
            st.dataframe(df)
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                df.to_excel(w, index=False)
            buf.seek(0)
            st.download_button("Download XLSX", data=buf, file_name="results.xlsx")

if __name__ == "__main__":
    main()
