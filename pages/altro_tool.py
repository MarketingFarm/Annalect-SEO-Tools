# pages/google_scraper.py

import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO
from urllib.parse import urlparse, parse_qs, unquote

# User-Agent e header per le richieste a Google
BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7"
}

COUNTRIES = {
    "Italia": "it",
    "Stati Uniti": "us",
    "Regno Unito": "uk",
    "Germania": "de",
    "Francia": "fr",
    "Spagna": "es",
    "Brasile": "br",
    "Giappone": "jp",
    "Canada": "ca",
    "India": "in",
}


def scrape_google(keyword: str, country_code: str, num: int) -> list[dict]:
    params = {
        "q": keyword,
        "num": num,
        "hl": "it",
        "gl": country_code,
    }
    resp = requests.get(
        "https://www.google.com/search", headers=BASE_HEADERS, params=params, timeout=10
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    results = []
    # Seleziona i blocchi risultati organici
    for g in soup.select("div#search .g"):  
        h3 = g.select_one("h3")
        if not h3:
            continue
        a = h3.find_parent("a", href=True)
        if not a:
            continue
        href = a["href"]
        # Google a volte ritorna /url?q=<link>&sa=...
        if href.startswith("/url?"):
            qs = parse_qs(urlparse(href).query)
            url = qs.get("q", [href])[0]
        else:
            url = href
        title = h3.get_text(strip=True)
        results.append({"Title": title, "URL": unquote(url)})
        if len(results) >= num:
            break
    return results


def main():
    st.title("🌐 Google Scraper")
    st.markdown(
        "Scrapa i primi risultati organici di Google per keyword e paese."
    )
    st.divider()

    keyword = st.text_input("🔑 Keyword da cercare", placeholder="es. chatbot AI")
    country = st.selectbox("🌍 Seleziona paese", list(COUNTRIES.keys()), index=0)
    num = st.slider("🎯 Numero di risultati", min_value=1, max_value=10, value=5)

    if st.button("🚀 Avvia scraping"):
        if not keyword.strip():
            st.error("Inserisci una keyword valida.")
            st.stop()

        with st.spinner(f"Scraping dei primi {num} risultati in {country}..."):
            try:
                items = scrape_google(keyword, COUNTRIES[country], num)
            except Exception as e:
                st.error(f"Errore durante lo scraping: {e}")
                st.stop()

        if not items:
            st.error("Nessun risultato organico trovato."
                     " Potrebbe essere necessario aumentare il numero di risultati o cambiare paese.")
            st.stop()

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
