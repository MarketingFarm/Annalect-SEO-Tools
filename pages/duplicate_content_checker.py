import streamlit as st
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
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
    """Scarica e parse la sitemap, estraendo tutte le <loc>."""
    try:
        resp = requests.get(sitemap_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        return [elem.text for elem in root.findall('.//{*}loc') if elem.text]
    except Exception as e:
        st.error(f"Errore fetching sitemap: {e}")
        return []

def fetch_content(url: str) -> str:
    """Scarica la pagina e restituisce il testo concatenato di tutti i <p>."""
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        return " ".join(p.get_text() for p in soup.find_all("p")).strip()
    except Exception as e:
        return f"[ERROR] {e}"

# --- Streamlit App ---

def main():
    st.title("Duplicate Content Checker – Manuale o Sitemap")
    st.divider()

    # Alert container posizionato in alto
    msg_container = st.container()

    # Layout a due colonne: sinistra 1/5, destra 4/5
    left, right = st.columns([1, 5], gap="large")

    # Colonna sinistra: modalità e soglia
    with left:
        mode = st.radio("Modalità di input", ["Manuale", "Sitemap"], index=0)
        threshold = st.slider("Soglia di similarità", 0.0, 1.0, 0.8, 0.01)

    # Inizializza session_state per gli URL
    if "urls" not in st.session_state:
        st.session_state["urls"] = []

    # Colonna destra: input + unico bottone
    with right:
        if mode == "Manuale":
            text = st.text_area(
                "Inserisci gli URL (uno per riga)",
                height=200,
                placeholder="https://esempio.com/p1\nhttps://esempio.com/p2"
            )
            st.session_state["urls"] = [
                u.strip() for u in text.splitlines() if u.strip()
            ]
        else:
            sitemap_url = st.text_input(
                "URL della sitemap",
                placeholder="https://esempio.com/sitemap.xml"
            )

        run = st.button("Analizza duplicati", key="run")

    urls = st.session_state["urls"]

    if run:
        # Se siamo in modalità sitemap, carichiamo gli URL automaticamente
        if mode == "Sitemap":
            if not sitemap_url or not sitemap_url.strip():
                msg_container.error("Per favore inserisci un URL di sitemap valido.")
                return
            with st.spinner("Scaricando sitemap..."):
                st.session_state["urls"] = fetch_sitemap_urls(sitemap_url)
            urls = st.session_state["urls"]
            if not urls:
                msg_container.warning("Nessun URL trovato o errore nella sitemap.")
                return
            else:
                msg_container.success(f"Trovati {len(urls)} URL nella sitemap.")

        # A questo punto 'urls' contiene la lista da processare
        if not urls:
            msg_container.error("Nessun URL da elaborare. Inserisci o carica gli URL.")
            return

        # 1) Download contenuti
        msg_container.info("Scaricamento contenuti in corso...")
        p1 = st.progress(0)
        contents = []
        for i, u in enumerate(urls, start=1):
            contents.append(fetch_content(u))
            p1.progress(i / len(urls))
        df = pd.DataFrame({"URL": urls, "Content": contents})

        # 2) Calcolo TF-IDF e matrice di similarità
        msg_container.info("Calcolo TF-IDF e matrice di similarità...")
        vect = TfidfVectorizer(stop_words="english")
        tfidf = vect.fit_transform(df["Content"])
        sim_mat = cosine_similarity(tfidf)
        sim_df = pd.DataFrame(sim_mat, index=urls, columns=urls)

        # 3) Individuazione duplicati
        msg_container.info("Individuazione duplicati...")
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
