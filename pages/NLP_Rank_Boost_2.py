import streamlit as st
import json

st.set_page_config(page_title="Analisi e Scrittura Contenuti SEO", layout="wide")

# Titolo della pagina
st.title("📝 Analisi e Scrittura Contenuti SEO")
st.markdown(
    """
    In questa pagina puoi caricare il JSON generato dalla pagina di raccolta dati SEO,
    selezionare quali informazioni utilizzare per l'analisi e preparare i testi.
    """
)

# Step 1: caricamento del file JSON
uploaded_file = st.file_uploader(
    "1. Carica il file JSON di export SEO",
    type="json",
    help="Carica qui il file JSON generato dalla pagina precedente"
)

if uploaded_file is not None:
    # Step 2: parsing del JSON
    try:
        data = json.load(uploaded_file)
    except json.JSONDecodeError as e:
        st.error(f"❌ Errore nel parsing del JSON: {e}")
        st.stop()

    # Mostra struttura del JSON
    st.subheader("📂 Struttura del JSON caricato")
    st.json(data)

    # Step 3: selezione delle informazioni da importare
    st.subheader("2. Seleziona le informazioni da importare per l'analisi")
    keys = list(data.keys())
    selected = st.multiselect(
        "Scegli le chiavi del JSON da includere",
        options=keys,
        default=keys
    )

    # Step 4: visualizzazione dei dati selezionati
    st.subheader("📑 Dati selezionati")
    for key in selected:
        st.markdown(f"**{key}**")
        st.write(data[key])

    # (In futuro qui potrai aggiungere altri step per l'analisi e la generazione del testo)

else:
    st.info("⏳ Carica un file JSON per procedere con l'analisi.")
