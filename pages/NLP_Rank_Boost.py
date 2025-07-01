import os
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlunparse
from collections import Counter

import pandas as pd
import requests
import streamlit as st
import google.generativeai as genai
from streamlit_quill import st_quill
from bs4 import BeautifulSoup

# --- 1. CONFIGURAZIONE E COSTANTI ---

# Configura il client Gemini
try:
    GEMINI_API_KEY = st.secrets.get("gemini", {}).get("api_key") or os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        st.error("GEMINI_API_KEY non trovata. Impostala nei Secrets di Streamlit o come variabile d'ambiente.")
        st.stop()
    
    genai.configure(api_key=GEMINI_API_KEY)
    
    gemini_client = genai.GenerativeModel("gemini-2.5-pro")
    
except AttributeError:
    st.error("Errore di configurazione di Gemini (AttributeError). Assicurati di avere l'ultima versione della libreria: 'pip install --upgrade google-generativeai'")
    st.stop()
except Exception as e:
    st.error(f"Errore generico nella configurazione di Gemini: {e}")
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


# --- 2. FUNZIONI DI UTILITY E API ---

@st.cache_data(show_spinner="Caricamento Nazioni (con codici)...")
def get_locations_data() -> pd.DataFrame:
    """Recupera e cachea la lista completa delle nazioni con i relativi codici."""
    try:
        resp = session.get('https://api.dataforseo.com/v3/serp/google/locations')
        resp.raise_for_status()
        locs = resp.json()['tasks'][0]['result']
        
        country_data = [
            {
                "name": loc.get("location_name"),
                "code": loc.get("location_code")
            }
            for loc in locs if loc.get('location_type') == 'Country' and loc.get("location_code")
        ]
        return pd.DataFrame(country_data).sort_values('name').reset_index(drop=True)
    except (requests.RequestException, KeyError, IndexError) as e:
        st.warning(f"Impossibile caricare le nazioni dall'API: {e}. Uso una lista di default.")
        default_data = [
            {'name': 'Italy', 'code': 2380}, {'name': 'United States', 'code': 2840},
            {'name': 'United Kingdom', 'code': 2826}, {'name': 'Germany', 'code': 2276},
            {'name': 'France', 'code': 2250}, {'name': 'Spain', 'code': 2724}
        ]
        return pd.DataFrame(default_data)

@st.cache_data(show_spinner="Caricamento Lingue (con codici)...")
def get_languages_data() -> pd.DataFrame:
    """Recupera e cachea la lista completa delle lingue con i relativi codici."""
    try:
        resp = session.get('https://api.dataforseo.com/v3/serp/google/languages')
        resp.raise_for_status()
        langs = resp.json()['tasks'][0]['result']
        lang_data = [
            {
                "name": lang.get("language_name"),
                "code": lang.get("language_code")
            }
            for lang in langs if lang.get("language_code")
        ]
        return pd.DataFrame(lang_data).sort_values('name').reset_index(drop=True)
    except (requests.RequestException, KeyError, IndexError) as e:
        st.warning(f"Impossibile caricare le lingue dall'API: {e}. Uso una lista di default.")
        default_data = [
            {'name': 'Italian', 'code': 'it'}, {'name': 'English', 'code': 'en'},
            {'name': 'German', 'code': 'de'}, {'name': 'French', 'code': 'fr'},
            {'name': 'Spanish', 'code': 'es'}
        ]
        return pd.DataFrame(default_data)

@st.cache_data(show_spinner=False, ttl=3600)
def fetch_main_image_url(url: str) -> str | None:
    """Tenta di estrarre l'immagine principale (og:image) da un URL."""
    if not url:
        return None
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, timeout=5, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            return og_image["content"]
        
        twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
        if twitter_image and twitter_image.get("content"):
            return twitter_image["content"]

    except requests.RequestException:
        return None
    return None

def clean_url(url: str) -> str:
    """Rimuove parametri e frammenti da un URL."""
    if not isinstance(url, str): return ""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query="", params="", fragment=""))

@st.cache_data(ttl=600, show_spinner="Analisi SERP in corso...")
def fetch_serp_data(query: str, location_code: int, language_code: str) -> dict | None:
    """Esegue la chiamata API a DataForSEO con la struttura del payload corretta e definitiva."""
    post_data = [{
        "keyword": query,
        "location_code": location_code,
        "language_code": language_code,
        "device": "desktop",
        "os": "windows",
        "depth": 10,
        "load_async_ai_overview": True,
        "people_also_ask_click_depth": 4
    }]
    try:
        response = session.post("https://api.dataforseo.com/v3/serp/google/organic/live/advanced", json=post_data)
        response.raise_for_status()
        data = response.json()
        
        if data.get("tasks_error", 0) > 0:
             st.error("DataForSEO ha restituito un errore nel task:")
             st.json(data["tasks"])
             return None

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
    """Estrae il 'main_topic' e gli headings da una pagina."""
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
                for item in primary_content_list:
                    text = item.get("text", "").strip()
                    if text:
                        html_parts.append(f"<p>{text}</p>")

        return {"html_content": "".join(html_parts), "headings": headings}
    except (requests.RequestException, KeyError, IndexError, TypeError):
        return default_return

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_ranked_keywords(url: str, location_name: str, language_name: str) -> dict:
    """Estrae le keyword posizionate."""
    payload = [{"target": url, "location_name": location_name, "language_name": language_name, "limit": 30}]
    try:
        response = session.post("https://api.dataforseo.com/v3/dataforseo_labs/google/ranked_keywords/live", json=payload)
        response.raise_for_status()
        data = response.json()
        if data.get("tasks_error", 0) > 0 or not data.get("tasks") or not data["tasks"][0].get("result"):
            error_message = data.get("tasks",[{}])[0].get("status_message", "N/A")
            return {"url": url, "status": "failed", "error": error_message, "items": []}
        
        api_items = data["tasks"][0]["result"][0].get("items")
        return {"url": url, "status": "ok", "items": api_items if api_items is not None else []}
    except requests.RequestException as e:
        return {"url": url, "status": "failed", "error": str(e), "items": []}

def run_nlu(prompt: str) -> str:
    """Esegue una singola chiamata al modello Gemini."""
    try:
        response = gemini_client.generate_content(prompt)
        if response.parts:
            return response.text
        return "Nessun contenuto generato. La risposta potrebbe essere stata bloccata per motivi di sicurezza."
    except Exception as e:
        st.error(f"Errore durante la chiamata a Gemini: {e}")
        return f"ERRORE NLU: {e}"

def parse_markdown_tables(text: str) -> list[pd.DataFrame]:
    """Estrae tabelle Markdown da un testo in modo robusto."""
    tables_md = re.findall(r"((?:\|.*\|[\r\n]+)+)", text)
    dataframes = []
    for table_md in tables_md:
        lines = [l.strip() for l in table_md.strip().splitlines() if l.strip()]
        if len(lines) < 2: continue
        
        header_line = lines[0]
        header = [h.strip() for h in header_line.split('|')[1:-1]]
        
        data_lines = []
        for line in lines[1:]:
            if all(cell.strip().startswith(':--') for cell in line.split('|')[1:-1]):
                continue
            data_lines.append(line)
        
        rows_data = []
        for row in data_lines:
            cells = [cell.strip() for cell in row.split('|')[1:-1]]
            if len(cells) == len(header):
                rows_data.append(cells)
        
        if rows_data:
            dataframes.append(pd.DataFrame(rows_data, columns=header))
    return dataframes

# --- 3. FUNZIONI PER LA COSTRUZIONE DEI PROMPT ---

def get_strategica_prompt(keyword: str, texts: str) -> str:
    """Costruisce il prompt per l'analisi strategica."""
    return f"""
## PROMPT: NLU Semantic Content Intelligence ##
**PERSONA:** Agisci come un **Lead SEO Strategist** con 15 anni di esperienza. Il tuo approccio è data-driven e focalizzato sull'intento di ricerca per creare contenuti dominanti.
**CONTESTO:** Ho estratto il contenuto testuale delle pagine top-ranking per la query.
**QUERY STRATEGICA:** {keyword}
### INIZIO TESTI DEI COMPETITOR DA ANALIZZARE ###
<TESTI>
{texts}
</TESTI>
---
**COMPITO E FORMATO DI OUTPUT:**
**Parte 1: Tabella Sintetica**
Analizza in modo aggregato i testi e compila la seguente tabella Markdown, rappresentando la tendenza predominante.
| Caratteristica SEO | Analisi Sintetica |
| :--- | :--- |
| **Search Intent Primario** | `[Determina: Informazionale, Commerciale, Transazionale, Navigazionale. Aggiungi breve approfondimento]` |
| **Search Intent Secondario** | `[Determina l'intento secondario, se presente. Aggiungi breve approfondimento]` |
| **Target Audience** | `[Definisci il target audience in massimo 10 parole]` |
| **Tone of Voice (ToV)** | `[Sintetizza il ToV predominante con 3 aggettivi chiave]` |
**Parte 2: Analisi Approfondita Audience**
Dopo la tabella, inserisci `---` seguito da un'analisi dell'audience con l'intestazione `### Analisi Approfondita Audience ###`. Descrivi il pubblico in termini di conoscenza, bisogni e pain points.
"""

def get_competitiva_prompt(keyword: str, texts: str) -> str:
    """Costruisce il prompt per l'analisi delle entità - VERSIONE RINFORZATA."""
    return f"""
**RUOLO**: Agisci come un sistema di Natural Language Processing (NLP) estremamente preciso. Il tuo unico scopo è estrarre entità e formattarle in una tabella Markdown. Non sei un assistente conversazionale.
**CONTESTO**: Analizzerò testi dei competitor per la keyword target per estrarre le entità semantiche più importanti.
**KEYWORD TARGET**: {keyword}

### INIZIO TESTI DA ANALIZZARE ###
<TESTI>
{texts}
</TESTI>
### FINE TESTI DA ANALIZZARE ###

**COMPITO FONDAMENTALE**:
1.  Estrai le entità nominate rilevanti dai testi.
2.  Assegna una categoria (es. Prodotto, Brand, Caratteristica, Località, Concetto Astratto).
3.  Assegna una rilevanza (Alta, Media). Ignora tutto ciò che ha rilevanza Bassa.
4.  Raggruppa le entità con la stessa Categoria e Rilevanza sulla stessa riga, separate da virgola.

**FORMATO DI OUTPUT OBBLIGATORIO**:
Genera **ESCLUSIVAMENTE** la tabella Markdown. Non includere **ASSOLUTAMENTE NESSUN** testo prima o dopo la tabella (niente introduzioni, niente spiegazioni, niente "Ecco la tabella:"). Il tuo output deve iniziare direttamente con la riga dell'header `| Categoria | Entità |...`.

| Categoria | Entità | Rilevanza Strategica |
| :--- | :--- | :--- |
"""

def get_topic_clusters_prompt(keyword: str, entities_md: str, headings_str: str, paa_str: str) -> str:
    """Costruisce il prompt per il Topical Modeling."""
    return f"""
## PROMPT: Topic Modeling & Information Architecture ##
**PERSONA:** Agisci come un **Information Architect e Semantic SEO Strategist**. Il tuo compito è decostruire un argomento complesso nei suoi pilastri concettuali.
**CONTESTO:** Sto pianificando un contenuto definitivo per la query `{keyword}`. Ho già estratto entità, headings e domande "People Also Ask" (PAA). Ora devo organizzarli in una struttura logica.
### DATI DI INPUT ###
**1. ENTITÀ RILEVANTI:**
{entities_md}
**2. HEADINGS STRUTTURALI:**
{headings_str}
**3. DOMANDE DEGLI UTENTI (PAA):**
{paa_str}
---
**COMPITO E FORMATO DI OUTPUT:**
1.  **Analisi e Sintesi:** Analizza TUTTI i dati per identificare i sotto-argomenti principali.
2.  **Clustering:** Raggruppa entità, headings e domande correlate in **5-7 cluster tematici**.
3.  **Formattazione:** Genera **ESCLUSIVAMENTE** una tabella Markdown. Non aggiungere introduzioni o commenti.
| Topic Cluster (Sotto-argomento Principale) | Concetti, Entità e Domande Chiave del Cluster |
| :--- | :--- |
"""

def get_content_brief_prompt(**kwargs) -> str:
    """Costruisce il prompt per generare il Content Brief finale."""
    return f"""
## PROMPT: Generatore di Content Brief SEO Strategico ##
**PERSONA:** Agisci come un **Head of Content** con profonde competenze SEO e NLU. Il tuo lavoro è tradurre analisi complesse in un brief attuabile per un copywriter.
**CONTESTO:** Sulla base di un'analisi approfondita della SERP per la query `{kwargs.get('keyword', '')}`, devi sintetizzare tutti i dati raccolti in un piano di contenuto dettagliato.
### DATI DI INPUT SINTETIZZATI ###
**1. Analisi Strategica:**
{kwargs.get('strat_analysis_str', '')}
**2. Architettura del Topic (Topic Clusters):**
{kwargs.get('topic_clusters_md', '')}
**3. Keyword Secondarie e Correlate (Opzionale):**
{kwargs.get('ranked_keywords_md', '')}
**4. Domande degli Utenti (PAA):**
{kwargs.get('paa_str', '')}
---
**COMPITO E FORMATO DI OUTPUT:**
Genera un content brief completo **ESCLUSIVAMENTE in formato Markdown**. Sii prescrittivo e chiaro.
1.  **Titolo e Meta Description:** Suggerisci 2 opzioni per `<title>` (60 caratteri max) e 1 opzione per `meta description` (155 caratteri max).
2.  **Struttura del Contenuto (Outline):** Crea una struttura gerarchica dettagliata (H1, H2, H3). L'H1 deve contenere la keyword. Gli H2 devono basarsi sui Topic Cluster. Sotto ogni H2, elenca i concetti e le domande da trattare.
3.  **Entità "Must-Have":** Elenca le 5-7 entità più importanti da includere.
4.  **Sezione FAQ:** Proponi una sezione `## FAQ` con le domande PAA più importanti come H3.
Inizia direttamente con `## ✍️ Content Brief: {kwargs.get('keyword', '')}`.
"""

# --- 4. INTERFACCIA UTENTE E FLUSSO PRINCIPALE ---

st.set_page_config(layout="wide", page_title="Advanced SEO Content Engine")

st.title("Analisi SEO Competitiva Multi-Step")
st.markdown("Questo tool esegue analisi SEO integrando SERP scraping, estrazione di contenuti on-page e NLU.")

st.markdown("""
<style>
    :root { 
        --m3c23: #8E87FF; /* Colore per il logo AIO */
        --m3c17: #dfe1e5; /* Colore per il bordo delle card AIO */
    }
    .stButton>button { border-radius: 4px; }
    .ql-editor { min-height: 250px; }
    h1 { font-size: 2.5rem; color: #333; }
    h2, h3 { color: #555; }
    .aio-header h2 {
        border: none;
        margin: 0;
        padding: 0;
        color: #333;
        font-size: 24px;
    }
    .show-more-button button {
        background-color: #d3e3fd;
        border-radius: 9999px;
        color: #001d35;
        border: 1px solid #c8dcfd;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

locations_df = get_locations_data()
languages_df = get_languages_data()

if 'analysis_started' not in st.session_state:
    st.session_state.analysis_started = False

def start_analysis():
    if not all([st.session_state.query, st.session_state.get('location_code'), st.session_state.get('language_code')]):
        st.warning("Tutti i campi (Query, Country, Lingua) sono obbligatori.")
        return
    # Pulisce lo stato per una nuova analisi, conservando solo gli input
    current_keys = ['query', 'location_code', 'language_code', 'location_name', 'language_name']
    for key in list(st.session_state.keys()):
        if key not in current_keys:
            del st.session_state[key]
    st.session_state.analysis_started = True
    st.rerun() 

def new_analysis():
    # Conserva solo gli input dell'utente, cancella tutto il resto
    current_keys = ['query', 'location_code', 'language_code', 'location_name', 'language_name']
    for key in list(st.session_state.keys()):
        if key not in current_keys:
            del st.session_state[key]
    st.session_state.analysis_started = False
    st.rerun()

with st.container():
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1.2])
    with col1:
        st.text_input("Query", key="query")
    with col2:
        loc_options = pd.concat([pd.DataFrame([{'name': '', 'code': None}]), locations_df], ignore_index=True)
        st.selectbox("Country", options=loc_options['name'], key="location_name")
        if st.session_state.location_name:
            st.session_state.location_code = int(loc_options[loc_options['name'] == st.session_state.location_name]['code'].iloc[0])
        else:
            st.session_state.location_code = None

    with col3:
        lang_options = pd.concat([pd.DataFrame([{'name': '', 'code': None}]), languages_df], ignore_index=True)
        st.selectbox("Lingua", options=lang_options['name'], key="language_name")
        if st.session_state.language_name:
            st.session_state.language_code = lang_options[lang_options['name'] == st.session_state.language_name]['code'].iloc[0]
        else:
            st.session_state.language_code = None

    with col4:
        st.markdown('<div style="height: 28px;"></div>', unsafe_allow_html=True)
        if st.session_state.get('analysis_started', False):
            st.button("↩️ Nuova Analisi", on_click=new_analysis, type="primary", use_container_width=True)
        else:
            st.button("🚀 Avvia Analisi", on_click=start_analysis, type="primary", use_container_width=True)

st.divider()

if st.session_state.get('analysis_started', False):
    query = st.session_state.query
    location_code = st.session_state.location_code
    language_code = st.session_state.language_code
    location_name = st.session_state.location_name
    language_name = st.session_state.language_name

    if 'serp_result' not in st.session_state:
        with st.spinner("Fase 1/5: Analizzo la SERP (attendo le AIO, può richiedere più tempo)..."):
            st.session_state.serp_result = fetch_serp_data(query, location_code, language_code)

    if not st.session_state.serp_result:
        st.error("Analisi interrotta: i dati della SERP non sono stati recuperati. Controllare i log sopra per l'errore API.")
        st.stop() 

    items = st.session_state.serp_result.get('items', [])
    organic_results = [item for item in items if item.get("type") == "organic"]
    
    AIO_TYPES = ["ai_overview", "generative_answers"]
    ai_overview = next((item for item in items if item.get("type") in AIO_TYPES), None)
    
    paa_items = next((item for item in items if item.get("type") == "people_also_ask"), {}).get("items", [])
    related_searches = next((item for item in items if item.get("type") == "related_searches"), {}).get("items", [])

    if 'parsed_contents' not in st.session_state:
        urls_to_parse = [r.get("url") for r in organic_results if r.get("url")]
        if urls_to_parse:
            with st.spinner(f"Fase 1.5/5: Estraggo i contenuti di {len(urls_to_parse)} pagine..."):
                with ThreadPoolExecutor(max_workers=5) as executor:
                    future_to_url = {executor.submit(parse_url_content, url): url for url in urls_to_parse}
                    results = {future_to_url[future]: future.result() for future in as_completed(future_to_url)}
                
                st.session_state.parsed_contents = [results.get(url, {"html_content": "", "headings": []}) for url in urls_to_parse]
                st.session_state.edited_html_contents = [res['html_content'] for res in st.session_state.parsed_contents]
        else:
            st.session_state.parsed_contents = []
            st.session_state.edited_html_contents = []

    if 'aio_source_images' not in st.session_state and ai_overview:
        aio_references = ai_overview.get("references", [])
        urls_to_fetch_images = [ref.get("url") for ref in aio_references if ref.get("url")]
        if urls_to_fetch_images:
            with st.spinner(f"Fase 1.6/5: Estraggo le immagini per {len(urls_to_fetch_images)} fonti AIO..."):
                 with ThreadPoolExecutor(max_workers=5) as executor:
                    future_to_url = {executor.submit(fetch_main_image_url, url): url for url in urls_to_fetch_images}
                    image_results = {future_to_url[future]: future.result() for future in as_completed(future_to_url)}
                    st.session_state.aio_source_images = image_results
    elif 'aio_source_images' not in st.session_state:
         st.session_state.aio_source_images = {}

    if 'ranked_keywords_results' not in st.session_state:
        urls_for_ranking = [clean_url(res.get("url")) for res in organic_results if res.get("url")]
        if urls_for_ranking:
            with st.spinner(f"Fase 2/5: Scopro le keyword di {len(urls_for_ranking)} competitor..."):
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(fetch_ranked_keywords, url, location_name, language_name) for url in urls_for_ranking]
                    st.session_state.ranked_keywords_results = [f.result() for f in as_completed(futures)]
        else:
            st.session_state.ranked_keywords_results = []
    
    if 'nlu_strat_text' not in st.session_state:
        initial_cleaned_texts = "\n\n--- SEPARATORE TESTO ---\n\n".join(
            filter(None, [BeautifulSoup(html, "html.parser").get_text(separator="\n", strip=True) for html in st.session_state.get('edited_html_contents', [])])
        )
        if not initial_cleaned_texts.strip():
            st.warning("Nessun contenuto testuale significativo recuperato dai competitor. L'analisi NLU sarà limitata.")
            st.session_state.nlu_strat_text = ""
            st.session_state.nlu_comp_text = ""
        else:
            with st.spinner("Fase 3/5: L'AI definisce l'intento e le entità..."):
                with ThreadPoolExecutor() as executor:
                    future_strat = executor.submit(run_nlu, get_strategica_prompt(query, initial_cleaned_texts))
                    future_comp = executor.submit(run_nlu, get_competitiva_prompt(query, initial_cleaned_texts))
                    st.session_state.nlu_strat_text = future_strat.result()
                    st.session_state.nlu_comp_text = future_comp.result()

    # --- INIZIO VISUALIZZAZIONE ---
    st.subheader("Analisi Strategica")
    nlu_strat_text = st.session_state.nlu_strat_text
    dfs_strat = parse_markdown_tables(nlu_strat_text.split("### Analisi Approfondita Audience ###")[0])
    if dfs_strat:
        df_strat = dfs_strat[0]
        if all(col in df_strat.columns for col in ['Caratteristica SEO', 'Analisi Sintetica']):
            analysis_map = pd.Series(df_strat['Analisi Sintetica'].values, index=df_strat['Caratteristica SEO'].str.replace(r'\*\*', '', regex=True)).to_dict()
            labels_to_display = ["Search Intent Primario", "Search Intent Secondario", "Target Audience", "Tone of Voice (ToV)"]
            cols = st.columns(len(labels_to_display))
            for col, label in zip(cols, labels_to_display):
                value = analysis_map.get(label, "N/D").replace('`', '')
                col.markdown(f"""<div style="padding: 0.75rem 1.5rem; border: 1px solid rgb(255 166 166); border-radius: 0.5rem; background-color: rgb(255, 246, 246); height: 100%;"><div style="font-size:0.8rem; color: rgb(255 70 70);">{label}</div><div style="font-size:1rem; color:#202124; font-weight:500;">{value}</div></div>""", unsafe_allow_html=True)
    
    st.divider()
    st.subheader("Rappresentazione Grafica della SERP")

    if ai_overview:
        with st.container(border=True):
            svg_logo = """<svg class="fWWlmf JzISke" height="24" width="24" aria-hidden="true" viewBox="0 0 471 471" xmlns="http://www.w3.org/2000/svg" style="vertical-align: middle;"><path fill="var(--m3c23)" d="M235.5 471C235.5 438.423 229.22 407.807 216.66 379.155C204.492 350.503 187.811 325.579 166.616 304.384C145.421 283.189 120.498 266.508 91.845 254.34C63.1925 241.78 32.5775 235.5 0 235.5C32.5775 235.5 63.1925 229.416 91.845 217.249C120.498 204.689 145.421 187.811 166.616 166.616C187.811 145.421 204.492 120.497 216.66 91.845C229.22 63.1925 235.5 32.5775 235.5 0C235.5 32.5775 241.584 63.1925 253.751 91.845C266.311 120.497 283.189 145.421 304.384 166.616C325.579 187.811 350.503 204.689 379.155 217.249C407.807 229.416 438.423 235.5 471 235.5C438.423 235.5 407.807 241.78 379.155 254.34C350.503 266.508 325.579 283.189 304.384 304.384C283.189 325.579 266.311 350.503 253.751 379.155C241.584 407.807 235.5 438.423 235.5 471Z"></path></svg>"""
            header_html = f'<div class="aio-header" style="display: flex; align-items: center; gap: 12px; margin-bottom: 1rem;">{svg_logo}<h2 style="margin: 0; border: none; font-size: 28px;">AI Overview</h2></div>'
            st.markdown(header_html, unsafe_allow_html=True)
            
            main_text_html = "<div style='font-size: 16px; line-height: 1.6;'>" + "<p>" + "</p><p>".join(item.get('text', '').replace('\n', '<br>') for item in ai_overview.get('items', []) if item.get('text')) + "</p></div>"
            st.markdown(main_text_html, unsafe_allow_html=True)
            
            all_references = ai_overview.get("references", [])
            if all_references:
                st.markdown("---")
                # Logica per "Mostra tutti / Mostra meno"
                if 'num_aio_sources_to_show' not in st.session_state:
                    st.session_state.num_aio_sources_to_show = 3

                def show_all_sources():
                    st.session_state.num_aio_sources_to_show = len(all_references)
                def show_fewer_sources():
                    st.session_state.num_aio_sources_to_show = 3

                references_to_show = all_references[:st.session_state.num_aio_sources_to_show]
                
                # Unico contenitore stilizzato per tutte le fonti
                sources_html_list = []
                for ref in references_to_show:
                    image_url = st.session_state.aio_source_images.get(ref.get("url"))
                    image_html = f'<div style="flex: 1; min-width: 120px;"><img src="{image_url}" style="width: 100%; border-radius: 8px;"></div>' if image_url else '<div style="flex: 1; min-width: 120px;"></div>'
                    
                    card_html = f"""
                    <div style="border-bottom: 1px solid #dadce0; padding-bottom: 16px; margin-bottom: 16px; display: flex; gap: 16px; align-items: flex-start;">
                        <div style="flex: 2.5; display: flex; flex-direction: column;">
                            <a href="{ref.get('url')}" target="_blank" style="text-decoration: none; color: inherit;">
                                <div style="font-weight: 500; color: #1f1f1f; margin-bottom: 8px; font-size: 16px;">{ref.get('title')}</div>
                                <div style="font-size: 14px; color: #4d5156;">{ref.get('text', '')[:120]}...</div>
                            </a>
                            <div style="font-size: 12px; color: #202124; display: flex; align-items: center; margin-top: 12px;">
                                <img src="https://www.google.com/s2/favicons?domain={ref.get('domain')}&sz=16" style="width:16px; height:16px; margin-right: 8px;">
                                <span>{ref.get('source', ref.get('domain'))}</span>
                            </div>
                        </div>
                        {image_html}
                    </div>
                    """
                    sources_html_list.append(card_html)
                
                # Renderizza il container principale con tutte le card
                st.markdown(f"""
                <div style="background-color: rgba(229, 237, 255, 0.5); border-radius: 16px; padding: 24px;">
                    {''.join(sources_html_list)}
                </div>
                """, unsafe_allow_html=True)

                # Logica per mostrare i pulsanti
                if len(all_references) > 3:
                    st.markdown('<div style="height: 1rem;"></div>', unsafe_allow_html=True) # Spazio
                    col_btn1, col_btn2 = st.columns(2)
                    if st.session_state.num_aio_sources_to_show < len(all_references):
                        with col_btn1:
                           st.button("Mostra tutti", on_click=show_all_sources, use_container_width=True)
                    else:
                        with col_btn1:
                           st.button("Mostra meno", on_click=show_fewer_sources, use_container_width=True)

        st.divider()

    left_col, right_col = st.columns([2, 1], gap="large")

    with left_col:
        st.markdown('<h3 style="margin-top:0; padding-top:0;">Risultati Organici</h3>', unsafe_allow_html=True)
        html_string = ""
        for res in organic_results:
            url_raw = res.get("url", "")
            if not url_raw: continue
            p = urlparse(url_raw)
            pretty_url = str(p.netloc + p.path).replace("www.","")
            name = res.get("breadcrumb", "").split("›")[0].strip() if res.get("breadcrumb") else p.netloc.replace('www.','')
            title = res.get("title", "")
            desc = res.get("description", "")
            html_string += f"""
            <div style="margin-bottom: 2rem;">
                <div style="display: flex; align-items: center; margin-bottom: 0.2rem;">
                    <img src="https://www.google.com/s2/favicons?domain={p.netloc}&sz=64" 
                         onerror="this.onerror=null;this.src='https://www.google.com/favicon.ico';" 
                         style="width: 26px; height: 26px; border-radius: 50%; border: 1px solid #d2d2d2; margin-right: 0.5rem;">
                    <div>
                        <div style="color: #202124; font-size: 16px; line-height: 20px;">{name}</div>
                        <div style="color: #4d5156; font-size: 14px; line-height: 18px;">{pretty_url}</div>
                    </div>
                </div>
                <a href="{url_raw}" target="_blank" style="color: #1a0dab; text-decoration: none; font-size: 23px; font-weight: 500;">
                    {title}
                </a>
                <div style="font-size: 16px; line-height: 22px; color: #474747;">
                    {desc}
                </div>
            </div>
            """
        st.markdown(html_string, unsafe_allow_html=True)

    with right_col:
        if paa_items:
            st.markdown('<h3 style="margin-top:0; padding-top:0;">People Also Ask</h3>', unsafe_allow_html=True)
            paa_pills = ''.join(f'<span style="background-color:#f7f8f9;padding:8px 12px;border-radius:4px;font-size:16px;margin-right:4px;margin-bottom:8px;display:inline-block;">{paa.get("title")}</span>' for paa in paa_items)
            st.markdown(f"<div>{paa_pills}</div>", unsafe_allow_html=True)
        
        if related_searches:
            st.markdown('<h3 style="margin-top:1.5rem;">Ricerche Correlate</h3>', unsafe_allow_html=True)
            related_pills = ''.join(f'<span style="background-color:#f7f8f9;padding:8px 12px;border-radius:4px;font-size:16px;margin-right:4px;margin-bottom:8px;display:inline-block;">{r}</span>' for r in related_searches)
            st.markdown(f"<div>{related_pills}</div>", unsafe_allow_html=True)

    st.divider()
    
    st.header("3. Contenuti dei Competitor")
    if organic_results:
        nav_labels = [f"{i+1}. {urlparse(res.get('url', '')).netloc.replace('www.', '')}" for i, res in enumerate(organic_results)]
        selected_index = st.radio("Seleziona un competitor da analizzare:", options=range(len(nav_labels)), format_func=lambda i: nav_labels[i], horizontal=True, label_visibility="collapsed")
        
        if selected_index < len(st.session_state.edited_html_contents):
            edited_content = st_quill(value=st.session_state.edited_html_contents[selected_index], html=True, key=f"quill_{selected_index}")
            if edited_content != st.session_state.edited_html_contents[selected_index]:
                st.session_state.edited_html_contents[selected_index] = edited_content
                st.rerun()
    else:
        st.write("Nessun contenuto da analizzare.")

    st.header("4. Analisi NLU Avanzata")
    
    st.subheader("Entità Rilevanti (Common Ground dei Competitor)")
    with st.expander("🔬 Clicca qui per vedere la risposta grezza dell'AI per le Entità"):
        st.text_area("Output NLU (Entità)", st.session_state.get('nlu_comp_text', 'N/A'), height=200)
    
    dfs_comp = parse_markdown_tables(st.session_state.nlu_comp_text)
    df_entities = dfs_comp[0] if dfs_comp else pd.DataFrame(columns=['Categoria', 'Entità', 'Rilevanza Strategica'])
    
    st.info("ℹ️ Puoi modificare le entità. Le tue modifiche guideranno la fase successiva.")
    if 'edited_df_entities' not in st.session_state:
        st.session_state.edited_df_entities = df_entities.copy()
    
    st.session_state.edited_df_entities = st.data_editor(st.session_state.edited_df_entities, use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_entities")

    if 'df_topic_clusters' not in st.session_state:
         with st.spinner("Fase 4/5: Raggruppo le entità in Topic Cluster semantici..."):
            all_headings = [h for res in st.session_state.parsed_contents for h in res['headings']]
            headings_str = "\n".join(list(dict.fromkeys(all_headings))[:30])
            paa_str = "\n".join([paa.get('title', '') for paa in paa_items])
            entities_md = st.session_state.edited_df_entities.to_markdown(index=False)
            
            topic_prompt = get_topic_clusters_prompt(query, entities_md, headings_str, paa_str)
            nlu_topic_text = run_nlu(topic_prompt)
            
            dfs_topics = parse_markdown_tables(nlu_topic_text)
            st.session_state.df_topic_clusters = dfs_topics[0] if dfs_topics else pd.DataFrame(columns=['Topic Cluster (Sotto-argomento Principale)', 'Concetti, Entità e Domande Chiave del Cluster'])

    st.subheader("Architettura del Topic (Topic Modeling)")
    st.info("ℹ️ Questa è la mappa concettuale. Gli H2 del tuo articolo dovrebbero basarsi su questi cluster.")

    if 'edited_df_topic_clusters' not in st.session_state:
        st.session_state.edited_df_topic_clusters = st.session_state.df_topic_clusters.copy()

    st.session_state.edited_df_topic_clusters = st.data_editor(st.session_state.edited_df_topic_clusters, use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_topics")

    st.header("5. Content Brief Strategico Finale")
    if st.button("✍️ Genera Brief Dettagliato", type="primary", use_container_width=True):
        with st.spinner("Fase 5/5: Sto scrivendo il brief per il tuo copywriter..."):
            strat_analysis_str = dfs_strat[0].to_markdown(index=False) if dfs_strat else "N/D"
            topic_clusters_md = st.session_state.edited_df_topic_clusters.to_markdown(index=False)

            all_kw_data = [item for result in st.session_state.ranked_keywords_results if result['status'] == 'ok' for item in result.get('items', [])]
            if all_kw_data:
                kw_list = [{"Keyword": item.get("keyword_data", {}).get("keyword"), "Volume": item.get("keyword_data", {}).get("search_volume")} for item in all_kw_data]
                ranked_keywords_df = pd.DataFrame(kw_list).dropna().drop_duplicates().sort_values("Volume", ascending=False).head(15)
                ranked_keywords_md = ranked_keywords_df.to_markdown(index=False)
            else:
                ranked_keywords_md = "Nessun dato sulle keyword."
            
            paa_str_for_prompt = "\n".join(f"- {paa.get('title', '')}" for paa in paa_items)

            brief_prompt_args = {
                "keyword": query, "strat_analysis_str": strat_analysis_str, "topic_clusters_md": topic_clusters_md,
                "ranked_keywords_md": ranked_keywords_md, "paa_str": paa_str_for_prompt,
            }

            final_brief = run_nlu(get_content_brief_prompt(**brief_prompt_args))
            st.session_state.final_brief = final_brief
    
    if 'final_brief' in st.session_state:
        st.markdown(st.session_state.final_brief)
    
    st.markdown("---")
    st.header("Appendice: Dati di Dettaglio")

    with st.expander("Visualizza Keyword Ranking dei Competitor e Matrice di Copertura"):
        all_keywords_data = []
        for result in st.session_state.ranked_keywords_results:
            if result['status'] == 'ok' and result.get('items'):
                competitor_domain = urlparse(result['url']).netloc.removeprefix('www.')
                for item in result['items']:
                    kd = item.get("keyword_data", {})
                    se = item.get("ranked_serp_element", {})
                    if kd.get("keyword") and kd.get("search_volume") is not None:
                        all_keywords_data.append({
                            "Competitor": competitor_domain, "Keyword": kd.get("keyword"),
                            "Posizione": se.get("rank_absolute"), "Volume": kd.get("search_volume")
                        })
        
        if all_keywords_data:
            df_ranked = pd.DataFrame(all_keywords_data).dropna().sort_values("Volume", ascending=False)
            st.write("**Tabella aggregata delle keyword:**")
            st.dataframe(df_ranked, use_container_width=True, height=300)

            st.write("**Matrice di Copertura (Posizione per Keyword):**")
            try:
                pivot_df = df_ranked.pivot_table(index='Keyword', columns='Competitor', values='Posizione').fillna('-')
                volume_map = df_ranked.set_index('Keyword')['Volume'].drop_duplicates()
                pivot_df['Volume'] = pivot_df.index.map(volume_map)
                pivot_df = pivot_df.sort_values('Volume', ascending=False).drop(columns='Volume')
                st.dataframe(pivot_df, use_container_width=True, height=300)
            except Exception as e:
                st.warning(f"Impossibile creare la matrice di copertura: {e}")
        else:
            st.write("_Nessuna keyword posizionata trovata per i competitor._")
            
    with st.expander("🕵️‍♂️ ISPEZIONE DATI GREZZI DALLA SERP (DEBUG)"):
        st.info("Usa questo box per verificare la risposta completa dell'API DataForSEO.")
        st.json(st.session_state.serp_result)
