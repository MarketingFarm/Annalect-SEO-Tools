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
    # Countries principali
    countries = ["", "Italy", "United States", "France", "Germany", "Spain"]
    country = st.selectbox("Country", countries, key="country")
with col3:
    # Lingue adattate al Country selezionato
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

# Box di testo per i 5 competitor come editor WYSIWYG con Quill
st.markdown("---")
competitor_texts = []
for i in range(1, 6):
    # Usa Quill editor per formattazione rich text
    content = st_quill(f"Editor Competitor {i}", key=f"comp_quill_{i}")
    competitor_texts.append(content)

# Pulsante di avvio analisi
action = st.button("🚀 Avvia l'Analisi")

# Ora tutte le variabili query, country, language, contesto, tipologia e comp_quill_1..5
# sono disponibili in st.session_state per i passaggi successivi.
