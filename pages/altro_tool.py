# pages/altro_tool.py

import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
from io import BytesIO
import time
import random

# NOTA: La chiamata a st.set_page_config() è stata rimossa da qui.
# Deve essere presente nel tuo file app.py principale.

# --- Configurazione Globale (costanti, ecc.) ---
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"

PAESI_GOOGLE = {
    "Italia": {"domain": "google.it", "hl": "it"},
    "Stati Uniti": {"domain": "google.com", "hl": "en"},
    "Regno Unito": {"domain": "google.co.uk", "hl": "en"},
    "Francia": {"domain": "google.fr", "hl": "fr"},
    "Germania": {"domain": "google.de", "hl": "de"},
    "Spagna": {"domain": "google.es", "hl": "es"},
}

# --- Funzioni di Scraping ---
def setup_driver():
    """Configura e restituisce un'istanza del WebDriver di Selenium."""
    chrome_options = Options()
    chrome_options.add_argument(f"user-agent={USER_AGENT}")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920x1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--lang=it-IT")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e_driver:
        st.error(f"Errore durante l'inizializzazione del WebDriver: {e_driver}")
        st.error("Verifica che Google Chrome sia installato e che ChromeDriver sia accessibile o installabile da webdriver-manager.")
        st.caption(f"Dettagli errore driver: {type(e_driver).__name__}")
        return None

    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def accetta_cookie(driver):
    """Tenta di accettare i cookie sulla pagina di Google."""
    possible_buttons_xpaths = [
        "//button[.//div[contains(text(),'Accetta tutto') or contains(text(),'Accept all')]]",
        "//button[contains(.,'Accetta tutto') or contains(.,'Accept all')]",
        "//div[text()='Accetta tutto']/ancestor::button",
        "//div[text()='Accept all']/ancestor::button",
        "//button[@id='L2AGLb']",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept all')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accetta tutto')]",
    ]
    try:
        iframes_consenso = driver.find_elements(By.XPATH, "//iframe[contains(@src, 'consent.google.com')]")
        if iframes_consenso:
            driver.switch_to.frame(iframes_consenso[0])

        accepted = False
        for xpath in possible_buttons_xpaths:
            try:
                cookie_button = WebDriverWait(driver, 3).until( # Timeout breve
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                if cookie_button.is_displayed() and cookie_button.is_enabled():
                    cookie_button.click()
                    accepted = True
                    break
            except:
                continue

        driver.switch_to.default_content()
        if accepted:
            time.sleep(random.uniform(0.5, 1.0))

    except Exception:
        driver.switch_to.default_content()


def scrape_google_serp(keyword: str, paese_info: dict, num_results: int) -> list:
    """Esegue lo scraping dei risultati organici di Google."""
    driver = setup_driver()
    if not driver:
        return []

    results_data = []
    google_num_param = min(num_results + 10, 100)
    search_url = f"https://www.{paese_info['domain']}/search?q={keyword.replace(' ', '+')}&hl={paese_info['hl']}&num={google_num_param}&start=0"

    try:
        driver.get(search_url)
        time.sleep(random.uniform(1, 2)) # Pausa ridotta
        accetta_cookie(driver)
        result_blocks_xpath = "//div[.//a[@href and .//h3] and not(.//span[contains(text(),'Annuncio') or contains(text(),'Ad') or contains(text(),'Sponsorizzato')])]"
        
        try:
            WebDriverWait(driver, 8).until( # Timeout leggermente ridotto
                 EC.presence_of_all_elements_located((By.XPATH, result_blocks_xpath))
            )
            search_results_elements = driver.find_elements(By.XPATH, result_blocks_xpath)
        except Exception: # Se non trova risultati con quel selettore dopo il timeout
            search_results_elements = []
            st.caption("Nessun blocco di risultati trovato o timeout.")


        count = 0
        for block in search_results_elements:
            if count >= num_results:
                break
            try:
                title_element = block.find_element(By.XPATH, ".//h3")
                title = title_element.text.strip()
                link_element = block.find_element(By.XPATH, ".//a[@href]")
                url = link_element.get_attribute("href")
                snippet = ""
                try:
                    snippet_candidates = block.find_elements(By.XPATH, ".//div[not(.//h3) and not(.//a) and string-length(normalize-space(text())) > 30]")
                    if not snippet_candidates:
                         snippet_candidates = block.find_elements(By.XPATH, ".//span[not(ancestor::h3) and not(ancestor::a) and string-length(normalize-space(text())) > 30]")
                    if snippet_candidates:
                        potential_snippets_text = [s.text.strip().replace("\n", " ") for s in snippet_candidates if url not in s.text]
                        if potential_snippets_text:
                            snippet = max(potential_snippets_text, key=len)
                            if len(snippet) > 250 : snippet = snippet[:247]+"..."
                except Exception:
                    snippet = "N/D"

                if title and url and url.startswith("http") and \
                   not any(domain_part in url for domain_part in [paese_info['domain']+"/search", "google.com/search", "google.com/aclk", "googleadservices.com", "google.com/url?q=","support.google.com", "accounts.google.com"]) and \
                   not any(r['URL'] == url for r in results_data):
                    results_data.append({"Posizione": count + 1, "Titolo": title, "URL": url, "Snippet": snippet if snippet else "N/D"})
                    count += 1
            except Exception:
                continue 
        # Logica di avviso spostata nella funzione chiamante se results_data è vuoto
    except Exception as e_scrape:
        st.error(f"Errore durante lo scraping: {e_scrape}")
        st.caption(f"Dettagli errore scraping: {type(e_scrape).__name__}")
    finally:
        if driver:
            driver.quit()
    return results_data[:num_results]

# --- Interfaccia Utente Streamlit ---
def display_serp_tool():
    st.title("🔎 Google SERP Scraper") # Questo è ok, non è st.set_page_config()

    st.markdown("Questo tool esegue lo scraping dei primi X risultati organici di Google...")
    st.info("⚠️ **Nota Bene:** Lo scraping di Google è tecnicamente contro i loro Termini di Servizio...")
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        keyword = st.text_input("🔑 Inserisci la Keyword", placeholder="es. migliori pizzerie roma")
    with col2:
        paese_selezionato_nome = st.selectbox("🌍 Seleziona il Paese", options=list(PAESI_GOOGLE.keys()), index=0)
    with col3:
        num_results_to_scrape = st.slider("🔢 Numero di Risultati (1-10)", min_value=1, max_value=10, value=5)

    if st.button("🚀 Avvia Scraping", type="primary", use_container_width=True):
        if not keyword.strip():
            st.error("Per favore, inserisci una keyword valida.")
        else:
            paese_info = PAESI_GOOGLE[paese_selezionato_nome]
            progress_bar = st.progress(0)
            status_text = st.empty()
            status_text.info(f"Ricerca in corso per '{keyword}' in {paese_selezionato_nome}...")

            start_time = time.time()
            scraped_data = scrape_google_serp(keyword, paese_info, num_results_to_scrape)
            end_time = time.time()
            
            progress_bar.progress(100)
            
            if scraped_data:
                status_text.success(f"Completato in {end_time - start_time:.2f}s! Trovati {len(scraped_data)} risultati.")
                df = pd.DataFrame(scraped_data)
                st.subheader("📊 Risultati Ottenuti")
                st.dataframe(df, use_container_width=True, hide_index=True)
                output_buffer = BytesIO()
                with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='SERP_Results')
                    worksheet = writer.sheets['SERP_Results']
                    for i, column in enumerate(df.columns):
                        column_letter = chr(65 + i)
                        max_len = max(df[column].astype(str).map(len).max(), len(column)) + 2
                        worksheet.column_dimensions[column_letter].width = min(max_len, 50) # Larghezza colonna limitata
                excel_data_bytes = output_buffer.getvalue()
                st.download_button(
                    label="📥 Download Risultati (XLSX)", data=excel_data_bytes,
                    file_name=f"serp_results_{keyword.replace(' ','_')}_{paese_selezionato_nome}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True
                )
            else: # Nessun dato ma keyword inserita
                 status_text.warning(f"Nessun risultato trovato per '{keyword}' o errore durante lo scraping. Controllare i log se disponibili.")
            # Considera di non svuotare la progress bar o il testo di stato immediatamente
            # per dare tempo all'utente di leggere il messaggio finale. Potresti farlo
            # al prossimo rerun o dopo un breve timeout. Per ora lo lascio così.
            # progress_bar.empty() 
            # status_text.empty()


    st.markdown("---")

display_serp_tool()

if __name__ == "__main__":
    pass # La logica principale è in display_serp_tool()
