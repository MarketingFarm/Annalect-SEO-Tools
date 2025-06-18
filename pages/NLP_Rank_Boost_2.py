import streamlit as st
import json
import pandas as pd
import re

# Questa pagina assume che st.set_page_config sia già stato chiamato nel file principale

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

    # --- 1) Tabella con Query, Country, Language (senza index) ---
    st.subheader("🔎 Dettagli della Query")
    df_details = pd.DataFrame([{
        "Query": data.get("query", ""),
        "Country": data.get("country", ""),
        "Language": data.get("language", "")
    }])
    # Usa st.dataframe con hide_index=True per nascondere la colonna degli indici
    st.dataframe(df_details, hide_index=True)

    # --- 2) Visualizzazione Top 10 Risultati Organici in stile SERP ---
    organic = data.get("organic", [])
    if organic:
        st.subheader("🖥️ Risultati Organici (Top 10)")
        for item in organic[:10]:
            # Estrazione URL dal tag <a>
            anchor = item.get("URL", "")
            m = re.search(r"href=['\"]([^'\"]+)['\"]", anchor)
            url = m.group(1) if m else anchor
            title = item.get("Meta Title", "")
            desc = item.get("Meta Description", "")
            # Markup in stile Google SERP
            st.markdown(f"""
<div style="margin-bottom:20px; line-height:1.2;">
  <div style="font-size:14px; color:#006621;">{url}</div>
  <a href="{url}" style="font-size:18px; color:#1a0dab; text-decoration:none;">{title}</a>
  <div style="font-size:14px; color:#545454; margin-top:4px;">{desc}</div>
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
        # Skip header (0) and alignment (1), process from line 2 onward
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
                cols[1].write(kw)  # senza elenco puntato
                if checked:
                    chosen.append(kw)
            selected_keywords[categoria] = chosen

        st.subheader("✅ Keywords selezionate")
        st.json(selected_keywords)
    else:
        st.warning("⚠️ Non ho trovato una tabella di Keyword Mining nel JSON.")

else:
    st.info("⏳ Carica un file JSON per procedere con l'analisi.")
