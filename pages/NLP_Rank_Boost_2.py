import streamlit as st
import json
import re
from urllib.parse import urlparse

# --- Assumo st.set_page_config già invocato nel file principale ---

# Titolo e descrizione
st.title("📝 Analisi e Scrittura Contenuti SEO")
st.markdown(
    """
    In questa pagina puoi caricare il JSON generato dalla pagina di raccolta dati SEO,
    visualizzare i dettagli della query, le People Also Ask, le Ricerche Correlate,
    e i primi 10 risultati organici in stile SERP, quindi selezionare le singole keywords.
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

# --- Caricamento JSON ---
uploaded_file = st.file_uploader(
    "Carica il file JSON",
    type="json",
    help="Carica qui il file JSON generato dalla pagina precedente"
)
if uploaded_file is None:
    st.info("⏳ Carica un file JSON per procedere con l'analisi.")
    st.stop()

try:
    data = json.load(uploaded_file)
except json.JSONDecodeError as e:
    st.error(f"❌ Errore nel parsing del JSON: {e}")
    st.stop()

# Inizializzo lo step
if 'step' not in st.session_state:
    st.session_state.step = 1

def go_next():
    st.session_state.step = 2

def go_back():
    st.session_state.step = 1

# === STEP 1 ===
if st.session_state.step == 1:
    # primo separatore
    st.markdown(separator, unsafe_allow_html=True)

    # Dettagli della Query + Segnali E-E-A-T spostati qui
    query   = data.get("query", "").strip()
    country = data.get("country", "").strip()
    lang    = data.get("language", "").strip()
    st.markdown(
        '<h3 style="margin-top:0.5rem; padding-top:0;">Dettagli della Query</h3>',
        unsafe_allow_html=True
    )

    # preparo mappa di Analysis Strategica
    analysis_list = data.get("analysis_strategica", [])
    analysis_map = {}
    for item in analysis_list:
        raw_label = item.get("Caratteristica SEO", "")
        clean_label = re.sub(r"\*+", "", raw_label).strip()
        clean_value = re.sub(r"\*+", "", item.get("Analisi Sintetica", "")).strip()
        analysis_map[clean_label] = clean_value

    # estraggo il solo valore "Segnali E-E-A-T" senza parentesi
    raw_signals = analysis_map.get("Segnali E-E-A-T", "")
    signals_val = re.sub(r"\s*\([^)]*\)", "", raw_signals).strip()

    # colonne: Query, Country, Language, Segnali E-E-A-T
    cols_main = st.columns(4, gap="small")
    labels_main = ["Query", "Country", "Language", "Segnali E-E-A-T"]
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

    # margine inferiore
    st.markdown('<div style="margin-bottom:1rem;"></div>', unsafe_allow_html=True)

    # Titolo Analisi Strategica
    st.markdown(
        '<h3 style="margin-top:1.5rem; padding-top:0;">Analisi Strategica</h3>',
        unsafe_allow_html=True
    )

    # cards di Analisi Strategica (4 card, senza segnali)
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

    # Separatore e colonne organici / PAA
    st.markdown("""
<div style="
  border-top:1px solid #ECEDEE;
  margin: 1.5rem 0px 2rem 0rem;
  padding-top:1rem;
"></div>""", unsafe_allow_html=True)
    col_org, col_paa = st.columns([2,1], gap="small")

    with col_org:
        st.markdown(
            '<h3 style="margin-top:0; padding-top:0;">Risultati Organici (Top 10)</h3>',
            unsafe_allow_html=True
        )
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
        st.markdown(
            '<h3 style="margin-top:0; padding-top:0;">People Also Ask</h3>',
            unsafe_allow_html=True
        )
        paa = data.get("people_also_ask", [])
        if paa:
            pills = ''.join(
              f'<span style="background-color:#f7f8f9;padding:8px 12px;border-radius:4px;font-size:16px;margin-bottom:8px;">{q}</span>'
              for q in paa
            )
            st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:4px;">{pills}</div>', unsafe_allow_html=True)
        else:
            st.write("_Nessuna PAA trovata_")

        st.markdown(
            '<h3 style="margin-top:1rem; padding-top:0;">Ricerche Correlate</h3>',
            unsafe_allow_html=True
        )
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
            st.markdown(
                '<div style="display:flex;flex-wrap:wrap;gap:4px;">' +
                ''.join(spans) +
                '</div>',
                unsafe_allow_html=True
            )
        else:
            st.write("_Nessuna ricerca correlata trovata_")

    st.markdown("<div style='margin-top:2rem; text-align:right;'>", unsafe_allow_html=True)
    st.button("Avanti", on_click=go_next, key="next_btn")
    st.markdown("</div>", unsafe_allow_html=True)

# === STEP 2 ===
else:
    st.markdown(separator, unsafe_allow_html=True)
    st.markdown(
        '<h3 style="margin-top:0; padding-top:0;">Seleziona le singole keywords per l\'analisi</h3>',
        unsafe_allow_html=True
    )

    keyword_mining = data.get("keyword_mining", [])
    if keyword_mining:
        for entry in keyword_mining:
            raw_cat = entry.get("Categoria Keyword", "")
            # rimuovo tutto da "(" in poi
            label = re.sub(r"\(.*", "", raw_cat.strip("* ").strip())
            kws_str = entry.get("Keywords / Concetti / Domande", "")
            kws = [k.strip(" `") for k in kws_str.split(",") if k.strip(" `")]

            st.markdown(
                f'<p style="font-size:1.25rem; font-weight:600; margin:1rem 0 0.75rem 0;">'
                f'{label}'
                f'</p>',
                unsafe_allow_html=True
            )
            st.multiselect(
                label="",
                options=kws,
                default=kws,
                key=f"ms_{label.replace(" ", "_")}"
            )
        st.button("Indietro", on_click=go_back, key="back_btn")
    else:
        st.warning("⚠️ Non ho trovato la sezione di Keyword Mining nel JSON.")
