import streamlit as st
import os
import pandas as pd
from google import genai

# --- INIEZIONE CSS per il bottone rosso e wrap testo nelle righe markdown ---
st.markdown("""
<style>
button {
  background-color: #e63946 !important;
  color: white !important;
}
/* wrap markdown in columns */
.streamlit-expanderContent, .streamlit-expanderHeader, .css-1d391kg {
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
if 'competitor_texts' not in st.session_state:
    st.session_state.competitor_texts = []
if 'analysis_tables' not in st.session_state:
    st.session_state.analysis_tables = []
if 'keyword_table' not in st.session_state:
    st.session_state.keyword_table = None
if 'selected_core' not in st.session_state:
    st.session_state.selected_core = []
if 'selected_missing' not in st.session_state:
    st.session_state.selected_missing = []

st.title("Analisi Competitiva & Content Gap con Gemini")
st.divider()

def go_to(step: int):
    st.session_state.step = step

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
            st.session_state.analysis_tables = []
            st.session_state.keyword_table = None
            st.session_state.selected_core = []
            st.session_state.selected_missing = []
            go_to(2)

# === STEP 2: Analisi Entità Fondamentali & Content Gap ===
elif st.session_state.step == 2:
    st.write("### Step 2: Analisi Entità Fondamentali e Content Gap")

    # Genera o rigenera l'analisi se necessario
    if not st.session_state.analysis_tables:
        prompt2 = f"""
## ANALISI COMPETITIVA E CONTENT GAP ##
**RUOLO:** Agisci come un analista SEO d'élite, specializzato in analisi semantica competitiva. La tua missione è "ingegneria inversa" del successo dei contenuti che si posizionano ai vertici di Google.

**CONTESTO:** Sto per scrivere o migliorare un testo e il mio obiettivo è superare i primi 3 competitor attualmente posizionati per la mia keyword target. Analizzerai i loro testi per darmi una mappa precisa delle entità che devo assolutamente trattare e delle opportunità (entità mancanti) che posso sfruttare per creare un contenuto oggettivamente più completo e autorevole.

**COMPITO:** Analizza i seguenti testi competitor:
---
{'\n---\n'.join(st.session_state.competitor_texts)}

1. Identifica e dichiara qual è l'**Argomento Principale Comune** o l'**Entità Centrale** condivisa da tutti i testi.
2. Basandoti su questo, definisci il **Search Intent Primario** a cui i competitor stanno rispondendo (es: "Confronto informativo tra prodotti", "Guida all'acquisto per principianti", "Spiegazione approfondita di un concetto").
3. Crea **due tabelle Markdown separate e distinte**, come descritto di seguito:

### TABELLA 1: ENTITÀ FONDAMENTALI (Common Ground Analysis)
*In questa tabella, elenca le entità più importanti che sono **presenti in almeno uno dei testi dei competitor**. Questo è il "minimo sindacale" semantico per essere competitivi.*

| Entità | Rilevanza Strategica | Azione per il Mio Testo |
| :--- | :--- | :--- |

### TABELLA 2: ENTITÀ MANCANTI (Content Gap Opportunity)
*In questa tabella, elenca le entità rilevanti che **nessuno (o quasi nessuno) dei competitor tratta in modo adeguato**. Queste sono le tue opportunità per superarli.*

| Entità da Aggiungere | Motivazione dell'Inclusione | Azione SEO Strategica |
| :--- | :--- | :--- |

Arricchisci la colonna "Entità" con esempi specifici tra parentesi.
Nella prima riga inserisci sempre l'entità principale.
Inserisci nelle tabelle solamente le informazioni **veramente utili** al fine di ottenere un testo semanticamente migliore rispetto a quello dei miei competitors, che rispetti l'intento di ricerca dell'argomento principale e che mi porti a superarli nella SERP.
Nota Bene: I testi sono inseriti in ordine casuale. Anche l'ordine delle frasi è inserito in ordine casuale. Questo per non falsificare i risultati e per non portarti a pensare che le informazioni che vengono inserite prima siano più importanti.
Mantieni solo le due tabelle, con markdown valido e wrap del testo.
"""
        with st.spinner("Eseguo analisi entità..."):
            resp2 = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt2]
            )
        md2 = resp2.text
        st.session_state.analysis_tables = [
            blk for blk in md2.split("\n\n") if blk.strip().startswith("|")
        ]

    # Parsing
    core_df    = parse_md_table(st.session_state.analysis_tables[0])
    missing_df = parse_md_table(st.session_state.analysis_tables[1])

    # Aggiungi colonna boolean per checkbox
    core_df['Seleziona']    = core_df['Entità'].isin(st.session_state.selected_core)
    missing_df['Seleziona'] = missing_df['Entità da Aggiungere'].isin(st.session_state.selected_missing)

    # Rendi 'Seleziona' la prima colonna
    core_df = core_df[['Seleziona', 'Entità', 'Rilevanza Strategica', 'Azione per il Mio Testo']]
    missing_df = missing_df[['Seleziona', 'Entità da Aggiungere', "Motivazione dell'Inclusione", 'Azione SEO Strategica']]

    # Mostra righe con checkbox e markdown per ciascuna
    st.subheader("Entità Fondamentali (Common Ground Analysis)")
    for idx, row in core_df.iterrows():
        col_chk, col_txt = st.columns([1, 9])
        with col_chk:
            checked = row['Seleziona']
            new = st.checkbox("", key=f"core_{idx}", value=checked)
            if new and row['Entità'] not in st.session_state.selected_core:
                st.session_state.selected_core.append(row['Entità'])
            if not new and row['Entità'] in st.session_state.selected_core:
                st.session_state.selected_core.remove(row['Entità'])
        with col_txt:
            st.markdown(
                f"**{row['Entità']}**  |  "
                f"{row['Rilevanza Strategica']}  |  "
                f"{row['Azione per il Mio Testo']}"
            )

    st.subheader("Entità Mancanti (Content Gap Opportunity)")
    for idx, row in missing_df.iterrows():
        col_chk, col_txt = st.columns([1, 9])
        with col_chk:
            checked = row['Seleziona']
            new = st.checkbox("", key=f"miss_{idx}", value=checked)
            ent = row['Entità da Aggiungere']
            if new and ent not in st.session_state.selected_missing:
                st.session_state.selected_missing.append(ent)
            if not new and ent in st.session_state.selected_missing:
                st.session_state.selected_missing.remove(ent)
        with col_txt:
            st.markdown(
                f"**{row['Entità da Aggiungere']}**  |  "
                f"{row['Motivazione dell'Inclusione']}  |  "
                f"{row['Azione SEO Strategica']}"
            )

    # Pulsanti di navigazione + Rifai analisi
    b1, b2, b3 = st.columns([1, 1, 1])
    with b1:
        if st.button("◀️ Indietro"):
            go_to(1)
    with b2:
        if st.button("🔄 Analizza di nuovo"):
            st.session_state.analysis_tables = []
            st.session_state.keyword_table    = None
            st.session_state.selected_core    = []
            st.session_state.selected_missing = []
    with b3:
        if st.button("Vai a Step 3 ▶️"):
            go_to(3)

# === STEP 3: Generazione della Keyword Strategy ===
elif st.session_state.step == 3:
    st.write("### Step 3: Generazione della Keyword Strategy")
    if not st.session_state.keyword_table:
        core_df    = parse_md_table(st.session_state.analysis_tables[0])
        missing_df = parse_md_table(st.session_state.analysis_tables[1])

        sel_core_df = core_df[core_df['Entità'].isin(st.session_state.selected_core)]
        sel_miss_df = missing_df[missing_df['Entità da Aggiungere'].isin(st.session_state.selected_missing)]

        table1_md = df_to_md(sel_core_df)
        table2_md = df_to_md(sel_miss_df)

        prompt3 = f"""
## GENERAZIONE KEYWORD STRATEGY ##
Usa queste informazioni:

**Testi competitor:**
---
{'\n---\n'.join(st.session_state.competitor_texts)}

**Tabella 1: Entità Fondamentali**
{table1_md}

**Tabella 2: Entità Mancanti**
{table2_md}

**RUOLO:** Agisci come uno specialista SEO d'élite, specializzato in analisi semantica competitiva e ricerca delle parole chiave. La tua missione è quella di ricercare le migliori keywords sulla base dei contenuti dei competitors.

**CONTESTO:** Sto per scrivere o migliorare un testo e il mio obiettivo è superare i primi 3 competitor attualmente posizionati per la mia keyword target. Analizzerai i loro testi per darmi una mappa precisa delle keywords che devo assolutamente inserire nel mio testo. Se ci sono, inserisci anche altre keywords che reputi importanti ma che non sono presenti nei testi dei competitors. L’obiettivo è quello di sfruttare queste keywords per creare un contenuto oggettivamente più completo e autorevole.

**COMPITO:** Partendo da questa analisi approfondita sui testi dei competitors, la tua missione è estrapolare e organizzare in una tabella intuitiva le keyword più efficaci per il mio contenuto, al fine di massimizzare la rilevanza e il posizionamento. La tabella dovrà specificare:
- La keyword principale su cui focalizzarsi.
- Le keyword secondarie/correlate per espandere la copertura semantica.
- Le LSI keywords per approfondire la comprensione di Google sull'argomento.
- Le keyword fondamentali mancanti (opportunità di content gap individuate nel passo precedente).

La tabella deve avere 3 colonne: **Categoria Keyword**, **Keywords** e **Valore Aggiunto**. Deve inoltre includere 4 righe con:
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

    st.markdown(st.session_state.keyword_table, unsafe_allow_html=True)
    d1, d2 = st.columns([1, 1])
    with d1:
        if st.button("◀️ Indietro"):
            go_to(2)
    with d2:
        if st.button("🔄 Ricomincia"):
            for k in ['step','competitor_texts','analysis_tables','keyword_table','selected_core','selected_missing']:
                st.session_state.pop(k, None)
            go_to(1)
