import streamlit as st
from streamlit_quill import st_quill
import requests
from urllib.parse import urlparse, urlunparse
import pandas as pd

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

# Utility to clean URL
def clean_url(url: str) -> str:
    parsed = urlparse(url)
    cleaned = parsed._replace(query='', params='', fragment='')
    return urlunparse(cleaned)

# Fetch SERP data from DataForSEO
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

# Enhanced CSS for tables
st.markdown("""
<style>
/* Button */
button { background-color: #e63946 !important; color: white !important; }
/* Table styling */
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
/* Wrap text */
td { white-space: normal !important; }
/* Center length columns */
table th:nth-child(3), table td:nth-child(3),
table th:nth-child(5), table td:nth-child(5) {
  text-align: center !important;
}
</style>
""", unsafe_allow_html=True)

# UI setup
st.title("Analisi SEO Competitiva Multi-Step")
st.markdown("Questo tool esegue analisi SEO integrando SERP scraping e NLU.")
st.divider()

# Input parameters
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
    tipologia = st.selectbox("Tipologia di Contenuto", [""] + tip_map.get(contesto, []), key="tipologia")

st.markdown("---")
# Number of competitors
num_opts = [""] + list(range(1, 6))
num_comp = st.selectbox("Numero di competitor da analizzare", num_opts, key="num_competitor")
count = int(num_comp) if isinstance(num_comp, int) else 0

# Dynamic competitor editors
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

# Launch analysis
if st.button("🚀 Avvia l'Analisi"):
    # Validate required fields
    if not (query and country and language):
        st.error("Query, Country e Lingua sono obbligatori.")
        st.stop()

    # Fetch SERP
    result = fetch_serp(query, country, language)
    items = result.get('items', [])

    # Organic results top 10 with length columns and formatting
    organic = [it for it in items if it.get('type') == 'organic'][:10]
    data = []
    for it in organic:
        title = it.get('title') or it.get('link_title', '')
        desc = it.get('description') or it.get('snippet', '')
        data.append({
            'URL': f"<a href='{clean_url(it.get('link') or it.get('url',''))}' target='_blank'>{clean_url(it.get('link') or it.get('url',''))}</a>",
            'Meta Title': title,
            'Lunghezza Title': len(title),
            'Meta Description': desc,
            'Lunghezza Description': len(desc)
        })
    df_org = pd.DataFrame(data)
    # Styling: highlight title length 50-60, desc 120-160
    def title_style(val):
        return 'background-color: #d4edda' if 50 <= val <= 60 else 'background-color: #f8d7da'
    def desc_style(val):
        return 'background-color: #d4edda' if 120 <= val <= 160 else 'background-color: #f8d7da'
    styled_org = df_org.style.format({'URL': lambda u: u}) 
    styled_org = styled_org.set_properties(subset=['Lunghezza Title','Lunghezza Description'], **{'text-align':'center'})
    styled_org = styled_org.applymap(title_style, subset=['Lunghezza Title'])
    styled_org = styled_org.applymap(desc_style, subset=['Lunghezza Description'])
    st.subheader("Risultati Organici (top 10)")
    st.write(styled_org.to_html(escape=False), unsafe_allow_html=True)

    # People Also Ask and Related in two columns
    paa_list = []
    related = []
    for element in items:
        if element.get('type') == 'people_also_ask':
            paa_list = [q.get('title') for q in element.get('items', [])]
        if element.get('type') in ('related_searches', 'related_search'):
            for rel in element.get('items', []):
                if isinstance(rel, str): related.append(rel)
                else: related.append(rel.get('query') or rel.get('keyword'))
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
