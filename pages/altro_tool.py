import streamlit as st
import pandas as pd
from io import BytesIO
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Configura logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paesi e codici Google (in ordine alfabetico)
COUNTRIES = {
    "Australia": "au", "Belgio": "be", "Brasile": "br", "Canada": "ca",
    "Francia": "fr", "Germania": "de", "Giappone": "jp", "Grecia": "gr",
    "India": "in", "Irlanda": "ie", "Italia": "it", "Paesi Bassi": "nl",
    "Polonia": "pl", "Portogallo": "pt", "Repubblica Ceca": "cz",
    "Regno Unito": "uk", "Romania": "ro", "Spagna": "es", "Svezia": "se",
    "Svizzera": "ch", "Ungheria": "hu", "Stati Uniti": "us"
}
ALL_COUNTRIES = sorted(COUNTRIES.keys())

@st.cache_resource
def get_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def scrape_with_selenium(keyword: str, country_code: str, num: int):
    driver = get_driver()
    # Costruisci URL di ricerca
    query = keyword.replace(' ', '+')
    url = f"https://www.google.com/search?q={query}&num={num}&hl=it&gl={country_code}&pws=0&filter=0"
    logger.info(f"Navigating to {url}")
    driver.get(url)
    # Attendi caricamento
    time.sleep(2)
    items = []
    # Trova i titoli dei risultati organici
    results = driver.find_elements(By.CSS_SELECTOR, 'div.g')
    for res in results:
        try:
            h3 = res.find_element(By.TAG_NAME, 'h3')
            a = h3.find_element(By.XPATH, './ancestor::a')
            title = h3.text
            link = a.get_attribute('href')
            items.append({'Title': title, 'URL': link})
            if len(items) >= num:
                break
        except Exception:
            continue
    return items


def main():
    st.title("🌐 Google Scraper con Selenium")
    st.markdown("Scrapa i risultati di Google usando Selenium headless per evitare blocchi.")
    col1, col2, col3 = st.columns(3)
    with col1:
        keyword = st.text_input("🔑 Keyword da cercare", placeholder="es. chatbot AI")
    with col2:
        country = st.selectbox("🌍 Seleziona paese", ALL_COUNTRIES,
                               index=ALL_COUNTRIES.index("Italia"))
    with col3:
        num = st.selectbox("🎯 Numero di risultati", list(range(1, 11)), index=9)

    if st.button("🚀 Avvia scraping"):
        if not keyword.strip():
            st.error("Inserisci una keyword valida.")
            return
        with st.spinner("Avvio browser e estrazione risultati…"):
            try:
                items = scrape_with_selenium(keyword, COUNTRIES[country], num)
            except Exception as e:
                st.error(f"Errore Selenium: {e}")
                return
        if not items:
            st.warning("Nessun risultato trovato o blocco inatteso.")
            return
        df = pd.DataFrame(items)
        st.dataframe(df, use_container_width=True)
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Risultati")
        buf.seek(0)
        st.download_button("📥 Scarica XLSX", data=buf,
                           file_name="google_selenium.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__ == "__main__":
    main()
