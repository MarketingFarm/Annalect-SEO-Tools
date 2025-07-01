Ecco il codice completo ottimizzato con tutte le modifiche richieste:

```python
import os
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlunparse
from collections import Counter
from datetime import datetime
import io

import pandas as pd
import requests
import streamlit as st
import google.generativeai as genai
from streamlit_quill import st_quill
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

# --- 1. CONFIGURAZIONE E COSTANTI ---

# Configura il client Gemini
try:
    GEMINI_API_KEY = st.secrets.get("gemini", {}).get("api_key") or os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        st.error("GEMINI_API_KEY non trovata. Impostala nei Secrets di Streamlit o come variabile d'ambiente.")
        st.stop()
    
    genai.configure(api_key=GEMINI_API_KEY)
    
    gemini_client = genai.GenerativeModel("gemini-1.5-pro")
    
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

# Inizializza tracking costi API
if 'api_costs' not in st.session_state:
    st.session_state.api_costs = {
        'dataforseo_calls': 0,
        'gemini_tokens': 0,
        'estimated_cost': 0.0,
        'parse_calls': 0,
        'ranked_keywords_calls': 0
    }

# --- 2. FUNZIONI DI UTILITY E API ---

def update_api_cost(api_type: str, units: int = 1):
    """Aggiorna il tracking dei costi API"""
    cost_map = {
        'dataforseo_serp': 0.0025,  # $2.5 per 1000
        'dataforseo_parse': 0.001,   # $1 per 1000
        'dataforseo_ranked': 0.002,  # $2 per 1000
        'gemini_1k_tokens': 0.00001  # Stima
    }
    
    if api_type == 'dataforseo_serp':
        st.session_state.api_costs['dataforseo_calls'] += units
        st.session_state.api_costs['estimated_cost'] += cost_map['dataforseo_serp'] * units
    elif api_type == 'dataforseo_parse':
        st.session_state.api_costs['parse_calls'] += units
        st.session_state.api_costs['estimated_cost'] += cost_map['dataforseo_parse'] * units
    elif api_type == 'dataforseo_ranked':
        st.session_state.api_costs['ranked_keywords_calls'] += units
        st.session_state.api_costs['estimated_cost'] += cost_map['dataforseo_ranked'] * units
    elif api_type == 'gemini_tokens':
        st.session_state.api_costs['gemini_tokens'] += units
        st.session_state.api_costs['estimated_cost'] += cost_map['gemini_1k_tokens'] * (units / 1000)

@st.cache_data(show_spinner="Caricamento Nazioni (con codici)...")
def get_locations_data() -> pd.DataFrame:
    """Recupera e cachea la lista completa delle nazioni con i relativi codici."""
    try:
        resp = session.get('https://api.dataforseo.com/v3/serp/google/locations', timeout=10)
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
        resp = session.get('https://api.dataforseo.com/v3/serp/google/languages', timeout=10)
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
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
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

@st.cache_data(ttl=86400, show_spinner="Analisi SERP in corso...")  # Cache 24 ore
def fetch_serp_data(query: str, location_code: int, language_code: str) -> dict | None:
    """Esegue la chiamata API a DataForSEO con retry logic e gestione rate limits."""
    post_data = [{
        "keyword": query,
        "location_code": location_code,
        "language_code": language_code,
        "device": "desktop",
        "os": "windows",
        "depth": 10,
        "load_async_ai_overview": True,
        "people_also_ask_click_depth": 1,  # Ridotto da 4
        "calculate_rectangles": False,  # Non necessario
        "load_async": ["organic", "paid", "featured_snippet", "people_also_ask", "related_searches", "knowledge_graph"]
    }]
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = session.post(
                "https://api.dataforseo.com/v3/serp/google/organic/live/advanced", 
                json=post_data,
                timeout=30
            )
            
            if response.status_code == 429:  # Rate limit
                wait_time = int(response.headers.get('Retry-After', 60))
                st.warning(f"Rate limit raggiunto. Attendo {wait_time} secondi...")
                time.sleep(wait_time)
                continue
                
            response.raise_for_status()
            data = response.json()
            
            if data.get("tasks_error", 0) > 0:
                st.error("DataForSEO ha restituito un errore nel task:")
                st.json(data["tasks"])
                return None

            if not data.get("tasks") or not data["tasks"][0].get("result"):
                st.error("Risposta da DataForSEO non valida o senza risultati.")
                return None
                
            # Aggiorna costi
            update_api_cost('dataforseo_serp')
            
            return data["tasks"][0]["result"][0]
            
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                st.warning(f"Tentativo {attempt + 1} fallito. Riprovo...")
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                st.error(f"Errore dopo {max_retries} tentativi: {e}")
                return None

@st.cache_data(ttl=86400, show_spinner=False)  # Cache 24 ore
def parse_url_content(url: str, enable_js: bool = False) -> dict:
    """Estrae il contenuto da una pagina con opzione per JavaScript."""
    default_return = {"text_content": "", "headings": []}
    if not url or url.lower().endswith('.pdf'):
        return default_return

    # Determina se abilitare JS basandosi sul dominio
    js_required_domains = ['medium.com', 'twitter.com', 'linkedin.com']
    if any(domain in url.lower() for domain in js_required_domains):
        enable_js = True

    post_data = [{
        "url": url, 
        "enable_javascript": enable_js,
        "enable_xhr": enable_js,
        "disable_cookie_popup": True,
        "load_resources": False,  # Risparmia banda
        "custom_js": "" if not enable_js else None
    }]
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = session.post(
                "https://api.dataforseo.com/v3/on_page/content_parsing/live", 
                json=post_data,
                timeout=20
            )
            
            if response.status_code == 429:
                wait_time = int(response.headers.get('Retry-After', 30))
                time.sleep(wait_time)
                continue
                
            response.raise_for_status()
            data = response.json()

            if data.get("tasks_error", 0) > 0 or not data.get("tasks"):
                return default_return

            result_list = data["tasks"][0].get("result")
            if not result_list: return default_return

            items_list = result_list[0].get("items")
            if not items_list: return default_return

            page_content = items_list[0].get("page_content")
            if not page_content: return default_return

            main_topic_data = page_content.get('main_topic')
            if not isinstance(main_topic_data, list): return default_return

            text_parts, headings = [], []
            for section in main_topic_data:
                h_title = section.get('h_title')
                if h_title:
                    level = section.get('level', 2)
                    headings.append(f"H{level}: {h_title}")

                primary_content_list = section.get('primary_content')
                if isinstance(primary_content_list, list):
                    for item in primary_content_list:
                        text = item.get("text", "").strip()
                        if text:
                            text_parts.append(text)

            # Aggiorna costi
            update_api_cost('dataforseo_parse')
            
            # Ritorna solo testo pulito, non HTML
            return {"text_content": "\n\n".join(text_parts), "headings": headings}
            
        except (requests.RequestException, KeyError, IndexError, TypeError) as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return default_return

@st.cache_data(ttl=86400, show_spinner=False)  # Cache 24 ore
def fetch_ranked_keywords(url: str, location_name: str, language_name: str) -> dict:
    """Estrae le keyword posizionate con retry logic."""
    payload = [{
        "target": url, 
        "location_name": location_name, 
        "language_name": language_name, 
        "limit": 20,  # Ridotto da 30
        "include_clickstream_data": False  # Risparmia costi
    }]
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = session.post(
                "https://api.dataforseo.com/v3/dataforseo_labs/google/ranked_keywords/live", 
                json=payload,
                timeout=20
            )
            
            if response.status_code == 429:
                wait_time = int(response.headers.get('Retry-After', 30))
                time.sleep(wait_time)
                continue
                
            response.raise_for_status()
            data = response.json()
            
            if data.get("tasks_error", 0) > 0 or not data.get("tasks"):
                error_message = data.get("tasks",[{}])[0].get("status_message", "N/A")
                return {"url": url, "status": "failed", "error": error_message, "items": []}
            
            # Aggiorna costi
            update_api_cost('dataforseo_ranked')
            
            api_items = data["tasks"][0]["result"][0].get("items")
            return {"url": url, "status": "ok", "items": api_items if api_items is not None else []}
            
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return {"url": url, "status": "failed", "error": str(e), "items": []}

def run_nlu(prompt: str) -> str:
    """Esegue una singola chiamata al modello Gemini con tracking tokens."""
    try:
        # Stima approssimativa tokens (4 caratteri = 1 token)
        estimated_tokens = len(prompt) // 4
        
        response = gemini_client.generate_content(prompt)
        
        # Aggiorna costi
        update_api_cost('gemini_tokens', estimated_tokens)
        
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

# --- 3. FUNZIONI PER LA COSTRUZIONE DEI PROMPT (OTTIMIZZATI) ---

def get_strategica_prompt(keyword: str, texts: str) -> str:
    """Prompt ottimizzato per l'analisi strategica."""
    # Limita lunghezza testi
    texts_limited = texts[:4000]
    
    return f"""Analizza per "{keyword}".

Crea SOLO questa tabella:
| Caratteristica SEO | Analisi Sintetica |
|---|---|
| **Search Intent Primario** | [tipo + max 5 parole] |
| **Search Intent Secondario** | [tipo + max 5 parole] |
| **Target Audience** | [max 6 parole] |
| **Tone of Voice (ToV)** | [3 aggettivi] |

Poi: 
### Analisi Approfondita Audience ###
[3-4 frasi su bisogni e pain points]

TESTI:
{texts_limited}"""

def get_competitiva_prompt(keyword: str, texts: str) -> str:
    """Prompt ottimizzato per l'analisi delle entità."""
    texts_limited = texts[:4000]
    
    return f"""Keyword: {keyword}

Estrai entità dai testi. Output SOLO tabella (no intro):

| Categoria | Entità | Rilevanza Strategica |
|---|---|---|
[righe con Categoria, Entità separate da virgola, Alta/Media]

TESTI:
{texts_limited}"""

def get_topic_clusters_prompt(keyword: str, entities_md: str, headings_str: str, paa_str: str) -> str:
    """Prompt ottimizzato per il Topical Modeling."""
    # Limita input
    entities_limited = entities_md[:1500]
    headings_limited = headings_str[:1000]
    paa_limited = paa_str[:500]
    
    return f"""Query: {keyword}

Crea 5-7 cluster tematici. SOLO tabella:

| Topic Cluster | Concetti e Domande Chiave |
|---|---|

Dati:
ENTITÀ: {entities_limited}
HEADINGS: {headings_limited}
PAA: {paa_limited}"""

def get_content_brief_prompt(**kwargs) -> str:
    """Prompt ottimizzato per generare il Content Brief."""
    # Limita tutti gli input
    strat_limited = kwargs.get('strat_analysis_str', '')[:1000]
    clusters_limited = kwargs.get('topic_clusters_md', '')[:1500]
    keywords_limited = kwargs.get('ranked_keywords_md', '')[:800]
    paa_limited = kwargs.get('paa_str', '')[:600]
    
    return f"""Query: {kwargs.get('keyword', '')}

Genera brief:
## ✍️ Content Brief: {kwargs.get('keyword', '')}

### Title & Meta
- 2 opzioni title (max 60 char)
- 1 meta description (max 155 char)

### Struttura
- H1 con keyword
- H2 basati su clusters
- Concetti sotto ogni H2

### Entità Must-Have
[5-7 entità chiave]

### FAQ
[PAA come H3]

Dati:
ANALISI: {strat_limited}
CLUSTERS: {clusters_limited}
KEYWORDS: {keywords_limited}
PAA: {paa_limited}"""

# --- 4. FUNZIONI EXPORT ---

def generate_pdf_report(analysis_data: dict) -> bytes:
    """Genera un report PDF con tutti i dati dell'analisi."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Titolo
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a0dab'),
        spaceAfter=30
    )
    
    story.append(Paragraph(f"SEO Analysis Report: {analysis_data.get('keyword', '')}", title_style))
    story.append(Spacer(1, 0.25*inch))
    
    # Data e costi
    story.append(Paragraph(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    story.append(Paragraph(f"Costo stimato analisi: ${analysis_data.get('cost', 0):.3f}", styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    # Analisi strategica
    if 'strategic_analysis' in analysis_data:
        story.append(Paragraph("Analisi Strategica", styles['Heading2']))
        story.append(Paragraph(analysis_data['strategic_analysis'], styles['Normal']))
        story.append(Spacer(1, 0.25*inch))
    
    # Topic clusters
    if 'topic_clusters' in analysis_data:
        story.append(Paragraph("Topic Clusters", styles['Heading2']))
        # Converti DataFrame in tabella
        data = [analysis_data['topic_clusters'].columns.tolist()]
        data.extend(analysis_data['topic_clusters'].values.tolist())
        
        t = Table(data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(t)
        story.append(Spacer(1, 0.25*inch))
    
    # Content brief
    if 'content_brief' in analysis_data:
        story.append(Paragraph("Content Brief", styles['Heading2']))
        story.append(Paragraph(analysis_data['content_brief'], styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.read()

def export_to_json(analysis_data: dict) -> str:
    """Esporta tutti i dati in formato JSON."""
    export_data = {
        "timestamp": datetime.now().isoformat(),
        "keyword": analysis_data.get('keyword', ''),
        "location": analysis_data.get('location', ''),
        "language": analysis_data.get('language', ''),
        "api_costs": st.session_state.api_costs,
        "serp_data": analysis_data.get('serp_data', {}),
        "competitors": analysis_data.get('competitors', []),
        "entities": analysis_data.get('entities', []),
        "topic_clusters": analysis_data.get('topic_clusters', []),
        "content_brief": analysis_data.get('content_brief', ''),
        "ranked_keywords": analysis_data.get('ranked_keywords', [])
    }
    
    return json.dumps(export_data, indent=2, ensure_ascii=False)

# --- 5. INTERFACCIA UTENTE E FLUSSO PRINCIPALE ---

st.set_page_config(layout="wide", page_title="Advanced SEO Content Engine", page_icon="🔍")

st.title("🔍 Analisi SEO Competitiva Multi-Step")
st.markdown("Tool avanzato per analisi SEO con SERP scraping, content parsing e AI analysis.")

# Mostra costi in sidebar
with st.sidebar:
    st.header("📊 Monitoraggio Costi API")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("DataForSEO Calls", st.session_state.api_costs['dataforseo_calls'])
        st.metric("Parse Calls", st.session_state.api_costs['parse_calls'])
    with col2:
        st.metric("Ranked KW Calls", st.session_state.api_costs['ranked_keywords_calls'])
        st.metric("Gemini Tokens", f"{st.session_state.api_costs['gemini_tokens']:,}")
    
    st.metric("💰 Costo Totale Stimato", f"${st.session_state.api_costs['estimated_cost']:.3f}")
    
    if st.button("🔄 Reset Contatori"):
        for key in st.session_state.api_costs:
            st.session_state.api_costs[key] = 0 if key != 'estimated_cost' else 0.0

st.markdown("""
<style>
    :root { --m3c23: #8E87FF; }
    .stButton>button { border-radius: 4px; }
    h1 { font-size: 2.5rem; color: #333; }
    h2, h3 { color: #555; }
    .metric-card {
        background-color: #f0f4ff;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.5rem;
    }
    .export-section {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 1.5rem;
        margin-top: 2rem;
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
    current_keys = ['query', 'location_code', 'language_code', 'location_name', 'language_name']
    for key in list(st.session_state.keys()):
        if key not in current_keys and key != 'api_costs':
            del st.session_state[key]
    st.session_state.analysis_started = True
    st.rerun() 

def new_analysis():
    current_keys = ['query', 'location_code', 'language_code', 'location_name', 'language_name', 'api_costs']
    for key in list(st.session_state.keys()):
        if key not in current_keys:
            del st.session_state[key]
    st.session_state.analysis_started = False
    st.rerun()

with st.container():
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1.2])
    with col1:
        st.text_input("Query", key="query", placeholder="es. migliori smartphone 2024")
    with col2:
        loc_options = pd.concat([pd.DataFrame([{'name': '', 'code': None}]), locations_df], ignore_index=True)
        selected_location_name = st.selectbox("Country", options=loc_options['name'], key="location_name")
        if selected_location_name:
            st.session_state.location_code = int(loc_options[loc_options['name'] == selected_location_name]['code'].iloc[0])
        else:
            st.session_state.location_code = None

    with col3:
        lang_options = pd.concat([pd.DataFrame([{'name': '', 'code': None}]), languages_df], ignore_index=True)
        selected_language_name = st.selectbox("Lingua", options=lang_options['name'], key="language_name")
        if selected_language_name:
            st.session_state.language_code = lang_options[lang_options['name'] == selected_language_name]['code'].iloc[0]
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
       with st.spinner("Fase 1/5: Analizzo la SERP..."):
           st.session_state.serp_result = fetch_serp_data(query, location_code, language_code)

   if not st.session_state.serp_result:
       st.error("Analisi interrotta: i dati della SERP non sono stati recuperati. Controllare i log sopra per l'errore API.")
       st.stop() 

   items = st.session_state.serp_result.get('items', [])
   organic_results = [item for item in items if item.get("type") == "organic"]
   
   # Estrai TUTTI i tipi di risultati SERP disponibili
   AIO_TYPES = ["ai_overview", "generative_answers"]
   ai_overview = next((item for item in items if item.get("type") in AIO_TYPES), None)
   featured_snippet = next((item for item in items if item.get("type") == "featured_snippet"), None)
   knowledge_graph = next((item for item in items if item.get("type") == "knowledge_graph"), None)
   
   paa_items = next((item for item in items if item.get("type") == "people_also_ask"), {}).get("items", [])
   related_searches = next((item for item in items if item.get("type") == "related_searches"), {}).get("items", [])

   if 'parsed_contents' not in st.session_state:
       urls_to_parse = [r.get("url") for r in organic_results[:5] if r.get("url")]  # Limita a top 5
       if urls_to_parse:
           with st.spinner(f"Fase 1.5/5: Estraggo i contenuti di {len(urls_to_parse)} pagine..."):
               with ThreadPoolExecutor(max_workers=3) as executor:  # Ridotto workers
                   future_to_url = {executor.submit(parse_url_content, url): url for url in urls_to_parse}
                   results = {future_to_url[future]: future.result() for future in as_completed(future_to_url)}
               
               st.session_state.parsed_contents = [results.get(url, {"text_content": "", "headings": []}) for url in urls_to_parse]
               # Salva solo testo pulito, non HTML
               st.session_state.parsed_texts = [res['text_content'] for res in st.session_state.parsed_contents]
       else:
           st.session_state.parsed_contents = []
           st.session_state.parsed_texts = []

   if 'aio_source_images' not in st.session_state and ai_overview:
       # Recupera immagini solo per le prime 3 fonti AIO
       aio_references = ai_overview.get("references", [])[:3]
       urls_to_fetch_images = [ref.get("url") for ref in aio_references if ref.get("url")]
       if urls_to_fetch_images:
           with st.spinner(f"Fase 1.6/5: Estraggo le immagini per {len(urls_to_fetch_images)} fonti AIO..."):
               with ThreadPoolExecutor(max_workers=3) as executor:
                   future_to_url = {executor.submit(fetch_main_image_url, url): url for url in urls_to_fetch_images}
                   image_results = {future_to_url[future]: future.result() for future in as_completed(future_to_url)}
                   st.session_state.aio_source_images = image_results
   elif 'aio_source_images' not in st.session_state:
       st.session_state.aio_source_images = {}

   if 'ranked_keywords_results' not in st.session_state:
       urls_for_ranking = [clean_url(res.get("url")) for res in organic_results[:3] if res.get("url")]  # Solo top 3
       if urls_for_ranking:
           with st.spinner(f"Fase 2/5: Scopro le keyword di {len(urls_for_ranking)} competitor..."):
               with ThreadPoolExecutor(max_workers=3) as executor:
                   futures = [executor.submit(fetch_ranked_keywords, url, location_name, language_name) for url in urls_for_ranking]
                   st.session_state.ranked_keywords_results = [f.result() for f in as_completed(futures)]
       else:
           st.session_state.ranked_keywords_results = []
   
   if 'nlu_strat_text' not in st.session_state:
       # Usa testo pulito salvato, non HTML
       initial_cleaned_texts = "\n\n--- SEPARATORE TESTO ---\n\n".join(
           filter(None, st.session_state.get('parsed_texts', []))
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
   
   # Mostra Featured Snippet se presente
   if featured_snippet:
       st.info("📌 **Featured Snippet**")
       col1, col2 = st.columns([3, 1])
       with col1:
           st.markdown(f"**{featured_snippet.get('title', '')}**")
           st.markdown(featured_snippet.get('description', ''))
       with col2:
           if featured_snippet.get('url'):
               st.markdown(f"[Fonte]({featured_snippet.get('url')})")
   
   # Mostra Knowledge Graph se presente
   if knowledge_graph:
       with st.expander("📊 Knowledge Graph"):
           kg_title = knowledge_graph.get('title', '')
           kg_description = knowledge_graph.get('description', '')
           kg_type = knowledge_graph.get('type', '')
           
           if kg_title:
               st.subheader(kg_title)
           if kg_type:
               st.caption(f"Tipo: {kg_type}")
           if kg_description:
               st.write(kg_description)
           
           # Mostra attributi aggiuntivi
           kg_items = knowledge_graph.get('items', [])
           if kg_items:
               for item in kg_items[:5]:  # Limita a 5 items
                   if item.get('title') and item.get('text'):
                       st.write(f"**{item['title']}**: {item['text']}")
   
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
               col.markdown(f"""<div class="metric-card"><div style="font-size:0.8rem; color: #666;">{label}</div><div style="font-size:1rem; color:#202124; font-weight:500;">{value}</div></div>""", unsafe_allow_html=True)
   
   # Mostra analisi audience se presente
   audience_analysis = nlu_strat_text.split("### Analisi Approfondita Audience ###")
   if len(audience_analysis) > 1:
       st.info("👥 " + audience_analysis[1].strip())
   
   st.divider()

   if ai_overview:
       all_references = ai_overview.get("references", [])
       if 'num_aio_sources_to_show' not in st.session_state:
           st.session_state.num_aio_sources_to_show = 3

       def show_all_sources():
           st.session_state.num_aio_sources_to_show = len(all_references)

       references_to_show = all_references[:st.session_state.num_aio_sources_to_show]

       svg_logo = """<svg class="fWWlmf JzISke" height="24" width="24" aria-hidden="true" viewBox="0 0 471 471" xmlns="http://www.w3.org/2000/svg" style="vertical-align: middle;"><path fill="var(--m3c23)" d="M235.5 471C235.5 438.423 229.22 407.807 216.66 379.155C204.492 350.503 187.811 325.579 166.616 304.384C145.421 283.189 120.498 266.508 91.845 254.34C63.1925 241.78 32.5775 235.5 0 235.5C32.5775 235.5 63.1925 229.416 91.845 217.249C120.498 204.689 145.421 187.811 166.616 166.616C187.811 145.421 204.492 120.497 216.66 91.845C229.22 63.1925 235.5 32.5775 235.5 0C235.5 32.5775 241.584 63.1925 253.751 91.845C266.311 120.497 283.189 145.421 304.384 166.616C325.579 187.811 350.503 204.689 379.155 217.249C407.807 229.416 438.423 235.5 471 235.5C438.423 235.5 407.807 241.78 379.155 254.34C350.503 266.508 325.579 283.189 304.384 304.384C283.189 325.579 266.311 350.503 253.751 379.155C241.584 407.807 235.5 438.423 235.5 471Z"></path></svg>"""
       header_html = f'<div style="display: flex; align-items: center; gap: 12px; margin-bottom: 1rem;">{svg_logo}<h2 style="margin: 0; font-size: 28px;">AI Overview</h2></div>'
       st.markdown(header_html, unsafe_allow_html=True)
       
       aio_col1, aio_col2 = st.columns([2, 1.5]) 
       
       with aio_col1:
           main_text_html = "<div style='font-size: 16px; line-height: 1.6;'>" + "<p>" + "</p><p>".join(item.get('text', '').replace('\n', '<br>') for item in ai_overview.get('items', []) if item.get('text')) + "</p></div>"
           st.markdown(main_text_html, unsafe_allow_html=True)

       with aio_col2:
           for ref in references_to_show:
               image_url = st.session_state.aio_source_images.get(ref.get("url"))
               image_html = f'<div style="flex: 1; min-width: 100px;"><a href="{ref.get("url")}" target="_blank"><img src="{image_url}" style="width: 100%; border-radius: 8px;"></a></div>' if image_url else ''
               
               card_html = f"""
               <div style="background-color: #f0f4ff; border-radius: 12px; padding: 16px; margin-bottom: 1rem; display: flex; gap: 16px; align-items: stretch;">
                   <div style="flex: 3; display: flex; flex-direction: column;">
                       <a href="{ref.get('url')}" target="_blank" style="text-decoration: none; color: inherit; flex-grow: 1;">
                           <div style="font-weight: 500; color: #1f1f1f; margin-bottom: 8px; font-size: 16px;">{ref.get('title')}</div>
                       </a>
                       <div style="font-size: 12px; color: #202124; display: flex; align-items: center; margin-top: 8px;">
                           <img src="https://www.google.com/s2/favicons?domain={ref.get('domain')}&sz=16" style="width:16px; height:16px; margin-right: 8px;">
                           <span>{ref.get('source', ref.get('domain'))}</span>
                       </div>
                   </div>
                   {image_html}
               </div>
               """
               st.markdown(card_html, unsafe_allow_html=True)
           
           if len(all_references) > st.session_state.num_aio_sources_to_show:
               st.button("Mostra tutti", on_click=show_all_sources, use_container_width=True)

       st.divider()

   left_col, right_col = st.columns([2, 1], gap="large")

   with left_col:
       st.markdown('<h3 style="margin-top:0;">Risultati Organici</h3>', unsafe_allow_html=True)
       html_string = ""
       for i, res in enumerate(organic_results[:10]):  # Mostra max 10 risultati
           url_raw = res.get("url", "")
           if not url_raw: continue
           p = urlparse(url_raw)
           pretty_url = str(p.netloc + p.path).replace("www.","")
           name = res.get("breadcrumb", "").split("›")[0].strip() if res.get("breadcrumb") else p.netloc.replace('www.','')
           title = res.get("title", "")
           desc = res.get("description", "")
           
           # Aggiungi indicatore se è stato analizzato
           analyzed_indicator = "✓" if i < len(st.session_state.parsed_contents) else ""
           
           html_string += f"""
           <div style="margin-bottom: 2rem;">
               <div style="display: flex; align-items: center; margin-bottom: 0.2rem;">
                   <img src="https://www.google.com/s2/favicons?domain={p.netloc}&sz=64" 
                        onerror="this.onerror=null;this.src='https://www.google.com/favicon.ico';" 
                        style="width: 26px; height: 26px; border-radius: 50%; border: 1px solid #d2d2d2; margin-right: 0.5rem;">
                   <div>
                       <div style="color: #202124; font-size: 16px; line-height: 20px;">{name} {analyzed_indicator}</div>
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
           st.markdown('<h3 style="margin-top:0;">People Also Ask</h3>', unsafe_allow_html=True)
           paa_pills = ''.join(f'<span style="background-color:#f7f8f9;padding:8px 12px;border-radius:4px;font-size:16px;margin-right:4px;margin-bottom:8px;display:inline-block;">{paa.get("title")}</span>' for paa in paa_items[:8])  # Limita a 8
           st.markdown(f"<div>{paa_pills}</div>", unsafe_allow_html=True)
       
       if related_searches:
           st.markdown('<h3 style="margin-top:1.5rem;">Ricerche Correlate</h3>', unsafe_allow_html=True)
           related_pills = ''.join(f'<span style="background-color:#f7f8f9;padding:8px 12px;border-radius:4px;font-size:16px;margin-right:4px;margin-bottom:8px;display:inline-block;">{r}</span>' for r in related_searches[:8])  # Limita a 8
           st.markdown(f"<div>{related_pills}</div>", unsafe_allow_html=True)

   st.divider()
   
   st.header("3. Contenuti dei Competitor")
   if organic_results and st.session_state.parsed_texts:
       nav_labels = [f"{i+1}. {urlparse(res.get('url', '')).netloc.replace('www.', '')}" for i, res in enumerate(organic_results[:len(st.session_state.parsed_texts)])]
       selected_index = st.radio("Seleziona un competitor:", options=range(len(nav_labels)), format_func=lambda i: nav_labels[i], horizontal=True, label_visibility="collapsed")
       
       if selected_index < len(st.session_state.parsed_texts):
           # Mostra solo testo, con possibilità di modifica
           edited_text = st.text_area(
               "Contenuto estratto (modificabile):",
               value=st.session_state.parsed_texts[selected_index],
               height=300,
               key=f"text_{selected_index}"
           )
           
           if edited_text != st.session_state.parsed_texts[selected_index]:
               st.session_state.parsed_texts[selected_index] = edited_text
               # Forza ricalcolo NLU
               if 'nlu_strat_text' in st.session_state:
                   del st.session_state['nlu_strat_text']
               if 'nlu_comp_text' in st.session_state:
                   del st.session_state['nlu_comp_text']
               st.rerun()
           
           # Mostra headings estratti
           if selected_index < len(st.session_state.parsed_contents):
               headings = st.session_state.parsed_contents[selected_index].get('headings', [])
               if headings:
                   with st.expander("📋 Struttura Headings"):
                       for h in headings:
                           st.write(h)
   else:
       st.write("Nessun contenuto da analizzare.")

   st.header("4. Analisi NLU Avanzata")
   
   st.subheader("Entità Rilevanti")
   with st.expander("🔬 Debug: Output grezzo AI"):
       col1, col2 = st.columns(2)
       with col1:
           st.text_area("Analisi Strategica", st.session_state.get('nlu_strat_text', 'N/A'), height=200)
       with col2:
           st.text_area("Analisi Entità", st.session_state.get('nlu_comp_text', 'N/A'), height=200)
   
   dfs_comp = parse_markdown_tables(st.session_state.nlu_comp_text)
   df_entities = dfs_comp[0] if dfs_comp else pd.DataFrame(columns=['Categoria', 'Entità', 'Rilevanza Strategica'])
   
   st.info("ℹ️ Modifica le entità per guidare la generazione dei topic cluster.")
   if 'edited_df_entities' not in st.session_state:
       st.session_state.edited_df_entities = df_entities.copy()
   
   st.session_state.edited_df_entities = st.data_editor(
       st.session_state.edited_df_entities, 
       use_container_width=True, 
       hide_index=True, 
       num_rows="dynamic", 
       key="editor_entities"
   )

   if 'df_topic_clusters' not in st.session_state:
       with st.spinner("Fase 4/5: Raggruppo in Topic Cluster..."):
           all_headings = [h for res in st.session_state.parsed_contents for h in res['headings']]
           headings_str = "\n".join(list(dict.fromkeys(all_headings))[:20])  # Limita a 20
           paa_str = "\n".join([paa.get('title', '') for paa in paa_items[:10]])  # Limita a 10
           entities_md = st.session_state.edited_df_entities.to_markdown(index=False)
           
           topic_prompt = get_topic_clusters_prompt(query, entities_md, headings_str, paa_str)
           nlu_topic_text = run_nlu(topic_prompt)
           
           dfs_topics = parse_markdown_tables(nlu_topic_text)
           st.session_state.df_topic_clusters = dfs_topics[0] if dfs_topics else pd.DataFrame(columns=['Topic Cluster', 'Concetti e Domande Chiave'])

   st.subheader("Architettura del Topic")
   st.info("ℹ️ Questi cluster diventeranno gli H2 del tuo contenuto.")

   if 'edited_df_topic_clusters' not in st.session_state:
       st.session_state.edited_df_topic_clusters = st.session_state.df_topic_clusters.copy()

   st.session_state.edited_df_topic_clusters = st.data_editor(
       st.session_state.edited_df_topic_clusters, 
       use_container_width=True, 
       hide_index=True, 
       num_rows="dynamic", 
       key="editor_topics"
   )

   st.header("5. Content Brief Finale")
   
   col1, col2, col3 = st.columns(3)
   with col1:
       generate_brief = st.button("✍️ Genera Brief", type="primary", use_container_width=True)
   with col2:
       export_pdf = st.button("📄 Esporta PDF", use_container_width=True, disabled='final_brief' not in st.session_state)
   with col3:
       export_json = st.button("💾 Esporta JSON", use_container_width=True, disabled='final_brief' not in st.session_state)
   
   if generate_brief:
       with st.spinner("Fase 5/5: Genero il content brief..."):
           strat_analysis_str = dfs_strat[0].to_markdown(index=False) if dfs_strat else "N/D"
           topic_clusters_md = st.session_state.edited_df_topic_clusters.to_markdown(index=False)

           all_kw_data = [item for result in st.session_state.ranked_keywords_results if result['status'] == 'ok' for item in result.get('items', [])]
           if all_kw_data:
               kw_list = [{"Keyword": item.get("keyword_data", {}).get("keyword"), "Volume": item.get("keyword_data", {}).get("search_volume")} for item in all_kw_data]
               ranked_keywords_df = pd.DataFrame(kw_list).dropna().drop_duplicates().sort_values("Volume", ascending=False).head(10)
               ranked_keywords_md = ranked_keywords_df.to_markdown(index=False)
           else:
               ranked_keywords_md = "Nessuna keyword trovata."
           
           paa_str_for_prompt = "\n".join(f"- {paa.get('title', '')}" for paa in paa_items[:8])

           brief_prompt_args = {
               "keyword": query, 
               "strat_analysis_str": strat_analysis_str, 
               "topic_clusters_md": topic_clusters_md,
               "ranked_keywords_md": ranked_keywords_md, 
               "paa_str": paa_str_for_prompt,
           }

           final_brief = run_nlu(get_content_brief_prompt(**brief_prompt_args))
           st.session_state.final_brief = final_brief
           st.session_state.analysis_data = {
               'keyword': query,
               'location': location_name,
               'language': language_name,
               'cost': st.session_state.api_costs['estimated_cost'],
               'strategic_analysis': strat_analysis_str,
               'topic_clusters': st.session_state.edited_df_topic_clusters,
               'content_brief': final_brief,
               'serp_data': st.session_state.serp_result,
               'competitors': organic_results[:5],
               'entities': st.session_state.edited_df_entities.to_dict('records'),
               'ranked_keywords': all_kw_data
           }
   
   if 'final_brief' in st.session_state:
       st.markdown(st.session_state.final_brief)
       
       # Export functionality
       if export_pdf:
           pdf_bytes = generate_pdf_report(st.session_state.analysis_data)
           st.download_button(
               label="⬇️ Scarica Report PDF",
               data=pdf_bytes,
               file_name=f"seo_analysis_{query.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
               mime="application/pdf"
           )
       
       if export_json:
           json_str = export_to_json(st.session_state.analysis_data)
           st.download_button(
               label="⬇️ Scarica Dati JSON",
               data=json_str,
               file_name=f"seo_data_{query.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
               mime="application/json"
           )
   
   st.markdown("---")
   st.header("📊 Appendice: Dati Dettaglio")

   with st.expander("Keyword Ranking e Matrice Copertura"):
       all_keywords_data = []
       for result in st.session_state.ranked_keywords_results:
           if result['status'] == 'ok' and result.get('items'):
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
           
           # Mostra metriche aggregate
           col1, col2, col3 = st.columns(3)
           with col1:
               st.metric("Keywords Totali", len(df_ranked['Keyword'].unique()))
           with col2:
               st.metric("Volume Medio", f"{df_ranked['Volume'].mean():.0f}")
           with col3:
               st.metric("Top Volume", f"{df_ranked['Volume'].max():,}")
           
           st.write("**Keywords Posizionate:**")
           st.dataframe(df_ranked, use_container_width=True, height=300)

           st.write("**Matrice di Copertura:**")
           try:
               pivot_df = df_ranked.pivot_table(index='Keyword', columns='Competitor', values='Posizione').fillna('-')
               volume_map = df_ranked.set_index('Keyword')['Volume'].drop_duplicates()
               pivot_df['Volume'] = pivot_df.index.map(volume_map)
               pivot_df = pivot_df.sort_values('Volume', ascending=False).drop(columns='Volume')
               
               # Applica styling condizionale
               def color_positions(val):
                   if val == '-':
                       return ''
                   try:
                       pos = int(val)
                       if pos <= 3:
                           return 'background-color: #90EE90'
                       elif pos <= 10:
                           return 'background-color: #FFFFE0'
                       else:
                           return 'background-color: #FFB6C1'
                   except:
                       return ''
               
               styled_df = pivot_df.style.applymap(color_positions)
               st.dataframe(styled_df, use_container_width=True, height=300)
               
               st.caption("🟢 Top 3 | 🟡 Posizione 4-10 | 🔴 Posizione 11+")
               
           except Exception as e:
               st.warning(f"Impossibile creare la matrice: {e}")
       else:
           st.write("_Nessuna keyword posizionata trovata._")
   
   with st.expander("🔍 Dati SERP Completi (Debug)"):
       st.json(st.session_state.serp_result)
   
# Footer con riepilogo costi
   st.markdown("---")
   col1, col2, col3 = st.columns(3)
   with col1:
       st.caption(f"Analisi completata: {datetime.now().strftime('%H:%M:%S')}")
   with col2:
       total_api_calls = (st.session_state.api_costs['dataforseo_calls'] + 
                         st.session_state.api_costs['parse_calls'] + 
                         st.session_state.api_costs['ranked_keywords_calls'])
       st.caption(f"API calls totali: {total_api_calls}")
   with col3:
       st.caption(f"Costo stimato: ${st.session_state.api_costs['estimated_cost']:.3f}")

# Se l'analisi non è stata avviata, mostra informazioni utili
else:
   st.markdown("""
   ### 🚀 Come utilizzare questo tool
   
   1. **Inserisci una Query**: La parola chiave per cui vuoi ottimizzare il contenuto
   2. **Seleziona Country e Lingua**: Per risultati localizzati
   3. **Clicca "Avvia Analisi"**: Il tool eseguirà 5 fasi di analisi
   
   ### 📊 Cosa analizza il tool:
   
   - **SERP Analysis**: Risultati organici, AI Overview, Featured Snippets, Knowledge Graph
   - **Content Extraction**: Estrae e analizza i contenuti dei top competitor
   - **Entity Recognition**: Identifica entità e concetti chiave
   - **Topic Modeling**: Raggruppa i contenuti in cluster tematici
   - **Content Brief**: Genera un brief dettagliato per la creazione del contenuto
   
   ### 💡 Features avanzate:
   
   - **Modifica in tempo reale**: Puoi modificare entità e topic cluster
   - **Export multipli**: PDF report e JSON per integrazioni
   - **Monitoraggio costi**: Traccia l'uso delle API in tempo reale
   - **Cache intelligente**: Risparmia sui costi con cache di 24 ore
   
   ### 📈 Metriche incluse:
   
   - Search Intent primario e secondario
   - Target audience e Tone of Voice
   - Keyword posizionate dei competitor
   - Matrice di copertura keyword
   - People Also Ask e ricerche correlate
   """)
   
   # Mostra esempi di query
   with st.expander("💡 Esempi di query da analizzare"):
       st.markdown("""
       **E-commerce:**
       - migliori smartphone 2024
       - come scegliere lavatrice
       - recensioni robot aspirapolvere
       
       **Informazionali:**
       - come investire in borsa
       - dieta mediterranea benefici
       - intelligenza artificiale cos'è
       
       **Local SEO:**
       - ristoranti Milano centro
       - dentista Roma prezzi
       - palestra Napoli economica
       
       **B2B:**
       - software gestionale PMI
       - consulenza SEO professionale
       - servizi cloud computing
       """)
   
   # Mostra statistiche di utilizzo se disponibili
   if st.session_state.api_costs['dataforseo_calls'] > 0:
       st.markdown("### 📊 Statistiche sessione corrente")
       col1, col2, col3, col4 = st.columns(4)
       with col1:
           st.metric("Analisi completate", st.session_state.api_costs['dataforseo_calls'])
       with col2:
           st.metric("Pagine analizzate", st.session_state.api_costs['parse_calls'])
       with col3:
           st.metric("Token Gemini", f"{st.session_state.api_costs['gemini_tokens']:,}")
       with col4:
           st.metric("Costo totale", f"${st.session_state.api_costs['estimated_cost']:.3f}")

# Aggiungi CSS per migliorare l'aspetto delle tabelle esportate
st.markdown("""
<style>
   /* Stile per le tabelle nel data editor */
   .stDataFrame {
       font-size: 14px;
   }
   
   /* Stile per i pulsanti di export */
   .stDownloadButton {
       margin-top: 1rem;
   }
   
   /* Migliora leggibilità metriche */
   [data-testid="metric-container"] {
       background-color: #f0f2f6;
       padding: 1rem;
       border-radius: 0.5rem;
       margin: 0.5rem 0;
   }
   
   /* Stile per expander */
   .streamlit-expanderHeader {
       font-weight: 600;
       font-size: 1.1rem;
   }
   
   /* Fix per il layout delle colonne */
   [data-testid="column"] {
       padding: 0 0.5rem;
   }
</style>
""", unsafe_allow_html=True)

# Script per tracking analytics (opzionale)
st.markdown("""
<script>
   // Log utilizzo features
   document.addEventListener('DOMContentLoaded', function() {
       const buttons = document.querySelectorAll('button');
       buttons.forEach(button => {
           button.addEventListener('click', function() {
               console.log('Feature used:', this.textContent);
           });
       });
   });
</script>
""", unsafe_allow_html=True)
