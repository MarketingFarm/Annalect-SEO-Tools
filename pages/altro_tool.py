# pages/altro_tool.py

import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- Funzioni di supporto ---

def fetch_content(url: str) -> str:
    """
    Scarica il contenuto testuale di una pagina: unisce tutti i paragrafi.
    Restituisce stringa vuota o messaggio di errore.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text() for p in paragraphs)
        return text.strip()
    except requests.RequestException as e:
        return f"[ERROR {getattr(e, 'response', None) and e.response.status_code or 'REQ'}]"
    except Exception as e:
        return f"[EXCEPTION] {e}"

# --- Interfaccia Streamlit ---

def main():
    st.title("📝 Duplicate Content Checker")
    st.markdown("Carica una lista di URL e individua possibili contenuti duplicati usando TF-IDF + similarità coseno.")
    st.divider()

    # Input URL
    urls_input = st.text_area(
        label="🔗 Inserisci gli URL (uno per riga)",
        value="https://example.com/page1\nhttps://example.com/page2",
        height=200,
        placeholder="Incolla qui gli URL…"
    )

    # Soglia di similarità
    threshold = st.slider(
        label="⚖️ Soglia di similarità",
        min_value=0.0,
        max_value=1.0,
        value=0.8,
        step=0.01
    )

    # Pulsante di analisi
    if st.button("🚀 Analizza duplicati"):
        urls = [u.strip() for u in urls_input.splitlines() if u.strip()]
        if not urls:
            st.error("Per favore inserisci almeno un URL valido.")
            return

        # Download contenuti con progress bar
        st.info("🔍 Download dei contenuti in corso...")
        progress_download = st.progress(0)
        contents = []
        for i, url in enumerate(urls, start=1):
            contents.append(fetch_content(url))
            progress_download.progress(i / len(urls))
        df = pd.DataFrame({"URL": urls, "Content": contents})

        # Calcola TF-IDF e similarità
        st.info("⚙️ Calcolo TF-IDF e matrice di similarità...")
        vect = TfidfVectorizer(stop_words="english")
        tfidf = vect.fit_transform(df["Content"])
        sim_mat = cosine_similarity(tfidf)
        sim_df = pd.DataFrame(sim_mat, index=urls, columns=urls)

        # Estrai duplicati sopra soglia con progress bar
        st.info("🔎 Analisi duplicati...")
        duplicates = []
        total_pairs = sum(1 for i in range(len(urls)) for j in range(i+1, len(urls)))
        progress_dup = st.progress(0)
        pair_count = 0
        for i in range(len(urls)):
            for j in range(i+1, len(urls)):
                score = sim_mat[i, j]
                if score >= threshold:
                    duplicates.append({
                        "URL 1": urls[i],
                        "URL 2": urls[j],
                        "Similarity": round(score, 4)
                    })
                pair_count += 1
                progress_dup.progress(pair_count / total_pairs)

        dup_df = pd.DataFrame(duplicates)

        # Mostra risultati
        st.subheader("📋 Risultati duplicati")
        if dup_df.empty:
            st.success(f"✅ Nessun duplicato sopra la soglia {threshold}.")
        else:
            st.warning(f"⚠️ Trovati {len(dup_df)} coppie con similarità ≥ {threshold}.")
            st.dataframe(dup_df, use_container_width=True)

        st.subheader("📊 Matrice di similarità completa")
        st.dataframe(sim_df, use_container_width=True)

        # Download matrice completa
        csv = sim_df.to_csv().encode('utf-8')
        st.download_button(
            label="📥 Download matrice (CSV)",
            data=csv,
            file_name="similarity_matrix.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    main()
