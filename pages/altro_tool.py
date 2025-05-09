# pages/altro_tool.py

import streamlit as st
import time
import random
import pandas as pd
from io import BytesIO
import os
import logging

# Riduci il log di webdriver-manager
os.environ["WDM_LOG_LEVEL"] = "0"

# Prova import Selenium; se fallisce, mostra errore
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.core.os_manager import ChromeType
    SELENIUM_OK = True
except ImportError as e:
    SELENIUM_OK = False
    IMPORT_ERR = str(e)

# Configura logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Costanti
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
PAESI = {
    "Italia":      {"domain": "google.it",    "hl": "it"},
    "Stati Uniti": {"domain": "google.com",   "hl": "en"},
    "Regno Unito": {"domain": "google.co.uk", "hl": "en"},
    "Francia":     {"domain": "google.fr",    "hl": "fr"},
    "Germania":    {"domain": "google.de",    "hl": "de"},
    "Spagna":      {"domain": "google.es",    "hl": "es"},
}

# Opzioni Chrome (Streamlit Cloud–friendly)
options = Options()
options.add_argument(f"user-agent={USER_AGENT}")
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--blink-settings=imagesEnabled=false")
# binario Chromium su Cloud
options.binary_location = "/usr/bin/chromium"

def get_driver():
    """Installa e restituisce un driver Chrome/Chromium."""
    path = ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
    service = Service(path)
    try:
        return webdriver.Chrome(service=service, options=options)
    except Exception as e:
        st.error(f"Errore avvio ChromeDriver: {e}")
        return None

def scrape_serp(keyword: str, paese: dict, n: int):
    driver = get_driver()
    if not driver:
        return []
    url = (
        f"https://www.{paese['domain']}/search?"
        f"q={keyword.replace(' ', '+')}"
        f"&hl={paese['hl']}&num={n}"
    )
    logger.info(f"Navigating to {url}")
    driver.get(url)
    time.sleep(random.uniform(1, 2))

    # Banner cookie
    try:
        btn = driver.find_element(
            By.XPATH,
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'accetta')"
            " or contains(.,'Accept all')]"
        )
        btn.click()
        time.sleep(1)
    except:
        pass

    # Aspetta i risultati
    try:
        WebDriverWait(driver, 8).until(
            EC.presence_of_all_elements_located((By.XPATH, "//a[.//h3]"))
        )
    except:
        st.caption("⚠️ Timeout ricezione risultati")

    # Raccogli titoli+link
    results = []
    for a in driver.find_elements(By.XPATH, "//a[.//h3]"):
        try:
            t = a.find_element(By.TAG_NAME, "h3").text
            u = a.get_attribute("href")
            if t and u.startswith("http"):
                results.append({"Title": t, "URL": u})
                if len(results) >= n:
                    break
        except:
            continue

    driver.quit()
    return results

def main():
    st.title("🛠️ Google SERP Scraper")
    st.markdown("Estrai i primi risultati organici di Google per keyword e paese.")
    if not SELENIUM_OK:
        st.error(
            "Manca Selenium/ Webdriver-manager: aggiungi a requirements.txt\n"
            f"Errore import: {IMPORT_ERR}"
        )
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        kw = st.text_input("🔑 Keyword", placeholder="es. scarpe nere")
    with c2:
        p  = st.selectbox("🌍 Paese", list(PAESI.keys()))
    with c3:
        cnt = st.slider("🔢 # Risultati", 1, 10, 5)

    if st.button("🚀 Avvia Scraping"):
        if not kw.strip():
            st.error("Inserisci una keyword valida.")
            return
        with st.spinner("Sto cercando…"):
            data = scrape_serp(kw, PAESI[p], cnt)
        if not data:
            st.warning("Nessun risultato trovato o errore.")
            return

        df = pd.DataFrame(data)
        st.subheader("📊 Risultati")
        st.dataframe(df, use_container_width=True)

        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="Risultati")
            ws = w.sheets["Risultati"]
            for i, col in enumerate(df.columns):
                width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                ws.column_dimensions[chr(65 + i)].width = min(width, 50)
        buf.seek(0)
        st.download_button(
            "📥 Download (XLSX)",
            data=buf.getvalue(),
            file_name=f"serp_{kw.replace(' ','_')}_{p}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

if __name__ == "__main__":
    main()
