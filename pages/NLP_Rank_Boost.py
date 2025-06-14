import streamlit as st
import os
from google import genai

# --- Dipendenze per sentiment e leggibilità ---
import textstat
import nltk
from transformers import pipeline
nltk.download('stopwords')
from nltk.corpus import stopwords
STOPWORDS_IT = set(stopwords.words('italian'))

# Inizializza modelli locali
sentiment_model = pipeline(
    'sentiment-analysis',
    model='nlptown/bert-base-multilingual-uncased-sentiment'
)

def compute_readability(text: str) -> float:
    sentences = textstat.sentence_count(text)
    words = len(text.split())
    letters = sum(c.isalpha() for c in text)
    return round(89 + (300 * sentences - 10 * letters) / words, 2) if words > 0 else None

def compute_sentiment_score(text: str) -> float:
    out = sentiment_model(text)[0]['label']  # es. "4 stars"
    return float(out.split()[0])

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

# --- Inizializza session_state ---
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

# === STEP 1 ===
if st.session_state.step == 1:
    st.markdown(
        f"<div style='{step_title_style}'>Step 1: Inserisci i testi dei competitor (max 5)</div>",
        unsafe_allow_html=True
    )
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        num_texts = st.selectbox("Numero di testi competitor da analizzare",
                                 list(range(1, 6)), key="num_texts_step1")
    with col2:
        contesti = ["", "E-commerce", "Blog / Contenuto Informativo"]
        contesto = st.selectbox("Contesto", contesti, key="contesto")
    with col3:
        mapping = {
            "E-commerce": ["Product Detail Page (PDP)", "Product Listing Page (PLP)"],
            "Blog / Contenuto Informativo": ["Articolo", "Pagina informativa"]
        }
        options = [""] + mapping.get(contesto, [])
        tipologia = st.selectbox("Tipologia di contenuto",
                                 options, key="tipologia",
                                 disabled=(contesto not in mapping))

    cols = st.columns(num_texts)
    texts = []
    for i, col in enumerate(cols, start=1):
        with col:
            texts.append(st.text_area(f"Testo competitor {i}", height=200,
                                     key=f"text_{i}").strip())

    if st.button("🚀 Avvia l'Analisi NLU"):
        if not contesto:
            st.error("Per favore, seleziona il Contesto prima di proseguire.")
        elif not tipologia:
            st.error("Per favore, seleziona la Tipologia di contenuto prima di proseguire.")
        else:
            non_empty = [t for t in texts if t]
            if not non_empty:
                st.error("Per favore, incolla almeno un testo.")
            else:
                st.session_state.competitor_texts = non_empty
                st.session_state.analysis_tables = []
                st.session_state.keyword_table = None
                go_to(2)

# === STEP 2 ===
elif st.session_state.step == 2:
    st.markdown(
        f"<div style='{step_title_style}'>Step 2: Analisi Entità Fondamentali e Content Gap</div>",
        unsafe_allow_html=True
    )

    # calcolo sentiment medio e leggibilità media
    texts = st.session_state.competitor_texts
    avg_sentiment = round(sum(compute_sentiment_score(t) for t in texts) / len(texts), 2)
    avg_readability = round(sum(compute_readability(t) for t in texts) / len(texts), 2)

    if not st.session_state.analysis_tables:
        prompt2 = f"""
## ANALISI COMPETITIVA E CONTENT GAP ##
**RUOLO:** Agisci come un analista SEO d'élite, specializzato in analisi semantica competitiva. La tua missione è "ingegneria inversa" del successo dei contenuti che si posizionano ai vertici di Google.

**CONTESTO:** Sto per scrivere o migliorare un testo e il mio obiettivo è superare i primi 3 competitor attualmente posizionati per la mia keyword target. Analizzerai i loro testi per darmi una mappa precisa delle entità che devo assolutamente trattare e delle opportunità (entità mancanti) che posso sfruttare per creare un contenuto oggettivamente più completo e autorevole.

**COMPITO AGGIUNTIVO:**  
1. Identifica il search intent dei vari testi. Dammi una sola risposta concisa (Informazionale, Navigazionale, Commerciale o Transazionale).  
2. Usa i risultati dei nostri script per il sentiment e la leggibilità:
   - Sentiment medio: {avg_sentiment}  
   - Indice Gulpease medio: {avg_readability}  

3. Crea una tabella Markdown con header e valori:
| Search Intent | Sentiment | Leggibilità |  
| :--- | :--- | :--- |  
| <!--intent--> | {avg_sentiment} | {avg_readability} |

4. Sotto questa tabella, continua con le due tabelle originali:

### TABELLA 1: ENTITÀ FONDAMENTALI (Common Ground Analysis)
| Entità | Rilevanza Strategica | Azione per il Mio Testo |
| :--- | :--- | :--- |

### TABELLA 2: ENTITÀ MANCANTI (Content Gap Opportunity)
| Entità da Aggiungere | Motivazione dell'Inclusione | Azione SEO Strategica |
| :--- | :--- | :--- |

Arricchisci la colonna "Entità" con esempi specifici tra parentesi.
Nella prima riga inserisci sempre l'entità principale.
Mantieni le tre tabelle, con markdown valido e wrap del testo.
"""
        with st.spinner("Eseguo analisi entità..."):
            resp2 = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt2]
            )
        md2 = resp2.text
        # estraggo le 3 tabelle generate
        st.session_state.analysis_tables = [
            blk for blk in md2.split("\n\n") if blk.strip().startswith("|")
        ]

    # visualizzo le 3 tabelle
    st.subheader("Sintesi Intent, Sentiment e Leggibilità")
    st.markdown(st.session_state.analysis_tables[0], unsafe_allow_html=True)

    st.subheader("Entità Fondamentali (Common Ground Analysis)")
    st.markdown(st.session_state.analysis_tables[1], unsafe_allow_html=True)

    st.subheader("Entità Mancanti (Content Gap Opportunity)")
    st.markdown(st.session_state.analysis_tables[2], unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        if st.button("◀️ Indietro"):
            go_to(1)
    with c2:
        if st.button("🔄 Analizza di nuovo"):
            st.session_state.analysis_tables = []
            st.session_state.keyword_table = None
    with c3:
        if st.button("Vai a Step 3 ▶️"):
            go_to(3)

# === STEP 3 ===
elif st.session_state.step == 3:
    st.markdown(
        f"<div style='{step_title_style}'>Step 3: Generazione della Keyword Strategy</div>",
        unsafe_allow_html=True
    )

    if st.session_state.keyword_table is None:
        full_text = "\n---\n".join(st.session_state.competitor_texts)
        table1 = st.session_state.analysis_tables[1]
        table2 = st.session_state.analysis_tables[2]
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
        if st.button("🔄 Ricomincia"):
            for k in ['step','competitor_texts','analysis_tables','keyword_table']:
                st.session_state.pop(k, None)
            go_to(1)
