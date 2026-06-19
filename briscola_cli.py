#!/usr/bin/env python3
"""
Briscola — CLI interface (v0.3)

Async, string-passing, honor-system two-player Briscola. The whole game lives
in a token string that players exchange manually.

v0.2 change: a device sets its player AUTOMATICALLY on import (a token is only
sent to you when it's your turn, so the importing device adopts state["turn"]
as its identity) and remembers it for the whole game, keyed by the token's
game_id. The identity is persisted to a small per-user file so it survives
quitting and relaunching between turns. If that file can't be written, it
falls back to in-memory for the session.

Still v0.x: honor system (full view — both hands shown), single game, no
following-suit rule. Display routes through engine.player_view.

Run:  python briscola_cli.py
"""

import json
import secrets
import sys
from pathlib import Path

import briscola_engine as be


# --------------------------------------------------------------------------- #
# Session store — remembers which player this device is, per game_id.
# Persists to a small file under the user's home dir; degrades to memory.
# --------------------------------------------------------------------------- #

class SessionStore:
    def __init__(self, path=None):
        if path is not None:
            self.path = Path(path)
        else:
            try:
                base = Path.home()
            except Exception:
                base = Path(".")
            self.path = base / ".briscola_sessions.json"
        self.data = self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
                return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f)
        except Exception:
            pass  # locked-down environment: keep going in memory only

    def get(self, game_id):
        entry = self.data.get(game_id)
        return entry.get("player") if isinstance(entry, dict) else None

    def set(self, game_id, player):
        self.data[game_id] = {"player": player}
        self._save()

    def clear(self, game_id):
        if game_id in self.data:
            del self.data[game_id]
            self._save()


def resolve_identity(sessions, state):
    """Return (player_index, is_new) for this device in this game.

    First time the device sees a game_id, it adopts whoever's turn it is (you
    only receive a token when it's your turn) and stores it. Afterwards the
    stored identity is authoritative and is never re-derived.
    """
    gid = state["game_id"]
    player = sessions.get(gid)
    if player is None:
        player = state["turn"]
        sessions.set(gid, player)
        return player, True
    return player, False


# --------------------------------------------------------------------------- #
# Rendering  (all reads go through player_view)
# --------------------------------------------------------------------------- #

def fmt_hand(cards):
    return "  ".join(f"[{i}] {be.card_name(c)}" for i, c in enumerate(cards)) or "(empty)"


def show_state(state, my_player):
    v = be.player_view(state, my_player)
    bs = v["briscola_suit"]
    me = v["you"]
    you = 1 - me
    print()
    print("=" * 64)
    if v["briscola_in_deck"]:
        trump = f"  Briscola (trump): {be.SUIT_NAMES[bs]}  —  card turned up: {v['briscola_card']}"
    else:
        trump = f"  Briscola (trump): {be.SUIT_NAMES[bs]}  —  set by {v['briscola_card']} (now drawn)"
    print(trump)
    print(f"  Cards left in deck: {v['deck_count']}    Trick #{v['trick_no']}")
    print(f"  Score —  Player 1: {v['captured_points'][0]} pt"
          f"   |   Player 2: {v['captured_points'][1]} pt")
    print("-" * 64)
    if v["table"]:
        played = "   ".join(f"P{p + 1}: {be.card_name(c)}" for p, c in v["table"])
        print(f"  On the table:  {played}")
    else:
        print("  On the table:  (nothing yet)")
    print("-" * 64)
    print(f"  Player {me + 1} hand (YOU): {fmt_hand(v['your_hand'])}")
    n = v["opponent_hand_count"]
    print(f"  Player {you + 1} hand:      {n} card{'s' if n != 1 else ''} (hidden)")
    print("=" * 64)
    leader_tag = "leads" if not v["table"] else "to respond"
    print(f"  >> It is Player {v['turn'] + 1}'s turn ({leader_tag}).")


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
    """Drive the game while it is this device's turn; export and stop otherwise.

    Returns the state it ended on (terminal, or paused awaiting the opponent).
    """
    while not be.is_terminal(state):
        show_state(state, my_player)

        if state["turn"] != my_player:
            print(f"\n  It is Player {state['turn'] + 1}'s move now.")
            export_token(state, state["turn"])
            print("\n  Waiting for them to play and send the next token back.")
            return state

        hand = be.legal_moves(state, my_player)
        print(f"\n  Your hand (Player {my_player + 1}):")
        print(f"    {fmt_hand(hand)}")
        choice = prompt("  Play which card? (index, or 'q' to quit): ").strip().lower()
        if choice in ("q", "quit"):
            print("  Leaving game. Latest token (current player to move):")
            export_token(state, state["turn"])
            return state
        if not choice.isdigit() or int(choice) not in range(len(hand)):
            print("  Invalid choice.")
            continue

        try:
            state = be.apply_move(state, my_player, hand[int(choice)])
        except be.IllegalMove as exc:
            print(f"  ! {exc}")
            continue

    show_result(state)
    return state


# --------------------------------------------------------------------------- #
# Flows
# --------------------------------------------------------------------------- #

def new_game_flow(sessions):
    seed = secrets.randbits(64)          # init-only entropy; never stored in state
    state = be.new_game(seed=seed)
    gid = state["game_id"]
    sessions.set(gid, 0)                 # the creator is Player 1
    print(f"\n  New game created (id {gid[:8]}…). You are Player 1.")
    print("  Player 2 leads the first trick — send them the opening token below.")
    final = play(state, 0)
    if be.is_terminal(final):
        sessions.clear(gid)


def load_game_flow(sessions):
    state = read_token()
    if state is None:
        return
    player, is_new = resolve_identity(sessions, state)
    gid = state["game_id"]
    if is_new:
        print(f"\n  Joined game {gid[:8]}… — you are Player {player + 1}.")
    else:
        print(f"\n  Resuming game {gid[:8]}… as Player {player + 1}.")
    final = play(state, player)
    if be.is_terminal(final):
        sessions.clear(gid)


# --------------------------------------------------------------------------- #
# Menu
# --------------------------------------------------------------------------- #

BANNER = r"""
  ____       _              _
 | __ ) _ __(_)___  ___ ___| | __ _
 |  _ \| '__| / __|/ __/ _ \ |/ _` |
 | |_) | |  | \__ \ (_| (_) | | (_| |
 |____/|_|  |_|___/\___\___/|_|\__,_|
        string-passing edition · v0.3
"""


def main():
    print(BANNER)
    sessions = SessionStore()
    while True:
        print("\n  [1] New game     [2] Load token     [q] Quit")
        choice = prompt("  Choose: ").strip().lower()
        if choice == "1":
            new_game_flow(sessions)
        elif choice == "2":
            load_game_flow(sessions)
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
