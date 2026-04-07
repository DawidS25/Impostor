import random
import string
import streamlit as st

from github_api import create_game_file, get_game_file, update_game_file, game_exists


# ------------------- SESSION STATE ------------------- #
if "screen" not in st.session_state:
    st.session_state.screen = "start"

if "player_name" not in st.session_state:
    st.session_state.player_name = ""

if "game_code" not in st.session_state:
    st.session_state.game_code = ""

if "is_host" not in st.session_state:
    st.session_state.is_host = False


# ------------------- HELPERS ------------------- #
def generate_game_code(length=6):
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
        if not game_exists(code):
            return code


def go_to_lobby(game_code, player_name, is_host=False):
    st.session_state.game_code = game_code
    st.session_state.player_name = player_name
    st.session_state.is_host = is_host
    st.session_state.screen = "lobby"


# ------------------- UI ------------------- #
st.title("Impostor")

if st.session_state.screen == "start":
    st.subheader("Wybierz opcję")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("HOST", use_container_width=True):
            st.session_state.screen = "host"

    with col2:
        if st.button("DOŁĄCZ", use_container_width=True):
            st.session_state.screen = "join"


elif st.session_state.screen == "host":
    st.subheader("Tworzenie nowej gry")

    player_name = st.text_input("Podaj swoją nazwę", key="host_name")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Stwórz grę", use_container_width=True):
            if not player_name.strip():
                st.error("Podaj nazwę gracza.")
            else:
                game_code = generate_game_code()

                game_data = {
                    "code": game_code,
                    "host": player_name.strip(),
                    "players": [player_name.strip()],
                    "status": "waiting"
                }

                success, result = create_game_file(game_code, game_data)

                if success:
                    st.success(f"Gra utworzona. Kod gry: {game_code}")
                    go_to_lobby(game_code, player_name.strip(), is_host=True)
                    st.rerun()
                else:
                    st.error(f"Błąd tworzenia gry: {result}")

    with col2:
        if st.button("Powrót", use_container_width=True):
            st.session_state.screen = "start"
            st.rerun()


elif st.session_state.screen == "join":
    st.subheader("Dołącz do gry")

    player_name = st.text_input("Podaj swoją nazwę", key="join_name")
    game_code = st.text_input("Podaj kod gry", key="join_code").strip().upper()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Dołącz", use_container_width=True):
            if not player_name.strip():
                st.error("Podaj nazwę gracza.")
            elif not game_code:
                st.error("Podaj kod gry.")
            else:
                success, game_data = get_game_file(game_code)

                if not success:
                    st.error("Gra o takim kodzie nie istnieje.")
                else:
                    if player_name.strip() in game_data["players"]:
                        st.warning("Gracz o tej nazwie już jest w tej grze.")
                    else:
                        game_data["players"].append(player_name.strip())
                        updated, result = update_game_file(game_code, game_data)

                        if updated:
                            st.success("Dołączono do gry.")
                            go_to_lobby(game_code, player_name.strip(), is_host=False)
                            st.rerun()
                        else:
                            st.error(f"Błąd dołączania: {result}")

    with col2:
        if st.button("Powrót", use_container_width=True):
            st.session_state.screen = "start"
            st.rerun()


elif st.session_state.screen == "lobby":
    game_code = st.session_state.game_code
    player_name = st.session_state.player_name
    is_host = st.session_state.is_host

    success, game_data = get_game_file(game_code)

    if not success:
        st.error("Nie udało się wczytać gry.")
    else:
        st.subheader("Lobby")
        st.write(f"**Kod gry:** {game_code}")
        st.write(f"**Twój nick:** {player_name}")
        st.write(f"**Host:** {game_data['host']}")
        st.write(f"**Status:** {game_data['status']}")

        st.write("### Gracze:")
        for player in game_data["players"]:
            st.write(f"- {player}")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Odśwież", use_container_width=True):
                st.rerun()

        with col2:
            if is_host:
                if st.button("Start gry", use_container_width=True):
                    game_data["status"] = "started"
                    updated, result = update_game_file(game_code, game_data)

                    if updated:
                        st.success("Gra wystartowała.")
                        st.rerun()
                    else:
                        st.error(f"Błąd startu gry: {result}")