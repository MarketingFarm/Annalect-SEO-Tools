import os
import io
import streamlit as st
import requests
import pandas as pd
from urllib.parse import urlparse, urlunparse
from streamlit_quill import st_quill
from google import genai

# --- INIEZIONE CSS GENERALE ---
st.markdown("""
<style>
.stElementContainer:has(> iframe) {
  height: 300px;
  overflow-y: scroll;
  overflow-x: hidden;
  max-height: 250px !important;
}
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
def fetch_serp(query: str, country: str, language: str) -> dict | None:
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
    data = resp.json()
    tasks = data.get('tasks')
    if not tasks:
        return None
    results = tasks[0].get('result')
    if not results:
        return None
    return results[0]

# --- CONFIG GEMINI / VERTEX AI ---
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# === SESSION STATE PER CHIUDERE EXPANDER DOPO ANALISI ===
if 'analysis_started' not in st.session_state:
    st.session_state['analysis_started'] = False

def start_analysis():
    st.session_state['analysis_started'] = True

# === UI PRINCIPALE ===
st.title("Analisi SEO Competitiva Multi-Step")
st.markdown("Questo tool esegue analisi SEO integrando SERP scraping e NLU.")
st.divider()

# Step 1 inputs: query, country, language, numero competitor
col1, col2, col3, col4 = st.columns(4)
with col1:
    query = st.text_input("Query", key="query")
with col2:
    country = st.selectbox("Country", [""] + get_countries(), key="country")
with col3:
    language = st.selectbox("Lingua", [""] + get_languages(), key="language")
with col4:
    num_opts = [""] + list(range(1, 6))
    num_comp = st.selectbox("Numero competitor", num_opts, key="num_competitor")
count = int(num_comp) if isinstance(num_comp, int) else 0

st.markdown("---")

# Placeholder contesto e tipologia (rimossi dall'UI)
contesto = ""
tipologia = ""

# Step 1c: editor in expander
competitor_texts: list[str] = []
with st.expander(
    "Testi dei Competitor",
    expanded=not st.session_state['analysis_started']
):
    if not st.session_state['analysis_started']:
        idx = 1
        for _ in range((count + 1) // 2):
            cols_pair = st.columns(2)
            for col in cols_pair:
                if idx <= count:
                    with col:
                        st.markdown(f"**Testo Competitor #{idx}**")
                        competitor_texts.append(st_quill("", key=f"comp_quill_{idx}"))
                    idx += 1
    else:
        # dopo l’analisi, recupera i testi già inseriti senza ricreare gli editor
        for i in range(1, count + 1):
            competitor_texts.append(st.session_state.get(f"comp_quill_{i}", ""))

# Bottone di avvio, chiude subito l’expander
st.button("🚀 Avvia l'Analisi", on_click=start_analysis)

# --- dopo il click, eseguo l’analisi ---
if st.session_state['analysis_started']:
    if not (query and country and language):
        st.error("Query, Country e Lingua sono obbligatori.")
        st.stop()

    # --- STEP SERP SCRAPING E TABELLE ---
    result = fetch_serp(query, country, language)
    if result is None:
        st.error("Errore nel recupero dei dati SERP. Verifica query e parametri.")
        st.stop()
    items = result.get('items', [])

    # ORGANIC TOP 10
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

    # PAA e Ricerche correlate
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
        if paa_list:
            df_paa = pd.DataFrame({'Domanda': paa_list})
            st.write(df_paa.to_html(index=False), unsafe_allow_html=True)
        else:
            st.write("Nessuna sezione PAA trovata.")
    with col_rel:
        st.subheader("Ricerche Correlate")
        if related:
            df_rel = pd.DataFrame({'Query Correlata': related})
            st.write(df_rel.to_html(index=False), unsafe_allow_html=True)
        else:
            st.write("Nessuna sezione Ricerche correlate trovata.")

    # --- STEP NLU: Semantic Content Intelligence ---
    separator = "\n\n--- SEPARATORE TESTO ---\n\n"
    joined_texts = separator.join(competitor_texts)

    prompt_strategica = f"""
## PROMPT: NLU Semantic Content Intelligence ##

**PERSONA:** Agisci come un **Lead SEO Strategist** con 15 anni di esperienza nel posizionare contenuti in settori altamente competitivi. Il tuo approccio è data-driven, ossessionato dall'intento di ricerca e focalizzato a identificare le debolezze dei competitor.
**TESTI DEI COMPETITOR DA ANALIZZARE:**
<TESTI>
{joined_texts}
</TESTI>

---
### ISTRUZIONI PER LA TABELA DI ANALISI

| Caratteristica SEO              | Analisi Sintetica                                                     | Giustificazione e Dettagli                                                                 |
| :------------------------------ | :-------------------------------------------------------------------- | :----------------------------------------------------------------------------------------- |
| **Search Intent Primario**      | `[Informazionale, Commerciale, ecc.]`                                  | `[Spiega perché... ]`                                                                       |
| **Search Intent Secondario**    | `[Informazionale, Commerciale, ecc. o "Nessuno"]`                       | `[Spiega il secondo livello...]`                                                           |
| **Target Audience & Leggibilità**| `[B2B Esperto, B2C Principiante, Generalista, ecc.]`                 | `[Stima il livello e il target]`                                                           |
| **Tone of Voice (ToV)**         | `[Es: "Didattico e professionale", ...]`                              | `[3 aggettivi chiave]`                                                                      |
| **Segnali E-E-A-T**             | `[Deboli / Medi / Forti]`                                             | `[Citazioni di esperti...]`                                                                 |
| **Angolo del Contenuto**        | `[Es: "Guida definitiva...", ...]`                                    | `[Descrive il "gancio"...]`                                                                |

OUTPUT: **SOLO** la tabella Markdown, senza testo aggiuntivo.
"""
    with st.spinner("Semantic Content Analysis..."):
        resp1 = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[prompt_strategica]
        )

    st.subheader("Analisi Strategica e GAP di Contenuto")
    st.markdown(resp1.text, unsafe_allow_html=True)

    # --- STEP ENTITÀ FONDAMENTALI & CONTENT GAP ---
    prompt_competitiva = f"""
## ANALISI COMPETITIVA E CONTENT GAP ##
**RUOLO:** Agisci come un analista SEO d'élite.
**TESTI:**
{joined_texts}

### TABELLA 1: Common Ground Analysis
| Entità | Rilevanza Strategica | Azione SEO Strategica |
| :--- | :--- | :--- |

### TABELLA 2: Content Gap Opportunity
| Entità da Aggiungere | Motivazione dell'Inclusione | Azione SEO Strategica |
| :--- | :--- | :--- |

OUTPUT: **SOLO** le due tabelle Markdown.
"""
    with st.spinner("Entity & Semantic Gap Extraction..."):
        resp2 = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[prompt_competitiva]
        )

    tables = [blk for blk in resp2.text.split("\n\n") if blk.strip().startswith("|")]
    if len(tables) >= 2:
        st.subheader("Semantic Common Ground Analysis")
        st.markdown(tables[0], unsafe_allow_html=True)
        st.subheader("Semantic Content Gap Opportunity")
        st.markdown(tables[1], unsafe_allow_html=True)
    else:
        st.error("⚠️ Gemini non ha restituito le tabelle attese per l'analisi entità.")
        st.markdown("**Output grezzo del modello:**")
        st.text(resp2.text)

    # --- STEP BANCA DATI KEYWORD STRATEGICHE ---
    keyword_principale = query
    table1_entities      = tables[0] if len(tables) > 0 else ""
    table2_gaps          = tables[1] if len(tables) > 1 else ""
    table3_related_searches = pd.DataFrame({'Query Correlata': related}).to_markdown(index=False)
    table4_paa              = pd.DataFrame({'Domanda': paa_list}).to_markdown(index=False)

    prompt_bank = f"""
## PROMPT: BANCA DATI KEYWORD STRATEGICHE ##

**INPUTS:**
* **Keyword Principale:** {keyword_principale}
* **Tabella 1: Entità Principali:** 
{table1_entities}
* **Tabella 2: Entità Mancanti:** 
{table2_gaps}
* **Tabella 3: Ricerche Correlate:** 
{table3_related_searches}
* **Tabella 4: People Also Ask:** 
{table4_paa}

<TASK>
...
OUTPUT: tabella unica...
</TASK>
"""
    with st.spinner("Semantic Keyword Mining..."):
        resp3 = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[prompt_bank]
        )
    st.subheader("Banca Dati Keyword Strategiche")
    st.markdown(resp3.text, unsafe_allow_html=True)
