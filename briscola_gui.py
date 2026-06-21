#!/usr/bin/env python3
"""
Briscola - desktop GUI (v0.1, CustomTkinter)

A single-window, single-executable front end for the same string-passing
game as briscola_cli.py: the whole game still lives in a token string that
players exchange manually (chat, email, etc.) - this module only adds a
graphical way to view and play it. No server, no network code.

Architecture: this is presentation + control flow only, exactly like
briscola_cli.py / briscola_render.py combined for a GUI toolkit instead of a
terminal. It imports briscola_engine for all rules and state, and reuses
briscola_cli.SessionStore / resolve_identity so a game can be picked up
interchangeably from the CLI or the GUI on the same machine. It never
invents its own rules and never touches the raw state for the opponent's
hand - everything routed through state the same way the CLI does (this
module IS the privileged "owning device", so it holds the full state, but
only ever displays the viewer's own hand/the public table).

Third-party dependency note: this module deliberately uses CustomTkinter
(and, transitively, Pillow for card images) instead of the stdlib-only rule
that applies to the rest of this project. That's a per-module exception for
the GUI; briscola_engine/render/cli/clipboard remain stdlib-only.

Packaging (single-file executable):
    pip install customtkinter pyinstaller
    pyinstaller --onefile --name briscola-gui ^
        --add-data "deck_config.csv;."  briscola_gui.py        (Windows)
    pyinstaller --onefile --name briscola-gui \
        --add-data "deck_config.csv:."  briscola_gui.py        (macOS/Linux)

`resource_path()` below resolves data files against `sys._MEIPASS` when
running from the bundled --onefile executable, and against this file's own
directory otherwise (plain `python briscola_gui.py`).

Run:  python briscola_gui.py
"""

import csv
import secrets
import sys
from pathlib import Path

import customtkinter as ctk
from PIL import Image

import briscola_engine as be
from briscola_cli import SessionStore, resolve_identity

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

CARD_W, CARD_H = 100, 145
DECK_CONFIG_FILE = "deck_config.csv"


# --------------------------------------------------------------------------- #
# Packaging / asset path helper
# --------------------------------------------------------------------------- #

def resource_path(*parts):
    """Resolve a data file path against the PyInstaller --onefile temp
    extraction dir (sys._MEIPASS) when bundled, or this file's own directory
    when running from source."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath(*parts)


def load_deck_config(path=None):
    """Read deck_config.csv (card_id,image_path) into {card_id: Path}.
    Any problem (missing file, unreadable CSV, bad rows) is swallowed and
    yields an empty mapping - callers fall back to styled text cards."""
    path = Path(path) if path is not None else resource_path(DECK_CONFIG_FILE)
    mapping = {}
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                card_id = (row.get("card_id") or "").strip()
                image_path = (row.get("image_path") or "").strip()
                if card_id and image_path:
                    mapping[card_id] = resource_path(image_path)
    except Exception:
        return {}
    return mapping


def fallback_label(card):
    """Styled text fallback for a card whose image is missing/unloadable."""
    suit, rank = be.card_suit(card), be.card_rank(card)
    return f"[ {be.RANK_NAMES[rank]} di {be.SUIT_NAMES[suit]} ]"


# --------------------------------------------------------------------------- #
# Card widgets
# --------------------------------------------------------------------------- #

class CardSlot(ctk.CTkFrame):
    """A fixed-size card-shaped slot: shows an image if one loads cleanly,
    otherwise a styled text fallback. Never raises into the UI loop."""

    def __init__(self, master, deck_assets, **kwargs):
        super().__init__(master, width=CARD_W, height=CARD_H, corner_radius=10, **kwargs)
        self.deck_assets = deck_assets
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._label = ctk.CTkLabel(self, text="", wraplength=CARD_W - 12, justify="center")
        self._label.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._image_ref = None  # keep a reference alive (Tk drops GC'd images)

    def _set_image_or_text(self, image_path, text, font_size=12):
        if image_path is not None:
            try:
                pil_img = Image.open(image_path)
                img = ctk.CTkImage(pil_img, size=(CARD_W - 18, CARD_H - 18))
                self._image_ref = img
                self._label.configure(image=img, text="")
                return
            except Exception:
                pass  # missing/corrupt asset: fall through to text
        self._image_ref = None
        self._label.configure(image=None, text=text, font=ctk.CTkFont(size=font_size, weight="bold"))

    def show_card(self, card):
        self._set_image_or_text(self.deck_assets.get(card), fallback_label(card))

    def show_back(self):
        self._set_image_or_text(self.deck_assets.get("__back__"), "[ CARTA ]", font_size=14)

    def show_empty(self, text=""):
        self._image_ref = None
        self._label.configure(image=None, text=text, font=ctk.CTkFont(size=11))


class HandCardButton(ctk.CTkButton):
    """Same fallback behaviour as CardSlot, but clickable - used for the
    viewer's own hand."""

    def __init__(self, master, deck_assets, card, command, **kwargs):
        super().__init__(master, width=CARD_W, height=CARD_H, corner_radius=10,
                          text="", command=command, **kwargs)
        self._image_ref = None
        path = deck_assets.get(card)
        if path is not None:
            try:
                pil_img = Image.open(path)
                self._image_ref = ctk.CTkImage(pil_img, size=(CARD_W - 18, CARD_H - 18))
                self.configure(image=self._image_ref, text="")
                return
            except Exception:
                pass
        self.configure(image=None, text=fallback_label(card),
                        font=ctk.CTkFont(size=12, weight="bold"))


# --------------------------------------------------------------------------- #
# Main application
# --------------------------------------------------------------------------- #

class BriscolaApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Briscola - string-passing edition")
        self.geometry("960x700")
        self.minsize(720, 540)

        self.deck_assets = load_deck_config()
        self.sessions = SessionStore()
        self.state = None
        self.my_player = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_top_bar()
        self._build_body()
        self._show_menu()

    # ----------------------------------------------------------------- #
    # Top panel: theme toggle + status header
    # ----------------------------------------------------------------- #

    def _build_top_bar(self):
        bar = ctk.CTkFrame(self, corner_radius=0)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_columnconfigure(1, weight=0)

        self.header_label = ctk.CTkLabel(
            bar, text="Briscola", font=ctk.CTkFont(size=18, weight="bold"), anchor="w"
        )
        self.header_label.grid(row=0, column=0, sticky="ew", padx=16, pady=12)

        self.theme_switch = ctk.CTkSwitch(
            bar, text="Dark mode", command=self._toggle_theme, onvalue=1, offvalue=0
        )
        self.theme_switch.select()  # starts in dark mode
        self.theme_switch.grid(row=0, column=1, sticky="e", padx=16, pady=12)

    def _toggle_theme(self):
        ctk.set_appearance_mode("dark" if self.theme_switch.get() else "light")

    def _set_header(self, text):
        self.header_label.configure(text=text)

    # ----------------------------------------------------------------- #
    # Body container - swapped between the menu and the table arena
    # ----------------------------------------------------------------- #

    def _build_body(self):
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.body.grid_columnconfigure(0, weight=1)
        self.body.grid_rowconfigure(0, weight=1)

    def _clear_body(self):
        for child in self.body.winfo_children():
            child.destroy()

    # ----------------------------------------------------------------- #
    # Menu screen
    # ----------------------------------------------------------------- #

    def _show_menu(self):
        self._clear_body()
        self._set_header("Briscola - paste a token to continue, or start a new game")

        menu = ctk.CTkFrame(self.body)
        menu.grid(row=0, column=0, sticky="n", pady=40)
        menu.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(menu, text="New game", command=self._new_game).grid(
            row=0, column=0, sticky="ew", padx=24, pady=(24, 8)
        )

        ctk.CTkLabel(menu, text="Paste a token to continue a game:").grid(
            row=1, column=0, sticky="w", padx=24, pady=(16, 4)
        )
        self.menu_token_box = ctk.CTkTextbox(menu, width=420, height=90)
        self.menu_token_box.grid(row=2, column=0, padx=24, pady=4, sticky="ew")

        self.menu_status = ctk.CTkLabel(menu, text="", text_color="orange")
        self.menu_status.grid(row=3, column=0, padx=24, pady=(0, 4), sticky="w")

        ctk.CTkButton(menu, text="Load token", command=self._load_token_from_menu).grid(
            row=4, column=0, sticky="ew", padx=24, pady=(8, 24)
        )

    def _new_game(self):
        seed = secrets.randbits(64)  # init-only entropy; never stored in state
        state = be.new_game(seed=seed)
        self.sessions.set(state["game_id"], 0)  # creator is Player 1
        self._start_state(state)

    def _load_token_from_menu(self):
        raw = self.menu_token_box.get("1.0", "end").strip()
        if not raw:
            self.menu_status.configure(text="Paste a token first.")
            return
        try:
            state = be.deserialize(raw)
        except be.TokenError as exc:
            self.menu_status.configure(text=f"Could not load token: {exc}")
            return
        self._start_state(state)

    # ----------------------------------------------------------------- #
    # Game lifecycle
    # ----------------------------------------------------------------- #

    def _start_state(self, state):
        player, _is_new = resolve_identity(self.sessions, state)
        self.state = state
        self.my_player = player
        self._show_table()

    def _resolve_forced_moves(self):
        """Last trick: both hands hold exactly one card each, so there is
        only one way the rest of the game can play out - resolve it without
        making either side click through a choice that isn't really one."""
        while not be.is_terminal(self.state):
            forced = be.legal_moves(self.state, self.state["turn"])
            if len(forced) != 1:
                return
            self.state = be.apply_move(self.state, self.state["turn"], forced[0])

    # ----------------------------------------------------------------- #
    # Table arena
    # ----------------------------------------------------------------- #

    def _show_table(self):
        self._resolve_forced_moves()
        self._clear_body()

        if be.is_terminal(self.state):
            self.sessions.clear(self.state["game_id"])

        view = be.player_view(self.state, self.my_player)

        arena = ctk.CTkFrame(self.body, fg_color="transparent")
        arena.grid(row=0, column=0, sticky="nsew")
        arena.grid_columnconfigure(0, weight=1)
        arena.grid_rowconfigure(3, weight=1)

        self._set_header(self._status_text(view))

        ctk.CTkLabel(arena, text=self._last_trick_text(view), anchor="w").grid(
            row=0, column=0, sticky="ew", pady=(0, 8)
        )

        top_row = ctk.CTkFrame(arena, fg_color="transparent")
        top_row.grid(row=1, column=0, sticky="ew", pady=4)
        top_row.grid_columnconfigure((0, 1), weight=1)
        self._build_trump_block(top_row, view).grid(row=0, column=0, sticky="w")
        self._build_opponent_block(top_row, view).grid(row=0, column=1, sticky="e")

        ctk.CTkFrame(arena, height=2, fg_color="gray40").grid(row=2, column=0, sticky="ew", pady=8)

        table_frame = ctk.CTkFrame(arena, fg_color="transparent")
        table_frame.grid(row=3, column=0, sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(1, weight=1)
        self._build_table_block(table_frame, view)

        bottom = ctk.CTkFrame(arena, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        bottom.grid_columnconfigure(0, weight=1)
        self._build_action_block(bottom, view)

    def _status_text(self, view):
        cp = view["captured_points"]
        gid = view["game_id"][:8]
        return (
            f"Game {gid}...  |  You are Player {view['you'] + 1}  |  "
            f"Trick {view['trick_no']}  |  Deck {view['deck_count']}  |  "
            f"Score P1 {cp[0]} - P2 {cp[1]}  |  Trump: {be.SUIT_NAMES[view['briscola_suit']]}"
        )

    def _last_trick_text(self, view):
        lt = view.get("last_trick")
        if not lt:
            return "Last trick: -  (game start)"
        a, b = lt["plays"][0], lt["plays"][1]

        def phrase(card):
            return f"{be.RANK_NAMES[be.card_rank(card)]} di {be.SUIT_NAMES[be.card_suit(card)]}"

        return (
            f"Last trick - P{a[0] + 1}: {phrase(a[1])}, P{b[0] + 1}: {phrase(b[1])} "
            f"-> P{lt['winner'] + 1} wins (+{lt['points']})"
        )

    def _build_trump_block(self, master, view):
        frame = ctk.CTkFrame(master, fg_color="transparent")
        ctk.CTkLabel(frame, text=f"TRUMP ({be.SUIT_NAMES[view['briscola_suit']]})").grid(
            row=0, column=0, pady=(0, 4)
        )
        slot = CardSlot(frame, self.deck_assets)
        slot.grid(row=1, column=0)
        if view["briscola_in_deck"]:
            slot.show_card(view["briscola_card"])
        else:
            slot.show_empty("(drawn)")
        return frame

    def _build_opponent_block(self, master, view):
        n = view["opponent_hand_count"]
        frame = ctk.CTkFrame(master, fg_color="transparent")
        ctk.CTkLabel(frame, text=f"OPPONENT ({n})").grid(row=0, column=0, columnspan=max(n, 1), pady=(0, 4))
        if n == 0:
            ctk.CTkLabel(frame, text="(no cards)").grid(row=1, column=0)
        else:
            for i in range(n):
                slot = CardSlot(frame, self.deck_assets, width=CARD_W // 2, height=CARD_H // 2)
                slot.show_back()
                slot.grid(row=1, column=i, padx=2)
        return frame

    def _build_table_block(self, master, view):
        plays = view["table"]
        if not plays:
            ctk.CTkLabel(master, text="ON THE TABLE: (empty - you lead this trick)").grid(
                row=0, column=0, sticky="w"
            )
            return
        ctk.CTkLabel(master, text="ON THE TABLE:").grid(row=0, column=0, sticky="w")
        row = ctk.CTkFrame(master, fg_color="transparent")
        row.grid(row=1, column=0, sticky="w", pady=4)
        for i, (p, c) in enumerate(plays):
            who = "You" if p == view["you"] else f"Player {p + 1}"
            col = ctk.CTkFrame(row, fg_color="transparent")
            col.grid(row=0, column=i, padx=12)
            ctk.CTkLabel(col, text=who).grid(row=0, column=0)
            slot = CardSlot(col, self.deck_assets)
            slot.show_card(c)
            slot.grid(row=1, column=0)

    def _build_action_block(self, master, view):
        if be.is_terminal(self.state):
            self._build_result_block(master)
            return

        if self.state["turn"] != self.my_player:
            self._build_handoff_block(master)
            return

        self._build_hand_block(master, view)

    def _build_hand_block(self, master, view):
        ctk.CTkLabel(master, text="YOUR HAND - click a card to play it:").grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        row = ctk.CTkFrame(master, fg_color="transparent")
        row.grid(row=1, column=0, sticky="w")
        for i, card in enumerate(view["your_hand"]):
            btn = HandCardButton(row, self.deck_assets, card, command=lambda i=i: self._play_card(i))
            btn.grid(row=0, column=i, padx=6)

    def _build_handoff_block(self, master):
        ctk.CTkLabel(
            master, text=f"It is Player {self.state['turn'] + 1}'s move now.", anchor="w"
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self._build_token_panel(master, row=1, to_player=self.state["turn"],
                                 paste_label="Paste their reply to continue:")

    def _build_result_block(self, master):
        r = be.result(self.state)
        if r["winner"] is None:
            text = f"GAME OVER - PAREGGIO (60-60 draw). P1 {r['points'][0]} - P2 {r['points'][1]}"
        else:
            text = (
                f"GAME OVER - PLAYER {r['winner'] + 1} WINS. "
                f"P1 {r['points'][0]} - P2 {r['points'][1]}"
            )
        ctk.CTkLabel(master, text=text, font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        other = 1 - self.my_player
        self._build_token_panel(master, row=1, to_player=other,
                                 label=f"Send this final token to Player {other + 1} "
                                       "so they see the result too:")
        ctk.CTkButton(master, text="Back to menu", command=self._show_menu).grid(
            row=2, column=0, sticky="w", pady=(8, 0)
        )

    def _build_token_panel(self, master, row, to_player, label=None, paste_label=None):
        token = be.serialize(self.state)
        panel = ctk.CTkFrame(master, fg_color="transparent")
        panel.grid(row=row, column=0, sticky="ew", pady=4)
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            panel, text=label or f"Send this token to Player {to_player + 1}:", anchor="w"
        ).grid(row=0, column=0, sticky="w")
        box = ctk.CTkTextbox(panel, height=70)
        box.insert("1.0", token)
        box.configure(state="disabled")
        box.grid(row=1, column=0, sticky="ew", pady=4)
        ctk.CTkButton(panel, text="Copy token", command=lambda: self._copy_to_clipboard(token)).grid(
            row=2, column=0, sticky="w", pady=(0, 8)
        )

        if paste_label is not None:
            ctk.CTkLabel(panel, text=paste_label, anchor="w").grid(row=3, column=0, sticky="w")
            reply_box = ctk.CTkTextbox(panel, height=70)
            reply_box.grid(row=4, column=0, sticky="ew", pady=4)
            status = ctk.CTkLabel(panel, text="", text_color="orange")
            status.grid(row=6, column=0, sticky="w")
            ctk.CTkButton(
                panel, text="Load reply",
                command=lambda: self._load_reply(reply_box, status),
            ).grid(row=5, column=0, sticky="w", pady=(0, 4))

    def _load_reply(self, reply_box, status_label):
        raw = reply_box.get("1.0", "end").strip()
        if not raw:
            status_label.configure(text="Paste the reply token first.")
            return
        try:
            state = be.deserialize(raw)
        except be.TokenError as exc:
            status_label.configure(text=f"Could not load token: {exc}")
            return
        if state["game_id"] != self.state["game_id"]:
            status_label.configure(text="That token belongs to a different game.")
            return
        self.state = state
        self._show_table()

    def _copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)

    def _play_card(self, index):
        hand = be.legal_moves(self.state, self.my_player)
        if index not in range(len(hand)):
            return
        try:
            self.state = be.apply_move(self.state, self.my_player, hand[index])
        except be.IllegalMove:
            return
        self._show_table()


def main():
    app = BriscolaApp()
    app.mainloop()


if __name__ == "__main__":
    main()
