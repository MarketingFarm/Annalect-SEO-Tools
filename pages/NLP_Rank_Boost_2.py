import streamlit as st
import json
import re
import pandas as pd
from urllib.parse import urlparse

# Funzione per pulire le etichette per la visualizzazione
def clean_label(raw_label):
    return re.sub(r'\*+', '', raw_label).strip()

# --- Configurazione Pagina ---
st.set_page_config(layout="wide")
st.title("📝 Analisi e Scrittura Contenuti SEO")
st.markdown(
    """
    In questa pagina puoi caricare il JSON generato dalla pagina di raccolta dati SEO,
    visualizzare i dettagli della query, le People Also Ask, le Ricerche Correlate,
    i primi 10 risultati organici in stile SERP, selezionare le singole keywords,
    e infine scegliere righe da Common Ground e Content Gap,
    e contestualizzare il contenuto.
    """
)

# --- Stile CSS Personalizzato ---
st.markdown(
    """
    <style>
      .stMultiSelect [data-baseweb="select"] span {
        max-width: none !important;
        white-space: normal !important;
        line-height: 1.3 !important;
      }
      .stMultiSelect > label {
        font-size: 1.25rem !important;
        font-weight: 500 !important;
      }
      .stMultiSelect [data-testid="stWidgetLabel"] {
        display: none !important; margin: 0; padding: 0; height: 0;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Elementi UI Standard ---
separator = """<div style="border-top:1px solid #ECEDEE; margin: 1.5rem 0; padding-top:1rem;"></div>"""

# --- Inizializzazione Session State ---
if "data" not in st.session_state:
    st.session_state.data = None
if "step" not in st.session_state:
    st.session_state.step = 1
if "keyword_widgets_map" not in st.session_state:
    st.session_state.keyword_widgets_map = {}

# --- Logica di Caricamento File ---
if st.session_state.data is None:
    uploaded_file = st.file_uploader("Carica il file JSON", type="json", help="Carica qui il file JSON generato dalla pagina precedente")
    if uploaded_file:
        try:
            st.session_state.data = json.load(uploaded_file)
            st.session_state.step = 1
            # Pulisce tutto lo stato vecchio per evitare conflitti
            keys_to_clear = list(st.session_state.keys())
            for key in keys_to_clear:
                if key != 'data' and key != 'step':
                    del st.session_state[key]
            st.rerun()
        except json.JSONDecodeError as e:
            st.error(f"❌ Errore nel parsing del JSON: {e}")
            st.stop()
    else:
        st.info("⏳ Carica un file JSON per procedere con l'analisi.")
        st.stop()

data = st.session_state.data

# --- Funzioni di Navigazione ---
def go_next():
    st.session_state.step = min(st.session_state.step + 1, 5)
def go_back():
    st.session_state.step = max(st.session_state.step - 1, 1)

# --- Indicatore di Step ---
st.markdown(f"## Step {st.session_state.step}")
st.markdown(separator, unsafe_allow_html=True)

# ==================== STEP 1 ====================
if st.session_state.step == 1:
    query = data.get("query", "")
    st.markdown(f"### Dati relativi alla query: *{query}*")
    st.markdown(separator, unsafe_allow_html=True)
    analysis_list = data.get("analysis_strategica", [])
    analysis_map = {clean_label(item.get("Caratteristica SEO", "")): clean_label(item.get("Analisi Sintetica", "")) for item in analysis_list}
    raw_signals = analysis_map.get("Segnali E-E-A-T", "")
    signals_val = re.sub(r"\s*\([^)]*\)", "", raw_signals).strip()
    st.markdown('<h5>Dettagli della Query</h5>', unsafe_allow_html=True)
    cols_main = st.columns(4, gap="small")
    labels_main = ["Query", "Country", "Language", "Segnali E-E-A-T"]
    vals_main = [data.get("query", ""), data.get("country", ""), data.get("language", ""), signals_val]
    for col, lbl, val in zip(cols_main, labels_main, vals_main):
        col.markdown(f"""<div style="padding: 0.75rem 1rem; border: 1px solid #dee2e6; border-radius: 0.5rem; background-color: #f8f9fa; margin-bottom: 1rem;"><div style="font-size:0.8rem; color: #6c757d;">{lbl}</div><div style="font-size:1.1rem; color:#212529; font-weight:500;">{val}</div></div>""", unsafe_allow_html=True)
    st.markdown('<h5 style="margin-top:1rem;">Analisi Strategica</h5>', unsafe_allow_html=True)
    labels_analysis = ["Search Intent Primario", "Search Intent Secondario", "Target Audience & Leggibilità", "Tone of Voice (ToV)"]
    cols2 = st.columns(len(labels_analysis), gap="small")
    for c, lbl in zip(cols2, labels_analysis):
        raw = analysis_map.get(lbl, "")
        v = re.sub(r"\s*\([^)]*\)", "", raw).strip()
        c.markdown(f"""<div style="padding: 0.75rem 1rem; border: 1px solid #dee2e6; border-radius: 0.5rem; background-color: #f8f9fa;"><div style="font-size:0.8rem; color: #6c757d;">{lbl}</div><div style="font-size:1rem; color:#212529; font-weight:500;">{v}</div></div>""", unsafe_allow_html=True)
    st.markdown(separator, unsafe_allow_html=True)
    col_org, col_paa = st.columns([2, 1], gap="large")
    with col_org:
        st.markdown('<h5>Risultati Organici (Top 10)</h5>', unsafe_allow_html=True)
        for it in data.get("organic", [])[:10]:
            url_raw, p = it.get("URL", ""), urlparse(it.get("URL", ""))
            st.markdown(f"""<div style="margin-bottom: 1.5rem;"><div style="display:flex; align-items:center; margin-bottom:0.2rem;"><img src="https://www.google.com/s2/favicons?domain={p.netloc}&sz=32" onerror="this.src='https://www.google.com/favicon.ico';" style="width:20px; height:20px; margin-right:0.5rem;"/><span style="font-size:14px; color:#4d5156;">{p.scheme}://{p.netloc}</span></div><a href="{url_raw}" style="color:#1a0dab; text-decoration:none; font-size:20px;">{it.get("Meta Title", "")}</a><div style="font-size:14px; color:#4d5156; line-height:1.4;">{it.get("Meta Description", "")}</div></div>""", unsafe_allow_html=True)
    with col_paa:
        st.markdown('<h5>People Also Ask</h5>', unsafe_allow_html=True)
        for q in data.get("people_also_ask", []): st.markdown(f"- {q}")
        st.markdown('<h5 style="margin-top:1.5rem;">Ricerche Correlate</h5>', unsafe_allow_html=True)
        for r in data.get("related_searches", []): st.markdown(f"- {r}")
    st.button("Avanti", on_click=go_next, key="next_btn", type="primary")

# ==================== STEP 2 ====================
elif st.session_state.step == 2:
    st.markdown('<h3 style="margin-top:0; padding-top:0;">Seleziona le singole keywords per l\'analisi</h3>', unsafe_allow_html=True)
    keyword_mining = data.get("keyword_mining", [])
    if keyword_mining:
        st.session_state.keyword_widgets_map = {}
        for i, entry in enumerate(keyword_mining):
            display_label = clean_label(entry.get("Categoria Keyword", ""))
            kws = [k.strip(" `") for k in entry.get("Keywords / Concetti / Domande", "").split(",")]
            widget_key = f"ms_keyword_{i}"
            st.session_state.keyword_widgets_map[widget_key] = display_label
            st.markdown(f'<p style="font-size:1.25rem; font-weight:600; margin:1rem 0 0.75rem 0;">{display_label}</p>', unsafe_allow_html=True)
            st.multiselect(label="", options=kws, default=kws, key=widget_key)
        c1, c2, _ = st.columns([1,1,6])
        c1.button("Indietro", on_click=go_back, key="back_btn")
        c2.button("Avanti", on_click=go_next, key="next2_btn", type="primary")
    else:
        st.warning("⚠️ Non ho trovato la sezione di Keyword Mining nel JSON.")
        st.button("Indietro", on_click=go_back, key="back_btn_empty")

# ==================== STEP 3 ====================
elif st.session_state.step == 3:
    st.markdown('<h3 style="margin-top:0.5rem; padding-top:0;">Analisi Semantica Avanzata</h3>', unsafe_allow_html=True)

    # Prepara i dati iniziali per i data_editor
    df_common_initial = pd.DataFrame(data.get("common_ground", []))
    if not df_common_initial.empty:
        df_common_initial.insert(0, "Seleziona", False)

    df_gap_initial = pd.DataFrame(data.get("content_gap", []))
    if not df_gap_initial.empty:
        df_gap_initial.insert(0, "Seleziona", False)

    st.subheader("Common Ground Analysis")
    st.data_editor(df_common_initial, use_container_width=True, hide_index=True, key="editor_common", height=300)

    st.subheader("Content Gap Opportunity")
    st.data_editor(df_gap_initial, use_container_width=True, hide_index=True, key="editor_gap", height=300)
    
    c1, c2, _ = st.columns([1,1,6])
    c1.button("Indietro", on_click=go_back, key="back_btn_3")
    c2.button("Avanti", on_click=go_next, key="next3_btn", type="primary")

# ==================== STEP 4 ====================
elif st.session_state.step == 4:
    st.markdown('<h3 style="margin-top:0.5rem; padding-top:0;">Contestualizzazione Contenuto</h3>', unsafe_allow_html=True)
    col1, col2 = st.columns(2, gap="small")
    dest_options = {"-- Seleziona --": ["-- Seleziona --"], "E-commerce": ["-- Seleziona --", "PLP", "PDP", "Guida Acquisto", "Articolo Blog"], "Magazine / Testata Giornalistica": ["-- Seleziona --", "Articolo Blog"]}
    
    # Inizializza le chiavi se non esistono
    if 'context_select' not in st.session_state:
        st.session_state.context_select = "-- Seleziona --"

    col1.selectbox("Contesto", dest_options.keys(), key="context_select")
    col2.selectbox("Destinazione Contenuto", dest_options.get(st.session_state.context_select, ["-- Seleziona --"]), key="dest_select")
    
    st.markdown("---")
    if st.toggle("Aggiungi Keyword Personalizzate", key="custom_kw_toggle"):
        st.text_area("Incolla le tue keyword (una per riga)", height=120, placeholder="keyword1\nkeyword2\nkeyword3", key="raw_custom_keywords")
    st.markdown("---")
    if st.toggle("Aggiungi ToV / Stile del Cliente", key="tov_toggle"):
        st.text_area("Descrivi lo stile o incolla esempi di testo", height=150, key="raw_tov_text")
    st.markdown("---")
    if st.toggle("Aggiungi Informazioni Aggiuntive", key="info_toggle"):
        st.text_area("Inserisci ulteriori informazioni (es. dettagli sul brand, obiettivi specifici, ecc.)", height=150, key="raw_additional_info")
        
    c1, c2, _ = st.columns([1,1,6])
    c1.button("Indietro", on_click=go_back, key="back_btn_4")
    c2.button("Avanti", on_click=go_next, key="next4_btn", type="primary")

# ==================== STEP 5 ====================
elif st.session_state.step == 5:
    st.markdown('<h3 style="margin-top:0.5rem; padding-top:0;">Recap delle Scelte</h3>', unsafe_allow_html=True)
    
    recap_data = {"Query": data.get("query", "")}
    
    # Keyword Mining
    if "keyword_widgets_map" in st.session_state:
        for widget_key, display_label in st.session_state.keyword_widgets_map.items():
            recap_data[f"{display_label} Selezionate"] = ", ".join(st.session_state.get(widget_key, []))

    # Analisi Strategica
    analysis_list = data.get("analysis_strategica", [])
    analysis_map = {clean_label(item.get("Caratteristica SEO", "")): clean_label(item.get("Analisi Sintetica", "")) for item in analysis_list}
    for key in ["Search Intent Primario", "Search Intent Secondario", "Target Audience & Leggibilità", "Tone of Voice (ToV)"]:
        recap_data[key] = re.sub(r"\s*\([^)]*\)", "", analysis_map.get(key, "")).strip()

    # Common Ground e Content Gap
    edited_common = st.session_state.get("editor_common", pd.DataFrame())
    if not edited_common.empty and "Seleziona" in edited_common.columns:
        recap_data["Righe Common Ground Selezionate"] = len(edited_common[edited_common["Seleziona"] == True])
    
    edited_gap = st.session_state.get("editor_gap", pd.DataFrame())
    if not edited_gap.empty and "Seleziona" in edited_gap.columns:
        recap_data["Righe Content Gap Selezionate"] = len(edited_gap[edited_gap["Seleziona"] == True])

    # Contestualizzazione
    recap_data["Contesto"] = st.session_state.get("context_select", "Non specificato")
    recap_data["Destinazione"] = st.session_state.get("dest_select", "Non specificato")
    recap_data["Keyword Personalizzate"] = st.session_state.get("raw_custom_keywords", "").replace('\n', ', ')
    recap_data["ToV Personalizzato"] = st.session_state.get("raw_tov_text", "")
    recap_data["Informazioni Aggiuntive"] = st.session_state.get("raw_additional_info", "")

    # Creazione DataFrame e visualizzazione
    df_recap = pd.DataFrame(recap_data.items(), columns=["Voce", "Valore"])
    st.table(df_recap)
    
    c1, c2, _ = st.columns([1,1,6])
    c1.button("Indietro", on_click=go_back, key="back_btn_5")
