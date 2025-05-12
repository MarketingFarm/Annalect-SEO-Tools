import streamlit as st
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import trafilatura
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- INIEZIONE CSS per il bottone rosso ---
st.markdown("""
<style>
button {
  background-color: #e63946 !important;
  color: white !important;
}
</style>
""", unsafe_allow_html=True)

# --- Funzioni di supporto ---

def fetch_sitemap_urls(sitemap_url: str) -> list[str]:
    """
    Scarica e parse la sitemap XML, estraendo tutte le <loc>.
    """
    try:
        resp = requests.get(sitemap_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        return [elem.text for elem in root.findall('.//{*}loc') if elem.text]
    except Exception as e:
        st.error(f"Errore fetching sitemap: {e}")
        return []

def fetch_content(url: str) -> str:
    """
    Scarica la pagina e restituisce solo il main text:
    1) prova con trafilatura.extract (euristiche robuste)
    2) fallback manuale: elimina header/footer/nav/aside/script/style,
       rimuove cookie-bar e tiene paragrafi > 50 caratteri.
    """
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        resp.raise_for_status()
        html = resp.text

        # 1) Tentativo con trafilatura
        text = trafilatura.extract(
            html,
            output_format="text",
            include_comments=False,
            favor_precision=True
        )
        if text and len(text) > 100:
            return text.strip()

        # 2) Fallback manuale
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["header", "footer", "nav", "aside", "script", "style", "noscript", "form"]):
            tag.decompose()

        # Rimuovi cookie-banner via id/class
        for el in soup.find_all(attrs={"class": lambda c: c and "cookie" in c.lower()}):
            el.decompose()
        for el in soup.find_all(attrs={"id": lambda i: i and "cookie" in i.lower()}):
            el.decompose()

        paras = [
            p.get_text(" ", strip=True)
            for p in soup.find_all("p")
            if len(p.get_text(strip=True)) > 50
        ]
        return "\n\n".join(paras).strip() or "[NO CONTENT]"

    except Exception as e:
        return f"[ERROR] {e}"

# --- Streamlit App ---

def main():
    st.title("Duplicate Content Checker – Manuale o Sitemap")
    st.divider()

    # Alert container (in testa)
    msg = st.container()

    # Layout 2 colonne: sinistra più stretta, destra più larga
    left, right = st.columns([1, 5], gap="large")

    # Colonna sinistra: modalità e soglia
    with left:
        mode = st.radio("Modalità di input", ["Manuale", "Sitemap"], index=0)
        threshold = st.slider("Soglia di similarità", 0.0, 1.0, 0.8, 0.01)

    # Inizializza session state per URLs
    if "urls" not in st.session_state:
        st.session_state["urls"] = []

    # Colonna destra: input e pulsante
    with right:
        if mode == "Manuale":
            text = st.text_area(
                "Inserisci gli URL (uno per riga)",
                height=200,
                placeholder="https://esempio.com/p1\nhttps://esempio.com/p2"
            )
            st.session_state["urls"] = [u.strip() for u in text.splitlines() if u.strip()]
        else:
            sitemap_url = st.text_input(
                "URL della sitemap",
                placeholder="https://esempio.com/sitemap.xml"
            )
        run = st.button("Analizza duplicati")

    urls = st.session_state["urls"]

    if run:
        # Se modalita Sitemap, carica automaticamente
        if mode == "Sitemap":
            if not sitemap_url or not sitemap_url.strip():
                msg.error("Per favore inserisci un URL di sitemap valido.")
                return
            with st.spinner("Scaricando sitemap..."):
                st.session_state["urls"] = fetch_sitemap_urls(sitemap_url)
            urls = st.session_state["urls"]
            if not urls:
                msg.warning("Nessun URL trovato o errore nella sitemap.")
                return
            msg.success(f"Trovati {len(urls)} URL nella sitemap.")

        if not urls:
            msg.error("Nessun URL da elaborare. Inserisci o carica gli URL.")
            return

        # 1) Download contenuti
        msg.info("Scaricamento contenuti in corso...")
        p1 = st.progress(0)
        contents = []
        for i, u in enumerate(urls, start=1):
            contents.append(fetch_content(u))
            p1.progress(i / len(urls))
        df = pd.DataFrame({"URL": urls, "Content": contents})

        # 2) TF-IDF e matrice di similarità
        msg.info("Calcolo TF-IDF e matrice di similarità...")
        vect = TfidfVectorizer(stop_words="english")
        tfidf = vect.fit_transform(df["Content"])
        sim_mat = cosine_similarity(tfidf)
        sim_df = pd.DataFrame(sim_mat, index=urls, columns=urls)

        # 3) Individuazione duplicati
        msg.info("Individuazione duplicati...")
        total_pairs = len(urls) * (len(urls) - 1) // 2
        p2 = st.progress(0)
        duplicates = []
        count = 0
        for i in range(len(urls)):
            for j in range(i + 1, len(urls)):
                count += 1
                score = sim_mat[i, j]
                if score >= threshold:
                    duplicates.append({
                        "URL 1": urls[i],
                        "URL 2": urls[j],
                        "Similarity": round(score, 4)
                    })
                p2.progress(count / total_pairs)

        dup_df = pd.DataFrame(duplicates)

        # Risultati
        st.subheader("Risultati duplicati")
        if dup_df.empty:
            st.success(f"Nessun duplicato sopra soglia {threshold}.")
        else:
            st.warning(f"{len(dup_df)} coppie duplicate trovate (≥ {threshold}).")
            st.dataframe(dup_df, use_container_width=True)

        st.subheader("Matrice di similarità completa")
        st.dataframe(sim_df, use_container_width=True)

        st.download_button(
            "Scarica matrice (CSV)",
            sim_df.to_csv().encode("utf-8"),
            file_name="similarity_matrix.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    main()
