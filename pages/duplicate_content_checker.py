# pages/altro_tool.py

import streamlit as st
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import time
import random

# --- Funzioni di supporto ---

def fetch_sitemap_urls(sitemap_url: str) -> list:
    """
    Scarica e fa parse di una sitemap XML per estrarre tutti gli URL.
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
    Scarica il contenuto testuale di una pagina: unisce tutti i paragrafi.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        text = " ".join(p.get_text() for p in soup.find_all("p"))
        return text.strip()
    except Exception as e:
        return f"[ERROR] {e}"

# --- Streamlit App ---

def main():
    st.title("Duplicate Content Checker – Manuale o da Sitemap")
    st.markdown("Scegli se inserire manualmente gli URL o fornire l'URL di una sitemap XML.")
    st.divider()

    # CSS per bottoni: Analizza duplicati rosso, Carica sitemap trasparente con bordo rosso
    st.markdown("""
    <style>
    div.stButton > button { background-color: #d9534f; color: white; border: none; }
    div.stButton > button:hover { background-color: #c9302c; color: white; }
    button[title="sitemap"] { background-color: transparent !important; color: #d9534f !important; border: 1px solid #d9534f !important; }
    button[title="sitemap"]:hover { background-color: rgba(217,83,79,0.1) !important; }
    div.stButton > button:hover { background-color: #c9302c; color: white; }
    button[aria-label="Carica sitemap"] {
        background-color: transparent !important;
        color: #d9534f !important;
        border: 1px solid #d9534f !important;
    }
    button[aria-label="Carica sitemap"]:hover {
        background-color: rgba(217,83,79,0.1) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Container per alert in cima
    msg_container = st.container()

    # Layout a due colonne (sinistra 1/5, destra 4/5) con gap largo
    left_col, right_col = st.columns([1, 5], gap="large")

    # Colonna sinistra: scelta modalità & soglia
    with left_col:
        mode = st.radio("Modalità di input", ["Manuale", "Sitemap"], index=0)
        threshold = st.slider("Soglia di similarità", 0.0, 1.0, 0.8, 0.01)

    # Inizializza session state per gli URL
    if 'urls' not in st.session_state:
        st.session_state['urls'] = []

    # Colonna destra: input e bottoni in linea
    with right_col:
        if mode == "Manuale":
            text = st.text_area("Inserisci gli URL (uno per riga)", height=200,
                                placeholder="https://example.com/page1\nhttps://example.com/page2")
            st.session_state['urls'] = [u.strip() for u in text.splitlines() if u.strip()]
            # Solo bottone Analizza
            run_click = st.button("Analizza duplicati", use_container_width=True)
            load_click = False
        else:
            sitemap_url = st.text_input("URL della sitemap", placeholder="https://example.com/sitemap.xml")
            # Due bottoni inline
            col1, col2 = st.columns([1,1])
            with col1:
                load_click = st.button("Carica sitemap")
            with col2:
                run_click = st.button("Analizza duplicati")
            if load_click:
                if not sitemap_url.strip():
                    msg_container.error("Per favore inserisci un URL di sitemap valido.")
                else:
                    with st.spinner("Scaricando e parsando sitemap..."):
                        st.session_state['urls'] = fetch_sitemap_urls(sitemap_url)
                    if st.session_state['urls']:
                        msg_container.success(f"Trovati {len(st.session_state['urls'])} URL nella sitemap.")
                    else:
                        msg_container.warning("Nessun URL trovato o errore nella sitemap.")

    urls = st.session_state['urls']

    # Esegui analisi se cliccato Analizza
    if run_click:
        if not urls:
            msg_container.error("Nessun URL da elaborare. Inserisci o carica gli URL.")
            return

        # 1) Download contenuti
        st.info("Scaricamento contenuti in corso...")
        progress1 = st.progress(0)
        contents = []
        for i, u in enumerate(urls, 1):
            contents.append(fetch_content(u))
            progress1.progress(i / len(urls))
        df = pd.DataFrame({"URL": urls, "Content": contents})

        # 2) TF-IDF + similarità
        st.info("Calcolo TF-IDF e matrice di similarità...")
        vect = TfidfVectorizer(stop_words='english')
        tfidf = vect.fit_transform(df['Content'])
        sim_mat = cosine_similarity(tfidf)
        sim_df = pd.DataFrame(sim_mat, index=urls, columns=urls)

        # 3) Individuazione duplicati
        st.info("Individuazione duplicati...")
        progress2 = st.progress(0)
        duplicates = []
        total = len(urls) * (len(urls) - 1) / 2
        cnt = 0
        for i in range(len(urls)):
            for j in range(i+1, len(urls)):
                score = sim_mat[i, j]
                if score >= threshold:
                    duplicates.append({"URL 1": urls[i], "URL 2": urls[j], "Similarity": round(score, 4)})
                cnt += 1
                progress2.progress(cnt / total)
        dup_df = pd.DataFrame(duplicates)

        # Risultati
        st.subheader("Risultati duplicati")
        if dup_df.empty:
            st.success(f"Nessun duplicato sopra {threshold}.")
        else:
            st.warning(f"{len(dup_df)} coppie duplicate trovate (≥ {threshold}).")
            st.dataframe(dup_df, use_container_width=True)

        st.subheader("Matrice di similarità completa")
        st.dataframe(sim_df, use_container_width=True)

        st.download_button("Scarica matrice (CSV)", sim_df.to_csv().encode('utf-8'),
                           file_name='similarity_matrix.csv', mime='text/csv')

if __name__ == '__main__':
    main()
