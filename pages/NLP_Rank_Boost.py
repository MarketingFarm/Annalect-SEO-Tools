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
    payload = [{
        "keyword": query,
        "location_name": country,
        "language_name": language,
        "get_generative_answers": True
    }]
    try:
        response = session.post("https://api.dataforseo.com/v3/serp/google/organic/live/advanced", json=payload)
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
def fetch_ranked_keywords(url: str, location: str, language: str) -> dict:
    """Estrae le keyword posizionate."""
    payload = [{"target": url, "location_name": location, "language_name": language, "limit": 30}]
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

st.title("🚀 Advanced SEO Content Engine")
st.markdown("Da SERP a Content Brief: un flusso di lavoro potenziato da AI per creare contenuti dominanti.")

st.markdown("""
<style>
    .reportview-container { background: #f0f2f6; }
    .stButton>button { border-radius: 20px; border: 1px solid #1E88E5; background-color: #1E88E5; color: white; }
    .stButton>button:hover { border: 1px solid #1565C0; background-color: #1565C0; color: white; }
    .ql-editor { min-height: 250px; }
    .block-container { padding-top: 2rem; }
    h1, h2 { color: #1E88E5; }
    h3 { border-bottom: 2px solid #90CAF9; padding-bottom: 5px; margin-top: 2rem; color: #1E88E5; }
</style>
""", unsafe_allow_html=True)

if 'analysis_started' not in st.session_state:
    st.session_state.analysis_started = False

def start_analysis():
    if not all([st.session_state.query, st.session_state.country, st.session_state.language]):
        st.warning("Per favore, compila tutti i campi: Query, Country e Lingua.")
        return
    # Pulisce lo stato per una nuova analisi, conservando solo gli input
    for key in list(st.session_state.keys()):
        if key not in ['query', 'country', 'language', 'analysis_started']:
            del st.session_state[key]
    st.session_state.analysis_started = True
    st.rerun() 

def new_analysis():
    st.session_state.analysis_started = False
    # Pulisce tutti i dati dell'analisi precedente
    for key in list(st.session_state.keys()):
        if key not in ['query', 'country', 'language']:
            st.session_state[key] = '' if isinstance(st.session_state[key], str) else None
    st.rerun()

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

if st.session_state.analysis_started:
    query, country, language = st.session_state.query, st.session_state.country, st.session_state.language

    # --- FASE 1: ESTRAZIONE E PARSING DATI SERP ---
    if 'serp_result' not in st.session_state:
        with st.spinner("Fase 1/5: Analizzo la SERP e i competitor..."):
            st.session_state.serp_result = fetch_serp_data(query, country, language)

    # CORREZIONE CRITICA: Controlliamo se la chiamata API ha fallito prima di procedere.
    if not st.session_state.serp_result:
        st.error("Analisi interrotta perché i dati della SERP non sono stati recuperati correttamente. Controllare i log sopra per i dettagli dell'errore API.")
        st.stop() # Ferma l'esecuzione dello script qui.

    items = st.session_state.serp_result.get('items', [])
    organic_results = [item for item in items if item.get("type") == "organic"][:10]
    ai_overview = next((item for item in items if item.get("type") == "generative_answers"), None)
    
    if 'parsed_contents' not in st.session_state:
        with st.spinner("Fase 1.5/5: Estraggo i contenuti delle pagine..."):
            urls_to_parse = [r.get("url") for r in organic_results if r.get("url")]
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_url = {executor.submit(parse_url_content, url): url for url in urls_to_parse}
                results = {future_to_url[future]: future.result() for future in as_completed(future_to_url)}
            
            st.session_state.parsed_contents = [results.get(url, {"html_content": "", "headings": []}) for url in urls_to_parse]
            st.session_state.edited_html_contents = [res['html_content'] for res in st.session_state.parsed_contents]

    # --- FASE 2: ESTRAZIONE KEYWORD RANKING ---
    if 'ranked_keywords_results' not in st.session_state:
        with st.spinner("Fase 2/5: Scopro le keyword dei competitor..."):
            urls_for_ranking = [clean_url(res.get("url")) for res in organic_results if res.get("url")]
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(fetch_ranked_keywords, url, country, language) for url in urls_for_ranking]
                st.session_state.ranked_keywords_results = [f.result() for f in as_completed(futures)]
    
    # --- FASE 3: ANALISI NLU ---
    if 'nlu_strat_text' not in st.session_state:
        with st.spinner("Fase 3/5: L'AI definisce l'intento e le entità..."):
            initial_cleaned_texts = "\n\n--- SEPARATORE TESTO ---\n\n".join(
                filter(None, [BeautifulSoup(html, "html.parser").get_text(separator="\n", strip=True) for html in st.session_state.edited_html_contents])
            )
            if not initial_cleaned_texts.strip():
                st.error("Impossibile recuperare contenuto testuale significativo. L'analisi non può continuare.")
                st.stop()

            with ThreadPoolExecutor() as executor:
                future_strat = executor.submit(run_nlu, get_strategica_prompt(query, initial_cleaned_texts))
                future_comp = executor.submit(run_nlu, get_competitiva_prompt(query, initial_cleaned_texts))
                st.session_state.nlu_strat_text = future_strat.result()
                st.session_state.nlu_comp_text = future_comp.result()

    # --- INIZIO VISUALIZZAZIONE ---
    st.header("1. Analisi Strategica della SERP")
    
    nlu_strat_text = st.session_state.nlu_strat_text
    dfs_strat = parse_markdown_tables(nlu_strat_text)
    if dfs_strat:
        df_strat = dfs_strat[0]
        # Controllo robusto delle colonne prima di creare la mappa
        if all(col in df_strat.columns for col in ['Caratteristica SEO', 'Analisi Sintetica']):
            analysis_map = pd.Series(df_strat['Analisi Sintetica'].values, index=df_strat['Caratteristica SEO'].str.replace(r'\*\*', '', regex=True)).to_dict()
            cols = st.columns(len(analysis_map))
            for col, (label, value) in zip(cols, analysis_map.items()):
                 col.metric(label, value.replace('`', ''))
    
    st.subheader("Paesaggio della SERP e AI Overviews")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.write("**Feature Rilevate in SERP:**")
        # Il conteggio delle feature viene ora fatto in modo diverso
        feature_counts = Counter(item.get("type") for item in items)
        st.dataframe(pd.DataFrame(feature_counts.items(), columns=['Feature', 'Conteggio']).sort_values('Conteggio', ascending=False), hide_index=True)
    with col2:
        st.write("**Analisi AI Overview (Risposta Generativa)**")
        if ai_overview:
            st.info(ai_overview.get("answer"))
            ai_overview_sources = [src.get('url') for src in ai_overview.get("links", [])]
            st.write("**Fonti Citate nell'AI Overview:**")
            if ai_overview_sources:
                for source_url in ai_overview_sources:
                    if any(clean_url(org_url.get('url','')) == clean_url(source_url) for org_url in organic_results):
                        st.success(f"✅ {urlparse(source_url).netloc} (Presente nei Top 10)")
                    else:
                        st.warning(f"⚠️ {urlparse(source_url).netloc} (Esterno ai Top 10)")
            else:
                st.write("_Nessuna fonte esplicitamente citata._")
        else:
            st.write("_Nessuna AI Overview rilevata per questa query._")

    st.header("2. Analisi dei Competitor")
    paa_list = list(dict.fromkeys(q.get("title", "") for item in items if item.get("type") == "people_also_ask" for q in item.get("items", []) if q.get("title")))
    related_list = list(dict.fromkeys((s.get("query") if isinstance(s, dict) else s) for item in items if item.get("type") in ("related_searches", "related_search") for s in item.get("items", [])))
    related_list = [q for q in related_list if q]

    st.subheader("Entità Rilevanti (Common Ground dei Competitor)")
    with st.expander("🔬 Clicca qui per vedere la risposta grezza dell'AI per le Entità"):
        st.text_area("Output NLU (Entità)", st.session_state.get('nlu_comp_text', 'N/A'), height=200)
    
    dfs_comp = parse_markdown_tables(st.session_state.nlu_comp_text)
    df_entities = dfs_comp[0] if dfs_comp else pd.DataFrame(columns=['Categoria', 'Entità', 'Rilevanza Strategica'])
    
    st.info("ℹ️ Puoi modificare le entità in questa tabella. Le tue modifiche guideranno la fase successiva di analisi dei Topic.")
    if 'edited_df_entities' not in st.session_state:
        st.session_state.edited_df_entities = df_entities
    
    st.session_state.edited_df_entities = st.data_editor(st.session_state.edited_df_entities, use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_entities")

    # --- FASE 4: TOPICAL MODELING ---
    if 'df_topic_clusters' not in st.session_state:
         with st.spinner("Fase 4/5: Raggruppo le entità in Topic Cluster semantici..."):
            all_headings = [h for res in st.session_state.parsed_contents for h in res['headings']]
            headings_str = "\n".join(list(dict.fromkeys(all_headings))[:30])
            paa_str = "\n".join(paa_list)
            entities_md = st.session_state.edited_df_entities.to_markdown(index=False)
            
            topic_prompt = get_topic_clusters_prompt(query, entities_md, headings_str, paa_str)
            nlu_topic_text = run_nlu(topic_prompt)
            
            dfs_topics = parse_markdown_tables(nlu_topic_text)
            st.session_state.df_topic_clusters = dfs_topics[0] if dfs_topics else pd.DataFrame(columns=['Topic Cluster (Sotto-argomento Principale)', 'Concetti, Entità e Domande Chiave del Cluster'])

    st.header("3. Architettura del Topic (Topic Modeling)")
    st.info("ℹ️ Questa è la mappa concettuale. Gli H2 del tuo articolo dovrebbero basarsi su questi cluster. Puoi modificare i nomi prima di generare il brief.")

    if 'edited_df_topic_clusters' not in st.session_state:
        st.session_state.edited_df_topic_clusters = st.session_state.df_topic_clusters

    st.session_state.edited_df_topic_clusters = st.data_editor(st.session_state.edited_df_topic_clusters, use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_topics")

    # --- FASE 5: GENERAZIONE CONTENT BRIEF ---
    st.header("4. Content Brief Strategico Finale")
    if st.button("✍️ Genera Brief Dettagliato", type="primary", use_container_width=True):
        with st.spinner("Fase 5/5: Sto scrivendo il brief per il tuo copywriter..."):
            strat_analysis_str = dfs_strat[0].to_markdown(index=False) if dfs_strat else "N/D"
            topic_clusters_md = st.session_state.edited_df_topic_clusters.to_markdown(index=False)

            all_kw_data = [item for result in st.session_state.ranked_keywords_results if result['status'] == 'ok' for item in result['items']]
            if all_kw_data:
                kw_list = [{"Keyword": item.get("keyword_data", {}).get("keyword"), "Volume": item.get("keyword_data", {}).get("search_volume")} for item in all_kw_data]
                ranked_keywords_df = pd.DataFrame(kw_list).dropna().drop_duplicates().sort_values("Volume", ascending=False).head(15)
                ranked_keywords_md = ranked_keywords_df.to_markdown(index=False)
            else:
                ranked_keywords_md = "Nessun dato sulle keyword."
            
            paa_str = "\n".join(f"- {q}" for q in paa_list)

            brief_prompt_args = {
                "keyword": query, "strat_analysis_str": strat_analysis_str, "topic_clusters_md": topic_clusters_md,
                "ranked_keywords_md": ranked_keywords_md, "paa_str": paa_str,
            }

            final_brief = run_nlu(get_content_brief_prompt(**brief_prompt_args))
            st.session_state.final_brief = final_brief
    
    if 'final_brief' in st.session_state:
        st.markdown(st.session_state.final_brief)
    
    st.markdown("---")
    st.header("Appendice: Dati di Dettaglio")

    with st.expander("Visualizza/Modifica Contenuti Estratti dai Competitor"):
        nav_labels = [f"{i+1}. {urlparse(res.get('url', '')).netloc.replace('www.', '')}" for i, res in enumerate(organic_results)]
        selected_index = st.selectbox("Seleziona un competitor:", options=range(len(nav_labels)), format_func=lambda i: nav_labels[i])
        
        st.markdown(f"**URL:** `{organic_results[selected_index].get('url', '')}`")
        # Assicuriamoci che l'indice esista prima di accedere
        if selected_index < len(st.session_state.edited_html_contents):
            edited_content = st_quill(value=st.session_state.edited_html_contents[selected_index], html=True, key=f"quill_{selected_index}")
            if edited_content != st.session_state.edited_html_contents[selected_index]:
                st.session_state.edited_html_contents[selected_index] = edited_content
                st.warning("Contenuto modificato. Per un'analisi aggiornata, avvia una nuova analisi.")

    with st.expander("Visualizza Keyword Ranking dei Competitor e Matrice di Copertura"):
        all_keywords_data = []
        for result in st.session_state.ranked_keywords_results:
            if result['status'] == 'ok' and result['items']:
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
