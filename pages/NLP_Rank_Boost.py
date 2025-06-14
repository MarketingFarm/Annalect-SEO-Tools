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

# --- Inizializza session_state per multi-step wizard e nuove variabili ---
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'competitor_texts' not in st.session_state:
    st.session_state.competitor_texts = []
if 'analysis_tables' not in st.session_state:
    st.session_state.analysis_tables = []
if 'keyword_table' not in st.session_state:
    st.session_state.keyword_table = None
if 'contesto' not in st.session_state:
    st.session_state.contesto = ""
if 'tipologia' not in st.session_state:
    st.session_state.tipologia = ""

st.title("Analisi Competitiva & Content Gap con Gemini")
st.divider()

# Funzione helper per cambiare step
def go_to(step):
    st.session_state.step = step

# stile CSS per i titoli degli step
step_title_style = (
    "background: rgba(255, 43, 43, 0.09);"
    "color: rgb(125, 53, 59);"
    "padding: 16px;"
    "border-radius: 8px;"
    "font-size: 19px;"
    "margin-bottom: 30px;"
    "font-weight: 600;"
)

# === STEP 1: Input testi competitor ===
if st.session_state.step == 1:
    st.markdown(
        f"<div style='{step_title_style}'>Step 1: Inserisci i testi dei competitor (max 5)</div>",
        unsafe_allow_html=True
    )
    # tre dropdown sulla stessa riga
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        num_texts = st.selectbox(
            "Numero di testi competitor da analizzare",
            list(range(1, 6)),
            index=0,
            key="num_texts_step1"
        )
    with col2:
        contesti = ["", "E-commerce", "Blog / Contenuto Informativo"]
        contesto = st.selectbox(
            "Contesto",
            contesti,
            index=contesti.index(st.session_state.contesto) 
                    if st.session_state.contesto in contesti else 0,
            key="contesto"
        )
    with col3:
        mapping = {
            "E-commerce": ["Product Detail Page (PDP)", "Product Listing Page (PLP)"],
            "Blog / Contenuto Informativo": ["Articolo", "Pagina informativa"]
        }
        tip_options = mapping.get(st.session_state.contesto, [""])
        tipologia = st.selectbox(
            "Tipologia di contenuto",
            tip_options,
            index=0,
            key="tipologia",
            disabled=(st.session_state.contesto not in mapping)
        )

    # generazione dei text_area per i testi
    cols = st.columns(num_texts)
    texts = []
    for i, col in enumerate(cols, start=1):
        with col:
            t = st.text_area(f"Testo competitor {i}", height=200, key=f"text_{i}")
            texts.append(t.strip())

    if st.button("🚀 Avvia l'Analisi NLU"):
        non_empty = [t for t in texts if t]
        if not non_empty:
            st.error("Per favore, incolla almeno un testo.")
        else:
            st.session_state.competitor_texts = non_empty
            # reset analysis e keyword precedenti
            st.session_state.analysis_tables = []
            st.session_state.keyword_table = None
            go_to(2)

# === STEP 2: Analisi Entità Fondamentali & Content Gap ===
elif st.session_state.step == 2:
    st.markdown(
        f"<div style='{step_title_style}'>Step 2: Analisi Entità Fondamentali e Content Gap</div>",
        unsafe_allow_html=True
    )

    # se non ho ancora le tabelle, o se ho premuto "Analizza di nuovo", genero l'analisi
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

    # Visualizzo le tabelle
    st.subheader("Entità Fondamentali (Common Ground Analysis)")
    st.markdown(st.session_state.analysis_tables[0], unsafe_allow_html=True)
    st.subheader("Entità Mancanti (Content Gap Opportunity)")
    st.markdown(st.session_state.analysis_tables[1], unsafe_allow_html=True)

    # Pulsanti di navigazione + Rifai analisi
    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        if st.button("◀️ Indietro"):
            go_to(1)
    with c2:
        if st.button("🔄 Analizza di nuovo"):
            # resetto solo le tabelle dell'analisi, manterrò competitor_texts
            st.session_state.analysis_tables = []
            st.session_state.keyword_table = None
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

**CONTESTO:** Sto per scrivere o migliorare un testo e il mio obiettivo è superare i primi 3 competitor attualmente posizionati per la mia keyword target. Analizzerai i loro testi per darmi una mappa precisa delle keywords che devo assolutamente inserire nel mio testo. Se ci sono inserisci anche altre keywords che reputi importanti ma che non sono presenti nei testi dei competitors. L’obbiettivo è quello di sfruttare queste keywords per creare un contenuto oggettivamente più completo e autorevole.

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

    # Visualizzo la tabella
    st.markdown(st.session_state.keyword_table, unsafe_allow_html=True)

    # Pulsanti di navigazione finale
    d1, d2 = st.columns([1,1])
    with d1:
        if st.button("◀️ Indietro"):
            go_to(2)
    with d2:
        if st.button("🔄 Ricomincia"):
            for k in ['step','competitor_texts','analysis_tables','keyword_table','contesto','tipologia']:
                st.session_state.pop(k, None)
            go_to(1)
