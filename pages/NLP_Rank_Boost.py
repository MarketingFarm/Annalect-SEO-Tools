import streamlit as st
from streamlit_quill import st_quill
import requests
from urllib.parse import urlparse, urlunparse
import pandas as pd
from google import genai

# --- CONFIG DATAFORSEO & GEMINI ---
DFS_USERNAME = st.secrets["dataforseo"]["username"]
DFS_PASSWORD = st.secrets["dataforseo"]["password"]
auth = (DFS_USERNAME, DFS_PASSWORD)
GEMINI_API_KEY = st.secrets["gemini"]["api_key"]
genai = Client(api_key=GEMINI_API_KEY)

# --- FUNZIONI DATAFORSEO ---
def get_countries():
    url = 'https://api.dataforseo.com/v3/serp/google/locations'
    resp = requests.get(url, auth=auth)
    resp.raise_for_status()
    locs = resp.json()['tasks'][0]['result']
    return sorted([l['location_name'] for l in locs if l.get('location_type')=='Country'])

@st.cache_data(show_spinner=False)
def get_languages():
    url = 'https://api.dataforseo.com/v3/serp/google/languages'
    resp = requests.get(url, auth=auth)
    resp.raise_for_status()
    langs = resp.json()['tasks'][0]['result']
    return sorted([l['language_name'] for l in langs])

# Utility pulizia URL
def clean_url(url: str) -> str:
    p = urlparse(url)
    return urlunparse(p._replace(query='', params='', fragment=''))

# Fetch SERP da DataForSEO
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

# CSS per tabelle e formattazioni
st.markdown("""
<style>
button{background:#e63946!important;color:#fff!important}
table{border-collapse:collapse;width:100%}
table,th,td{border:1px solid #ddd!important;padding:8px!important;font-size:14px}
th{background:#f1f1f1!important;position:sticky;top:0;z-index:1}
td{white-space:normal!important}
/* Centra colonne lunghezze */
table th:nth-child(3),table td:nth-child(3),table th:nth-child(5),table td:nth-child(5){text-align:center!important}
</style>
""", unsafe_allow_html=True)

# Titolo e descrizione
st.title("Analisi SEO Competitiva Multi-Step")
st.markdown("Questo tool integra scraping SERP, analisi NLU e content gap.")
st.divider()

# Input principali
c1,c2,c3,c4,c5 = st.columns(5)
with c1:
    query = st.text_input("Query")
with c2:
    country = st.selectbox("Country", [""] + get_countries())
with c3:
    language = st.selectbox("Lingua", [""] + get_languages())
with c4:
    contesti = ["", "E-commerce", "Blog / Contenuto Informativo"]
    contesto = st.selectbox("Contesto", contesti)
with c5:
    tip_map = {"E-commerce":["PDP","PLP"], "Blog / Contenuto Informativo":["Articolo","Pagina informativa"]}
    tipologia = st.selectbox("Tipologia di Contenuto", [""] + tip_map.get(contesto, []))

st.markdown("---")
# Editor testi competitor
num_opts = [""] + list(range(1,6))
num_comp = st.selectbox("Numero di competitor da analizzare", num_opts)
count = int(num_comp) if isinstance(num_comp,int) else 0
texts = []
idx = 1
for _ in range((count+1)//2):
    cols = st.columns(2)
    for col in cols:
        if idx <= count:
            with col:
                st.markdown(f"**Testo Competitor #{idx}**")
                texts.append(st_quill("", key=f"comp{idx}"))
            idx += 1

# Avvia analisi
if st.button("🚀 Avvia l'Analisi"):
    if not(query and country and language):
        st.error("Query, Country e Lingua obbligatori.")
        st.stop()

    # Scraping SERP
    res = fetch_serp(query,country,language)
    items = res.get('items',[])

    # Risultati organici top10
    organic = [it for it in items if it.get('type')=='organic'][:10]
    rows = []
    for it in organic:
        title = it.get('title') or it.get('link_title','')
        desc = it.get('description') or it.get('snippet','')
        url = clean_url(it.get('link') or it.get('url',''))
        rows.append({
            'URL': f"<a href='{url}' target='_blank'>{url}</a>",
            'Meta Title': title,
            'Lunghezza Title': len(title),
            'Meta Description': desc,
            'Lunghezza Description': len(desc)
        })
    df_org = pd.DataFrame(rows)
    def style_title(v): return 'background:#d4edda' if 50<=v<=60 else 'background:#f8d7da'
    def style_desc(v): return 'background:#d4edda' if 120<=v<=160 else 'background:#f8d7da'
    styled = df_org.style.format({'URL':lambda u:u}) 
    styled = styled.set_properties(subset=['Lunghezza Title','Lunghezza Description'], **{'text-align':'center'})
    styled = styled.applymap(style_title, subset=['Lunghezza Title']).applymap(style_desc, subset=['Lunghezza Description'])
    st.subheader("Risultati Organici (top 10)")
    st.write(styled.to_html(escape=False), unsafe_allow_html=True)

    # PAA e Ricerche correlate
    paa=[]; related=[]
    for e in items:
        if e.get('type')=='people_also_ask': paa=[q.get('title') for q in e.get('items',[])]
        if e.get('type') in ('related_searches','related_search'):
            for r in e.get('items',[]):
                related.append(r if isinstance(r,str) else r.get('query') or r.get('keyword'))
    col1,col2 = st.columns(2)
    with col1:
        st.subheader("People Also Ask")
        if paa: st.write(pd.DataFrame({'Domanda':paa}).to_html(index=False), unsafe_allow_html=True)
        else: st.write("Nessuna sezione PAA trovata.")
    with col2:
        st.subheader("Ricerche Correlate")
        if related: st.write(pd.DataFrame({'Query Correlata':related}).to_html(index=False), unsafe_allow_html=True)
        else: st.write("Nessuna sezione Ricerche correlate trovata.")

    # Preparazione testi per NLU
    joined_texts = "\n---\n".join(texts)

    # Prompt 1: Analisi Sintetica Avanzata del Contenuto
    prompt1 = f"""
## PROMPT: ANALISI SINTETICA AVANZATA DEL CONTENUTO ##

**RUOLO:** Agisci come un analista SEO e Content Strategist esperto. Il tuo compito è distillare le caratteristiche qualitative fondamentali da un insieme di testi dei competitor.

**CONTESTO:** Ho raccolto i testi delle pagine che si posizionano meglio in Google per una specifica query. Devo capire le loro caratteristiche comuni per creare un contenuto superiore.

**OBIETTIVO:** Analizza i testi forniti di seguito e compila UNA SINGOLA tabella Markdown di sintesi. La tabella deve rappresentare la media o la tendenza predominante riscontrata in TUTTI i testi. Analizzare i testi singolarmente, ma fornisci una visione d'insieme consolidata.

**TESTI DA ANALIZZARE:**
---
{joined_texts}
---

**ISTRUZIONI DETTAGLIATE PER LA COMPILAZIONE:**

1. **Livello Leggibilità:** Stima il pubblico di destinazione basandoti sulla complessità generale del linguaggio e dei concetti. Esempi: "Semplice, per un pubblico di principianti", "Intermedio, richiede una conoscenza di base dell'argomento", "Avanzato, per un pubblico di esperti o tecnici". Inserisci anche il target di destinazione (Generalista, B2C, B2B o più di uno).

2. **Search Intent:** Identifica l'intento di ricerca primario e prevalente che i testi soddisfano (es: Informazionale, Transazionale, Commerciale, Navigazionale). Fornisci solo la classificazione.

3. **Tone of Voce:** Definisci il tono di voce predominante nell'insieme dei testi. Sii specifico. Esempi: "Formale e accademico", "Informale e rassicurante", "Tecnico e didattico", "Entusiasta e promozionale", "Umoristico e coinvolgente".

4. **Tone of Voice (Approfondimento):** Fornisci tre aggettivi distinti che lo descrivono. Non ripetere un aggettivo già usato nel Tone of Voice.

5. **Sentiment Medio:** Valuta il sentiment generale (Positivo, Neutro, Negativo) e aggiungi una giustificazione estremamente concisa (massimo 10 parole) che spieghi il perché. Esempio: "Positivo, grazie all'uso di aggettivi entusiastici e focus sui beneficios".

**COMPITO FINALE:**
Genera come output **ESCLUSIVAMENTE** la tabella Markdown compilata con la tua analisi. Non aggiungere alcuna frase introduttiva, commento o conclusione. L'output deve iniziare direttamente con la riga dell'header della tabella.

| Livello Leggibilità | Search Intent | Tone of Voce | Tone of Voice (Approfondimento) | Sentiment Medio |
| :--- | :--- | :--- | :--- | :--- |
"""
    resp1 = genai.chat.create(messages=[{"content": prompt1, "author": "user"}], model="gemini-proto")
    st.markdown(resp1.last.reply.content, unsafe_allow_html=True)

    # Prompt 2: Analisi Competitiva e Content Gap
    prompt2 = f"""
## ANALISI COMPETITIVA E CONTENT GAP ##
**RUOLO:** Agisci come un analista SEO d'élite, specializzato in analisi semantica competitiva. La tua missione è "ingegneria inversa" del successo dei contenuti che si posizionano ai vertici di Google.

**CONTESTO:** Sto per scrivere o migliorare un testo e il mio obiettivo è superare i primi 3 competitor attualmente posizionati per la mia keyword target. Analizzerai i loro testi per darmi una mappa precisa delle entità che devo assolutamente trattare e delle opportunità (entità mancanti) che posso sfruttare per creare un contenuto oggettivamente più completo e autorevole.

**COMPITO:** Analizza i seguenti testi competitor:
---
{joined_texts}

1. Identifica e dichiara qual è l'**Argomento Principale Comune** o l'**Entità Centrale** condivisa da tutti i testi.
2. Basandoti su questo, definisci il **Search Intent Primario** a cui i competitor stanno rispondendo (es: "Confronto informativo tra prodotti", "Guida all'acquisto per principianti", "Spiegazione approfondita di un concetto").
3. Crea **due tabelle Markdown separate e distinte**, come descritto di seguito:

### TABELLA 1: ENTITÀ FONDAMENTALI (Common Ground Analysis)
| Entità | Rilevanza Strategica | Azione per il Mio Testo |
| :--- | :--- | :--- |

### TABELLA 2: ENTITÀ MANCANTI (Content Gap Opportunity)
| Entità da Aggiungere | Motivazione dell'Inclusione | Azione SEO Strategica |
| :--- | :--- | :--- |

Arricchisci la colonna "Entità" con esempi specifici tra parentesi.
Nella prima riga inserisci sempre l'entità principale.
Mantieni solo le due tabelle, con markdown valido e wrap del testo.
"""
    resp2 = genai.chat.create(messages=[{"content": prompt2, "author": "user"}], model="gemini-proto")
    st.markdown(resp2.last.reply.content, unsafe_allow_html=True)
