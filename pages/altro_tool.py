import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO
import random
import time
import logging

# Configura logging interno
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lista estesa di User-Agent per rotazione
USER_AGENTS = [
    # Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.5790.170 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:101.0) Gecko/20100101 Firefox/101.0",
    # Safari
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.2 Safari/605.1.15",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.5790.170 Safari/537.36 Edg/115.0.1901.183",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_6_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.5790.170 Safari/537.36 Edg/115.0.1901.183",
    # Mobile Android
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.199 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.199 Mobile Safari/537.36",
]

# Proxy placeholder
PROXIES = []

# Paesi e codici
COUNTRIES = {"Australia":"au","Belgio":"be","Brasile":"br","Canada":"ca","Germania":"de","Spagna":"es","Stati Uniti":"us","Francia":"fr","Grecia":"gr","India":"in","Irlanda":"ie","Italia":"it","Giappone":"jp","Paesi Bassi":"nl","Polonia":"pl","Portogallo":"pt","Repubblica Ceca":"cz","Regno Unito":"uk","Romania":"ro","Svezia":"se","Svizzera":"ch","Ungheria":"hu"}
ALL_COUNTRIES = sorted(COUNTRIES.keys())


def scrape_google(keyword: str, country_code: str, num: int) -> list[dict]:
    # Ritardo random
    delay = random.uniform(2, 5)
    logger.info(f"Sleep for {delay:.2f}s before request")
    time.sleep(delay)

    # Scegli headers e proxy
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/"
    }
    proxies = None
    if PROXIES:
        proxy = random.choice(PROXIES)
        proxies = {"http": proxy, "https": proxy}
        logger.info(f"Using proxy {proxy}")

    params = {"q":keyword, "num":num, "hl":"it", "gl":country_code, "pws":0, "filter":0, "_":int(time.time()*1000)}
    logger.info(f"Requesting Google with params: {params}")

    resp = requests.get("https://www.google.com/search", headers=headers, params=params, timeout=10, proxies=proxies)
    logger.info(f"Response status: {resp.status_code}")
    text = resp.text
    # debug: log snippet
    logger.debug(f"Response snippet: {text[:500]}")

    if "Our systems have detected unusual traffic" in text:
        logger.error("Captcha detected in response")
        raise Exception("Google captcha detected: blocco temporaneo.")

    soup = BeautifulSoup(text, "html.parser")
    results = []
    for h3 in soup.find_all("h3"):
        a = h3.find_parent("a")
        if a and a.has_attr("href"):
            title = h3.get_text(strip=True)
            url = a["href"]
            results.append({"Title":title, "URL":url})
            if len(results)>=num:
                break
    logger.info(f"Found {len(results)} results")
    return results


def main():
    st.title("🌐 Google Scraper (DEBUG)")
    st.markdown("*Versione con logging e controlli aggiuntivi*.")
    st.divider()
    col1, col2, col3 = st.columns(3, gap="small")
    with col1:
        keyword = st.text_input("Keyword", key="keyword")
    with col2:
        country = st.selectbox("Paese", ALL_COUNTRIES, index=ALL_COUNTRIES.index("Italia"), key="country")
    with col3:
        num = st.selectbox("Risultati", list(range(1,11)), index=9, key="num")

    if st.button("Avvia scraping"):
        try:
            items = scrape_google(keyword, COUNTRIES[country], num)
        except Exception as e:
            st.error(f"Errore: {e}")
            return
        if not items:
            st.warning("Nessun risultato rilevato dal parser. Controlla gli snippet nei log.")
            return
        df = pd.DataFrame(items)
        st.dataframe(df)
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        buf.seek(0)
        st.download_button("Download XLSX", data=buf, file_name="results.xlsx")

if __name__=="__main__":
    main()
