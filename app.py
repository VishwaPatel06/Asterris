"""Celestial Cartographers - entry point (Streamlit multipage app).

Run:  streamlit run app.py
"""
import streamlit as st

from components.theme import apply_theme

st.set_page_config(page_title="Celestial Cartographers", page_icon=":material/public:", layout="wide", initial_sidebar_state="expanded")
apply_theme()

pg = st.navigation(
    [
        st.Page("views/00_Home.py", title="Overview", icon=":material/home:", default=True),
        st.Page("views/01_Mission_Control.py", title="Mission Control", icon=":material/tune:"),
        st.Page("views/02_Planetary_Explorer.py", title="Planetary Explorer", icon=":material/language:"),
        st.Page("views/03_Analog_Discovery_Lab.py", title="Analog Discovery Lab", icon=":material/travel_explore:"),
        st.Page("views/04_Scientific_Comparison.py", title="Scientific Comparison", icon=":material/balance:"),
        st.Page("views/05_Mission_Engineering.py", title="Mission Engineering", icon=":material/precision_manufacturing:"),
        st.Page("views/06_Field_Campaign_Reports.py", title="Field Campaign", icon=":material/description:"),
        st.Page("views/07_AI_Research_Assistant.py", title="Research Assistant", icon=":material/forum:"),
    ],
    position="top",
)
pg.run()
