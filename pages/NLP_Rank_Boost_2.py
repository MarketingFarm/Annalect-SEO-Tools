import streamlit as st
import json
import re
import pandas as pd
from urllib.parse import urlparse

# Questa pagina assume che st.set_page_config sia già stata chiamata nel file principale

st.title("📝 Analisi e Scrittura Contenuti SEO")
st.markdown(
    """
    In questa pagina puoi caricare il JSON generato dalla pagina di raccolta dati SEO,
    visualizzare i dettagli della query, le People Also Ask, le Ricerche Correlate,
    e i primi 10 risultati organici in stile SERP, quindi selezionare le singole keywords.
    """
)

# --- Separator standardizzato ---
separator = """
<div style="
  border-top:1px solid #ECEDEE;
  margin: 1rem 0;
  padding-top:1rem;
"></div>
"""

# sotto descrizione
st.markdown(separator, unsafe_allow_html=True)

# --- Caricamento file JSON ---
uploaded_file = st.file_uploader(
    "Carica il file JSON",
    type="json",
    help="Carica qui il file JSON generato dalla pagina precedente"
)
if uploaded_file is None:
    st.info("⏳ Carica un file JSON per procedere con l'analisi.")
    st.stop()

# --- Parsing JSON ---
try:
    data = json.load(uploaded_file)
except json.JSONDecodeError as e:
    st.error(f"❌ Errore nel parsing del JSON: {e}")
    st.stop()

# --- Separator prima di "Dettagli della Query" ---
st.markdown(separator, unsafe_allow_html=True)

# --- Dettagli della Query come card ---
query   = data.get("query", "").strip()
country = data.get("country", "").strip()
lang    = data.get("language", "").strip()

st.markdown('<h3 style="margin-top:0; padding-top:0;">Dettagli della Query</h3>', unsafe_allow_html=True)

cols = st.columns(3, gap="small")
labels = ["Query", "Country", "Language"]
values = [query, country, lang]

for col, label, val in zip(cols, labels, values):
    col.markdown(f"""
<div style="
  padding: 0.75rem 1rem;
  border: 1px solid rgb(254, 212, 212);
  border-radius: 0.5rem;
  background-color: rgb(255, 246, 246);
">
  <div style="font-size:0.8rem; color: rgb(255, 136, 136);">{label}</div>
  <div style="font-size:1.15rem; color:#202124; font-weight:500;">{val}</div>
</div>
""", unsafe_allow_html=True)

# margine inferiore di 1rem sotto alla riga delle card
st.markdown('<div style="margin-bottom:1rem;"></div>', unsafe_allow_html=True)

# --- Separator specifico prima di Risultati Organici ---
separator_organic = """
<div style="
  border-top:1px solid #ECEDEE;
  margin: 1rem 0px 1.75rem 0rem;
  padding-top:1rem;
"></div>
"""
st.markdown(separator_organic, unsafe_allow_html=True)

# --- Due colonne: sinistra risultati organici, destra PAA+related ---
col_org, col_paa = st.columns([2, 1], gap="small")

with col_org:
    st.markdown('<h3 style="margin-top:0; padding-top:0;">Risultati Organici (Top 10)</h3>', unsafe_allow_html=True)
    organic = data.get("organic", [])
    if organic:
        html = '<div style="padding-right:3.5rem;">'
        for item in organic[:10]:
            anchor = item.get("URL", "")
            m = re.search(r"href=[\'\"]([^\'\"]+)[\'\"]", anchor)
            url = m.group(1) if m else anchor

            parsed = urlparse(url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            segments = [seg for seg in parsed.path.split("/") if seg]
            pretty_url = base + (" › " + " › ".join(segments) if segments else "")

            host = parsed.netloc
            parts = host.split('.')
            raw = parts[1] if len(parts) > 2 else parts[0]
            site_name = raw.replace('-', ' ').title()

            title = item.get("Meta Title", "")
            desc  = item.get("Meta Description", "")

            html += (
                '<div style="margin-bottom:2rem;">'
                  '<div style="display:flex;align-items:center;margin-bottom:0.2rem;">'
                    f'<img src="https://www.google.com/s2/favicons?domain={parsed.netloc}&sz=64" '
