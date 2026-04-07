import base64
import json
import requests
import streamlit as st

GITHUB_API_URL = "https://api.github.com"


def get_github_headers():
    token = st.secrets["GIT_TOKEN"]
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }


def get_repo_info():
    owner = "TWOJ_LOGIN"
    repo = "Impostor"
    branch = "master"
    return owner, repo, branch


def get_file_path(game_code):
    return f"data/games/{game_code}.json"


def game_exists(game_code):
    return False