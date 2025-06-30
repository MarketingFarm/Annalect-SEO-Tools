# -*- coding: utf-8 -*-
import os
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlunparse
import ast

# --- Importazioni Fondamentali ---
import pandas as pd
import numpy as np
from numpy.linalg import norm
import requests
import streamlit as st
from google import generativeai as genai

# --- Importazioni per UI Avanzata ---
from streamlit_quill import st_quill
from streamlit_agraph import agraph, Node, Edge, Config
from bs4 import BeautifulSoup


# --- 1. CONFIGURAZIONE E COSTANTI ---

# Configura il client Gemini
try:
    # NOTA: Assicurati di aver impostato la variabile d'ambiente GEMINI_API_KEY
    GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except KeyError:
    st.error("GEMINI_API_KEY non trovata. Imposta la variabile d'ambiente.")
    st.stop()

# Configura le credenziali DataForSEO
try:
    # NOTA: Assicurati di aver configurato i secrets di Streamlit [dataforseo]
    DFS_AUTH = (st.secrets["dataforseo"]["username"], st.secrets["dataforseo"]["password"])
except (KeyError, FileNotFoundError):
    st.error("Credenziali DataForSEO non trovate negli secrets di Streamlit.")
    st.stop()

# Sessione HTTP globale per riutilizzo connessioni
session = requests.Session()
session.auth = DFS_AUTH

# Modelli Gemini da utilizzare
GEMINI_PRO_MODEL = "gemini-1.5-pro-latest"
GEMINI_EMBEDDING_MODEL = "text-embedding-004"


# --- 2. FUNZIONI DI UTILITY E API EVOLUTE ---

# --- FUNZIONI API DATA-FOR-SEO ---

@st.cache_data(show_spinner=False)
def get_countries() -> list[str]:
    """Recupera e cachea la lista dei paesi da DataForSEO."""
    try:
        resp = session.get('https://api.dataforseo.com/v3/serp/google/locations')
        resp.raise_for_status()
        locs = resp.json()['tasks'][0]['result']
        return sorted(loc['location_name'] for loc in locs if loc.get('location_type') == 'Country')
    except (requests.RequestException, KeyError, IndexError):
        return ["United States"] # Fallback

@st.cache_data(show_spinner=False)
def get_languages() -> list[str]:
    """Recupera e cachea la lista delle lingue da DataForSEO."""
    try:
        resp = session.get('https://api.dataforseo.com/v3/serp/google/languages')
        resp.raise_for_status()
        langs = resp.json()['tasks'][0]['result']
        return sorted(lang['language_name'] for lang in langs)
    except (requests.RequestException, KeyError, IndexError):
        return ["English"] # Fallback

@st.cache_data(ttl=600)
def fetch_serp_data(query: str, country: str, language: str) -> dict | None:
    """Esegue la chiamata API a DataForSEO per ottenere l'intero ecosistema della SERP."""
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
    Estrae contenuto testuale E strutturale (headings) da un URL.
    Restituisce un dizionario con 'text' e 'headings'.
    """
    if url.lower().endswith(('.pdf', '.xml', '.jpg', '.png', '.gif')):
        return {"text": "", "headings": {}}

    post_data = [{"url": url, "enable_javascript": True}]
    try:
        response = session.post("https://api.dataforseo.com/v3/on_page/page_content/live", json=post_data)
        response.raise_for_status()
        data = response.json()

        if data.get("tasks_error", 0) > 0 or not data.get("tasks") or not data["tasks"][0].get("result"):
            return {"text": "", "headings": {}}

        result_item = data["tasks"][0]["result"][0]["items"][0]
        full_content = result_item.get("page_content", "")
        
        # Estrazione Heading
        headings = {}
        if result_item.get("meta", {}).get("htags"):
            for tag, values in result_item["meta"]["htags"].items():
                if values:
                    headings[tag.upper()] = values

        # Estrazione testo pulito da HTML per robustezza
        soup = BeautifulSoup(full_content, 'html.parser')
        # Rimuove elementi non contenutistici
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()
        
        text = soup.get_text(separator=' ', strip=True)
        return {"text": text, "headings": headings}

    except (requests.RequestException, KeyError, IndexError, TypeError):
        return {"text": "", "headings": {}}

# --- FUNZIONI GEMINI E NLU ---

@st.cache_data(ttl=3600, show_spinner=False)
def get_embedding(text: str) -> list[float] | None:
    """Genera embedding per un testo usando il modello Gemini."""
    if not text:
        return None
    try:
        result = genai.embed_content(model=f"models/{GEMINI_EMBEDDING_MODEL}", content=text)
        return result['embedding']
    except Exception:
        return None

def run_nlu(prompt: str) -> str:
    """Esegue una singola chiamata al modello Gemini Pro."""
    try:
        model = genai.GenerativeModel(GEMINI_PRO_MODEL)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Errore durante la chiamata a Gemini: {e}")
        return f"ERRORE NLU: {e}"

# --- FUNZIONI DI ANALISI SEMANTICA ---

def calculate_cosine_similarity(vec_a, vec_b) -> float:
    """Calcola la similarità coseno tra due vettori di embedding."""
    if vec_a is None or vec_b is None:
        return 0.0
    # Converto in array numpy se non lo sono già
    np_vec_a = np.array(vec_a)
    np_vec_b = np.array(vec_b)
    
    # Calcolo il prodotto scalare
    dot_product = np.dot(np_vec_a, np_vec_b)
    
    # Calcolo la norma (magnitudine) di ogni vettore
    norm_a = norm(np_vec_a)
    norm_b = norm(np_vec_b)
    
    # Calcolo la similarità coseno, gestendo il caso di vettori a norma zero
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)

def analyze_serp_ecosystem(serp_result: dict) -> dict:
    """Analizza l'intero risultato della SERP e lo categorizza."""
    ecosystem = {
        "ai_overview": [],
        "organic": [],
        "people_also_ask": [],
        "related_searches": [],
        "video": [],
        "knowledge_graph": [],
        "top_stories": [],
        "other_features": []
    }
    
    paa_titles = set()
    items = serp_result.get("items", [])
    if not items: return ecosystem

    for item in items:
        item_type = item.get("type")
        if item_type == "organic":
            ecosystem["organic"].append(item)
        elif item_type == "ai_overview":
            ecosystem["ai_overview"].append(item.get("text", ""))
        elif item_type == "people_also_ask":
            for paa_item in item.get("items", []):
                if title := paa_item.get("title"):
                    if title not in paa_titles:
                        ecosystem["people_also_ask"].append(title)
                        paa_titles.add(title)
        elif item_type in ("related_searches", "related_search"):
             ecosystem["related_searches"].extend([s.get("query", s) for s in item.get("items", []) if isinstance(s, (dict, str))])
        elif item_type == "video":
            ecosystem["video"].extend([v.get("title") for v in item.get("items", []) if v.get("title")])
        elif item_type == "knowledge_graph":
            ecosystem["knowledge_graph"].append(item.get("description"))
        elif item_type == "top_stories":
            ecosystem["top_stories"].extend([s.get("title") for s in item.get("items", []) if s.get("title")])
        else:
            ecosystem["other_features"].append(item_type)

    # Rimuovi duplicati
    ecosystem["related_searches"] = list(dict.fromkeys(filter(None, ecosystem["related_searches"])))
    ecosystem["people_also_ask"] = list(paa_titles)
    
    return ecosystem

def parse_markdown_tables(text: str) -> list[pd.DataFrame]:
    """Estrae tutte le tabelle Markdown da un testo e le converte in DataFrame."""
    tables_md = re.findall(r"((?:\|.*\|[\r\n]+)+)", text)
    dataframes = []
    for table_md in tables_md:
        lines = [l.strip() for l in table_md.strip().splitlines()]
        if len(lines) < 2: continue
        
        # Gestisce header con spazi extra
        header = [h.strip() for h in lines[0].split('|') if h.strip()]
        
        # La riga di separazione non è necessaria per il parsing
        rows_data = []
        for row_line in lines[2:]:
            cells = [cell.strip() for cell in row_line.split('|')]
            # Rimuove il primo e l'ultimo elemento vuoto derivanti dagli split
            if len(cells) > 1:
                row_data = cells[1:-1]
                # Assicura che il numero di colonne corrisponda all'header
                if len(row_data) == len(header):
                    rows_data.append(row_data)

        if rows_data:
            try:
                df = pd.DataFrame(rows_data, columns=header)
                dataframes.append(df)
            except Exception:
                # Se la creazione fallisce, salta questa tabella
                continue
    return dataframes
    
def parse_triplets(text: str) -> list:
    """Estrae triplette (soggetto, relazione, oggetto) da una stringa."""
    triplets = []
    # Cerca pattern come ('entità 1', 'relazione', 'entità 2')
    found = re.findall(r"\((['\"].*?['\"]),\s*(['\"].*?['\"]),\s*(['\"].*?['\"])\)", text)
    for match in found:
        try:
            # Pulisce le virgolette e gli spazi
            triplet = tuple(ast.literal_eval(item) for item in match)
            triplets.append(triplet)
        except:
            continue
    return triplets


# --- 3. PROMPT EVOLUTI PER L'ARCHITETTURA DI CONTENUTI ---

def get_strategica_prompt_v2(keyword: str, serp_summary: str) -> str:
    """Costruisce il prompt per l'analisi strategica della SERP."""
    return f"""
## PROMPT: NLU SERP Intelligence ##
**PERSONA:** Agisci come un **Lead SEO Strategist** con 15 anni di esperienza nel posizionare contenuti in settori altamente competitivi. Il tuo approccio è data-driven, ossessionato dall'intento di ricerca e focalizzato a identificare le debolezze dei competitor per creare contenuti dominanti. Pensi in termini di E-E-A-T, topic authority e user journey.

**CONTESTO:** Ho analizzato la SERP di Google per la query strategica e ho estratto non solo i risultati organici, ma l'intero ecosistema di features. Il tuo compito è interpretare questi dati per definire la strategia di base.

**QUERY STRATEGICA:** {keyword}

**ECOSISTEMA DELLA SERP:**
```markdown
{serp_summary}
