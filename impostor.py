import random
import string
import streamlit as st
from streamlit_autorefresh import st_autorefresh

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
    selected_difficulties = settings.get(
       "selected_difficulties",
        ["łatwe", "średnie", "trudne", "ekstremalnie trudne"]
    )
    hint_mode = settings.get("hint_mode", "off")

    available_categories = [cat for cat in selected_categories if cat in WORDS]

    if not available_categories:
        return False, "Brak dostępnych kategorii do losowania."

    impostor = random.choice(players)
    category = random.choice(available_categories)
    available_words = [
        entry for entry in WORDS[category]
        if entry.get("difficulty") in selected_difficulties
    ]
    if not available_words:
        return False, "Brak słów dla wybranych poziomów trudności w tej kategorii."

    chosen_entry = random.choice(available_words)
    word = chosen_entry["word"]
    hint = chosen_entry.get("hint", "")

    starter = choose_round_starter(players, impostor)

    roles = {}
    for player in players:
        if player == impostor:
            roles[player] = {
                "role": "impostor"
            }

            if hint_mode == "category":
                roles[player]["category"] = category
            elif hint_mode == "hint":
                roles[player]["hint"] = hint

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
    game_data["starter"] = starter
    if "stats" in game_data and impostor in game_data["stats"]:
        game_data["stats"][impostor]["times_impostor"] += 1
    game_data["roles"] = roles
    game_data["submissions"] = {player: [] for player in players}
    game_data["impostor_guess"] = ""
    game_data["guess_status"] = "none"
    game_data["votes"] = {}
    game_data["voted_out"] = None
    game_data["reactions"] = {}
    game_data["round_winner"] = None

    return True, game_data

def next_round_logic(game_data):
    players = game_data["players"]

    settings = game_data.get("settings", {})
    selected_categories = settings.get("selected_categories", list(WORDS.keys()))
    selected_difficulties = settings.get(
        "selected_difficulties",
        ["łatwe", "średnie", "trudne", "ekstremalnie trudne"]
    )    
    hint_mode = settings.get("hint_mode", "off")

    available_categories = [cat for cat in selected_categories if cat in WORDS]

    if not available_categories:
        return game_data

    impostor = random.choice(players)
    starter = choose_round_starter(players, impostor)
    category = random.choice(available_categories)
    available_words = [
        entry for entry in WORDS[category]
        if entry.get("difficulty") in selected_difficulties
    ]
    if not available_words:
     return game_data

    chosen_entry = random.choice(available_words)
    word = chosen_entry["word"]
    hint = chosen_entry.get("hint", "")

    roles = {}
    for player in players:
        if player == impostor:
            roles[player] = {
                "role": "impostor"
            }

            if hint_mode == "category":
                roles[player]["category"] = category
            elif hint_mode == "hint":
                roles[player]["hint"] = hint

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
    game_data["starter"] = starter
    if "stats" in game_data and impostor in game_data["stats"]:
        game_data["stats"][impostor]["times_impostor"] += 1
    game_data["roles"] = roles
    game_data["round"] = game_data.get("round", 1) + 1
    game_data["submissions"] = {player: [] for player in players}
    game_data["impostor_guess"] = ""
    game_data["guess_status"] = "none"
    game_data["votes"] = {}
    game_data["voted_out"] = None
    game_data["reactions"] = {}
    game_data["round_winner"] = None

    if is_game_over(game_data):
        game_data["status"] = "finished"

    return game_data

def get_winners(game_data):
    scores = game_data.get("scores", {})

    if not scores or len(scores) == 0:
        return []

    max_score = max(scores.values())
    return [player for player, score in scores.items() if score == max_score]

def resolve_voting_result(game_data):
    votes = game_data.get("votes", {})
    players = game_data.get("players", [])
    impostor = game_data.get("impostor")

    if len(votes) < len(players):
        return False, "Nie wszyscy gracze oddali głos."

    vote_count = {}

    for voted_player in votes.values():
        if voted_player not in vote_count:
            vote_count[voted_player] = 0
        vote_count[voted_player] += 1

    max_votes = max(vote_count.values())
    top_players = [player for player, count in vote_count.items() if count == max_votes]

    # Jeśli impostor jest w remisie z innymi, impostor przeżywa.
    if impostor in top_players and len(top_players) > 1:
        non_impostor_tied = [player for player in top_players if player != impostor]
        voted_out = random.choice(non_impostor_tied)
    else:
        voted_out = random.choice(top_players)

    game_data["voted_out"] = voted_out

    if voted_out == impostor:
        game_data["round_winner"] = "players"
    else:
        game_data["round_winner"] = "impostor"

    game_data["status"] = "round_result"

    return True, game_data

def apply_round_points(game_data):
    scores = game_data.get("scores", {})
    impostor = game_data.get("impostor")
    guess_status = game_data.get("guess_status")
    round_winner = game_data.get("round_winner")
    votes = game_data.get("votes", {})

    # 1. Impostor wygrał przez zgadywanie
    if guess_status in ["exact", "approved_by_host"]:
        if impostor in scores:
            scores[impostor] += 3

    # 2. Głosowanie: gracze wygrali, bo impostor został wyrzucony
    elif round_winner == "players":
        for player, voted in votes.items():
            if voted == impostor and player in scores:
                scores[player] += 1

    # 3. Głosowanie: impostor wygrał, bo nie został wyrzucony
    elif round_winner == "impostor":
        if impostor in scores:
            scores[impostor] += 3

        for player, voted in votes.items():
            if voted == impostor and player in scores:
                scores[player] += 1

    game_data["scores"] = scores
    return game_data

def apply_round_stats(game_data):
    stats = game_data.get("stats", {})
    votes = game_data.get("votes", {})
    impostor = game_data.get("impostor")
    guess_status = game_data.get("guess_status")
    round_winner = game_data.get("round_winner")

    if impostor not in stats:
        return game_data

    # 1. Wygrana/przegrana impostora
    if guess_status in ["exact", "approved_by_host"]:
        stats[impostor]["impostor_wins"] += 1

    elif guess_status == "rejected_by_host":
        stats[impostor]["impostor_losses"] += 1

    elif round_winner == "impostor":
        stats[impostor]["impostor_wins"] += 1

    elif round_winner == "players":
        stats[impostor]["impostor_losses"] += 1

    # 2. Poprawne głosy na impostora
    for player, voted_player in votes.items():
        if voted_player == impostor and player in stats:
            stats[player]["correct_votes"] += 1

    # 3. Liczba głosów otrzymanych przez każdego gracza
    vote_received_count = {}

    for voted_player in votes.values():
        if voted_player not in vote_received_count:
            vote_received_count[voted_player] = 0
        vote_received_count[voted_player] += 1

    for player, received in vote_received_count.items():
        if player in stats:
            stats[player]["total_votes_received"] += received

    game_data["stats"] = stats
    return game_data

def compute_game_rankings(game_data):
    stats = game_data.get("stats", {})
    scores = game_data.get("scores", {})

    if not stats:
        return {}

    def get_all_max_players(value_map):
        if not value_map:
            return []
        max_value = max(value_map.values())
        return [player for player, value in value_map.items() if value == max_value]

    def get_all_min_players(value_map):
        if not value_map:
            return []
        min_value = min(value_map.values())
        return [player for player, value in value_map.items() if value == min_value]

    # 🏆 ranking punktowy
    score_ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # 📊 skuteczność impostora
    impostor_efficiency = {}
    impostor_games = {}
    impostor_wins = {}

    for player, s in stats.items():
        times = s.get("times_impostor", 0)
        wins = s.get("impostor_wins", 0)

        impostor_games[player] = times
        impostor_wins[player] = wins

        if times > 0:
            impostor_efficiency[player] = round((wins / times) * 100, 1)
        else:
            impostor_efficiency[player] = 0.0

    # sortowanie skuteczności:
    # 1) procent malejąco
    # 2) liczba gier jako impostor malejąco
    # 3) nazwa rosnąco dla stabilności
    impostor_efficiency_ranking = sorted(
        impostor_efficiency.items(),
        key=lambda x: (-x[1], -impostor_games[x[0]], x[0])
    )

    # 🕵️ najlepszy detektyw
    detective_values = {player: s.get("correct_votes", 0) for player, s in stats.items()}
    best_detectives = get_all_max_players(detective_values)
    best_detective_value = max(detective_values.values()) if detective_values else 0

    # 😈 najlepszy impostor
    best_impostors = []
    if impostor_efficiency:
        best_eff = max(impostor_efficiency.values())
        best_eff_players = [
            player for player, eff in impostor_efficiency.items()
            if eff == best_eff
        ]

        max_games_among_best = max(impostor_games[player] for player in best_eff_players)
        best_impostors = [
            player for player in best_eff_players
            if impostor_games[player] == max_games_among_best
        ]

    # 💀 najgorszy impostor
    worst_impostors = []
    if impostor_efficiency:
        worst_eff = min(impostor_efficiency.values())
        worst_eff_players = [
            player for player, eff in impostor_efficiency.items()
            if eff == worst_eff
        ]

        max_games_among_worst = max(impostor_games[player] for player in worst_eff_players)
        worst_impostors = [
            player for player in worst_eff_players
            if impostor_games[player] == max_games_among_worst
        ]

    # 🎭 najczęstszy impostor
    times_impostor_values = {player: s.get("times_impostor", 0) for player, s in stats.items()}
    most_impostors = get_all_max_players(times_impostor_values)
    most_impostor_value = max(times_impostor_values.values()) if times_impostor_values else 0

    # 🛡️ najbezpieczniejszy gracz
    safest_values = {player: s.get("total_votes_received", 0) for player, s in stats.items()}
    safest_players = get_all_min_players(safest_values)
    safest_value = min(safest_values.values()) if safest_values else 0

    # Emoji leaders — przy remisie wypisz wszystkich
    emoji_leaders = {}
    for emoji in ["🔥", "👍", "😐", "👎", "💀"]:
        emoji_values = {
            player: s.get("emoji_received", {}).get(emoji, 0)
            for player, s in stats.items()
        }
        leaders = get_all_max_players(emoji_values)
        leader_value = max(emoji_values.values()) if emoji_values else 0
        emoji_leaders[emoji] = (leaders, leader_value)

    return {
        "score_ranking": score_ranking,

        "best_detectives": best_detectives,
        "best_detective_value": best_detective_value,

        "best_impostors": best_impostors,
        "worst_impostors": worst_impostors,

        "most_impostors": most_impostors,
        "most_impostor_value": most_impostor_value,

        "safest_players": safest_players,
        "safest_value": safest_value,

        "impostor_efficiency": impostor_efficiency,
        "impostor_efficiency_ranking": impostor_efficiency_ranking,

        "impostor_games": impostor_games,
        "impostor_wins": impostor_wins,

        "emoji_leaders": emoji_leaders
    }

def format_player_list(players):
    if not players:
        return "Brak"
    if len(players) == 1:
        return players[0]
    return " i ".join(players)

def choose_round_starter(players, impostor):
    weighted_players = []
    weights = []

    for player in players:
        weighted_players.append(player)

        if player == impostor:
            weights.append(0.4)
        else:
            weights.append(1.0)

    return random.choices(weighted_players, weights=weights, k=1)[0]

def reset_game_to_lobby(game_data):
    players = game_data.get("players", [])

    # reset punktów
    game_data["scores"] = {player: 0 for player in players}

    # reset statystyk
    game_data["stats"] = {
        player: {
            "times_impostor": 0,
            "impostor_wins": 0,
            "impostor_losses": 0,
            "correct_votes": 0,
            "total_votes_received": 0,
            "emoji_received": {
                "🔥": 0,
                "👍": 0,
                "😐": 0,
                "👎": 0,
                "💀": 0
            }
        }
        for player in players
    }

    # reset rundy i stanu
    game_data["round"] = 0
    game_data["status"] = "lobby"

    # czyszczenie rundy
    game_data["submissions"] = {player: [] for player in players}
    game_data["votes"] = {}
    game_data["voted_out"] = None
    game_data["round_winner"] = None
    game_data["impostor_guess"] = ""
    game_data["guess_status"] = "none"
    game_data["impostor"] = None
    game_data["roles"] = {}
    game_data["starter"] = None

    return game_data

def remove_player(game_data, player_to_remove):
    if player_to_remove == game_data.get("host"):
        return game_data

    players = game_data.get("players", [])
    game_data["players"] = [p for p in players if p != player_to_remove]

    if "scores" in game_data and player_to_remove in game_data["scores"]:
        del game_data["scores"][player_to_remove]

    if "stats" in game_data and player_to_remove in game_data["stats"]:
        del game_data["stats"][player_to_remove]

    if "submissions" in game_data and player_to_remove in game_data["submissions"]:
        del game_data["submissions"][player_to_remove]

    if "votes" in game_data:
        game_data["votes"] = {
            voter: target
            for voter, target in game_data["votes"].items()
            if voter != player_to_remove and target != player_to_remove
        }

    if "roles" in game_data and player_to_remove in game_data["roles"]:
        del game_data["roles"][player_to_remove]

    return game_data

def kick_if_removed(game_data, player_name):
    players = game_data.get("players", [])

    if player_name not in players:
        st.warning("Zostałeś usunięty z gry przez hosta.")
        st.session_state.screen = "start"
        st.session_state.game_code = ""
        st.session_state.player_name = ""
        st.session_state.is_host = False
        st.stop()

def set_player_reaction(game_data, reactor, target, emoji):
    if "reactions" not in game_data:
        game_data["reactions"] = {}

    if reactor not in game_data["reactions"]:
        game_data["reactions"][reactor] = {}

    game_data["reactions"][reactor][target] = emoji
    return game_data

def apply_reaction_stats(game_data):
    stats = game_data.get("stats", {})
    reactions = game_data.get("reactions", {})

    for reactor, target_map in reactions.items():
        for target, emoji in target_map.items():
            if target in stats:
                if "emoji_received" not in stats[target]:
                    stats[target]["emoji_received"] = {
                        "🔥": 0,
                        "👍": 0,
                        "😐": 0,
                        "👎": 0,
                        "💀": 0
                    }

                if emoji in stats[target]["emoji_received"]:
                    stats[target]["emoji_received"][emoji] += 1

    game_data["stats"] = stats
    return game_data

# ------------------- UI ------------------- #
if st.session_state.screen == "start":
    st.title("Impostor")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("STWÓRZ GRĘ", use_container_width=True):
            st.session_state.screen = "host"
            st.rerun()

    with col2:
        if st.button("DOŁĄCZ DO GRY", use_container_width=True):
            st.session_state.screen = "join"
            st.rerun()


elif st.session_state.screen == "host":
    st.title("Impostor")
    st.subheader("Tworzenie nowej gry")

    player_name = st.text_input("Podaj swój nick", key="host_name")

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
                        "selected_categories": list(WORDS.keys()),
                        "selected_difficulties": ["łatwe", "średnie", "trudne", "ekstremalnie trudne"]
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
                    "votes": {},
                    "voted_out": None,
                    "reactions": {},
                    "round_winner": None,
                    "starter": None,
                    "stats": {
                        player_name.strip(): {
                            "times_impostor": 0,
                            "impostor_wins": 0,
                            "impostor_losses": 0,
                            "correct_votes": 0,
                            "total_votes_received": 0,
                            "emoji_received": {
                                "🔥": 0,
                                "👍": 0,
                                "😐": 0,
                                "👎": 0,
                                "💀": 0
                            }
                        }
                    },                 
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
    st.title("Impostor")
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

                        if "stats" not in game_data:
                            game_data["stats"] = {}

                        game_data["stats"][player_name.strip()] = {
                            "times_impostor": 0,
                            "impostor_wins": 0,
                            "impostor_losses": 0,
                            "correct_votes": 0,
                            "total_votes_received": 0,
                            "emoji_received": {
                                "🔥": 0,
                                "👍": 0,
                                "😐": 0,
                                "👎": 0,
                                "💀": 0
                            } 
                        }
                        
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
    st_autorefresh(interval=5000, key="game_autorefresh")
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
                "selected_categories": list(WORDS.keys()),
                "selected_difficulties": ["łatwe", "średnie", "trudne", "ekstremalnie trudne"]
            }
            changed = True

        if "selected_difficulties" not in game_data["settings"]:
            game_data["settings"]["selected_difficulties"] = ["łatwe", "średnie", "trudne", "ekstremalnie trudne"]
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

        if "voted_out" not in game_data:
            game_data["voted_out"] = None
            changed = True

        if "round_winner" not in game_data:
            game_data["round_winner"] = None
            changed = True
        
        if "stats" not in game_data:
            game_data["stats"] = {}
            changed = True
        
        if "starter" not in game_data:
            game_data["starter"] = None
            changed = True

        for player in game_data.get("players", []):
            if player not in game_data["stats"]:
                game_data["stats"][player] = {
                    "times_impostor": 0,
                    "impostor_wins": 0,
                    "impostor_losses": 0,
                    "correct_votes": 0,
                    "total_votes_received": 0,
                    "emoji_received": {
                        "🔥": 0,
                        "👍": 0,
                        "😐": 0,
                        "👎": 0,
                        "💀": 0
                    }
                }
                changed = True

        if "reactions" not in game_data:
            game_data["reactions"] = {}
            changed = True

        for player in game_data.get("players", []):
            if "emoji_received" not in game_data["stats"].get(player, {}):
                game_data["stats"][player]["emoji_received"] = {
                    "🔥": 0,
                    "👍": 0,
                    "😐": 0,
                    "👎": 0,
                    "💀": 0
                }
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
            col1, col2 = st.columns([3, 1])

            with col1:
                st.write(f"- {player}")

            with col2:
                if st.session_state.is_host and player != game_data.get("host"):
                    if st.button("❌", key=f"remove_{player}"):
                        new_data = remove_player(game_data, player)
                        kick_if_removed(game_data, player_name)
                        updated, result = update_game_file(game_code, new_data)

                        if updated:
                            st.success(f"Usunięto gracza: {player}")
                            st.rerun()
                        else:
                            st.error(f"Błąd usuwania gracza: {result}")
                            
        st.write("### Aktualne ustawienia")
        st.write(f"**Podpowiedzi:** {game_data['settings'].get('hint_mode', 'off')}")
        st.write(f"**Limit rund:** {game_data['settings'].get('round_limit', 10)}")
        st.write(f"**Kategorie:** {', '.join(game_data['settings'].get('selected_categories', []))}")
        st.write(f"**Trudności:** {', '.join(game_data['settings'].get('selected_difficulties', []))}")

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

            difficulty_options = ["łatwe", "średnie", "trudne", "ekstremalnie trudne"]
            current_difficulties = current_settings.get(
                "selected_difficulties",
                difficulty_options
            )

            selected_difficulties = st.multiselect(
                "Aktywne poziomy trudności",
                difficulty_options,
                default=current_difficulties
            )


            if st.button("Zapisz ustawienia", use_container_width=True):
                if not selected_categories:
                    st.error("Wybierz przynajmniej jedną kategorię.")
                elif not selected_difficulties:
                    st.error("Wybierz przynajmniej jeden poziom trudności.")
                else:
                    game_data["settings"]["hint_mode"] = hint_mode_map[selected_hint_label]
                    game_data["settings"]["round_limit"] = round_limit_map[selected_round_label]
                    game_data["settings"]["selected_categories"] = selected_categories
                    game_data["settings"]["selected_difficulties"] = selected_difficulties

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
    st_autorefresh(interval=3000, key="game_autorefresh")
    game_code = st.session_state.game_code
    player_name = st.session_state.player_name

    success, game_data = get_game_file(game_code)

    if not success:
        st.error("Nie udało się wczytać danych gry.")
        st.stop()
    kick_if_removed(game_data, player_name)

    if game_data.get("status") == "lobby":
        st.session_state.screen = "lobby"
        st.rerun()

    if game_data.get("status") == "round_result":
        st.subheader("Koniec rundy")

        guess_status = game_data.get("guess_status", "none")
        impostor_name = game_data.get("impostor", "Nieznany")
        real_word = game_data.get("word", "")
        guessed_word = game_data.get("impostor_guess", "")

        round_winner = game_data.get("round_winner")
        voted_out = game_data.get("voted_out")

        if guess_status == "exact":
            st.success(f"Impostor ({impostor_name}) wygrał rundę, bo odgadł hasło idealnie.")
        elif guess_status == "approved_by_host":
            st.success(f"Impostor ({impostor_name}) wygrał rundę, bo host uznał zgadywanie.")
        elif guess_status == "rejected_by_host":
            st.info("Gracze wygrali rundę, ponieważ host odrzucił zgadywanie impostora.")
        elif round_winner == "players":
            st.success(f"Gracze wygrali rundę. Wyrzucono impostora: {voted_out}")
        elif round_winner == "impostor":
            st.error(f"Impostor wygrał rundę. Wyrzucono niewłaściwego gracza: {voted_out}")
        else:
            st.info("Runda została zakończona.")

        st.write(f"**Prawidłowe hasło:** {real_word}")
        if guessed_word:
            st.write(f"**Zgadywanie impostora:** {guessed_word}")

        st.write("### Aktualne wyniki")

        for player, score in game_data.get("scores", {}).items():
            st.write(f"**{player}:** {score} pkt")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Odśwież", key="refresh_round_result", use_container_width=True):
                st.rerun()

        with col2:
            if st.session_state.is_host:
                if st.button("Zakończ grę", use_container_width=True):
                    game_data["status"] = "finished"

                    updated, result = update_game_file(game_code, game_data)

                    if updated:
                        st.success("Gra zakończona przez hosta.")
                        st.rerun()
                    else:
                        st.error(f"Błąd zakończenia gry: {result}")                

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
    
    if game_data.get("status") == "voting":
        st.subheader("Głosowanie")

        st.write("Wskaż, kto według Ciebie jest impostorem.")
        
        st.write("### Hasła graczy")

        submissions = game_data.get("submissions", {})

        lines = []

        for player in game_data.get("players", []):
            player_text = submissions.get(player, [])

            if isinstance(player_text, str):
                player_text = [player_text] if player_text.strip() else []

            if player_text:
                line = f"<b>{player}:</b> {', '.join(player_text)}"
            else:
                line = f"**{player}:** (brak)"

            lines.append(line)

        st.markdown(
            """
        <div style="
            padding: 10px;
            border-radius: 10px;
            border: 1px solid #ccc;
            background-color: #111;
            font-size: 14px;
            line-height: 1.6;
        ">
        """ + "<br>".join(lines) + """
        </div>
        """,
            unsafe_allow_html=True
        )

        available_targets = [p for p in game_data.get("players", []) if p != player_name]

        current_vote = game_data.get("votes", {}).get(player_name)

        if available_targets:
            default_index = 0
            if current_vote in available_targets:
                default_index = available_targets.index(current_vote)

            vote_target = st.selectbox(
                "Na kogo głosujesz?",
                available_targets,
                index=default_index,
                key=f"vote_target_{player_name}"
            )

            if st.button("Oddaj głos", key=f"submit_vote_{player_name}", use_container_width=True):
                if "votes" not in game_data:
                    game_data["votes"] = {}

                game_data["votes"][player_name] = vote_target

                updated, result = update_game_file(game_code, game_data)

                if updated:
                    st.success("Głos zapisany.")
                    st.rerun()
                else:
                    st.error(f"Błąd zapisu głosu: {result}")

            st.write("### Status głosowania")
            votes = game_data.get("votes", {})
            for p in game_data.get("players", []):
                if p in votes:
                    st.write(f"**{p}:** zagłosował")
                else:
                    st.write(f"**{p}:** jeszcze nie zagłosował")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Odśwież", key="refresh_voting", use_container_width=True):
                    st.rerun()

            with col2:
                if st.session_state.is_host:
                    if st.button("Zakończ głosowanie", key="finish_voting", use_container_width=True):
                        success_vote, result_vote = resolve_voting_result(game_data)

                        success_vote, result_vote = resolve_voting_result(game_data)

                        if not success_vote:
                            st.error(result_vote)
                        else:
                            result_vote = apply_round_points(result_vote)
                            result_vote = apply_round_stats(result_vote)
                            result_vote = apply_reaction_stats(result_vote)

                            updated, result = update_game_file(game_code, result_vote)

                            if updated:
                                st.success("Głosowanie zakończone.")
                                st.rerun()
                            else:
                                st.error(f"Błąd rozliczenia głosowania: {result}")

            st.stop()

    if game_data.get("status") == "finished":
        st.subheader("Koniec gry")

        rankings = compute_game_rankings(game_data)

        st.write(rankings)

        # 🏆 Ranking punktowy
        st.write("### 🏆 Ranking punktowy")
        for i, (player, score) in enumerate(rankings["score_ranking"], start=1):
            st.write(f"{i}. **{player}** — {score} pkt")

        st.divider()

        # 🎖️ Nagrody
        st.write("### 🎖️ Wyróżnienia")

        st.write(
            f"🕵️ **Najlepszy detektyw:** {format_player_list(rankings['best_detectives'])} "
            f"({rankings['best_detective_value']} trafionych głosów)"
        )

        if rankings["best_impostors"]:
            best_players = rankings["best_impostors"]
            best_imp = best_players[0]
            best_imp_wins = rankings["impostor_wins"].get(best_imp, 0)
            best_imp_eff = rankings["impostor_efficiency"].get(best_imp, 0.0)

            st.write(
                f"😈 **Najlepszy impostor:** {format_player_list(best_players)} "
                f"({best_imp_wins} zwycięstwa jako impostor ({best_imp_eff}%))"
            )

        if rankings["worst_impostors"]:
            worst_players = rankings["worst_impostors"]
            worst_imp = worst_players[0]
            worst_imp_wins = rankings["impostor_wins"].get(worst_imp, 0)
            worst_imp_eff = rankings["impostor_efficiency"].get(worst_imp, 0.0)

            st.write(
                f"💀 **Najgorszy impostor:** {format_player_list(worst_players)} "
                f"({worst_imp_wins} zwycięstw jako impostor ({worst_imp_eff}%))"
            )

        st.write(
            f"🎭 **Najczęstszy impostor:** {format_player_list(rankings['most_impostors'])} "
            f"({rankings['most_impostor_value']} razy jako impostor)"
        )

        st.write(
            f"🛡️ **Najbezpieczniejszy gracz:** {format_player_list(rankings['safest_players'])} "
            f"(najmniejsza liczba głosów - {rankings['safest_value']})"
        )
        st.divider()

        # 📊 Skuteczność impostora
        st.write("### 📊 Skuteczność impostora")

        for player, efficiency in rankings["impostor_efficiency_ranking"]:
            games = rankings["impostor_games"].get(player, 0)
            wins = rankings["impostor_wins"].get(player, 0)
            st.write(f"**{player}** — {efficiency}% ({wins}/{games})")

        st.divider()

        st.write("### Emoji Awards")
        for emoji, (players, count) in rankings["emoji_leaders"].items():
            st.write(f"{emoji} **{format_player_list(players)}** — {count}")

        # 📋 Surowe statystyki (debug + ciekawostka)
        st.write("### 📋 Statystyki szczegółowe")

        for player, s in game_data.get("stats", {}).items():
            st.write(f"**{player}**")
            st.write(f"- impostor: {s['times_impostor']} razy")
            st.write(f"- wygrane jako impostor: {s['impostor_wins']}")
            st.write(f"- przegrane jako impostor: {s['impostor_losses']}")
            st.write(f"- poprawne głosy: {s['correct_votes']}")
            st.write(f"- otrzymane głosy: {s['total_votes_received']}")
        
        if st.session_state.is_host:
            st.divider()

            if st.button("🔄 Zagraj ponownie", use_container_width=True):
                new_data = reset_game_to_lobby(game_data)

                updated, result = update_game_file(game_code, new_data)

                if updated:
                    st.session_state.screen = "lobby"
                    st.success("Gra została zresetowana.")
                    st.rerun()
                else:
                    st.error(f"Błąd resetu gry: {result}")

        st.stop()

    st.subheader("Gra trwa")
    st.write(f"**Kod gry:** {game_code}")
    st.write(f"**Gracz:** {player_name}")
    st.write(f"**Runda:** {game_data.get('round', 1)}")
    st.write(f"**Tę rundę zaczyna:** {game_data.get('starter', 'Brak')}")

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
        reactions = game_data.get("reactions", {})
        players = game_data.get("players", [])
        emoji_options = ["🔥", "👍", "😐", "👎", "💀"]

        reaction_totals = {}

        for reactor, target_map in reactions.items():
            for target, emoji in target_map.items():
                if target not in reaction_totals:
                    reaction_totals[target] = {"🔥": 0, "👍": 0, "😐": 0, "👎": 0, "💀": 0}
                reaction_totals[target][emoji] += 1

        lines = []

        for target_player in players:
            player_text = submissions.get(target_player, [])

            if isinstance(player_text, str):
                player_text = [player_text] if player_text.strip() else []

            text_display = ", ".join(player_text) if player_text else "(brak)"
            totals = reaction_totals.get(target_player, {"🔥": 0, "👍": 0, "😐": 0, "👎": 0, "💀": 0})

            line = (
                f"<b>{target_player}:</b> {text_display}"
                f" <span style='color:#888;'>|</span> "
                f"🔥 {totals['🔥']} "
                f"👍 {totals['👍']} "
                f"😐 {totals['😐']} "
                f"👎 {totals['👎']} "
                f"💀 {totals['💀']}"
            )
            lines.append(line)

        st.markdown(
            """
        <div style="
            padding: 10px;
            border-radius: 10px;
            border: 1px solid #444;
            background-color: #111;
            font-size: 14px;
            line-height: 1.6;
        ">
        """ + "<br>".join(lines) + """
        </div>
        """,
            unsafe_allow_html=True
        )

        with st.expander("Dodaj reakcje", expanded=False):
            emoji_options = ["🔥", "👍", "😐", "👎", "💀"]
            reactions = game_data.get("reactions", {})

            for target_player in game_data.get("players", []):
                current_reaction = reactions.get(player_name, {}).get(target_player, "")

                cols = st.columns([2, 1, 1, 1, 1, 1])

                with cols[0]:
                    st.write(f"**{target_player}**")
                    if current_reaction:
                        st.caption(f"Twoja reakcja: {current_reaction}")

                for i, emoji in enumerate(emoji_options, start=1):
                    with cols[i]:
                        if st.button(emoji, key=f"react_{player_name}_{target_player}_{emoji}"):
                            game_data = set_player_reaction(game_data, player_name, target_player, emoji)

                            updated, result = update_game_file(game_code, game_data)

                            if updated:
                                st.rerun()
                            else:
                                st.error(f"Błąd zapisu reakcji: {result}")        

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
            if game_data.get("guess_status") == "pending_host_review":
                st.write("### Zgadywanie impostora do oceny")
                st.write(f"**Zgadywane hasło:** {game_data.get('impostor_guess', '')}")
                st.write(f"**Prawidłowe hasło:** {game_data.get('word', '')}")

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("Uznaj zgadywanie", use_container_width=True):
                        game_data["guess_status"] = "approved_by_host"
                        game_data["status"] = "round_result"
                        game_data = apply_round_points(game_data)
                        game_data = apply_round_stats(game_data)
                        game_data = apply_reaction_stats(game_data)

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
                        game_data = apply_round_stats(game_data)
                        game_data = apply_reaction_stats(game_data)

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
                    game_data = apply_round_points(game_data)
                    game_data = apply_round_stats(game_data)
                    game_data = apply_reaction_stats(game_data)

                else:
                    game_data["guess_status"] = "pending_host_review"

                updated, result = update_game_file(game_code, game_data)

                if updated:
                    st.success("Zgadywanie zapisane.")
                    st.rerun()
                else:
                    st.error(f"Błąd zapisu zgadywania: {result}")

