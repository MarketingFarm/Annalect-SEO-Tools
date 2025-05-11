import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ----- Funzioni core -----

def fetch_content(url):
    """Scarica e restituisce il testo visibile (<p>) di una pagina."""
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            paragraphs = soup.find_all("p")
            text = " ".join(p.get_text() for p in paragraphs)
            return text.strip()
        else:
            return f"[ERROR {resp.status_code}]"
    except Exception as e:
        return f"[EXCEPTION] {e}"

def analyze_duplicates(urls, threshold):
    """Dato un elenco di URL e una soglia, torna DataFrame duplicati e matrice di similarità."""
    df = pd.DataFrame({"URL": urls})
    df["Content"] = df["URL"].apply(fetch_content)

    vect = TfidfVectorizer(stop_words="english")
    tfidf = vect.fit_transform(df["Content"])
    sim_mat = cosine_similarity(tfidf)

    # Crea lista di duplicati sopra soglia
    duplicates = []
    for i in range(len(df)):
        for j in range(i+1, len(df)):
            score = sim_mat[i, j]
            if score >= threshold:
                duplicates.append({
                    "URL 1": df.at[i, "URL"],
                    "URL 2": df.at[j, "URL"],
                    "Similarity": round(score, 4)
                })
    dup_df = pd.DataFrame(duplicates)
    sim_df = pd.DataFrame(sim_mat, index=df["URL"], columns=df["URL"])
    return dup_df, sim_df

def to_excel_bytes(df: pd.DataFrame) -> bytes:
    """Serializza un DataFrame in un file Excel in memoria."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Duplicates")
        ws = writer.sheets["Duplicates"]
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            ws.column_dimensions[chr(65 + i)].width = min(max_len, 50)
    buf.seek(0)
    return buf.getvalue()

# ----- Interfaccia Streamlit -----

st.set_page_config(
    page_title="Duplicate Content Audit",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🕵️‍♀️ Duplicate Content Audit Tool")
st.markdown("""
Inserisci una lista di URL (uno per riga) nel form qui sotto e scegli la soglia 
di similarità (TF-IDF + Cosine) per individuare contenuti duplicati o troppo simili.
""")

# Sidebar: soglia e info
st.sidebar.header("Impostazioni")
threshold = st.sidebar.slider(
    "Soglia di similarità",
    min_value=0.0,
    max_value=1.0,
    value=0.8,
    step=0.01,
    help="Valori vicini a 1 richiedono testi quasi identici."
)
st.sidebar.markdown("© 2025 by il tuo nome")

# Main form
urls_input = st.text_area(
    "⤵️ Incolla qui i tuoi URL (uno per riga)",
    height=150,
    placeholder="https://tuosito.it/pagina1\nhttps://tuosito.it/pagina2\n..."
)

if st.button("🔍 Analizza duplicati"):
    urls = [u.strip() for u in urls_input.splitlines() if u.strip()]
    if not urls:
        st.error("Per favore, inserisci almeno un URL valido.")
    else:
        with st.spinner("Analizzo i contenuti…"):
            dup_df, sim_df = analyze_duplicates(urls, threshold)

        if dup_df.empty:
            st.success(f"Nessun duplicato trovato sopra la soglia {threshold}")
        else:
            st.warning(f"Trovate {len(dup_df)} coppie di potenziali duplicati:")
            st.dataframe(dup_df, use_container_width=True)

            # Download CSV
            csv = dup_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Scarica CSV dei duplicati",
                data=csv,
                file_name="duplicate_content.csv",
                mime="text/csv"
            )

            # Download Excel
            xlsx = to_excel_bytes(dup_df)
            st.download_button(
                label="📥 Scarica Excel dei duplicati",
                data=xlsx,
                file_name="duplicate_content.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        # Mostra matrice completa
        with st.expander("📊 Mostra matrice di similarità completa"):
            st.dataframe(sim_df, use_container_width=True)
