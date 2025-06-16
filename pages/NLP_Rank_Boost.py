import streamlit as st
from streamlit_quill import st_quill

# --- INIEZIONE CSS per stile pulsante rosso e wrap tabelle (esempio) ---
st.markdown("""
<style>
button {
  background-color: #e63946 !important;
  color: white !important;
}
/* wrap table cells */
table td {
  white-space: normal !important;
}
</style>
""", unsafe_allow_html=True)

# Titolo principale e descrizione
st.title("Analisi SEO Competitiva Multi-Step")
st.markdown("Questo tool ti aiuta a eseguire un'analisi SEO competitiva in più fasi, integrando scraping SERP, analisi NLU e molto altro.")
st.divider()

# Step 1: Input parametri di base
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    query = st.text_input("Query", key="query", placeholder="Inserisci la query di ricerca")
with col2:
    countries = ["", "Italy", "United States", "France", "Germany", "Spain"]
    country = st.selectbox("Country", countries, key="country")
with col3:
    lang_map = {
        "Italy": ["Italiano"],
        "United States": ["English"],
        "France": ["Français"],
        "Germany": ["Deutsch"],
        "Spain": ["Español"]
    }
    languages = lang_map.get(st.session_state.get("country", ""), [])
    language = st.selectbox("Lingua", [""] + languages, key="language", disabled=(not languages))
with col4:
    contesti = ["", "E-commerce", "Blog / Contenuto Informativo"]
    contesto = st.selectbox("Contesto", contesti, key="contesto")
with col5:
    tip_map = {
        "E-commerce": ["Product Detail Page (PDP)", "Product Listing Page (PLP)"],
        "Blog / Contenuto Informativo": ["Articolo", "Pagina informativa"]
    }
    tipologie = tip_map.get(st.session_state.get("contesto", ""), [])
    tipologia = st.selectbox(
        "Tipologia di Contenuto",
        [""] + tipologie,
        key="tipologia",
        disabled=(not tipologie)
    )

# Selezione numero di competitor e editor dinamici
st.markdown("---")
num_competitor = st.selectbox(
    "Numero di competitor da analizzare", 
    options=[i for i in range(1, 6)],
    index=4,
    key="num_competitor"
)

# Creazione editor in due colonne
competitor_texts = []
idx = 1
for row_start in range(1, num_competitor + 1, 2):
    cols = st.columns(2)
    for col in cols:
        if idx <= num_competitor:
            content = col.quill_editor(label=f"Editor Competitor {idx}", key=f"comp_quill_{idx}")
            competitor_texts.append(content)
            idx += 1

# Pulsante di avvio analisi
action = st.button("🚀 Avvia l'Analisi")

# session_state contiene: query, country, language, contesto, tipologia, num_competitor e comp_quill_1..N
