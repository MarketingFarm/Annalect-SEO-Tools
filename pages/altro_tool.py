# pages/altro_tool.py

import streamlit as st
import time
import random
import logging
import os
import pandas as pd
from io import BytesIO

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
from pages.parserp.organic_results   import parse_organic_results
from pages.parserp.inline_shopping   import parse_inline_shopping
from pages.parserp.paa_results        import parse_paa_results
from pages.parserp.related_searches   import parse_related_searches

# Riduci log di webdriver-manager
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
options.binary_location = "/usr/bin/chromium"  # binario Chromium su Cloud

def get_driver():
    """Installa e restituisce un ChromeDriver compatibile con Chromium."""
    path = ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
    service = Service(path)
    try:
        return webdriver.Chrome(service=service, options=options)
    except Exception as e:
        st.error(f"Errore avvio ChromeDriver: {e}")
        return None

def scrape_serp(keyword: str, paese: dict, n: int):
    """Apre la SERP, estrae HTML e chiama i parser per ogni sezione."""
    driver = get_driver()
    if not driver:
        return {}

    # Costruisci URL
    url = (
        f"https://www.{paese['domain']}/search?"
        f"q={keyword.replace(' ', '+')}"
        f"&hl={paese['hl']}&num={n}"
    )
    logger.info(f"Navigating to {url}")
    driver.get(url)
    time.sleep(random.uniform(1, 2))

    # Prova a chiudere banner cookie
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

    # Aspetta che compaiano i risultati organici
    try:
        WebDriverWait(driver, 8).until(
            EC.presence_of_all_elements_located((By.XPATH, "//a[.//h3]"))
        )
    except:
        st.caption("⚠️ Timeout ricezione risultati")

    # Prendi l'HTML e chiudi il driver
    html_source = driver.page_source
    driver.quit()

    # Chiama i tuoi parser
    organic   = parse_organic_results(html_source, n)
    shopping  = parse_inline_shopping(html_source, n)
    paa       = parse_paa_results(html_source)
    related   = parse_related_searches(html_source)

    return {
        "organic":  organic,
        "shopping": shopping,
        "paa":      paa,
        "related":  related
    }

def main():
    st.title("🛠️ Google SERP Scraper")
    st.markdown("Estrai le diverse sezioni (organici, shopping, PAA, correlate) di Google SERP.")

    c1, c2, c3 = st.columns(3)
    with c1:
        kw  = st.text_input("🔑 Keyword", placeholder="es. scarpe nere")
    with c2:
        paeso = st.selectbox("🌍 Paese", list(PAESI.keys()))
    with c3:
        cnt  = st.slider("🔢 Risultati organici", 1, 10, 5)

    if st.button("🚀 Avvia Scraping"):
        if not kw.strip():
            st.error("Inserisci una keyword valida.")
            return

        with st.spinner("Sto estraendo la SERP..."):
            data = scrape_serp(kw, PAESI[paeso], cnt)

        # Se non è tornato nulla
        if not data or not data["organic"]:
            st.warning("Nessun risultato trovato o errore.")
            return

        # Organici
        df_org = pd.DataFrame(data["organic"])
        st.subheader("📄 Risultati organici")
        st.dataframe(df_org, use_container_width=True)

        # Inline Shopping (se presente)
        if data["shopping"]:
            df_shp = pd.DataFrame(data["shopping"])
            st.subheader("🛒 Shopping")
            st.dataframe(df_shp, use_container_width=True)

        # People Also Ask
        if data["paa"]:
            df_paa = pd.DataFrame(data["paa"])
            st.subheader("❓ People Also Ask")
            st.dataframe(df_paa, use_container_width=True)

        # Ricerche correlate
        if data["related"]:
            df_rel = pd.DataFrame(data["related"], columns=["Related"])
            st.subheader("🔗 Ricerche correlate")
            st.dataframe(df_rel, use_container_width=True)

        # Export Excel unificato
        with BytesIO() as buf:
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df_org.to_excel(writer, sheet_name="Organici", index=False)
                if data["shopping"]:
                    df_shp.to_excel(writer, sheet_name="Shopping", index=False)
                if data["paa"]:
                    df_paa.to_excel(writer, sheet_name="PAA", index=False)
                if data["related"]:
                    df_rel.to_excel(writer, sheet_name="Correlate", index=False)
                # auto-width
                for sheet in writer.sheets.values():
                    for col in sheet.columns:
                        max_len = max(len(str(cell.value)) for cell in col) + 2
                        sheet.column_dimensions[col[0].column_letter].width = min(max_len, 50)
            st.download_button(
                "📥 Scarica Tutto (XLSX)", buf.getvalue(),
                file_name=f"serp_{kw.replace(' ','_')}_{paeso}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

if __name__ == "__main__":
    main()
