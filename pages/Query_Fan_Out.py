import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re
import spacy
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# --- 1. CONFIGURAZIONE INIZIALE E API KEY ---

st.set_page_config(
    page_title="Qforia - GEO & AI Content Architect", 
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="♟️"
)

try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except (KeyError, AttributeError):
    st.error("Chiave API di Gemini non trovata! Aggiungi 'GEMINI_API_KEY = \"tua_chiave\"' al tuo file .streamlit/secrets.toml.")
    st.stop()

# --- CACHING E INIZIALIZZAZIONE ---

@st.cache_resource
def load_spacy_model(model_name):
    try:
        nlp = spacy.load(model_name)
        return nlp
    except OSError:
        st.error(f"Modello spaCy '{model_name}' non trovato. Assicurati che sia specificato nel tuo requirements.txt.")
        st.stop()

if 'history' not in st.session_state:
    st.session_state.history = []

# --- 2. INTERFACCIA UTENTE ---

st.markdown("""<h1>♟️ Qforia - GEO & AI Content Architect</h1><p>Blueprint Strategici su Misura per Ogni Contesto</p>""", unsafe_allow_html=True)
st.sidebar.markdown("""<h2>⚙️ Configurazione Strategica</h2>""", unsafe_allow_html=True)

destination_map = {
    "Articolo del Blog (Pillar Page)": "BLOG_POST",
    "Landing Page di Conversione": "LANDING_PAGE",
    "PLP (Pagina Elenco Prodotti)": "PLP",
    "PDP (Pagina Dettaglio Prodotto)": "PDP"
}
selected_destination_name = st.sidebar.selectbox(
    "📍 Destinazione del Contenuto",
    options=list(destination_map.keys()),
    help="Scegli il contesto per adattare i consigli strategici."
)
selected_destination_code = destination_map[selected_destination_name]

language_map = {"Italiano": "it_core_news_sm", "Inglese": "en_core_web_sm"}
selected_language_name = st.sidebar.selectbox("🌍 Lingua di Analisi", options=list(language_map.keys()))
selected_model = language_map[selected_language_name]

user_query = st.sidebar.text_area("💭 Inserisci la tua query o prodotto principale", "vestiti eleganti donna", height=100)
user_industry = st.sidebar.text_input("🎯 Qual è il tuo settore?", placeholder="Es. E-commerce di moda")
exclude_brands = st.sidebar.toggle("🚫 Escludi Brand Specifici", value=False)

# --- 3. PROMPT STRATEGICI DINAMICI ---

def get_strategic_prompt(destination_code, query, industry, exclude_brands):
    """
    Costruisce un prompt dinamico che mantiene la struttura a 3 pilastri,
    ma adatta la "persona" e le istruzioni in base alla destinazione scelta.
    """
    
    # Mappatura delle personalizzazioni
    persona_map = {
        "BLOG_POST": "You are an 'Expert SEO & AI Content Architect'. Your mission is to create a content strategy to build topical authority and dominate organic search.",
        "LANDING_PAGE": "You are a 'Direct Response Copywriter & Conversion Rate Optimization (CRO) Specialist'. Your goal is to design a high-converting landing page strategy that persuades users to take action.",
        "PLP": "You are an 'E-commerce SEO & UX Specialist'. Your task is to provide a strategy to optimize an existing Product Listing Page (PLP) to improve rankings and user experience.",
        "PDP": "You are an 'E-commerce Product Merchandiser & Copywriter'. Your goal is to create a blueprint to enrich a Product Detail Page (PDP), answer all user questions, and drive sales."
    }
    
    # Mappatura dei nomi delle sezioni per chiarezza
    structure_name_map = {
        "BLOG_POST": "Pillar Page Structure",
        "LANDING_PAGE": "Core Landing Page Content Structure",
        "PLP": "PLP On-Page Content Structure",
        "PDP": "PDP Content Enhancement Structure"
    }
    
    cluster_name_map = {
        "BLOG_POST": "Cluster Content Ideas (Supporting Articles)",
        "LANDING_PAGE": "Supporting Assets (e.g., Case Studies, Webinars)",
        "PLP": "Supporting Content to Link from PLP",
        "PDP": "Supporting Content to build trust (e.g., a detailed review)"
    }
    
    # Seleziona la personalizzazione corretta, con un default sicuro
    persona = persona_map.get(destination_code, persona_map["BLOG_POST"])
    structure_name = structure_name_map.get(destination_code, "Core Content Structure")
    cluster_name = cluster_name_map.get(destination_code, "Supporting Content Ideas")
    
    brand_instruction = "IMPORTANT CONSTRAINT: Do NOT mention any commercial brands." if exclude_brands else "You can mention relevant brand names."
    industry_context = f"The user is in the '{industry}' sector. All recommendations must be tailored to this context." if industry else ""

    # Costruzione del prompt finale
    return (
        f"{persona}\n\n"
        f"**User Query/Topic:** \"{query}\"\n"
        f"**Content Destination:** \"{selected_destination_name}\"\n"
        f"{industry_context}\n{brand_instruction}\n\n"
        f"**Your Task:** Generate a complete strategic blueprint in a valid JSON format ONLY. Do not include any text before or after the JSON object. The blueprint must have three main keys, adapting their content to the chosen destination:\n\n"
        f"1.  **`core_content_structure`**: Outline the sections of the main content. The title of this section in your output should be '{structure_name}'. Each item must have `section_title` and `content_to_include`.\n"
        f"2.  **`supporting_content_ideas`**: Propose 2-4 supporting assets. The title of this section should be '{cluster_name}'. Each item must have `asset_title` and `strategic_goal`.\n"
        f"3.  **`technical_and_ecommerce_recommendations`**: Provide 2-4 actionable recommendations for the website. Each item must have `recommendation_type` and `actionable_step`.\n\n"
        f"**JSON Format:**\n"
        "{\n"
        f"  \"strategic_blueprint\": {{\n"
        f"    \"{structure_name}\": [\n"
        "      { \"section_title\": \"...\", \"content_to_include\": \"...\" }\n"
        "    ],\n"
        f"    \"{cluster_name}\": [\n"
        "      { \"asset_title\": \"...\", \"strategic_goal\": \"...\" }\n"
        "    ],\n"
        f"    \"Technical and E-commerce Recommendations\": [\n"
        "      { \"recommendation_type\": \"...\", \"actionable_step\": \"...\" }\n"
        "    ]\n"
        "  }\n"
        "}"
    )

@st.cache_data(show_spinner=False)
def generate_fanout_cached(query, industry, exclude_brands, destination_code):
    prompt = get_strategic_prompt(destination_code, query, industry, exclude_brands)
    raw_response_text = ""
    try:
        model = genai.GenerativeModel("gemini-1.5-pro-latest")
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.7))
        raw_response_text = response.text
        
        json_text = raw_response_text.strip().replace('```json', '').replace('```', '')
        json_text = re.sub(r'}\s*,?\s*{', '},{', json_text)
        
        data = json.loads(json_text)
        return data, getattr(response, 'usage_metadata', None)
        
    except Exception as e:
        st.error(f"🔴 Errore durante l'analisi della risposta: {e}")
        st.expander("🔍 Visualizza Risposta Grezza").text(raw_response_text)
        return None, None

# --- 4. ESECUZIONE E VISUALIZZAZIONE ---

if st.sidebar.button("🚀 Avvia Analisi GEO", type="primary"):
    with st.spinner(f"Caricamento modello linguistico ({selected_language_name})..."):
        nlp = load_spacy_model(selected_model)

    with st.spinner(f"🤖 Adattando la strategia per: **{selected_destination_name}**..."):
        results_data, usage_metadata = generate_fanout_cached(user_query, user_industry, exclude_brands, selected_destination_code)

    if results_data and "strategic_blueprint" in results_data:
        st.success(f"✅ Blueprint per **{selected_destination_name}** generato con successo!")
        blueprint = results_data["strategic_blueprint"]
        
        # Estrai i dati usando le chiavi dinamiche
        # Trova la chiave che assomiglia a "Structure"
        core_structure_key = next((k for k in blueprint if "Structure" in k), None)
        # Trova la chiave che assomiglia a "Content" o "Assets"
        supporting_content_key = next((k for k in blueprint if "Content" in k or "Assets" in k), None)
        
        core_structure = blueprint.get(core_structure_key, [])
        supporting_content = blueprint.get(supporting_content_key, [])
        tech_recs = blueprint.get("Technical and E-commerce Recommendations", [])
        
        st.markdown(f"### ♟️ Blueprint Strategico: **{selected_destination_name}**")

        if core_structure:
            st.markdown(f"### 🏛️ {core_structure_key}")
            st.info(f"Usa questi blocchi per costruire il contenuto principale della tua pagina.", icon="ℹ️")
            for i, item in enumerate(core_structure):
                with st.expander(f"**Sezione {i+1}: {item.get('section_title', 'N/D')}**", expanded=i<4):
                    st.markdown(f"**Cosa Includere:** {item.get('content_to_include', 'N/D')}")
        
        if supporting_content:
            st.markdown("---")
            st.markdown(f"### 📚 {supporting_content_key}")
            st.info("Crea questi contenuti di supporto per rafforzare la tua strategia.", icon="ℹ️")
            for item in supporting_content:
                 with st.container(border=True):
                    st.markdown(f"**Titolo/Asset:** {item.get('asset_title', 'N/D')}")
                    st.write(f"**Obiettivo Strategico:** {item.get('strategic_goal', 'N/D')}")

        if tech_recs:
            st.markdown("---")
            st.markdown("### 🛠️ Raccomandazioni Tecniche e E-commerce")
            st.info("Implementa queste modifiche sul tuo sito per migliorare l'esperienza e i risultati.", icon="ℹ️")
            for item in tech_recs:
                with st.container(border=True):
                    st.markdown(f"**Tipo:** `{item.get('recommendation_type', 'N/D')}`")
                    st.write(f"**Azione:** {item.get('actionable_step', 'N/D')}")
    else:
        st.error("Non è stato possibile generare un blueprint. Controlla la risposta grezza se disponibile.")
