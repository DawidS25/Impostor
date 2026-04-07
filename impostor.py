import streamlit as st

token = st.secrets["GIT_TOKEN"]

st.write("Token wczytany:", token[:5] + "...")