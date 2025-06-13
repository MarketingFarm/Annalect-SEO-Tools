import streamlit as st
import os
from google import genai
import pandas as pd
import json
import re

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

st.title("Analisi Competitiva & Keyword Strategy con Gemini")
st.markdown(f"**Step {st.session_state.get('step',1)}/2**")
st.divider()

# Initialize session state
if 'step' not in st.session_state:
    st.session_state.step = 1

# Step 1: inserimento testi

def step1():
    st.header("Step 1: Inserimento Testi Competitor")
    num = st.selectbox("Numero di testi competitor (max 5)", [1,2,3,4,5], index=0, key='num_texts')
    cols = st.columns(num)
    texts = []
    for i, col in enumerate(cols, start=1):
        with col:
            t = st.text_area(f"Testo competitor {i}", height=200, key=f"text_{i}")
            texts.append(t.strip())
    if st.button("Prosegui al Step 2 🚀"):
        comp = [t for t in texts if t]
        if not comp:
            st.error("Inserisci almeno un testo.")
        else:
            st.session_state.competitor_texts = comp
            st.session_state.step = 2

# Step 2: analisi e keyword strategy

def step2():
    st.header("Step 2: Analisi e Generazione Keyword Strategy")
    # Check competitor_texts
    if 'competitor_texts' not in st.session_state:
        st.error("Prima completa lo Step 1.")
        if st.button("Torna a Step 1 🔙"):
            st.session_state.step = 1
        return

    # Accordion con dati step1
    with st.expander("Mostra/Nascondi: Dati Step 1"):
        st.subheader("Testi Competitor Inseriti")
        for idx, txt in enumerate(st.session_state.competitor_texts, start=1):
            st.markdown(f"**Competitor {idx}:** {txt[:100]}{'...' if len(txt)>100 else ''}")
        if 'analysis_tables' in st.session_state and len(st.session_state.analysis_tables) >= 2:
            st.subheader("Entità Fondamentali")
            st.markdown(st.session_state.analysis_tables[0], unsafe_allow_html=True)
            st.subheader("Entità Mancanti")
            st.markdown(st.session_state.analysis_tables[1], unsafe_allow_html=True)

    st.markdown("---")

    # Genera analisi se non esistono
    if 'analysis_tables' not in st.session_state:
        full_text = "
---
".join(st.session_state.competitor_texts)
        prompt1 = f"""
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
Crea **due tabelle Markdown separate e distinte**, come descritto di seguito.

---

### TABELLA 1: ENTITÀ FONDAMENTALI (Common Ground Analysis)
| Entità | Rilevanza Strategica | Azione per il Mio Testo |
| :--- | :--- | :--- |

---

### TABELLA 2: ENTITÀ MANCANTI (Content Gap Opportunity)
| Entità da Aggiungere | Motivazione dell'Inclusione | Azione SEO Strategica |
| :--- | :--- | :--- |

Arricchisci la colonna "Entità" con esempi specifici tra parentesi.
Nella prima riga inserisci sempre l'entità principale.
Mantieni solo le due tabelle, con markdown valido e wrap del testo.
"""
        with st.spinner("Analisi competitor in corso..."):
            resp1 = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt1]
            )
        md = resp1.text
        tables = [blk for blk in md.split("

") if blk.strip().startswith("|")][:2]
        st.session_state.analysis_tables = tables

    # Visualizza tabelle di analisi
    tables = st.session_state.get('analysis_tables', [])
    if len(tables) >= 1:
        st.subheader("Entità Fondamentali (Common Ground)")
        st.markdown(tables[0], unsafe_allow_html=True)
    if len(tables) >= 2:
        st.subheader("Entità Mancanti (Content Gap)")
        st.markdown(tables[1], unsafe_allow_html=True)
    st.markdown("---")

    # Bottone genera keyword strategy
    if st.button("Genera Keyword Strategy 🚀"):
        prompt2 = f"""
Partendo dall'analisi:
{tables[0] if len(tables)>=1 else ''}
{tables[1] if len(tables)>=2 else ''}
Genera in Markdown una tabella con:
| Categoria Keyword | Keywords | Valore Aggiunto |
| :--- | :--- | :--- |
Con righe: Keyword Principale, Secondarie/Correlate, LSI, Fondamentali Mancanti.
"""
        with st.spinner("Generating strategy..."):
            resp2 = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt2]
            )
        md2 = resp2.text
        lines = [l for l in md2.splitlines() if l.startswith("|")]
        if len(lines) >= 3:
            header = [h.strip() for h in lines[0].strip("|").split("|")]
            data = [row.strip("|").split("|") for row in lines[2:]]
            df_kw = pd.DataFrame([[cell.strip() for cell in r] for r in data], columns=header)
            st.subheader("Keyword Strategy")
            st.dataframe(df_kw, use_container_width=True)
        else:
            st.error("Tabella Keyword Strategy non valida.")

    # Bottone torna step1
    if st.button("Torna a Step 1 🔙"):
        st.session_state.step = 1

# Main navigation
if st.session_state.step == 1:
    step1()
else:
    step2()
