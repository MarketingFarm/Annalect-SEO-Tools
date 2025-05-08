import streamlit as st
import pandas as pd
from io import BytesIO

# Prova import nuova libreria OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError as e:
    OPENAI_AVAILABLE = False
    OPENAI_ERROR = str(e)

# --- Funzione di scraping con OpenAI (nuova API v1) ---
def scrape_with_openai(keyword: str, country: str, num: int) -> list[dict]:
    """
    Usa l'API di OpenAI client.chat.completions per simulare una ricerca SERP di Google.
    Ritorna lista di dict con 'Title' e 'URL'.
    """
    # Inizializza client
    client = OpenAI(api_key=st.secrets["OPENAI"]["api_key"])  # settata in .streamlit/secrets.toml

    system_prompt = (
        "You are a helpful assistant that provides the top organic Google search results. "
        "Given a query, country code (ISO2), and number of results, return ONLY a JSON array of objects with keys 'Title' and 'URL'."
    )
    user_prompt = (
        f"Query: {keyword}\n"
        f"Country code: {country}\n"
        f"Number of results: {num}\n"
        "Output ONLY the JSON array."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.0,
        max_tokens=500
    )
    content = response.choices[0].message.content.strip()
    try:
        # Carica JSON in pandas per validazione
        df = pd.read_json(content)
        records = df.to_dict(orient="records")
        return records[:num]
    except Exception as e:
        st.error(f"Errore parsing JSON da OpenAI: {e}")
        st.code(content, language='json')
        return []

# --- Interfaccia Streamlit ---
def main():
    st.title("🔎 Google SERP via OpenAI API")
    st.markdown("Simula una ricerca SERP con OpenAI e ottieni i primi risultati.")

    if not OPENAI_AVAILABLE:
        st.error(
            "Modulo openai non installato. "
            "Aggiungi `openai>=1.0.0` al tuo requirements.txt e ripubblica l'app."
            f" Dettaglio: {OPENAI_ERROR}"
        )
        return

    keyword = st.text_input("🔑 Keyword", "chatbot AI")
    country = st.text_input("🌍 Codice Paese (ISO2)", "IT").upper()
    num = st.slider("🔢 Numero di risultati", 1, 10, 5)

    if st.button("🚀 Cerca con OpenAI"):
        if not keyword.strip():
            st.error("Inserisci una keyword valida.")
            return

        with st.spinner("Chiamata a OpenAI in corso..."):
            results = scrape_with_openai(keyword, country, num)

        if results:
            df = pd.DataFrame(results)
            st.subheader("Risultati SERP")
            st.dataframe(df, use_container_width=True)

            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Results")
                ws = writer.sheets["Results"]
                for idx, col in enumerate(df.columns):
                    max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                    ws.column_dimensions[chr(65+idx)].width = min(max_len, 50)
            buf.seek(0)

            st.download_button(
                "📥 Download XLSX",
                data=buf.getvalue(),
                file_name=f"serp_{keyword.replace(' ','_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.warning("Nessun risultato restituito dalla API.")

if __name__ == "__main__":
    main()
