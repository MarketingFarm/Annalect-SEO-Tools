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

# Parser organici
from pages.parserp.organic_results import get_organic_results

# Riduci log di webdriver-manager
os.environ['WDM_LOG_LEVEL'] = '0'
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

# Lista di User-Agent per rotazione (desktop e mobile, vari browser)
UA_LIST = [
    # Chrome desktop
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.224 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.118 Safari/537.36",
    # Firefox desktop
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 11.6; rv:115.0) Gecko/20100101 Firefox/115.0",
    # Edge desktop
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Safari mobile
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    # Android mobile
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
]

def get_random_ua():
    return random.choice(UA_LIST)

def get_driver():
    options = Options()
    # Rotazione UA
    options.add_argument(f"user-agent={get_random_ua()}")
    # Finestra casuale per variare footprint
    width = random.choice([1024, 1280, 1366, 1440, 1600, 1920])
    height = random.choice([768, 800, 900, 1050, 1080, 1200])
    options.add_argument(f"--window-size={width},{height}")
    # Headless e performance
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    # Blocca immagini per velocità e privacy
    options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    # Stealth
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option('excludeSwitches', ['enable-automation','enable-logging'])
    options.add_experimental_option('useAutomationExtension', False)
    options.binary_location = '/usr/bin/chromium'

    # Monta driver
    path = ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
    service = Service(path)
    try:
        driver = webdriver.Chrome(service=service, options=options)
        # Rimuove webdriver flag
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        })
        return driver
    except Exception as e:
        st.error(f"Errore avvio ChromeDriver: {e}")
        return None
():
    return random.choice(UA_LIST)


def get_driver():
    options = Options()
    options.add_argument(f"user-agent={get_random_ua()}")
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option('excludeSwitches', ['enable-automation','enable-logging'])
    options.add_experimental_option('useAutomationExtension', False)
    options.binary_location = '/usr/bin/chromium'

    path = ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
    service = Service(path)
    try:
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        })
        return driver
    except Exception as e:
        st.error(f"Errore avvio ChromeDriver: {e}")
        return None


def scrape_serp(keyword: str, paese: dict, n: int) -> list:
    driver = get_driver()
    if not driver:
        return []

    query = keyword.replace(' ', '+')
    url = f"https://www.{paese['domain']}/search?q={query}&hl={paese['hl']}&num={n}"
    logger.info(f"Navigating to {url}")
    driver.get(url)
    time.sleep(random.uniform(2, 4))

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div.g'))
        )
    except:
        st.caption("⚠️ Timeout ricezione risultati – verifica i selettori")

    html = driver.page_source
    driver.quit()

    soup = BeautifulSoup(html, 'html.parser')
    return get_organic_results(soup, n)


def main():
    st.title("🛠️ Google SERP Scraper – Solo Organici")
    st.markdown("Estrai i primi risultati organici di Google per keyword e paese.")

    if not SELENIUM_OK:
        st.error(f"Manca Selenium/Webdriver-manager. Errore import: {IMPORT_ERR}")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        kw = st.text_input("🔑 Keyword", placeholder="es. scarpe nere")
    with c2:
        pa = st.selectbox("🌍 Paese", list(PAESI.keys()))
    with c3:
        cnt = st.slider("🔢 # Risultati organici", 1, 10, 5)

    if st.button("🚀 Avvia Scraping"):
        if not kw.strip():
            st.error("Inserisci una keyword valida.")
            return

        with st.spinner("Sto cercando…"):
            results = scrape_serp(kw, PAESI[pa], cnt)

        if not results:
            st.warning("Nessun risultato trovato o errore.")
            return

        df = pd.DataFrame(results)
        st.subheader("📄 Risultati organici")
        st.dataframe(df, use_container_width=True)

        # Export XLSX
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Organici')
            ws = writer.sheets['Organici']
            for i, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                ws.column_dimensions[chr(65 + i)].width = min(max_len, 50)
        buf.seek(0)
        st.download_button(
            "📥 Download Risultati (XLSX)", buf.getvalue(),
            file_name=f"serp_{kw.replace(' ','_')}_{pa}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

if __name__ == "__main__":
    main()
