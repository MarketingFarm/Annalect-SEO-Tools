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

# --- Inizializza session_state per multi-step wizard ---
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'competitor_texts' not in st.session_state:
    st.session_state.competitor_texts = []
if 'analysis_tables' not in st.session_state:
    st.session_state.analysis_tables = []
if 'keyword_table' not in st.session_state:
    st.session_state.keyword_table = None

st.title("Analisi Competitiva & Content Gap con Gemini")
st.divider()

def to_step(n):
    st.session_state.step = n

# === STEP 1: Input testi competitor ===
if st.session_state.step == 1:
    st.write("### Step 1: Inserisci i testi dei competitor (max 5)")
    num_texts = st.selectbox(
        "Numero di testi competitor da analizzare",
        list(range(1, 6)),
        index=0,
        key="num_texts_step1"
    )
    cols = st.columns(num_texts)
    texts = []
    for i, col in enumerate(cols, start=1):
        with col:
            t = st.text_area(f"Testo competitor {i}", height=200, key=f"text_{i}")
            texts.append(t.strip())

    if st.button("Vai a Step 2 ▶️"):
        non_empty = [t for t in texts if t]
        if not non_empty:
            st.error("Per favore, incolla almeno un testo.")
        else:
            st.session_state.competitor_texts = non_empty
            to_step(2)
            st.stop()

# === STEP 2: Analisi Entità Fondamentali & Content Gap ===
elif st.session_state.step == 2:
    st.write("### Step 2: Analisi Entità Fondamentali e Content Gap")
    # se non ho ancora le tabelle, chiamo Gemini
    if not st.session_state.analysis_tables:
        prompt2 = f"""
## ANALISI COMPETITIVA E CONTENT GAP ##

Analizza i seguenti testi competitor:
---
{'\n---\n'.join(st.session_state.competitor_texts)}

1. Identifica l'**Argomento Principale Comune** e il **Search Intent Primario**.
2. Crea **due tabelle Markdown**:

### TABELLA 1: ENTITÀ FONDAMENTALI (Common Ground Analysis)
| Entità | Rilevanza Strategica | Azione per il Mio Testo |
| :--- | :--- | :--- |

### TABELLA 2: ENTITÀ MANCANTI (Content Gap Opportunity)
| Entità da Aggiungere | Motivazione dell'Inclusione | Azione SEO Strategica |
| :--- | :--- | :--- |

Arricchisci la colonna "Entità" con esempi specifici tra parentesi.
Mantieni solo le due tabelle, con markdown valido e wrap del testo.
"""
        with st.spinner("Eseguo analisi entità..."):
            resp2 = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt2]
            )
        md2 = resp2.text
        tables2 = [blk for blk in md2.split("\n\n") if blk.strip().startswith("|")]
        st.session_state.analysis_tables = tables2

    # Mostro le due tabelle
    st.subheader("Entità Fondamentali (Common Ground Analysis)")
    st.markdown(st.session_state.analysis_tables[0], unsafe_allow_html=True)
    st.subheader("Entità Mancanti (Content Gap Opportunity)")
    st.markdown(st.session_state.analysis_tables[1], unsafe_allow_html=True)

    # Pulsanti di navigazione
    nav_cols = st.columns([1, 1, 1])
    with nav_cols[0]:
        if st.button("◀️ Indietro"):
            to_step(1)
            st.stop()
    with nav_cols[2]:
        if st.button("Vai a Step 3 ▶️"):
            to_step(3)
            st.stop()

# === STEP 3: Generazione della Keyword Strategy ===
elif st.session_state.step == 3:
    st.write("### Step 3: Generazione della Keyword Strategy")
    if st.session_state.keyword_table is None:
        prompt3 = f"""
Partendo dall'analisi approfondita dei testi competitor eseguita, la tua missione è estrapolare e organizzare in una tabella intuitiva le keyword più efficaci per il mio contenuto, al fine di massimizzare la rilevanza e il posizionamento. La tabella dovrà specificare:

- La keyword principale su cui focalizzarsi.
- Le keyword secondarie/correlate per espandere la copertura semantica.
- Le LSI keywords per approfondire la comprensione di Google sull'argomento.
- Non limitarti all'esistente: se ritieni che vi siano keyword fondamentali assenti nei testi analizzati ma indispensabili per creare un contenuto superiore, integrale nella tabella evidenziandone il valore aggiunto.

La tabella deve avere 3 colonne: **Categoria Keyword**, **Keywords** e **Valore Aggiunto**. Deve inoltre avere 4 righe con:
- "Keyword Principale (Focus Primario)"
- "Keyword Secondarie/Correlate (Espansione Semantica)"
- "LSI Keywords (Comprensione Approfondita)"
- "Keyword Fondamentali Mancanti (Opportunità di Content Gap)"
"""
        with st.spinner("Eseguo estrazione keyword..."):
            resp3 = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt3]
            )
        st.session_state.keyword_table = resp3.text

    # Visualizzo la tabella
    st.markdown(st.session_state.keyword_table, unsafe_allow_html=True)

    # Pulsanti di navigazione
    nav_cols = st.columns([1, 1])
    with nav_cols[0]:
        if st.button("◀️ Indietro"):
            to_step(2)
            st.stop()
    with nav_cols[1]:
        if st.button("🔄 Ricomincia"):
            for key in ['step', 'competitor_texts', 'analysis_tables', 'keyword_table']:
                st.session_state.pop(key, None)
            st.stop()
