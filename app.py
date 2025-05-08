import streamlit as st

# Configurazione pagina
st.set_page_config(
    page_title="Multi-Tool Dashboard",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar: logo personalizzato
st.sidebar.markdown(
    '<div style="text-align:center; margin-bottom:20px;">'
    '<img src="https://i.ibb.co/0yMG6kDs/logo.png" width="40"/>'
    '</div>',
    unsafe_allow_html=True
)

# Definizione delle pagine (tool)
pages = {
    "On-Page SEO": [
        st.Page("pages/seo_extractor.py", title="🔍 SEO Extractor", icon="🔍"),
        st.Page("pages/altro_tool.py",    title="🛠️ Altro Tool",      icon="🛠️")
    ],
    "Technical SEO": [
        # st.Page("pages/tool2.py", title="🛠️ Tool A", icon="⚙️"),
        # st.Page("pages/tool3.py", title="🛠️ Tool B", icon="⚙️")
    ],
    "Off-Page SEO": [
        # st.Page("pages/tool4.py", title="🛠️ Tool C", icon="📈"),
        # st.Page("pages/tool5.py", title="🛠️ Tool D", icon="🔗")
    ]
}

# Renderizza il menu di navigazione nella sidebar
selected_page = st.navigation(
    pages,
    position="sidebar",
    expanded=True
)

# Esegui la pagina selezionata
selected_page.run()
