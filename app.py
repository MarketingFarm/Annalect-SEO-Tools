import streamlit as st

st.set_page_config(
    page_title="Multi-Tool Dashboard",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar: logo in alto
with st.sidebar:
    st.image(
        "https://i.ibb.co/C57SRppY/annalect-logo-400x113.png",
        use_container_width=True
    )
    st.markdown("---")  # separatore

# Definizione delle pagine (tool)
pages = {
    "On-Page SEO": [
        st.Page("pages/seo_extractor.py", title="🔍 SEO Extractor"),
        st.Page("pages/altro_tool.py",    title="🛠️ Altro Tool")
    ],
    "Technical SEO": [
        # aggiungi qui altri tool
    ],
    "Off-Page SEO": [
        # aggiungi qui altri tool
    ]
}

# Menu di navigazione (renderizzato nella sidebar, subito sotto il logo)
selected_page = st.navigation(
    pages,
    position="sidebar",
    expanded=True
)

# Esegui la pagina selezionata
selected_page.run()
