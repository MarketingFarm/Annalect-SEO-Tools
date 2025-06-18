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

# Step 1: caricamento del file JSON
uploaded_file = st.file_uploader(
    "1. Carica il file JSON di export SEO",
    type="json",
    help="Carica qui il file JSON generato dalla pagina precedente"
)

if uploaded_file is not None:
    # Step 2: parsing del JSON
    try:
        data = json.load(uploaded_file)
    except json.JSONDecodeError as e:
        st.error(f"❌ Errore nel parsing del JSON: {e}")
        st.stop()

    # Accordion con JSON completo
    with st.expander("📂 Espandi per visualizzare il JSON completo"):
        st.json(data)

    # --- 1) Tabella con Query, Country, Language (senza indice) ---
    st.subheader("🔎 Dettagli della Query")
    df_details = pd.DataFrame([{
        "Query":    data.get("query", ""),
        "Country":  data.get("country", ""),
        "Language": data.get("language", "")
    }])
    st.dataframe(df_details, hide_index=True)

    # --- 2) Visualizzazione Top 10 Risultati Organici in stile SERP ---
    organic = data.get("organic", [])
    if organic:
        st.subheader("🖥️ Risultati Organici (Top 10)")
        for item in organic[:10]:
            # estraggo l'URL
            anchor = item.get("URL", "")
            m = re.search(r"href=['\"]([^'\"]+)['\"]", anchor)
            url = m.group(1) if m else anchor

            # ricavo il nome del sito da www.xxx.yyy → xxx
            parsed = urlparse(url)
            host = parsed.netloc
            parts = host.split('.')
            site_raw = parts[1] if len(parts) > 2 else parts[0]
            site_name = site_raw.replace('-', ' ').title()

            title = item.get("Meta Title", "")
            desc  = item.get("Meta Description", "")

            # Markup in stile Google SERP con 30px separazione
            st.markdown(f"""
<div style="margin-bottom:30px;">
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
    margin-bottom: 6px;
  ">{url}</div>
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
    margin-top: 4px;
  ">{desc}</div>
</div>
""", unsafe_allow_html=True)
    else:
        st.warning("⚠️ Nessun risultato organico trovato nel JSON.")

    # --- 3) Selezione singole keywords dalla tabella di Keyword Mining ---
    st.subheader("🔍 Seleziona le singole keywords per l'analisi")
    table_str = data.get("keyword_mining", "")
    lines = [line for line in table_str.split("\n") if line.strip()]
    if len(lines) >= 3:
        rows = []
        # salto header e riga di allineamento
        for line in lines[2:]:
            parts = [cell.strip() for cell in line.split("|") if cell.strip()]
            if len(parts) == 3:
                rows.append(parts)  # [Categoria, Keywords stringa, Intento]

        selected_keywords = {}
        for categoria, keywords_str, intento in rows:
            keywords_list = [kw.strip(" `") for kw in keywords_str.split(",") if kw.strip()]
            st.markdown(f"**{categoria}**  _(Intento: {intento})_")
            cols = st.columns([1, 9])
            chosen = []
            for kw in keywords_list:
                checked = cols[0].checkbox("", value=True, key=f"chk_{categoria}_{kw}")
                cols[1].write(kw)  # mostro la keyword senza elenco puntato
                if checked:
                    chosen.append(kw)
            selected_keywords[categoria] = chosen

        st.subheader("✅ Keywords selezionate")
        st.json(selected_keywords)
    else:
        st.warning("⚠️ Non ho trovato una tabella di Keyword Mining nel JSON.")

else:
    st.info("⏳ Carica un file JSON per procedere con l'analisi.")
