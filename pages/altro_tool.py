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
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.5790.170 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:101.0) Gecko/20100101 Firefox/101.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.5790.170 Safari/537.36 Edg/115.0.1901.183",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.199 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.199 Mobile Safari/537.36"
]

# Proxy placeholder
PROXIES = []  # Inserisci proxy in formato "ip:port"

# Paesi e codici Google (alfabetico)
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
    """
    Effettua richiesta a Google e restituisce:
    - status_code: stato HTTP o codice errore custom
    - data: lista risultati o snippet di errore
    - ua: user-agent usato
    """
    delay = random.uniform(2, 5)
    logger.info(f"Sleeping {delay:.2f}s before request")
    time.sleep(delay)

    ua = random.choice(USER_AGENTS)
    headers = {
        "User-Agent": ua,
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/"
    }
    proxies = None
    if PROXIES:
        proxy = random.choice(PROXIES)
        proxies = {"http": proxy, "https": proxy}
        logger.info(f"Using proxy: {proxy}")

    params = {"q": keyword, "num": num, "hl": "it", "gl": country_code, "pws": 0, "filter": 0}
    logger.info(f"Requesting with UA: {ua} and params: {params}")
    try:
        resp = requests.get("https://www.google.com/search", headers=headers, params=params, timeout=10, proxies=proxies)
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return "REQUEST_ERROR", str(e), ua

    status = resp.status_code
    text = resp.text or ""
    snippet = text[:1000]
    logger.info(f"Response status: {status}")

    if status == 429:
        return "TOO_MANY_REQUESTS", snippet, ua
    if status != 200:
        return "HTTP_ERROR", snippet, ua
    if "unusual traffic" in text.lower():
        return "CAPTCHA", snippet, ua

    soup = BeautifulSoup(text, "html.parser")
    titles = [h.get_text(strip=True) for h in soup.find_all("h3")]
    urls = [a.get('href') for a in soup.find_all("a") if a.find("h3")]
    results = [{"Title": t, "URL": u} for t, u in zip(titles, urls)][:num]
    return "OK", results, ua


def main():
    st.title("🛠️ Google Scraper Debug")
    st.markdown("Debug: mostra codice esito, snippet e user-agent.")
    col1, col2, col3 = st.columns(3)
    with col1:
        keyword = st.text_input("Keyword", key="keyword")
    with col2:
        country = st.selectbox("Paese", ALL_COUNTRIES, index=ALL_COUNTRIES.index("Italia"), key="country")
    with col3:
        num = st.selectbox("Risultati", list(range(1, 11)), index=9, key="num")

    if st.button("Avvia scraping"):
        if not keyword.strip():
            st.error("Inserisci keyword.")
            return
        status, data, ua = scrape_google(keyword, COUNTRIES[country], num)
        st.write(f"Esito: {status}")
        st.write(f"User-Agent usato: {ua}")
        if status != "OK":
            st.error(f"Errore o blocco: {status}")
            st.text_area("Snippet risposta:", data, height=200)
            return
        # OK
        df = pd.DataFrame(data)
        st.dataframe(df)
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Risultati")
        buf.seek(0)
        st.download_button("📥 Download XLSX", data=buf, file_name="results.xlsx")

if __name__ == "__main__":
    main()
