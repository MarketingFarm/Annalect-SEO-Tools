# pages/altro_tool.py

import streamlit as st
import time
import random
import logging
import os
import pandas as pd
from io import BytesIO
from bs4 import BeautifulSoup

# Selenium e WebDriver-Manager
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

# I tuoi parser dalla cartella pages/parserp
from pages.parserp.organic_results import get_organic_results
from pages.parserp.inline_shopping import get_inline_shopping
from pages.parserp.paa_results import get_paa_results
from pages.parserp.related_searches import get_related_searches

# Riduci il log di webdriver-manager
os.environ["WDM_LOG_LEVEL"] = "0"

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

# Opzioni Chrome (compatibili Streamlit Cloud)
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
    """
    Installa e restituisce un ChromeDriver compatibile con Chromium.
    """
    driver_path = ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
    service = Service(driver_path)
    try:
        return webdriver.Chrome(service=service, options=options)
    except Exception as e:
        st.error(f"Errore avvio ChromeDriver: {e}")
        return None


def scrape_serp(keyword: str, paese: dict, n: int) -> dict:
    """
    Apre la SERP di Google, estrae l'HTML e chiama i parser.
    Restituisce un dict con sezioni: organic, shopping, paa, related.
    """
    driver = get_driver()
    if not driver:
        return {}

    url = (
        f"https://www.{paese['domain']}/search?"
        f"q={keyword.replace(' ', '+')}&hl={paese['hl']}&num={n}"
    )
    logger.info(f"Navigating to {url}")
    driver.get(url)
    time.sleep(random.uniform(1, 2))

    # Banner cookie
    try:
        btn = driver.find_element(
            By.XPATH,
            ("//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
             "'abcdefghijklmnopqrstuvwxyz'),'accetta')"
             " or contains(.,'Accept all')]")
        )
        btn.click()
        time.sleep(1)
    except:
        pass

        # Aspetta i risultati organici (div.g)
    try:
        WebDriverWait(driver, 8).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.g"))
        )
    except:
        st.caption("⚠️ Timeout ricezione risultati – il layout potrebbe essere cambiato")


    html_source = driver.page_source
    driver.quit()

    # Parsers
    soup = BeautifulSoup(html_source, "html.parser")
    organic = get_organic_results(soup)
    shopping = get_inline_shopping(soup)
    paa = get_paa_results(soup)
    related = get_related_searches(soup)

    # Limita organici a n
    organic = organic[:n]

    return {
        "organic":  organic,
        "shopping": shopping,
        "paa":      paa,
        "related":  related
    }


def main():
    st.title("🛠️ Google SERP Scraper")
    st.markdown("Estrai le sezioni organiche, Shopping, PAA e correlate dalla SERP di Google.")

    c1, c2, c3 = st.columns(3)
    with c1:
        kw  = st.text_input("🔑 Keyword", placeholder="es. scarpe nere")
    with c2:
        paese = st.selectbox("🌍 Paese", list(PAESI.keys()))
    with c3:
        cnt = st.slider("🔢 # risultati organici", 1, 10, 5)

    if st.button("🚀 Avvia Scraping"):
        if not kw.strip():
            st.error("Inserisci una keyword valida.")
            return

        with st.spinner("Estraggo la SERP..."):
            data = scrape_serp(kw, PAESI[paese], cnt)

        if not data or not data.get("organic"):
            st.warning("Nessun risultato trovato o errore.")
            return

        # Organici
        df_org = pd.DataFrame(data["organic"])
        st.subheader("📄 Risultati organici")
        st.dataframe(df_org, use_container_width=True)

        # Shopping
        if data["shopping"]:
            df_shp = pd.DataFrame(data["shopping"])
            st.subheader("🛒 Inline Shopping")
            st.dataframe(df_shp, use_container_width=True)

        # PAA
        if data["paa"]:
            df_paa = pd.DataFrame(data["paa"])
            st.subheader("❓ People Also Ask")
            st.dataframe(df_paa, use_container_width=True)

        # Correlate
        if data["related"]:
            df_rel = pd.DataFrame(data["related"], columns=["Related"])
            st.subheader("🔗 Ricerche correlate")
            st.dataframe(df_rel, use_container_width=True)

        # Excel multi-sheet
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df_org.to_excel(w, sheet_name="Organici", index=False)
            if data["shopping"]: df_shp.to_excel(w, sheet_name="Shopping", index=False)
            if data["paa"]: df_paa.to_excel(w, sheet_name="PAA", index=False)
            if data["related"]: df_rel.to_excel(w, sheet_name="Correlate", index=False)
            for ws in w.sheets.values():
                for col in ws.columns:
                    max_len = max(len(str(cell.value)) for cell in col) + 2
                    ws.column_dimensions[col[0].column_letter].width = min(max_len, 50)
        buf.seek(0)
        st.download_button(
            "📥 Scarica (XLSX)", buf.getvalue(),
            file_name=f"serp_{kw.replace(' ','_')}_{paese}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

if __name__ == "__main__":
    main()
