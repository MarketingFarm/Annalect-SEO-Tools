import streamlit as st
import json
import re
from urllib.parse import urlparse

# --- Assumo st.set_page_config già invocato nel file principale ---

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
    # singolo separatore all'inizio
    st.markdown(separator, unsafe_allow_html=True)

    # 1) Dettagli della Query
    query   = data.get("query", "").strip()
    country = data.get("country", "").strip()
    lang    = data.get("language", "").strip()
    st.markdown(
        '<h3 style="margin-top:0.5rem; padding-top:0;">Dettagli della Query</h3>',
        unsafe_allow_html=True
    )
    cols = st.columns(3, gap="small")
    for col, label, val in zip(cols, ["Query","Country","Language"], [query,country,lang]):
        col.markdown(f"""
<div style="
  padding: 0.75rem 1.5rem;
  border: 1px solid rgb(254, 212, 212);
  border-radius: 0.5rem;
  background-color: rgb(255, 246, 246);
  margin-bottom: 0.5rem;
">
  <div style="font-size:0.8rem; color: rgb(255, 136, 136);">{label}</div>
  <div style="font-size:1.15rem; color:#202124; font-weight:500;">{val}</div>
</div>
""", unsafe_allow_html=True)
    st.markdown('<div style="margin-bottom:1rem;"></div>', unsafe_allow_html=True)

    # 1b) Nuova riga di card da analysis_strategica
    analysis_strategica = data.get("analysis_strategica", "")
    # predispongo i campi
    fields = {
        "Search Intent Primario": "",
        "Search Intent Secondario": "",
        "Target Audience & Leggibilità": "",
        "Tone of Voice (ToV)": "",
        "Segnali E-E-A-T": ""
    }
    # regex per catturare | **Label** | **Valore** |
    pattern = re.compile(r"\|\s*\*\*(?P<label>.*?)\*\*\s*\|\s*\*\*(?P<val>.*?)\*\*")
    for m in pattern.finditer(analysis_strategica):
        lbl = m.group("label").strip()
        val = m.group("val").strip()
        if lbl in fields:
            fields[lbl] = val

    cols2 = st.columns(5, gap="small")
    for col, label in zip(cols2, fields.keys()):
        val = fields[label]
        col.markdown(f"""
<div style="
  padding: 0.75rem 1.5rem;
  border: 1px solid rgb(254, 212, 212);
  border-radius: 0.5rem;
  background-color: rgb(255, 246, 246);
  margin-bottom: 0.5rem;
">
  <div style="font-size:0.8rem; color: rgb(255, 136, 136);">{label}</div>
  <div style="font-size:1.15rem; color:#202124; font-weight:500;">{val}</div>
</div>
""", unsafe_allow_html=True)
    st.markdown('<div style="margin-bottom:1rem;"></div>', unsafe_allow_html=True)

    # 2) Separatore e colonne Organici / PAA+Correlate
    st.markdown("""
<div style="
  border-top:1px solid #ECEDEE;
  margin: 1rem 0px 2rem 0rem;
  padding-top:1rem;
"></div>
""", unsafe_allow_html=True)
    col_org, col_paa = st.columns([2,1], gap="small")

    with col_org:
        st.markdown(
            '<h3 style="margin-top:0; padding-top:0;">Risultati Organici (Top 10)</h3>',
            unsafe_allow_html=True
        )
        organic = data.get("organic",[])
        if organic:
            html = '<div style="padding-right:3.5rem;">'
            for it in organic[:10]:
                m = re.search(r"href=[\'\"]([^\'\"]+)[\'\"]", it.get("URL",""))
                url = m.group(1) if m else it.get("URL","")
                p = urlparse(url)
                base = f"{p.scheme}://{p.netloc}"
                seg = [s for s in p.path.split("/") if s]
                pretty = base + (" › " + " › ".join(seg) if seg else "")
                hn = p.netloc.split('.')
                name = (hn[1] if len(hn)>2 else hn[0]).replace('-',' ').title()
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
        paa = data.get("people_also_ask",[])
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
        related = data.get("related_searches",[])
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

    # pulsante avanti
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
            label = raw_cat.replace("*","").strip()
            kws_str = entry.get("Keywords / Concetti / Domande", "")
            options = [k.strip(" `") for k in kws_str.split(",") if k.strip()]
            st.markdown(
                f'<p style="font-size:1.25rem; font-weight:600; margin:1rem 0 0.75rem 0;">'
                f'{label}'
                f'</p>',
                unsafe_allow_html=True
            )
            st.multiselect(
                label="",
                options=options,
                default=options,
                key=f"ms_{label.replace(' ', '_')}"
            )
        st.button("Indietro", on_click=go_back, key="back_btn")
    else:
        st.warning("⚠️ Non ho trovato la sezione di Keyword Mining nel JSON.")
