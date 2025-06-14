import streamlit as st
import os
import io
import pandas as pd
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

# --- Inizializza session_state per multi-step wizard e nuove variabili ---
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'competitor_texts' not in st.session_state:
    st.session_state.competitor_texts = []
if 'analysis_tables' not in st.session_state:
    st.session_state.analysis_tables = []
if 'keyword_table' not in st.session_state:
    st.session_state.keyword_table = ""
if 'search_intent' not in st.session_state:
    st.session_state.search_intent = None
if 'meta_md' not in st.session_state:
    st.session_state.meta_md = None
# Initialize contesto and tipologia so keys exist
if 'contesto' not in st.session_state:
    st.session_state.contesto = ""
if 'tipologia' not in st.session_state:
    st.session_state.tipologia = ""

st.title("Analisi Competitiva & Content Gap con Gemini")
st.divider()

def go_to(step):
    st.session_state.step = step

step_title_style = (
    "background: rgba(255, 43, 43, 0.09);"
    "color: rgb(125, 53, 59);"
    "padding: 16px;"
    "border-radius: 8px;"
    "font-size: 19px;"
    "margin-bottom: 30px;"
    "font-weight: 600;"
)

def parse_md_table(md: str) -> pd.DataFrame:
    """
    Parse a Markdown table into a DataFrame, merging extra cells into the last column
    if rows contain more pipes than headers, and padding if fewer.
    """
    lines = [l for l in md.splitlines() if l.startswith("|") and not l.startswith("| :")]
    # header
    header = [h.strip() for h in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) > len(header):
            # merge extra into last column
            merged = cells[:len(header)-1] + [" | ".join(cells[len(header)-1:])]
            cells = merged
        elif len(cells) < len(header):
            # pad missing
            cells += [""] * (len(header) - len(cells))
        rows.append(cells)
    return pd.DataFrame(rows, columns=header)


# === STEP 1: Input testi competitor ===
if st.session_state.step == 1:
    st.markdown(
        f"<div style='{step_title_style}'>Step 1: Inserisci i testi dei competitor (max 5)</div>",
        unsafe_allow_html=True
    )
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        num_texts = st.selectbox(
            "Numero di testi competitor da analizzare",
            list(range(1, 6)),
            key="num_texts_step1"
        )
    with col2:
        contesto = st.selectbox(
            "Contesto",
            ["", "E-commerce", "Blog / Contenuto Informativo"],
            key="contesto"
        )
    with col3:
        mapping = {
            "E-commerce": ["Product Detail Page (PDP)", "Product Listing Page (PLP)"],
            "Blog / Contenuto Informativo": ["Articolo", "Pagina informativa"]
        }
        opts = [""] + mapping.get(st.session_state.contesto, []) if st.session_state.contesto in mapping else [""]
        tipologia = st.selectbox(
            "Tipologia di contenuto",
            opts,
            key="tipologia",
            disabled=(st.session_state.contesto not in mapping)
        )

    cols = st.columns(num_texts)
    texts = []
    for i, col in enumerate(cols, start=1):
        with col:
            texts.append(st.text_area(f"Testo competitor {i}", height=200, key=f"text_{i}").strip())

    if st.button("🚀 Avvia l'Analisi NLU"):
        if not st.session_state.contesto:
            st.error("Per favore, seleziona il Contesto prima di proseguire.")
        elif not st.session_state.tipologia:
            st.error("Per favore, seleziona la Tipologia di contenuto prima di proseguire.")
        else:
            non_empty = [t for t in texts if t]
            if not non_empty:
                st.error("Per favore, incolla almeno un testo.")
            else:
                st.session_state.competitor_texts = non_empty
                st.session_state.analysis_tables = []
                st.session_state.keyword_table = None
                st.session_state.search_intent = None
                st.session_state.meta_md = None
                go_to(2)

# === STEP 2: Analisi Entità Fondamentali & Content Gap + Intent Table ===
elif st.session_state.step == 2:
    st.markdown(
        f"<div style='{step_title_style}'>Step 2: Analisi Entità Fondamentali e Content Gap</div>",
        unsafe_allow_html=True
    )

    # 1) Extract Search Intent once
    if st.session_state.search_intent is None:
        prompt_intent = f"""
Identifica il search intent dei seguenti testi competitor. Dammi una sola risposta concisa, che sia la media dei punteggi dei vari testi.
Per il Search Intent non darmi informazioni aggiuntive, voglio sapere solamente qual è l'intento di ricerca (Informazionale, Navigazionale, Commerciale o Transazionale).

Testi:
---
{'\n---\n'.join(st.session_state.competitor_texts)}
"""
        with st.spinner("Estrazione Search Intent..."):
            resp_intent = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt_intent]
            )
        st.session_state.search_intent = resp_intent.text.strip()

    # 2) Original entities prompt
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
Mantieni solo le due tabelle, con markdown valido e wrap del testo.
"""
        with st.spinner("Eseguo analisi entità..."):
            resp2 = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt2]
            )
        st.session_state.analysis_tables = [
            blk for blk in resp2.text.split("\n\n") if blk.strip().startswith("|")
        ]

    # 3) Show summary table
    st.subheader("Sintesi Search Intent, Sentiment e Leggibilità")
    st.markdown(
        "| Search Intent | Sentiment (media dei testi forniti) | Score di leggibilità (media dei testi forniti) |\n"
        "| :--- | :--- | :--- |\n"
        f"| {st.session_state.search_intent} |  |  |",
        unsafe_allow_html=True
    )

    # 4) Show entity tables
    st.subheader("Entità Fondamentali (Common Ground Analysis)")
    st.markdown(st.session_state.analysis_tables[0], unsafe_allow_html=True)
    st.subheader("Entità Mancanti (Content Gap Opportunity)")
    st.markdown(st.session_state.analysis_tables[1], unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        if st.button("◀️ Indietro"):
            go_to(1)
    with c2:
        if st.button("🔄 Analizza di nuovo"):
            st.session_state.analysis_tables = []
            st.session_state.keyword_table = None
            st.session_state.search_intent = None
    with c3:
        if st.button("Vai a Step 3 ▶️"):
            go_to(3)

# === STEP 3: Generazione della Keyword Strategy ===
elif st.session_state.step == 3:
    st.markdown(
        f"<div style='{step_title_style}'>Step 3: Generazione della Keyword Strategy</div>",
        unsafe_allow_html=True
    )

    if st.session_state.keyword_table is None:
        full_text = "\n---\n".join(st.session_state.competitor_texts)
        table1 = st.session_state.analysis_tables[0]
        table2 = st.session_state.analysis_tables[1]
        prompt3 = f"""
## GENERAZIONE KEYWORD STRATEGY ##

Usa queste informazioni:

**Contesto:** {st.session_state.contesto}  
**Tipologia di contenuto:** {st.session_state.tipologia}  

**Testi competitor:**
---
{full_text}

**Tabella 1: Entità Fondamentali**
{table1}

**Tabella 2: Entità Mancanti**
{table2}

**RUOLO:** Agisci come uno specialista SEO d'élite, specializzato in analisi semantica competitiva e ricerca delle parole chiave. La tua missione è quella di ricercare le migliori keywords sulla base dei contenuti dei competitors.

**CONTESTO:** Sto per scrivere o migliorare un testo e il mio obiettivo è superare i primi 3 competitor attualmente posizionati per la mia keyword target. Analizzerai i loro testi per darti una mappa precisa delle keywords che devo assolutamente inserire nel mio testo. Se ci sono inserisci anche altre keywords che reputi importanti ma che non sono presenti nei testi dei competitors. L’obbiettivo è quello di sfruttare queste keywords per creare un contenuto oggettivamente più completo e autorevole.

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

    d1, d2 = st.columns([1,1])
    with d1:
        if st.button("◀️ Indietro"):
            go_to(2)
    with d2:
        if st.button("Vai a Step 4 ▶️"):
            go_to(4)

# === STEP 4: Generazione Meta Title & Description ===
elif st.session_state.step == 4:
    st.markdown(
        f"<div style='{step_title_style}'>Step 4: Generazione Meta Title & Description</div>",
        unsafe_allow_html=True
    )

    if st.session_state.meta_md is None:
        # estraggo keyword principale dalla prima tabella entità
        df_ent = parse_md_table(st.session_state.analysis_tables[0])
        main_entity = df_ent.iloc[0, 0]

        # estraggo keyword secondarie/correlate dalla tabella delle keyword
        df_kw = parse_md_table(st.session_state.keyword_table)
        # assumiamo che la riga con "Keyword Secondarie" sia indicizzata
        sec_row = df_kw[df_kw.iloc[:,0].str.contains("Keyword Secondarie", na=False)]
        secondary_kw = sec_row.iloc[0,1] if not sec_row.empty else ""

        prompt4 = f"""
RUOLO: Agisci come uno specialista SEO d'élite, esperto in scrittura di testi ottimizzati e semantica competitiva.

CONTESTO: L'obiettivo è superare i principali competitor in SERP per la keyword principale: {main_entity}. Il contenuto sarà inserito in una {st.session_state.tipologia} con un {st.session_state.contesto}.

COMPITO: Genera 5 varianti di meta title e 5 varianti di meta description semanticamente perfette per rispondere all'intento di ricerca {st.session_state.search_intent}.

Requisiti:

Lingua: Italiano perfetto, fluido e scorrevole.
Terminologia: Adatta al topic di {main_entity}.
Keyword: Utilizzo naturale, con la keyword principale all'inizio o quasi (sia nel title che nella description).
Meta Title: Lunghezza tra 50 e 60 caratteri.
Meta Description: Lunghezza tra 120 e 158 caratteri, includendo sempre una CTA (Call to Action).

Crea poi una **tabella Markdown** come descritto di seguito:
| N. Variante | Tipologia | Testo | Lunghezza |
| :--- | :--- | :--- | :--- |
"""
        with st.spinner("Generazione meta..."):
            r4 = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt4]
            )
        st.session_state.meta_md = r4.text

    # estraiamo solo le righe che fanno parte della tabella Markdown
    full = st.session_state.meta_md.splitlines()
    table_lines = []
    in_table = False
    for ln in full:
        if ln.startswith("|"):
            in_table = True
            table_lines.append(ln)
        elif in_table:
            # appena finisce il blocco di righe che iniziano con '|' usciamo
            break

    table_md = "\n".join(table_lines)

    # mostriamo solo la tabella vera e propria
    st.markdown(table_md, unsafe_allow_html=True)

    # e la passiamo al parser, senza errori di colonne in eccesso
    df_meta = parse_md_table(table_md)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_meta.to_excel(writer, index=False, sheet_name="Varianti")
    buf.seek(0)
    st.download_button(
        "Scarica .xlsx",
        buf,
        file_name="meta_varianti.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    e1, e2 = st.columns([1,1])
    with e1:
        if st.button("◀️ Indietro"):
            go_to(3)
    with e2:
        if st.button("🔄 Ricomincia"):
            for k in ['step','competitor_texts','analysis_tables','keyword_table','search_intent','contesto','tipologia','meta_md']:
                st.session_state.pop(k, None)
            go_to(1)
