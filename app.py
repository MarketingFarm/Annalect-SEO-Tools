import streamlit as st

st.set_page_config(
    page_title="Multi-Tool Dashboard",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar: logo
st.sidebar.markdown(
    '<div style="text-align:center; margin-bottom:20px;">'
    '<img src="https://i.ibb.co/0yMG6kDs/logo.png" width="40"/>'
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
        # st.Page("pages/tool2.py", title="🛠️ Tool A"),
    ],
    "Off-Page SEO": [
        # st.Page("pages/tool4.py", title="🛠️ Tool C"),
    ]
}

# Renderizza il menu e avvia la pagina selezionata
selected_page = st.navigation(pages, position="sidebar", expanded=True)
selected_page.run()
