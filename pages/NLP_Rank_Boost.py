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

# --- CONFIG GEMINI / VERTEX AI ---
# Assicurati che la API key di Gemini sia configurata come environment variable
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    # Fallback per lo sviluppo locale se usi st.secrets
    try:
        genai.configure(api_key=st.secrets["gemini"]["api_key"])
    except (KeyError, AttributeError):
        st.error("API Key di Gemini non trovata. Impostala come environment variable o in st.secrets.")
        st.stop()


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
                competitor_texts.append(st_quill("", key=f"comp_quill_{idx}", html=False)) # Usiamo il testo puro
            idx += 1

# Avvia Analisi
if st.button("🚀 Avvia l'Analisi"):
    # Validazione input
    if not (query and country and language and contesto and tipologia):
        st.error("Tutti i campi (Query, Country, Lingua, Contesto, Tipologia) sono obbligatori.")
        st.stop()
    if not any(competitor_texts):
         st.error("Devi inserire il testo di almeno un competitor per procedere con l'analisi NLU.")
         st.stop()


    # --- STEP 1: SERP SCRAPING E TABELLE ---
    st.header("Step 1: Analisi della SERP")
    with st.spinner("Recupero i dati dalla SERP di Google..."):
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
    st.markdown("---")

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
            st.dataframe(df_paa, use_container_width=True)
        else:
            st.info("Nessuna sezione PAA trovata.")
    with col_rel:
        st.subheader("Ricerche Correlate")
        if related:
            df_rel = pd.DataFrame({'Query Correlata': related})
            st.dataframe(df_rel, use_container_width=True)
        else:
            st.info("Nessuna sezione Ricerche correlate trovata.")
    st.markdown("---")


    # --- STEP 2: NLU - ANALISI QUALITATIVA E COMPETITIVA ---
    st.header("Step 2: Analisi NLU dei Competitor")
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    
    # Filtra solo i testi non vuoti
    active_competitor_texts = [text for text in competitor_texts if text and text.strip()]
    joined_texts = "\n\n---\n\n".join(active_competitor_texts)

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
    
    with st.spinner("Eseguo analisi qualitativa (leggibilità, intent, tone, sentiment)..."):
        resp1 = model.generate_content([prompt_sintetica])
    st.subheader("Sintesi Qualitativa dei Contenuti Competitor")
    st.markdown(resp1.text, unsafe_allow_html=True)
    st.markdown("---")

    prompt_competitiva = f"""
## ANALISI COMPETITIVA E CONTENT GAP ##
**RUOLO:** Agisci come un analista SEO d'élite, specializzato in analisi semantica competitiva.
**CONTESTO:** Obiettivo: superare i primi competitor per la keyword target. Analizza i loro testi.
**COMPITO:** Analizza i testi competitor:
---
{joined_texts}
---
1. Identifica l'**Entità Centrale** condivisa da tutti i testi.
2. Definisci il **Search Intent Primario** a cui i competitor rispondono.
3. Crea DUE tabelle Markdown separate:
### TABELLA 1: ENTITÀ FONDAMENTALI (Common Ground Analysis)
| Entità | Rilevanza Strategica | Azione per il Mio Testo |
| :--- | :--- | :--- |
### TABELLA 2: ENTITÀ MANCANTI (Content Gap Opportunity)
| Entità da Aggiungere | Motivazione dell'Inclusione | Azione SEO Strategica |
| :--- | :--- | :--- |
Mantieni solo le due tabelle, con markdown valido e separate da una linea vuota.
"""
    with st.spinner("Identifico entità fondamentali e content gap..."):
        resp2 = model.generate_content([prompt_competitiva])

    # Splitting robusto per le due tabelle markdown
    tables_from_resp2 = [blk.strip() for blk in resp2.text.split('###') if blk.strip().startswith("|")]
    
    # Controllo per assicurarsi che l'output sia corretto
    if len(tables_from_resp2) >= 2:
        table1_entities = tables_from_resp2[0]
        table2_gaps = tables_from_resp2[1]
        st.subheader("Entità Fondamentali (Common Ground Analysis)")
        st.markdown(table1_entities, unsafe_allow_html=True)
        st.subheader("Entità Mancanti (Content Gap Opportunity)")
        st.markdown(table2_gaps, unsafe_allow_html=True)
        st.markdown("---")
    else:
        st.error("L'analisi delle entità e dei content gap non ha prodotto i risultati attesi. Riprova o modifica i testi dei competitor.")
        st.write("Output ricevuto dal modello:")
        st.text(resp2.text)
        st.stop()


    # --- NUOVO STEP 3: SEO STRATEGY E GENERAZIONE KEYWORD ---
    st.header("Step 3: Strategia SEO e di Contenuto")
    
    # Preparazione dati PAA e Correlate in formato Markdown per il prompt
    paa_markdown = df_paa.to_markdown(index=False) if paa_list else "Nessuna domanda 'People Also Ask' trovata."
    related_markdown = df_rel.to_markdown(index=False) if related else "Nessuna 'Ricerca Correlata' trovata."

    prompt_strategia = f"""
## ANALISI SEO STRATEGICA E GENERAZIONE KEYWORD ##

**RUOLO:** Assumi il ruolo di un SEO Strategist di livello mondiale, con specializzazione in SEO semantica, analisi dell'intento di ricerca e data-driven content strategy. La tua missione è quella di sezionare il panorama competitivo e i dati della SERP per costruire una strategia di keyword e contenuti inattaccabile.

**OBIETTIVO PRIMARIO:** Elaborare una strategia completa e attuabile che mi permetta di creare un contenuto (testo) oggettivamente superiore a quello dei competitor. L'obiettivo non è solo inserire keyword, ma raggiungere una rilevanza e un'autorità tematica (topical authority) schiaccianti per dominare la SERP per la keyword principale.

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

**COMPITO DETTAGLIATO (Esegui in ordine):**

1.  **Analisi dell'Intento di Ricerca (Search Intent):** Basandoti su tutti i dati forniti (keyword, PAA, correlate, tipologia di contenuto dei competitor), definisci l'intento di ricerca primario (es. informativo, commerciale, transazionale, di navigazione) e gli eventuali intenti secondari. Questa analisi è il fondamento di tutta la strategia.

2.  **Sintesi e Correlazione dei Dati:** Analizza e metti in relazione TUTTE le fonti di dati. Ad esempio, collega le domande dei PAA alle entità mancanti per trovare nuove sezioni da creare, o usa le ricerche correlate per dare un contesto più ampio alle entità principali.

3.  **Generazione della Strategia Keyword e Contenutistica:** Produci l'output finale organizzando le informazioni nelle seguenti tabelle chiare e distinte. Sii preciso e strategico.

---

**FORMATO DI OUTPUT OBBLIGATORIO:**

**(Inizia sempre con questo sommario)**

**Executive Summary:**
* **Keyword Principale:** {query}
* **Intento di Ricerca Primario:** [Indica l'intento primario che hai identificato]
* **Intenti di Ricerca Secondari:** [Elenca gli intenti secondari, se presenti]
* **Angolo Strategico Raccomandato:** [Descrivi brevemente l'approccio unico che il nuovo contenuto dovrebbe adottare per superare i competitor, basandoti sui dati.]

**Tabella 1: Architettura delle Keyword**

| Categoria | Keyword / Concetto / Domanda | Fonte Dati Principale | Azione Strategica / Valore Aggiunto |
| :--- | :--- | :--- | :--- |
| **Keyword Principale (Focus)** | [La keyword principale esatta da usare] | Input Utente | Inserire nel Titolo (H1), nel primo paragrafo, nell'URL e in modo naturale nel testo. È il fulcro del contenuto. |
| **Cluster di Keyword Secondarie** | [Elenco puntato di 3-5 keyword secondarie che coprono sotto-argomenti cruciali] | Competitor / Correlate | Usare per creare sottotitoli (H2, H3) e sezioni dedicate. Ognuna risponde a un micro-intento specifico. |
| **Entità e Concetti Correlati (LSI)**| [Elenco puntato delle entità/concetti chiave per costruire il contesto semantico] | Entità / Testi Competitor| Spargere naturalmente nel testo per dimostrare a Google la profondità della conoscenza sull'argomento. |
| **Domande degli Utenti (da PAA)**| [Elenco puntato delle domande più pertinenti tratte dai PAA] | PAA / Correlate | Creare una sezione FAQ o integrare le risposte direttamente nei paragrafi pertinenti per catturare featured snippet. |

<br>

**Tabella 2: Opportunità Strategiche (Content Gaps)**

| Opportunità di Gap / Angolo d'Attacco | Dati a Supporto (da quale fonte) | Azione Raccomandata per il Contenuto |
| :--- | :--- | :--- |
| [Descrivi la prima opportunità. Es: "Approfondire l'aspetto X, ignorato dai competitor"] | Entità Mancanti / PAA | Creare un nuovo paragrafo/sezione intitolato "Perché X è importante" e rispondere alle domande correlate. |
| [Descrivi la seconda opportunità. Es: "Trattare il topic Y, presente solo nelle ricerche correlate"] | Ricerche Correlate | Introdurre un capitolo che confronti Y con l'argomento principale, per intercettare un'audience più ampia. |
| [Descrivi la terza opportunità. Es: "Rispondere alla domanda Z, non coperta esaustivamente"] | PAA / Analisi Testi | Dedicare una spiegazione dettagliata con esempi pratici alla domanda Z, posizionandosi come la risorsa più completa. |
"""
    
    with st.spinner("Elaboro la strategia SEO e contenutistica finale..."):
        resp3 = model.generate_content([prompt_strategia])
        
    st.subheader("Piano d'Azione Strategico")
    st.markdown(resp3.text, unsafe_allow_html=True)
    st.success("Analisi completata!")
