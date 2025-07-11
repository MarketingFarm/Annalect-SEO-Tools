import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re
import spacy
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# --- 1. CONFIGURAZIONE INIZIALE E API KEY ---

# Configurazione della pagina (deve essere il primo comando Streamlit)
st.set_page_config(
    page_title="Qforia - GEO & AI Content Architect", 
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🧠"
)

# --- NUOVO: Caricamento automatico della chiave API da st.secrets ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except KeyError:
    st.error(" Chiave API di Gemini non trovata! Per favore, aggiungi 'GEMINI_API_KEY = \"tua_chiave\"' al tuo file .streamlit/secrets.toml.")
    st.stop()
except Exception as e:
    st.error(f" Impossibile configurare Gemini. Errore: {e}")
    st.stop()


# --- CACHING E INIZIALIZZAZIONE ---

# Caricamento del modello spaCy (messo in cache per non ricaricarlo ogni volta)
@st.cache_resource
def load_spacy_model(model_name):
    try:
        nlp = spacy.load(model_name)
        return nlp
    except OSError:
        st.error(f"Modello spaCy '{model_name}' non trovato. Esegui 'python -m spacy download {model_name}' nel tuo terminale.")
        st.stop()

nlp = load_spacy_model("en_core_web_sm")

# Inizializzazione dello stato della sessione per la cronologia
if 'history' not in st.session_state:
    st.session_state.history = []


# --- 2. STYLING E INTERFACCIA UTENTE ---

def load_custom_css():
    st.markdown("""
    <style>
    /* ... [Il tuo CSS completo va qui, l'ho omesso per brevità] ... */
    .main { background-color: #F5F7FA; }
    .main-header { background: linear-gradient(135deg, #0D47A1 0%, #4285F4 100%); color: white; padding: 2rem; border-radius: 10px; margin-bottom: 2rem; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15); text-align: center; }
    .main-header h1 { color: white !important; text-shadow: 1px 1px 2px rgba(0,0,0,0.2); }
    .main-header p { color: #E3F2FD !important; }
    .sidebar-header { background: linear-gradient(135deg, #00796B 0%, #009688 100%); color: white; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; text-align: center; }
    .sidebar-header h2 { color: white !important; margin:0; }
    .stButton > button { background: linear-gradient(135deg, #0D47A1 0%, #4285F4 100%); color: white; border: none; border-radius: 8px; padding: 0.75rem 1.5rem; font-weight: bold; font-size: 1.1rem; transition: all 0.3s ease; box-shadow: 0 2px 4px rgba(0,0,0,0.2); width: 100%; }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.3); filter: brightness(1.1); }
    .generation-details { background-color: #E0F2F1; padding: 1.5rem; border-radius: 10px; margin: 1rem 0; border-left: 5px solid #009688; }
    .stDownloadButton > button { background: linear-gradient(135deg, #28A745 0%, #20C997 100%); color: white; border: none; border-radius: 8px; padding: 0.75rem 1.5rem; font-weight: bold; transition: all 0.3s ease; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

load_custom_css()

# Intestazione principale
st.markdown("""
<div class="main-header">
    <h1>🧠 Qforia - GEO & AI Content Architect</h1>
    <p>Simulatore Avanzato di Fan-Out per la Generative Engine Optimization</p>
</div>
""", unsafe_allow_html=True)

# --- Barra Laterale di Configurazione ---
st.sidebar.markdown("""
<div class="sidebar-header">
    <h2>⚙️ Configurazione Strategica</h2>
</div>
""", unsafe_allow_html=True)

user_query = st.sidebar.text_area("💭 Inserisci la tua query principale", "miglior macchina per caffè in grani", height=100)

user_industry = st.sidebar.text_input(
    "🎯 Qual è il tuo settore o caso d'uso? (Opzionale)",
    placeholder="Es. Content Marketing, Ricerca di Mercato"
)

mode = st.sidebar.radio(
    "🔍 Livello di Analisi", 
    ["AI Overview (Veloce)", "AI Mode (Approfondita)"],
    captions=["10+ query mirate", "20+ query strategiche"],
    horizontal=True
)

exclude_brands = st.sidebar.toggle(
    "🚫 Escludi Brand Specifici", 
    value=False,
    help="Se attivato, l'IA non menzionerà nomi di brand commerciali (es. De'Longhi, Dyson), concentrandosi su categorie e feature. Utile per query generiche come 'olio extravergine'."
)


# --- 3. LOGICA DI GENERAZIONE E PROMPT ENGINEERING ---

def QUERY_FANOUT_PROMPT(q, mode, industry, exclude_brands_flag):
    min_queries_simple = 10
    min_queries_complex = 20
    persona_prompt = (
        "You are an 'Expert SEO & AI Content Architect'. Your primary mission is to deconstruct a user's query "
        "to create a comprehensive content blueprint. This blueprint must be designed to create a single piece of content "
        "so thorough, authoritative, and well-structured that it can dominate traditional SERPs, be heavily featured in Google's AI Overviews, "
        "and become a canonical source of information for LLMs like Gemini and ChatGPT.\n\n"
        "You think in terms of entities, topic clusters, and user intent funnels. Every query you generate is a strategic component "
        "of this master content plan. Your goal is not just to answer the user's question, but to answer every possible follow-up question."
    )
    if mode == "AI Overview (Veloce)":
        num_queries_instruction = f"Decide on an optimal number of queries to generate, **at least {min_queries_simple}**."
    else:
        num_queries_instruction = f"Decide on an optimal number of queries to generate, **at least {min_queries_complex}**. For this deep analysis, aim for a comprehensive set."
    
    brand_instruction = "IMPORTANT CONSTRAINT: The user has requested to exclude specific brand names. DO NOT mention any commercial brands (e.g., De'Longhi, Dyson, Sony). Instead, focus entirely on product categories, technical features, material types, and user needs." if exclude_brands_flag else "You are encouraged to mention specific, relevant brand names as they are key entities for competitor analysis and user searches."
    industry_context = f"The user is operating in the '{industry}' sector. Tailor the 'possible_usage_in_industry' field to be highly relevant and specific to this context." if industry else ""

    return (
        f"{persona_prompt}\n\n"
        f"The user's original query is: \"{q}\". The selected analysis level is: \"{mode}\".\n"
        f"{industry_context}\n{brand_instruction}\n\n"
        f"**Your Task:**\n"
        f"1.  **Determine Query Count:** Based on the query's complexity and the '{mode}' level, {num_queries_instruction} Provide a brief reasoning for your choice.\n"
        f"2.  **Generate Queries:** Generate exactly that many unique queries. These queries should form a logical content structure, covering all angles: reformulations, implicit questions, comparisons, entity explorations (like features, not just brands if excluded), and follow-up questions.\n"
        f"3.  **Provide Detailed Fields:** For each query, provide 'type', 'user_intent', 'reasoning', and 'possible_usage_in_industry'.\n"
        f"4.  **JSON Output:** Return ONLY a valid JSON object following the specified format. Do not include any text before or after the JSON object.\n\n"
        f"**JSON Format:**\n"
        "{\n"
        "  \"generation_details\": { \"target_query_count\": <your_determined_number>, \"reasoning_for_count\": \"<your_reasoning>\" },\n"
        "  \"expanded_queries\": [ { \"query\": \"...\", \"type\": \"...\", \"user_intent\": \"...\", \"reasoning\": \"...\", \"possible_usage_in_industry\": \"...\" } ]\n"
        "}"
    )

@st.cache_data(show_spinner=False)
def generate_fanout_cached(_query, _mode, _industry, _exclude_brands):
    prompt = QUERY_FANOUT_PROMPT(_query, _mode, _industry, _exclude_brands)
    raw_response_text = ""
    try:
        model = genai.GenerativeModel("gemini-1.5-pro-latest")
        response = model.generate_content(prompt)
        raw_response_text = response.text
        
        json_text = raw_response_text.strip()
        match = re.search(r'```json\s*(\{.*?\})\s*```', json_text, re.DOTALL)
        if match:
            json_text = match.group(1)
        
        data = json.loads(json_text)
        return data, response.usage_metadata
        
    except json.JSONDecodeError as e:
        st.error(f"🔴 Errore nel decodificare la risposta JSON: {e}")
        st.expander("🔍 Visualizza Risposta Grezza").text(raw_response_text)
        return None, None
    except Exception as e:
        st.error(f"🔴 Errore inatteso durante la generazione: {e}")
        if raw_response_text:
            st.expander("🔍 Visualizza Risposta Grezza").text(raw_response_text)
        return None, None


# --- 4. ESECUZIONE E VISUALIZZAZIONE DEI RISULTATI ---

if st.sidebar.button("🚀 Avvia Analisi GEO", type="primary"):
    if not user_query.strip():
        st.warning("⚠️ Inserisci una query da analizzare.")
        st.stop()
        
    with st.spinner("🤖 L'Architetto IA sta costruendo il tuo blueprint di contenuti..."):
        results_data, usage_metadata = generate_fanout_cached(user_query, mode, user_industry, exclude_brands)

    if results_data:
        st.success("✅ Blueprint di contenuti generato con successo!")
        
        # Estrazione e salvataggio
        expanded_queries = results_data.get("expanded_queries", [])
        if not expanded_queries:
             st.warning("L'IA ha restituito una risposta valida ma senza query. Prova a riformulare la tua richiesta.")
             st.stop()
        
        st.session_state.history.insert(0, {
            "query": user_query, "mode": mode, "results_data": results_data, 
            "usage_metadata": usage_metadata, "timestamp": pd.Timestamp.now()
        })
        
        df = pd.DataFrame(expanded_queries)
        tab1, tab2, tab3 = st.tabs(["📊 Blueprint Principale", "🧠 Analisi Avanzata", "📜 Cronologia Analisi"])

        with tab1:
            details = results_data.get("generation_details", {})
            st.markdown("### Strategia di Generazione dell'IA")
            col1, col2, col3 = st.columns(3)
            target_count, generated_count = details.get('target_query_count', 'N/A'), len(df)
            col1.metric("🎯 Query Previste", target_count)
            col2.metric("✅ Query Generate", generated_count)
            col3.metric("📊 Corrispondenza", "Perfetta" if target_count == generated_count else "Varianza")
            st.markdown(f"**🤔 Ragionamento dell'IA:** *{details.get('reasoning_for_count', 'Non fornito.')}*")
            if usage_metadata:
                 st.info(f"💡 Token utilizzati: {usage_metadata.total_token_count}", icon="🪙")

            st.markdown("---")
            st.markdown("### Query Generate (Blueprint del Contenuto)")
            st.dataframe(df, use_container_width=True, height=min(len(df) + 1, 20) * 35 + 3)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download Blueprint (CSV)", csv, f"geo_blueprint_{user_query[:20]}.csv", "text/csv")
            json_data = json.dumps(results_data, indent=2).encode("utf-8")
            st.download_button("📥 Download Dati Grezzi (JSON)", json_data, f"geo_raw_{user_query[:20]}.json", "application/json")

        with tab2:
            st.markdown("### Analisi Approfondita del Blueprint")
            st.subheader("Distribuzione dei Tipi di Query")
            type_counts = df['type'].value_counts()
            st.bar_chart(type_counts)
            
            st.subheader("Entità Chiave Estratte")
            all_queries_text = " ".join(df['query'].tolist())
            doc = nlp(all_queries_text)
            entities = [(ent.text, ent.label_) for ent in doc.ents if ent.label_ in ["ORG", "PRODUCT", "PERSON", "GPE", "FAC", "LOC"]]
            if entities:
                entity_df = pd.DataFrame(entities, columns=['Entità', 'Tipo']).value_counts().reset_index(name='Frequenza')
                st.dataframe(entity_df, use_container_width=True)
            else:
                st.info("Nessuna entità chiave (Brand, Prodotti, Luoghi) trovata nelle query.")
                
            st.subheader("Termini Ricorrenti")
            if len(all_queries_text) > 10:
                wordcloud = WordCloud(width=800, height=300, background_color="white", colormap="viridis").generate(all_queries_text)
                fig, ax = plt.subplots()
                ax.imshow(wordcloud, interpolation='bilinear')
                ax.axis("off")
                st.pyplot(fig)
            else:
                st.warning("Testo insufficiente per generare una word cloud.")

        with tab3:
            st.markdown("### Cronologia delle Analisi Recenti")
            if not st.session_state.history:
                st.info("Nessuna analisi eseguita in questa sessione.")
            else:
                for record in st.session_state.history:
                    with st.expander(f"**{record['timestamp'].strftime('%H:%M:%S')}** - Query: `{record['query']}`"):
                        queries_in_record = record['results_data'].get('expanded_queries', [])
                        st.metric("Query Generate", len(queries_in_record))
                        st.dataframe(pd.DataFrame(queries_in_record), use_container_width=True)
