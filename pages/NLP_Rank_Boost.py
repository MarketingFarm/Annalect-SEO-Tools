import streamlit as st
import os
from google import genai

# --- INIEZIONE CSS per il bottone rosso e wrap testo nelle tabelle ---
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

# --- Config Gemini ---
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

st.title("Analisi Competitiva & Content Gap con Gemini")
st.divider()

# Inizializza lo step
if 'step' not in st.session_state:
    st.session_state.step = 1

# Step 1: raccolta testi competitor
def step1():
    st.header("Step 1: Analisi Competitiva & Content Gap")
    st.info("Inserisci fino a 5 testi da competitor.")
    num_texts = st.selectbox(
        "Numero di testi competitor da analizzare (max 5)",
        list(range(1, 6)),
        index=0,
        key='num_texts'
    )
    cols = st.columns(st.session_state.num_texts)
    texts = []
    for i, col in enumerate(cols, 1):
        with col:
            t = st.text_area(f"Testo competitor {i}", height=200, key=f"text_{i}")
            texts.append(t.strip())

    if st.button("Prosegui al Step 2 🚀"):
        competitor_texts = [t for t in texts if t]
        if not competitor_texts:
            st.error("Per favore, incolla almeno un testo da competitor.")
        else:
            st.session_state.competitor_texts = competitor_texts
            st.session_state.step = 2
            st.experimental_rerun()

# Step 2: generazione keyword strategy
def step2():
    st.header("Step 2: Generazione Keyword Strategy")
    # Se manca l'analisi di step1, invita a tornare indietro
    if 'competitor_texts' not in st.session_state:
        st.error("Dati mancanti. Ritorna allo step precedente.")
        return

    # Visualizza le tabelle di analisi Competitive Gap
    if 'analysis_tables' in st.session_state:
        st.subheader("Entità Fondamentali (Common Ground Analysis)")
        st.markdown(st.session_state.analysis_tables[0], unsafe_allow_html=True)
        st.subheader("Entità Mancanti (Content Gap Opportunity)")
        st.markdown(st.session_state.analysis_tables[1], unsafe_allow_html=True)
    else:
        st.info("Analisi non eseguita. Ritorna allo step 1 e clicca su \"Prosegui\".")

    st.markdown("---")
    st.write("Ora genera la strategia keyword basata sull'analisi precedente.")

    if st.button("Genera Keyword Strategy 🚀"):
        prompt2 = f"""
Partendo dall'analisi approfondita dei testi competitor, estrai e organizza in JSON le keyword più efficaci per il contenuto:

- Categoria: Keyword Principale (Focus Primario)
- Categoria: Keyword Secondarie/Correlate (Espansione Semantica)
- Categoria: LSI Keywords (Comprensione Approfondita)
- Categoria: Keyword Fondamentali Mancanti (Opportunità Content Gap)

Restituisci un oggetto JSON con struttura:

{{
  "Keyword Strategy": [
    {{
      "Categoria": "Keyword Principale (Focus Primario)",
      "Keywords": [...],
      "Valore Aggiunto": "..."
    }},
    {{
      "Categoria": "Keyword Secondarie/Correlate",
      "Keywords": [...],
      "Valore Aggiunto": "..."
    }},
    {{
      "Categoria": "LSI Keywords (Comprensione Approfondita)",
      "Keywords": [...],
      "Valore Aggiunto": "..."
    }},
    {{
      "Categoria": "Keyword Fondamentali Mancanti (Opportunità Content Gap)",
      "Keywords": [...],
      "Valore Aggiunto": "..."
    }}
  ]
}}
"""
        with st.spinner("Generazione in corso..."):
            resp2 = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt2]
            )
        # Il client Google GenAI non fornisce .json(), usiamo text e poi json.loads
        import json
        try:
            strategy = json.loads(resp2.text)
        except Exception:
            strategy = resp2.text
        st.subheader("Keyword Strategy JSON")
        st.json(strategy)

    if st.button("Torna allo Step 1 🔙"):
        st.session_state.step = 1
        st.experimental_rerun()

# Main navigation
if st.session_state.step == 1:
    step1()
else:
    # Se non sono ancora state generate le tabelle di analisi, chiamale automaticamente
    if 'analysis_tables' not in st.session_state and 'competitor_texts' in st.session_state:
        full_text = "\n---\n".join(st.session_state.competitor_texts)
        prompt1 = f"""
## PROMPT DI ANALISI COMPETITIVA E CONTENT GAP ##

**RUOLO:** Agisci come analista SEO d'élite.

**CONTESTO:** Supera i competitor per la keyword target.

**TESTI COMPETITOR:**  
{full_text}

**COMPITO:**  
1. Identifica l'Argomento Principale Comune e il Search Intent Primario.  
2. Genera due tabelle Markdown:

### TABELLA 1: ENTITÀ FONDAMENTALI
| Entità | Rilevanza Strategica | Azione per il Mio Testo |
| :--- | :--- | :--- |

### TABELLA 2: ENTITÀ MANCANTI
| Entità da Aggiungere | Motivazione dell'Inclusione | Azione SEO Strategica |
| :--- | :--- | :--- |

Arricchisci la colonna “Entità” con esempi specifici. Mantieni solo le due tabelle in Markdown.
"""
        with st.spinner("Analisi in corso con Gemini..."):
            resp1 = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt1]
            )
        md = resp1.text
        # Estrai solo i blocchi che iniziano con '|' (le due tabelle)
        tables = [blk for blk in md.split("\n\n") if blk.strip().startswith("|")]
        st.session_state.analysis_tables = tables

    step2()
