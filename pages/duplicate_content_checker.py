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
        urls = [elem.text for elem in root.findall('.//{*}loc') if elem.text]
        return urls
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
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text() for p in paragraphs)
        return text.strip()
    except Exception as e:
        return f"[ERROR] {e}"

# --- Interfaccia Streamlit ---

def main():
    st.title("Duplicate Content Checker – Manuale o da Sitemap")
    st.markdown("Scegli se inserire manualmente gli URL o fornire l'URL di una sitemap XML.")
    st.divider()

    # Layout a due colonne con gap aumentato
    left_col, right_col = st.columns([1, 3], gap="large")

    # Colonna sinistra: modalità e soglia
    with left_col:
        mode = st.radio(
            label="Modalità di input",
            options=["Manuale", "Sitemap"],
            index=0
        )
        threshold = st.slider(
            label="Soglia di similarità",
            min_value=0.0,
            max_value=1.0,
            value=0.8,
            step=0.01
        )

    # Colonna destra: input dinamico e pulsante
    urls = []
    with right_col:
        if mode == "Manuale":
            input_text = st.text_area(
                label="Inserisci gli URL (uno per riga)",
                height=200,
                placeholder="https://example.com/page1\nhttps://example.com/page2"
            )
            urls = [u.strip() for u in input_text.splitlines() if u.strip()]
        else:
            sitemap_url = st.text_input(
                label="URL della sitemap",
                placeholder="https://example.com/sitemap.xml"
            )
            if st.button("Carica sitemap"):
                if not sitemap_url.strip():
                    st.error("Per favore inserisci un URL di sitemap valido.")
                else:
                    with st.spinner("Scaricando e parsando sitemap..."):
                        urls = fetch_sitemap_urls(sitemap_url)
                    if urls:
                        st.success(f"Trovati {len(urls)} URL nella sitemap.")
                    else:
                        st.warning("Nessun URL trovato o errore nella sitemap.")
        st.button("Analizza duplicati", key="run", use_container_width=True)

    # Bottone e logica di analisi
    if st.session_state.get("run") is not None:
        st.session_state.pop("run")
        if not urls:
            st.error("Nessun URL da elaborare. Assicurati di aver caricato o inserito gli URL.")
            return

        # Fase 1: scaricamento contenuti
        st.info("Scaricamento contenuti in corso...")
        progress_fetch = st.progress(0)
        contents = []
        for idx, url in enumerate(urls, start=1):
            contents.append(fetch_content(url))
            progress_fetch.progress(idx / len(urls))
        df = pd.DataFrame({"URL": urls, "Content": contents})

        # Fase 2: TF-IDF
        st.info("Calcolo TF-IDF e matrice di similarità...")
        vect = TfidfVectorizer(stop_words='english')
        tfidf = vect.fit_transform(df['Content'])
        sim_mat = cosine_similarity(tfidf)
        sim_df = pd.DataFrame(sim_mat, index=urls, columns=urls)

        # Fase 3: individuazione duplicati
        st.info("Individuazione duplicati in corso...")
        duplicates = []
        total_pairs = len(urls) * (len(urls) - 1) / 2
        progress_dup = st.progress(0)
        count = 0
        for i in range(len(urls)):
            for j in range(i+1, len(urls)):
                score = sim_mat[i, j]
                if score >= threshold:
                    duplicates.append({
                        'URL 1': urls[i],
                        'URL 2': urls[j],
                        'Similarity': round(score, 4)
                    })
                count += 1
                progress_dup.progress(count / total_pairs)
        dup_df = pd.DataFrame(duplicates)

        # Visualizzazione risultati
        st.subheader("Risultati duplicati")
        if dup_df.empty:
            st.success(f"Nessun duplicato sopra {threshold}.")
        else:
            st.warning(f"{len(dup_df)} coppie duplicate trovate (≥ {threshold}).")
            st.dataframe(dup_df, use_container_width=True)

        st.subheader("Matrice di similarità completa")
        st.dataframe(sim_df, use_container_width=True)

        # Download CSV
        st.download_button(
            label="Scarica matrice (CSV)",
            data=sim_df.to_csv().encode('utf-8'),
            file_name='similarity_matrix.csv',
            mime='text/csv'
        )

if __name__ == '__main__':
    main()
