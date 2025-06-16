import os
import io
import streamlit as st
import requests
import pandas as pd
from urllib.parse import urlparse, urlunparse
from streamlit_quill import st_quill
# Correzione: Import esplicito e standard per la libreria di Gemini
import google.generativeai as genai

# --- INIEZIONE CSS GENERALE ---
st.markdown("""
<style>
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
# Assicurati che i secrets siano configurati in Streamlit Cloud
DFS_USERNAME = st.secrets["dataforseo"]["username"]
DFS_PASSWORD = st.secrets["dataforseo"]["password"]
auth = (DFS_USERNAME, DFS_PASSWORD)

@st.cache_data(show_spinner=False)
def get_countries():
    url = 'https://api.dataforseo.com/v3/serp/google/locations'
    resp = requests.get(url, auth=auth)
    resp.raise_for_status()
    locations = resp.json()['tasks'][0]['result']
    return sorted(loc['location_name'] for loc in locations if loc.get('location_type') == 'Country')

@st.cache_data(show_spinner=False)
def get_languages():
    url = 'https://api.dataforseo.com/v3/serp/google/languages'
    resp = requests.get(url, auth=auth)
    resp.raise_for_status()
    langs = resp.json()['tasks'][0]['result']
    return sorted(lang['language_name'] for lang in langs)

def clean_url(url: str) -> str:
    parsed = urlparse(url)
    cleaned = parsed._replace(query='', params='', fragment='')
    return urlunparse(cleaned)

@st.cache_data(show_spinner=True)
def fetch_serp(query: str, country: str, language: str) -> dict:
    payload = [{
        'keyword': query,
        'location_name': country,
        'language_name': language,
        'calculate_rectangles': True,
        'people_also_ask_click_depth': 1
    }]
    resp = requests.post(
        'https://api.dataforseo.com/v3/serp/google/organic/live/advanced',
        auth=auth,
        json=payload
    )
    resp.raise_for_status()
    return resp.json()['tasks'][0]['result'][0]

# --- CONFIGURAZIONE CORRETTA DI GEMINI ---
try:
    # Prova a prendere la chiave API dai secrets di Streamlit
    api_key = st.secrets["gemini"]["api_key"]
except (KeyError, AttributeError):
    # Altrimenti, prendila dalle variabili d'ambiente
    api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error("API Key di Gemini non trovata. Impostala nei secrets di Streamlit o come variabile d'ambiente (GEMINI_API_KEY).")
    st.stop()

# Configura la libreria con la chiave API. Questo è il metodo corretto.
genai.configure(api_key=api_key)


# === UI PRINCIPALE ===
st.title("Analisi SEO Competitiva Multi-Step")
st.markdown("Questo tool esegue analisi SEO integrando SERP scraping e NLU.")
st.divider()

# Step 1 inputs
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    query = st.text_input("Query", key="query", placeholder="es. migliori scarpe da trekking")
with col2:
    country = st.selectbox("Country", [""] + get_countries(), key="country")
with col3:
    language = st.selectbox("Lingua", [""] + get_languages(), key="language")
with col4:
    contesti = ["", "E-commerce", "Blog / Contenuto Informativo"]
    contesto = st.selectbox("Contesto", contesti, key="contesto")
with col5:
    tip_map = {
        "E-commerce": ["PDP", "PLP"],
        "Blog / Contenuto Informativo": ["Articolo", "Pagina informativa"]
    }
    tipologia = st.selectbox(
        "Tipologia di Contenuto",
        [""] + tip_map.get(contesto, []),
        key="tipologia"
    )

st.markdown("---")
num_opts = [""] + list(range(1, 6))
num_comp = st.selectbox("Numero di competitor da analizzare", num_opts, key="num_competitor", help="Seleziona il numero di testi dei competitor che vuoi analizzare.")
count = int(num_comp) if isinstance(num_comp, int) else 0

# editor WYSIWYG per competitor
st.write("**Incolla qui il testo dei competitor che vuoi analizzare.**")
competitor_texts = []
idx = 1
for _ in range((count + 1) // 2):
    cols_pair = st.columns(2)
    for col in cols_pair:
        if idx <= count:
            with col:
                st.markdown(f"**Testo Competitor #{idx}**")
                competitor_texts.append(st_quill("", key=f"comp_quill_{idx}", html=False))
            idx += 1

# Avvia Analisi
if st.button("🚀 Avvia l'Analisi"):
    if not (query and country and language and contesto and tipologia):
        st.error("Tutti i campi (Query, Country, Lingua, Contesto, Tipologia) sono obbligatori.")
        st.stop()
    active_competitor_texts = [text for text in competitor_texts if text and text.strip()]
    if not active_competitor_texts:
         st.error("Devi inserire il testo di almeno un competitor per procedere con l'analisi NLU.")
         st.stop()

    # --- STEP 1: SERP SCRAPING E TABELLE ---
    st.header("Step 1: Analisi della SERP")
    with st.spinner("Recupero i dati dalla SERP di Google..."):
        result = fetch_serp(query, country, language)
    items = result.get('items', [])

    organic = [it for it in items if it.get('type') == 'organic'][:10]
    data = []
    for it in organic:
        title = it.get('title') or it.get('link_title', '')
        desc = it.get('description') or it.get('snippet', '')
        clean = clean_url(it.get('link') or it.get('url',''))
        data.append({
            'URL': f"<a href='{clean}' target='_blank'>{clean}</a>",
            'Meta Title': title,
            'Lunghezza Title': len(title),
            'Meta Description': desc,
            'Lunghezza Description': len(desc)
        })
    df_org = pd.DataFrame(data)
    def style_title(val):
        return 'background-color: #d4edda' if 50 <= val <= 60 else 'background-color: #f8d7da'
    def style_desc(val):
        return 'background-color: #d4edda' if 120 <= val <= 160 else 'background-color: #f8d7da'
    styled = (
        df_org.style
        .format({'URL': lambda u: u})
        .set_properties(subset=['Lunghezza Title','Lunghezza Description'], **{'text-align':'center'})
        .map(style_title, subset=['Lunghezza Title'])
        .map(style_desc, subset=['Lunghezza Description'])
    )
    st.subheader("Risultati Organici (top 10)")
    st.write(styled.to_html(escape=False), unsafe_allow_html=True)
    st.markdown("---")

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
        df_paa = pd.DataFrame()
        if paa_list:
            df_paa = pd.DataFrame({'Domanda': paa_list})
            st.dataframe(df_paa, use_container_width=True)
        else:
            st.info("Nessuna sezione PAA trovata.")
    with col_rel:
        st.subheader("Ricerche Correlate")
        df_rel = pd.DataFrame()
        if related:
            df_rel = pd.DataFrame({'Query Correlata': related})
            st.dataframe(df_rel, use_container_width=True)
        else:
            st.info("Nessuna sezione Ricerche correlate trovata.")
    st.markdown("---")

    # --- STEP 2: NLU - ANALISI QUALITATIVA E COMPETITIVA ---
    st.header("Step 2: Analisi NLU dei Competitor")
    # Inizializza il modello una sola volta
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    joined_texts = "\n\n---\n\n".join(active_competitor_texts)

    prompt_sintetica = f"""...il tuo prompt per l'analisi sintetica...""" # Ho abbreviato per leggibilità
    
    with st.spinner("Eseguo analisi qualitativa (leggibilità, intent, tone, sentiment)..."):
        # Chiamata API standard
        resp1 = model.generate_content(prompt_sintetica)
    st.subheader("Sintesi Qualitativa dei Contenuti Competitor")
    st.markdown(resp1.text, unsafe_allow_html=True)
    st.markdown("---")

    prompt_competitiva = f"""...il tuo prompt per l'analisi competitiva...""" # Ho abbreviato per leggibilità

    with st.spinner("Identifico entità fondamentali e content gap..."):
        # Chiamata API standard
        resp2 = model.generate_content(prompt_competitiva)
        
    tables_from_resp2 = [blk.strip() for blk in resp2.text.split('###') if blk.strip().startswith("|")]
    
    if len(tables_from_resp2) >= 2:
        table1_entities = tables_from_resp2[0]
        table2_gaps = tables_from_resp2[1]
        st.subheader("Entità Fondamentali (Common Ground Analysis)")
        st.markdown(table1_entities, unsafe_allow_html=True)
        st.subheader("Entità Mancanti (Content Gap Opportunity)")
        st.markdown(table2_gaps, unsafe_allow_html=True)
        st.markdown("---")
    else:
        st.error("L'analisi delle entità e dei content gap non ha prodotto i risultati attesi.")
        st.stop()

    # --- STEP 3: SEO STRATEGY E GENERAZIONE KEYWORD ---
    st.header("Step 3: Strategia SEO e di Contenuto")
    
    paa_markdown = df_paa.to_markdown(index=False) if not df_paa.empty else "Nessuna domanda 'People Also Ask' trovata."
    related_markdown = df_rel.to_markdown(index=False) if not df_rel.empty else "Nessuna 'Ricerca Correlata' trovata."

    prompt_strategia = f"""
## ANALISI SEO STRATEGICA E GENERAZIONE KEYWORD ##
**RUOLO:** ...
---
**DATI FORNITI PER L'ANALISI:**
* **Keyword Principale:** {query}
* **Country:** {country}
* **Lingua:** {language}
* **Contesto del Contenuto:** {contesto}
* **Tipologia di Contenuto:** {tipologia}
* **Testi Completi dei Competitor:**
    {joined_texts}
* **Tabella 1: Entità Principali Estratte dai Competitor:**
    {table1_entities}
* **Tabella 2: Entità Mancanti / Content Gap:**
    {table2_gaps}
* **Tabella 3: Ricerche Correlate dalla SERP:**
    {related_markdown}
* **Tabella 4: People Also Ask (PAA) dalla SERP:**
    {paa_markdown}
---
**COMPITO DETTAGLIATO...**
---
**FORMATO DI OUTPUT OBBLIGATORIO...**
""" # Ho abbreviato i prompt per leggibilità, ma nel codice lasciali interi
    
    with st.spinner("Elaboro la strategia SEO e contenutistica finale..."):
        # Chiamata API standard
        resp3 = model.generate_content(prompt_strategia)
        
    st.subheader("Piano d'Azione Strategico")
    st.markdown(resp3.text, unsafe_allow_html=True)
    st.success("Analisi completata!")
