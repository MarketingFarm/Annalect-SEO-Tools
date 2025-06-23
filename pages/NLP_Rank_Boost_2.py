import streamlit as st
import json
import re
import pandas as pd
from urllib.parse import urlparse

# Funzione per pulire le etichette per la visualizzazione
def clean_label(raw_label):
    return re.sub(r'\*+', '', raw_label).strip()

# --- Assumo st.set_page_config già invocato nel file principale ---
st.set_page_config(layout="wide")

# Titolo e descrizione
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

# --- Hack CSS per multiselect senza troncamento, label più grandi, e rimozione spazio vuoto ---
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
        display: none !important;
        margin: 0;
        padding: 0;
        height: 0;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Separatore standardizzato ---
separator = """
<div style="
  border-top:1px solid #ECEDEE;
  margin: 1rem 0;
  padding-top:1rem;
"></div>
"""

# --- Inizializzazione Session State ---
if "data" not in st.session_state:
    st.session_state.data = None
if "step" not in st.session_state:
    st.session_state.step = 1
# APPROCCIO DEFINITIVO: Dizionario per salvare le chiavi e le etichette dei widget
if "keyword_widgets_map" not in st.session_state:
    st.session_state.keyword_widgets_map = {}

# --- Caricamento JSON (solo se non già caricato) ---
if st.session_state.data is None:
    uploaded_file = st.file_uploader(
        "Carica il file JSON",
        type="json",
        help="Carica qui il file JSON generato dalla pagina precedente"
    )
    if uploaded_file:
        try:
            st.session_state.data = json.load(uploaded_file)
            # Resetta lo stato se un nuovo file viene caricato
            st.session_state.step = 1
            st.session_state.keyword_widgets_map = {}
            # Pulisce anche gli stati degli altri widget per evitare dati vecchi
            for key in ["editor_common", "editor_gap", "raw_custom_keywords", "raw_tov_text", "raw_additional_info"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun() # Forza il refresh dell'app con i nuovi dati
        except json.JSONDecodeError as e:
            st.error(f"❌ Errore nel parsing del JSON: {e}")
            st.stop()
    else:
        st.info("⏳ Carica un file JSON per procedere con l'analisi.")
        st.stop()

data = st.session_state.data

def go_next():
    st.session_state.step = min(st.session_state.step + 1, 5)

def go_back():
    st.session_state.step = max(st.session_state.step - 1, 1)

# --- Step indicator ---
st.markdown(f"## Step {st.session_state.step}", unsafe_allow_html=True)

# === STEP 1 ===
if st.session_state.step == 1:
    st.markdown(separator, unsafe_allow_html=True)
    query = data.get("query", "").strip()
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
        organic = data.get("organic", [])
        if organic:
            for it in organic[:10]:
                url_raw = it.get("URL", "")
                p = urlparse(url_raw)
                st.markdown(f"""
                <div style="margin-bottom: 1.5rem;">
                    <div style="display:flex; align-items:center; margin-bottom:0.2rem;">
                        <img src="https://www.google.com/s2/favicons?domain={p.netloc}&sz=32" onerror="this.src='https://www.google.com/favicon.ico';" style="width:20px; height:20px; margin-right:0.5rem;"/>
                        <span style="font-size:14px; color:#4d5156;">{p.scheme}://{p.netloc}</span>
                    </div>
                    <a href="{url_raw}" style="color:#1a0dab; text-decoration:none; font-size:20px;">{it.get("Meta Title", "")}</a>
                    <div style="font-size:14px; color:#4d5156; line-height:1.4;">{it.get("Meta Description", "")}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("⚠️ Nessun risultato organico trovato.")
            
    with col_paa:
        st.markdown('<h5>People Also Ask</h5>', unsafe_allow_html=True)
        paa = data.get("people_also_ask", [])
        if paa:
            for q in paa:
                st.markdown(f"- {q}")
        else:
            st.write("_Nessuna PAA trovata_")
        st.markdown('<h5 style="margin-top:1.5rem;">Ricerche Correlate</h5>', unsafe_allow_html=True)
        related = data.get("related_searches", [])
        if related:
            for r in related:
                st.markdown(f"- {r}")
        else:
            st.write("_Nessuna ricerca correlata trovata_")
            
    st.button("Avanti", on_click=go_next, key="next_btn", type="primary")

# === STEP 2 ===
elif st.session_state.step == 2:
    st.markdown(separator, unsafe_allow_html=True)
    st.markdown('<h3 style="margin-top:0; padding-top:0;">Seleziona le singole keywords per l\'analisi</h3>', unsafe_allow_html=True)
    keyword_mining = data.get("keyword_mining", [])
    if keyword_mining:
        st.session_state.keyword_widgets_map.clear()
        for i, entry in enumerate(keyword_mining):
            original_label = entry.get("Categoria Keyword", "")
            display_label = clean_label(original_label)
            kws = [k.strip(" `") for k in entry.get("Keywords / Concetti / Domande", "").split(",")]
            widget_key = f"ms_keyword_{i}"
            st.session_state.keyword_widgets_map[widget_key] = display_label
            st.markdown(f'<p style="font-size:1.25rem; font-weight:600; margin:1rem 0 0.75rem 0;">{display_label}</p>', unsafe_allow_html=True)
            st.multiselect(label="", options=kws, default=kws, key=widget_key)
        c1, c2, _ = st.columns([1,1,6])
        with c1:
            st.button("Indietro", on_click=go_back, key="back_btn")
        with c2:
            st.button("Avanti", on_click=go_next, key="next2_btn", type="primary")
    else:
        st.warning("⚠️ Non ho trovato la sezione di Keyword Mining nel JSON.")
        st.button("Indietro", on_click=go_back, key="back_btn_empty")

# === STEP 3: Common Ground & Content Gap ===
elif st.session_state.step == 3:
    st.markdown(separator, unsafe_allow_html=True)
    st.markdown('<h3 style="margin-top:0.5rem; padding-top:0;">Analisi Semantica Avanzata</h3>', unsafe_allow_html=True)
    
    # Prepara il DataFrame per Common Ground
    common_data = data.get("common_ground", [])
    df_common = pd.DataFrame(common_data)
    if not df_common.empty:
        df_common.insert(0, "Seleziona", False)
    st.subheader("Common Ground Analysis")
    st.data_editor(df_common, use_container_width=True, hide_index=True, key="editor_common", height=300)

    # Prepara il DataFrame per Content Gap
    gap_data = data.get("content_gap", [])
    df_gap = pd.DataFrame(gap_data)
    if not df_gap.empty:
        df_gap.insert(0, "Seleziona", False)
    st.subheader("Content Gap Opportunity")
    st.data_editor(df_gap, use_container_width=True, hide_index=True, key="editor_gap", height=300)
    
    c1, c2, _ = st.columns([1,1,6])
    with c1:
        st.button("Indietro", on_click=go_back, key="back_btn_3")
    with c2:
        st.button("Avanti", on_click=go_next, key="next3_btn", type="primary")

# === STEP 4: Contestualizzazione e keyword personalizzate ===
elif st.session_state.step == 4:
    st.markdown(separator, unsafe_allow_html=True)
    st.markdown('<h3 style="margin-top:0.5rem; padding-top:0;">Contestualizzazione Contenuto</h3>', unsafe_allow_html=True)
    col1, col2 = st.columns(2, gap="small")
    with col1:
        st.selectbox("Contesto", ["-- Seleziona --", "E-commerce", "Magazine / Testata Giornalistica"], key="context_select")
    with col2:
        dest_options = {"-- Seleziona --": ["-- Seleziona --"], "E-commerce": ["-- Seleziona --", "Product Listing Page (PLP)", "Product Detail Page (PDP)", "Guida all'Acquisto", "Articolo del Blog"], "Magazine / Testata Giornalistica": ["-- Seleziona --", "Articolo del Blog"]}
        st.selectbox("Destinazione Contenuto", dest_options.get(st.session_state.context_select, ["-- Seleziona --"]), key="dest_select")
    
    st.markdown("---")
    if st.toggle("Aggiungi Keyword Personalizzate", value=False, key="custom_kw_toggle"):
        st.text_area("Incolla le tue keyword (una per riga)", height=120, placeholder="keyword1\nkeyword2\nkeyword3", key="raw_custom_keywords")
    
    st.markdown("---")
    if st.toggle("Aggiungi ToV / Stile del Cliente", value=False, key="tov_toggle"):
        num_tov = st.number_input("Quanti esempi di ToV vuoi inserire?", min_value=1, max_value=6, value=1, key="tov_count")
        tov_list = [st.text_area(f"Esempio ToV #{i+1}", height=120, key=f"tov_example_{i+1}") for i in range(num_tov)]
        st.session_state.raw_tov_text = "; ".join(tov_list)
        
    st.markdown("---")
    if st.toggle("Aggiungi Informazioni Aggiuntive", value=False, key="info_toggle"):
        st.text_area("Inserisci ulteriori informazioni", height=120, placeholder="Dettagli aggiuntivi...", key="raw_additional_info")
        
    c1, c2, _ = st.columns([1,1,6])
    with c1:
        st.button("Indietro", on_click=go_back, key="back_btn_4")
    with c2:
        st.button("Avanti", on_click=go_next, key="next4_btn", type="primary")

# === STEP 5: Recap Finale ===
elif st.session_state.step == 5:
    st.markdown(separator, unsafe_allow_html=True)
    st.markdown('<h3 style="margin-top:0.5rem; padding-top:0;">Recap delle Scelte</h3>', unsafe_allow_html=True)
    
    recap_data = {}
    
    # Dati di base
    recap_data["Query"] = data.get("query", "")
    recap_data["Country"] = data.get("country", "")
    recap_data["Language"] = data.get("language", "")

    # Analisi Strategica
    analysis_list = data.get("analysis_strategica", [])
    analysis_map = {clean_label(item.get("Caratteristica SEO", "")): clean_label(item.get("Analisi Sintetica", "")) for item in analysis_list}
    for key in ["Search Intent Primario", "Search Intent Secondario", "Target Audience & Leggibilità", "Tone of Voice (ToV)"]:
        recap_data[key] = re.sub(r"\s*\([^)]*\)", "", analysis_map.get(key, "")).strip()

    # Keyword Mining
    if "keyword_widgets_map" in st.session_state:
        for widget_key, display_label in st.session_state.keyword_widgets_map.items():
            selected_keywords = st.session_state.get(widget_key, [])
            recap_data[f"{display_label} Selezionate"] = ", ".join(selected_keywords)

    # Common Ground e Content Gap
    edited_common = st.session_state.get("editor_common", pd.DataFrame())
    if not edited_common.empty and "Seleziona" in edited_common.columns:
        common_selected = edited_common[edited_common["Seleziona"] == True].to_dict(orient="records")
        recap_data["Righe Common Ground Selezionate"] = len(common_selected)
    
    edited_gap = st.session_state.get("editor_gap", pd.DataFrame())
    if not edited_gap.empty and "Seleziona" in edited_gap.columns:
        gap_selected = edited_gap[edited_gap["Seleziona"] == True].to_dict(orient="records")
        recap_data["Righe Content Gap Selezionate"] = len(gap_selected)

    # Contestualizzazione
    recap_data["Contesto"] = st.session_state.get("context_select", "")
    recap_data["Destinazione"] = st.session_state.get("dest_select", "")
    recap_data["Keyword Personalizzate"] = st.session_state.get("raw_custom_keywords", "").replace('\n', ', ')
    recap_data["ToV Personalizzato"] = st.session_state.get("raw_tov_text", "")
    recap_data["Informazioni Aggiuntive"] = st.session_state.get("raw_additional_info", "")

    # Creazione DataFrame e visualizzazione
    df_recap = pd.DataFrame(recap_data.items(), columns=["Voce", "Valore"])
    st.table(df_recap)
    
    c1, c2, _ = st.columns([1,1,6])
    with c1:
        st.button("Indietro", on_click=go_back, key="back_btn_5")
