import requests
import streamlit as st

if "GIT_TOKEN" not in st.secrets:
    st.error("Brak GIT_TOKEN w secrets")
    st.stop()

token = st.secrets["GIT_TOKEN"]

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
    owner = "DawidS25"
    repo = "Impostor"
    branch = "main"
    return owner, repo, branch


def get_file_path(game_code):
    return f"data/games/{game_code}.json"


def create_game_file(game_code, game_data):
    """
    Tworzy nowy plik gry w repo.
    Jeśli plik już istnieje, GitHub zwróci błąd.
    """
    owner, repo, branch = get_repo_info()
    path = get_file_path(game_code)

    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents/{path}"

    content_json = json.dumps(game_data, ensure_ascii=False, indent=2)
    content_base64 = base64.b64encode(content_json.encode("utf-8")).decode("utf-8")

    payload = {
        "message": f"Create game {game_code}",
        "content": content_base64,
        "branch": branch
    }

    response = requests.put(url, headers=get_github_headers(), json=payload)

    if response.status_code in (200, 201):
        return True, response.json()
    return False, response.text


def get_game_file(game_code):
    """
    Pobiera dane gry z repo i zwraca słownik Pythona.
    """
    owner, repo, branch = get_repo_info()
    path = get_file_path(game_code)

    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents/{path}?ref={branch}"

    response = requests.get(url, headers=get_github_headers())

    if response.status_code == 200:
        data = response.json()
        content_base64 = data["content"]
        decoded = base64.b64decode(content_base64).decode("utf-8")
        return True, json.loads(decoded)

    return False, None


def get_game_file_with_sha(game_code):
    """
    Pobiera dane gry oraz SHA pliku potrzebne do aktualizacji.
    """
    owner, repo, branch = get_repo_info()
    path = get_file_path(game_code)

    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents/{path}?ref={branch}"

    response = requests.get(url, headers=get_github_headers())

    if response.status_code == 200:
        data = response.json()
        content_base64 = data["content"]
        decoded = base64.b64decode(content_base64).decode("utf-8")
        file_data = json.loads(decoded)
        file_sha = data["sha"]
        return True, file_data, file_sha

    return False, None, None


def update_game_file(game_code, game_data):
    """
    Aktualizuje istniejący plik gry.
    """
    owner, repo, branch = get_repo_info()
    path = get_file_path(game_code)

    success, _, file_sha = get_game_file_with_sha(game_code)
    if not success:
        return False, "Nie znaleziono pliku do aktualizacji."

    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents/{path}"

    content_json = json.dumps(game_data, ensure_ascii=False, indent=2)
    content_base64 = base64.b64encode(content_json.encode("utf-8")).decode("utf-8")

    payload = {
        "message": f"Update game {game_code}",
        "content": content_base64,
        "sha": file_sha,
        "branch": branch
    }

    response = requests.put(url, headers=get_github_headers(), json=payload)

    if response.status_code == 200:
        return True, response.json()
    return False, response.text


def game_exists(game_code):
    success, _ = get_game_file(game_code)
    return success