import streamlit as st
import pandas as pd
from io import BytesIO
import openai

def scrape_with_openai(keyword: str, country: str, num: int) -> list[dict]:
    """
    Usa l'API di OpenAI per simulare una ricerca SERP di Google.
    Ritorna una lista di dizionari con 'Title' e 'URL'.
    """
    # Imposta la tua OpenAI API key
    openai.api_key = st.secrets.get("OPENAI_API_KEY")
    system_prompt = (
        "You are a helpful assistant that provides the top organic Google search results. "
        "For a given query, country code (using ISO 3166-1 alpha-2), and number of results, "
        "return a JSON array of objects with keys 'Title' and 'URL'."
    )
    user_prompt = (
        f"Query: {keyword}\n"
        f"Country code: {country}\n"
        f"Number of results: {num}\n"
        "Return only JSON array."
    )
    response = openai.ChatCompletion.create(
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
        results = pd.read_json(content)
        # assicuriamoci la struttura lista di dict
        records = results.to_dict(orient="records")
        return records[:num]
    except Exception as e:
        st.error(f"Errore parsing JSON da OpenAI: {e}")
        st.json(content)
        return []

# --- Streamlit UI ---
def main():
    st.title("🔎 Google SERP via OpenAI API")
    st.markdown(
        "Utilizza il modello OpenAI per simulare una ricerca SERP e ottenere i primi risultati organici."
    )
    keyword = st.text_input("🔑 Inserisci keyword", "chatbot AI")
    country = st.text_input("🌍 Codice Paese (ISO2)", "IT")
    num = st.slider("🔢 Numero risultati", 1, 10, 5)

    if st.button("🚀 Cerca con OpenAI"):
        if not keyword.strip():
            st.error("Inserisci una keyword valida.")
        else:
            with st.spinner("Chiamata a OpenAI in corso..."):
                data = scrape_with_openai(keyword, country.upper(), num)
            if data:
                df = pd.DataFrame(data)
                st.dataframe(df)
                buf = BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name='Results')
                buf.seek(0)
                st.download_button(
                    "📥 Download XLSX",
                    data=buf.getvalue(),
                    file_name=f"serp_{keyword.replace(' ','_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("Nessun risultato restituito dalla API.")

if __name__ == "__main__":
    main()
