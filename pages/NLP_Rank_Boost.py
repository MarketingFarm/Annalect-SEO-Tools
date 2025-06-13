import streamlit as st
import os
from google import genai
import json
import re
import pandas as pd

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
st.markdown("**Step {}/2**".format(st.session_state.get('step',1)))
st.divider()

# Initialize session state
if 'step' not in st.session_state:
    st.session_state.step = 1

# Step 1: Input competitor texts

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

# Step 2: Analysis & Keyword Strategy

def step2():
    st.header("Step 2: Analisi e Generazione Keyword Strategy")
    if 'competitor_texts' not in st.session_state:
        st.error("Step 1 non completato.")
        if st.button("Torna a Step 1 🔙"):
            st.session_state.step = 1
        return

    # Accordion con testi competitor e analisi
    with st.expander("Mostra / Nascondi: Dati del Step 1"):
        st.subheader("Testi Competitor Inseriti")
        for idx, txt in enumerate(st.session_state.competitor_texts, start=1):
            st.markdown(f"**Competitor {idx}:** {txt[:100]}{'...' if len(txt)>100 else ''}")
        if 'analysis_tables' in st.session_state:
            st.subheader("Entità Fondamentali")
            st.markdown(st.session_state.analysis_tables[0], unsafe_allow_html=True)
            st.subheader("Entità Mancanti")
            st.markdown(st.session_state.analysis_tables[1], unsafe_allow_html=True)

    st.markdown("---")

    # Generate analysis tables once
    if 'analysis_tables' not in st.session_state:
        full_text = "\n---\n".join(st.session_state.competitor_texts)
        prompt1 = f"""
## Analisi Competitiva & Content Gap
Analizza i testi competitor:
{full_text}
1) Argomento Principale Comune e Search Intent Primario
2) Tabelle: Entità Fondamentali e Entità Mancanti (content gap)
Mantieni in Markdown wrap text.
"""
        with st.spinner("Analisi competitor in corso..."):
            resp1 = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt1]
            )
        md = resp1.text
        tables = [blk for blk in md.split("\n\n") if blk.strip().startswith("|")][:2]
        st.session_state.analysis_tables = tables

    # Mostro analisi principali
    st.subheader("Entità Fondamentali (Common Ground)")
    st.markdown(st.session_state.analysis_tables[0], unsafe_allow_html=True)
    st.subheader("Entità Mancanti (Content Gap)")
    st.markdown(st.session_state.analysis_tables[1], unsafe_allow_html=True)
    st.markdown("---")

    # Generazione keyword strategy
    if st.button("Genera Keyword Strategy 🚀"):
        prompt2 = f"""
Partendo dall'analisi delle entità:
{st.session_state.analysis_tables[0]}
{st.session_state.analysis_tables[1]}
Genera una tabella con colonne:
- Categoria Keyword
- Keywords
- Valore Aggiunto
E con 4 righe: Keyword Principale, Secondarie/Correlate, LSI, Fondamentali Mancanti.
Mantieni solo la tabella in Markdown.
"""
        with st.spinner("Generazione keyword strategy..."):
            resp2 = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt2]
            )
        md2 = resp2.text
        lines = [l for l in md2.splitlines() if l.startswith("|")]
        header = [h.strip() for h in lines[0].strip("|").split("|")]
        data = [row.strip("|").split("|") for row in lines[2:]]
        df_kw = pd.DataFrame([[cell.strip() for cell in r] for r in data], columns=header)
        st.subheader("Keyword Strategy")
        st.dataframe(df_kw, use_container_width=True)

    if st.button("Torna a Step 1 🔙"):
        st.session_state.step = 1

# Main navigation
if st.session_state.step == 1:
    step1()
else:
    step2()
