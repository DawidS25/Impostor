import random
import string
import streamlit as st

from github_api import create_game_file, get_game_file, update_game_file, game_exists
from slowa import WORDS


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

def is_game_over(game_data):
    round_limit = game_data.get("settings", {}).get("round_limit")
    current_round = game_data.get("round", 0)

    if round_limit is None:
        return False

    return current_round >= round_limit

def start_game_logic(game_data):
    players = game_data["players"]

    if len(players) < 3:
        return False, "Do startu potrzeba co najmniej 3 graczy."

    settings = game_data.get("settings", {})
    selected_categories = settings.get("selected_categories", list(WORDS.keys()))
    hint_mode = settings.get("hint_mode", "off")

    available_categories = [cat for cat in selected_categories if cat in WORDS]

    if not available_categories:
        return False, "Brak dostępnych kategorii do losowania."

    impostor = random.choice(players)
    category = random.choice(available_categories)
    word = random.choice(WORDS[category])

    roles = {}
    for player in players:
        if player == impostor:
            roles[player] = {
                "role": "impostor"
            }

            if hint_mode == "category":
                roles[player]["category"] = category
            elif hint_mode == "hint":
                roles[player]["hint"] = "Brak podpowiedzi tekstowej na tym etapie"

        else:
            roles[player] = {
                "role": "player",
                "category": category,
                "word": word
            }

    game_data["status"] = "started"
    game_data["category"] = category
    game_data["word"] = word
    game_data["impostor"] = impostor
    game_data["roles"] = roles
    game_data["submissions"] = {player: [] for player in players}
    game_data["impostor_guess"] = ""
    game_data["guess_status"] = "none"
    game_data["votes"] = {}

    return True, game_data

def next_round_logic(game_data):
    players = game_data["players"]

    settings = game_data.get("settings", {})
    selected_categories = settings.get("selected_categories", list(WORDS.keys()))
    hint_mode = settings.get("hint_mode", "off")

    available_categories = [cat for cat in selected_categories if cat in WORDS]

    if not available_categories:
        return game_data

    impostor = random.choice(players)
    category = random.choice(available_categories)
    word = random.choice(WORDS[category])

    roles = {}
    for player in players:
        if player == impostor:
            roles[player] = {
                "role": "impostor"
            }

            if hint_mode == "category":
                roles[player]["category"] = category
            elif hint_mode == "hint":
                roles[player]["hint"] = "Brak podpowiedzi tekstowej na tym etapie"

        else:
            roles[player] = {
                "role": "player",
                "category": category,
                "word": word
            }

    game_data["status"] = "started"
    game_data["category"] = category
    game_data["word"] = word
    game_data["impostor"] = impostor
    game_data["roles"] = roles
    game_data["round"] = game_data.get("round", 1) + 1
    game_data["submissions"] = {player: [] for player in players}
    game_data["impostor_guess"] = ""
    game_data["guess_status"] = "none"
    game_data["votes"] = {}

    if is_game_over(game_data):
        game_data["status"] = "finished"

    return game_data

def get_winners(game_data):
    scores = game_data.get("scores", {})

    if not scores or len(scores) == 0:
        return []

    max_score = max(scores.values())
    return [player for player, score in scores.items() if score == max_score]

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
                    "status": "waiting",
                    "settings": {
                        "hint_mode": "off",
                        "round_limit": 10,
                        "selected_categories": list(WORDS.keys())
                    },
                    "round": 0,
                    "scores": {
                        player_name.strip(): 0
                    },
                    "submissions": {
                       player_name.strip(): []
                    },
                    "impostor_guess": "",
                    "guess_status": "none",
                    "votes": {}                  
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
                if success and "settings" not in game_data:
                    game_data["settings"] = {
                        "hint_mode": "off",
                        "round_limit": 10,
                        "selected_categories": list(WORDS.keys())
                    }
                    update_game_file(game_code, game_data)

                if not success:
                    st.error("Gra o takim kodzie nie istnieje.")
                else:
                    if player_name.strip() in game_data["players"]:
                        st.warning("Gracz o tej nazwie już jest w tej grze.")
                    else:
                        game_data["players"].append(player_name.strip())
                        game_data["scores"][player_name.strip()] = 0
                        
                        if "submissions" not in game_data:
                            game_data["submissions"] = {}
                        game_data["submissions"][player_name.strip()] = []
                        
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

    if success:
        changed = False

        if "settings" not in game_data:
            game_data["settings"] = {
                "hint_mode": "off",
                "round_limit": 10,
                "selected_categories": list(WORDS.keys())
            }
            changed = True

        if "scores" not in game_data:
            game_data["scores"] = {player: 0 for player in game_data.get("players", [])}
            changed = True

        if "round" not in game_data:
            game_data["round"] = 0
            changed = True
        
        if "submissions" not in game_data:
            game_data["submissions"] = {player: [] for player in game_data.get("players", [])}
            changed = True
        
        if "impostor_guess" not in game_data:
            game_data["impostor_guess"] = ""
            changed = True

        if "guess_status" not in game_data:
            game_data["guess_status"] = "none"
            changed = True        
        
        if "votes" not in game_data:
            game_data["votes"] = {}
            changed = True

        if changed:
            update_game_file(game_code, game_data)

    if not success:
        st.error("Nie udało się wczytać gry.")
    else:
        if game_data["status"] == "started":
            st.session_state.screen = "game"
            st.rerun()
        st.subheader("Lobby")
        st.write(f"**Kod gry:** {game_code}")
        st.write(f"**Twój nick:** {player_name}")
        st.write(f"**Host:** {game_data['host']}")
        st.write(f"**Status:** {game_data['status']}")

        st.write("### Gracze:")
        for player in game_data["players"]:
            st.write(f"- {player}")
        st.write("### Aktualne ustawienia")
        st.write(f"**Podpowiedzi:** {game_data['settings'].get('hint_mode', 'off')}")
        st.write(f"**Limit rund:** {game_data['settings'].get('round_limit', 10)}")
        st.write(f"**Kategorie:** {', '.join(game_data['settings'].get('selected_categories', []))}")

        if is_host:
            st.write("### Ustawienia gry")

            current_settings = game_data.get("settings", {})

            hint_mode_map = {
                "Wyłączone": "off",
                "Kategoria": "category",
                "Podpowiedź": "hint"
            }

            round_limit_map = {
                "5": 5,
                "10": 10,
                "20": 20,
                "Bez limitu": None
            }

            current_hint_value = current_settings.get("hint_mode", "off")
            current_round_value = current_settings.get("round_limit", 10)
            current_categories = current_settings.get("selected_categories", list(WORDS.keys()))

            hint_labels = list(hint_mode_map.keys())
            round_labels = list(round_limit_map.keys())

            current_hint_label = next(
                (label for label, value in hint_mode_map.items() if value == current_hint_value),
                "Wyłączone"
            )

            current_round_label = next(
                (label for label, value in round_limit_map.items() if value == current_round_value),
                "10"
            )

            selected_hint_label = st.selectbox(
                "Podpowiedzi dla impostora",
                hint_labels,
                index=hint_labels.index(current_hint_label)
            )

            selected_round_label = st.selectbox(
                "Liczba rund",
                round_labels,
                index=round_labels.index(current_round_label)
            )

            selected_categories = st.multiselect(
                "Aktywne kategorie",
                list(WORDS.keys()),
                default=current_categories
            )

            if st.button("Zapisz ustawienia", use_container_width=True):
                if not selected_categories:
                    st.error("Wybierz przynajmniej jedną kategorię.")
                else:
                    game_data["settings"]["hint_mode"] = hint_mode_map[selected_hint_label]
                    game_data["settings"]["round_limit"] = round_limit_map[selected_round_label]
                    game_data["settings"]["selected_categories"] = selected_categories

                    updated, result = update_game_file(game_code, game_data)

                    if updated:
                        st.success("Ustawienia zapisane.")
                        st.rerun()
                    else:
                        st.error(f"Błąd zapisu ustawień: {result}")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Odśwież", use_container_width=True):
                st.rerun()

        with col2:
            if is_host:
                if st.button("Start gry", use_container_width=True):
                    success_logic, result_logic = start_game_logic(game_data)

                    if not success_logic:
                        st.error(result_logic)
                    else:
                        updated, result = update_game_file(game_code, result_logic)

                        if updated:
                            st.success("Gra wystartowała.")
                            st.rerun()
                        else:
                            st.error(f"Błąd startu gry: {result}")

elif st.session_state.screen == "game":
    game_code = st.session_state.game_code
    player_name = st.session_state.player_name

    success, game_data = get_game_file(game_code)

    if not success:
        st.error("Nie udało się wczytać danych gry.")
        st.stop()

    if game_data.get("status") == "round_result":
        st.subheader("Koniec rundy")

        guess_status = game_data.get("guess_status", "none")
        impostor_name = game_data.get("impostor", "Nieznany")
        real_word = game_data.get("word", "")
        guessed_word = game_data.get("impostor_guess", "")

        if guess_status == "exact":
            st.success(f"Impostor ({impostor_name}) wygrał rundę, bo odgadł hasło idealnie.")
        elif guess_status == "approved_by_host":
            st.success(f"Impostor ({impostor_name}) wygrał rundę, bo host uznał zgadywanie.")
        elif guess_status == "rejected_by_host":
            st.info("Gracze wygrali rundę, ponieważ host odrzucił zgadywanie impostora.")
        else:
            st.info("Runda została zakończona.")

        st.write(f"**Prawidłowe hasło:** {real_word}")
        if guessed_word:
            st.write(f"**Zgadywanie impostora:** {guessed_word}")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Odśwież", key="refresh_round_result", use_container_width=True):
                st.rerun()

        with col2:
            if st.session_state.is_host:
                if st.button("Przejdź do następnej rundy", key="next_round_result", use_container_width=True):
                    new_data = next_round_logic(game_data)

                    updated, result = update_game_file(game_code, new_data)

                    if updated:
                        st.success("Rozpoczęto nową rundę.")
                        st.rerun()
                    else:
                        st.error(f"Błąd przejścia do następnej rundy: {result}")

        st.stop()

    if game_data.get("status") == "finished":
        st.subheader("Koniec gry")
        guess_status = game_data.get("guess_status", "none")
        impostor_name = game_data.get("impostor", "Nieznany")

        if guess_status in ["exact", "approved_by_host"]:
            st.success(f"Impostor ({impostor_name}) wygrał, bo poprawnie odgadł hasło.")
        elif guess_status == "rejected_by_host":
            st.info("Gracze wygrali, ponieważ host odrzucił zgadywanie impostora.")

        scores = game_data.get("scores", {})

        if not scores:
            scores = {player: 0 for player in game_data.get("players", [])}

        st.write("### Wyniki")
        for player, score in scores.items():
            st.write(f"**{player}:** {score} pkt")

        winners = get_winners({"scores": scores})

        st.write("### Zwycięzca / zwycięzcy")
        if winners:
            st.write(", ".join(winners))
        else:
            st.write("Brak danych o zwycięzcy")

        st.stop()

    st.subheader("Gra trwa")
    st.write(f"**Kod gry:** {game_code}")
    st.write(f"**Gracz:** {player_name}")
    st.write(f"**Runda:** {game_data.get('round', 1)}")

    if not success:
        st.error("Nie udało się wczytać danych gry.")
    else:
        if "roles" not in game_data:
            st.error("Brak 'roles' w game_data")
            st.stop()


        if player_name not in game_data["roles"]:
            st.error("Nie znaleziono Twojej roli.")
            st.stop()

        my_role = game_data["roles"][player_name]

        if my_role["role"] == "impostor":
            st.write("### DEBUG zgadywania")
            st.write("guess_status:", game_data.get("guess_status", "brak"))
            st.write("impostor_guess:", game_data.get("impostor_guess", "brak"))
           
            st.error("Jesteś IMPOSTOREM")
            st.write("Spróbuj wtopić się w grupę.")

            if "category" in my_role:
                st.write(f"**Podpowiedź - kategoria:** {my_role['category']}")

            if "hint" in my_role:
                st.write(f"**Podpowiedź:** {my_role['hint']}")


        else:
            st.success("Jesteś zwykłym graczem")
            st.write(f"**Kategoria:** {my_role['category']}")
            st.write(f"**Hasło:** {my_role['word']}")
        

        st.write("### Twoje hasła")

        with st.form(key=f"submission_form_{player_name}", clear_on_submit=True):
            submission_text = st.text_input(
                "Wpisz kolejne hasło / skojarzenie",
                key=f"submission_input_{player_name}"
            )

            submitted = st.form_submit_button("Dodaj hasło", use_container_width=True)

        if submitted:
            new_text = submission_text.strip()

            if not new_text:
                st.error("Wpisz hasło.")
            else:
                if "submissions" not in game_data:
                    game_data["submissions"] = {}

                if player_name not in game_data["submissions"]:
                    game_data["submissions"][player_name] = []

                if isinstance(game_data["submissions"][player_name], str):
                    old_value = game_data["submissions"][player_name].strip()
                    game_data["submissions"][player_name] = [old_value] if old_value else []

                game_data["submissions"][player_name].append(new_text)

                updated, result = update_game_file(game_code, game_data)

                if updated:
                    st.success("Hasło dodane.")
                    st.rerun()
                else:
                    st.error(f"Błąd zapisu hasła: {result}")

        st.write("### Hasła graczy")

        submissions = game_data.get("submissions", {})

        for player in game_data.get("players", []):
            player_text = submissions.get(player, "")
            if player_text:
                st.write(f"**{player}:** {player_text}")
            else:
                st.write(f"**{player}:** (brak)")



        if st.button("Odśwież", use_container_width=True):
            st.rerun()

        if st.session_state.is_host:
            if st.button("Przejdź do głosowania", use_container_width=True):
                game_data["status"] = "voting"

                updated, result = update_game_file(game_code, game_data)

                if updated:
                    st.success("Rozpoczęto głosowanie.")
                    st.rerun()
                else:
                    st.error(f"Błąd przejścia do głosowania: {result}")
        if st.session_state.is_host:
            if st.button("Następna runda", use_container_width=True):
                new_data = next_round_logic(game_data)

                updated, result = update_game_file(game_code, new_data)

                if updated:
                    st.success("Nowa runda rozpoczęta")
                    st.rerun()
                else:
                    st.error(f"Błąd: {result}")
        if st.session_state.is_host:
            if st.button("Zakończ grę", use_container_width=True):
                game_data["status"] = "finished"

                updated, result = update_game_file(game_code, game_data)

                if updated:
                    st.success("Gra zakończona przez hosta.")
                    st.rerun()
                else:
                    st.error(f"Błąd zakończenia gry: {result}") 

            if game_data.get("guess_status") == "pending_host_review":
                st.write("### Zgadywanie impostora do oceny")
                st.write(f"**Zgadywane hasło:** {game_data.get('impostor_guess', '')}")
                st.write(f"**Prawidłowe hasło:** {game_data.get('word', '')}")

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("Uznaj zgadywanie", use_container_width=True):
                        game_data["guess_status"] = "approved_by_host"
                        game_data["status"] = "round_result"

                        updated, result = update_game_file(game_code, game_data)

                        if updated:
                            st.success("Host uznał zgadywanie impostora.")
                            st.rerun()
                        else:
                            st.error(f"Błąd zapisu decyzji hosta: {result}")

                with col2:
                    if st.button("Odrzuć zgadywanie", use_container_width=True):
                        game_data["guess_status"] = "rejected_by_host"
                        game_data["status"] = "round_result"

                        updated, result = update_game_file(game_code, game_data)

                        if updated:
                            st.success("Host odrzucił zgadywanie impostora.")
                            st.rerun()
                        else:
                            st.error(f"Błąd zapisu decyzji hosta: {result}")       
 
        if my_role["role"] == "impostor":
            st.warning("### Zgadnij właściwe hasło")
            with st.form(key=f"guess_form_{player_name}", clear_on_submit=True):
                impostor_guess_input = st.text_input(
                    "Wpisz zgadywane hasło",
                    key=f"guess_input_{player_name}"
                )
                guess_submitted = st.form_submit_button("Zgłoś zgadywanie", use_container_width=True)

            if guess_submitted:
                new_guess = impostor_guess_input.strip()

                if not new_guess:
                    st.error("Wpisz hasło do zgadnięcia.")
                else:
                    game_data["impostor_guess"] = new_guess

                    real_word = game_data.get("word", "").strip().lower()

                if new_guess.lower() == real_word:
                    game_data["guess_status"] = "exact"
                    game_data["status"] = "round_result"
                else:
                    game_data["guess_status"] = "pending_host_review"

                updated, result = update_game_file(game_code, game_data)

                if updated:
                    st.success("Zgadywanie zapisane.")
                    st.rerun()
                else:
                    st.error(f"Błąd zapisu zgadywania: {result}")