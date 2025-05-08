import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO

# User-Agent per le richieste a Google
BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/115.0.0.0 Safari/537.36"
}

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
    Esegue una query su Google con parametro gl (geolocalizzazione),
    restituisce una lista di dict con 'Title' e 'URL' dei risultati organici.
    """
    params = {"q": keyword, "num": num, "hl": "it", "gl": country_code}
    resp = requests.get(
        "https://www.google.com/search",
        headers=BASE_HEADERS,
        params=params,
        timeout=10
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for h3 in soup.find_all("h3"):
        a = h3.find_parent("a")
        if a and a.has_attr("href"):
            results.append({"Title": h3.get_text(strip=True), "URL": a["href"]})
            if len(results) >= num:
                break
    return results


def main():
    st.title("🌐 Google Scraper")
    st.markdown("Scrapa i primi risultati organici di Google per keyword e paese.")
    st.divider()

    # Widgets: usando key per mantenere valore tra rerun
    col1, col2, col3 = st.columns(3, gap="small")
    with col1:
        keyword = st.text_input(
            "🔑 Keyword da cercare",
            placeholder="es. chatbot AI",
            key="keyword"
        )
    with col2:
        country = st.selectbox(
            "🌍 Seleziona paese",
            ALL_COUNTRIES,
            index=ALL_COUNTRIES.index("Italia"),
            key="country"
        )
    with col3:
        num = st.selectbox(
            "🎯 Numero di risultati",
            options=list(range(1, 11)),
            index=9,  # default 10
            key="num"
        )

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
            st.warning("Nessun risultato trovato.")
            return

        # DataFrame e tabella
        df = pd.DataFrame(items)
        st.dataframe(df, use_container_width=True)

        # Preparazione Excel
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
