#!/usr/bin/env python3
"""
Briscola - CLI interface (v0.5.0)

Async, string-passing, honor-system two-player Briscola. The whole game lives
in a token string that players exchange manually.

This file is control flow only: the menu, the paste-to-load default, identity/
session handling, input, and the game loop. All drawing is delegated to
briscola_render (pure view -> text); all rules to briscola_engine; clipboard
auto-copy to briscola_clipboard.

v0.5.0:
- Tokens are auto-copied to the clipboard when shown (Windows; write-only).
- Figure cards display as K/Q/J by default (setting in briscola_render).

Run:  python briscola_cli.py
"""

import json
import os
import secrets
import sys
from pathlib import Path

import briscola_engine as be
import briscola_render as br
import briscola_clipboard as clip


# --------------------------------------------------------------------------- #
# Session store - remembers which player this device is, per game_id.
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
    """Return (player_index, is_new). First sight of a game adopts whoever's
    turn it is (you only receive a token on your turn); afterwards locked."""
    gid = state["game_id"]
    player = sessions.get(gid)
    if player is None:
        player = state["turn"]
        sessions.set(gid, player)
        return player, True
    return player, False


# --------------------------------------------------------------------------- #
# Terminal helpers
# --------------------------------------------------------------------------- #

def clear_screen():
    """Clear the screen on an interactive terminal; no-op (blank line) when the
    output is piped or redirected, so logs/tests don't fill with escape codes."""
    if not sys.stdout.isatty():
        print()
        return
    if os.name == "nt":
        os.system("")  # enables ANSI escape handling on Windows 10+ consoles
    print("\033[2J\033[3J\033[H", end="")


def prompt(msg):
    try:
        return input(msg)
    except EOFError:
        return "q"


def render_screen(state, my_player):
    clear_screen()
    print(br.render_board(be.player_view(state, my_player)))


def print_token(state, to_player):
    token = be.serialize(state)
    print(f"\n  --> Send this token to Player {to_player + 1}:\n")
    print(token)
    if clip.copy_to_clipboard(token):
        print("\n  (copied to clipboard - just paste it to your opponent)")


def show_result(state):
    r = be.result(state)
    print()
    print("#" * 64)
    print(f"  GAME OVER  -  Player 1: {r['points'][0]} pt   Player 2: {r['points'][1]} pt")
    if r["winner"] is None:
        print("  Result: PAREGGIO (60-60 draw).")
    else:
        print(f"  Result: PLAYER {r['winner'] + 1} WINS.")
    print("#" * 64)


# --------------------------------------------------------------------------- #
# Game loop
# --------------------------------------------------------------------------- #

def play(state, my_player):
    """Play while it is this device's turn; hand off (print token) otherwise.
    Returns the state it ended on (terminal or paused)."""
    while not be.is_terminal(state):
        # Last trick: both hands hold exactly one card each, so there is only
        # one way the rest of the game can play out - resolve it without
        # making either side click through a choice that isn't really one.
        forced = be.legal_moves(state, state["turn"])
        if len(forced) == 1:
            state = be.apply_move(state, state["turn"], forced[0])
            continue

        render_screen(state, my_player)

        if state["turn"] != my_player:
            print(f"\n  It is Player {state['turn'] + 1}'s move now.")
            print_token(state, state["turn"])
            print("\n  (Load the token they send back to continue.)")
            return state

        hand = be.legal_moves(state, my_player)
        choice = prompt(f"\n  Your move (Player {my_player + 1}) - "
                        f"play which card? [0-{len(hand) - 1}] or 'q': ").strip().lower()
        if choice in ("q", "quit"):
            print("  Paused - your latest token:")
            print_token(state, state["turn"])
            return state
        if not choice.isdigit() or int(choice) not in range(len(hand)):
            print("  Invalid choice.")
            continue
        try:
            state = be.apply_move(state, my_player, hand[int(choice)])
        except be.IllegalMove as exc:
            print(f"  ! {exc}")

    render_screen(state, my_player)
    show_result(state)
    other = 1 - my_player
    print(f"\n  Send this final token to Player {other + 1} so they see the result too:")
    print_token(state, other)
    return state


# --------------------------------------------------------------------------- #
# Flows
# --------------------------------------------------------------------------- #

def new_game_flow(sessions):
    seed = secrets.randbits(64)          # init-only entropy; never stored in state
    state = be.new_game(seed=seed)
    gid = state["game_id"]
    sessions.set(gid, 0)                 # the creator is Player 1
    print(f"\n  New game created (id {gid[:8]}...). You are Player 1.")
    print("  Player 2 leads the first trick - send them the opening token below.")
    final = play(state, 0)
    if be.is_terminal(final):
        sessions.clear(gid)


def start_loaded_game(sessions, state):
    player, is_new = resolve_identity(sessions, state)
    gid = state["game_id"]
    if is_new:
        print(f"\n  Joined game {gid[:8]}... - you are Player {player + 1}.")
    else:
        print(f"\n  Resuming game {gid[:8]}... as Player {player + 1}.")
    final = play(state, player)
    if be.is_terminal(final):
        sessions.clear(gid)


def load_game_flow(sessions):
    """Explicit load path: prompt for a paste, then start."""
    print("\n  Paste the token, then press Enter (or blank to cancel):")
    raw = prompt("  > ").strip()
    if not raw:
        return
    try:
        state = be.deserialize(raw)
    except be.TokenError as exc:
        print(f"  ! Could not load token: {exc}")
        return
    start_loaded_game(sessions, state)


# --------------------------------------------------------------------------- #
# Menu - pasting a token is the default action
# --------------------------------------------------------------------------- #

def interpret_command(raw):
    """Map raw menu input to ('new'|'load'|'quit'|'empty'|'token'|'unknown', state)."""
    low = raw.strip().lower()
    if low in ("1", "new", "n"):
        return "new", None
    if low in ("2", "load", "l"):
        return "load", None
    if low in ("q", "quit", "exit"):
        return "quit", None
    if raw.strip() == "":
        return "empty", None
    try:
        return "token", be.deserialize(raw.strip())
    except be.TokenError:
        return "unknown", None


BANNER = r"""
  ____       _              _
 | __ ) _ __(_)___  ___ ___| | __ _
 |  _ \| '__| / __|/ __/ _ \ |/ _` |
 | |_) | |  | \__ \ (_| (_) | | (_| |
 |____/|_|  |_|___/\___\___/|_|\__,_|
        string-passing edition - v0.5.0
"""


def main():
    print(BANNER)
    sessions = SessionStore()
    while True:
        print("\n  Paste a token to continue a game,  or  [1] new  |  [2] load  |  [q] quit")
        raw = prompt("  > ")
        kind, state = interpret_command(raw)
        if kind == "new":
            new_game_flow(sessions)
        elif kind == "load":
            load_game_flow(sessions)
        elif kind == "quit":
            print("  Ciao!")
            return
        elif kind == "token":
            start_loaded_game(sessions, state)
        elif kind == "empty":
            continue
        else:
            print("  Not a menu choice or a valid token. Try again, or [q] to quit.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Ciao!")
        sys.exit(0)
