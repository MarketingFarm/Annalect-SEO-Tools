import streamlit as st
from streamlit_quill import st_quill
import requests
from urllib.parse import urlparse, urlunparse

# --- CONFIG DATAFORSEO ---
# Credenziali via st.secrets
DFS_USERNAME = st.secrets["dataforseo"]["username"]
DFS_PASSWORD = st.secrets["dataforseo"]["password"]
auth = (DFS_USERNAME, DFS_PASSWORD)

@st.cache_data(show_spinner=False)
def get_countries():
    """Recupera la lista di paesi da DataForSEO"""
    url = 'https://api.dataforseo.com/v3/serp/google/locations'
    resp = requests.get(url, auth=auth)
    resp.raise_for_status()
    data = resp.json()
    locations = data['tasks'][0]['result']
    return sorted(
        loc['location_name']
        for loc in locations
        if loc.get('location_type') == 'Country'
    )

@st.cache_data(show_spinner=False)
def get_languages():
    """Recupera la lista di lingue da DataForSEO"""
    url = 'https://api.dataforseo.com/v3/serp/google/languages'
    resp = requests.get(url, auth=auth)
    resp.raise_for_status()
    data = resp.json()
    langs = data['tasks'][0]['result']
    return sorted(
        lang['language_name']
        for lang in langs
    )

# --- INIEZIONE CSS ---
st.markdown("""
<style>
button { background-color: #e63946 !important; color: white !important; }
table td { white-space: normal !important; }
</style>
""", unsafe_allow_html=True)

# Titolo e descrizione
st.title("Analisi SEO Competitiva Multi-Step")
st.markdown("Questo tool esegue analisi SEO integrando SERP scraping e NLU.")
st.divider()

# Step 1: Parametri di base
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    query = st.text_input("Query", key="query", placeholder="Inserisci la query")
with col2:
    countries = get_countries()
    country = st.selectbox("Country", [""] + countries, key="country")
with col3:
    all_langs = get_languages()
    language = st.selectbox(
        "Lingua",
        [""] + all_langs,
        key="language"
    )
with col4:
    contesti = ["", "E-commerce", "Blog / Contenuto Informativo"]
    contesto = st.selectbox("Contesto", contesti, key="contesto")
with col5:
    tip_map = {
        "E-commerce": ["Product Detail Page (PDP)", "Product Listing Page (PLP)"],
        "Blog / Contenuto Informativo": ["Articolo", "Pagina informativa"]
    }
    tipologie = tip_map.get(contesto, [])
    tipologia = st.selectbox(
        "Tipologia di Contenuto",
        [""] + tipologie,
        key="tipologia",
        disabled=(not tipologie)
    )

# Selezione numero competitor\st.markdown("---")
num_opts = [""] + list(range(1, 6))
num_comp = st.selectbox("Numero di competitor da analizzare", num_opts, key="num_competitor")
count = int(num_comp) if isinstance(num_comp, int) else 0

# Editor WYSIWYG dinamici (2 colonne per riga)
competitor_texts = []
idx = 1
for _ in range((count + 1) // 2):
    cols = st.columns(2)
    for col in cols:
        if idx <= count:
            with col:
                st.markdown(f"**Testo Competitor #{idx}**")
                content = st_quill("", key=f"comp_quill_{idx}")
            competitor_texts.append(content)
            idx += 1

# Pulsante di avvio analisi
action = st.button("🚀 Avvia l'Analisi")

# Ora st.session_state contiene tutti i valori per i passi successivi.
