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

# Configura il client Gemini (fallisce subito se la chiave non è presente)
try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
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

@st.cache_data
def get_api_data(url: str, result_key: str, name_key: str) -> list[str]:
    """Funzione generica e cacheata per recuperare dati (lingue/paesi) da DataForSEO."""
    try:
        response = session.get(url)
        response.raise_for_status()
        results = response.json()["tasks"][0]["result"]
        return sorted(item[name_key] for item in results if item.get("location_type") != "Continent")
    except (requests.RequestException, KeyError, IndexError) as e:
        st.error(f"Impossibile recuperare i dati da {url}. Errore: {e}")
        return []

def clean_url(url: str) -> str:
    """Rimuove parametri e frammenti da un URL."""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query="", params="", fragment=""))

@st.cache_data(ttl=600)
def fetch_serp_data(query: str, country: str, language: str) -> dict | None:
    """Esegue la chiamata API a DataForSEO per ottenere i dati della SERP."""
    payload = [{
        "keyword": query,
        "location_name": country,
        "language_name": language,
    }]
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
    """Esegue una singola chiamata al modello Gemini e restituisce il testo."""
    model = genai.GenerativeModel(model_name)
    try:
        response = model.generate_content(prompt)
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
        if len(lines) < 2:
            continue
        
        header = [h.strip() for h in lines[0].split('|')[1:-1]]
        # Rimuovi la linea di separazione '---'
        rows_data = [
            [cell.strip() for cell in row.split('|')[1:-1]]
            for row in lines[2:]
        ]
        
        # Filtra righe che non hanno il numero corretto di colonne
        rows_data = [row for row in rows_data if len(row) == len(header)]
        
        if rows_data:
            dataframes.append(pd.DataFrame(rows_data, columns=header))
            
    return dataframes


# --- 3. FUNZIONI PER LA COSTRUZIONE DEI PROMPT ---

def get_strategica_prompt(keyword: str, texts: str) -> str:
    """Costruisce il prompt per l'analisi strategica."""
    return f"""
**PERSONA:** Agisci come un Lead SEO Strategist con 15 anni di esperienza.
**CONTESTO:** Ho estratto i testi dei top-ranking per la query '{keyword}'. Identifica le loro caratteristiche comuni e le lacune per surclassarli.
**QUERY STRATEGICA:** {keyword}
**TESTI DEI COMPETITOR:**\n{texts}
**COMPITO:** Analizza i testi e compila ESCLUSIVAMENTE la seguente tabella Markdown, sintetizzando la tendenza predominante.
| Caratteristica SEO | Analisi Sintetica | Giustificazione e Dettagli |
| :--- | :--- | :--- |
| **Search Intent Primario** | `[Informazionale, Commerciale, Transazionale, Navigazionale]` | `[Spiega perché, basandoti sui testi]` |
| **Search Intent Secondario** | `[Determina l'intento secondario o "Nessuno evidente"]` | `[Spiega il secondo livello di bisogno]` |
| **Target Audience & Leggibilità** | `[Definisci il target, es: "B2C Principiante"]` | `[Stima la complessità del linguaggio]` |
| **Tone of Voice (ToV)** | `[Sintetizza il ToV, es: "Didattico e professionale"]` | `[Elenca 3 aggettivi chiave, es: "autorevole, chiaro"]` |
"""

def get_competitiva_prompt(keyword: str, texts: str) -> str:
    """Costruisce il prompt per l'analisi competitiva (entità)."""
    return f"""
**RUOLO**: Agisci come un analista SEO d'élite specializzato in analisi semantica competitiva.
**CONTESTO**: L'obiettivo è superare i competitor per la keyword '{keyword}' identificando le entità semantiche rilevanti e quelle mancanti.
**TESTI DA ANALIZZARE:**\n{texts}
**COMPITO**: Esegui un'analisi semantica e genera ESCLUSIVAMENTE due tabelle Markdown.
1. Estrai le entità nominate e assegna loro una categoria semantica (es. Brand, Caratteristica Prodotto, ecc.) e una rilevanza strategica (Alta, Media). Filtra via la rilevanza Bassa.
2. Identifica le entità mancanti strategiche (Content Gap).
3. Raggruppa le entità per Categoria e Rilevanza.

### TABELLA 1: Entità Rilevanti (Common Ground)
| Categoria | Entità | Rilevanza Strategica |
| :--- | :--- | :--- |

### TABELLA 2: Entità Mancanti (Content Gap)
| Categoria | Entità | Rilevanza Strategica |
| :--- | :--- | :--- |
"""

def get_mining_prompt(**kwargs) -> str:
    """Costruisce il prompt per il keyword mining."""
    return f"""
**PERSONA:** Agisci come un Semantic SEO Data-Miner il cui scopo è estrarre e classificare l'intero patrimonio di keyword di una SERP.
**DATI DI INPUT:**
* Keyword Principale: {kwargs.get('keyword', '')}
* Country: {kwargs.get('country', '')}
* Lingua: {kwargs.get('language', '')}
* Testi dei Competitor:\n{kwargs.get('texts', '')}
* Tabella Entità Principali:\n{kwargs.get('entities_table', '')}
* Tabella Content Gap:\n{kwargs.get('gap_table', '')}
* Ricerche Correlate:\n{kwargs.get('related_table', '')}
* People Also Ask:\n{kwargs.get('paa_table', '')}
**COMPITO:** Analizza e correla TUTTI i dati di input. Estrai una lista filtrata di keyword secondarie, varianti, sinonimi e domande con alta rilevanza e volume di ricerca. Compila ESCLUSIVAMENTE la seguente tabella Markdown, usando keyword in minuscolo (tranne la prima lettera delle domande).
| Categoria Keyword | Keywords / Concetti / Domande | Intento Prevalente |
| :--- | :--- | :--- |
| **Keyword Principale** | `{kwargs.get('keyword', '').lower()}` | _(determina e inserisci l'intento)_ |
| **Keyword Secondarie** | _(elenca le keyword secondarie più importanti)_ | _(Informazionale / Commerciale ecc.)_ |
| **Keyword Correlate e Varianti** | _(elenca varianti, sinonimi e concetti strategici)_ | _(Supporto all'intento)_ |
| **Domande degli Utenti (FAQ)** | _(elenca le domande più rilevanti e ricercate)_ | _(Informazionale (Specifico))_ |
"""


# --- 4. INTERFACCIA UTENTE E FLUSSO PRINCIPALE ---

st.title("Analisi SEO Competitiva Multi-Step")
st.markdown("Questo tool esegue analisi SEO integrando SERP scraping e NLU.")
st.divider()

# Inizializzazione stato
if 'analysis_started' not in st.session_state:
    st.session_state.analysis_started = False

# Input form
with st.container():
    col1, col2, col3, col4 = st.columns(4)
    query = col1.text_input("Query", key="query")
    country = col2.selectbox("Country", get_api_data("https://api.dataforseo.com/v3/serp/google/locations", "result", "location_name"), key="country")
    language = col3.selectbox("Lingua", get_api_data("https://api.dataforseo.com/v3/serp/google/languages", "result", "language_name"), key="language")
    num_comp = col4.selectbox("Numero competitor", list(range(1, 6)), index=2, key="num_competitor")

with st.expander("Testi dei Competitor", expanded=not st.session_state.analysis_started):
    if not st.session_state.analysis_started:
        # Crea dinamicamente gli editor di testo per i competitor
        for i in range(1, num_comp + 1):
            st_quill(key=f"comp_quill_{i}", html=False, placeholder=f"Incolla qui il testo del Competitor #{i}")

def start_analysis():
    if not all([st.session_state.query, st.session_state.country, st.session_state.language]):
        st.error("Query, Country e Lingua sono obbligatori per avviare l'analisi.")
    else:
        st.session_state.analysis_started = True

st.button("🚀 Avvia l'Analisi", on_click=start_analysis, type="primary")

# --- ESECUZIONE ANALISI ---
if st.session_state.analysis_started:
    
    # 1. Fetch e analisi SERP
    with st.spinner("Recupero e analisi dati SERP..."):
        serp_result = fetch_serp(query, country, language)
        if not serp_result:
            st.error("Analisi interrotta a causa di un errore nel recupero dei dati SERP.")
            st.stop()

        items = serp_result.get('items', [])
        
        # Estrazione Dati Strutturati
        organic_results = [item for item in items if item.get("type") == "organic"][:10]
        paa_list = list(dict.fromkeys(q.get("title", "") for item in items if item.get("type") == "people_also_ask" for q in item.get("items", []) if q.get("title")))
        related_list = list(dict.fromkeys(s.get("query", "") for item in items if item.get("type") in ("related_searches", "related_search") for s in item.get("items", []) if s.get("query")))

        # Preparazione DataFrame Organici
        df_org = pd.DataFrame([
            {
                "URL": clean_url(r.get("url", "")),
                "Meta Title": r.get("title", ""),
                "Lunghezza Title": len(r.get("title", "")),
                "Meta Description": r.get("description", ""),
                "Lunghezza Description": len(r.get("description", "")),
            }
            for r in organic_results
        ])

    # Visualizzazione Dati SERP
    st.subheader("Risultati Organici (Top 10)")
    st.dataframe(df_org, use_container_width=True, hide_index=True)
    
    col_paa, col_rel = st.columns(2)
    col_paa.subheader("People Also Ask")
    col_paa.dataframe(pd.DataFrame(paa_list, columns=["Domanda"]), use_container_width=True, hide_index=True)
    col_rel.subheader("Ricerche Correlate")
    col_rel.dataframe(pd.DataFrame(related_list, columns=["Query Correlata"]), use_container_width=True, hide_index=True)

    # 2. Analisi NLU in parallelo
    competitor_texts_list = [st.session_state.get(f"comp_quill_{i}", "") for i in range(1, num_comp + 1)]
    joined_texts = "\n\n--- SEPARATORE TESTO ---\n\n".join(filter(None, competitor_texts_list))

    with st.spinner("Esecuzione analisi NLU Strategica e Competitiva in parallelo..."):
        with ThreadPoolExecutor() as executor:
            future_strat = executor.submit(run_nlu, get_strategica_prompt(query, joined_texts))
            future_comp = executor.submit(run_nlu, get_competitiva_prompt(query, joined_texts))
            
            nlu_strat_text = future_strat.result()
            nlu_comp_text = future_comp.result()

    # Parsing e visualizzazione risultati NLU
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

    # 3. Keyword Mining
    with st.spinner("Esecuzione NLU per Keyword Mining..."):
        prompt_mining_args = {
            "keyword": query, "country": country, "language": language, "texts": joined_texts,
            "entities_table": df_entities.to_markdown(index=False),
            "gap_table": df_gap.to_markdown(index=False),
            "related_table": pd.DataFrame(related_list).to_markdown(index=False),
            "paa_table": pd.DataFrame(paa_list).to_markdown(index=False)
        }
        nlu_mining_text = run_nlu(get_mining_prompt(**prompt_mining_args))
    
    dfs_mining = parse_markdown_tables(nlu_mining_text)
    st.subheader("Semantic Keyword Mining")
    df_mining = dfs_mining[0] if dfs_mining else pd.DataFrame()
    st.dataframe(df_mining, use_container_width=True, hide_index=True)

    # 4. Preparazione e download JSON
    export_data = {
        "query": query, "country": country, "language": language,
        "num_competitor": num_comp, "competitor_texts": competitor_texts_list,
        "organic": df_org.to_dict(orient="records"),
        "people_also_ask": paa_list, "related_searches": related_list,
        "analysis_strategica": dfs_strat[0].to_dict(orient="records") if dfs_strat else [],
        "common_ground": df_entities.to_dict(orient="records"),
        "content_gap": df_gap.to_dict(orient="records"),
        "keyword_mining": df_mining.to_dict(orient="records")
    }
    
    def reset_analysis():
        st.session_state.analysis_started = False
        # Potresti voler pulire anche altri campi qui
        
    col_btn1, col_btn2 = st.columns(2)
    col_btn1.button("↩️ Nuova Analisi", on_click=reset_analysis)
    col_btn2.download_button(
        label="📥 Download Risultati (JSON)",
        data=json.dumps(export_data, ensure_ascii=False, indent=2),
        file_name=f"analisi_seo_{query.replace(' ', '_')}.json",
        mime="application/json",
    )
