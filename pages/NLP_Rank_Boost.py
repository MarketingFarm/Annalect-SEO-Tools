import streamlit as st
import pandas as pd
from openai import OpenAI

# --- INIEZIONE CSS per il bottone rosso ---
st.markdown("""
<style>
button {
  background-color: #e63946 !important;
  color: white !important;
}
</style>
""", unsafe_allow_html=True)

# --- Config OpenAI ---
# Assicurati di impostare la tua API key come variabile d'ambiente OPENAI_API_KEY
client = OpenAI()

# --- Modalità input testi ---
st.title("Estrazione Entità SEO con AI")
st.divider()

# Selezione numero di testi da analizzare
num_texts = st.selectbox("Numero di testi da analizzare", [1, 2, 3, 4, 5], index=0)

# Crea campi di testo dinamici
text_inputs = []
for i in range(num_texts):
    text = st.text_area(
        label=f"Testo {i+1}",
        placeholder="Incolla qui il testo da analizzare...",
        height=150
    )
    text_inputs.append(text)

# Pulsante di analisi
if st.button("Analizza Entità 🚀"):
    # Verifica input
    texts = [t.strip() for t in text_inputs if t.strip()]
    if not texts:
        st.error("Per favore, incolla almeno un testo da analizzare.")
    else:
        full_text = "\n---\n".join(texts)
        prompt = f"""
Analizza il seguente testo ed estrai solo le entità e i concetti chiave *veramente rilevanti* per l’ottimizzazione SEO, ovvero quelli che possono avere un impatto concreto sul posizionamento nei risultati di ricerca di Google. Prima di estrarre le entità analizza il/i testo/i e capisci qual’è l’intento di ricerca / topic ed estrai solo le entità correlate a quell’intento di ricerca / topic.

✅ Includi esclusivamente:
- Keyword con intento informazionale o commerciale
- Categorie di prodotto/servizio con volume di ricerca
- Brand conosciuti o potenzialmente ricercabili
- Temi o concetti ricorrenti che definiscono l’intento di ricerca

❌ Escludi:
- Sinonimi non strategici della stessa keyword
- Dettagli tecnici secondari (tessuti, colori, caratteristiche decorative, ecc.)
- Termini generici, emozionali o descrittivi non ricercabili

Restituisci le entità in tabella con tre colonne:
| Entità | Tipologia | Rilevanza semantica |
|--------|-----------|---------------------|
{full_text}
---
Per ogni entità, nella colonna “Rilevanza semantica” indica un valore numerico tra 0.00 e 1.00 (due decimali) che rappresenti l’importanza di quell’entità rispetto al topic complessivo. Estrai tutte le entità con una rilevanza semantica uguale o maggiore di 0.50.
"""
        with st.spinner("Analisi in corso..."):
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Sei un assistente esperto di SEO, NLU e analisi semantica."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=4000,
            )
        md = resp.choices[0].message.content
        # Parsing Markdown table in DataFrame
        lines = [l for l in md.splitlines() if l.startswith("|") and l.endswith("|")]
        if len(lines) <= 2:
            st.warning("Nessuna entità trovata con rilevanza ≥ 0.50.")
        else:
            data_lines = lines[2:]
            rows = []
            for row in data_lines:
                cells = [c.strip() for c in row.strip("|").split("|")]
                while len(cells) < 3:
                    cells.append("0.00")
                rows.append(cells[:3])
            df = pd.DataFrame(rows, columns=["Entità", "Tipologia", "Rilevanza semantica"])
            df["Rilevanza semantica"] = pd.to_numeric(df["Rilevanza semantica"], errors="coerce").fillna(0.0)
            st.subheader("Entità Estratte")
            st.dataframe(df, use_container_width=True)
            st.download_button(
                "Scarica entità (CSV)",
                df.to_csv(index=False).encode("utf-8"),
                file_name="seo_entities.csv",
                mime="text/csv"
            )
