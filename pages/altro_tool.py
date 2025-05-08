import streamlit as st
import time
import random
import pandas as pd
import requests
from bs4 import BeautifulSoup
from io import BytesIO
from urllib.parse import quote_plus, urlencode

# Lista di User-Agents per rotazione
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36 Edg/108.0.1462.76"
]

# Lista di paesi supportati con codici TLD di Google
PAESI = {
    "Italia": {"tld": "it", "hl": "it", "gl": "it"},
    "Stati Uniti": {"tld": "com", "hl": "en", "gl": "us"},
    "Regno Unito": {"tld": "co.uk", "hl": "en", "gl": "uk"},
    "Francia": {"tld": "fr", "hl": "fr", "gl": "fr"},
    "Germania": {"tld": "de", "hl": "de", "gl": "de"},
    "Spagna": {"tld": "es", "hl": "es", "gl": "es"},
    "Portogallo": {"tld": "pt", "hl": "pt", "gl": "pt"},
    "Paesi Bassi": {"tld": "nl", "hl": "nl", "gl": "nl"},
    "Belgio": {"tld": "be", "hl": "nl", "gl": "be"},
    "Svizzera": {"tld": "ch", "hl": "de", "gl": "ch"}
}

def get_random_headers():
    """Genera header casuali per le richieste HTTP"""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

def scrape_serp(keyword, paese, num_risultati):
    """Effettua lo scraping dei risultati di ricerca Google"""
    paese_info = PAESI[paese]
    tld = paese_info["tld"]
    hl = paese_info["hl"]
    gl = paese_info["gl"]
    
    # Costruisci l'URL con parametri di query
    params = {
        "q": keyword,
        "hl": hl,
        "gl": gl,
        "num": 100,  # Richiedi più risultati di quelli necessari
        "ie": "utf8",
        "oe": "utf8",
        "pws": 0,     # Disattiva la personalizzazione della ricerca
        "gws_rd": "ssl"
    }
    url = f"https://www.google.{tld}/search?" + urlencode(params)
    
    try:
        # Aggiungi un ritardo casuale prima di ogni richiesta
        time.sleep(random.uniform(1, 3))
        
        # Effettua la richiesta HTTP
        headers = get_random_headers()
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Analizza la risposta con BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Estrai i risultati
        risultati = []
        elementi = soup.select("div.g")
        
        for i, elemento in enumerate(elementi[:num_risultati], 1):
            try:
                # Titolo
                titolo_elem = elemento.select_one("h3")
                titolo = titolo_elem.get_text() if titolo_elem else "N/A"
                
                # URL
                link_elem = elemento.select_one("a")
                url = link_elem.get("href") if link_elem and link_elem.get("href") and link_elem.get("href").startswith("http") else "N/A"
                
                # Snippet/descrizione
                snippet_elem = elemento.select_one("div[style='-webkit-line-clamp:2']") or elemento.select_one("div.VwiC3b")
                snippet = snippet_elem.get_text() if snippet_elem else "N/A"
                
                # Solo se l'URL è valido
                if url != "N/A":
                    risultati.append({
                        "Posizione": i,
                        "Titolo": titolo,
                        "URL": url,
                        "Snippet": snippet
                    })
            except Exception as e:
                st.error(f"Errore nell'estrazione del risultato {i}: {str(e)}")
                continue
                
        return risultati
    
    except Exception as e:
        st.error(f"Errore durante lo scraping: {str(e)}")
        return []

def main():
    st.title("🔍 SERP Scraper")
    
    # Spiegazione
    st.markdown(
        "Estrai i risultati di ricerca Google (SERP) per una keyword in un determinato paese."
    )
    
    # Avviso in box info
    st.info(
        "⚠️ Nota: lo scraping delle SERP di Google potrebbe essere soggetto a limitazioni. "
        "L'applicazione utilizza tecniche per ridurre il rischio di blocchi, ma è consigliabile "
        "limitare il numero di richieste consecutive."
    )
    
    st.divider()
    
    # Input utente
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        keyword = st.text_input(
            "Keyword da analizzare",
            placeholder="Es. marketing digitale"
        )
    
    with col2:
        paese = st.selectbox(
            "Paese",
            options=list(PAESI.keys()),
            index=0
        )
    
    with col3:
        num_risultati = st.slider(
            "Numero di risultati",
            min_value=1, 
            max_value=10,
            value=5
        )
    
    # Pulsante per avviare lo scraping
    if st.button("🚀 Avvia Scraping SERP"):
        if not keyword:
            st.error("Inserisci una keyword da analizzare.")
            return
        
        with st.spinner(f"Analisi in corso per '{keyword}' in {paese}..."):
            risultati = scrape_serp(keyword, paese, num_risultati)
            
            if risultati:
                st.success(f"Trovati {len(risultati)} risultati per '{keyword}'")
                
                # Mostra i risultati in una tabella
                df = pd.DataFrame(risultati)
                st.dataframe(df, use_container_width=True)
                
                # Genera Excel con colonne auto-adattate
                buf = BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name="SERP Results")
                    ws = writer.sheets["SERP Results"]
                    for col_cells in ws.columns:
                        length = max(len(str(cell.value)) for cell in col_cells) + 2
                        ws.column_dimensions[col_cells[0].column_letter].width = length
                buf.seek(0)
                
                st.download_button(
                    "📥 Download XLSX",
                    data=buf,
                    file_name=f"serp_{keyword.replace(' ', '_')}_{paese}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("Nessun risultato trovato. Riprova con una keyword diversa o controlla la connessione.")
                
                # Aggiungi pulsante per usare un servizio proxy come fallback
                if st.button("Prova con servizio proxy (SerpAPI)"):
                    st.info("Per utilizzare SerpAPI è necessario registrarsi e ottenere una API key. Questo approccio è più affidabile ma richiede un account.")
                    st.markdown("[Registrati su SerpAPI](https://serpapi.com/)")

if __name__ == "__main__":
    main()
