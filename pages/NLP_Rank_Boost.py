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

# --- CONFIG GEMINI / VERTEX AI ---
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# === UI PRINCIPALE ===
st.title("Analisi SEO Competitiva Multi-Step")
st.markdown("Questo tool esegue analisi SEO integrando SERP scraping e NLU.")
st.divider()

# Step 1 inputs
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    query = st.text_input("Query", key="query")
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
num_comp = st.selectbox("Numero di competitor da analizzare", num_opts, key="num_competitor")
count = int(num_comp) if isinstance(num_comp, int) else 0

# editor WYSIWYG per competitor
competitor_texts = []
idx = 1
for _ in range((count + 1) // 2):
    cols_pair = st.columns(2)
    for col in cols_pair:
        if idx <= count:
            with col:
                st.markdown(f"**Testo Competitor #{idx}**")
                competitor_texts.append(st_quill("", key=f"comp_quill_{idx}"))
            idx += 1

# Avvia Analisi
if st.button("🚀 Avvia l'Analisi"):
    if not (query and country and language):
        st.error("Query, Country e Lingua sono obbligatori.")
        st.stop()

    # --- STEP SERP SCRAPING E TABELLE ---
    result = fetch_serp(query, country, language)
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
        .applymap(style_title, subset=['Lunghezza Title'])
        .applymap(style_desc, subset=['Lunghezza Description'])
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

    # --- STEP NLU: leggibilità, intent, tone, sentiment ---
    joined_texts = "\n---\n".join(competitor_texts)
    prompt_sintetica = f"""
## PROMPT: ANALISI SINTETICA AVANZATA DEL CONTENUTO ##

**RUOLO:** Agisci come un analista SEO e Content Strategist esperto. Il tuo compito è distillare le caratteristiche qualitative fondamentali da un insieme di testi dei competitor.

**CONTESTO:** Ho raccolto i testi delle pagine che si posizionano meglio in Google per una specifica query. Devo capire le loro caratteristiche comuni per creare un contenuto superiore.

**OBIETTIVO:** Analizza i testi forniti di seguito e compila UNA SINGOLA tabella Markdown di sintesi. La tabella deve rappresentare la media o la tendenza predominante riscontrata in TUTTI i testi.

**TESTI DA ANALIZZARE:**
---
{joined_texts}
---

**ISTRUZIONI DETTAGLIATE PER LA COMPILAZIONE:**

1. **Livello Leggibilità:** Stima il pubblico di destinazione basandoti sulla complessità generale del linguaggio e dei concetti. Inserisci anche il target (Generalista, B2C, B2B o più di uno).
2. **Search Intent:** Classificazione (Informazionale, Transazionale, Commerciale, Navigazionale).
3. **Tone of Voce:** Tono predominante (es: "Formale e accademico", "Informale e rassicurante").
4. **Tone of Voice (Approfondimento):** Tre aggettivi distinti.
5. **Sentiment Medio:** Positivo/Neutro/Negativo con giustificazione (≤10 parole).

Output: **SOLO** la tabella Markdown iniziando dall’header.
| Livello Leggibilità | Search Intent | Tone of Voce | Tone of Voice (Approfondimento) | Sentiment Medio |
| :--- | :--- | :--- | :--- | :--- |
"""
    with st.spinner("Analisi qualitativa (leggibilità, intent, tone, sentiment)..."):
        resp1 = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[prompt_sintetica]
        )
    st.subheader("Sintesi Qualitativa")
    st.markdown(resp1.text, unsafe_allow_html=True)

    # --- STEP ENTITÀ FONDAMENTALI & CONTENT GAP ---
    prompt_competitiva = f"""
## ANALISI COMPETITIVA E CONTENT GAP ##
**RUOLO:** Agisci come un analista SEO d'élite, specializzato in analisi semantica competitiva.

**CONTESTO:** Obiettivo: superare i primi 3 competitor per la keyword target. Analizza i loro testi.

**COMPITO:** Analizza i testi competitor:
---
{joined_texts}

1. Identifica l'**Entità Centrale** condivisa da tutti i testi.
2. Definisci il **Search Intent Primario** a cui i competitor rispondono.
3. Crea DUE tabelle Markdown separate:

### TABELLA 1: ENTITÀ FONDAMENTALI (Common Ground Analysis)
| Entità | Rilevanza Strategica | Azione per il Mio Testo |
| :--- | :--- | :--- |

### TABELLA 2: ENTITÀ MANCANTI (Content Gap Opportunity)
| Entità da Aggiungere | Motivazione dell'Inclusione | Azione SEO Strategica |
| :--- | :--- | :--- |

Mantieni solo le due tabelle, con markdown valido.
"""
    with st.spinner("Analisi entità e content gap..."):
        resp2 = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[prompt_competitiva]
        )
    tables = [blk for blk in resp2.text.split("\n\n") if blk.strip().startswith("|")]
    st.subheader("Entità Fondamentali (Common Ground Analysis)")
    st.markdown(tables[0], unsafe_allow_html=True)
    st.subheader("Entità Mancanti (Content Gap Opportunity)")
    st.markdown(tables[1], unsafe_allow_html=True)

    # --- STEP BANCA DATI KEYWORD STRATEGICHE ---
    # Preparo variabili per il prompt
    keyword_principale = query
    table1_entities = tables[0]
    table2_gaps = tables[1]
    table3_related_searches = (
        "| Query Correlata |\n| :--- |\n" +
        "\n".join(f"| {item} |" for item in related)
    )
    table4_paa = (
        "| Domanda |\n| :--- |\n" +
        "\n".join(f"| {q} |" for q in paa_list)
    )
    full_text = joined_texts

    prompt_banca = f"""
## PROMPT: BANCA DATI KEYWORD STRATEGICHE ##

**PERSONA:** Agisci come un Semantic SEO Data-Miner, un analista d'élite il cui unico scopo è estrarre e classificare l'intero patrimonio di keyword di una SERP...

<INPUTS>
* **Keyword Principale:** {keyword_principale}
* **Country:** {country}
* **Lingua:** {language}
* **Contesto del Contenuto:** {contesto}
* **Tipologia di Contenuto:** {tipologia}
* **Testi Completi dei Competitor:** {full_text}
* **Tabella 1: Entità Principali Estratte:** {table1_entities}
* **Tabella 2: Entità Mancanti / Content Gap:** {table2_gaps}
* **Tabella 3: Ricerche Correlate dalla SERP:** {table3_related_searches}
* **Tabella 4: People Also Ask (PAA) dalla SERP:** {table4_paa}
</INPUTS>

<TASK>
1. Analisi e Classificazione di keyword, entità e domande.
2. Aggregazione e Sintesi in categorie e priorità.
3. Formattazione finale in un'unica tabella.
</TASK>

<OUTPUT_FORMAT>
### Banca Dati Keyword per: "{keyword_principale}"

| Categoria Keyword | Elenco Keyword / Concetti / Domande (virgola) | Intento Prevalente | Fonte Dati Principale |
| :--- | :--- | :--- | :--- |
| **Keyword Principale** | [{keyword_principale}] | Informazionale | Input Utente |
| **Keyword Secondarie (Priorità Alta)** |  |  | Competitor / Correlate |
| **Keyword Secondarie (Priorità Media)** |  |  | Competitor / Correlate |
| **Entità Semantiche (Priorità Alta)** |  |  | Entità / Testi Competitor |
| **Entità Semantiche (Priorità Media)** |  |  | Entità / Testi Competitor |
| **Domande degli Utenti (H3/FAQ)** |  |  | PAA / Correlate |
</OUTPUT_FORMAT>
"""
    with st.spinner("Generazione Banca Dati Keyword Strategiche..."):
        resp_banca = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[prompt_banca]
        )
    st.subheader(f"Banca Dati Keyword per: \"{keyword_principale}\"")
    st.markdown(resp_banca.text, unsafe_allow_html=True)
