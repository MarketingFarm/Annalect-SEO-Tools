import os
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlunparse

import pandas as pd
import requests
import streamlit as st
from google import genai
# Importazioni dal client DataForSEO
from dataforseo_client.api_client import ApiClient
from dataforseo_client.configuration import Configuration
from dataforseo_client.api.on_page_api import OnPageApi
from dataforseo_client.models.on_page_content_parsing_live_request_info import OnPageContentParsingLiveRequestInfo
# Importazione per gli editor di testo
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

# Sessione HTTP globale per riutilizzo connessioni (per SERP API e altre)
session = requests.Session()
session.auth = DFS_AUTH

# Client API DataForSEO per On-Page Parsing
try:
    config = Configuration(username=DFS_AUTH[0], password=DFS_AUTH[1])
    api_client = ApiClient(config)
    on_page_api = OnPageApi(api_client)
except Exception as e:
    st.error(f"Errore nella configurazione del client DataForSEO: {e}")
    st.stop()

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
    """Estrae il contenuto testuale da un URL usando l'API On-Page di DataForSEO."""
    post_data = [
        OnPageContentParsingLiveRequestInfo(
            url=url,
            markdown_view=True,
            enable_javascript=True,
            enable_xhr=True,
            disable_cookie_popup=True
        )
    ]
    try:
        response = on_page_api.content_parsing_live(post_data)
        if response.status_code != 20000:
            return f"## Errore API ##\nCodice: {response.status_code} - Messaggio: {response.status_message}"
        task = response.tasks[0]
        if task.status_code != 20000:
            return f"## Errore Task ##\nCodice: {task.status_code} - Messaggio: {task.status_message}"
        result_item = task.result[0]
        if not result_item.items:
             return "## Nessun Item nel Risultato ##"
        page_item = result_item.items[0]
        markdown_content = getattr(page_item, 'page_as_markdown', None)
        if markdown_content and isinstance(markdown_content, str):
            return markdown_content
        page_content = page_item.page_content
        if not page_content:
            return f"## Contenuto non Trovato ##\nNessun contenuto testuale analizzabile per {url}."
        text_parts = []
        all_topics = (page_content.main_topic or []) + (page_content.secondary_topic or [])
        if not all_topics:
            return f"## Contenuto non Strutturato ##\nNessun topic (h1, h2...) rilevato per {url}."
        all_topics.sort(key=lambda x: x.level or 99)
        for topic in all_topics:
            if topic.h_title:
                text_parts.append(f"<{ 'h' + str(topic.level) }>{' '.join(topic.h_title.split())}</{ 'h' + str(topic.level) }>")
            if topic.primary_content:
                for content in topic.primary_content:
                    if content.text:
                        text_parts.append(' '.join(content.text.split()))
        return "\n\n".join(text_parts)
    except Exception as e:
        return f"## Errore Imprevisto ##\nDurante l'analisi dell'URL {url}: {str(e)}"

# --- MODIFICA: Rimosso il parametro 'order_by' non valido ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_ranked_keywords(url: str, location: str, language: str) -> dict:
    """Estrae le keyword posizionate e restituisce un dizionario con lo stato."""
    payload = [{
        "target": url,
        "location_name": location,
        "language_name": language,
        "limit": 30
    }]
    try:
        response = session.post("https://api.dataforseo.com/v3/dataforseo_labs/google/ranked_keywords/live", json=payload)
        response.raise_for_status()
        data = response.json()
        if data.get("tasks_error", 0) > 0 or not data.get("tasks") or not data["tasks"][0].get("result"):
            error_message = data.get("tasks",[{}])[0].get("status_message", "Nessun risultato nell'API.")
            return {"url": url, "status": "failed", "error": error_message, "items": []}
        return {"url": url, "status": "ok", "items": data["tasks"][0]["result"][0].get("items", [])}
    except requests.RequestException as e:
        return {"url": url, "status": "failed", "error": str(e), "items": []}

def run_nlu(prompt: str, model_name: str = GEMINI_MODEL) -> str:
    """Esegue una singola chiamata al modello Gemini usando il client."""
    try:
        response = gemini_client.models.generate_content(model=f"models/{model_name}", contents=[prompt])
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
st.divider()

def start_analysis_callback():
    if not all([st.session_state.query, st.session_state.country, st.session_state.language]):
        st.error("Tutti i campi (Query, Country, Lingua) sono obbligatori.")
        return
    st.session_state.analysis_started = True

def new_analysis_callback():
    keys_to_clear = list(st.session_state.keys())
    for key in keys_to_clear:
        del st.session_state[key]
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

        if 'competitor_texts_list' not in st.session_state:
            urls_to_parse = [r.get("url") for r in organic_results if r.get("url")]
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_url = {executor.submit(parse_url_content, url): url for url in urls_to_parse}
                results = {}
                for future in as_completed(future_to_url):
                    url = future_to_url[future]
                    results[url] = future.result()
            st.session_state.competitor_texts_list = [results.get(url, "") for url in urls_to_parse]

    with st.spinner("Fase 2/4: Estrazione keyword posizionate per ogni URL..."):
        if 'ranked_keywords_results' not in st.session_state:
            ranked_keywords_api_results = []
            urls_for_ranking = [res.get("url") for res in organic_results]
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_url = {executor.submit(fetch_ranked_keywords, url, st.session_state.country, st.session_state.language): url for url in urls_for_ranking}
                for future in as_completed(future_to_url):
                    ranked_keywords_api_results.append(future.result())
            st.session_state.ranked_keywords_results = ranked_keywords_api_results

    initial_texts = st.session_state.get('competitor_texts_list', [])
    initial_joined_texts = "\n\n--- SEPARATORE TESTO ---\n\n".join(filter(None, initial_texts))

    if not initial_joined_texts.strip():
        st.error("Impossibile recuperare il contenuto testuale da analizzare. L'analisi non può continuare.")
        st.stop()

    with st.spinner("Fase 3/4: Esecuzione analisi NLU..."):
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

    st.subheader("Contenuti dei Competitor Analizzati")
    for i, result in enumerate(organic_results):
        url = result.get('url', '')
        domain_full = urlparse(url).netloc if url else "URL non disponibile"
        domain_clean = domain_full.removeprefix("www.")
        with st.expander(f"**Competitor #{i+1}:** {domain_clean}"):
            st.markdown(f"**URL:** `{url}`")
            st_quill(
                value=initial_texts[i] if i < len(initial_texts) else "",
                key=f"quill_editor_{i}"
            )
    
    st.divider()

    st.subheader("Keyword Ranking dei Competitor (Top 30 per URL)")
    ranked_keywords_results = st.session_state.get('ranked_keywords_results', [])
    
    with st.expander("Mostra report dettagliato dell'estrazione keyword"):
        if not ranked_keywords_results:
            st.write("Nessun tentativo di estrazione registrato.")
        for result in ranked_keywords_results:
            domain = urlparse(result['url']).netloc.removeprefix('www.')
            if result['status'] == 'ok':
                st.success(f"✅ {domain}: OK ({len(result['items'])} keyword trovate)")
            else:
                st.error(f"❌ {domain}: ERRORE ({result['error']})")

    all_keywords_data = []
    for result in ranked_keywords_results:
        if result['status'] == 'ok':
            competitor_domain = urlparse(result['url']).netloc.removeprefix('www.')
            for item in result['items']:
                kd = item.get("keyword_data", {})
                se = item.get("ranked_serp_element", {})
                intent_info = kd.get("intent_info", {})
                all_keywords_data.append({
                    "Competitor": competitor_domain,
                    "Keyword": kd.get("keyword"),
                    "Posizione": se.get("rank_absolute"),
                    "Volume di Ricerca": kd.get("search_volume"),
                    "Search Intent": intent_info.get("intent", "N/D").title() if intent_info else "N/D"
                })
    
    if all_keywords_data:
        ranked_keywords_df = pd.DataFrame(all_keywords_data)
        ranked_keywords_df = ranked_keywords_df.dropna(subset=["Keyword", "Volume di Ricerca"])
        ranked_keywords_df["Volume di Ricerca"] = pd.to_numeric(ranked_keywords_df["Volume di Ricerca"])
        ranked_keywords_df = ranked_keywords_df.sort_values(by="Volume di Ricerca", ascending=False).reset_index(drop=True)

        st.info("Tabella completa con tutte le keyword posizionate dai competitor, ordinate per volume di ricerca.")
        st.dataframe(ranked_keywords_df, use_container_width=True, height=350)
        
        st.info("Matrice di copertura: mostra per ogni keyword la posizione dei vari competitor. Utile per identificare sovrapposizioni e opportunità.")
        
        try:
            keyword_info = ranked_keywords_df[['Keyword', 'Volume di Ricerca', 'Search Intent']].drop_duplicates(subset='Keyword').set_index('Keyword')
            pivot_df = ranked_keywords_df.pivot_table(
                index='Keyword',
                columns='Competitor',
                values='Posizione'
            ).fillna('')
            
            coverage_matrix = keyword_info.join(pivot_df).sort_values(by='Volume di Ricerca', ascending=False)
            
            st.dataframe(coverage_matrix, use_container_width=True, height=350)
        except Exception as e:
            st.warning(f"Non è stato possibile creare la matrice di copertura: {e}")

    else:
        st.warning("Nessuna keyword posizionata trovata per gli URL analizzati.")

    st.divider()
    
    edited_competitor_texts = [st.session_state.get(f"quill_editor_{i}", "") for i in range(len(organic_results))]
    final_joined_texts = "\n\n--- SEPARATORE TESTO ---\n\n".join(filter(None, edited_competitor_texts))
    
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
            prompt_mining_args = {
                "keyword": st.session_state.query, "country": st.session_state.country, "language": st.session_state.language, "texts": final_joined_texts,
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
