import os
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, urlunparse

import pandas as pd
import requests
import streamlit as st
from google import genai
from streamlit_quill import st_quill

# --- 1. CONFIGURAZIONE E COSTANTI ---

# Configura il client Gemini
try:
    GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except KeyError:
    st.error("GEMINI_API_KEY non trovata. Imposta la variabile d'ambiente.")
    st.stop()

# Configura le credenziali DataForSEO
try:
    DFS_AUTH = (st.secrets["dataforseo"]["username"], st.secrets["dataforseo"]["password"])
except (KeyError, FileNotFoundError):
    st.error("Credenziali DataForSEO non trovate negli secrets di Streamlit.")
    st.stop()

# Sessione HTTP globale per riutilizzo connessioni
session = requests.Session()
session.auth = DFS_AUTH

# Modello Gemini da utilizzare
GEMINI_MODEL = "gemini-1.5-flash-latest"


# --- 2. FUNZIONI DI UTILITY E API ---

@st.cache_data(show_spinner=False)
def get_countries() -> list[str]:
    """Recupera e cachea la lista dei paesi da DataForSEO."""
    try:
        resp = session.get('https://api.dataforseo.com/v3/serp/google/locations')
        resp.raise_for_status()
        locs = resp.json()['tasks'][0]['result']
        return sorted(loc['location_name'] for loc in locs if loc.get('location_type') == 'Country')
    except (requests.RequestException, KeyError, IndexError):
        return []

@st.cache_data(show_spinner=False)
def get_languages() -> list[str]:
    """Recupera e cachea la lista delle lingue da DataForSEO."""
    try:
        resp = session.get('https://api.dataforseo.com/v3/serp/google/languages')
        resp.raise_for_status()
        langs = resp.json()['tasks'][0]['result']
        return sorted(lang['language_name'] for lang in langs)
    except (requests.RequestException, KeyError, IndexError):
        return []

def clean_url(url: str) -> str:
    """Rimuove parametri e frammenti da un URL."""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query="", params="", fragment=""))

@st.cache_data(ttl=600)
def fetch_serp_data(query: str, country: str, language: str) -> dict | None:
    """Esegue la chiamata API a DataForSEO per ottenere i dati della SERP."""
    payload = [{"keyword": query, "location_name": country, "language_name": language}]
    try:
        response = session.post("https://api.dataforseo.com/v3/serp/google/organic/live/advanced", json=payload)
        response.raise_for_status()
        data = response.json()
        if not data.get("tasks") or not data["tasks"][0].get("result"):
            st.error("Risposta da DataForSEO non valida o senza risultati.")
            st.json(data)
            return None
        return data["tasks"][0]["result"][0]
    except requests.RequestException as e:
        st.error(f"Errore chiamata a DataForSEO: {e}")
        return None

def run_nlu(prompt: str, model_name: str = GEMINI_MODEL) -> str:
    """Esegue una singola chiamata al modello Gemini usando il client."""
    try:
        response = gemini_client.models.generate_content(model=model_name, contents=[prompt])
        return response.text
    except Exception as e:
        st.error(f"Errore durante la chiamata a Gemini: {e}")
        return f"ERRORE NLU: {e}"

def parse_markdown_tables(text: str) -> list[pd.DataFrame]:
    """Estrae tutte le tabelle Markdown da un testo e le converte in DataFrame."""
    tables_md = re.findall(r"((?:\|.*\|[\r\n]+)+)", text)
    dataframes = []
    for table_md in tables_md:
        lines = [l.strip() for l in table_md.strip().splitlines()]
        if len(lines) < 2: continue
        
        header = [h.strip() for h in lines[0].split('|')[1:-1]]
        rows_data = [
            [cell.strip() for cell in row.split('|')[1:-1]]
            for row in lines[2:]
            if len(row.split('|')) == len(header) + 2
        ]
        
        if rows_data:
            dataframes.append(pd.DataFrame(rows_data, columns=header))
    return dataframes


# --- 3. FUNZIONI PER LA COSTRUZIONE DEI PROMPT ---

def get_strategica_prompt(keyword: str, texts: str) -> str:
    """Costruisce il prompt per l'analisi strategica."""
    return f"""
## PROMPT: NLU Semantic Content Intelligence ##

**PERSONA:** Agisci come un **Lead SEO Strategist** con 15 anni di esperienza nel posizionare contenuti in settori altamente competitivi. Il tuo approccio è data-driven, ossessionato dall'intento di ricerca e focalizzato a identificare le debolezze dei competitor per creare contenuti dominanti. Pensa in termini di E-E-A-T, topic authority e user journey.

**CONTESTO:** Ho estratto il contenuto testuale completo delle pagine top-ranking su Google per la query strategica specificata di seguito. Il mio obiettivo non è solo eguagliare questi contenuti, ma surclassarli identificando le loro caratteristiche comuni e, soprattutto, le loro lacune.

**QUERY STRATEGICA:** {keyword}

### INIZIO TESTI DEI COMPETITOR DA ANALIZZARE ###

<TESTI>
{texts}
</TESTI>

---

**COMPITO E FORMATO DI OUTPUT:**

Analizza in modo aggregato tutti i testi forniti tra i delimitatori `### INIZIO` e `### FINE`. Sintetizza le tue scoperte compilando la seguente tabella Markdown. Per ogni riga, la tua analisi deve rappresentare la tendenza predominante o la media osservata in TUTTI i testi. Se noti forti divergenze, segnalale nel campo "Giustificazione e Dettagli".

Genera **ESCLUSIVAMENTE** la tabella Markdown completa, iniziando dalla riga dell’header e **senza** alcuna introduzione, commento o testo conclusivo.

| Caratteristica SEO | Analisi Sintetica | Giustificazione e Dettagli |
| :--- | :--- | :--- |
| **Search Intent Primario** | `[Determina e inserisci qui: Informazionale, Commerciale, Transazionale, Navigazionale]` | `[Spiega perché, es: "L'utente cerca definizioni, guide e 'come fare', indicando una fase di apprendimento."]` |
| **Search Intent Secondario** | `[Determina e inserisci qui l'intento secondario o "Nessuno evidente"]` | `[Spiega il secondo livello di bisogno, es: "Dopo aver capito 'cos'è', l'utente inizia a confrontare soluzioni e prodotti."]` |
| **Target Audience & Leggibilità** | `[Definisci il target, es: "B2C Principiante", "B2B Esperto", "Generalista"]` | `[Stima il livello di complessità, es: "Linguaggio semplice e accessibile, evita gergo tecnico. Adatto a non addetti ai lavori."]` |
| **Tone of Voice (ToV)** | `[Sintetizza il ToV predominante, es: "Didattico e professionale"]` | `[Elenca 3 aggettivi chiave che catturano l'essenza del ToV, es: "autorevole, chiaro, pragmatico".]` |
"""

def get_competitiva_prompt(keyword: str, texts: str) -> str:
    """Costruisce il prompt per l'analisi competitiva (entità)."""
    return f"""
**RUOLO**: Agisci come un analista SEO d'élite, specializzato in analisi semantica competitiva con un profondo background in Natural Language Processing (NLP) e Natural Language Understanding (NLU). Sei in grado di imitare i processi di estrazione delle entità nativi di Google.

**CONTESTO**: L'obiettivo primario è superare i principali competitor per la keyword target. Per raggiungere ciò, è fondamentale analizzare in profondità i testi dei competitor forniti, identificando e categorizzando le entità semantiche rilevanti.

**KEYWORD TARGET**: {keyword}

### INIZIO TESTI DA ANALIZZARE ###

<TESTI>
{texts}
</TESTI>

### FINE TESTI DA ANALIZZARE ###

**COMPITO**: Esegui un'analisi semantica dettagliata dei testi contenuti tra i delimitatori `### INIZIO TESTI DA ANALIZZARE ###` e `### FINE TESTI DA ANALIZZARE ###`, seguendo scrupolosamente questi passaggi:

1.  **Named Entity Recognition (NER):** Estrai tutte le entità nominate dai testi. Escludi rigorosamente entità che sono parte di sezioni FAQ o Domande Frequenti.
2.  **Identificazione Entità Mancanti (Content Gap):** Sulla base delle entità rilevate e della tua conoscenza del settore, identifica entità strategiche che sono assenti nei testi dei competitor ma che sarebbero rilevanti per la keyword target.
3.  **Categorizzazione delle Entità:** Assegna una categoria semantica appropriata ad ogni entità estratta (es. Categoria Prodotto, Brand, Caratteristica Prodotto, Processo di Produzione, Località Geografica, ecc.).
4.  **Assegnazione Rilevanza Strategica:** Valuta e assegna un grado di rilevanza strategica ad ogni entità, utilizzando la seguente scala: Alta, Medio/Alta, Media, Medio/Bassa, Bassa.
5.  **Filtro Rilevanza:** Rimuovi tutte le entità che hanno una rilevanza strategica "Medio/Bassa" e "Bassa" dalle liste finali.
6.  **Raggruppamento Entità:** Le entità che condividono la stessa Categoria e lo stesso grado di Rilevanza Strategica devono essere raggruppate sulla stessa riga nella tabella. Ogni entità all'interno di un raggruppamento deve essere separata da una virgola (,).
7.  **Formattazione Output:** Genera ESCLUSIVAMENTE due tabelle in formato Markdown, attenendoti alla struttura esatta fornita di seguito. Non aggiungere alcuna introduzione, testo aggiuntivo o commenti. Inizia direttamente con la prima tabella.

### TABELLA 1: Entità
| Categoria | Entità | Rilevanza Strategica |
| :--- | :--- | :--- |

### TABELLA 2: Entità Mancanti (Content Gap)
| Categoria | Entità | Rilevanza Strategica |
| :--- | :--- | :--- |
"""

def get_mining_prompt(**kwargs) -> str:
    """Costruisce il prompt per il keyword mining."""
    return f"""
## PROMPT: BANCA DATI KEYWORD STRATEGICHE ##

**PERSONA:** Agisci come un **Semantic SEO Data-Miner**, un analista d'élite il cui unico scopo è estrarre e classificare l'intero patrimonio di keyword di una SERP. Sei un veterano della keyword research che possiede tutti i dati statistici e storici delle varie keywords di Google. Il tuo superpotere è trasformare dati grezzi e disordinati in una "banca dati" di keyword pulita e prioritaria.

---
### DATI DI INPUT ###

**1. CONTESTO DI BASE**
* **Keyword Principale:** {kwargs.get('keyword', '')}
* **Country:** {kwargs.get('country', '')}
* **Lingua:** {kwargs.get('language', '')}

**2. CONTENUTI GREZZI DA ANALIZZARE**
* **Testi Completi dei Competitor:**
    {kwargs.get('texts', '')}

**3. DATI STRUTTURATI DALLA SERP E DAI TESTI**
* **Tabella 1: Entità Principali Estratte dai Competitor:**
    {kwargs.get('entities_table', '')}
* **Tabella 2: Entità Mancanti / Content Gap:**
    {kwargs.get('gap_table', '')}
* **Tabella 3: Ricerche Correlate dalla SERP:**
    {kwargs.get('related_table', '')}
* **Tabella 4: People Also Ask (PAA) dalla SERP:**
    {kwargs.get('paa_table', '')}

---

### COMPITO E FORMATO DI OUTPUT ###

**PROCESSO DI ESECUZIONE (In ordine rigoroso):**

1.  **Assimilazione e Correlazione:** Analizza e metti in relazione TUTTI i dati forniti nella sezione "DATI DI INPUT". Il tuo obiettivo è trovare le connessioni tra i concetti nei testi grezzi, le entità estratte, le ricerche correlate e le domande degli utenti (PAA).
2.  **Identificazione e Filtraggio:** Da questa analisi, estrai una lista completa di **keyword secondarie, varianti della keyword principale, sinonimi, termini semanticamente correlati** e domande. Filtra questa lista per mantenere **solo** gli elementi che soddisfano tutti questi criteri:
    * Alta rilevanza semantica con la **Keyword Principale**.
    * Alta priorità strategica per l'utente (rispondono a bisogni chiave).
    * Supportati da alti volumi di ricerca (basandoti sulla tua conoscenza da esperto).
3.  **Compilazione e Formattazione:** Aggrega gli elementi filtrati nella tabella sottostante. Attieniti scrupolosamente alle seguenti regole:
    * Usa la virgola (`,`) come separatore per le liste di keyword/concetti all'interno della stessa cella.
    * **IMPORTANTE:** Scrivi tutte le keyword e i concenti in **minuscolo**. L'unica eccezione sono le "Domande degli Utenti", dove la prima lettera della domanda deve essere **maiuscola**.

Genera **ESCLUSIVAMENTE** la tabella Markdown finale, iniziando dalla riga dell'header e senza aggiungere alcuna introduzione o commento.

### Semantic Keyword Mining with NLP

| Categoria Keyword | Keywords / Concetti / Domande | Intento Prevalente |
| :--- | :--- | :--- |
| **Keyword Principale** | `{kwargs.get('keyword', '').lower()}` | _(determina e inserisci l'intento primario)_ |
| **Keyword Secondarie** | _(elenca le keyword secondarie più importanti; non ripetere la keyword principale)_ | _(Informazionale / Commerciale ecc.)_ |
| **Keyword Correlate e Varianti** | _(elenca varianti, sinonimi e concetti semanticamente correlati più strategici)_ | _(Supporto all'intento)_ |
| **Domande degli Utenti (FAQ)** | _(elenca le domande più rilevanti e ricercate, prima lettera maiuscola)_ | _(Informazionale (Specifico))_ |
"""

# --- 4. INTERFACCIA UTENTE E FLUSSO PRINCIPALE ---

st.title("Analisi SEO Competitiva Multi-Step")
st.markdown("Questo tool esegue analisi SEO integrando SERP scraping e NLU.")
st.divider()

if 'analysis_started' not in st.session_state:
    st.session_state.analysis_started = False

with st.container():
    col1, col2, col3, col4 = st.columns(4)
    query = col1.text_input("Query", key="query")
    country = col2.selectbox("Country", [""] + get_countries(), key="country")
    language = col3.selectbox("Lingua", [""] + get_languages(), key="language")
    num_comp_opts = [""] + list(range(1, 6))
    num_comp = col4.selectbox("Numero competitor", num_comp_opts, key="num_competitor")
    count = int(num_comp) if isinstance(num_comp, int) else 0

with st.expander("Testi dei Competitor", expanded=not st.session_state.analysis_started):
    if not st.session_state.analysis_started and count > 0:
        idx = 1
        for _ in range((count + 1) // 2):
            cols_pair = st.columns(2)
            for col in cols_pair:
                if idx <= count:
                    with col:
                        st.markdown(f"**Testo Competitor #{idx}**")
                        st_quill(key=f"comp_quill_{idx}", html=False, placeholder=f"Incolla qui il testo del Competitor #{idx}")
                    idx += 1

def start_analysis():
    if not all([st.session_state.query, st.session_state.country, st.session_state.language, st.session_state.num_competitor]):
        st.error("Tutti i campi (Query, Country, Lingua, Numero competitor) sono obbligatori.")
    else:
        st.session_state.analysis_started = True

st.button("🚀 Avvia l'Analisi", on_click=start_analysis, type="primary")

# --- ESECUZIONE ANALISI ---
if st.session_state.analysis_started:
    
    with st.spinner("Recupero e analisi dati SERP..."):
        serp_result = fetch_serp_data(query, country, language)
        if not serp_result:
            st.error("Analisi interrotta a causa di un errore nel recupero dei dati SERP.")
            st.stop()
            
        items = serp_result.get('items', [])
        organic_results = [item for item in items if item.get("type") == "organic"][:10]
        paa_list = list(dict.fromkeys(
            q.get("title", "") 
            for item in items if item.get("type") == "people_also_ask" 
            for q in item.get("items", []) if q.get("title")
        ))
        
        related_raw = []
        for item in items:
            if item.get("type") in ("related_searches", "related_search"):
                for s in item.get("items", []):
                    term = s if isinstance(s, str) else s.get("query", "")
                    if term:
                        related_raw.append(term)
        related_list = list(dict.fromkeys(related_raw))

        df_org = pd.DataFrame([
            {"URL": clean_url(r.get("url", "")), 
             "Meta Title": r.get("title", ""), "Lunghezza Title": len(r.get("title", "")),
             "Meta Description": r.get("description", ""), "Lunghezza Description": len(r.get("description", ""))}
            for r in organic_results
        ])

    st.subheader("Risultati Organici (Top 10)")
    st.dataframe(df_org, use_container_width=True, hide_index=True)
    
    col_paa, col_rel = st.columns(2)
    col_paa.subheader("People Also Ask")
    col_paa.dataframe(pd.DataFrame(paa_list, columns=["Domanda"]), use_container_width=True, hide_index=True)
    col_rel.subheader("Ricerche Correlate")
    col_rel.dataframe(pd.DataFrame(related_list, columns=["Query Correlata"]), use_container_width=True, hide_index=True)

    competitor_texts_list = [st.session_state.get(f"comp_quill_{i}", "") for i in range(1, count + 1)]
    joined_texts = "\n\n--- SEPARATORE TESTO ---\n\n".join(filter(None, competitor_texts_list))

    with st.spinner("Esecuzione analisi NLU Strategica e Competitiva in parallelo..."):
        with ThreadPoolExecutor() as executor:
            future_strat = executor.submit(run_nlu, get_strategica_prompt(query, joined_texts))
            future_comp = executor.submit(run_nlu, get_competitiva_prompt(query, joined_texts))
            nlu_strat_text = future_strat.result()
            nlu_comp_text = future_comp.result()

    dfs_strat = parse_markdown_tables(nlu_strat_text)
    st.subheader("Analisi Strategica (Intento, Audience, ToV)")
    st.dataframe(dfs_strat[0] if dfs_strat else pd.DataFrame(), use_container_width=True, hide_index=True)
    
    dfs_comp = parse_markdown_tables(nlu_comp_text)
    df_entities = dfs_comp[0] if len(dfs_comp) > 0 else pd.DataFrame()
    df_gap = dfs_comp[1] if len(dfs_comp) > 1 else pd.DataFrame()
    
    st.subheader("Entità Rilevanti (Common Ground)")
    st.dataframe(df_entities, use_container_width=True, hide_index=True)
    st.subheader("Entità Mancanti (Content Gap)")
    st.dataframe(df_gap, use_container_width=True, hide_index=True)

    with st.spinner("Esecuzione NLU per Keyword Mining..."):
        prompt_mining_args = {
            "keyword": query, "country": country, "language": language, "texts": joined_texts,
            "entities_table": df_entities.to_markdown(index=False),
            "gap_table": df_gap.to_markdown(index=False),
            "related_table": pd.DataFrame(related_list, columns=["Query Correlata"]).to_markdown(index=False),
            "paa_table": pd.DataFrame(paa_list, columns=["Domanda"]).to_markdown(index=False)
        }
        nlu_mining_text = run_nlu(get_mining_prompt(**prompt_mining_args))
    
    dfs_mining = parse_markdown_tables(nlu_mining_text)
    df_mining = dfs_mining[0] if dfs_mining else pd.DataFrame()
    st.subheader("Semantic Keyword Mining")
    st.dataframe(df_mining, use_container_width=True, hide_index=True)

    export_data = {
        "query": query, "country": country, "language": language,
        "num_competitor": count, "competitor_texts": competitor_texts_list,
        "organic": df_org.to_dict(orient="records"),
        "people_also_ask": paa_list, "related_searches": related_list,
        "analysis_strategica": dfs_strat[0].to_dict(orient="records") if dfs_strat else [],
        "common_ground": df_entities.to_dict(orient="records"),
        "content_gap": df_gap.to_dict(orient="records"),
        "keyword_mining": df_mining.to_dict(orient="records")
    }
    
    def reset_analysis():
        keys_to_clear = list(st.session_state.keys())
        for key in keys_to_clear:
            if key != 'data': 
                 del st.session_state[key]
        
    col_btn1, col_btn2 = st.columns(2)
    col_btn1.button("↩️ Nuova Analisi", on_click=reset_analysis)
    col_btn2.download_button(
        label="📥 Download Risultati (JSON)",
        data=json.dumps(export_data, ensure_ascii=False, indent=2),
        file_name=f"analisi_seo_{query.replace(' ', '_')}.json",
        mime="application/json",
    )
