import streamlit as st
import json
import pandas as pd
import re
from urllib.parse import urlparse

# Questa pagina assume che st.set_page_config sia già stata chiamata nel file principale

st.title("📝 Analisi e Scrittura Contenuti SEO")
st.markdown(
    """
    In questa pagina puoi caricare il JSON generato dalla pagina di raccolta dati SEO,
    visualizzare i dettagli della query, i primi 10 risultati organici in stile SERP,
    e selezionare le singole keywords per l'analisi.
    """
)

# --- Delimitatore sotto alla descrizione della pagina ---
st.markdown("""
<div style="
  border-top:1px solid #ECEDEE;
  margin: 1rem 0;
  padding-top:1rem;
"></div>
""", unsafe_allow_html=True)

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

# --- Delimitatore sopra a "Dettagli della Query" ---
st.markdown("""
<div style="
  border-top:1px solid #ECEDEE;
  margin: 1rem 0;
  padding-top:1rem;
"></div>
""", unsafe_allow_html=True)

# --- Dettagli della Query ---
st.markdown('<h3 style="margin-top:0px;">Dettagli della Query</h3>', unsafe_allow_html=True)
df_details = pd.DataFrame([{
    "Query":    data.get("query", ""),
    "Country":  data.get("country", ""),
    "Language": data.get("language", "")
}])
st.dataframe(df_details, hide_index=True)

# --- Risultati Organici (Top 10) in stile SERP ---
organic = data.get("organic", [])
if organic:
    # container grigio con bordo arrotondato e padding
    html = """
<div style="
  background-color: #FFFFFF;
  border: 1px solid #ECEDEE;
  border-radius: 0.5rem;
  padding: 3rem;
">
  <h3 style="
    margin-top:0px;
    padding-top:0px;
    margin-bottom:1rem;
    font-family: Source Sans Pro, sans-serif;
    color: #202124;
    font-size: 28px;
    line-height: 24px;
  ">Risultati Organici (Top 10) 👇</h3>
"""
    for item in organic[:10]:
        # Estrazione URL
        anchor = item.get("URL", "")
        m = re.search(r"href=['\"]([^'\"]+)['\"]", anchor)
        url = m.group(1) if m else anchor

        # Pretty URL
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        segments = [seg for seg in parsed.path.split("/") if seg]
        pretty_url = base
        if segments:
            pretty_url += " › " + " › ".join(segments)

        # Site name
        host = parsed.netloc
        parts = host.split('.')
        raw = parts[1] if len(parts) > 2 else parts[0]
        site_name = raw.replace('-', ' ').title()

        title = item.get("Meta Title", "")
        desc  = item.get("Meta Description", "")

        html += f"""
  <div style="margin-bottom:2rem;">
    <div style="display:flex; align-items:center; margin-bottom:0.5rem;">
      <img src="https://www.google.com/favicon.ico" style="
        width:26px;
        height:26px;
        border-radius:50%;
        border:1px solid #d2d2d2;
        margin-right:0.5rem;
      "/>
      <div>
        <div style="
          font-family: Arial, sans-serif;
          color: #202124;
          font-size: 14px;
          line-height: 20px;
        ">{site_name}</div>
        <div style="
          font-family: Arial, sans-serif;
          color: #4d5156;
          font-size: 12px;
          line-height: 18px;
        ">{pretty_url}</div>
      </div>
    </div>
    <a href="{url}" style="
      color: #1a0dab;
      text-decoration: none;
      font-family: Arial, sans-serif;
      font-size: 20px;
      font-weight: 400;
    ">{title}</a>
    <div style="
      font-family: Arial, sans-serif;
      font-size: 14px;
      line-height: 22px;
      color: #474747;
      margin-top: 0.5rem;
    ">{desc}</div>
  </div>
"""
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)
else:
    st.warning("⚠️ Nessun risultato organico trovato nel JSON.")

# --- Delimitatore tra risultati e keyword mining ---
st.markdown("""
<div style="
  border-top:1px solid #ECEDEE;
  margin: 1.5rem 0;
  padding-top:1rem;
"></div>
""", unsafe_allow_html=True)

# --- Selezione delle keywords ---
st.subheader("🔍 Seleziona le singole keywords per l'analisi")
table_str = data.get("keyword_mining", "")
lines = [l for l in table_str.split("\n") if l.strip()]
if len(lines) >= 3:
    rows = []
    for line in lines[2:]:
        parts = [c.strip() for c in line.split("|") if c.strip()]
        if len(parts) == 3:
            rows.append(parts)

    selected = {}
    for cat, kw_str, intent in rows:
        kws = [k.strip(" `") for k in kw_str.split(",") if k.strip()]
        st.markdown(f"**{cat}** _(Intento: {intent})_")
        cols = st.columns([1, 9])
        chosen = []
        for kw in kws:
            chk = cols[0].checkbox("", value=True, key=f"chk_{cat}_{kw}")
            cols[1].write(kw)
            if chk:
                chosen.append(kw)
        selected[cat] = chosen

    st.subheader("✅ Keywords selezionate")
    st.json(selected)
else:
    st.warning("⚠️ Non ho trovato la tabella di Keyword Mining nel JSON.")
