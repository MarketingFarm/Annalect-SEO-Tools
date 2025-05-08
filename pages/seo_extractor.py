import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO

# User-Agent per le richieste
BASE_HEADERS = {"User-Agent": "Mozilla/5.0"}

def estrai_info(url: str) -> dict:
    """
    Fa GET via requests, parsea con BeautifulSoup e restituisce
    dizionario con H1–H4, Meta title/description, canonical e robots.
    """
    resp = requests.get(url, headers=BASE_HEADERS, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Selezione del main content (fallback su body)
    content = (
        soup.find("main")
        or soup.find("article")
        or soup.find("div", id="content")
        or soup.find("div", class_="entry-content")
        or soup.find("div", class_="post-body")
        or soup.find("body")
        or soup
    )

    # Estrazione headings
    h1 = content.find("h1")
    h2s = [h.get_text(strip=True) for h in content.find_all("h2")]
    h3s = [h.get_text(strip=True) for h in content.find_all("h3")]
    h4s = [h.get_text(strip=True) for h in content.find_all("h4")]

    # Meta SEO globali
    title_tag = soup.title
    desc = soup.find("meta", {"name": "description"})
    canonical = soup.find("link", rel="canonical")
    robots = soup.find("meta", {"name": "robots"})

    return {
        "H1": h1.get_text(strip=True) if h1 else "",
        "H2": " | ".join(h2s),
        "H3": " | ".join(h3s),
        "H4": " | ".join(h4s),
        "Meta title": title_tag.get_text(strip=True) if title_tag else "",
        "Meta title length": len(title_tag.get_text(strip=True)) if title_tag else 0,
        "Meta description": desc["content"].strip() if desc and desc.has_attr("content") else "",
        "Meta description length": len(desc["content"].strip()) if desc and desc.has_attr("content") else 0,
        "Canonical": canonical["href"].strip() if canonical and canonical.has_attr("href") else "",
        "Meta robots": robots["content"].strip() if robots and robots.has_attr("content") else ""
    }

def main():
    st.title("🔍 SEO Extractor")
    st.markdown(
        "Estrai H1–H4 dal contenuto principale (main/article), più "
        "Meta title/description, Canonical e Meta robots."
    )
    st.divider()

    col1, col2 = st.columns([2, 1], gap="large")
    with col1:
        urls = st.text_area(
            "Incolla URL (uno per riga)",
            height=200,
            placeholder="https://esempio.com/p1\nhttps://esempio.com/p2"
        )
    with col2:
        example = estrai_info("https://www.example.com")
        # Mostra solo i campi base (senza *length) nel menu
        fields = st.pills(
            "Campi da estrarre",
            [k for k in example.keys() if not k.endswith("length")],
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
                info = {k: (f"Errore: {e}" if not k.endswith("length") else 0)
                        for k in example.keys()}

            row = {"URL": u}
            # Aggiungi campi scelti
            for f in fields:
                row[f] = info.get(f, "")
            # Aggiungi lunghezze solo se selezionate
            if "Meta title" in fields:
                row["Meta title length"] = info["Meta title length"]
            if "Meta description" in fields:
                row["Meta description length"] = info["Meta description length"]

            results.append(row)
            prog.progress(int(i / len(url_list) * 100))

        st.success(f"Analizzati {len(results)} URL.")
        df = pd.DataFrame(results)
        # Riorganizza colonne: URL, selezionati, e lunghezze
        cols = ["URL"] + fields
        if "Meta title" in fields: cols.append("Meta title length")
        if "Meta description" in fields: cols.append("Meta description length")
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

if __name__ == "__main__":
    main()
