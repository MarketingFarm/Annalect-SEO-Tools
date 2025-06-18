import streamlit as st
import json
import pandas as pd
import re
from urllib.parse import urlparse

# Questa pagina assume che st.set_page_config sia già stata chiamata nel file principale

# Sidebar per il caricamento del file JSON
st.sidebar.title("Importazione JSON")
uploaded_file = st.sidebar.file_uploader(
    "Carica il file JSON di export SEO",
    type="json",
    help="Carica qui il file JSON generato dalla pagina precedente"
)

# Main area
st.title("📝 Analisi e Scrittura Contenuti SEO")
st.markdown(
    """
    In questa pagina puoi visualizzare i dettagli della query, i primi 10 risultati organici
    in stile SERP, e selezionare le singole keywords per l'analisi.
    """
)

if uploaded_file is not None:
    # Parsing del JSON
    try:
        data = json.load(uploaded_file)
    except json.JSONDecodeError as e:
        st.error(f"❌ Errore nel parsing del JSON: {e}")
        st.stop()

    # Accordion con JSON completo
    with st.expander("📂 Espandi per visualizzare il JSON completo"):
        st.json(data)

    # --- 1) Dettagli della Query ---
    st.subheader("Dettagli della Query")
    df_details = pd.DataFrame([{
        "Query":    data.get("query", ""),
        "Country":  data.get("country", ""),
        "Language": data.get("language", "")
    }])
    st.dataframe(df_details, hide_index=True)

    # --- 2) Risultati Organici (Top 10) in stile SERP ---
    organic = data.get("organic", [])
    if organic:
        st.subheader("Risultati Organici (Top 10)")

        # div contenitore per tutti i risultati
        html = """
<div style="
  background-color: #F8F9FB;
  border: 1px solid #ECEDEE;
  border-radius: 0.5rem;
  padding: 1rem;
">
"""
        for item in organic[:10]:
            # estraggo l'URL
            anchor = item.get("URL", "")
            m = re.search(r"href=['\"]([^'\"]+)['\"]", anchor)
            url = m.group(1) if m else anchor

            # formatto l'URL in segmenti separati da " › "
            parsed = urlparse(url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            path_segments = [seg for seg in parsed.path.split("/") if seg]
            pretty_url = base
            if path_segments:
                pretty_url += " › " + " › ".join(path_segments)

            # ricavo il nome del sito da www.xxx.yyy → xxx
            host = parsed.netloc
            parts = host.split('.')
            site_raw = parts[1] if len(parts) > 2 else parts[0]
            site_name = site_raw.replace('-', ' ').title()

            title = item.get("Meta Title", "")
            desc  = item.get("Meta Description", "")

            # aggiungo il singolo risultato all'HTML
            html += f"""
  <div style="margin-bottom:30px;">
    <div style="display:flex; align-items:center; margin-bottom:6px;">
      <img src="https://www.google.com/favicon.ico" style="
        width:26px;
        height:26px;
        border-radius:50%;
        border:1px solid #d2d2d2;
        margin-right:8px;
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
          font-weight: 400;
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
      font-weight: 400;
      line-height: 22px;
      color: #474747;
      margin-top: 0px;
    ">{desc}</div>
  </div>
"""
        html += "</div>"

        st.markdown(html, unsafe_allow_html=True)
    else:
        st.warning("⚠️ Nessun risultato organico trovato nel JSON.")

    # --- 3) Selezione singole keywords dalla tabella di Keyword Mining ---
    st.subheader("🔍 Seleziona le singole keywords per l'analisi")
    table_str = data.get("keyword_mining", "")
    lines = [line for line in table_str.split("\n") if line.strip()]
    if len(lines) >= 3:
        rows = []
        for line in lines[2:]:
            parts = [cell.strip() for cell in line.split("|") if cell.strip()]
            if len(parts) == 3:
                rows.append(parts)

        selected_keywords = {}
        for categoria, keywords_str, intento in rows:
            keywords_list = [kw.strip(" `") for kw in keywords_str.split(",") if kw.strip()]
            st.markdown(f"**{categoria}**  _(Intento: {intento})_")
            cols = st.columns([1, 9])
            chosen = []
            for kw in keywords_list:
                checked = cols[0].checkbox("", value=True, key=f"chk_{categoria}_{kw}")
                cols[1].write(kw)
                if checked:
                    chosen.append(kw)
            selected_keywords[categoria] = chosen

        st.subheader("✅ Keywords selezionate")
        st.json(selected_keywords)
    else:
        st.warning("⚠️ Non ho trovato una tabella di Keyword Mining nel JSON.")
else:
    st.sidebar.info("⏳ Carica un file JSON per procedere con l'analisi.")
