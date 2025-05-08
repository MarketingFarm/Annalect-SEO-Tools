import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO

# Headers per richieste HTTP
BASE_HEADERS = {"User-Agent": "Mozilla/5.0"}

def estrai_info(url: str) -> dict:
    """
    Estrae H1, H2, meta title, meta description, canonical e meta robots dalla pagina.
    """
    resp = requests.get(url, headers=BASE_HEADERS, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Estraggo elementi
    h1 = soup.find("h1")
    h2s = [h.get_text(strip=True) for h in soup.find_all("h2")]
    title = soup.title
    desc = soup.find("meta", {"name": "description"})
    canonical = soup.find("link", rel="canonical")
    robots = soup.find("meta", {"name": "robots"})

    return {
        "H1": h1.get_text(strip=True) if h1 else "",
        "H2": " | ".join(h2s),
        "Meta title": title.get_text(strip=True) if title else "",
        "Meta title length": len(title.get_text(strip=True)) if title else 0,
        "Meta description": desc["content"].strip() if desc and desc.has_attr("content") else "",
        "Meta description length": len(desc["content"].strip()) if desc and desc.has_attr("content") else 0,
        "Canonical": canonical["href"].strip() if canonical and canonical.has_attr("href") else "",
        "Meta robots": robots["content"].strip() if robots and robots.has_attr("content") else ""
    }


def main():
    # Titolo e descrizione
    st.title("🔍 SEO Extractor")
    st.markdown("Estrai H1, H2, Meta title/length, Meta description/length, Canonical e Meta robots.")
    st.divider()

    # Layout colonne
    col1, col2 = st.columns([2, 1], gap="large")
    with col1:
        urls = st.text_area(
            "Incolla URL (una per riga)",
            height=200,
            placeholder="https://esempio.com/p1\nhttps://esempio.com/p2"
        )
    with col2:
        # Selezione campi da estrarre usando un esempio
        example_keys = list(estrai_info("https://www.example.com").keys())
        fields = st.pills(
            "Campi da estrarre",
            example_keys,
            selection_mode="multi",
            default=[]
        )

    # Avvio estrazione
    if st.button("🚀 Avvia Estrazione"):
        if not fields:
            st.error("Seleziona almeno un campo.")
            return

        url_list = [u.strip() for u in urls.splitlines() if u.strip()]
        if not url_list:
            st.error("Inserisci almeno un URL valido.")
            return

        prog = st.progress(0)
        results = []
        with st.spinner("Analisi in corso…"):
            for i, u in enumerate(url_list, 1):
                try:
                    info = estrai_info(u)
                except Exception as e:
                    info = {k: f"Errore: {e}" for k in example_keys}
                row = {"URL": u}
                for f in fields:
                    row[f] = info.get(f, "")
                results.append(row)
                prog.progress(int(i / len(url_list) * 100))

        st.success(f"Analizzati {len(url_list)} URL.")
        st.balloons()

        # Mostro DataFrame
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)

        # Bottone per download Excel
        buf = BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        st.download_button(
            "📥 Download XLSX",
            data=buf,
            file_name="estrazione_seo.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


# Esegui main solo quando importato come pagina
if __name__ == "__page__":
    main()
