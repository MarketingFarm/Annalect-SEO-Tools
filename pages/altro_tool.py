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

# --- Configurazione Globale ---
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"

# Dizionario dei paesi e dei rispettivi domini Google e lingue (per il parametro hl)
# Puoi espandere questa lista come necessario
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
    chrome_options.add_argument("--headless")  # Esegui in background
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920x1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--lang=it-IT") # Imposta la lingua del browser
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging']) # Nasconde i log di DevTools

    # Per evitare il rilevamento di Selenium (parzialmente)
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    try:
        # Usa webdriver_manager per gestire automaticamente il ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        st.error(f"Errore durante l'inizializzazione del WebDriver: {e}")
        st.error("Assicurati di avere Google Chrome installato e che ChromeDriver sia accessibile.")
        st.info("Potrebbe essere necessario installare manualmente ChromeDriver e specificare il percorso.")
        return None

    # Ulteriori tentativi per mascherare Selenium
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def accetta_cookie(driver, paese_info):
    """Tenta di accettare i cookie sulla pagina di Google."""
    try:
        # Google usa diversi selettori per il banner dei cookie a seconda della regione/lingua
        # Prova alcuni selettori comuni
        possible_buttons = [
            "//button[.//div[contains(text(),'Accetta tutto')]]", # Italiano
            "//button[.//div[contains(text(),'Accept all')]]",    # Inglese
            "//div[contains(text(), 'Accetta tutto')]/ancestor::button",
            "//div[contains(text(), 'Accept all')]/ancestor::button",
            "//button[@id='L2AGLb']", # Altro selettore comune
            "//button[contains(., 'Accept')]",
            "//button[contains(., 'Accetto')]"
        ]
        
        cookie_button = None
        for xpath in possible_buttons:
            try:
                button_element = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                if button_element:
                    cookie_button = button_element
                    break
            except:
                continue # Prova il prossimo selettore

        if cookie_button:
            cookie_button.click()
            time.sleep(random.uniform(1, 3)) # Attendi che il banner scompaia
            st.write(f"Banner cookie gestito (o non trovato dopo il timeout).")
        else:
            st.write("Nessun banner cookie evidente trovato o gestito entro il timeout.")

    except Exception as e:
        st.warning(f"Non è stato possibile gestire il banner dei cookie (potrebbe non essere presente): {e}")


def scrape_google_serp(keyword: str, paese_info: dict, num_results: int) -> list:
    """
    Esegue lo scraping dei risultati organici di Google per una data keyword e paese.
    Restituisce una lista di dizionari, ognuno rappresentante un risultato.
    """
    driver = setup_driver()
    if not driver:
        return []

    results = []
    search_url = f"https://www.{paese_info['domain']}/search?q={keyword.replace(' ', '+')}&hl={paese_info['hl']}&num={num_results + 2}" # Chiedi un po' più risultati per sicurezza

    st.write(f"Accesso a: {search_url}")

    try:
        driver.get(search_url)
        time.sleep(random.uniform(2, 5)) # Attesa per il caricamento iniziale e per sembrare più umano

        # Tenta di accettare i cookie
        accetta_cookie(driver, paese_info)

        # I selettori di Google possono cambiare. Questi sono quelli comuni al momento della scrittura.
        # Faremo affidamento sui div che sembrano contenere i risultati organici.
        # Google usa spesso `div` con classi come `g`, `Ww4FFb`, `Gx5Zad`, `fP1Qef`, etc.
        # Un approccio più generale è cercare link all'interno di sezioni che non siano annunci.
        
        # Attendiamo che almeno un risultato di ricerca sia visibile
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-ved] a[href]"))
        )
        
        # Identifica i blocchi dei risultati organici
        # Questo selettore cerca i contenitori principali dei risultati
        # e poi estrae titolo (h3), link (a) e snippet (div con testo più lungo).
        # Potrebbe essere necessario aggiustarlo se Google cambia il layout.
        # Il selettore `div.g` è un classico, ma potrebbe essere troppo generico o obsoleto.
        # Proviamo qualcosa di più specifico, ma con fallback.
        
        # Tentativo 1: Selettore più moderno (basato su osservazioni recenti)
        # Spesso i risultati sono in div che hanno un 'data-hveid' e un link diretto con 'jsname'.
        # Tuttavia, è più robusto cercare elementi con un h3 (titolo) e un link associato.
        
        # Selettore per contenitori di risultati organici (esclude annunci, "Le persone hanno chiesto anche", video, immagini etc.)
        # Si cercano div che contengono un h3 (titolo) e un link (a href)
        # e che non siano chiaramente identificati come annunci (es. tramite la presenza di "Annuncio" o "Sponsorizzato")
        
        # Attendiamo che i risultati siano caricati
        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.XPATH, "//div[.//a[starts-with(@href, 'http')] and .//h3]"))
        )
        
        # Salvataggio screenshot per debug (opzionale)
        # driver.save_screenshot("debug_serp_page.png")
        # st.image("debug_serp_page.png")

        # Estrai gli elementi dei risultati
        # Questo è un selettore di base, potrebbe essere necessario affinarlo
        # Cerca div che contengano un link (a href) e un titolo (h3)
        # e che non siano chiaramente identificati come annunci.
        
        # Selettore XPath per i risultati organici. Questo cerca div che:
        # 1. Contengono un link (<a>) con un href.
        # 2. Contengono un titolo (<h3>).
        # 3. Non contengono testi tipici degli annunci (es. "Annuncio", "Sponsorizzato").
        #    NOTA: I testi degli annunci possono variare per lingua e regione.
        #    Per semplicità, ci concentriamo sulla struttura.
        
        # La struttura dei risultati di Google può essere complessa.
        # Una strategia comune è cercare i div che contengono un titolo (h3) e un link (a).
        # Gli annunci spesso hanno una marcatura specifica.
        
        # Usiamo un selettore CSS più flessibile, cercando div che contengono un h3 e un link sottostante.
        # Questo è un tentativo. L'HTML di Google è dinamico e cambia.
        
        search_results_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'MjjYud') or contains(@class, 'Gx5Zad') or contains(@class, 'srg') or contains(@class, 'g Ww4FFb')]//a[h3 and @href]")
        # Fallback se il precedente non trova nulla o per coprire altri layout:
        if not search_results_elements:
            search_results_elements = driver.find_elements(By.XPATH, "//div[div/a[@href and h3]]")


        count = 0
        for res_link_element in search_results_elements:
            if count >= num_results:
                break

            try:
                url = res_link_element.get_attribute("href")
                title_element = res_link_element.find_element(By.XPATH, ".//h3")
                title = title_element.text.strip()

                # Tenta di trovare lo snippet. Lo snippet è spesso in un div vicino all'h3 o al link.
                # Questo è il punto più instabile perché la struttura varia molto.
                snippet = ""
                try:
                    # Prova 1: Snippet in un div fratello o figlio del genitore del link/titolo
                    # Cerchiamo un div che contenga testo e non sia il titolo stesso, vicino al link
                    parent_block = res_link_element.find_element(By.XPATH, "./ancestor::div[1]") # Il primo div genitore del link
                    
                    # Tentativo di trovare lo snippet, questo è altamente euristico
                    # Si cerca un div con testo che non sia un link e non sia il titolo
                    snippet_elements = parent_block.find_elements(By.XPATH, ".//div[not(.//a) and string-length(normalize-space(text())) > 50 and not(.//h3)]")
                    if snippet_elements:
                        snippet = snippet_elements[0].text.strip()
                    else: # Fallback: cerca un testo più lungo nel blocco genitore
                        all_text_nodes = parent_block.find_elements(By.XPATH, ".//text()[normalize-space()]")
                        potential_snippets = [t.strip() for t in driver.execute_script("return arguments[0].innerText;", parent_block).split('\n') if len(t.strip()) > 50 and title.lower() not in t.lower()]
                        if potential_snippets:
                            snippet = max(potential_snippets, key=len)


                except Exception:
                    snippet = "Snippet non trovato"
                
                # Controllo base per escludere link interni di Google o risultati non validi
                if url and url.startswith("http") and "google.com" not in url.split('/')[2] and "google.it" not in url.split('/')[2] : # Assicurati che non sia un link di Google
                    if not any(r['URL'] == url for r in results): # Evita duplicati (rari ma possibili)
                        results.append({"Posizione": count + 1, "Titolo": title, "URL": url, "Snippet": snippet if snippet else "N/D"})
                        count += 1
                        if count >= num_results:
                            break
            
            except Exception as e_inner:
                st.write(f"Errore nell'elaborare un risultato: {e_inner}")
                continue # Passa al prossimo elemento

        if not results:
            st.warning("Nessun risultato organico trovato con i selettori attuali. La struttura di Google potrebbe essere cambiata.")
            st.info("Potrebbe essere utile salvare uno screenshot della pagina (driver.save_screenshot('debug_serp.png')) per analizzare l'HTML corrente se il problema persiste.")

    except Exception as e:
        st.error(f"Errore durante lo scraping: {e}")
        # Salva screenshot in caso di errore per debug
        try:
            driver.save_screenshot("error_page.png")
            st.image("error_page.png", caption="Pagina al momento dell'errore")
        except:
            pass # Se il driver non è disponibile

    finally:
        if driver:
            driver.quit()
    
    return results[:num_results] # Assicura di restituire solo il numero richiesto

# --- Interfaccia Streamlit ---

def main():
    st.set_page_config(page_title="Google SERP Scraper", page_icon="🔎", layout="wide")
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
        paese_info = PAESI_GOOGLE[paese_selezionato_nome]

    with col3:
        num_results = st.slider("🔢 Numero di Risultati da Estrarre", min_value=1, max_value=10, value=5)

    if st.button("🚀 Avvia Scraping", type="primary", use_container_width=True):
        if not keyword:
            st.error("Per favore, inserisci una keyword.")
            return

        with st.spinner(f"Ricerca in corso per '{keyword}' in {paese_selezionato_nome}... Attendere prego."):
            start_time = time.time()
            scraped_data = scrape_google_serp(keyword, paese_info, num_results)
            end_time = time.time()

        if scraped_data:
            st.success(f"Scraping completato in {end_time - start_time:.2f} secondi! Trovati {len(scraped_data)} risultati.")
            
            df = pd.DataFrame(scraped_data)
            
            st.subheader("📊 Risultati Ottenuti")
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Genera Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='SERP Results')
                # Auto-adatta larghezza colonne
                worksheet = writer.sheets['SERP Results']
                for column_cells in worksheet.columns:
                    length = max(len(str(cell.value)) for cell in column_cells)
                    adjusted_width = (length + 2) * 1.2
                    worksheet.column_dimensions[column_cells[0].column_letter].width = adjusted_width
            excel_data = output.getvalue()

            st.download_button(
                label="📥 Download Risultati (XLSX)",
                data=excel_data,
                file_name=f"serp_results_{keyword.replace(' ','_')}_{paese_selezionato_nome}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        elif not keyword:
             pass # Errore già gestito
        else:
            st.warning("Nessun dato restituito dallo scraping. Controlla i messaggi di log sopra.")

    st.markdown("---")
    st.markdown("Creato con ❤️ da un AI Assistant per te!")

if __name__ == "__main__":
    main()
