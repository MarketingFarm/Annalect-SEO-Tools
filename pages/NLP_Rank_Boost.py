import streamlit as st
import os
from google import genai

# --- INIEZIONE CSS per il bottone rosso e wrap testo nelle tabelle ---
st.markdown("""
<style>
button {
  background-color: #e63946 !important;
  color: white !important;
}
/* wrap table cells */
table td {
  white-space: normal !important;
}
</style>
""", unsafe_allow_html=True)

# --- Config Gemini ---
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

st.title("Analisi Competitiva & Content Gap con Gemini")
st.divider()

# Selezione numero di testi competitor (max 5)
num_texts = st.selectbox(
    "Numero di testi competitor da analizzare (su 5 max)",
    list(range(1,6)), index=0
)

# Disposizione orizzontale dei text_area
cols = st.columns(num_texts)
texts = []
for i, col in enumerate(cols, 1):
    with col:
        t = st.text_area(f"Testo competitor {i}", height=200)
        texts.append(t.strip())

if st.button("Analizza Contenuti 🚀"):
    competitor_texts = [t for t in texts if t]
    if not competitor_texts:
        st.error("Per favore, incolla almeno un testo da competitor.")
        st.stop()

    full_text = "\n---\n".join(competitor_texts)
    prompt = f"""
## PROMPT DI ANALISI COMPETITIVA E CONTENT GAP ##

**RUOLO:**
Agisci come un analista SEO d'élite, specializzato in analisi semantica competitiva.

**CONTESTO:**
Obiettivo: superare i competitor posizionati per la keyword target. Fornisci le entità da includere e le opportunità di content gap.

**COMPITO:**
Analizza i seguenti testi competitor:
{full_text}

1. Identifica l'**Argomento Principale Comune** e il **Search Intent Primario**.
2. Crea **due tabelle Markdown**:

---
### TABELLA 1: ENTITÀ FONDAMENTALI (Common Ground Analysis)
| Entità | Rilevanza Strategica | Azione per il Mio Testo |
| :--- | :--- | :--- |
# (Compila con le entità viste nei testi)

---
### TABELLA 2: ENTITÀ MANCANTI (Content Gap Opportunity)
| Entità da Aggiungere | Motivazione dell'Inclusione | Azione SEO Strategica |
| :--- | :--- | :--- |
# (Compila con entità mancanti nei testi)

Arricchisci la colonna "Entità" con esempi specifici tra parentesi.
Nella prima riga inserisci sempre l'entità principale.
Mantieni solo le due tabelle, con markdown valido e wrap del testo.
"""
    with st.spinner("Analisi in corso con Gemini..."):
        resp = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[prompt]
        )
    md = resp.text

    # Estrai blocchi Markdown di tabelle
    tables = [blk for blk in md.split("\n\n") if blk.strip().startswith("|")]
    if not tables:
        st.warning("Non sono state generate tabelle valide.")
        st.stop()

    # Mostra tabelle con st.markdown per preservare grassetto e wrap
    st.subheader("Entità Fondamentali (Common Ground Analysis)")
    st.markdown(tables[0], unsafe_allow_html=True)

    if len(tables) > 1:
        st.subheader("Entità Mancanti (Content Gap Opportunity)")
        st.markdown(tables[1], unsafe_allow_html=True)
    else:
        st.info("Seconda tabella non trovata.")
