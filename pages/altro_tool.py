import streamlit as st
import pandas as pd
from io import BytesIO
import time

# Import dei parser SERP da cartella parserp
from pages.parserp.inline_shopping import parse_inline_shopping
from parserp.organic_results import parse_organic_results
from parserp.paa_results import parse_paa_results
from parserp.related_searches import parse_related_searches

# Configurazione delle pagine e lingua
PAESI_GOOGLE = {
    "Italia": ("google.it", "it"),
    "Stati Uniti": ("google.com", "en"),
    "Regno Unito": ("google.co.uk", "en"),
    "Francia": ("google.fr", "fr"),
    "Germania": ("google.de", "de"),
    "Spagna": ("google.es", "es"),
}

# Funzione principale di scraping SERP
@st.cache_data(show_spinner=False)
def scrape_serp(keyword: str, domain: str, hl: str, num: int):
    """
    Fa richiesta a Google SERP e restituisce un dict:
    - inline_shopping
    - organic_results
    - paa_results
    - related_searches
    """
    url = (
        f"https://{domain}/search?q={keyword.replace(' ', '+')}"
        f"&hl={hl}&num={num}&pws=0&filter=0"
    )
    # Richiesta HTTP
    import requests
    resp = requests.get(url, headers={"User-Agent": st.secrets.get('USER_AGENT', '')})
    resp.raise_for_status()
    html = resp.text

    # Parsing con moduli dedicati
    inline = parse_inline_shopping(html)
    organic = parse_organic_results(html)
    paa = parse_paa_results(html)
    related = parse_related_searches(html)

    return {
        "inline_shopping": inline,
        "organic_results": organic,
        "paa_results": paa,
        "related_searches": related
    }

# Streamlit UI
st.set_page_config(page_title="Google SERP Parser", layout="wide")

def main():
    st.title("🔎 Google SERP Parser")
    st.markdown("Esegui scraping e parsing della SERP di Google usando moduli dedicati.")

    col1, col2, col3 = st.columns(3)
    with col1:
        keyword = st.text_input("Keyword", "chatbot AI")
    with col2:
        paese = st.selectbox("Paese", list(PAESI_GOOGLE.keys()), index=0)
    with col3:
        num = st.slider("Risultati", 1, 10, 5)

    if st.button("Avvia scraping"):
        domain, hl = PAESI_GOOGLE[paese]
        start = time.time()
        try:
            data = scrape_serp(keyword, domain, hl, num)
        except Exception as e:
            st.error(f"Errore scraping: {e}")
            return
        elapsed = time.time() - start
        st.success(f"Completed in {elapsed:.2f}s")

        # Mostra tabelle
        st.subheader("Organic Results")
        df_org = pd.DataFrame(data['organic_results'])
        st.dataframe(df_org)

        st.subheader("People Also Ask")
        df_paa = pd.DataFrame(data['paa_results'])
        st.dataframe(df_paa)

        st.subheader("Related Searches")
        df_rel = pd.DataFrame(data['related_searches'])
        st.dataframe(df_rel)

        if data['inline_shopping']:
            st.subheader("Inline Shopping")
            df_shop = pd.DataFrame(data['inline_shopping'])
            st.dataframe(df_shop)

        # Download Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_org.to_excel(writer, index=False, sheet_name='Organic')
            df_paa.to_excel(writer, index=False, sheet_name='PAA')
            df_rel.to_excel(writer, index=False, sheet_name='Related')
            if data['inline_shopping']:
                df_shop.to_excel(writer, index=False, sheet_name='Shopping')
        output.seek(0)
        st.download_button("Download XLSX", data=output.getvalue(), file_name="serp_data.xlsx")

if __name__ == '__main__':
    main()
