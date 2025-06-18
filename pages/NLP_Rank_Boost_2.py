import streamlit as st
import json
import pandas as pd
from io import StringIO

# La configurazione della pagina è già gestita nel file principale

st.title("📝 Analisi e Scrittura Contenuti SEO")
st.markdown(
    """
    In questa pagina puoi caricare il JSON generato dalla pagina di raccolta dati SEO,
    e selezionare direttamente le singole keywords dalla tabella di Keyword Mining.
    """
)

# Step 1: caricamento del file JSON
uploaded_file = st.file_uploader(
    "1. Carica il file JSON di export SEO",
    type="json",
    help="Carica qui il file JSON generato dalla pagina precedente"
)

if uploaded_file:
    try:
        data = json.load(uploaded_file)
    except json.JSONDecodeError as e:
        st.error(f"❌ Errore nel parsing del JSON: {e}")
        st.stop()

    # Mostro il JSON intero in un expander
    st.subheader("📂 Dati SEO Importati")
    with st.expander("Espandi per visualizzare il JSON completo"):
        st.json(data)

    # Estraggo la tabella di Keyword Mining dal JSON
    table_str = data.get("keyword_mining", "")
    lines = [line for line in table_str.split("\n") if line.strip()]
    if len(lines) >= 3:
        # Header e skip della riga di allineamento
        data_lines = lines[2:]
        rows = []
        for line in data_lines:
            parts = [cell.strip() for cell in line.split("|") if cell.strip()]
            if len(parts) == 3:
                rows.append(parts)  # [Categoria, Keywords stringa, Intento]

        st.subheader("🔍 Seleziona le singole keywords per l'analisi")
        selected_keywords = {}

        for categoria, keywords_str, intento in rows:
            keywords_list = [kw.strip(" `") for kw in keywords_str.split(",")]
            st.markdown(f"**{categoria}**  _(Intento: {intento})_")
            cols = st.columns([1, 9])
            chosen = []
            for kw in keywords_list:
                checked = cols[0].checkbox("", value=True, key=f"chk_{categoria}_{kw}")
                # Mostro la keyword senza elenco puntato
                cols[1].write(kw)
                if checked:
                    chosen.append(kw)
            selected_keywords[categoria] = chosen

        st.subheader("✅ Keywords selezionate")
        st.json(selected_keywords)

    else:
        st.warning("⚠️ Non ho trovato una tabella di Keyword Mining nel JSON.")

else:
    st.info("⏳ Carica un file JSON per procedere con l'analisi.")
