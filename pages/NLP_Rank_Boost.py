import os
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlunparse

import pandas as pd
import requests
import streamlit as st
from google import genai
# Importazione per gli editor di testo
from streamlit_quill import st_quill
# Importazione per ripulire l'output HTML dell'editor
from bs4 import BeautifulSoup


# --- 1. CONFIGURAZIONE E COSTANTI ---

# Configura la libreria Gemini (metodo aggiornato)
try:
    GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
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
GEMINI_MODEL = "gemini-1.5-pro-latest"


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

@st.cache_data(ttl=3600, show_spinner=False)
def parse_url_content(url: str) -> str:
    """
    Estrae il 'main_topic' e lo restituisce come una stringa HTML pulita.
    Restituisce una stringa vuota in caso di PDF o errori di parsing noti.
    """
    if url.lower().endswith('.pdf'):
        return ""

    post_data = [{"url": url, "enable_javascript": True, "enable_xhr": True, "disable_cookie_popup": True}]
    try:
        response = session.post("https://api.dataforseo.com/v3/on_page/content_parsing/live", json=post_data)
        response.raise_for_status()
        data = response.json()

        if data.get("tasks_error", 0) > 0 or not data.get("tasks") or not data["tasks"][0].get("result"):
            error_message = data.get("tasks", [{}])[0].get("status_message", "Nessun risultato nell'API.")
            if 'pdf' in error_message.lower() or 'content type' in error_message.lower():
                return ""
            return f"<h2>Errore API</h2><p>{error_message}</p>"

        result_list = data["tasks"][0].get("result")
        if not result_list:
            return ""

        items_list = result_list[0].get("items")
        if not items_list:
            return ""

        items = items_list[0]
        
        page_content = items.get("page_content")

        if page_content:
            main_topic_data = page_content.get('main_topic')
            if not isinstance(main_topic_data, list):
                return ""

            html_parts = []
            for section in main_topic_data:
                h_title = section.get('h_title')
                if h_title:
                    level = section.get('level', 2)
                    html_parts.append(f"<h{level}>{h_title}</h{level}>")

                primary_content_list = section.get('primary_content')
                if isinstance(primary_content_list, list) and primary_content_list:
                    first_item_text = primary_content_list[0].get("text", "").strip()
                    is_a_list = first_item_text.startswith(("- ", "* "))

                    if is_a_list:
                        html_parts.append("<ul>")
                        for item in primary_content_list:
                            text = item.get("text", "").strip()
                            if text:
                                cleaned_text = text.lstrip("-* ").strip()
                                html_parts.append(f"<li>{cleaned_text}</li>")
                        html_parts.append("</ul>")
                    else:
                        for item in primary_content_list:
                            text = item.get('text')
                            if text:
                                html_parts.append(f"<p>{text.strip()}</p>")
            
            return "".join(html_parts)
        else:
            return ""
            
    except requests.RequestException as e:
        return f"<h2>Errore di Rete</h2><p>Durante l'analisi dell'URL {url}: {str(e)}</p>"
    except Exception as e:
        return f"<h2>Errore Imprevisto</h2><p>URL: {url}<br>Errore: {str(e)}</p>"

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
        safe_items = api_items if api_items is not None else []
        return {"url": url, "status": "ok", "items": safe_items}
    except requests.RequestException as e:
        return {"url": url, "status": "failed", "error": str(e), "items": []}

# --- FUNZIONE RUN_NLU AGGIORNATA ---
def run_nlu(prompt: str, model_name: str = GEMINI_MODEL) -> str:
    """Esegue una singola chiamata al modello Gemini usando il pattern GenerativeModel."""
    try:
        generation_config = None
        # Se il prompt richiede un output JSON, configuriamo il modello di conseguenza
        if "JSON_OUTPUT" in prompt or "Restituisci ESATTAMENTE e SOLO un oggetto JSON" in prompt:
            generation_config = genai.types.GenerationConfig(response_mime_type="application/json")

        model = genai.GenerativeModel(model_name, generation_config=generation_config)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.warning(f"Errore durante la chiamata a Gemini: {str(e)}")
        return "" # Restituisce una stringa vuota per causare un fallimento controllato

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

def get_position_from_item(item: dict) -> int | None:
    """
    Cerca di estrarre la posizione assoluta da un item della risposta API,
    provando diversi percorsi noti per massima compatibilità.
    """
    if not isinstance(item, dict):
        return None

    # Percorso 1: `serp_info` (come da documentazione principale)
    serp_info = item.get("serp_info")
    if isinstance(serp_info, dict):
        serp_item = serp_info.get("serp_item")
        if isinstance(serp_item, dict):
            position = serp_item.get("rank_absolute")
            if position is not None:
                return position

    # Percorso 2: `ranked_serp_element` (struttura alternativa comune)
    ranked_serp_element = item.get("ranked_serp_element")
    if isinstance(ranked_serp_element, dict):
        serp_item = ranked_serp_element.get("serp_item")
        if isinstance(serp_item, dict):
            position = serp_item.get("rank_absolute")
            if position is not None:
                return position

    return None

def filter_unbranded_keywords_with_gemini(keywords: list[str], domain: str) -> list[str]:
    """
    Usa Gemini per analizzare una lista di keyword e restituire solo quelle non-brand.
    """
    if not keywords:
        return []

    base_name = domain.removeprefix("www.").rsplit('.', 1)[0].replace('-', ' ').title()

    prompt = f"""
    **RUOLO**: Sei un esperto SEO specializzato in analisi della brand identity.
    **CONTESTO**: Sto analizzando le keyword per cui si posiziona il dominio '{domain}', il cui brand è verosimilmente '{base_name}'.
    **COMPITO**: Data la seguente lista di keyword in formato JSON, identifica quali sono puramente "unbranded" (generiche/informative) e quali sono "branded" (contengono il nome del brand, sue variazioni o acronimi noti).
    **FORMATO DI OUTPUT**: Restituisci ESATTAMENTE e SOLO un oggetto JSON con una singola chiave, "unbranded_keywords". Il valore di questa chiave deve essere una lista di stringhe contenente SOLO le keyword che hai identificato come unbranded. Non includere le keyword branded.

    **LISTA KEYWORD DA ANALIZZARE**:
    {json.dumps(keywords)}
    """
    
    try:
        response_text = run_nlu(prompt)
        if not response_text: # Gestisce il caso in cui run_nlu restituisce stringa vuota per errore
            raise json.JSONDecodeError("Risposta vuota da Gemini", "", 0)

        cleaned_response = re.sub(r'```json\n?|```', '', response_text).strip()
        data = json.loads(cleaned_response)
        unbranded = data.get("unbranded_keywords", [])
        
        if isinstance(unbranded, list):
            return unbranded
        else:
             st.warning(f"Gemini ha restituito un formato imprevisto per {domain}. Le keyword non saranno filtrate.")
             return keywords
    except (json.JSONDecodeError, AttributeError, KeyError) as e:
        st.warning(f"Impossibile analizzare le keyword con Gemini per il dominio {domain}. Errore: {e}. Le keyword non verranno filtrate per questo dominio.")
        return keywords


# --- 3. FUNZIONI PER LA COSTRUZIONE DEI PROMPT ---

def get_strategica_prompt(keyword: str, texts: str) -> str:
    """Costruisce il prompt per l'analisi strategica."""
    return f"""
## PROMPT: NLU Semantic Content Intelligence ##
**PERSONA:** Agisci come un **Lead SEO Strategist** con 15 anni di esperienza nel posizionare contenuti in settori altamente competitivi. Il tuo approccio è data-driven, ossessionato dall'intento di ricerca e focalizzato a identificare le debolezze dei competitor per creare contenuti dominanti. Pensa in termini di E-E-A-T, topic authority e user journey.
**CONTESTO:** Ho estratto il contenuto testuale completo delle pagine top-ranking su Google per la query strategica specificata di seguito. Il mio obiettivo non è solo eguagliare questi contenuti, ma surclassarli identificando le loro caratteristiche comuni.
**QUERY STRATEGICA:** {keyword}
### INIZIO TESTI DEI COMPETITOR DA ANALIZZARE ###
<TESTI>
{texts}
</TESTI>
---
**COMPITO E FORMATO DI OUTPUT:**
**Parte 1: Tabella Sintetica**
Analizza in modo aggregato tutti i testi forniti. Sintetizza le tue scoperte compilando la seguente tabella Markdown. Per ogni riga, la tua analisi deve rappresentare la tendenza predominante o la media osservata in TUTTI i testi. Genera **ESCLUSIVAMENTE** la tabella Markdown completa, iniziando dalla riga dell’header.
| Caratteristica SEO | Analisi Sintetica |
| :--- | :--- |
| **Search Intent Primario** | `[Determina e inserisci qui: Informazionale, Commerciale, Transazionale, Navigazionale. Aggiungi tra parentesi un brevissimo approfondimenti di massimo 5/6 parole]` |
| **Search Intent Secondario** | `[Determina e inserisci qui l'intento secondario. Aggiungi tra parentesi un brevissimo approfondimenti di massimo 5/6 parole]` |
| **Target Audience** | `[Definisci il target audience in massimo 6 parole]` |
| **Tone of Voice (ToV)** | `[Sintetizza il ToV predominante con 3 aggettivi chiave]` |
**Parte 2: Analisi Approfondita Audience**
Dopo la tabella, inserisci un separatore `---` seguito da un'analisi dettagliata del target audience. Inizia questa sezione con l'intestazione esatta: `### Analisi Approfondita Audience ###`.
Il testo deve essere un paragrafo di 3-4 frasi che descriva il pubblico in termini di livello di conoscenza, bisogni, possibili punti deboli (pain points) e cosa si aspetta di trovare nel contenuto. Questa analisi deve servire come guida per un copywriter.
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
2.  **Categorizzazione delle Entità:** Assegna una categoria semantica appropriata ad ogni entità estratta (es. Categoria Prodotto, Brand, Caratteristica Prodotto, Processo di Produzione, Località Geografica, ecc.).
3.  **Assegnazione Rilevanza Strategica:** Valuta e assegna un grado di rilevanza strategica ad ogni entità, utilizzando la seguente scala: Alta, Medio/Alta, Media.
4.  **Filtro Rilevanza:** Rimuovi tutte le entità che hanno una rilevanza strategica inferiore a "Media".
5.  **Raggruppamento Entità:** Le entità che condividono la stessa Categoria e lo stesso grado di Rilevanza Strategica devono essere raggruppate sulla stessa riga nella tabella. Ogni entità all'interno di un raggruppamento deve essere separata da una virgola (,).
6.  **Formattazione Output:** Genera ESCLUSIVAMENTE la tabella Markdown richiesta, attenendoti alla struttura esatta fornita di seguito. Non aggiungere alcuna introduzione, testo aggiuntivo o commenti.
### TABELLA DELLE ENTITÀ
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
* **Tabella 2: Ricerche Correlate dalla SERP:**
    {kwargs.get('related_table', '')}
* **Tabella 3: People Also Ask (PAA) dalla SERP:**
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
| Categoria Keyword | Keywords / Concetti / Domande |
| :--- | :--- |
| **Keyword Principale** | {kwargs.get('keyword', '').lower()} |
| **Keyword Secondarie** | _(elenca le keyword secondarie più importanti; non ripetere la keyword principale)_ |
| **Keyword Correlate e Varianti** | _(elenca varianti, sinonimi e concetti semanticamente correlati più strategici)_ |
| **Domande degli Utenti (FAQ)** | _(elenca le domande più rilevanti e ricercate, prima lettera maiuscola)_ |
"""


# --- 4. INTERFACCIA UTENTE E FLUSSO PRINCIPALE ---

st.title("Analisi SEO Competitiva Multi-Step")
st.markdown("Questo tool esegue analisi SEO integrando SERP scraping, estrazione di contenuti on-page e NLU.")

st.markdown("""
<style>
    .ql-editor {
        height: 300px !important;
        overflow-y: scroll !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
    #competitor-layout-wrapper [data-testid="stHorizontalBlock"] > div:nth-child(1) {
        background-color: rgb(247, 248, 249);
        border-radius: 8px;
        padding: 1rem;
    }
    #competitor-layout-wrapper [data-testid="stHorizontalBlock"] > div:nth-child(2) {
        padding: 1rem;
    }
</style>
""", unsafe_allow_html=True)

st.divider()

def start_analysis_callback():
    if not all([st.session_state.query, st.session_state.country, st.session_state.language]):
        st.error("Tutti i campi (Query, Country, Lingua) sono obbligatori.")
        return
    st.session_state.analysis_started = True

def new_analysis_callback():
    keys_to_preserve = ['query', 'country', 'language']
    keys_to_clear = [k for k in st.session_state.keys() if k not in keys_to_preserve]
    for key in keys_to_clear:
        del st.session_state[key]
    st.session_state.analysis_started = False
    st.rerun()

with st.container():
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1.2])
    with col1:
        query = st.text_input("Query", key="query")
    with col2:
        country = st.selectbox("Country", [""] + get_countries(), key="country")
    with col3:
        language = st.selectbox("Lingua", [""] + get_languages(), key="language")
    with col4:
        st.markdown('<div style="height: 28px;"></div>', unsafe_allow_html=True)
        if st.session_state.get('analysis_started', False):
            st.button("↩️ Nuova Analisi", on_click=new_analysis_callback, type="primary", use_container_width=True)
        else:
            st.button("🚀 Avvia Analisi", on_click=start_analysis_callback, type="primary", use_container_width=True)

if st.session_state.get('analysis_started', False):
    
    with st.spinner("Fase 1/4: Estrazione dati SERP e contenuti..."):
        if 'serp_result' not in st.session_state:
            st.session_state.serp_result = fetch_serp_data(st.session_state.query, st.session_state.country, st.session_state.language)
        
        if not st.session_state.serp_result:
            st.error("Analisi interrotta a causa di un errore nel recupero dei dati SERP.")
            st.stop()
            
        items = st.session_state.serp_result.get('items', [])
        organic_results = [item for item in items if item.get("type") == "organic"][:10]
        st.session_state.organic_results = organic_results

        if 'initial_html_contents' not in st.session_state:
            urls_to_parse = [r.get("url") for r in organic_results if r.get("url")]
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_url = {executor.submit(parse_url_content, url): url for url in urls_to_parse}
                results = {}
                for future in as_completed(future_to_url):
                    url = future_to_url[future]
                    results[url] = future.result()
            st.session_state.initial_html_contents = [results.get(url, "") for url in urls_to_parse]

        if 'edited_html_contents' not in st.session_state:
            st.session_state.edited_html_contents = list(st.session_state.initial_html_contents)

    with st.spinner("Fase 2/4: Estrazione e filtro keyword posizionate..."):
        if 'ranked_keywords_results' not in st.session_state:
            ranked_keywords_api_results = []
            urls_for_ranking = [clean_url(res.get("url")) for res in organic_results if res.get("url")]
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_url = {executor.submit(fetch_ranked_keywords, url, st.session_state.country, st.session_state.language): url for url in urls_for_ranking}
                for future in as_completed(future_to_url):
                    ranked_keywords_api_results.append(future.result())
            st.session_state.ranked_keywords_results = ranked_keywords_api_results

    initial_cleaned_texts = [BeautifulSoup(html, "html.parser").get_text(separator="\n", strip=True) for html in st.session_state.initial_html_contents]
    initial_joined_texts = "\n\n--- SEPARATORE TESTO ---\n\n".join(filter(None, initial_cleaned_texts))

    if not initial_joined_texts.strip():
        st.error("Impossibile recuperare il contenuto testuale da analizzare. L'analisi non può continuare.")
        st.stop()

    with st.spinner("Fase 3/4: Esecuzione analisi NLU strategica..."):
        if 'nlu_strat_text' not in st.session_state or 'nlu_comp_text' not in st.session_state:
            with ThreadPoolExecutor() as executor:
                future_strat = executor.submit(run_nlu, get_strategica_prompt(st.session_state.query, initial_joined_texts))
                future_comp = executor.submit(run_nlu, get_competitiva_prompt(st.session_state.query, initial_joined_texts))
                st.session_state.nlu_strat_text = future_strat.result()
                st.session_state.nlu_comp_text = future_comp.result()

    st.subheader("Analisi Strategica")
    nlu_strat_text = st.session_state.nlu_strat_text
    audience_detail_text = ""
    table_text = nlu_strat_text
    if "### Analisi Approfondita Audience ###" in nlu_strat_text:
        parts = nlu_strat_text.split("### Analisi Approfondita Audience ###")
        table_text = parts[0]
        audience_detail_text = parts[1].strip().removeprefix('---').strip()
    dfs_strat = parse_markdown_tables(table_text)
    if dfs_strat and not dfs_strat[0].empty:
        df_strat = dfs_strat[0]
        if 'Caratteristica SEO' in df_strat.columns and 'Analisi Sintetica' in df_strat.columns:
            df_strat['Caratteristica SEO'] = df_strat['Caratteristica SEO'].str.replace('*', '', regex=False).str.strip()
            analysis_map = pd.Series(df_strat['Analisi Sintetica'].values, index=df_strat['Caratteristica SEO']).to_dict()
            labels_to_display = ["Search Intent Primario", "Search Intent Secondario", "Target Audience", "Tone of Voice (ToV)"]
            cols = st.columns(len(labels_to_display))
            for col, label in zip(cols, labels_to_display):
                value = analysis_map.get(label, "N/D").replace('`', '')
                col.markdown(f"""<div style="padding: 0.75rem 1.5rem; border: 1px solid rgb(255 166 166); border-radius: 0.5rem; background-color: rgb(255, 246, 246); height: 100%;"><div style="font-size:0.8rem; color: rgb(255 70 70);">{label}</div><div style="font-size:1rem; color:#202124; font-weight:500;">{value}</div></div>""", unsafe_allow_html=True)
            if audience_detail_text:
                st.divider()
                st.markdown("<h6>Analisi Dettagliata Audience</h6>", unsafe_allow_html=True)
                st.write(audience_detail_text)
        else:
            st.dataframe(df_strat)
    else:
        st.text(nlu_strat_text)
    
    st.markdown("""<div style="border-top:1px solid #ECEDEE; margin: 1.5rem 0px 2rem 0rem; padding-top:1rem;"></div>""", unsafe_allow_html=True)
    
    col_org, col_paa = st.columns([2, 1], gap="large")
    with col_org:
        st.markdown('<h3 style="margin-top:0; padding-top:0;">Risultati Organici (Top 10)</h3>', unsafe_allow_html=True)
        if organic_results:
            html = '<div style="padding-right:3.5rem;">'
            for it in organic_results:
                url_raw, p = it.get("url", ""), urlparse(it.get("url", ""))
                base, segs = f"{p.scheme}://{p.netloc}", [s for s in p.path.split("/") if s]
                pretty = base + (" › " + " › ".join(segs) if segs else "")
                hn = p.netloc.split('.')
                name = (hn[1] if len(hn) > 2 else hn[0]).replace('-', ' ').title()
                title, desc = it.get("title", ""), it.get("description", "")
                html += (f'<div style="margin-bottom:2rem;"><div style="display:flex;align-items:center;margin-bottom:0.2rem;"><img src="https://www.google.com/s2/favicons?domain={p.netloc}&sz=64" onerror="this.src=\'https://www.google.com/favicon.ico\';" style="width:26px;height:26px;border-radius:50%;border:1px solid #d2d2d2;margin-right:0.5rem;"/><div><div style="color:#202124;font-size:16px;line-height:20px;">{name}</div><div style="color:#4d5156;font-size:14px;line-height:18px;">{pretty}</div></div></div><a href="{url_raw}" style="color:#1a0dab;text-decoration:none;font-size:23px;font-weight:500;">{title}</a><div style="font-size:16px;line-height:22px;color:#474747;">{desc}</div></div>')
            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.warning("⚠️ Nessun risultato organico trovato.")
            
    with col_paa:
        st.markdown('<h3 style="margin-top:0; padding-top:0;">People Also Ask</h3>', unsafe_allow_html=True)
        paa_list = list(dict.fromkeys(q.get("title", "") for item in items if item.get("type") == "people_also_ask" for q in item.get("items", []) if q.get("title")))
        if paa_list:
            pills = ''.join(f'<span style="background-color:#f7f8f9;padding:8px 12px;border-radius:4px;font-size:16px;margin-right:4px;margin-bottom:8px;display:inline-block;">{q}</span>' for q in paa_list)
            st.markdown(f"<div>{pills}</div>", unsafe_allow_html=True)
        else:
            st.write("_Nessuna PAA trovata_")
        st.markdown('<h3 style="margin-top:1.5rem;">Ricerche Correlate</h3>', unsafe_allow_html=True)
        related_raw = [s if isinstance(s, str) else s.get("query", "") for item in items if item.get("type") in ("related_searches", "related_search") for s in item.get("items", [])]
        related_list = list(dict.fromkeys(filter(None, related_raw)))
        if related_list:
            pills = ""
            pat = re.compile(st.session_state.query, re.IGNORECASE) if st.session_state.query else None
            for r in related_list:
                txt = r.strip()
                if pat and (m := pat.search(txt)):
                    pre, suf = txt[:m.end()], txt[m.end():]
                    formatted_txt = pre + (f"<strong>{suf}</strong>" if suf else "")
                else:
                    formatted_txt = txt
                pills += f'<span style="background-color:#f7f8f9;padding:8px 12px;border-radius:4px;font-size:16px;margin-right:4px;margin-bottom:8px;display:inline-block;">{formatted_txt}</span>'
            st.markdown(f"<div>{pills}</div>", unsafe_allow_html=True)
        else:
            st.write("_Nessuna ricerca correlata trovata_")
            
    st.divider()
    st.subheader("Contenuti dei Competitor Analizzati (Main Topic)")

    nav_labels = []
    for i, result in enumerate(organic_results):
        url = result.get('url', '')
        domain_clean = urlparse(url).netloc.removeprefix("www.") if url else "URL non disponibile"
        nav_labels.append(f"{i+1}. {domain_clean}")

    st.markdown('<div id="competitor-columns-marker"></div>', unsafe_allow_html=True)
    
    col_nav, col_content = st.columns([1.5, 5])

    with col_nav:
        st.markdown("<h6>Competitors</h6>", unsafe_allow_html=True)
        selected_index = st.radio(
            "Seleziona un competitor",
            options=range(len(nav_labels)),
            format_func=lambda i: nav_labels[i],
            key="competitor_selector",
            label_visibility="collapsed"
        )

    with col_content:
        selected_url_raw = organic_results[selected_index].get('url', '')
        cleaned_display_url = selected_url_raw.split('?')[0]
        st.markdown(f"**URL Selezionato:** `{cleaned_display_url}`")
        editor_key = f"quill_editor_{selected_index}"
        content_to_display = st.session_state.edited_html_contents[selected_index]
        edited_content = st_quill(
            value=content_to_display,
            html=True,
            key=editor_key
        )
        if edited_content != content_to_display:
            st.session_state.edited_html_contents[selected_index] = edited_content
            st.rerun()

    st.divider()

    st.subheader("Keyword Ranking dei Competitor (Filtrato per Brand)")
    ranked_keywords_results = st.session_state.get('ranked_keywords_results', [])
    
    with st.expander("Mostra report dettagliato dell'estrazione keyword"):
        if not ranked_keywords_results:
            st.write("Nessun tentativo di estrazione registrato.")
        for result in ranked_keywords_results:
            domain = urlparse(result['url']).netloc.removeprefix('www.')
            if result['status'] == 'ok':
                num_items = len(result.get('items', []))
                st.success(f"✅ {domain}: OK ({num_items} keyword trovate)")
            else:
                st.error(f"❌ {domain}: ERRORE ({result.get('error', 'Sconosciuto')})")

    all_keywords_data = []
    for result in ranked_keywords_results:
        if result['status'] == 'ok' and result.get('items'):
            competitor_domain = urlparse(result['url']).netloc
            
            all_competitor_keywords = [item.get("keyword_data", {}).get("keyword") for item in result['items'] if item.get("keyword_data", {}).get("keyword")]
            
            if not all_competitor_keywords:
                continue

            unbranded_keywords_list = filter_unbranded_keywords_with_gemini(all_competitor_keywords, competitor_domain)
            unbranded_keywords_set = set(unbranded_keywords_list)

            for item in result['items']:
                keyword_data = item.get("keyword_data", {})
                keyword = keyword_data.get("keyword")

                if keyword in unbranded_keywords_set:
                    keyword_info = keyword_data.get("keyword_info", {})
                    search_intent_info = keyword_data.get("search_intent_info", {})
                    
                    search_volume = keyword_info.get("search_volume") if keyword_info else None
                    main_intent = search_intent_info.get("main_intent", "N/D") if search_intent_info else "N/D"
                    
                    position = get_position_from_item(item)

                    all_keywords_data.append({
                        "Competitor": competitor_domain.removeprefix("www."),
                        "Keyword": keyword,
                        "Posizione": position,
                        "Volume di Ricerca": search_volume,
                        "Search Intent": main_intent.title() if main_intent else "N/D"
                    })
    
    if all_keywords_data:
        ranked_keywords_df = pd.DataFrame(all_keywords_data)
        
        ranked_keywords_df["Volume di Ricerca"] = ranked_keywords_df["Volume di Ricerca"].fillna(0)
        ranked_keywords_df["Posizione"] = ranked_keywords_df["Posizione"].fillna(0)
        
        ranked_keywords_df["Volume di Ricerca"] = ranked_keywords_df["Volume di Ricerca"].astype(int)
        ranked_keywords_df["Posizione"] = ranked_keywords_df["Posizione"].astype(int)
        
        ranked_keywords_df = ranked_keywords_df[ranked_keywords_df['Posizione'] > 0]

        if not ranked_keywords_df.empty:
            ranked_keywords_df = ranked_keywords_df.sort_values(by="Volume di Ricerca", ascending=False).reset_index(drop=True)

            st.info("Tabella completa con le keyword NON-BRAND posizionate dai competitor, ordinate per volume di ricerca.")
            st.dataframe(ranked_keywords_df, use_container_width=True, height=350)
            
            st.info("Matrice di copertura: mostra per ogni keyword NON-BRAND la posizione dei vari competitor.")
            
            try:
                keyword_info = ranked_keywords_df[['Keyword', 'Volume di Ricerca', 'Search Intent']].drop_duplicates(subset='Keyword').set_index('Keyword')
                pivot_df = ranked_keywords_df.pivot_table(
                    index='Keyword',
                    columns='Competitor',
                    values='Posizione'
                ).fillna('')
                
                coverage_matrix = keyword_info.join(pivot_df).sort_values(by='Volume di Ricerca', ascending=False)
                
                for col in coverage_matrix.columns:
                    if col not in ['Volume di Ricerca', 'Search Intent']:
                        coverage_matrix[col] = coverage_matrix[col].apply(lambda x: int(x) if x != '' else '')

                st.dataframe(coverage_matrix, use_container_width=True, height=350)

            except Exception as e:
                st.warning(f"Non è stato possibile creare la matrice di copertura: {e}")
        else:
            st.warning("Nessuna keyword non-brand con dati di ranking validi trovata dopo la pulizia.")

    else:
        st.warning("Nessuna keyword posizionata (o nessuna keyword non-brand) trovata per gli URL analizzati.")

    st.divider()
    
    final_edited_htmls = st.session_state.edited_html_contents

    cleaned_texts = [BeautifulSoup(html, "html.parser").get_text(separator="\n", strip=True) for html in final_edited_htmls]
    final_joined_texts = "\n\n--- SEPARATORE TESTO ---\n\n".join(filter(None, cleaned_texts))

    nlu_comp_text = st.session_state.nlu_comp_text
    dfs_comp = parse_markdown_tables(nlu_comp_text)
    df_entities = dfs_comp[0] if len(dfs_comp) > 0 else pd.DataFrame()
    
    st.subheader("Entità Rilevanti (Common Ground)")
    st.info("ℹ️ Puoi modificare o eliminare i valori direttamente in questa tabella. Le modifiche verranno usate per i passaggi successivi.")
    edited_df_entities = st.data_editor(
        df_entities,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key="editor_entities",
        column_config={ "Rilevanza Strategica": None }
    )
    def regenerate_keywords():
        if 'nlu_mining_text' in st.session_state:
            del st.session_state['nlu_mining_text']
    st.button("🔄 Rigenera Keyword dalle Entità Modificate", on_click=regenerate_keywords)
    
    with st.spinner("Fase 4/4: Esecuzione NLU per Keyword Mining..."):
        if 'nlu_mining_text' not in st.session_state:
            related_list = list(dict.fromkeys(filter(None, related_raw)))
            paa_list = list(dict.fromkeys(q.get("title", "") for item in items if item.get("type") == "people_also_ask" for q in item.get("items", []) if q.get("title")))
            prompt_mining_args = {
                "keyword": st.session_state.query, "country": st.session_state.country, "language": st.session_state.language, 
                "texts": final_joined_texts,
                "entities_table": edited_df_entities.to_markdown(index=False),
                "related_table": pd.DataFrame(related_list, columns=["Query Correlata"]).to_markdown(index=False),
                "paa_table": pd.DataFrame(paa_list, columns=["Domanda"]).to_markdown(index=False)
            }
            st.session_state.nlu_mining_text = run_nlu(get_mining_prompt(**prompt_mining_args))
    
    nlu_mining_text = st.session_state.nlu_mining_text
    dfs_mining = parse_markdown_tables(nlu_mining_text)
    df_mining = dfs_mining[0] if dfs_mining else pd.DataFrame()
    
    st.subheader("Semantic Keyword Mining")
    st.info("ℹ️ Puoi modificare o eliminare le keyword e le categorie prima di esportare i dati.")
    edited_df_mining = st.data_editor(df_mining, use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_mining")
