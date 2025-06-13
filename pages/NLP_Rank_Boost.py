import streamlit as st
import pandas as pd
import os
from google import genai

# --- INIEZIONE CSS per il bottone rosso ---
st.markdown("""
<style>
button {
  background-color: #e63946 !important;
  color: white !important;
}
</style>
""", unsafe_allow_html=True)

# --- Config Gemini ---
# Imposta la tua API key come secret GEMINI_API_KEY in Streamlit Cloud
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

st.title("Analisi Competitiva & Content Gap con Gemini")
st.divider()

# Selezione dinamica dei competitor (max 5)
num_texts = st.selectbox(
    "Numero di testi competitor da analizzare (su 5 max)",
    list(range(1,6)),
    index=0
)

# Disposizione orizzontale dei text_area usando columns
cols = st.columns(num_texts)
texts = []
for idx, col in enumerate(cols):
    with col:
        text = st.text_area(
            label=f"Testo {idx+1}",
            placeholder="Incolla qui il testo del competitor...",
            height=200
        ).strip()
        texts.append(text)

if st.button("Analizza Contenuti 🚀"):
    competitor_texts = [t for t in texts if t]
    if not competitor_texts:
        st.error("Per favore, incolla almeno un testo da competitor.")
        st.stop()

    full_text = "\n---\n".join(competitor_texts)
    prompt = f"""
## PROMPT DI ANALISI COMPETITIVA E CONTENT GAP ##

**RUOLO:**
Agisci come un analista SEO d'élite, specializzato in analisi semantica competitiva. La tua missione è "ingegneria inversa" del successo dei contenuti che si posizionano ai vertici di Google.

**CONTESTO:**
Sto per scrivere o migliorare un testo e il mio obiettivo è superare i primi competitor attualmente posizionati per la mia keyword target. Analizzerai i loro testi per darmi una mappa precisa delle entità che devo assolutamente trattare e delle opportunità (entità mancanti) che posso sfruttare per creare un contenuto oggettivamente più completo e autorevole.

**COMPITO:**
Analizza i testi dei competitor forniti di seguito. Svolgi i seguenti passaggi:

1. **Sintesi Strategica Iniziale:**
   - Identifica e dichiara qual è l'**Argomento Principale Comune** o l'**Entità Centrale** condivisa da tutti i testi.
   - Basandoti su questo, definisci il **Search Intent Primario** a cui i competitor stanno rispondendo.

2. **Generazione delle Tabelle di Analisi:**
   Crea **due tabelle Markdown separate e distinte**:
---
### TABELLA 1: ENTITÀ FONDAMENTALI (Common Ground Analysis)
| Entità | Presenza nei Competitor | Rilevanza Strategica | Azione per il Mio Testo |
| :--- | :--- | :--- | :--- |
# (Compila con dati)
---
### TABELLA 2: ENTITÀ MANCANTI (Content Gap Opportunity)
| Entità da Aggiungere (Opportunità) | Motivazione dell'Inclusione | Azione SEO Strategica |
| :--- | :--- | :--- |
# (Compila con dati)
---
Analizza questi testi:
{full_text}
Mantieni vivo il formato delle tabelle in Markdown e non aggiungere altro testo fuori da esse.
"""

    with st.spinner("Analisi in corso con Gemini..."):
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[prompt]
        )
    md = response.text

    # Estrai blocchi di tabelle Markdown
    blocks = [blk for blk in md.split("\n\n") if blk.strip().startswith("|")]
    if not blocks:
        st.warning("Non sono state generate tabelle valide.")
        st.stop()

    # Visualizza tabelle
    st.subheader("1. Entità Fondamentali")
    st.markdown(blocks[0], unsafe_allow_html=True)
    if len(blocks) > 1:
        st.subheader("2. Entità Mancanti")
        st.markdown(blocks[1], unsafe_allow_html=True)
    else:
        st.info("Non è stata trovata una seconda tabella per le entità mancanti.")
