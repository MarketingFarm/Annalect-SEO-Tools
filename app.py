import streamlit as st

st.set_page_config(
    page_title="Multi-Tool Dashboard",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar: logo
st.sidebar.markdown(
    '<div style="text-align:left; margin-bottom:20px;">'
    '<img src="https://i.ibb.co/C57SRppY/annalect-logo-400x113.png" width="150"/>'
    '</div>',
    unsafe_allow_html=True
)

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

# Renderizza il menu e avvia la pagina selezionata
selected_page = st.navigation(pages, position="sidebar", expanded=True)
selected_page.run()
