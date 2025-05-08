import streamlit as st
from pages import seo_extractor, altro_tool

st.set_page_config(
    page_title="Multi-Tool Dashboard",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.sidebar.markdown(
    '<div style="text-align:center; margin-bottom:20px;">'
    '<img src="https://i.ibb.co/0yMG6kDs/logo.png" width="40"/>'
    '</div>',
    unsafe_allow_html=True
)

pages = {
    "On-Page SEO": [
        st.Page(seo_extractor.main, title="🔍 SEO Extractor"),
        st.Page(altro_tool.main,    title="🛠️ Altro Tool")
    ],
    # …
}

selected_page = st.navigation(pages, position="sidebar", expanded=True)
selected_page.run()
