import requests
import streamlit as st

token = st.secrets["GIT_TOKEN"]

headers = {
    "Authorization": f"token {token}"
}

response = requests.get("https://api.github.com/user", headers=headers)

if response.status_code == 200:
    st.success("Token działa ✅")
    st.write(response.json()["login"])
else:
    st.error(f"Błąd: {response.status_code}")