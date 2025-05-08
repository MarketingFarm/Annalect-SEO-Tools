import streamlit as st
from pages import seo_extractor, altro_tool

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

# Definizione delle pagine (tool) con pathnames unici
docs_pages = {
    "On-Page SEO": [
        st.Page(
            seo_extractor.main,
            title="🔍 SEO Extractor",
            pathname="seo_extractor"
        ),
        st.Page(
            altro_tool.main,
            title="🛠️ Altro Tool",
            pathname="altro_tool"
        )
    ],
    "Technical SEO": [
        # st.Page(tool2.main, title="🛠️ Tool A", pathname="tool_a"),
        # st.Page(tool3.main, title="🛠️ Tool B", pathname="tool_b")
    ],
    "Off-Page SEO": [
        # st.Page(tool4.main, title="🛠️ Tool C", pathname="tool_c"),
        # st.Page(tool5.main, title="🛠️ Tool D", pathname="tool_d")
    ]
}

# Renderizza il menu di navigazione nella sidebar
selected_page = st.navigation(
    docs_pages,
    position="sidebar",
    expanded=True
)

# Esegui la pagina selezionata
selected_page.run()
