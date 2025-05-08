import streamlit as st
from pages import seo_extractor, altro_tool

st.set_page_config(
    page_title="Multi-Tool Dashboard",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 1) Logo in alto
st.sidebar.image(
    "https://i.ibb.co/C57SRppY/annalect-logo-400x113.png",
    use_container_width=True
)
st.sidebar.markdown("---")

# 2) Menu “manuale” (sezione → tool)
menu = {
    "On-Page SEO": {
        "🔍 SEO Extractor": seo_extractor.main,
        "🛠️ Altro Tool": altro_tool.main
    },
    "Technical SEO": {
        # "🛠️ Tool A": tool_a.main,
        # …
    },
    "Off-Page SEO": {
        # "🛠️ Tool C": tool_c.main,
        # …
    }
}

section = st.sidebar.radio("Sezione", list(menu.keys()))
tool_label = st.sidebar.radio("", list(menu[section].keys()))
run_fn = menu[section][tool_label]

# 3) Esegui il tool selezionato
run_fn()
