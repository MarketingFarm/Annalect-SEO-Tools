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
  margin: 1.5rem 0;
  padding: 0rem 0px 1.5rem;
"></div>
""", unsafe_allow_html=True)

# --- Dettagli della Query come card ---
query   = data.get("query", "").strip()
country = data.get("country", "").strip()
lang    = data.get("language", "").strip()

st.markdown("### Dettagli della Query")
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

# --- Delimitatore tra dettagli e sezioni PAA/Organic ---
st.markdown("""
<div style="
  border-top:1px solid #ECEDEE;
  margin: 1.5rem 0;
  padding-top:1rem;
"></div>
""", unsafe_allow_html=True)

# --- Due colonne: sinistra risultati organici, destra PAA+related ---
col_org, col_paa = st.columns([2, 1], gap="small")

with col_org:
    st.subheader("Risultati Organici (Top 10)")
    organic = data.get("organic", [])
    if organic:
        # costruiamo l'HTML per i risultati organici, visibili tutti senza scroll aggiuntivo
        html = '<div style="padding-right:3.5rem;">'
        for item in organic[:10]:
            anchor = item.get("URL", "")
            m = re.search(r"href=['\"]([^'\"]+)['\"]", anchor)
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
                       'onerror="this.src=\'https://www.google.com/favicon.ico\';" '
                       'style="width:26px;height:26px;border-radius:50%;border:1px solid #d2d2d2;margin-right:0.5rem;"/>'
                    '<div>'
                      f'<div style="color:#202124;font-size:16px;line-height:20px;">{site_name}</div>'
                      f'<div style="color:#4d5156;font-size:14px;line-height:18px;">{pretty_url}</div>'
                    '</div>'
                  '</div>'
                  f'<a href="{url}" style="color:#1a0dab;text-decoration:none;font-size:23px;font-weight:500;">{title}</a>'
                  f'<div style="font-size:16px;line-height:22px;color:#474747;">{desc}</div>'
                '</div>'
            )
        html += '</div>'

        st.markdown(html, unsafe_allow_html=True)
    else:
        st.warning("⚠️ Nessun risultato organico trovato nel JSON.")

with col_paa:
    # People Also Ask come pillole
    st.subheader("💡 People Also Ask")
    paa = data.get("people_also_ask", [])
    if paa:
        st.markdown(
            '<div style="display:flex;flex-wrap:wrap;gap:4px;">'
            + ''.join(
                f'<span style="background-color:#E8F4FD;padding:4px 8px;border-radius:4px;font-family:Arial,sans-serif;font-size:14px;">{q}</span>'
                for q in paa
            )
            + '</div>',
            unsafe_allow_html=True
        )
    else:
        st.write("_Nessuna PAA trovata_")

    # Ricerche Correlate: evidenziamo la parte eccedente alla keyword principale in grassetto
    st.subheader("🔎 Ricerche Correlate")
    related = data.get("related_searches", [])
    if related:
        # Precompiliamo pattern regex per keyword principale, IGNORECASE
        q = query.strip()
        if q:
            pattern = re.compile(re.escape(q), re.IGNORECASE)
        else:
            pattern = None

        spans = []
        for r in related:
            text = r.strip()
            highlighted = ""
            if pattern:
                m = pattern.search(text)
                if m:
                    # Manteniamo esattamente il testo originale fino a m.end(), poi bold il resto
                    prefix = text[:m.end()]
                    suffix = text[m.end():]
                    if suffix:
                        # escape HTML in prefix/suffix? Qui assumiamo che i testi non contengano HTML pericoloso
                        highlighted = f"{prefix}<strong>{suffix}</strong>"
                    else:
                        # se non c'è suffisso, non boldare nulla
                        highlighted = prefix
                else:
                    highlighted = text
            else:
                highlighted = text

            # wrap in pill-style span
            span_html = (
                f'<span style="background-color:#f7f8f9;'
                f'padding:8px 12px; border-radius:4px; '
                f'font-size:16px; margin-bottom:8px;">'
                f'{highlighted}</span>'
            )
            spans.append(span_html)

        # Disporre le pillole con flex-wrap
        st.markdown(
            '<div style="display:flex;flex-wrap:wrap;gap:4px;">'
            + ''.join(spans)
            + '</div>',
            unsafe_allow_html=True
        )
    else:
        st.write("_Nessuna ricerca correlata trovata_")

# --- Delimitatore tra sezioni e keyword mining ---
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
