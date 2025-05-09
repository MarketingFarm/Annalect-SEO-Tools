import streamlit as st
import time
import random
import logging
import os
import pandas as pd
from io import BytesIO
from bs4 import BeautifulSoup

# Selenium e WebDriver-Manager
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

# I tuoi parser dalla cartella pages/parserp
from pages.parserp.organic_results import get_organic_results
from pages.parserp.inline_shopping import get_inline_shopping
from pages.parserp.paa_results import get_paa_results
from pages.parserp.related_searches import get_related_searches

# Riduci il log di webdriver-manager
os.environ['WDM_LOG_LEVEL'] = '0'
# Configura logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mappatura paesi
PAESI = {
    "Italia":      {"domain": "google.it",    "hl": "it"},
    "Stati Uniti": {"domain": "google.com",   "hl": "en"},
    "Regno Unito": {"domain": "google.co.uk", "hl": "en"},
    "Francia":     {"domain": "google.fr",    "hl": "fr"},
    "Germania":    {"domain": "google.de",    "hl": "de"},
    "Spagna":      {"domain": "google.es",    "hl": "es"},
}

# Lista di User-Agent per rotazione
UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
]

def get_random_ua():
    return random.choice(UA_LIST)


def get_driver():
    """Installa e restituisce un driver Chrome/Chromium con opzioni stealth."""
    options = Options()
    # Rotazione UA
    ua = get_random_ua()
    options.add_argument(f"user-agent={ua}")
    # Headless e performance
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--blink-settings=imagesEnabled=false")
    # Evita rilevamento Automation
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    options.add_experimental_option('excludeSwitches', ['enable-automation','enable-logging'])
    options.add_experimental_option('useAutomationExtension', False)
    # Binario Chromium su Streamlit Cloud
    options.binary_location = '/usr/bin/chromium'

    driver_path = ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
    service = Service(driver_path)
    try:
        driver = webdriver.Chrome(service=service, options=options)
        # Stealth: rimuove webdriver property
        driver.execute_cdp_cmd(
            'Page.addScriptToEvaluateOnNewDocument',
            {'source': """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """}
        )
        return driver
    except Exception as e:
        st.error(f"Errore avvio ChromeDriver: {e}")
        return None


def accept_cookies(driver):
    """Prova a gestire banner cookie EU se presente"""
    try:
        btn = driver.find_element(
            By.XPATH,
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'accetta')"
            " or contains(.,'Accept all') or contains(.,'I agree')]")
        if btn.is_displayed():
            btn.click()
            time.sleep(random.uniform(0.5, 1.5))
    except:
        pass


def scrape_serp(keyword: str, paese: dict, n: int) -> dict:
    """
    Apre la SERP di Google, attende i risultati, estrae HTML e chiama i parser.
    Restituisce dizionario con sezioni: organic, shopping, paa, related.
    """
    driver = get_driver()
    if not driver:
        return {}

    # Costruisci URL
    query = keyword.replace(' ', '+')
    url = f"https://www.{paese['domain']}/search?q={query}&hl={paese['hl']}&num={n}"
    logger.info(f"Navigating to {url}")
    driver.get(url)

    # Pausa umana prima di interagire
    time.sleep(random.uniform(2, 4))
    accept_cookies(driver)

    # Aspetta i blocchi organici
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div.g'))
        )
    except:
        st.caption("⚠️ Timeout ricezione risultati – verifica i selettori")

    # Prendi sorgente e chiudi browser
    html = driver.page_source
    driver.quit()

    soup = BeautifulSoup(html, 'html.parser')
    # Chiama i parser
    organic  = get_organic_results(soup, n)
    shopping = get_inline_shopping(soup, n)
    paa      = get_paa_results(soup)
    related  = get_related_searches(soup)

    return {
        'organic':  organic,
        'shopping': shopping,
        'paa':      paa,
        'related':  related
    }


def main():
    st.title("🛠️ Google SERP Scraper")
    st.markdown("Estrai le sezioni organiche, Shopping, PAA e correlate dalla SERP di Google.")

    if not SELENIUM_OK:
        st.error(
            "Manca Selenium/Webdriver-manager in requirements.txt. "
            f"Errore import: {IMPORT_ERR}"
        )
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        kw = st.text_input("🔑 Keyword", placeholder="es. scarpe nere")
    with c2:
        paese_sel = st.selectbox("🌍 Paese", list(PAESI.keys()))
    with c3:
        cnt = st.slider("🔢 Risultati organici", 1, 10, 5)

    if st.button("🚀 Avvia Scraping"):
        if not kw.strip():
            st.error("Inserisci una keyword valida.")
            return

        with st.spinner("Estraggo la SERP..."):
            data = scrape_serp(kw, PAESI[paese_sel], cnt)

        # Controlla organici
        if not data.get('organic'):
            st.warning("Nessun risultato trovato o errore.")
            return

        # Mostra DataFrame
        df_org = pd.DataFrame(data['organic'])
        st.subheader("📄 Risultati organici")
        st.dataframe(df_org, use_container_width=True)

        # Inline Shopping
        if data['shopping']:
            df_shp = pd.DataFrame(data['shopping'])
            st.subheader("🛒 Shopping")
            st.dataframe(df_shp, use_container_width=True)

        # PAA
        if data['paa']:
            df_paa = pd.DataFrame(data['paa'])
            st.subheader("❓ People Also Ask")
            st.dataframe(df_paa, use_container_width=True)

        # Correlate
        if data['related']:
            df_rel = pd.DataFrame(data['related'])
            st.subheader("🔗 Ricerche correlate")
            st.dataframe(df_rel, use_container_width=True)

        # Export multi-sheet
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df_org.to_excel(writer, sheet_name='Organici', index=False)
            if data['shopping']:
                df_shp.to_excel(writer, sheet_name='Shopping', index=False)
            if data['paa']:
                df_paa.to_excel(writer, sheet_name='PAA', index=False)
            if data['related']:
                df_rel.to_excel(writer, sheet_name='Correlate', index=False)
            for ws in writer.sheets.values():
                for col in ws.columns:
                    max_len = max(len(str(cell.value)) for cell in col) + 2
                    ws.column_dimensions[col[0].column_letter].width = min(max_len, 50)
        buf.seek(0)
        st.download_button(
            "📥 Scarica Tutto (XLSX)",
            buf.getvalue(),
            file_name=f"serp_{kw.replace(' ','_')}_{paese_sel}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

if __name__ == "__main__":
    main()
