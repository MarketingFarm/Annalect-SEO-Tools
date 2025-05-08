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

# --- Configurazione Pagina Streamlit ---
# QUESTA DEVE ESSERE LA PRIMA ISTRUZIONE STREAMLIT NEL FILE DELLA PAGINA
# Assicurati che non ci sia un'altra chiamata a st.set_page_config() nel tuo app.py principale
# se vuoi che ogni pagina abbia la sua configurazione.
# Se app.py ha già una configurazione globale, potresti doverla rimuovere da qui
# o gestire la logica di conseguenza.
try:
    st.set_page_config(page_title="Google SERP Scraper", page_icon="🔎", layout="wide")
except st.errors.StreamlitAPIException as e:
    if "st.set_page_config() can only be called once per app" in str(e) or \
       "st.set_page_config() must be the first Streamlit command" in str(e):
        # Questo può accadere se la configurazione è già stata impostata in app.py
        # o se lo script viene rieseguito in un modo che viola la regola.
        # Per una pagina in 'pages/', questa chiamata dovrebbe funzionare se è la prima.
        pass
    else:
        raise e # Rilancia altre eccezioni st.set_page_config

# --- Configurazione Globale (costanti, ecc.) ---
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36" # Aggiornato leggermente User Agent

PAESI_GOOGLE = {
    "Italia": {"domain": "google.it", "hl": "it"},
    "Stati Uniti": {"domain": "google.com", "hl": "en"},
    "Regno Unito": {"domain": "google.co.uk", "hl": "en"},
    "Francia": {"domain": "google.fr", "hl": "fr"},
    "Germania": {"domain": "google.de", "hl": "de"},
    "Spagna": {"domain": "google.es", "hl": "es"},
    # Aggiungi altri paesi qui
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
    chrome_options.add_argument("--lang=it-IT") # Imposta la lingua del browser per coerenza
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging']) # Nasconde i log di DevTools

    # Tentativi per mascherare Selenium
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    # chrome_options.add_argument('--disable-blink-features=AutomationControlled') # Altra opzione

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
    """Tenta di accettare i cookie sulla pagina di Google in modo più robusto."""
    # Google può usare iframes per i consensi, o diversi pulsanti
    # Questo è un tentativo generico
    possible_buttons_xpaths = [
        "//button[.//div[contains(text(),'Accetta tutto') or contains(text(),'Accept all')]]",
        "//button[contains(.,'Accetta tutto') or contains(.,'Accept all')]",
        "//div[text()='Accetta tutto']/ancestor::button",
        "//div[text()='Accept all']/ancestor::button",
        "//button[@id='L2AGLb']", # Selettore comune
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept all')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accetta tutto')]",
    ]
    try:
        # Verifica se siamo in un iframe di consenso (alcune versioni di Google lo usano)
        iframes_consenso = driver.find_elements(By.XPATH, "//iframe[contains(@src, 'consent.google.com')]")
        if iframes_consenso:
            driver.switch_to.frame(iframes_consenso[0])
            st.caption("Switchato a iframe consenso cookie.") # Debug

        accepted = False
        for xpath in possible_buttons_xpaths:
            try:
                cookie_button = WebDriverWait(driver, 4).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                if cookie_button.is_displayed() and cookie_button.is_enabled():
                    cookie_button.click()
                    st.caption(f"Cookie banner gestito con selettore: {xpath.split('/')[-1].split('[')[0]}") # Debug
                    accepted = True
                    break
            except:
                continue # Prova il prossimo selettore

        if not accepted:
            st.caption("Nessun banner cookie evidente trovato o cliccato con i selettori comuni.")

        # Torna al contenuto principale se eravamo in un iframe
        driver.switch_to.default_content()
        time.sleep(random.uniform(0.5, 1.5)) # Pausa dopo gestione cookie

    except Exception as e_cookie:
        st.caption(f"Avviso: Problema nella gestione cookie (potrebbe non essere presente): {e_cookie}")
        driver.switch_to.default_content() # Assicura di tornare al default content


def scrape_google_serp(keyword: str, paese_info: dict, num_results: int) -> list:
    """Esegue lo scraping dei risultati organici di Google."""
    driver = setup_driver()
    if not driver:
        return []

    results_data = []
    # Google non sempre rispetta `num` esattamente, quindi ne chiediamo un po' di più
    # e poi tronchiamo lato client. Per 10 risultati, chiederne 15-20 è ragionevole.
    google_num_param = min(num_results + 10, 100) # Google non mostra più di 100 senza paginazione
    search_url = f"https://www.{paese_info['domain']}/search?q={keyword.replace(' ', '+')}&hl={paese_info['hl']}&num={google_num_param}&start=0"
    # st.caption(f"URL di ricerca: {search_url}") # Per debug

    try:
        driver.get(search_url)
        time.sleep(random.uniform(2, 4)) # Attesa per caricamento e per non sembrare troppo veloce

        accetta_cookie(driver) # Chiama la funzione per i cookie

        # Selettori per i risultati. Questi sono soggetti a cambiamenti da parte di Google.
        # L'obiettivo è trovare i contenitori principali di ogni risultato organico.
        # Un selettore comune (ma da verificare) per i blocchi dei risultati:
        # "//div[@class='g' or contains(@class,'MjjYud') or contains(@class,'Gx5Zad') or contains(@class,'srg') or contains(@class,'Ww4FFb')]"
        # Più specificamente, cerchiamo blocchi che contengano un link con un H3:
        result_blocks_xpath = "//div[.//a[@href and .//h3] and not(.//span[contains(text(),'Annuncio') or contains(text(),'Ad') or contains(text(),'Sponsorizzato')])]"
        
        WebDriverWait(driver, 10).until(
             EC.presence_of_all_elements_located((By.XPATH, result_blocks_xpath))
        )
        # driver.save_screenshot("debug_serp_page.png"); st.image("debug_serp_page.png") # Per debug

        search_results_elements = driver.find_elements(By.XPATH, result_blocks_xpath)

        count = 0
        for block in search_results_elements:
            if count >= num_results:
                break
            try:
                title_element = block.find_element(By.XPATH, ".//h3")
                title = title_element.text.strip()

                link_element = block.find_element(By.XPATH, ".//a[@href]")
                url = link_element.get_attribute("href")

                # Estrazione dello snippet (descrizione)
                snippet = ""
                try:
                    # Lo snippet è spesso in un div all'interno del blocco, che non è il titolo o il link stesso.
                    # Questo è un tentativo euristico.
                    snippet_candidates = block.find_elements(By.XPATH, ".//div[not(.//h3) and not(.//a) and string-length(normalize-space(text())) > 40]")
                    if not snippet_candidates: # Prova un percorso diverso se il primo fallisce
                         snippet_candidates = block.find_elements(By.XPATH, ".//span[not(ancestor::h3) and not(ancestor::a) and string-length(normalize-space(text())) > 40]")
                    
                    if snippet_candidates:
                        # Prendi il testo più lungo tra i candidati, che non sia parte dell'URL visibile
                        potential_snippets_text = [s.text.strip() for s in snippet_candidates if url not in s.text]
                        if potential_snippets_text:
                            snippet = max(potential_snippets_text, key=len)
                            snippet = snippet.replace("\n", " ").strip() # Pulisci
                            if len(snippet) > 300 : snippet = snippet[:297]+"..." # Tronca se troppo lungo
                except Exception:
                    snippet = "Snippet non trovato"

                # Filtri aggiuntivi per la validità dell'URL
                if title and url and url.startswith("http") and \
                   not any(domain_part in url for domain_part in [paese_info['domain']+"/search", "google.com/search", "google.com/aclk", "googleadservices.com", "google.com/url?q=","support.google.com", "accounts.google.com"]) and \
                   not any(r['URL'] == url for r in results_data): # Evita duplicati
                    results_data.append({"Posizione": count + 1, "Titolo": title, "URL": url, "Snippet": snippet if snippet else "N/D"})
                    count += 1
            
            except Exception: # se un blocco non è formattato come previsto, lo salta
                continue 

        if not results_data and search_results_elements:
             st.warning("Trovati blocchi di risultati, ma non è stato possibile estrarre dati formattati. Controllare i selettori interni (titolo, link, snippet).")
        elif not search_results_elements:
            st.warning("Nessun blocco di risultato trovato con il selettore principale. La struttura della SERP di Google potrebbe essere cambiata o la pagina non ha restituito risultati.")
            # driver.save_screenshot("debug_no_blocks.png"); st.image("debug_no_blocks.png") # Per debug

    except Exception as e_scrape:
        st.error(f"Errore durante lo scraping: {e_scrape}")
        st.caption(f"Dettagli errore scraping: {type(e_scrape).__name__}")
        # try: # Salva screenshot in caso di errore per debug
        #     driver.save_screenshot("error_page_scraping.png")
        #     st.image("error_page_scraping.png", caption="Pagina al momento dell'errore di scraping")
        # except: pass
    finally:
        if driver:
            driver.quit()
    
    return results_data[:num_results] # Assicura di restituire solo il numero richiesto

# --- Interfaccia Utente Streamlit ---
def display_serp_tool():
    st.title("🔎 Google SERP Scraper")

    st.markdown(
        """
        Questo tool esegue lo scraping dei primi X risultati organici di Google
        per una keyword e un paese specificati.
        """
    )
    st.info(
        "⚠️ **Nota Bene:** Lo scraping di Google è tecnicamente contro i loro Termini di Servizio. "
        "Usare con cautela e a proprio rischio. Google potrebbe bloccare temporaneamente l'IP "
        "o presentare CAPTCHA se rileva un traffico anomalo. "
        "I selettori HTML usati per estrarre i dati potrebbero smettere di funzionare se Google aggiorna il layout delle sue pagine."
    )
    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        keyword = st.text_input("🔑 Inserisci la Keyword", placeholder="es. migliori pizzerie roma")
    
    with col2:
        paese_selezionato_nome = st.selectbox(
            "🌍 Seleziona il Paese",
            options=list(PAESI_GOOGLE.keys()),
            index=0 # Default Italia
        )
    with col3:
        # Slider per un massimo di 10 risultati, come richiesto
        num_results_to_scrape = st.slider("🔢 Numero di Risultati da Estrarre (1-10)", min_value=1, max_value=10, value=5)

    if st.button("🚀 Avvia Scraping", type="primary", use_container_width=True):
        if not keyword.strip():
            st.error("Per favore, inserisci una keyword valida.")
        else:
            paese_info = PAESI_GOOGLE[paese_selezionato_nome]
            progress_bar = st.progress(0)
            status_text = st.empty()
            status_text.text(f"Ricerca in corso per '{keyword}' in {paese_selezionato_nome}...")

            start_time = time.time()
            # In un vero scenario con molti risultati o paginazione, qui si aggiornerebbe la progress bar
            scraped_data = scrape_google_serp(keyword, paese_info, num_results_to_scrape)
            end_time = time.time()
            
            progress_bar.progress(100) # Completa la progress bar
            status_text.text("Completato!")


            if scraped_data:
                st.success(f"Scraping completato in {end_time - start_time:.2f} secondi! Trovati {len(scraped_data)} risultati.")
                
                df = pd.DataFrame(scraped_data)
                
                st.subheader("📊 Risultati Ottenuti")
                # Mostra il dataframe, permettendo all'utente di vedere più testo se necessario
                st.dataframe(df, use_container_width=True, hide_index=True)

                # Genera Excel
                output_buffer = BytesIO()
                with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='SERP_Results')
                    worksheet = writer.sheets['SERP_Results']
                    for i, column in enumerate(df.columns): # Itera sulle colonne del DataFrame
                        column_letter = chr(65 + i) # Converte l'indice della colonna in lettera (A, B, C...)
                        max_len = max(df[column].astype(str).map(len).max(), len(column)) + 2 # +2 per un po' di padding
                        worksheet.column_dimensions[column_letter].width = min(max_len, 60) # Limita larghezza massima
                excel_data_bytes = output_buffer.getvalue()

                st.download_button(
                    label="📥 Download Risultati (XLSX)",
                    data=excel_data_bytes,
                    file_name=f"serp_results_{keyword.replace(' ','_')}_{paese_selezionato_nome}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            elif keyword.strip(): # Keyword inserita ma nessun dato
                 status_text.warning("Nessun dato utile restituito dallo scraping per la keyword fornita.")
            progress_bar.empty() # Nasconde la progress bar dopo il completamento o l'errore


    st.markdown("---")
    # st.markdown("Tool sviluppato per l'analisi SERP.") # Puoi personalizzare questo messaggio

# Chiamata alla funzione che costruisce l'interfaccia utente della pagina
# Quando Streamlit esegue questo file come parte di un'app multipagina,
# eseguirà il codice dall'alto, quindi `st.set_page_config` sarà la prima cosa,
# e poi questa chiamata costruirà il resto della pagina.
display_serp_tool()

# Il blocco if __name__ == "__main__": è utile se si desidera eseguire questo script
# direttamente (es. `python nome_file_tool.py`) per testarlo isolatamente.
# In un'app multipagina, Streamlit non esegue questo blocco quando carica la pagina,
# ma esegue tutto ciò che è al di fuori di esso.
if __name__ == "__main__":
    # Non è necessario richiamare display_serp_tool() qui se è già chiamata sopra
    # al livello superiore dello script, poiché sarebbe già stata eseguita.
    pass
