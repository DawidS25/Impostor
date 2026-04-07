import streamlit as st
from github_api import create_game_file, get_game_file, update_game_file

st.title("Test GitHub API")

game_code = "TEST123"

sample_data = {
    "code": game_code,
    "host": "Dawid",
    "players": ["Dawid"],
    "status": "waiting"
}

if st.button("Utwórz grę"):
    success, result = create_game_file(game_code, sample_data)
    if success:
        st.success("Gra została utworzona w repo.")
    else:
        st.error(f"Błąd tworzenia: {result}")

if st.button("Wczytaj grę"):
    success, data = get_game_file(game_code)
    if success:
        st.success("Gra wczytana.")
        st.json(data)
    else:
        st.error("Nie udało się wczytać gry.")

if st.button("Dodaj gracza"):
    success, data = get_game_file(game_code)
    if success:
        data["players"].append("NowyGracz")
        updated, result = update_game_file(game_code, data)
        if updated:
            st.success("Gra zaktualizowana.")
        else:
            st.error(f"Błąd aktualizacji: {result}")
    else:
        st.error("Najpierw utwórz grę.")