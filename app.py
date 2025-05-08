import streamlit as st

st.set_page_config(
    page_title="Multi-Tool Dashboard",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Logo in alto nella sidebar
st.sidebar.image(
    "https://i.ibb.co/C57SRppY/annalect-logo-400x113.png",
    use_container_width=True
)
st.sidebar.markdown("---")  # linea di separazione

# Definizione delle pagine (tool)
pages = {
    "On-Page SEO": [
        st.Page("pages/seo_extractor.py", title="🔍 SEO Extractor"),
        st.Page("pages/altro_tool.py",    title="🛠️ Altro Tool")
    ],
    "Technical SEO": [
        # st.Page("pages/tool2.py", title="🛠️ Tool A"),
    ],
    "Off-Page SEO": [
        # st.Page("pages/tool4.py", title="🛠️ Tool C"),
    ]
}

# Menu di navigazione subito sotto il logo nella stessa sidebar
selected_page = st.navigation(
    pages,
    position="sidebar",
    expanded=True
)

# Esegui la pagina selezionata
selected_page.run()
