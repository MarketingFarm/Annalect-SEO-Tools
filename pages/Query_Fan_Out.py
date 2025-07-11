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
    page_icon="🧠"
)

# Caricamento sicuro della chiave API dai segreti di Streamlit
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except (KeyError, AttributeError):
    st.error("Chiave API di Gemini non trovata! Per favore, aggiungi 'GEMINI_API_KEY = \"tua_chiave\"' al tuo file .streamlit/secrets.toml.")
    st.stop()
except Exception as e:
    st.error(f"Impossibile configurare Gemini. Errore: {e}")
    st.stop()

# --- CACHING DEI MODELLI E INIZIALIZZAZIONE DELLO STATO ---

@st.cache_resource
def load_spacy_model(model_name):
    """Carica un modello spaCy, gestendo gli errori se non è installato."""
    try:
        nlp = spacy.load(model_name)
        return nlp
    except OSError:
        st.error(f"Modello spaCy '{model_name}' non trovato. Assicurati che sia specificato correttamente nel tuo file requirements.txt.")
        st.stop()

# Inizializza la cronologia nella sessione se non esiste
if 'history' not in st.session_state:
    st.session_state.history = []

# --- 2. STYLING E INTERFACCIA UTENTE ---

def load_custom_css():
    """Carica CSS personalizzato per migliorare l'aspetto dell'app."""
    st.markdown("""
    <style>
    .main { background-color: #F5F7FA; }
    .main-header { background: linear-gradient(135deg, #0D47A1 0%, #4285F4 100%); color: white; padding: 2rem; border-radius: 10px; margin-bottom: 2rem; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15); text-align: center; }
    .main-header h1 { color: white !important; text-shadow: 1px 1px 2px rgba(0,0,0,0.2); }
    .sidebar-header { background: linear-gradient(135deg, #00796B 0%, #009688 100%); color: white; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; text-align: center; }
    .sidebar-header h2 { color: white !important; margin:0; }
    #MainMenu, footer, header { visibility: hidden; }
    .stButton > button { font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

load_custom_css()

# Intestazione Principale
st.markdown("""
<div class="main-header">
    <h1>🧠 Qforia - GEO & AI Content Architect</h1>
    <p>Simulatore Avanzato di Fan-Out per la Generative Engine Optimization</p>
</div>
""", unsafe_allow_html=True)

# --- Barra Laterale di Configurazione ---
st.sidebar.markdown("""<div class="sidebar-header"><h2>⚙️ Configurazione Strategica</h2></div>""", unsafe_allow_html=True)

language_map = {"Italiano": "it_core_news_sm", "Inglese": "en_core_web_sm"}
selected_language_name = st.sidebar.selectbox(
    "🌍 Lingua di Analisi",
    options=list(language_map.keys()),
    help="Seleziona la lingua della query per un'analisi delle entità più accurata."
)
selected_model = language_map[selected_language_name]

user_query = st.sidebar.text_area("💭 Inserisci la tua query principale", "vestiti eleganti donna", height=100)
user_industry = st.sidebar.text_input("🎯 Qual è il tuo settore o caso d'uso? (Opzionale)", placeholder="Es. E-commerce di moda")
mode = st.sidebar.radio("🔍 Livello di Analisi", ["AI Overview (Veloce)", "AI Mode (Approfondita)"], horizontal=True, captions=["~10 query", "20+ query"])
exclude_brands = st.sidebar.toggle("🚫 Escludi Brand Specifici", value=False, help="Se attivato, l'IA non menzionerà nomi di brand, concentrandosi su categorie e feature.")

# --- 3. LOGICA DI GENERAZIONE E PROMPT STRATEGICO ---

def QUERY_FANOUT_PROMPT_STRATEGIC(q, mode, industry, exclude_brands_flag):
    """Costruisce il prompt strategico per Gemini, richiedendo un output JSON strutturato."""
    persona_prompt = (
        "You are an 'Expert SEO & AI Content Architect'. Your mission is to analyze the user's query and produce a complete, actionable content strategy blueprint. "
        "Your output must be structured to guide the user in creating a dominant online presence for the topic. "
        "You must categorize your findings into three distinct, strategic sections: Pillar Page Structure, Cluster Content Ideas, and Technical/E-commerce Recommendations."
    )
    brand_instruction = "IMPORTANT CONSTRAINT: Do NOT mention any commercial brands (e.g., De'Longhi, Zara). Focus on categories, features, and user needs." if exclude_brands_flag else "You are encouraged to mention relevant brand names as they are key entities."
    industry_context = f"The user is in the '{industry}' sector. All recommendations must be tailored to this context." if industry else ""

    return (
        f"{persona_prompt}\n\n"
        f"**User Query:** \"{q}\"\n"
        f"**Analysis Level:** \"{mode}\"\n"
        f"{industry_context}\n{brand_instruction}\n\n"
        f"**Your Task:** Generate a complete strategic blueprint in a valid JSON format ONLY. Do not include any text before or after the JSON object. The blueprint must have three main keys:\n\n"
        f"1.  **`pillar_page_structure`**: Outline the sections of the main guide. Each item must be an object with `section_title` (an H2 for the page), `content_to_include` (a brief on what to write, including suggestions for tables or lists), and `user_intent`.\n"
        f"2.  **`cluster_content_ideas`**: Propose 2-4 deep-dive articles to build topical authority. Each item must be an object with `article_title` (a compelling, SEO-friendly title), `strategic_goal` (what this article achieves, e.g., 'capturing a niche audience'), and `content_summary`.\n"
        f"3.  **`technical_and_ecommerce_recommendations`**: Provide 2-4 actionable recommendations for the website itself. Each item must be an object with `recommendation_type` (e.g., 'New E-commerce Filter', 'Product Page Enhancement'), `actionable_step` (what the developer or marketer should do), and `reasoning` (why this is important).\n\n"
        f"**JSON Format Example:**\n"
        "{\n"
        "  \"strategic_blueprint\": {\n"
        "    \"pillar_page_structure\": [\n"
        "      { \"section_title\": \"Titolo Sezione 1\", \"content_to_include\": \"Scrivere di X e Y. Includere una tabella comparativa.\", \"user_intent\": \"Informational\" }\n"
        "    ],\n"
        "    \"cluster_content_ideas\": [\n"
        "      { \"article_title\": \"Articolo Dettagliato su Z\", \"strategic_goal\": \"Targettizzare la nicchia Z.\", \"content_summary\": \"L'articolo deve coprire A, B, C.\" }\n"
        "    ],\n"
        "    \"technical_and_ecommerce_recommendations\": [\n"
        "      { \"recommendation_type\": \"Nuovo Filtro di Ricerca\", \"actionable_step\": \"Aggiungere un filtro 'Tessuto' con le opzioni: Seta, Cotone.\", \"reasoning\": \"Migliora la navigazione per gli utenti esperti.\" }\n"
        "    ]\n"
        "  }\n"
        "}"
    )

@st.cache_data(show_spinner=False)
def generate_fanout_cached(query, mode, industry, exclude_brands):
    """Chiama l'API di Gemini e gestisce la risposta, correggendo il JSON se necessario."""
    prompt = QUERY_FANOUT_PROMPT_STRATEGIC(query, mode, industry, exclude_brands)
    raw_response_text = ""
    try:
        model = genai.GenerativeModel("gemini-1.5-pro-latest")
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.7))
        raw_response_text = response.text
        
        json_text = raw_response_text.strip().replace('```json', '').replace('```', '')
        json_text = re.sub(r'}\s*,?\s*{', '},{', json_text) # Correzione per virgole mancanti
        
        data = json.loads(json_text)
        return data, getattr(response, 'usage_metadata', None)
        
    except json.JSONDecodeError as e:
        st.error(f"🔴 Errore nel decodificare la risposta JSON: {e}")
        st.expander("🔍 Visualizza Risposta Grezza (Dopo Correzione Automatica)").text(json_text)
        return None, None
    except Exception as e:
        st.error(f"🔴 Errore inatteso durante la generazione: {e}")
        if raw_response_text:
            st.expander("🔍 Visualizza Risposta Grezza").text(raw_response_text)
        return None, None

# --- 4. ESECUZIONE E VISUALIZZAZIONE STRATEGICA ---

if st.sidebar.button("🚀 Avvia Analisi GEO", type="primary"):
    if not user_query.strip():
        st.warning("⚠️ Inserisci una query da analizzare.")
        st.stop()
        
    with st.spinner(f"Caricamento del modello linguistico ({selected_language_name})..."):
        nlp = load_spacy_model(selected_model)

    with st.spinner("🤖 L'Architetto IA sta costruendo il tuo blueprint strategico..."):
        results_data, usage_metadata = generate_fanout_cached(user_query, mode, user_industry, exclude_brands)

    if results_data and "strategic_blueprint" in results_data:
        st.success("✅ Blueprint strategico generato con successo!")
        
        blueprint = results_data["strategic_blueprint"]
        pillar_page = blueprint.get("pillar_page_structure", [])
        cluster_content = blueprint.get("cluster_content_ideas", [])
        tech_recs = blueprint.get("technical_and_ecommerce_recommendations", [])
        
        st.session_state.history.insert(0, {
            "query": user_query, "results_data": results_data, "timestamp": pd.Timestamp.now(), "language": selected_language_name
        })
        
        tab1, tab2, tab3 = st.tabs(["**♟️ Blueprint Strategico**", "**🧠 Analisi Avanzata**", "**📜 Cronologia**"])

        with tab1:
            st.markdown("### 🏛️ Struttura della Pillar Page (Pagina Principale)")
            st.info("Usa questi blocchi come sezioni `<h2>` della tua guida principale. L'ordine suggerito è strategico.", icon="ℹ️")
            for i, item in enumerate(pillar_page):
                with st.expander(f"**Sezione {i+1}: {item.get('section_title', 'N/D')}**", expanded=i<3):
                    st.markdown(f"**Cosa Includere:** {item.get('content_to_include', 'N/D')}")
                    st.markdown(f"**Intento Utente Soddisfatto:** `{item.get('user_intent', 'N/D')}`")
            
            st.markdown("---")
            st.markdown("### 📚 Idee per Cluster Content (Articoli di Supporto)")
            st.info("Crea queste pagine o articoli per costruire la tua autorità e linkali alla Pillar Page.", icon="ℹ️")
            for item in cluster_content:
                 with st.container(border=True, height=220):
                    st.markdown(f"##### {item.get('article_title', 'N/D')}")
                    st.markdown(f"**Obiettivo:** *{item.get('strategic_goal', 'N/D')}*")
                    st.write(f"**Contenuto:** {item.get('content_summary', 'N/D')}")

            st.markdown("---")
            st.markdown("### 🛠️ Raccomandazioni Tecniche e E-commerce")
            st.info("Implementa queste modifiche sul sito per migliorare esperienza utente e vendite.", icon="ℹ️")
            for item in tech_recs:
                with st.container(border=True):
                    st.markdown(f"**Tipo:** `{item.get('recommendation_type', 'N/D')}`")
                    st.markdown(f"**Azione:** {item.get('actionable_step', 'N/D')}")
                    st.write(f"**Motivazione:** {item.get('reasoning', 'N/D')}")

            st.markdown("---")
            st.subheader("📥 Download del Blueprint")
            json_data = json.dumps(results_data, indent=2, ensure_ascii=False).encode("utf-8")
            st.download_button("Download Blueprint Completo (JSON)", json_data, f"geo_blueprint_{user_query[:20].replace(' ', '_')}.json", "application/json")

        with tab2:
            st.markdown("### Analisi Approfondita dei Testi Generati")
            all_text = " ".join([
                str(value) for item in pillar_page + cluster_content + tech_recs for value in item.values()
            ])

            if all_text.strip():
                st.subheader(f"Entità Chiave Estratte (Lingua: {selected_language_name})")
                doc = nlp(all_text)
                entities = [(ent.text, ent.label_) for ent in doc.ents if ent.label_ in ["ORG", "PRODUCT", "PERSON", "GPE", "LOC", "MISC"]]
                if entities:
                    st.dataframe(pd.DataFrame(entities, columns=['Entità', 'Tipo']).value_counts().reset_index(name='Frequenza'), use_container_width=True)
                else:
                    st.info("Nessuna entità chiave trovata nel blueprint.")
                
                st.subheader("Termini Ricorrenti")
                try:
                    wordcloud = WordCloud(width=800, height=300, background_color="white", colormap="viridis", max_words=100, contour_width=3, contour_color='steelblue').generate(all_text)
                    fig, ax = plt.subplots()
                    ax.imshow(wordcloud, interpolation='bilinear')
                    ax.axis("off")
                    st.pyplot(fig)
                except:
                    st.warning("Testo insufficiente per generare una word cloud significativa.")
            else:
                st.warning("Nessun testo da analizzare.")

        with tab3:
            st.markdown("### Cronologia delle Analisi Recenti")
            if not st.session_state.history:
                st.info("Nessuna analisi eseguita in questa sessione.")
            else:
                for record in st.session_state.history:
                    ts = record.get('timestamp', pd.Timestamp.now()).strftime('%H:%M:%S')
                    lang = record.get('language', 'N/A')
                    q = record.get('query', 'N/D')
                    with st.expander(f"**{ts}** [{lang}] - Query: `{q}`"):
                        blueprint_history = record.get('results_data', {}).get('strategic_blueprint', {})
                        st.markdown(f"**Pillar Page Sections:** {len(blueprint_history.get('pillar_page_structure', []))}")
                        st.markdown(f"**Cluster Content Ideas:** {len(blueprint_history.get('cluster_content_ideas', []))}")
                        st.markdown(f"**Tech Recommendations:** {len(blueprint_history.get('technical_and_ecommerce_recommendations', []))}")
                        if st.button("Mostra Dettagli", key=f"btn_{ts}_{q}"):
                            st.json(blueprint_history)
                            
    elif results_data is None:
        # L'errore è già stato mostrato dalla funzione di generazione.
        pass
    else:
        st.warning("⚠️ L'IA ha restituito una risposta non valida o vuota. Prova a riformulare la tua richiesta o controlla i log.")
        st.json(results_data)
