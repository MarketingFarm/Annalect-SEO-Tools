import streamlit as st
from streamlit_quill import st_quill
import requests
from urllib.parse import urlparse, urlunparse
import pandas as pd
from google_genai import Client

# --- CONFIG DATAFORSEO & GEMINI ---
DFS_USERNAME = st.secrets["dataforseo"]["username"]
DFS_PASSWORD = st.secrets["dataforseo"]["password"]
auth = (DFS_USERNAME, DFS_PASSWORD)
GEMINI_API_KEY = st.secrets["gemini"]["api_key"]
genai = Client()

def get_countries():
    """Recupera i paesi da DataForSEO"""
    url = 'https://api.dataforseo.com/v3/serp/google/locations'
    resp = requests.get(url, auth=auth)
    resp.raise_for_status()
    locs = resp.json()['tasks'][0]['result']
    return sorted([l['location_name'] for l in locs if l.get('location_type')=='Country'])

@st.cache_data(show_spinner=False)
def get_languages():
    """Recupera le lingue da DataForSEO"""
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

# CSS per tabelle
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

    # Prompt 1: leggibilità, intent, tone, sentiment
    prompt1 = f"""
## PROMPT: ANALISI SINTETICA AVANZATA DEL CONTENUTO ##
**RUOLO:** Agisci come un analista SEO e Content Strategist esperto.
**CONTESTO:** Analizza i testi dei competitor per una query.
**OBIETTIVO:** Fornisci UNA tabella Markdown sintetica con:
Livello Leggibilità | Search Intent | Tone of Voce | Tone of Voice (Approfondimento) | Sentiment Medio

**TESTI:**
{joined_texts}

**OUTPUT:** Esclusivamente la tabella con header e dati, nulla più.
| Livello Leggibilità | Search Intent | Tone of Voce | Tone of Voice (Approfondimento) | Sentiment Medio |
| :--- | :--- | :--- | :--- | :--- |
"""
    resp1 = genai.chat.create(messages=[{"content":prompt1,"author":"user"}], model="gemini-proto")
    st.markdown(resp1.last.reply.content)

    # Prompt 2: entità e content gap
    prompt2 = f"""
## ANALISI COMPETITIVA E CONTENT GAP ##
**RUOLO:** Analista SEO d'élite.
**CONTESTO:** Analisi testi per individuare entità e gap.

**TESTI:**
{joined_texts}

1. Identifica Entità Centrale.
2. Definisci Search Intent Primario.
3. Crea due tabelle Markdown:

### TABELLA 1: ENTITÀ FONDAMENTALI (Common Ground Analysis)
| Entità | Rilevanza Strategica | Azione per il Mio Testo |
| :--- | :--- | :--- |

### TABELLA 2: ENTITÀ MANCANTI (Content Gap Opportunity)
| Entità da Aggiungere | Motivazione dell'Inclusione | Azione SEO Strategica |
| :--- | :--- | :--- |
"""
    resp2 = genai.chat.create(messages=[{"content":prompt2,"author":"user"}], model="gemini-proto")
    st.markdown(resp2.last.reply.content)
