import streamlit as st
import json
import re
import pandas as pd
from urllib.parse import urlparse

# Utility per creare uno slug coerente dal label, inclusi eventuali contenuti tra parentesi
def slugify_label(raw_label):
    # Rimuove eventuali asterischi
    label = re.sub(r"\*+", "", raw_label).strip()
    # Se c'è una parte tra parentesi, la include nel slug
    m = re.match(r"(.+?)\s*\(([^)]+)\)$", label)
    if m:
        base = m.group(1).strip()
        paren = m.group(2).strip()
        combined = f"{base} {paren}"
    else:
        combined = label
    # Sostituisce tutto ciò che non è alfanumerico con underscore
    slug = re.sub(r"[^0-9A-Za-z]+", "_", combined).strip("_")
    return slug

# --- Assumo st.set_page_config già invocato nel file principale ---

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
      /* Multiselect pill wrap */
      .stMultiSelect [data-baseweb="select"] span {
        max-width: none !important;
        white-space: normal !important;
        line-height: 1.3 !important;
      }
      /* Aumenta font delle etichette multiselect */
      .stMultiSelect > label {
        font-size: 1.25rem !important;
        font-weight: 500 !important;
      }
      /* Nasconde il label vuoto per evitare spazio extra */
      .stMultiSelect [data-testid="stWidgetLabel"] {
        display: none !important;
        margin: 0;
        padding: 0;
        height: 0;
      }
      .st-c6 {
        padding: 10px;
      }
      .stMultiSelect [data-baseweb="select"] span {
        background-color: rgb(84 87 101);
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

# --- Persistenza del JSON in session_state ---
if "data" not in st.session_state:
    st.session_state.data = None

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
        except json.JSONDecodeError as e:
            st.error(f"❌ Errore nel parsing del JSON: {e}")
            st.stop()
    else:
        st.info("⏳ Carica un file JSON per procedere con l'analisi.")
        st.stop()

data = st.session_state.data

# --- Session state per multi-step ---
if "step" not in st.session_state:
    st.session_state.step = 1

def go_next():
    st.session_state.step = min(st.session_state.step + 1, 5)

def go_back():
    st.session_state.step = max(st.session_state.step - 1, 1)

# --- Step indicator ---
st.markdown(f"## Step {st.session_state.step}", unsafe_allow_html=True)

# === STEP 1 ===
if st.session_state.step == 1:
    st.markdown(separator, unsafe_allow_html=True)

    query   = data.get("query", "").strip()
    country = data.get("country", "").strip()
    lang    = data.get("language", "").strip()

    st.markdown('<h3 style="margin-top:0.5rem; padding-top:0;">Dettagli della Query</h3>', unsafe_allow_html=True)

    # Analisi strategica mappata
    analysis_list = data.get("analysis_strategica", [])
    analysis_map = {
        re.sub(r"\*+", "", item.get("Caratteristica SEO", "")).strip():
        re.sub(r"\*+", "", item.get("Analisi Sintetica", "")).strip()
        for item in analysis_list
    }

    # Segnali E-E-A-T no parentesi
    raw_signals = analysis_map.get("Segnali E-E-A-T", "")
    signals_val = re.sub(r"\s*\([^)]*\)", "", raw_signals).strip()

    cols_main = st.columns(4, gap="small")
    labels_main = ["Query","Country","Language","Segnali E-E-A-T"]
    vals_main   = [query, country, lang, signals_val]
    for col, lbl, val in zip(cols_main, labels_main, vals_main):
        col.markdown(f"""
<div style="
  padding: 0.75rem 1.5rem;
  border: 1px solid rgb(255 166 166);
  border-radius: 0.5rem;
  background-color: rgb(255, 246, 246);
  margin-bottom: 0.5rem;
">
  <div style="font-size:0.8rem; color: rgb(255 70 70);">{lbl}</div>
  <div style="font-size:1.1rem; color:#202124; font-weight:500;">{val}</div>
</div>
""", unsafe_allow_html=True)
    st.markdown('<div style="margin-bottom:1rem;"></div>', unsafe_allow_html=True)

    st.markdown('<h3 style="margin-top:1.5rem; padding-top:0;">Analisi Strategica</h3>', unsafe_allow_html=True)

    labels_analysis = [
        "Search Intent Primario",
        "Search Intent Secondario",
        "Target Audience & Leggibilità",
        "Tone of Voice (ToV)"
    ]
    cols2 = st.columns(len(labels_analysis), gap="small")
    for c, lbl in zip(cols2, labels_analysis):
        raw = analysis_map.get(lbl, "")
        v = re.sub(r"\s*\([^)]*\)", "", raw).strip()
        c.markdown(f"""
<div style="
  padding: 0.75rem 1.5rem;
  border: 1px solid rgb(255 166 166);
  border-radius: 0.5rem;
  background-color: rgb(255, 246, 246);
">
  <div style="font-size:0.8rem; color: rgb(255 70 70);">{lbl}</div>
  <div style="font-size:1rem; color:#202124; font-weight:500;">{v}</div>
</div>
""", unsafe_allow_html=True)
    st.markdown('<div style="margin-bottom:1rem;"></div>', unsafe_allow_html=True)

    st.markdown("""
<div style="
  border-top:1px solid #ECEDEE;
  margin: 1.5rem 0px 2rem 0rem;
  padding-top:1rem;
"></div>""", unsafe_allow_html=True)
    col_org, col_paa = st.columns([2,1], gap="small")
    with col_org:
        st.markdown('<h3 style="margin-top:0; padding-top:0;">Risultati Organici (Top 10)</h3>', unsafe_allow_html=True)
        organic = data.get("organic", [])
        if organic:
            html = '<div style="padding-right:3.5rem;">'
            for it in organic[:10]:
                m   = re.search(r"href=[\'\"]([^\'\"]+)[\'\"]", it.get("URL",""))
                url = m.group(1) if m else it.get("URL","")
                p   = urlparse(url)
                base = f"{p.scheme}://{p.netloc}"
                segs = [s for s in p.path.split("/") if s]
                pretty = base + (" › " + " › ".join(segs) if segs else "")
                hn   = p.netloc.split('.')
                name = (hn[1] if len(hn)>2 else hn[0]).replace('-', ' ').title()
                title = it.get("Meta Title","")
                desc  = it.get("Meta Description","")
                html += (
                    '<div style="margin-bottom:2rem;">'
                      '<div style="display:flex;align-items:center;margin-bottom:0.2rem;">'
                        f'<img src="https://www.google.com/s2/favicons?domain={p.netloc}&sz=64" '
                           'onerror="this.src=\'https://www.google.com/favicon.ico\';" '
                           'style="width:26px;height:26px;border-radius:50%;border:1px solid #d2d2d2;margin-right:0.5rem;"/>'
                        '<div>'
                          f'<div style="color:#202124;font-size:16px;line-height:20px;">{name}</div>'
                          f'<div style="color:#4d5156;font-size:14px;line-height:18px;">{pretty}</div>'
                        '</div>'
                      '</div>'
                      f'<a href="{url}" style="color:#1a0dab;text-decoration:none;font-size:23px;font-weight:500;">{title}</a>'
                      f'<div style="font-size:16px;line-height:22px;color:#474747;">{desc}</div>'
                    '</div>'
                )
            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.warning("⚠️ Nessun risultato organico trovato.")
    with col_paa:
        st.markdown('<h3 style="margin-top:0; padding-top:0;">People Also Ask</h3>', unsafe_allow_html=True)
        paa = data.get("people_also_ask", [])
        if paa:
            pills = ''.join(
              f'<span style="background-color:#f7f8f9;padding:8px 12px;border-radius:4px;font-size:16px;margin-bottom:8px;">{q}</span>'
              for q in paa
            )
            st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:4px;">{pills}</div>', unsafe_allow_html=True)
        else:
            st.write("_Nessuna PAA trovata_")
        st.markdown('<h3 style="margin-top:1rem; padding-top:0;">Ricerche Correlate</h3>', unsafe_allow_html=True)
        related = data.get("related_searches", [])
        if related:
            pat = re.compile(re.escape(query), re.IGNORECASE) if query else None
            spans = []
            for r in related:
                txt = r.strip()
                if pat:
                    m = pat.search(txt)
                    if m:
                        pre, suf = txt[:m.end()], txt[m.end():]
                        txt = pre + (f"<strong>{suf}</strong>" if suf else "")
                spans.append(
                  f'<span style="background-color:#f7f8f9;padding:8px 12px;border-radius:4px;font-size:16px;margin-bottom:8px;">{txt}</span>'
                )
            st.markdown('<div style="display:flex;flex-wrap:wrap;gap:4px;">' + ''.join(spans) + '</div>', unsafe_allow_html=True)
        else:
            st.write("_Nessuna ricerca correlata trovata_")

    st.button("Avanti", on_click=go_next, key="next_btn")

# === STEP 2 ===
elif st.session_state.step == 2:
    st.markdown(separator, unsafe_allow_html=True)
    st.markdown('<h3 style="margin-top:0; padding-top:0;">Seleziona le singole keywords per l\'analisi</h3>', unsafe_allow_html=True)

    keyword_mining = data.get("keyword_mining", [])
    if keyword_mining:
        for entry in keyword_mining:
            raw_label = entry.get("Categoria Keyword", "")
            raw_label = re.sub(r"\*+", "", raw_label).strip()
            kws = [k.strip(" `") for k in entry.get("Keywords / Concetti / Domande", "").split(",")]
            slug = slugify_label(raw_label)
            widget_key = f"ms_{slug}"
            st.markdown(
                f'<p style="font-size:1.25rem; font-weight:600; margin:1rem 0 0.75rem 0;">{raw_label}</p>',
                unsafe_allow_html=True
            )
            st.multiselect(label="", options=kws, default=kws, key=widget_key)
        c1, c2 = st.columns(2)
        with c1:
            st.button("Indietro", on_click=go_back, key="back_btn")
        with c2:
            st.button("Avanti", on_click=go_next, key="next2_btn")
    else:
        st.warning("⚠️ Non ho trovato la sezione di Keyword Mining nel JSON.")

# === STEP 3: Common Ground & Content Gap ===
elif st.session_state.step == 3:
    st.markdown(separator, unsafe_allow_html=True)
    st.markdown('<h3 style="margin-top:0.5rem; padding-top:0;">Analisi Semantica Avanzata</h3>', unsafe_allow_html=True)

    common = data.get("common_ground", [])
    gap    = data.get("content_gap", [])

    df_common = pd.DataFrame(common)
    df_common.insert(0, "Seleziona", False)
    st.subheader("Common Ground Analysis")
    edited_common = st.data_editor(
        df_common,
        num_rows=len(df_common),
        use_container_width=True,
        hide_index=True,
        key="editor_common"
    )
    st.session_state.edited_common = edited_common

    df_gap = pd.DataFrame(gap)
    df_gap.insert(0, "Seleziona", False)
    st.subheader("Content Gap Opportunity")
    edited_gap = st.data_editor(
        df_gap,
        num_rows=len(df_gap),
        use_container_width=True,
        hide_index=True,
        key="editor_gap"
    )
    st.session_state.edited_gap = edited_gap

    c1, c2 = st.columns(2)
    with c1:
        st.button("Indietro", on_click=go_back, key="back_btn_3")
    with c2:
        st.button("Avanti", on_click=go_next, key="next3_btn")

# === STEP 4: Contestualizzazione e keyword personalizzate ===
elif st.session_state.step == 4:
    st.markdown(separator, unsafe_allow_html=True)
    st.markdown('<h3 style="margin-top:0.5rem; padding-top:0;">Contestualizzazione Contenuto</h3>', unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="small")
    with col1:
        context = st.selectbox("Contesto",
                               ["-- Seleziona --", "E-commerce", "Magazine / Testata Giornalistica"],
                               key="context_select")
    with col2:
        dest_options = {
            "-- Seleziona --": ["-- Seleziona --"],
            "E-commerce": ["-- Seleziona --", "Product Listing Page (PLP)", "Product Detail Page (PDP)", "Guida all'Acquisto", "Articolo del Blog"],
            "Magazine / Testata Giornalistica": ["-- Seleziona --", "Articolo del Blog"]
        }
        destino = st.selectbox("Destinazione Contenuto",
                               dest_options.get(context, ["-- Seleziona --"]),
                               key="dest_select")

    custom_toggle = st.toggle("Keyword Personalizzate", value=False, key="custom_kw_toggle")
    if custom_toggle:
        raw_input = st.text_area("Incolla le tue keyword (una per riga)",
                                 height=120,
                                 placeholder="keyword1\nkeyword2\nkeyword3",
                                 key="raw_custom_kw")
        st.session_state.raw_custom_keywords = raw_input.splitlines()

    tov_toggle = st.toggle("ToV / Stile del Cliente", value=False, key="tov_toggle")
    if tov_toggle:
        num_tov = st.selectbox("Quanti esempi di ToV vuoi inserire?", list(range(1,7)), index=0, key="tov_count")
        rows = (num_tov + 1) // 2
        idx = 1
        for _ in range(rows):
            cols = st.columns(2, gap="small")
            for col in cols:
                if idx <= num_tov:
                    col.text_area(f"Esempio ToV #{idx}", height=120, key=f"tov_example_{idx}")
                    idx += 1
        tov_list = [st.session_state.get(f"tov_example_{i}", "") for i in range(1, num_tov+1)]
        st.session_state.raw_tov_text = tov_list

    info_toggle = st.toggle("Informazioni Aggiuntive", value=False, key="info_toggle")
    if info_toggle:
        info_input = st.text_area("Inserisci ulteriori informazioni",
                                  height=120,
                                  placeholder="Dettagli aggiuntivi...",
                                  key="raw_info_input")
        st.session_state.raw_additional_info = info_input

    c1, c2 = st.columns(2)
    with c1:
        st.button("Indietro", on_click=go_back, key="back_btn_4")
    with c2:
        st.button("Avanti", on_click=go_next, key="next4_btn")

# === STEP 5: Recap Finale ===
elif st.session_state.step == 5:
    st.markdown(separator, unsafe_allow_html=True)
    st.markdown('<h3 style="margin-top:0.5rem; padding-top:0;">Recap delle Scelte</h3>', unsafe_allow_html=True)

    analysis_list = data.get("analysis_strategica", [])
    analysis_map = {
        re.sub(r"\*+", "", item.get("Caratteristica SEO", "")).strip():
        re.sub(r"\*+", "", item.get("Analisi Sintetica", "")).strip()
        for item in analysis_list
    }

    edited_common = st.session_state.get("edited_common", pd.DataFrame())
    edited_gap    = st.session_state.get("edited_gap", pd.DataFrame())
    common_selected = (
        edited_common[edited_common["Seleziona"]==True].to_dict(orient="records")
        if not edited_common.empty else []
    )
    gap_selected = (
        edited_gap[edited_gap["Seleziona"]==True].to_dict(orient="records")
        if not edited_gap.empty else []
    )

    recap = {
        "Query": data.get("query",""),
        "Country": data.get("country",""),
        "Language": data.get("language",""),
        "Segnali E-E-A-T": re.sub(r"\s*\([^)]*\)","", analysis_map.get("Segnali E-E-A-T","")).strip(),
        "Search Intent Primario": re.sub(r"\s*\([^)]*\)","", analysis_map.get("Search Intent Primario","")).strip(),
        "Search Intent Secondario": re.sub(r"\s*\([^)]*\)","", analysis_map.get("Search Intent Secondario","")).strip(),
        "Target Audience & Leggibilità": re.sub(r"\s*\([^)]*\)","", analysis_map.get("Target Audience & Leggibilità","")).strip(),
        "Tone of Voice (ToV)": re.sub(r"\s*\([^)]*\)","", analysis_map.get("Tone of Voice (ToV)","")).strip(),
        "People Also Ask": ", ".join(data.get("people_also_ask", [])),
        "Ricerche Correlate": ", ".join(data.get("related_searches", [])),
        "Organic Titles": "; ".join([it.get("Meta Title","") for it in data.get("organic",[])[:10]]),
        "Organic Descriptions": "; ".join([it.get("Meta Description","") for it in data.get("organic",[])[:10]]),
        "Righe Common Ground Selezionate": ", ".join(str(r) for r in common_selected),
        "Righe Content Gap Selezionate": ", ".join(str(r) for r in gap_selected),
        "Contesto": st.session_state.get("context_select",""),
        "Destinazione": st.session_state.get("dest_select",""),
        "Keyword Personalizzate": ", ".join(st.session_state.get("raw_custom_keywords", [])),
        "ToV Personalizzato": "; ".join(st.session_state.get("raw_tov_text", [])),
        "Informazioni Aggiuntive": st.session_state.get("raw_additional_info", "")
    }

    # Aggiungo le selezioni di keyword mining con i nomi esatti dal JSON
    for entry in data.get("keyword_mining", []):
        raw_label = entry.get("Categoria Keyword", "")
        raw_label = re.sub(r"\*+", "", raw_label).strip()
        slug = slugify_label(raw_label)
        widget_key = f"ms_{slug}"
        selected = st.session_state.get(widget_key, [])
        recap[f"{raw_label} Selezionate"] = ", ".join(selected)

    df_recap = pd.DataFrame([recap]).T.reset_index()
    df_recap.columns = ["Voce", "Valore"]
    st.table(df_recap)

    st.button("Indietro", on_click=go_back, key="back_btn_5")
