import os
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlunparse
from collections import Counter

import pandas as pd
import requests
import streamlit as st
from google import genai
from streamlit_quill import st_quill
from bs4 import BeautifulSoup

# --- 1. CONFIGURAZIONE E COSTANTI ---

# Configura il client Gemini
try:
    # Per deployment su Streamlit Cloud, la chiave va messa nei Secrets
    GEMINI_API_KEY = st.secrets.get("gemini", {}).get("api_key") or os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        st.error("GEMINI_API_KEY non trovata. Impostala nei Secrets di Streamlit o come variabile d'ambiente.")
        st.stop()
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_client = genai.GenerativeModel("gemini-1.5-pro-latest")
except Exception as e:
    st.error(f"Errore nella configurazione di Gemini: {e}")
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

# Modello Gemini da utilizzare (già definito nella creazione del client)
GEMINI_MODEL_NAME = "gemini-1.5-pro-latest"


# --- 2. FUNZIONI DI UTILITY E API ---

@st.cache_data(show_spinner="Caricamento Paesi...")
def get_countries() -> list[str]:
    """Recupera e cachea la lista dei paesi da DataForSEO."""
    try:
        resp = session.get('https://api.dataforseo.com/v3/serp/google/locations')
        resp.raise_for_status()
        locs = resp.json()['tasks'][0]['result']
        return sorted(loc['location_name'] for loc in locs if loc.get('location_type') == 'Country')
    except (requests.RequestException, KeyError, IndexError) as e:
        st.warning(f"Impossibile caricare la lista dei paesi: {e}")
        return ["United States", "Italy", "United Kingdom", "Germany", "France", "Spain"]

@st.cache_data(show_spinner="Caricamento Lingue...")
def get_languages() -> list[str]:
    """Recupera e cachea la lista delle lingue da DataForSEO."""
    try:
        resp = session.get('https://api.dataforseo.com/v3/serp/google/languages')
        resp.raise_for_status()
        langs = resp.json()['tasks'][0]['result']
        return sorted(lang['language_name'] for lang in langs)
    except (requests.RequestException, KeyError, IndexError) as e:
        st.warning(f"Impossibile caricare la lista delle lingue: {e}")
        return ["English", "Italian", "German", "French", "Spanish"]

def clean_url(url: str) -> str:
    """Rimuove parametri e frammenti da un URL."""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query="", params="", fragment=""))

@st.cache_data(ttl=600, show_spinner="Analisi SERP in corso...")
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

@st.cache_data(ttl=3600, show_spinner=False)
def parse_url_content(url: str) -> dict:
    """
    Estrae il 'main_topic' e gli headings da una pagina.
    Restituisce un dizionario con contenuto HTML e lista di headings.
    """
    default_return = {"html_content": "", "headings": []}
    if not url or url.lower().endswith('.pdf'):
        return default_return

    post_data = [{"url": url, "enable_javascript": True, "enable_xhr": True, "disable_cookie_popup": True}]
    try:
        response = session.post("https://api.dataforseo.com/v3/on_page/content_parsing/live", json=post_data)
        response.raise_for_status()
        data = response.json()

        if data.get("tasks_error", 0) > 0 or not data.get("tasks") or not data["tasks"][0].get("result"):
            return default_return

        result_list = data["tasks"][0].get("result")
        if not result_list: return default_return

        items_list = result_list[0].get("items")
        if not items_list: return default_return

        page_content = items_list[0].get("page_content")
        if not page_content: return default_return

        main_topic_data = page_content.get('main_topic')
        if not isinstance(main_topic_data, list): return default_return

        html_parts, headings = [], []
        for section in main_topic_data:
            h_title = section.get('h_title')
            if h_title:
                level = section.get('level', 2)
                html_parts.append(f"<h{level}>{h_title}</h{level}>")
                headings.append(f"H{level}: {h_title}")

            primary_content_list = section.get('primary_content')
            if isinstance(primary_content_list, list):
                # Semplice logica per formattare paragrafi e liste
                for item in primary_content_list:
                    text = item.get("text", "").strip()
                    if text:
                        html_parts.append(f"<p>{text}</p>")

        return {"html_content": "".join(html_parts), "headings": headings}

    except (requests.RequestException, KeyError, IndexError, TypeError):
        return default_return

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_ranked_keywords(url: str, location: str, language: str) -> dict:
    """Estrae le keyword posizionate e restituisce un dizionario con lo stato."""
    payload = [{"target": url, "location_name": location, "language_name": language, "limit": 30}]
    try:
        response = session.post("https://api.dataforseo.com/v3/dataforseo_labs/google/ranked_keywords/live", json=payload)
        response.raise_for_status()
        data = response.json()
        if data.get("tasks_error", 0) > 0 or not data.get("tasks") or not data["tasks"][0].get("result"):
            error_message = data.get("tasks",[{}])[0].get("status_message", "Nessun risultato nell'API.")
            return {"url": url, "status": "failed", "error": error_message, "items": []}
        
        api_items = data["tasks"][0]["result"][0].get("items")
        return {"url": url, "status": "ok", "items": api_items if api_items is not None else []}
    except requests.RequestException as e:
        return {"url": url, "status": "failed", "error": str(e), "items": []}

def run_nlu(prompt: str) -> str:
    """Esegue una singola chiamata al modello Gemini."""
    try:
        response = gemini_client.generate_content(prompt)
        # Accesso al testo con il nuovo SDK
        if response.parts:
            return response.text
        # Gestione di risposte bloccate per sicurezza
        return "Nessun contenuto generato. La risposta potrebbe essere stata bloccata per motivi di sicurezza."
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
        
        # Ignora la linea di separazione (es. |:---|:---|)
        header_line = lines[0]
        separator_line_index = -1
        for i, line in enumerate(lines):
            if all(cell.strip().startswith(':--') for cell in line.split('|')[1:-1]):
                separator_line_index = i
                break
        
        if separator_line_index == -1: continue

        header = [h.strip() for h in header_line.split('|')[1:-1]]
        data_lines = lines[separator_line_index + 1:]
        
        rows_data = []
        for row in data_lines:
            cells = [cell.strip() for cell in row.split('|')[1:-1]]
            if len(cells) == len(header):
                rows_data.append(cells)
        
        if rows_data:
            dataframes.append(pd.DataFrame(rows_data, columns=header))
    return dataframes

# --- 3. NUOVE FUNZIONI PER LA COSTRUZIONE DEI PROMPT ---

def get_strategica_prompt(keyword: str, texts: str) -> str:
    # (Invariato - Ottimo prompt)
    return f"""
## PROMPT: NLU Semantic Content Intelligence ##
**PERSONA:** Agisci come un **Lead SEO Strategist** con 15 anni di esperienza nel posizionare contenuti in settori altamente competitivi. Il tuo approccio è data-driven, ossessionato dall'intento di ricerca e focalizzato a identificare le debolezze dei competitor per creare contenuti dominanti. Pensa in termini di E-E-A-T, topic authority e user journey.
**CONTESTO:** Ho estratto il contenuto testuale completo delle pagine top-ranking su Google per la query strategica specificata. Il mio obiettivo non è solo eguagliare questi contenuti, ma surclassarli.
**QUERY STRATEGICA:** {keyword}
### INIZIO TESTI DEI COMPETITOR DA ANALIZZARE ###
<TESTI>
{texts}
</TESTI>
---
**COMPITO E FORMATO DI OUTPUT:**
**Parte 1: Tabella Sintetica**
Analizza in modo aggregato tutti i testi forniti. Sintetizza le tue scoperte compilando la seguente tabella Markdown. Per ogni riga, la tua analisi deve rappresentare la tendenza predominante. Genera **ESCLUSIVAMENTE** la tabella Markdown completa.
| Caratteristica SEO | Analisi Sintetica |
| :--- | :--- |
| **Search Intent Primario** | `[Determina e inserisci qui: Informazionale, Commerciale, Transazionale, Navigazionale. Aggiungi tra parentesi un brevissimo approfondimento]` |
| **Search Intent Secondario** | `[Determina e inserisci qui l'intento secondario, se presente. Aggiungi breve approfondimento]` |
| **Target Audience** | `[Definisci il target audience in massimo 10 parole]` |
| **Tone of Voice (ToV)** | `[Sintetizza il ToV predominante con 3 aggettivi chiave]` |
**Parte 2: Analisi Approfondita Audience**
Dopo la tabella, inserisci un separatore `---` seguito da un'analisi dettagliata del target audience con l'intestazione esatta: `### Analisi Approfondita Audience ###`. Descrivi il pubblico in termini di livello di conoscenza, bisogni e pain points.
"""

def get_competitiva_prompt(keyword: str, texts: str) -> str:
    # (Invariato - Ottimo prompt)
    return f"""
**RUOLO**: Agisci come un analista SEO d'élite, specializzato in analisi semantica competitiva con un profondo background in NLP.
**CONTESTO**: L'obiettivo è superare i competitor per la keyword target analizzando i loro testi per identificare e categorizzare le entità semantiche rilevanti.
**KEYWORD TARGET**: {keyword}
### INIZIO TESTI DA ANALIZZARE ###
<TESTI>
{texts}
</TESTI>
### FINE TESTI DA ANALIZZARE ###
**COMPITO**: Esegui un'analisi semantica dettagliata dei testi.
1.  **Named Entity Recognition (NER):** Estrai tutte le entità nominate rilevanti.
2.  **Categorizzazione:** Assegna una categoria semantica appropriata (es. Prodotto, Brand, Caratteristica, Località, Concetto Astratto).
3.  **Rilevanza:** Assegna una rilevanza strategica (Alta, Media). Filtra via tutto ciò che è inferiore a "Media".
4.  **Raggruppamento:** Raggruppa le entità che condividono Categoria e Rilevanza sulla stessa riga, separate da virgola.
5.  **Formattazione:** Genera ESCLUSIVAMENTE la tabella Markdown.
### TABELLA DELLE ENTITÀ
| Categoria | Entità | Rilevanza Strategica |
| :--- | :--- | :--- |
"""

def get_topic_clusters_prompt(keyword: str, entities_md: str, headings_str: str, paa_str: str) -> str:
    """ **NUOVO PROMPT** per il Topical Modeling."""
    return f"""
## PROMPT: Topic Modeling & Information Architecture ##
**PERSONA:** Agisci come un **Information Architect e Semantic SEO Strategist**. Il tuo compito è decostruire un argomento complesso nei suoi pilastri concettuali fondamentali. Non pensi in termini di singole keyword, ma di **cluster di intenti e argomenti**.
**CONTESTO:** Sto pianificando la creazione di un contenuto definitivo per la query `{keyword}`. Ho già estratto le entità principali menzionate dai competitor, i loro headings (H2, H3, etc.) e le domande "People Also Ask" (PAA) dalla SERP. Ora devo organizzare questa massa di informazioni in una struttura logica.
### DATI DI INPUT ###
**1. ENTITÀ RILEVANTI (estratte dai competitor):**
{entities_md}
**2. HEADINGS STRUTTURALI (H2, H3 dai competitor):**
{headings_str}
**3. DOMANDE DEGLI UTENTI (People Also Ask):**
{paa_str}
---
**COMPITO E FORMATO DI OUTPUT:**
1.  **Analisi e Sintesi:** Analizza TUTTI i dati di input per identificare i sotto-argomenti principali, i temi ricorrenti e i concetti fondamentali.
2.  **Clustering:** Raggruppa entità, headings e domande correlate in **5-7 cluster tematici**. Ogni cluster deve rappresentare una macro-area dell'argomento principale.
3.  **Formattazione:** Genera **ESCLUSIVAMENTE** una tabella Markdown con la seguente struttura. Non aggiungere introduzioni o commenti.
| Topic Cluster (Sotto-argomento Principale) | Concetti, Entità e Domande Chiave del Cluster |
| :--- | :--- |
"""

def get_content_brief_prompt(**kwargs) -> str:
    """ **NUOVO PROMPT** per generare il Content Brief finale."""
    return f"""
## PROMPT: Generatore di Content Brief SEO Strategico ##
**PERSONA:** Agisci come un **Head of Content** con profonde competenze SEO e NLU. Il tuo lavoro è tradurre analisi complesse in un brief attuabile per un copywriter, garantendo che il contenuto finale sia completo, autorevole e ottimizzato per dominare la SERP.
**CONTESTO:** Sulla base di un'analisi approfondita della SERP per la query `{kwargs.get('keyword', '')}`, ho raccolto tutti i dati necessari. Ora devi sintetizzarli in un piano di contenuto dettagliato.
### DATI DI INPUT SINTETIZZATI ###
**1. Analisi Strategica:**
{kwargs.get('strat_analysis_str', '')}
**2. Architettura del Topic (Topic Clusters):**
{kwargs.get('topic_clusters_md', '')}
**3. Keyword Secondarie e Correlate (Opzionale, da integrare):**
{kwargs.get('ranked_keywords_md', '')}
**4. Domande degli Utenti (PAA):**
{kwargs.get('paa_str', '')}
---
**COMPITO E FORMATO DI OUTPUT:**
Genera un content brief completo **ESCLUSIVAMENTE in formato Markdown**. Sii prescrittivo e chiaro.
1.  **Titolo e Meta Description:** Suggerisci 2-3 opzioni per il tag `<title>` (60 caratteri max) e 1 opzione per la `meta description` (155 caratteri max).
2.  **Struttura del Contenuto (Outline):** Crea una struttura gerarchica dettagliata usando H1, H2, H3.
    * L'H1 deve contenere la keyword principale.
    * Gli H2 devono basarsi sui **Topic Cluster** che ti ho fornito.
    * Sotto ogni H2, inserisci come punti elenco (`*`) i "Concetti, Entità e Domande" da trattare in quella sezione. Integra qui le keyword secondarie e le domande PAA pertinenti.
3.  **Entità "Must-Have":** Elenca le 5-7 entità più importanti (prese dai cluster) che devono assolutamente essere menzionate nel testo.
4.  **Sezione FAQ:** Proponi una sezione `## FAQ` alla fine, con le domande PAA più importanti formattate come H3.
Inizia direttamente con `## ✍️ Content Brief: {kwargs.get('keyword', '')}`. Non aggiungere altro testo introduttivo.
"""


# --- 4. INTERFACCIA UTENTE E FLUSSO PRINCIPALE ---

st.set_page_config(layout="wide", page_title="Advanced SEO Content Engine")

st.title("🚀 Advanced SEO Content Engine")
st.markdown("Da SERP a Content Brief: un flusso di lavoro potenziato da AI per creare contenuti dominanti.")

# CSS per personalizzazioni
st.markdown("""
<style>
    .reportview-container { background: #f0f2f6; }
    .stButton>button { border-radius: 20px; border: 1px solid #1E88E5; background-color: #1E88E5; color: white; }
    .stButton>button:hover { border: 1px solid #1565C0; background-color: #1565C0; color: white; }
    .ql-editor { min-height: 250px; }
    .block-container { padding-top: 2rem; }
    h1, h2, h3 { color: #1E88E5; }
    h3 { border-bottom: 2px solid #90CAF9; padding-bottom: 5px; margin-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# Gestione dello stato
if 'analysis_started' not in st.session_state:
    st.session_state.analysis_started = False

def start_analysis():
    if not all([st.session_state.query, st.session_state.country, st.session_state.language]):
        st.warning("Per favore, compila tutti i campi: Query, Country e Lingua.")
        return
    # Reset di tutti i dati precedenti eccetto i campi di input
    for key in list(st.session_state.keys()):
        if key not in ['query', 'country', 'language', 'analysis_started']:
            del st.session_state[key]
    st.session_state.analysis_started = True

def new_analysis():
    st.session_state.analysis_started = False
    for key in list(st.session_state.keys()):
        if key not in ['query', 'country', 'language']:
            st.session_state[key] = '' if isinstance(st.session_state[key], str) else None


# --- Input Form ---
with st.container():
    c1, c2, c3, c4 = st.columns([2.5, 1.5, 1.5, 1.5])
    with c1:
        st.text_input("🎯 Inserisci la tua Keyword target", key="query")
    with c2:
        st.selectbox("🌍 Seleziona il Paese", options=[""] + get_countries(), key="country")
    with c3:
        st.selectbox("🗣️ Seleziona la Lingua", options=[""] + get_languages(), key="language")
    with c4:
        st.markdown('<div style="height: 28px;"></div>', unsafe_allow_html=True)
        if st.session_state.analysis_started:
            st.button("🔄 Nuova Analisi", on_click=new_analysis, use_container_width=True)
        else:
            st.button("⚡ Avvia Analisi", on_click=start_analysis, type="primary", use_container_width=True)

st.divider()

# --- Flusso di Analisi Principale ---
if st.session_state.analysis_started:
    query, country, language = st.session_state.query, st.session_state.country, st.session_state.language

    # --- FASE 1: ESTRAZIONE DATI SERP E CONTENUTI ---
    if 'serp_result' not in st.session_state:
        with st.spinner("Fase 1/5: Analizzo la SERP, estraggo AI Overviews e contenuti dei competitor..."):
            st.session_state.serp_result = fetch_serp_data(query, country, language)
            if not st.session_state.serp_result:
                st.error("Analisi interrotta: impossibile ottenere i dati dalla SERP.")
                st.stop()

            items = st.session_state.serp_result.get('items', [])
            st.session_state.organic_results = [item for item in items if item.get("type") == "organic"][:10]
            
            # NUOVO: Estrazione AI Overview
            ai_overview = next((item for item in items if item.get("type") == "generative_answers"), None)
            st.session_state.ai_overview_text = ai_overview.get("answer") if ai_overview else None
            st.session_state.ai_overview_sources = [src.get('url') for src in ai_overview.get("links", [])] if ai_overview else []

            # NUOVO: Estrazione landscape SERP
            st.session_state.serp_feature_counts = Counter(item.get("type") for item in items)

            # Estrazione contenuti
            urls_to_parse = [r.get("url") for r in st.session_state.organic_results if r.get("url")]
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_url = {executor.submit(parse_url_content, url): url for url in urls_to_parse}
                results = {}
                for future in as_completed(future_to_url):
                    results[future_to_url[future]] = future.result()
            
            # st.session_state.parsed_contents contiene dict {"html_content": ..., "headings": ...}
            st.session_state.parsed_contents = [results.get(url, {"html_content": "", "headings": []}) for url in urls_to_parse]
            st.session_state.edited_html_contents = [res['html_content'] for res in st.session_state.parsed_contents]

    # --- FASE 2: ESTRAZIONE KEYWORD RANKING ---
    if 'ranked_keywords_results' not in st.session_state:
        with st.spinner("Fase 2/5: Scopro le keyword per cui si posizionano i competitor..."):
            ranked_keywords_api_results = []
            urls_for_ranking = [clean_url(res.get("url")) for res in st.session_state.organic_results if res.get("url")]
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_url = {executor.submit(fetch_ranked_keywords, url, country, language): url for url in urls_for_ranking}
                for future in as_completed(future_to_url):
                    ranked_keywords_api_results.append(future.result())
            st.session_state.ranked_keywords_results = ranked_keywords_api_results
    
    # Prepara dati per NLU
    initial_cleaned_texts = [BeautifulSoup(html, "html.parser").get_text(separator="\n", strip=True) for html in st.session_state.edited_html_contents]
    initial_joined_texts = "\n\n--- SEPARATORE TESTO ---\n\n".join(filter(None, initial_cleaned_texts))

    if not initial_joined_texts.strip():
        st.error("Impossibile recuperare contenuto testuale significativo dai competitor. L'analisi non può continuare.")
        st.stop()

    # --- FASE 3: ANALISI NLU STRATEGICA E DI ENTITÀ ---
    if 'nlu_strat_text' not in st.session_state:
        with st.spinner("Fase 3/5: L'AI sta definendo l'intento, il target e le entità chiave..."):
            with ThreadPoolExecutor() as executor:
                future_strat = executor.submit(run_nlu, get_strategica_prompt(query, initial_joined_texts))
                future_comp = executor.submit(run_nlu, get_competitiva_prompt(query, initial_joined_texts))
                st.session_state.nlu_strat_text = future_strat.result()
                st.session_state.nlu_comp_text = future_comp.result()

    # --- UI: VISUALIZZAZIONE ANALISI INIZIALI ---
    st.header("1. Analisi Strategica della SERP")

    # Visualizzazione analisi strategica (intent, audience...)
    nlu_strat_text = st.session_state.nlu_strat_text
    dfs_strat = parse_markdown_tables(nlu_strat_text)
    if dfs_strat:
        df_strat = dfs_strat[0]
        analysis_map = pd.Series(df_strat['Analisi Sintetica'].values, index=df_strat['Caratteristica SEO'].str.replace(r'\*\*', '', regex=True)).to_dict()
        cols = st.columns(len(analysis_map))
        for col, (label, value) in zip(cols, analysis_map.items()):
             col.metric(label, value.replace('`', ''))
    
    # NUOVO: UI per SERP Landscape e AI Overview
    st.subheader("Paesaggio della SERP e AI Overviews")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.write("**Feature Rilevate in SERP:**")
        df_features = pd.DataFrame(st.session_state.serp_feature_counts.items(), columns=['Feature', 'Conteggio']).sort_values('Conteggio', ascending=False)
        st.dataframe(df_features, hide_index=True)
    with col2:
        st.write("**Analisi AI Overview (Risposta Generativa)**")
        if st.session_state.ai_overview_text:
            st.info(st.session_state.ai_overview_text)
            st.write("**Fonti Citate nell'AI Overview:**")
            if st.session_state.ai_overview_sources:
                for source_url in st.session_state.ai_overview_sources:
                    # Controlla se una delle nostre URL organiche è una fonte
                    if any(clean_url(org_url['url']) == clean_url(source_url) for org_url in st.session_state.organic_results):
                        st.success(f"✅ {urlparse(source_url).netloc} (Presente nei Top 10)")
                    else:
                        st.warning(f"⚠️ {urlparse(source_url).netloc} (Esterno ai Top 10)")
            else:
                st.write("_Nessuna fonte esplicitamente citata._")
        else:
            st.write("_Nessuna AI Overview rilevata per questa query._")


    st.header("2. Analisi dei Competitor")
    # Estrazione PAA e Correlate per uso futuro
    items = st.session_state.serp_result.get('items', [])
    paa_list = list(dict.fromkeys(q.get("title", "") for item in items if item.get("type") == "people_also_ask" for q in item.get("items", []) if q.get("title")))
    related_list = list(dict.fromkeys(s.get("query", "") for item in items if item.get("type") in ("related_searches", "related_search") for s in item.get("items", []) if s.get("query")))

    # Editor Entità
    st.subheader("Entità Rilevanti (Common Ground dei Competitor)")
    dfs_comp = parse_markdown_tables(st.session_state.nlu_comp_text)
    df_entities = dfs_comp[0] if dfs_comp else pd.DataFrame(columns=['Categoria', 'Entità', 'Rilevanza Strategica'])
    
    st.info("ℹ️ Puoi modificare o eliminare le entità in questa tabella. Le tue modifiche guideranno la fase successiva di analisi dei Topic.")
    if 'edited_df_entities' not in st.session_state:
        st.session_state.edited_df_entities = df_entities
    
    st.session_state.edited_df_entities = st.data_editor(
        st.session_state.edited_df_entities, use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_entities"
    )

    # --- FASE 4: TOPICAL MODELING ---
    if 'df_topic_clusters' not in st.session_state:
         with st.spinner("Fase 4/5: Raggruppo le entità in Topic Cluster semantici..."):
            all_headings = [h for res in st.session_state.parsed_contents for h in res['headings']]
            headings_str = "\n".join(list(dict.fromkeys(all_headings))[:30]) # Limita per contesto
            paa_str = "\n".join(paa_list)
            entities_md = st.session_state.edited_df_entities.to_markdown(index=False)
            
            topic_prompt = get_topic_clusters_prompt(query, entities_md, headings_str, paa_str)
            nlu_topic_text = run_nlu(topic_prompt)
            
            dfs_topics = parse_markdown_tables(nlu_topic_text)
            st.session_state.df_topic_clusters = dfs_topics[0] if dfs_topics else pd.DataFrame(columns=['Topic Cluster (Sotto-argomento Principale)', 'Concetti, Entità e Domande Chiave del Cluster'])

    # UI per Topical Modeling
    st.header("3. Architettura del Topic (Topic Modeling)")
    st.info("ℹ️ Questa è la mappa concettuale del tuo contenuto. Gli H2 del tuo articolo dovrebbero basarsi su questi cluster. Puoi modificare i nomi dei cluster prima di generare il brief.")

    if 'edited_df_topic_clusters' not in st.session_state:
        st.session_state.edited_df_topic_clusters = st.session_state.df_topic_clusters

    st.session_state.edited_df_topic_clusters = st.data_editor(
        st.session_state.edited_df_topic_clusters, use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_topics"
    )

    # --- FASE 5: GENERAZIONE CONTENT BRIEF ---
    st.header("4. Content Brief Strategico Finale")
    
    if st.button("✍️ Genera Brief Dettagliato", type="primary", use_container_width=True):
        with st.spinner("Fase 5/5: Sto scrivendo il brief per il tuo copywriter..."):
            # Raccogli tutti i dati necessari per il prompt finale
            strat_analysis_str = dfs_strat[0].to_markdown(index=False) if dfs_strat else "N/D"
            topic_clusters_md = st.session_state.edited_df_topic_clusters.to_markdown(index=False)

            # Prepara una tabella opzionale di keyword ad alto volume
            ranked_keywords_df = pd.DataFrame() # Inizializza vuoto
            all_keywords_data = [item for result in st.session_state.ranked_keywords_results if result['status'] == 'ok' for item in result['items']]
            if all_keywords_data:
                kw_list = [{"Keyword": item.get("keyword_data", {}).get("keyword"), "Volume": item.get("keyword_data", {}).get("search_volume")} for item in all_keywords_data]
                ranked_keywords_df = pd.DataFrame(kw_list).dropna().drop_duplicates().sort_values("Volume", ascending=False).head(15)

            ranked_keywords_md = ranked_keywords_df.to_markdown(index=False) if not ranked_keywords_df.empty else "Nessun dato sulle keyword."
            paa_str = "\n".join(f"- {q}" for q in paa_list)

            brief_prompt_args = {
                "keyword": query,
                "strat_analysis_str": strat_analysis_str,
                "topic_clusters_md": topic_clusters_md,
                "ranked_keywords_md": ranked_keywords_md,
                "paa_str": paa_str,
            }

            final_brief = run_nlu(get_content_brief_prompt(**brief_prompt_args))
            st.session_state.final_brief = final_brief
    
    if 'final_brief' in st.session_state:
        st.markdown(st.session_state.final_brief)
    
    # --- SEZIONI ESPANDIBILI PER DATI DI DETTAGLIO ---
    st.markdown("---")
    st.header("Appendice: Dati di Dettaglio")

    with st.expander("Visualizza/Modifica Contenuti Estratti dai Competitor"):
        nav_labels = [f"{i+1}. {urlparse(res.get('url', '')).netloc.replace('www.', '')}" for i, res in enumerate(st.session_state.organic_results)]
        selected_index = st.selectbox("Seleziona un competitor:", options=range(len(nav_labels)), format_func=lambda i: nav_labels[i])
        
        st.markdown(f"**URL:** `{st.session_state.organic_results[selected_index].get('url', '')}`")
        edited_content = st_quill(value=st.session_state.edited_html_contents[selected_index], html=True, key=f"quill_{selected_index}")
        if edited_content != st.session_state.edited_html_contents[selected_index]:
            st.session_state.edited_html_contents[selected_index] = edited_content
            # Potresti aggiungere un pulsante per ri-analizzare con i contenuti modificati
            st.warning("Contenuto modificato. Per un'analisi aggiornata, avvia una nuova analisi.")

    with st.expander("Visualizza Keyword Ranking dei Competitor e Matrice di Copertura"):
         # Codice per la visualizzazione delle keyword (invariato dall'originale, ma ora è in un expander)
        all_keywords_data = []
        for result in st.session_state.ranked_keywords_results:
            if result['status'] == 'ok' and result['items']:
                competitor_domain = urlparse(result['url']).netloc.removeprefix('www.')
                for item in result['items']:
                    kd = item.get("keyword_data", {})
                    se = item.get("ranked_serp_element", {})
                    if kd.get("keyword") and kd.get("search_volume") is not None:
                        all_keywords_data.append({
                            "Competitor": competitor_domain,
                            "Keyword": kd.get("keyword"),
                            "Posizione": se.get("rank_absolute"),
                            "Volume": kd.get("search_volume")
                        })
        
        if all_keywords_data:
            df_ranked = pd.DataFrame(all_keywords_data).dropna().sort_values("Volume", ascending=False)
            st.write("**Tabella aggregata delle keyword:**")
            st.dataframe(df_ranked, use_container_width=True, height=300)

            st.write("**Matrice di Copertura (Posizione per Keyword):**")
            try:
                pivot_df = df_ranked.pivot_table(index='Keyword', columns='Competitor', values='Posizione').fillna('-')
                # Aggiungi colonna Volume per ordinamento
                volume_map = df_ranked.set_index('Keyword')['Volume'].drop_duplicates()
                pivot_df['Volume'] = pivot_df.index.map(volume_map)
                pivot_df = pivot_df.sort_values('Volume', ascending=False).drop(columns='Volume')
                st.dataframe(pivot_df, use_container_width=True, height=300)
            except Exception as e:
                st.warning(f"Impossibile creare la matrice di copertura: {e}")
        else:
            st.write("_Nessuna keyword posizionata trovata per i competitor._")
