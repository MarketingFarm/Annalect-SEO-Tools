import os
import re
import json
import streamlit as st
import requests
import pandas as pd
from urllib.parse import urlparse, urlunparse
from streamlit_quill import st_quill
from google import genai
from concurrent.futures import ThreadPoolExecutor

# --- SESSIONE HTTP GLOBALE PER RIUSO CONNESSIONE ---
session = requests.Session()

# --- UTILITIES NLU GENERICA ---
def run_nlu(prompt: str) -> str:
    return client.models.generate_content(
        model="gemini-2.5-flash-preview-05-20",
        contents=[prompt]
    ).text

# wrapper per mantenere le funzioni originali
def run_nlu_strategica(prompt: str) -> str:
    return run_nlu(prompt)

def run_nlu_competitiva(prompt: str) -> str:
    return run_nlu(prompt)

def run_nlu_mining(prompt: str) -> str:
    return run_nlu(prompt)


# --- INIEZIONE CSS GENERALE ---
st.markdown("""
<style>
.stElementContainer:has(> iframe) {
  height: 300px;
  overflow-y: scroll;
  overflow-x: hidden;
  max-height: 250px !important;
}
/* Bottone rosso */
button {
  background-color: #e63946 !important;
  color: white !important;
}
/* Tabelle */
table {
  border-collapse: collapse;
  width: 100%;
}
table, th, td {
  border: 1px solid #ddd !important;
  padding: 8px !important;
  font-size: 14px;
}
th {
  background-color: #f1f1f1 !important;
  position: sticky;
  top: 0;
  z-index: 1;
}
/* Wrap testo */
td { white-space: normal !important; }
/* Centra le colonne di lunghezza (3ª e 5ª) */
table th:nth-child(3), table td:nth-child(3),
table th:nth-child(5), table td:nth-child(5) {
  text-align: center !important;
}
</style>
""", unsafe_allow_html=True)


# --- CONFIG DATAFORSEO ---
DFS_USERNAME = st.secrets["dataforseo"]["username"]
DFS_PASSWORD = st.secrets["dataforseo"]["password"]
auth = (DFS_USERNAME, DFS_PASSWORD)

@st.cache_data(show_spinner=False)
def get_countries() -> list[str]:
    resp = session.get('https://api.dataforseo.com/v3/serp/google/locations', auth=auth)
    resp.raise_for_status()
    locs = resp.json()['tasks'][0]['result']
    return sorted(loc['location_name'] for loc in locs if loc.get('location_type') == 'Country')

@st.cache_data(show_spinner=False)
def get_languages() -> list[str]:
    resp = session.get('https://api.dataforseo.com/v3/serp/google/languages', auth=auth)
    resp.raise_for_status()
    langs = resp.json()['tasks'][0]['result']
    return sorted(lang['language_name'] for lang in langs)

def clean_url(url: str) -> str:
    parsed = urlparse(url)
    cleaned = parsed._replace(query='', params='', fragment='')
    return urlunparse(cleaned)

@st.cache_data(show_spinner=True)
def fetch_serp(query: str, country: str, language: str) -> dict | None:
    payload = [{
        'keyword': query,
        'location_name': country,
        'language_name': language,
        'calculate_rectangles': True,
        'people_also_ask_click_depth': 1
    }]
    resp = session.post(
        'https://api.dataforseo.com/v3/serp/google/organic/live/advanced',
        auth=auth,
        json=payload
    )
    resp.raise_for_status()
    tasks = resp.json().get('tasks', [])
    if not tasks or not tasks[0].get('result'):
        return None
    return tasks[0]['result'][0]


# --- CONFIG GEMINI / VERTEX AI ---
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error("GEMINI_API_KEY non trovata in environment.")
    st.stop()
client = genai.Client(api_key=api_key)


# === SESSION STATE PER CHIUDERE EXPANDER DOPO ANALISI ===
if 'analysis_started' not in st.session_state:
    st.session_state['analysis_started'] = False

def start_analysis():
    st.session_state['analysis_started'] = True


# === UI PRINCIPALE ===
st.title("Analisi SEO Competitiva Multi-Step")
st.markdown("Questo tool esegue analisi SEO integrando SERP scraping e NLU.")
st.divider()

col1, col2, col3, col4 = st.columns(4)
with col1:
    query = st.text_input("Query", key="query")
with col2:
    country = st.selectbox("Country", [""] + get_countries(), key="country")
with col3:
    language = st.selectbox("Lingua", [""] + get_languages(), key="language")
with col4:
    num_opts = [""] + list(range(1, 6))
    num_comp = st.selectbox("Numero competitor", num_opts, key="num_competitor")
count = int(num_comp) if isinstance(num_comp, int) else 0

st.markdown("---")

# Step 1c: editor in expander
with st.expander(
    "Testi dei Competitor",
    expanded=not st.session_state['analysis_started']
):
    if not st.session_state['analysis_started']:
        idx = 1
        for _ in range((count + 1) // 2):
            cols_pair = st.columns(2)
            for col in cols_pair:
                if idx <= count:
                    with col:
                        st.markdown(f"**Testo Competitor #{idx}**")
                        st_quill("", key=f"comp_quill_{idx}")
                    idx += 1

st.button("🚀 Avvia l'Analisi", on_click=start_analysis)


# --- helper per estrarre tutte le tabelle Markdown da un testo
def extract_markdown_tables(text: str) -> list[str]:
    lines = text.splitlines()
    tables = []
    buf = []
    for line in lines:
        if line.strip().startswith("|"):
            buf.append(line)
        else:
            if buf:
                tables.append("\n".join(buf))
                buf = []
    if buf:
        tables.append("\n".join(buf))
    return tables

# parsing generico Markdown→lista di dict
def parse_md_table(md: str) -> list[dict]:
    lines = [l for l in md.splitlines() if l.strip()]
    if len(lines) < 2:
        return []
    header = [h.strip().strip('* ') for h in lines[0].split('|')[1:-1]]
    rows = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.split('|')[1:-1]]
        if len(cells) == len(header):
            rows.append(dict(zip(header, cells)))
    return rows


if st.session_state['analysis_started']:
    if not (query and country and language):
        st.error("Query, Country e Lingua sono obbligatori.")
        st.stop()

    # --- STEP SERP SCRAPING E TABELLE ---
    result = fetch_serp(query, country, language)
    if result is None:
        st.error("Errore nel recupero dei dati SERP. Verifica query e parametri.")
        st.stop()
    items = result.get('items', [])

    organic = [it for it in items if it.get('type') == 'organic'][:10]
    data_org = []
    for it in organic:
        title = it.get('title') or it.get('link_title', '')
        desc = it.get('description') or it.get('snippet', '')
        clean = clean_url(it.get('link') or it.get('url',''))
        data_org.append({
            'URL': clean,
            'Meta Title': title,
            'Lunghezza Title': len(title),
            'Meta Description': desc,
            'Lunghezza Description': len(desc)
        })
    df_org = pd.DataFrame(data_org)

    def style_title(val):
        return 'background-color: #d4edda' if 50 <= val <= 60 else 'background-color: #f8d7da'
    def style_desc(val):
        return 'background-color: #d4edda' if 120 <= val <= 160 else 'background-color: #f8d7da'

    styled = (
        df_org.style
        .format({'URL': lambda u: f"<a href='{u}' target='_blank'>{u}</a>"})
        .set_properties(subset=['Lunghezza Title','Lunghezza Description'], **{'text-align':'center'})
        .map(style_title, subset=['Lunghezza Title'])
        .map(style_desc, subset=['Lunghezza Description'])
    )

    st.subheader("Risultati Organici (top 10)")
    st.dataframe(styled)

    paa_list, related = [], []
    for el in items:
        if el.get('type') == 'people_also_ask':
            paa_list = [q.get('title') for q in el.get('items', [])]
        if el.get('type') in ('related_searches','related_search'):
            for rel in el.get('items', []):
                related.append(rel if isinstance(rel, str) else rel.get('query') or rel.get('keyword'))

    col_paa, col_rel = st.columns(2)
    with col_paa:
        st.subheader("People Also Ask")
        if paa_list:
            st.table(pd.DataFrame({'Domanda': paa_list}))
        else:
            st.write("Nessuna sezione PAA trovata.")
    with col_rel:
        st.subheader("Ricerche Correlate")
        if related:
            st.table(pd.DataFrame({'Query Correlata': related}))
        else:
            st.write("Nessuna sezione Ricerche correlate trovata.")

    # --- PREPARAZIONE TEXTI E PROMPT ---
    separator = "\n\n--- SEPARATORE TESTO ---\n\n"
    competitor_texts = [
        str(st.session_state.get(f"comp_quill_{i}", "") or "")
        for i in range(1, count+1)
    ]
    joined_texts = separator.join(competitor_texts)

    prompt_strategica = f"""
## PROMPT: NLU Semantic Content Intelligence ##

**PERSONA:** Agisci come un **Lead SEO Strategist** con 15 anni di esperienza nel posizionare contenuti in settori altamente competitivi. Il tuo approccio è data-driven, ossessionato dall'intento di ricerca e focalizzato a identificare le debolezze dei competitor per creare contenuti dominanti. Pensa in termini di E-E-A-T, topic authority e user journey.

**CONTESTO:** Ho estratto il contenuto testuale completo delle pagine top-ranking su Google per una query strategica. Il mio obiettivo non è solo eguagliare questi contenuti, ma surclassarli identificando le loro caratteristiche comuni e, soprattutto, le loro lacune.

**OBIETTIVO FINALE:** Esegui una procedura in una singola fase per fornirmi un'analisi comparativa.
1.  **FASE 1: ANALISI COMPARATIVA.** Analizza tutti i testi forniti e aggrega i risultati in una SINGOLA tabella Markdown di sintesi. La tabella deve riflettere la tendenza predominante o la media.

**TESTI DEI COMPETITOR DA ANALIZZARE:**
<TESTI>
{joined_texts}
</TESTI>

---
### **FASE 1: ISTRUZIONI PER LA TABELLA DI ANALISI**

Compila la seguente tabella. Per ogni colonna, analizza TUTTI i testi e sintetizza il risultato. Se noti forti divergenze, segnalale (es. "Misto: 60% Informale, 40% Formale").

| Caratteristica SEO              | Analisi Sintetica                                                     | Giustificazione e Dettagli                                                                 |
| :------------------------------ | :-------------------------------------------------------------------- | :----------------------------------------------------------------------------------------- |
| **Search Intent Primario**      | `[Informazionale, Commerciale, ecc.]`                                  | `[Spiega perché, es: "L'utente cerca definizioni e guide, non vuole ancora comprare."]`    |
| **Search Intent Secondario**    | `[Informazionale, Commerciale, ecc. o "Nessuno"]`                       | `[Spiega il secondo livello di bisogno, es: "Dopo aver capito 'cos'è', l'utente confronta soluzioni."]` |
| **Target Audience & Leggibilità**| `[B2B Esperto, B2C Principiante, Generalista, ecc.]`                  | `[Stima il livello (es: "Linguaggio semplice, per non addetti ai lavori") e il target.]`    |
| **Tone of Voice (ToV)**         | `[Es: "Didattico e professionale", "Empatico e rassicurante"]`         | `[Elenca 3 aggettivi chiave che catturano l'essenza del ToV, es: "autorevole, chiaro, pragmatico".]` |
| **Segnali E-E-A-T**             | `[Deboli / Medi / Forti]`                                             | `[Elenca i segnali trovati, es: "Citazioni di esperti, dati originali, biografia autore, casi studio, link a fonti autorevoli."]` |
| **Angolo del Contenuto**        | `[Es: "Guida definitiva step-by-step", "Analisi comparativa basata su dati", "Elenco curato di risorse"]` | `[Descrive il "gancio" principale usato per attrarre il lettore.]`        |

OUTPUT: Genera **ESCLUSIVAMENTE** la tabella Markdown con la struttura qui sopra, iniziando dalla riga dell’header e **senza** alcuna introduzione o testo aggiuntivo.
"""
    prompt_competitiva = f"""
RUOLO: Agisci come un analista SEO d'élite, specializzato in analisi semantica competitiva con un profondo background in Natural Language Processing (NLP) e Natural Language Understanding (NLU). Sei in grado di imitare i processi di estrazione delle entità nativi di Google.

CONTESTO: L'obiettivo primario è superare i principali competitor per una keyword target specifica. Per raggiungere ciò, è fondamentale analizzare in profondità i testi dei competitor forniti, identificando e categorizzando le entità semantiche rilevanti.

COMPITO: Esegui un'analisi semantica dettagliata dei testi dei competitor forniti, seguendo scrupolosamente questi passaggi:

1. Named Entity Recognition (NER): Estrai tutte le entità nominate dai testi. Escludi rigorosamente entità che sono parte di sezioni FAQ o Domande Frequenti.

2. Identificazione Entità Mancanti (Content Gap): Sulla base delle entità rilevate e della tua conoscenza del settore, identifica entità strategiche che sono assenti nei testi dei competitor ma che sarebbero rilevanti per la keyword target.

3. Categorizzazione delle Entità: Assegna una categoria semantica appropriata ad ogni entità estratta (es. Categoria Prodotto, Brand, Caratteristica Prodotto, Processo di Produzione, Località Geografica, ecc.).

4. Assegnazione Rilevanza Strategica: Valuta e assegna un grado di rilevanza strategica ad ogni entità, utilizzando la seguente scala: Alta, Medio/Alta, Media, Medio/Bassa, Bassa.

5. Filtro Rilevanza: Rimuovi tutte le entità che hanno una rilevanza strategica "Medio/Bassa" e "Bassa" dalle liste finali.

6. Raggruppamento Entità: Le entità che condividono la stessa Categoria e lo stesso grado di Rilevanza Strategica devono essere raggruppate sulla stessa riga nella tabella. Ogni entità all'interno di un raggruppamento deve essere separata da una virgola (;).

7. Formattazione Output: Genera ESCLUSIVAMENTE due tabelle in formato Markdown, attenendoti alla struttura esatta fornita di seguito, senza alcuna introduzione, testo aggiuntivo o commenti. Inizia direttamente dalla riga dell'header di ciascuna tabella.

### TABELLA 1: Entità
| Categoria | Entità | Rilevanza Strategica |
| :--- | :--- | :--- |

### TABELLA 2: Entità Mancanti (Content Gap)
| Categoria | Entità | Rilevanza Strategica |
| :--- | :--- | :--- |

TESTI DEI COMPETITOR:
{joined_texts}
"""

    # --- STEP 2: parallelizzo le due chiamate NLU indipendenti ---
    with st.spinner("Esecuzione parallela delle analisi NLU..."):
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut1 = executor.submit(run_nlu_strategica, prompt_strategica)
            fut2 = executor.submit(run_nlu_competitiva, prompt_competitiva)
            resp1_text = fut1.result()
            resp2_text = fut2.result()

    # Rendering strategica
    st.subheader("Search Intent & Content Analysis with NLU")
    st.markdown(resp1_text, unsafe_allow_html=False)

    # Rendering competitiva
    tables = extract_markdown_tables(resp2_text)
    if len(tables) >= 2:
        table_entities   = tables[0]
        table_contentgap = tables[1]
        st.subheader("Entità Rilevanti (Common Ground)")
        st.markdown(table_entities, unsafe_allow_html=True)
        st.subheader("Entità Mancanti (Content Gap)")
        st.markdown(table_contentgap, unsafe_allow_html=True)
    else:
        st.error("Non sono state trovate due tabelle nel risultato NLU.")
        st.text(resp2_text)
        table_entities = ""
        table_contentgap = ""

    # --- STEP BANCA DATI KEYWORD STRATEGICHE ---
    keyword_principale = query
    table3_related = pd.DataFrame({'Query Correlata': related}).to_markdown(index=False)
    table4_paa     = pd.DataFrame({'Domanda': paa_list}).to_markdown(index=False)

    prompt_bank = f"""
## PROMPT: BANCA DATI KEYWORD STRATEGICHE ##

**PERSONA:** Agisci come un **Semantic SEO Data-Miner**, un analista d'élite il cui unico scopo è estrarre e classificare l'intero patrimonio di keyword di una SERP. Sei un veterano della keyword research che possiede tutti i dati statistici e storici delle varie keywords di Google. Il tuo superpotere è trasformare dati grezzi e disordinati in una "banca dati" di keyword pulita e prioritaria.  
* **Keyword Principale:** {keyword_principale}  
* **Country:** {country}  
* **Lingua:** {language}  
* **Testi Completi dei Competitor:** {joined_texts}  
* **Tabella 1: Entità Principali Estratte dai Competitor:**  
{table_entities}  
* **Tabella 2: Entità Mancanti / Content Gap:**  
{table_contentgap}  
* **Tabella 3: Ricerche Correlate dalla SERP:**  
{table3_related}  
* **Tabella 4: People Anche Ask (PAA) dalla SERP:**  
{table4_paa}

---

<TASK>
**PROCESSO DI ESECUZIONE (In ordine rigoroso):**

1. **Analisi e Classificazione:** Analizza e correla tutti i dati per identificare ogni keyword, concetto e domande. Assegna a ciascuna una tipologia e una priorità strategica e restituisci solo quelle che hanno alti volumi di ricerca, rilevanza semantica con l'argomento e una priorità strategica elevata.
2. **Aggregazione e Sintesi:** Raggruppa tutti gli elementi identificati nelle categorie richieste dal formato di output.
3. **Formattazione dell'Output:** Produci l'output finale nell'unica tabella specificata, seguendo queste regole di formattazione:
    * Usa la virgola come separatore per le liste.
    * **IMPORTANT:** Scrivi tutte le keyword e i concetti in minuscolo. Fai eccezione solo per la lettera iniziale delle "Domande degli Utenti", che deve essere maiuscola.

</TASK>

<OUTPUT_FORMAT>
### Semantic Keyword Mining with NLP

| Categoria Keyword                 | Keywords / Concetti / Domande           | Intento Prevalente           |
| :-------------------------------- | :-------------------------------------- | :---------------------------- |
| **Keyword Principale**            | `{keyword_principale.lower()}`          | _(inserisci intento primario)_|
| **Keyword Secondarie**            | _(elenca keyword secondarie più importanti, non inserire in questa riga la keyword principale se già presente)_      | _(Informazionale / Commerciale ecc.)_|
| **LSI Keywords**                  | _(elenca le migliori Keywords LSI)_                     | _(Supporto all'intento)_      |
| **Domande degli Utenti (FAQ)**    | _(elenca domande, prima lettera maiuscola)_| _(Informazionale (Specifico))_|
</OUTPUT_FORMAT>
"""
    if 'resp3_text' not in st.session_state:
        with st.spinner("Semantic Keyword Mining..."):
            st.session_state['resp3_text'] = run_nlu_mining(prompt_bank)
    resp3_text = st.session_state['resp3_text']

    # estrazione della prima tabella trovata
    tables_mining = extract_markdown_tables(resp3_text)
    if tables_mining:
        table_mining = tables_mining[0]
        st.subheader("Semantic Keyword Mining with NLP")
        st.markdown(table_mining)
    else:
        st.subheader("Semantic Keyword Mining with NLP")
        st.markdown(resp3_text)

    # --- Costruzione export JSON strutturato ---
    analisi_struct        = parse_md_table(resp1_text)
    common_ground_struct  = parse_md_table(table_entities)
    content_gap_struct    = parse_md_table(table_contentgap)
    keyword_mining_struct = parse_md_table(table_mining if tables_mining else resp3_text)

    export_data = {
        "query": query,
        "country": country,
        "language": language,
        "num_competitor": count,
        "competitor_texts": competitor_texts,
        "organic": data_org,
        "people_also_ask": paa_list,
        "related_searches": related,
        "analysis_strategica": analisi_struct,
        "common_ground": common_ground_struct,
        "content_gap": content_gap_struct,
        "keyword_mining": keyword_mining_struct
    }
    export_json = json.dumps(export_data, ensure_ascii=False, indent=2)

    def reset_all():
        keys_to_remove = [
            "query","country","language","num_competitor","analysis_started",
            *(f"comp_quill_{i}" for i in range(1, count+1)),
            "resp3_text"
        ]
        for k in keys_to_remove:
            st.session_state.pop(k, None)

    col1, col2 = st.columns(2)
    with col1:
        st.button("Reset", on_click=reset_all, key="reset_btn")
    with col2:
        st.download_button(
            "Download (json)",
            data=export_json,
            file_name=f"{keyword_principale}.json",
            mime="application/json",
            key="download_json_btn"
        )
