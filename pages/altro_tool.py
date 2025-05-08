# pages/altro_tool.py

import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.utils import ChromeType # Per specificare Chromium
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
from io import BytesIO
import time
import random

# NOTA: La chiamata a st.set_page_config() è stata rimossa da questo file.
# Si presume che sia gestita centralmente nel tuo file app.py principale.

# --- Configurazione Globale (costanti, ecc.) ---
# User agent aggiornato per simulare un browser comune (Maggio 2025)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

PAESI_GOOGLE = {
    "Italia": {"domain": "google.it", "hl": "it"},
    "Stati Uniti": {"domain": "google.com", "hl": "en"},
    "Regno Unito": {"domain": "google.co.uk", "hl": "en"},
    "Francia": {"domain": "google.fr", "hl": "fr"},
    "Germania": {"domain": "google.de", "hl": "de"},
    "Spagna": {"domain": "google.es", "hl": "es"},
    # Aggiungi altri paesi se necessario
}

# --- Funzioni di Scraping ---
def setup_driver():
    """Configura e restituisce un'istanza del WebDriver di Selenium."""
    chrome_options = Options()
    chrome_options.add_argument(f"user-agent={USER_AGENT}")
    chrome_options.add_argument("--headless") # Esegui in background senza UI visibile
    chrome_options.add_argument("--disable-gpu") # Spesso raccomandato per headless
    chrome_options.add_argument("--window-size=1920x1080") # Imposta una dimensione finestra standard
    chrome_options.add_argument("--no-sandbox") # Cruciale per ambienti Linux/container come Streamlit Cloud
    chrome_options.add_argument("--disable-dev-shm-usage") # Supera problemi di risorse limitate /tmp
    chrome_options.add_argument("--lang=it-IT") # Imposta la lingua del browser
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging']) # Nasconde i log di DevTools console

    # Tentativi per rendere Selenium meno rilevabile
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    # chrome_options.add_argument('--disable-blink-features=AutomationControlled') # Altra opzione anti-rilevamento

    try:
        st.caption("Inizializzazione WebDriver: installazione/verifica di ChromeDriver per Chromium...")
        # Specifica ChromeType.CHROMIUM se il browser nel tuo ambiente è Chromium.
        # Se è Google Chrome standard, puoi omettere chrome_type o usare ChromeType.GOOGLE
        service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
        
        driver = webdriver.Chrome(service=service, options=chrome_options)
        st.caption("WebDriver inizializzato con successo.")
    except Exception as e_driver:
        # Mostra un messaggio di errore più dettagliato e utile
        error_message = getattr(e_driver, 'msg', str(e_driver)) # Tenta di ottenere il messaggio specifico dell'eccezione
        st.error(f"Errore fatale durante l'inizializzazione del WebDriver: {error_message}")
        st.error("Verifica quanto segue:")
        st.error("  1. Che `webdriver-manager` (versione >= 4.0.0) sia nel tuo `requirements.txt` e installato.")
        st.error("  2. Che `Chromium` o `Google Chrome` sia correttamente installato nell'ambiente di esecuzione.")
        st.error("  3. Che non ci siano problemi di rete o permessi che impediscano il download/esecuzione di ChromeDriver.")
        st.error("  4. Se l'errore persiste, controlla i log dell'app per ulteriori dettagli sull'incompatibilità di versione.")
        st.caption(f"Tipo di eccezione: {type(e_driver).__name__}")
        return None

    # Maschera la proprietà navigator.webdriver
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def accetta_cookie(driver):
    """Tenta di individuare e cliccare il pulsante di accettazione dei cookie."""
    # Lista di selettori XPath comuni per i pulsanti di accettazione cookie
    possible_buttons_xpaths = [
        "//button[.//div[contains(text(),'Accetta tutto') or contains(text(),'Accept all')]]",
        "//button[contains(.,'Accetta tutto') or contains(.,'Accept all')]",
        "//div[text()='Accetta tutto']/ancestor::button",
        "//div[text()='Accept all']/ancestor::button",
        "//button[@id='L2AGLb']", # Un ID comune osservato in passato
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept all')]", # Case-insensitive
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accetta tutto')]", # Case-insensitive
        "//button[contains(.,'Consenti tutti') or contains(.,'Allow all')]", # Altre varianti
    ]
    try:
        # Verifica se il banner dei cookie è in un iframe
        iframes_consenso = driver.find_elements(By.XPATH, "//iframe[contains(@src, 'consent.google.')]")
        switched_to_iframe = False
        if iframes_consenso:
            driver.switch_to.frame(iframes_consenso[0])
            switched_to_iframe = True
            # st.caption("Switchato a iframe per gestione cookie.") # Debug

        accepted = False
        for xpath in possible_buttons_xpaths:
            try:
                # Usa un timeout breve per ogni tentativo di selettore
                cookie_button = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                if cookie_button.is_displayed() and cookie_button.is_enabled():
                    cookie_button.click()
                    # st.caption(f"Cookie banner gestito con: {xpath.split('/')[-1]}") # Debug
                    accepted = True
                    break # Esce dal loop se il pulsante è stato cliccato
            except:
                continue # Prova il prossimo selettore

        if switched_to_iframe:
            driver.switch_to.default_content() # Torna sempre al contesto principale

        if accepted:
            time.sleep(random.uniform(0.5, 1.2)) # Breve pausa per stabilizzazione pagina

    except Exception: # Se qualcosa va storto, assicurati di tornare al contesto principale
        if switched_to_iframe: # Assicurati di non rimanere bloccato nell'iframe
             driver.switch_to.default_content()
        # st.caption("Banner cookie non gestito o non trovato.") # Debug


def scrape_google_serp(keyword: str, paese_info: dict, num_results: int) -> list:
    """Esegue lo scraping dei risultati organici di Google per una data keyword e paese."""
    driver = setup_driver()
    if not driver: # Se setup_driver fallisce e restituisce None
        return []

    results_data = []
    # Chiede a Google qualche risultato in più per sicurezza, ma non troppi. Max 100 per pagina.
    google_num_param = min(num_results + 5, 100)
    search_url = f"https://www.{paese_info['domain']}/search?q={keyword.replace(' ', '+')}&hl={paese_info['hl']}&num={google_num_param}&start=0"
    # st.caption(f"URL di ricerca: {search_url}") # Utile per debug

    try:
        driver.get(search_url)
        time.sleep(random.uniform(1.5, 3.0)) # Pausa per caricamento iniziale

        accetta_cookie(driver) # Tenta di gestire il banner dei cookie

        # Selettore XPath per i blocchi dei risultati organici.
        # Esclude annunci comuni (controllando la presenza di testi come "Annuncio", "Ad", "Sponsorizzato").
        result_blocks_xpath = "//div[.//a[@href and .//h3] and not(.//span[contains(lower-case(text()),'annuncio') or contains(lower-case(text()),'ad') or contains(lower-case(text()),'sponsor')])]//ancestor::div[self::div[@data-hveid or @data-ved]][1]"
        # Fallback più generico se il precedente è troppo restrittivo
        fallback_blocks_xpath = "//div[@class='g' or contains(@class,'MjjYud') or contains(@class,'Gx5Zad') or contains(@class,'srg') or contains(@class,'Ww4FFb')][.//a[@href and .//h3]]"

        search_results_elements = []
        try:
            WebDriverWait(driver, 8).until( # Attendi che almeno un elemento sia presente
                 EC.presence_of_all_elements_located((By.XPATH, result_blocks_xpath))
            )
            search_results_elements = driver.find_elements(By.XPATH, result_blocks_xpath)
        except Exception: # Timeout o nessun elemento trovato
            try:
                # st.caption("Selettore primario non ha trovato risultati, tento fallback...") # Debug
                WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((By.XPATH, fallback_blocks_xpath))
                )
                search_results_elements = driver.find_elements(By.XPATH, fallback_blocks_xpath)
            except Exception:
                search_results_elements = [] # Nessun risultato con entrambi i selettori

        if not search_results_elements:
            st.warning(f"Nessun blocco di risultati di ricerca trovato per '{keyword}'. La struttura della pagina di Google potrebbe essere cambiata o non ci sono risultati organici evidenti.")
            # driver.save_screenshot("debug_no_results_blocks.png") # Per debug manuale
            # st.image("debug_no_results_blocks.png")
            return []

        count = 0
        for block_index, block in enumerate(search_results_elements):
            if count >= num_results:
                break
            try:
                # Estrai Titolo e URL (elementi più stabili)
                title_element = block.find_element(By.XPATH, ".//h3")
                title = title_element.text.strip()

                link_element = block.find_element(By.XPATH, ".//a[@href]")
                url = link_element.get_attribute("href")

                # Estrazione dello Snippet (più variabile e soggetto a errori)
                snippet = ""
                try:
                    # Cerca div o span che contengano testo significativo e non siano il titolo/link
                    snippet_candidates = block.find_elements(By.XPATH, ".//div[string-length(normalize-space(.)) > 40 and not(.//h3) and not(.//a[normalize-space(.)=normalize-space(@href)])] | .//span[string-length(normalize-space(.)) > 40 and not(ancestor::h3) and not(ancestor::a[normalize-space(.)=normalize-space(@href)])]")
                    if snippet_candidates:
                        potential_snippets_text = [s.text.strip().replace("\n", " ") for s in snippet_candidates if url not in s.text and title not in s.text]
                        if potential_snippets_text:
                            snippet = max(potential_snippets_text, key=len)
                            if len(snippet) > 280 : snippet = snippet[:277]+"..." # Tronca snippet lunghi
                except Exception:
                    snippet = "N/D (Non Disponibile)"


                # Filtri per validare il risultato come organico e non duplicato
                if title and url and url.startswith("http") and \
                   not any(excluded_domain in url for excluded_domain in [
                       "google.com/search", "google.com/aclk", "googleadservices.com", 
                       "google.com/url?q=", "support.google.com", "accounts.google.com",
                       paese_info['domain']+"/search" # Esclude link di ricerca interni al paese
                   ]) and \
                   not any(r['URL'] == url for r in results_data): # Controllo duplicati

                    results_data.append({
                        "Posizione": count + 1,
                        "Titolo": title,
                        "URL": url,
                        "Snippet": snippet if snippet else "N/D"
                    })
                    count += 1
            
            except Exception: # Se un singolo blocco non può essere processato, passa al successivo
                # st.caption(f"Blocco {block_index+1} saltato a causa di un errore di parsing interno.") # Debug
                continue 
        
        if not results_data and search_results_elements:
             st.warning("Trovati blocchi di risultati, ma non è stato possibile estrarre dati formattati (titolo/URL/snippet). Controllare i selettori XPath interni.")

    except Exception as e_scrape:
        st.error(f"Errore generale durante l'operazione di scraping: {e_scrape}")
        st.caption(f"Tipo di eccezione: {type(e_scrape).__name__}")
        # Considera di salvare uno screenshot per il debug in caso di errori imprevisti
        # if driver:
        #     try:
        #         driver.save_screenshot("error_page_scraping.png")
        #         st.image("error_page_scraping.png", caption="Pagina al momento dell'errore")
        #     except: pass
    finally:
        if driver:
            driver.quit() # Assicura che il browser venga sempre chiuso
    
    return results_data[:num_results] # Restituisce al massimo il numero di risultati richiesti

# --- Interfaccia Utente Streamlit ---
def display_serp_tool():
    # st.title() e altri comandi UI sono permessi qui, dato che st.set_page_config è in app.py
    st.title("🔎 Google SERP Scraper")

    st.markdown(
        """
        Questo strumento estrae i primi X risultati organici dalla pagina dei risultati di Google (SERP)
        per una specifica parola chiave e paese.
        """
    )
    st.info(
        "⚠️ **Avviso:** Lo scraping automatico delle pagine di Google è contrario ai loro Termini di Servizio. "
        "Utilizza questo strumento con cautela e a tuo rischio. Un uso eccessivo potrebbe portare a blocchi temporanei dell'IP "
        "o alla visualizzazione di CAPTCHA. I selettori HTML usati per l'estrazione dei dati potrebbero necessitare di aggiornamenti "
        "se Google modifica il layout delle sue pagine."
    )
    st.divider()

    col1, col2, col3 = st.columns([2,1,1]) # Keyword più larga

    with col1:
        keyword = st.text_input("🔑 Inserisci la Parola Chiave", placeholder="es. migliori ristoranti milano")
    
    with col2:
        paese_selezionato_nome = st.selectbox(
            "🌍 Paese",
            options=list(PAESI_GOOGLE.keys()),
            index=0 # Default Italia
        )
    with col3:
        num_results_to_scrape = st.slider(
            "🔢 N. Risultati", 
            min_value=1, max_value=10, value=5, # Richiesta originale: 1-10 risultati
            help="Seleziona il numero di risultati organici da estrarre (massimo 10)."
        )

    if st.button("🚀 Avvia Scraping", type="primary", use_container_width=True):
        if not keyword.strip():
            st.error("Per favore, inserisci una parola chiave valida.")
        else:
            paese_info = PAESI_GOOGLE[paese_selezionato_nome]
            
            # Placeholder per progress bar e testo di stato
            progress_bar_placeholder = st.empty()
            status_text_placeholder = st.empty()

            status_text_placeholder.info(f"Ricerca in corso per '{keyword}' in {paese_selezionato_nome}. Attendere prego...")
            progress_bar_placeholder.progress(10) # Inizio visuale

            start_time = time.time()
            scraped_data = scrape_google_serp(keyword, paese_info, num_results_to_scrape)
            end_time = time.time()
            
            progress_bar_placeholder.progress(100) # Scraping completato
            
            if scraped_data:
                status_text_placeholder.success(f"Scraping completato in {end_time - start_time:.2f} secondi! Trovati {len(scraped_data)} risultati.")
                
                df = pd.DataFrame(scraped_data)
                
                st.subheader("📊 Risultati Ottenuti")
                st.dataframe(df, use_container_width=True, hide_index=True)

                # Generazione file Excel in memoria
                output_buffer = BytesIO()
                with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='SERP_Results')
                    worksheet = writer.sheets['SERP_Results']
                    # Auto-adattamento larghezza colonne
                    for i, column_df in enumerate(df.columns):
                        column_letter = chr(65 + i) # Da indice a lettera colonna Excel (A, B, ..)
                        # Calcola lunghezza massima del contenuto della colonna o dell'header
                        max_len = max(df[column_df].astype(str).map(len).max(), len(column_df)) + 2 
                        worksheet.column_dimensions[column_letter].width = min(max_len, 70) # Limita larghezza massima per leggibilità
                excel_data_bytes = output_buffer.getvalue()

                st.download_button(
                    label="📥 Download Risultati (XLSX)",
                    data=excel_data_bytes,
                    file_name=f"serp_results_{keyword.replace(' ','_')}_{paese_selezionato_nome}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else: # Nessun dato utile, ma la keyword era valida e lo scraping è terminato
                 status_text_placeholder.warning(f"Nessun risultato organico trovato per '{keyword}' o si è verificato un errore durante l'estrazione. Controllare i messaggi di log/errore sopra, se presenti.")
            
            # Pulisci la progress bar dopo un po' o lasciala piena
            time.sleep(3) # Lascia il messaggio di stato per qualche secondo
            progress_bar_placeholder.empty()
            # status_text_placeholder.empty() # Opzionale: pulire anche il testo di stato


    st.markdown("---")
    st.markdown(f"Ultimo aggiornamento codice: Maggio 2025") # Esempio di piè di pagina

# Chiamata principale per costruire l'interfaccia utente di questa pagina
# Questo viene eseguito quando Streamlit carica questo file dalla cartella 'pages'.
display_serp_tool()

# Il blocco if __name__ == "__main__": è utile principalmente se si esegue
# questo script Python direttamente (es. `python pages/altro_tool.py`) per testarlo
# isolatamente. Quando Streamlit lo esegue come pagina, non entra in questo blocco.
if __name__ == "__main__":
    # Se eseguito direttamente, la configurazione della pagina non sarebbe impostata da app.py,
    # quindi potremmo volerla impostare qui per il testing.
    # try:
    #     st.set_page_config(page_title="Test SERP Scraper", layout="wide")
    # except st.errors.StreamlitAPIException:
    #     pass # Già impostata se rieseguito in qualche modo
    # display_serp_tool() # La chiamata è già al livello superiore, quindi non serve qui.
    pass
