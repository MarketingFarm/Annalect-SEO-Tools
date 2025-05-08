import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO

# Headers per richieste HTTP
BASE_HEADERS = {"User-Agent": "Mozilla/5.0"}

# Funzione per estrarre info SEO
def estrai_info(url: str) -> dict:
    resp = requests.get(url, headers=BASE_HEADERS, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

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

# Funzione main per interfaccia Streamlit
def main():
    st.title("🔍 SEO Extractor")
    st.markdown("Estrai H1, H2, Meta title, Meta description, Canonical e Meta robots.\n" \
                "I campi 'Meta title length' e 'Meta description length' sono sempre inclusi nell'export.")
    st.divider()

    col1, col2 = st.columns([2, 1], gap="large")
    with col1:
        urls = st.text_area(
            "Incolla URL (una per riga)",
            height=200,
            placeholder="https://esempio.com/p1\nhttps://esempio.com/p2"
        )
    with col2:
        # Ottieni chiavi e rimuovi i campi di lunghezza
        sample_info = estrai_info("https://www.example.com")
        example_keys = [k for k in sample_info.keys() if k not in ("Meta title length", "Meta description length")]
        fields = st.pills(
            "Campi da estrarre",
            example_keys,
            selection_mode="multi",
            default=[]
        )

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

        for i, u in enumerate(url_list, 1):
            try:
                info = estrai_info(u)
            except Exception as e:
                info = {k: f"Errore: {e}" for k in sample_info.keys()}

            row = {"URL": u}
            # Aggiungi i campi selezionati
            for f in fields:
                row[f] = info.get(f, "")
            # Aggiungi sempre le lunghezze
            row["Meta title length"] = info.get("Meta title length", 0)
            row["Meta description length"] = info.get("Meta description length", 0)

            results.append(row)
            prog.progress(int(i / len(url_list) * 100))

        st.success(f"Analizzati {len(url_list)} URL.")

        df = pd.DataFrame(results)
        # Riordina colonne: URL, campi selezionati, poi lunghezze
        cols = ["URL"] + fields + ["Meta title length", "Meta description length"]
        df = df[cols]

        st.dataframe(df, use_container_width=True)

        buf = BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        st.download_button(
            "📥 Download XLSX",
            data=buf,
            file_name="estrazione_seo.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# Esegui la pagina
if __name__ == "__main__":
    main()
