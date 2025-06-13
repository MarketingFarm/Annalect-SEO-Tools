import streamlit as st
import os
from google import genai
import json

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

# Initialize session state
if 'step' not in st.session_state:
    st.session_state.step = 1

# Step 1: Input competitor texts

def step1():
    st.header("Step 1: Inserimento Testi Competitor")
    num_texts = st.selectbox(
        "Numero di testi competitor da analizzare (max 5)",
        [1,2,3,4,5],
        index=0,
        key='num_texts'
    )
    cols = st.columns(st.session_state.num_texts)
    texts = []
    for i, col in enumerate(cols, start=1):
        with col:
            t = st.text_area(
                label=f"Testo competitor {i}",
                height=200,
                key=f"text_{i}"
            ).strip()
            texts.append(t)
    if st.button("Prosegui al Step 2 🚀"):
        competitor_texts = [t for t in texts if t]
        if not competitor_texts:
            st.error("Per favore, incolla almeno un testo da competitor.")
        else:
            st.session_state.competitor_texts = competitor_texts
            st.session_state.step = 2
            st.experimental_rerun()

# Step 2: Display analysis and keyword strategy

def step2():
    st.header("Step 2: Analisi e Keyword Strategy")
    if 'competitor_texts' not in st.session_state:
        st.error("Step 1 non completato. Torna indietro.")
        return

    # Generate analysis tables once
    if 'analysis_tables' not in st.session_state:
        full_text = "\n---\n".join(st.session_state.competitor_texts)
        prompt1 = f"""
## PROMPT DI ANALISI COMPETITIVA E CONTENT GAP ##

**RUOLO:** Agisci come un analista SEO d'élite.

**CONTESTO:** Supera i competitor per la keyword target.

**TESTI COMPETITOR:**
{full_text}

**COMPITO:**
1. Identifica l'Argomento Principale Comune e il Search Intent Primario.
2. Genera due tabelle Markdown:

### TABELLA 1: ENTITÀ FONDAMENTALI
| Entità | Rilevanza Strategica | Azione per il Mio Testo |
| :--- | :--- | :--- |

### TABELLA 2: ENTITÀ MANCANTI
| Entità da Aggiungere | Motivazione dell'Inclusione | Azione SEO Strategica |
| :--- | :--- | :--- |

Arricchisci la colonna "Entità" con esempi specifici. Mantieni solo le due tabelle.
"""
        with st.spinner("Analisi competitor in corso..."):
            resp1 = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt1]
            )
        md = resp1.text
        tables = [blk for blk in md.split("\n\n") if blk.strip().startswith("|")]
        st.session_state.analysis_tables = tables

    # Display analysis tables
    tables = st.session_state.analysis_tables
    if len(tables) >= 1:
        st.subheader("Entità Fondamentali (Common Ground Analysis)")
        st.markdown(tables[0], unsafe_allow_html=True)
    if len(tables) >= 2:
        st.subheader("Entità Mancanti (Content Gap Opportunity)")
        st.markdown(tables[1], unsafe_allow_html=True)

    st.markdown("---")
    if st.button("Genera Keyword Strategy 🚀"):
        prompt2 = f"""
Partendo dall'analisi approfondita dei testi competitor, estrai e organizza in JSON le keyword più efficaci:

- Categoria: Keyword Principale (Focus Primario)
- Categoria: Keyword Secondarie/Correlate (Espansione Semantica)
- Categoria: LSI Keywords (Comprensione Approfondita)
- Categoria: Keyword Fondamentali Mancanti (Opportunità Content Gap)

Restituisci un oggetto JSON:
{{
  "Keyword Strategy": [
    {{"Categoria": "Keyword Principale (Focus Primario)", "Keywords": [...], "Valore Aggiunto": "..."}},
    {{"Categoria": "Keyword Secondarie/Correlate", "Keywords": [...], "Valore Aggiunto": "..."}},
    {{"Categoria": "LSI Keywords (Comprensione Approfondita)", "Keywords": [...], "Valore Aggiunto": "..."}},
    {{"Categoria": "Keyword Fondamentali Mancanti (Opportunità Content Gap)", "Keywords": [...], "Valore Aggiunto": "..."}}
  ]
}}
"""
        with st.spinner("Generazione keyword strategy in corso..."):
            resp2 = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt2]
            )
        try:
            strategy = json.loads(resp2.text)
        except Exception:
            strategy = resp2.text
        st.subheader("Keyword Strategy JSON")
        st.json(strategy)

    if st.button("Torna allo Step 1 🔙"):
        st.session_state.step = 1
        st.experimental_rerun()

# Main navigation
if st.session_state.step == 1:
    step1()
else:
    step2()
