import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO

# Proviamo a importare Playwright per rendering JS più affidabile
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

# Headers per richieste HTTP
BASE_HEADERS = {"User-Agent": "Mozilla/5.0"}

# Funzione per ottenere HTML, con render JS se possibile
def fetch_html(url: str) -> str:
    if HAS_PLAYWRIGHT:
        # Usa Playwright per caricare interamente la pagina e attendere network idle
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(
                user_agent=BASE_HEADERS["User-Agent"],
                viewport={"width": 1280, "height": 800}
            )
            page.goto(url, wait_until="networkidle")
            html = page.content()
            browser.close()
            return html
    else:
        # Fallback a requests
        resp = requests.get(url, headers=BASE_HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.text

# Funzione per estrarre info SEO dal contenuto principale
def estrai_info(url: str) -> dict:
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    # Selettori contenuto principale comuni
    content = (
        soup.find("main")
        or soup.find("article")
        or soup.find("div", id="content")
        or soup.find("div", class_="entry-content")
        or soup.find("div", class_="post-body")
        or soup.find("body")
        or soup
    )

    # Estrai headings
    h1_tag = content.find("h1")
    h2s = [h.get_text(strip=True) for h in content.find_all("h2")]
    h3s = [h.get_text(strip=True) for h in content.find_all("h3")]
    h4s = [h.get_text(strip=True) for h in content.find_all("h4")]

    # Meta dati
    title_tag = soup.title
    desc = soup.find("meta", {"name": "description"})
    canonical = soup.find("link", rel="canonical")
    robots = soup.find("meta", {"name": "robots"})

    return {
        "H1": h1_tag.get_text(strip=True) if h1_tag else "",
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

# Interfaccia Streamlit
def main():
    st.title("🔍 SEO Extractor con Playwright JS Rendering")
    if not HAS_PLAYWRIGHT:
        st.warning("Per estrarre contenuti caricati via JS installa `playwright` e aggiungi `playwright install chromium` alle dipendenze.")
    st.markdown(
        "Estrai H1–H4 dal contenuto principale, anche se generato post-hydration, e Meta title/description.\n"
        "Le colonne 'length' vengono incluse solo se selezionati i rispettivi campi."
    )
    st.divider()

    col1, col2 = st.columns([2, 1], gap="large")
    with col1:
        urls = st.text_area(
            "Incolla URL (una per riga)",
            height=200,
            placeholder="https://esempio.com/p1\nhttps://esempio.com/p2"
        )
    with col2:
        sample_info = estrai_info("https://www.example.com")
        base_keys = [k for k in sample_info.keys() if not k.endswith("length")]
        fields = st.pills(
            "Campi da estrarre",
            base_keys,
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
                info = {k: (f"Errore: {e}" if not k.endswith("length") else 0) for k in sample_info.keys()}
            row = {"URL": u}
            for f in fields:
                row[f] = info.get(f, "")
            if "Meta title" in fields:
                row["Meta title length"] = info.get("Meta title length", 0)
            if "Meta description" in fields:
                row["Meta description length"] = info.get("Meta description length", 0)
            results.append(row)
            prog.progress(int(i / len(url_list) * 100))

        st.success(f"Analizzati {len(url_list)} URL.")
        df = pd.DataFrame(results)
        cols = ["URL"] + fields
        if "Meta title" in fields:
            cols.append("Meta title length")
        if "Meta description" in fields:
            cols.append("Meta description length")
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
