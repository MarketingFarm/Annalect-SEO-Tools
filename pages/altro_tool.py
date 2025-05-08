import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO
import random
import time

# Lista di User-Agent per rotazione
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
    # aggiungi altri se vuoi
]

# Mappa nome-paese → codice GL per Google (principali paesi europei inclusi)
COUNTRIES = {
    "Australia": "au",
    "Belgio": "be",
    "Brasile": "br",
    "Canada": "ca",
    "Germania": "de",
    "Spagna": "es",
    "Stati Uniti": "us",
    "Francia": "fr",
    "Grecia": "gr",
    "India": "in",
    "Irlanda": "ie",
    "Italia": "it",
    "Giappone": "jp",
    "Paesi Bassi": "nl",
    "Polonia": "pl",
    "Portogallo": "pt",
    "Repubblica Ceca": "cz",
    "Regno Unito": "uk",
    "Romania": "ro",
    "Svezia": "se",
    "Svizzera": "ch",
    "Ungheria": "hu"
}
# Ordiniamo alfabeticamente le chiavi
ALL_COUNTRIES = sorted(COUNTRIES.keys(), key=lambda x: x)


def scrape_google(keyword: str, country_code: str, num: int) -> list[dict]:
    """
    Esegue una query su Google con parametri anti-bot:
    - rotazione User-Agent
    - aggiunta di pws=0 e filter=0
    - delay casuale
    - header Accept-Language e Referer
    """
    # Delay random tra 1 e 3 secondi
    time.sleep(random.uniform(1, 3))

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/"
    }
    params = {
        "q": keyword,
        "num": num,
        "hl": "it",
        "gl": country_code,
        "pws": 0,       # disabilita risultati personalizzati
        "filter": 0     # mostra risultati duplicati se necessario
    }
    resp = requests.get(
        "https://www.google.com/search",
        headers=headers,
        params=params,
        timeout=10
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    results = []
    for h3 in soup.find_all("h3"):
        a = h3.find_parent("a")
        if a and a.has_attr("href"):
            url = a["href"]
            title = h3.get_text(strip=True)
            results.append({"Title": title, "URL": url})
            if len(results) >= num:
                break
    return results


def main():
    st.title("🌐 Google Scraper")
    st.markdown("Scrapa i primi risultati organici di Google con pratiche anti-bot.")
    st.divider()

    col1, col2, col3 = st.columns(3, gap="small")
    with col1:
        keyword = st.text_input("🔑 Keyword da cercare", placeholder="es. chatbot AI", key="keyword")
    with col2:
        country = st.selectbox("🌍 Seleziona paese", ALL_COUNTRIES, index=ALL_COUNTRIES.index("Italia"), key="country")
    with col3:
        num = st.selectbox("🎯 Numero di risultati", options=list(range(1, 11)), index=9, key="num")

    if st.button("🚀 Avvia scraping"):
        if not keyword.strip():
            st.error("Inserisci una keyword valida.")
            return
        with st.spinner(f"Scraping dei primi {num} risultati in {country}..."):
            try:
                items = scrape_google(keyword, COUNTRIES[country], num)
            except Exception as e:
                st.error(f"Errore durante lo scraping: {e}")
                return

        if not items:
            st.warning("Nessun risultato trovato. Potresti essere bloccato o il markup di Google è cambiato.")
            return

        df = pd.DataFrame(items)
        st.dataframe(df, use_container_width=True)

        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Risultati")
            ws = writer.sheets["Risultati"]
            for col_cells in ws.columns:
                length = max(len(str(cell.value)) for cell in col_cells) + 2
                ws.column_dimensions[col_cells[0].column_letter].width = length
        buf.seek(0)

        st.download_button(
            "📥 Scarica XLSX",
            data=buf,
            file_name="google_scraping.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

if __name__ == "__main__":
    main()
