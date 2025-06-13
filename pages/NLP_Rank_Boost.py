import streamlit as st
import os
import pandas as pd
from google import genai

# --- INIEZIONE CSS per il bottone rosso e wrap delle celle nella tabella Markdown ---
st.markdown("""
<style>
button {
  background-color: #e63946 !important;
  color: white !important;
}
/* For HTML tables rendered via Markdown */
table td, table th {
  white-space: normal !important;
}
</style>
""", unsafe_allow_html=True)

# --- Config Gemini ---
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# --- Funzioni di supporto per parsing e ricostruzione Markdown/Table ---
def parse_md_table(md: str) -> pd.DataFrame:
    lines = [l for l in md.splitlines() if l.strip().startswith("|")]
    header = lines[0]
    cols = [h.strip() for h in header.strip("|").split("|")]
    data = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.strip("|").split("|")]
        data.append(cells)
    return pd.DataFrame(data, columns=cols)

def df_to_md(df: pd.DataFrame) -> str:
    header = "| " + " | ".join(df.columns) + " |"
    sep    = "| " + " | ".join(["---"] * len(df.columns)) + " |"
    rows   = ["| " + " | ".join(map(str, row)) + " |" for row in df.values.tolist()]
    return "\n".join([header, sep] + rows)

# --- Inizializza session_state ---
if 'step' not in st.session_state:
    st.session_state.step = 1
for key in ('competitor_texts','analysis_tables','keyword_table',
            'selected_core','selected_missing'):
    if key not in st.session_state:
        st.session_state[key] = [] if 'texts' in key or 'selected' in key or 'tables' in key else None

st.title("Analisi Competitiva & Content Gap con Gemini")
st.divider()

def go_to(step: int):
    st.session_state.step = step

# === STEP 1: Input testi competitor ===
if st.session_state.step == 1:
    st.write("### Step 1: Inserisci i testi dei competitor (max 5)")
    n = st.selectbox("Numero di testi competitor da analizzare", list(range(1,6)), index=0)
    cols = st.columns(n)
    texts = []
    for i, col in enumerate(cols, start=1):
        with col:
            texts.append(st.text_area(f"Testo competitor {i}", height=200).strip())
    if st.button("Vai a Step 2 ▶️"):
        non_empty = [t for t in texts if t]
        if not non_empty:
            st.error("Per favore, incolla almeno un testo.")
        else:
            st.session_state.competitor_texts = non_empty
            st.session_state.analysis_tables = []
            st.session_state.keyword_table   = None
            st.session_state.selected_core   = []
            st.session_state.selected_missing= []
            go_to(2)

# === STEP 2: Analisi Entità Fondamentali & Content Gap ===
elif st.session_state.step == 2:
    st.write("### Step 2: Analisi Entità Fondamentali & Content Gap")

    # Genera o rigenera l'analisi se necessario
    if not st.session_state.analysis_tables:
        prompt2 = f"""
## ANALISI COMPETITIVA E CONTENT GAP ##
**RUOLO:** Agisci come un analista SEO d'élite...
**CONTESTO:** ...
**COMPITO:** Analizza i testi:
---
{'\n---\n'.join(st.session_state.competitor_texts)}

1. Identifica l'Argomento Principale e il Search Intent.
2. Crea due tabelle Markdown:
### TABELLA 1
| Entità | Rilevanza Strategica | Azione per il Mio Testo |
| :--- | :--- | :--- |
### TABELLA 2
| Entità da Aggiungere | Motivazione dell'Inclusione | Azione SEO Strategica |
| :--- | :--- | :--- |
"""
        with st.spinner("Eseguo analisi..."):
            r = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt2]
            )
        st.session_state.analysis_tables = [
            blk for blk in r.text.split("\n\n") if blk.strip().startswith("|")
        ]

    # Parsing delle tabelle
    core_df    = parse_md_table(st.session_state.analysis_tables[0])
    missing_df = parse_md_table(st.session_state.analysis_tables[1])

    # Aggiungo colonna boolean e riordino mettendola per prima
    core_df['Seleziona']    = core_df['Entità'].isin(st.session_state.selected_core)
    core_df = core_df[['Seleziona','Entità','Rilevanza Strategica','Azione per il Mio Testo']]
    missing_df['Seleziona'] = missing_df['Entità da Aggiungere'].isin(st.session_state.selected_missing)
    missing_df = missing_df[['Seleziona','Entità da Aggiungere',"Motivazione dell'Inclusione",'Azione SEO Strategica']]

    # Stampo righe con checkbox all'inizio e Markdown per il contenuto (bold funziona)
    st.subheader("Entità Fondamentali (Common Ground Analysis)")
    for idx, row in core_df.iterrows():
        chk_col, txt_col = st.columns([1,9])
        with chk_col:
            new = st.checkbox("", key=f"core_{idx}", value=row['Seleziona'])
            if new and row['Entità'] not in st.session_state.selected_core:
                st.session_state.selected_core.append(row['Entità'])
            if not new and row['Entità'] in st.session_state.selected_core:
                st.session_state.selected_core.remove(row['Entità'])
        with txt_col:
            st.markdown(f"**{row['Entità']}**  |  {row['Rilevanza Strategica']}  |  {row['Azione per il Mio Testo']}")

    st.subheader("Entità Mancanti (Content Gap Opportunity)")
    for idx, row in missing_df.iterrows():
        chk_col, txt_col = st.columns([1,9])
        ent    = row['Entità da Aggiungere']
        motiv  = row["Motivazione dell'Inclusione"]
        azione = row['Azione SEO Strategica']
        with chk_col:
            new = st.checkbox("", key=f"miss_{idx}", value=row['Seleziona'])
            if new and ent not in st.session_state.selected_missing:
                st.session_state.selected_missing.append(ent)
            if not new and ent in st.session_state.selected_missing:
                st.session_state.selected_missing.remove(ent)
        with txt_col:
            st.markdown(f"**{ent}**  |  {motiv}  |  {azione}")

    # Pulsanti di navigazione
    c1,c2,c3 = st.columns([1,1,1])
    with c1:
        if st.button("◀️ Indietro"):
            go_to(1)
    with c2:
        if st.button("🔄 Analizza di nuovo"):
            st.session_state.analysis_tables = []
            st.session_state.keyword_table    = None
            st.session_state.selected_core    = []
            st.session_state.selected_missing = []
    with c3:
        if st.button("Vai a Step 3 ▶️"):
            go_to(3)

# === STEP 3: Generazione della Keyword Strategy ===
elif st.session_state.step == 3:
    st.write("### Step 3: Generazione della Keyword Strategy")
    if not st.session_state.keyword_table:
        core_df    = parse_md_table(st.session_state.analysis_tables[0])
        missing_df = parse_md_table(st.session_state.analysis_tables[1])
        sel_core  = core_df[core_df['Entità'].isin(st.session_state.selected_core)]
        sel_miss  = missing_df[missing_df['Entità da Aggiungere'].isin(st.session_state.selected_missing)]
        t1 = df_to_md(sel_core)
        t2 = df_to_md(sel_miss)
        prompt3 = f"""
## GENERAZIONE KEYWORD STRATEGY ##
**Testi competitor:**
---
{'\n---\n'.join(st.session_state.competitor_texts)}

**Tabella 1: Entità Fondamentali**
{t1}

**Tabella 2: Entità Mancanti**
{t2}

... (resto del prompt invariato) ...
"""
        with st.spinner("Eseguo estrazione keyword..."):
            r3 = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt3]
            )
        st.session_state.keyword_table = r3.text

    st.markdown(st.session_state.keyword_table, unsafe_allow_html=True)
    d1,d2 = st.columns([1,1])
    with d1:
        if st.button("◀️ Indietro"):
            go_to(2)
    with d2:
        if st.button("🔄 Ricomincia"):
            for k in ['step','competitor_texts','analysis_tables','keyword_table','selected_core','selected_missing']:
                st.session_state.pop(k, None)
            go_to(1)
