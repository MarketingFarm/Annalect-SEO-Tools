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

# Initialize session state for step
if 'step' not in st.session_state:
    st.session_state.step = 1
# step1 UI
def step1():
    st.header("Step 1: Analisi Competitiva & Content Gap")
    num_texts = st.selectbox(
        "Numero di testi competitor da analizzare (su 5 max)",
        list(range(1,6)), index=0, key='num_texts')
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

# step2 UI
def step2():
    st.header("Step 2: Generazione Keyword Strategy")
    if 'competitor_texts' not in st.session_state:
        st.error("Dati mancanti. Ritorna allo step precedente.")
        return
    # Show previous analysis tables
    if 'analysis_tables' in st.session_state:
        st.subheader("Entità Fondamentali (Common Ground Analysis)")
        st.markdown(st.session_state.analysis_tables[0], unsafe_allow_html=True)
        st.subheader("Entità Mancanti (Content Gap Opportunity)")
        st.markdown(st.session_state.analysis_tables[1], unsafe_allow_html=True)
    else:
        st.info("Analisi non eseguita. Ritorna allo step 1.")
    st.markdown("---")
    st.write("Ora genera la strategia keyword basata sull'analisi precedente.")
    if st.button("Genera Keyword Strategy 🚀"):
        prompt2 = f"""
Partendo dall'analisi approfondita dei testi competitor eseguita, la tua missione è estrapolare e organizzare in una tabella intuitiva le keyword più efficaci per il mio contenuto, al fine di massimizzare la rilevanza e il posizionamento. La tabella dovrà specificare:

- La keyword principale su cui focalizzarsi.
- Le keyword secondarie/correlate per espandere la copertura semantica.
- Le LSI keywords per approfondire la comprensione di Google sull'argomento.

Non limitarti all'esistente: se vi siano keyword fondamentali assenti nei testi analizzati ma indispensabili per creare un contenuto superiore, integrale nella tabella evidenziandone il valore aggiunto.

Restituisci il risultato in JSON con le chiavi:
```
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
    "Categoria": "Keyword Fondamentali Mancanti (Opportunità di Content Gap)",
    "Keywords": [...],
    "Valore Aggiunto": "..."
  }}
]
```
"""
        with st.spinner("Generazione in corso..."):
            resp2 = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt2]
            )
        try:
            strategy = resp2.json()
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
    # Before step2 generate and cache analysis tables if not exists
    if 'analysis_tables' not in st.session_state and 'competitor_texts' in st.session_state:
        full_text = "
---
".join(st.session_state.competitor_texts)
        # reuse original prompt to get analysis tables
        prompt = f"""
## PROMPT DI ANALISI COMPETITIVA E CONTENT GAP ##

**RUOLO:**
Agisci come un analista SEO d'élite, specializzato in analisi semantica competitiva.

**CONTESTO:**
Obiettivo: superare i competitor posizionati per la keyword target. Fornisci le entità da includere e le opportunità di content gap.

**COMPITO:**
Analizza i seguenti testi competitor:
{full_text}

1. Identifica l'**Argomento Principale Comune** e il **Search Intent Primario**.
2. Crea **due tabelle Markdown**:

---
### TABELLA 1: ENTITÀ FONDAMENTALI (Common Ground Analysis)
| Entità | Rilevanza Strategica | Azione per il Mio Testo |
| :--- | :--- | :--- |

---
### TABELLA 2: ENTITÀ MANCANTI (Content Gap Opportunity)
| Entità da Aggiungere | Motivazione dell'Inclusione | Azione SEO Strategica |
| :--- | :--- | :--- |

Arricchisci la colonna "Entità" con esempi specifici tra parentesi.
Mantieni solo le due tabelle, con markdown valido e wrap del testo.
"""
        resp = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[prompt]
        )
        md = resp.text
        tables = [blk for blk in md.split("

") if blk.strip().startswith("|")]
        st.session_state.analysis_tables = tables
    step2()
