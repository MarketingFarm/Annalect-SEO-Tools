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

# === SESSION STATE PER CHIUSURA EXPANDER DOPO ANALISI ===
if 'analysis_started' not in st.session_state:
    st.session_state['analysis_started'] = False

# === UI PRINCIPALE ===
st.title("Analisi SEO Competitiva Multi-Step")
st.markdown("Questo tool esegue analisi SEO integrando SERP scraping e NLU.")
st.divider()

# Step 1 inputs: query, country, language, contesto, tipologia
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

# Dropdown numero competitor appena dopo i parametri di ricerca
num_opts = [""] + list(range(1, 6))
num_comp = st.selectbox("Numero di competitor da analizzare", num_opts, key="num_competitor")
count = int(num_comp) if isinstance(num_comp, int) else 0

# Expander per i testi dei competitor
competitor_texts = []
with st.expander("Testi dei Competitor", expanded=not st.session_state['analysis_started']):
    idx = 1
    for _ in range((count + 1) // 2):
        cols_pair = st.columns(2)
        for col in cols_pair:
            if idx <= count:
                with col:
                    st.markdown(f"**Testo Competitor #{idx}**")
                    competitor_texts.append(st_quill("", key=f"comp_quill_{idx}"))
                idx += 1

# Bottone di avvio
if st.button("🚀 Avvia l'Analisi"):
    st.session_state['analysis_started'] = True

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
## PROMPT: ANALISI STRATEGICA E DI GAP DI CONTENUTO ##

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
| **Angolo del Contenuto**        | `[Es: "Guida definitiva step-by-step", "Analisi comparativa basata su dati", "Elenco curato di risorse"]` | `[Descrive il "gancio" principale usato per attrarre il lettore.]`        |
| **Cluster di Topic / Entità**   | `[Elenca i 3-5 sotto-argomenti o entità più comuni]`                   | `[Esempi di concetti ricorrenti che dimostrano la completezza, es: "Prezzi, Vantaggi, Alternative A, Normativa XYZ".]` |
| **Segnali E-E-A-T**             | `[Deboli / Medi / Forti]`                                             | `[Elenca i segnali trovati, es: "Citazioni di esperti, dati originali, biografia autore, casi studio, link a fonti autorevoli."]` |

OUTPUT: Genera **ESCLUSIVAMENTE** la tabella Markdown con la struttura qui sopra, iniziando dalla riga dell’header e **senza** alcuna introduzione o testo aggiuntivo.
"""

    with st.spinner("Analisi strategica e gap di contenuto..."):
        resp1 = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[prompt_strategica]
        )

    st.subheader("Analisi Strategica e GAP di Contenuto")
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
    keyword_principale = query
    table1_entities = tables[0]
    table2_gaps = tables[1]
    table3_related_searches = pd.DataFrame({'Query Correlata': related}).to_markdown(index=False)
    table4_paa = pd.DataFrame({'Domanda': paa_list}).to_markdown(index=False)

    prompt_bank = f"""
## PROMPT: BANCA DATI KEYWORD STRATEGICHE ##

**PERSONA:** Agisci come un **Semantic SEO Data-Miner**, un analista d'élite il cui unico scopo è estrarre e classificare l'intero patrimonio di keyword di una SERP. Il tuo superpotere è trasformare dati grezzi e disordinati in una "banca dati" di keyword pulita e priorizzata: la base strategica indispensabile per armare un team di contenuti e costruire un pezzo definitivo, progettato per dominare la SERP superando i competitor attuali.

**OBIETTIVO FINALE:** Utilizzare l'insieme di dati forniti per generare un'unica e sintetica **banca dati di keyword strategiche**. L'output deve aggregare tutti i termini di ricerca in categorie chiare basate sulla loro tipologia e priorità, fornendo una risorsa densa e di rapida consultazione.

---

<INPUTS>
* **Keyword Principale:** {keyword_principale}
* **Country:** {country}
* **Lingua:** {language}
* **Contesto del Contenuto:** {contesto}
* **Tipologia di Contenuto:** {tipologia}
* **Testi Completi dei Competitor:** {joined_texts}
* **Tabella 1: Entità Principali Estratte dai Competitor:** 
{table1_entities}
* **Tabella 2: Entità Mancanti / Content Gap:** 
{table2_gaps}
* **Tabella 3: Ricerche Correlate dalla SERP:** 
{table3_related_searches}
* **Tabella 4: People Also Ask (PAA) dalla SERP:** 
{table4_paa}
</INPUTS>

---

<TASK>
**PROCESSO DI ESECUZIONE (In ordine rigoroso):**

1. **Analisi e Classificazione:** Analizza e correla tutti i dati per identificare ogni keyword, concetto e domanda. Assegna a ciascuna una tipologia e una priorità strategica (Alta, Media).
2. **Aggregazione e Sintesi:** Raggruppa tutti gli elementi identificati nelle categorie richieste dal formato di output.
3. **Formattazione dell'Output:** Produci l'output finale nell'unica tabella specificata, seguendo queste regole di formattazione:
    * Usa la virgola come separatore per le liste.
    * **IMPORTANTE:** Scrivi tutte le keyword e i concetti in minuscolo. Fai eccezione solo per la lettera iniziale delle "Domande degli Utenti", che deve essere maiuscola.

</TASK>

<OUTPUT_FORMAT>
### Banca Dati Keyword per: "{keyword_principale}"

| Categoria Keyword | Keywords / Concetti / Domande | Intento Prevalente |
| :--- | :--- | :--- |
| **Keyword Principale** | `{keyword_principale.lower()}` | _(inserisci intento primario)_ |
| **Keyword Secondarie (Priorità Alta)** | _(inserisci qui le keyword secondarie ALTE)_ | _(es: informazionale / commerciale)_ |
| **Keyword Secondarie (Priorità Media)** | _(inserisci qui le keyword secondarie MEDIE)_ | _(es: informazionale (pratico))_ |
| **Keyword Correlate e LSI (Priorità Alta)** | _(inserisci qui i termini correlati ALTI)_ | _(supporto all'intento)_ |
| **Keyword Correlate e LSI (Priorità Media)** | _(inserisci qui i termini correlati MEDI)_ | _(supporto all'intento)_ |
| **Domande degli Utenti (H3/FAQ)** | _(inserisci qui le domande, prima lettera maiuscola)_ | _(informazionale (specifico))_ |
"""
    with st.spinner("Generazione banca dati keyword..."):
        resp3 = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[prompt_bank]
        )
    st.subheader("Banca Dati Keyword Strategiche")
    st.markdown(resp3.text, unsafe_allow_html=True)
