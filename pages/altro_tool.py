import streamlit as st
import pandas as pd
from io import BytesIO

# Prova import OpenAI
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError as e:
    OPENAI_AVAILABLE = False
    OPENAI_ERROR = str(e)

# --- Funzione di scraping con OpenAI ---
def scrape_with_openai(keyword: str, country: str, num: int) -> list[dict]:
    """
    Usa l'API di OpenAI per simulare una ricerca SERP di Google.
    Ritorna una lista di dizionari con 'Title' e 'URL'.
    """
    # Recupera chiave da secrets
    openai.api_key = st.secrets.get("OPENAI_API_KEY")
    messages = [
        {"role": "system", "content": (
            "You are a helpful assistant that provides the top organic Google search results. "
            "Given a query, country code (ISO2), and number of results, return a JSON array of objects with keys 'Title' and 'URL'."
        )},
        {"role": "user", "content": (
            f"Query: {keyword}\nCountry code: {country}\nNumber of results: {num}\nReturn only a JSON array."
        )}
    ]
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.0,
        max_tokens=500
    )
    content = response.choices[0].message.content.strip()
    try:
        df = pd.read_json(content)
        return df.to_dict(orient="records")[:num]
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
            "Aggiungi `openai` al tuo requirements.txt e ripubblica l'app. "
            f"Errore: {OPENAI_ERROR}"
        )
        return

    keyword = st.text_input("🔑 Keyword", "chatbot AI")
    country = st.text_input("🌍 Codice Paese (ISO2)", "IT")
    num = st.slider("🔢 Numero di risultati", 1, 10, 5)

    if st.button("🚀 Cerca con OpenAI"):
        if not keyword:
            st.error("Inserisci una keyword valida.")
            return
        with st.spinner("Chiamata a OpenAI in corso..."):
            results = scrape_with_openai(keyword, country.upper(), num)
        if results:
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Results")
            buf.seek(0)
            st.download_button(
                "📥 Download XLSX",
                data=buf.getvalue(),
                file_name=f"serp_{keyword.replace(' ','_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Nessun risultato dalla API.")

if __name__ == "__main__":
    main()
