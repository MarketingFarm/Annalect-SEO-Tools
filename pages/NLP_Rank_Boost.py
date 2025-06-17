import os
import io
import re
import json
import streamlit as st
import requests
import pandas as pd
from urllib.parse import urlparse, urlunparse
from streamlit_quill import st_quill
from google import genai
from reportlab.platypus import SimpleDocTemplate, Paragraph, Preformatted
from reportlab.lib.styles import getSampleStyleSheet

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
        for i in range(1, count + 1):
            competitor_texts.append(st.session_state.get(f"comp_quill_{i}", ""))

# Bottone di avvio, usa on_click per chiudere l’expander immediatamente
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

    # --- STEP NLU: analisi strategica e gap di contenuto ---
    separator = "\n\n--- SEPARATORE TESTO ---\n\n"
    joined_texts = separator.join(competitor_texts)

    prompt_strategica = f"""
## PROMPT: NLU Semantic Content Intelligence ##

**PERSONA:** Agisci come un **Lead SEO Strategist** con 15 anni di esperienza nel posizionare contenuti in settori altamente competitivi. Il tuo approccio è data-driven, ossessionato dall'intento di ricerca e focalizzato a identificare le debolezze dei competitor per creare contenuti dominanti. Pensa in termini di E-E-A-T, topic authority e user journey.

**CONTESTO:** Ho estratto il contenuto testuale completo delle pagine top-ranking su Google per una query strategica. Il mio obiettivo non è solo eguagliare questi contenuti, ma surclassarli identificando le loro caratteristiche comuni e, soprattutto, le loro lacune.

**OBIETTIVO FINALE:** Esegui una procedura in una singola fase per fornirmi un'analisi comparativa.
1.  **FASE 1: ANALISI COMPARATIVA.** Analizza tutti i testi forniti e aggrega i risultati in una SINGOLA tabella Markdown di sintesi. La tabella deve riflettere la tendenza predominante o la media.

**TESTI DEI COMPETITOR DA ANALIZZARE:**
<TESTI>
{joined_texts}
</TESTI>

---
### **FASE 1: ISTRUZIONI PER LA TABELLA DI ANALISI**

Compila la seguente tabella. Per ogni colonna, analizza TUTTI i testi e sintetizza il risultato. Se noti forti divergenze, segnalale (es. "Misto: 60% Informale, 40% Formale").

| Caratteristica SEO              | Analisi Sintetica                                                     | Giustificazione e Dettagli                                                                 |
| :------------------------------ | :-------------------------------------------------------------------- | :----------------------------------------------------------------------------------------- |
| **Search Intent Primario**      | `[Informazionale, Commerciale, ecc.]`                                  | `[Spiega perché, es: "L'utente cerca definizioni e guide, non vuole ancora comprare."]`    |
| **Search Intent Secondario**    | `[Informazionale, Commerciale, ecc. o "Nessuno"]`                       | `[Spiega il secondo livello di bisogno, es: "Dopo aver capito 'cos'è', l'utente confronta soluzioni."]` |
| **Target Audience & Leggibilità**| `[B2B Esperto, B2C Principiante, Generalista, ecc.]`                  | `[Stima il livello (es: "Linguaggio semplice, per non addetti ai lavori") e il target.]`    |
| **Tone of Voice (ToV)**         | `[Es: "Didattico e professionale", "Empatico e rassicurante"]`         | `[Elenca 3 aggettivi chiave che catturano l'essenza del ToV, es: "autorevole, chiaro, pragmatico".]` |
| **Segnali E-E-A-T**             | `[Deboli / Medi / Forti]`                                             | `[Elenca i segnali trovati, es: "Citazioni di esperti, dati originali, biografia autore, casi studio, link a fonti autorevoli."]` |
| **Angolo del Contenuto**        | `[Es: "Guida definitiva step-by-step", "Analisi comparativa basata su dati", "Elenco curato di risorse"]` | `[Descrive il "gancio" principale usato per attrarre il lettore.]`        |

OUTPUT: Genera **ESCLUSIVAMENTE** la tabella Markdown con la struttura qui sopra, iniziando dalla riga dell’header e **senza** alcuna introduzione o testo aggiuntivo.
"""
    with st.spinner("Semantic Content Analysis with NLU..."):
        resp1 = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[prompt_strategica]
        )
    st.subheader("Search Intent & Content Analysis with NLU")
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

### TABELLA 1: Common Ground Analysis
| Entità | Rilevanza Strategica | Azione SEO Strategica |
| :--- | :--- | :--- |

### TABELLA 2: Content Gap Opportunity
| Entità da Aggiungere | Motivazione dell'Inclusione | Azione SEO Strategica |
| :--- | :--- | :--- |

OUTPUT: Genera **ESCLUSIVAMENTE** le due tabelle Markdown con la struttura qui sopra, iniziando dalla riga dell’header e **senza** alcuna introduzione o testo aggiuntivo.
"""
    with st.spinner("Entity & Semantic Gap Extraction..."):
        resp2 = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[prompt_competitiva]
        )
    # Estrazione robusta delle tabelle Markdown con regex
    resp2_text = resp2.text or ""
    pattern = r"(\|[^\n]+\n(?:\|[^\n]+\n?)+)"
    table_blocks = re.findall(pattern, resp2_text)
    if len(table_blocks) >= 2:
        table1_entities = table_blocks[0].strip()
        table2_gaps = table_blocks[1].strip()
        st.subheader("Semantic Common Ground Analysis")
        st.markdown(table1_entities, unsafe_allow_html=True)
        st.subheader("Semantic Content Gap Opportunity")
        st.markdown(table2_gaps, unsafe_allow_html=True)
    else:
        st.subheader("Errore nell'estrazione delle tabelle NLU")
        st.error("Non sono state trovate due tabelle nel testo restituito da Gemini. Ecco il testo completo:")
        st.text(resp2_text)
        table1_entities = ""
        table2_gaps = ""

    # --- STEP BANCA DATI KEYWORD STRATEGICHE ---
    keyword_principale = query
    table3_related_searches = pd.DataFrame({'Query Correlata': related}).to_markdown(index=False)
    table4_paa = pd.DataFrame({'Domanda': paa_list}).to_markdown(index=False)

    prompt_bank = f"""
## PROMPT: BANCA DATI KEYWORD STRATEGICHE ##

**PERSONA:** Agisci come un **Semantic SEO Data-Miner**, un analista d'élite il cui unico scopo è estrarre e classificare l'intero patrimonio di keyword di una SERP. Sei un veterano della keyword research che possiede tutti i dati statistici e storici delle varie keywords di Google. Il tuo superpotere è trasformare dati grezzi e disordinati in una "banca dati" di keyword pulita e prioritaria.  
* **Keyword Principale:** {keyword_principale}  
* **Country:** {country}  
* **Lingua:** {language}  
* **Testi Completi dei Competitor:** {joined_texts}  
* **Tabella 1: Entità Principali Estratte dai Competitor:**  
{table1_entities}  
* **Tabella 2: Entità Mancanti / Content Gap:**  
{table2_gaps}  
* **Tabella 3: Ricerche Correlate dalla SERP:**  
{table3_related_searches}  
* **Tabella 4: People Also Ask (PAA) dalla SERP:**  
{table4_paa}

---

<TASK>
**PROCESSO DI ESECUZIONE (In ordine rigoroso):**

1. **Analisi e Classificazione:** Analizza e correla tutti i dati per identificare ogni keyword, concento e domande. Assegna a ciascuna una tipologia e una priorità strategica e restituisci solo quelle che hanno alti volumi di ricerca, rilevanza semantica con l'argomento e una priorità strategica elevata.
2. **Aggregazione e Sintesi:** Raggruppa tutti gli elementi identificati nelle categorie richieste dal formato di output.
3. **Formattazione dell'Output:** Produci l'output finale nell'unica tabella specificata, seguendo queste regole di formattazione:
    * Usa la virgola come separatore per le liste.
    * **IMPORTANTE:** Scrivi tutte le keyword e i concetti in minuscolo. Fai eccezione solo per la lettera iniziale delle "Domande degli Utenti", che deve essere maiuscola.

</TASK>

<OUTPUT_FORMAT>
### Semantic Keyword Mining with NLP

| Categoria Keyword                 | Keywords / Concetti / Domande           | Intento Prevalente           |
| :-------------------------------- | :-------------------------------------- | :---------------------------- |
| **Keyword Principale**            | `{keyword_principale.lower()}`          | _(inserisci intento primario)_|
| **Keyword Secondarie**     | _(elenca keyword secondarie più importanti, non inserire in questa riga la keyword principale se già presente)_      | _(Informazionale / Commerciale ecc.)_|
| **LSI Keywords**| _(elenca le migliori Keywords LSI)_                     | _(Supporto all'intento)_      |
| **Domande degli Utenti (FAQ)**    | _(elenca domande, prima lettera maiuscola)_| _(Informazionale (Specifico))_|
</OUTPUT_FORMAT>
"""
    with st.spinner("Semantic Keyword Mining..."):
        resp3 = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[prompt_bank]
        )

    # --- Estrazione e rendering della tabella di Semantic Keyword Mining ---
    resp3_text = resp3.text or ""
    table_mining = None

    # Prima provo con la regex multiline
    regex = r"(\|[^\n]+\n\|[^\n]+\n(?:\|.*\n)+)"
    match = re.search(regex, resp3_text + "\n", re.MULTILINE)
    if match:
        table_mining = match.group(1).strip()
    else:
        # fallback: parsing manuale se tutto in una linea
        if "| Categoria Keyword" in resp3_text:
            parts = resp3_text.split("|")[1:]
            rows = []
            for i in range(0, len(parts), 4):
                if i + 2 < len(parts):
                    f1 = parts[i].strip()
                    f2 = parts[i+1].strip()
                    f3 = parts[i+2].strip()
                    rows.append(f"| {f1} | {f2} | {f3} |")
            if rows:
                header = rows[0]
                alignment = "| :-------------------------------- | :-------------------------------------- | :---------------------------- |"
                table_mining = "\n".join([header, alignment] + rows[1:])

    st.subheader("Semantic Keyword Mining with NLP")
    if table_mining:
        st.markdown(table_mining, unsafe_allow_html=True)
    else:
        st.markdown(resp3_text, unsafe_allow_html=True)

    # --- Pulsanti Reset, Esporta PDF, Download JSON ---
    export_data = {
        "query": query,
        "country": country,
        "language": language,
        "num_competitor": count,
        "competitor_texts": competitor_texts,
        "organic": data,
        "people_also_ask": paa_list,
        "related_searches": related,
        "analysis_strategica": resp1.text,
        "common_ground": table1_entities,
        "content_gap": table2_gaps,
        "keyword_mining": table_mining or resp3_text
    }
    export_json = json.dumps(export_data, ensure_ascii=False, indent=2)

    # Genera PDF
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer)
    styles = getSampleStyleSheet()
    flowables = [
        Paragraph("Analisi SEO Competitiva Multi-Step", styles['Title']),
        Preformatted(export_json, styles['Code'])
    ]
    doc.build(flowables)
    pdf_bytes = pdf_buffer.getvalue()

    # Mostra i pulsanti
    col_reset, col_pdf, col_json = st.columns(3)
    with col_reset:
        if st.button("Reset"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.experimental_rerun()
    with col_pdf:
        st.download_button("Esporta il Report", data=pdf_bytes, file_name="report.pdf", mime="application/pdf")
    with col_json:
        st.download_button("Download (json)", data=export_json, file_name="data.json", mime="application/json")
