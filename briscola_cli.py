#!/usr/bin/env python3
"""
Briscola — CLI interface (v0.1)

Async, string-passing, honor-system two-player Briscola. The whole game lives
in a token string that players exchange manually. This v0.1 shows a FULL VIEW
(both hands), routed through engine.player_view so hidden hands can be added
later without changing this file's structure.

Run:  python briscola_cli.py
"""

import secrets
import sys

import briscola_engine as be


# --------------------------------------------------------------------------- #
# Rendering  (all reads go through player_view)
# --------------------------------------------------------------------------- #

def fmt_hand(cards):
    return "  ".join(f"[{i}] {be.card_name(c)}" for i, c in enumerate(cards)) or "(empty)"


def show_state(state, my_player):
    view = be.player_view(state, my_player)
    bs = view["briscola_suit"]
    print()
    print("=" * 64)
    print(f"  Briscola (trump): {be.SUIT_NAMES[bs]}  —  card turned up: {view['briscola_card']}")
    print(f"  Cards left in deck: {len(view['deck'])}    Trick #{view['trick_no']}")
    print(f"  Score —  Player 1: {view['captured_points'][0]} pt"
          f"   |   Player 2: {view['captured_points'][1]} pt")
    print("-" * 64)
    if view["table"]:
        played = "   ".join(f"P{p + 1}: {be.card_name(c)}" for p, c in view["table"])
        print(f"  On the table:  {played}")
    else:
        print("  On the table:  (nothing yet)")
    print("-" * 64)
    # full view (v0.1): show both hands
    print(f"  Player 1 hand: {fmt_hand(view['hands'][0])}")
    print(f"  Player 2 hand: {fmt_hand(view['hands'][1])}")
    print("=" * 64)
    leader_tag = "leads" if not view["table"] else "to respond"
    print(f"  >> It is Player {view['turn'] + 1}'s turn ({leader_tag}).")


def show_result(state):
    r = be.result(state)
    print()
    print("#" * 64)
    print(f"  GAME OVER  —  Player 1: {r['points'][0]} pt   Player 2: {r['points'][1]} pt")
    if r["winner"] is None:
        print("  Result: PAREGGIO (60–60 draw).")
    else:
        print(f"  Result: PLAYER {r['winner'] + 1} WINS.")
    print("#" * 64)


# --------------------------------------------------------------------------- #
# Input helpers
# --------------------------------------------------------------------------- #

def prompt(msg):
    try:
        return input(msg)
    except EOFError:
        return "q"


def read_token():
    print("\nPaste the token, then press Enter (or 'b' to go back):")
    raw = prompt("> ").strip()
    if raw.lower() in ("b", "back", ""):
        return None
    try:
        return be.deserialize(raw)
    except be.TokenError as exc:
        print(f"\n  ! Could not load token: {exc}")
        return None


def choose_player():
    while True:
        ans = prompt("Which player are you on this device? [1/2]: ").strip()
        if ans in ("1", "2"):
            return int(ans) - 1
        print("  Please enter 1 or 2.")


def export_token(state, to_player):
    print()
    print("-" * 64)
    print(f"  Send this token to Player {to_player + 1}:")
    print("-" * 64)
    print(be.serialize(state))
    print("-" * 64)


# --------------------------------------------------------------------------- #
# Play loop
# --------------------------------------------------------------------------- #

def play(state, my_player):
    """Drive the game while it is this player's turn; export and stop otherwise."""
    while not be.is_terminal(state):
        show_state(state, my_player)

        if state["turn"] != my_player:
            print(f"\n  It is Player {state['turn'] + 1}'s move now.")
            export_token(state, state["turn"])
            print("\n  Waiting for them to play and send the next token back.")
            return

        hand = be.legal_moves(state, my_player)
        print(f"\n  Your hand (Player {my_player + 1}):")
        print(f"    {fmt_hand(hand)}")
        choice = prompt("  Play which card? (index, or 'q' to quit): ").strip().lower()
        if choice in ("q", "quit"):
            print("  Leaving game. Your latest token (current player to move):")
            export_token(state, state["turn"])
            return
        if not choice.isdigit() or int(choice) not in range(len(hand)):
            print("  Invalid choice.")
            continue

        try:
            state = be.apply_move(state, my_player, hand[int(choice)])
        except be.IllegalMove as exc:
            print(f"  ! {exc}")
            continue

    show_result(state)


# --------------------------------------------------------------------------- #
# Menu
# --------------------------------------------------------------------------- #

BANNER = r"""
  ____       _              _       
 | __ ) _ __(_)___  ___ ___| | __ _ 
 |  _ \| '__| / __|/ __/ _ \ |/ _` |
 | |_) | |  | \__ \ (_| (_) | | (_| |
 |____/|_|  |_|___/\___\___/|_|\__,_|
        string-passing edition · v0.1
"""


def new_game_flow():
    # The player who starts a new game is Player 1 (index 0).
    # Non-starting player (Player 2) leads the first trick, so the freshly
    # created token is immediately the opponent's move to make.
    seed = secrets.randbits(64)          # init-only entropy; never stored in state
    state = be.new_game(seed=seed)
    print("\n  New game created. You are Player 1.")
    print("  Player 2 leads the first trick — send them the opening token.")
    play(state, my_player=0)


def load_game_flow():
    state = read_token()
    if state is None:
        return
    my_player = choose_player()
    play(state, my_player)


def main():
    print(BANNER)
    while True:
        print("\n  [1] New game     [2] Load token     [q] Quit")
        choice = prompt("  Choose: ").strip().lower()
        if choice == "1":
            new_game_flow()
        elif choice == "2":
            load_game_flow()
        elif choice in ("q", "quit"):
            print("  Ciao!")
            return
        else:
            print("  Please choose 1, 2, or q.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Ciao!")
        sys.exit(0)
