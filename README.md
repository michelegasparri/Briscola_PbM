# Briscola - string-passing edition (v0.5.0)

A two-player, serverless [Briscola](https://en.wikipedia.org/wiki/Briscola)
where the **entire game lives in a token string** that players exchange
manually (chat, email, etc.). No server, no live connection - the token *is*
the game and the save file.

Single game, CLI, two players, no following-suit rule. Targeted at Windows.

## What's new in v0.5.0
- **Auto-copy to clipboard:** whenever the app shows a token to send, it is
  copied to the clipboard automatically (Windows, via the built-in `clip`
  command). This is **write-only** - the app never reads the clipboard.
- **Figure cards display as K / Q / J by default:** 10 -> K (Re), 9 -> Q
  (Cavallo), 8 -> J (Fante). A single setting toggles this (see below). It is a
  display-only change; the token and notation are unchanged.
- Token format is unchanged (still **version 3**).

## The figures setting
In `briscola_render.py`:

```python
SHOW_FIGURES_AS_LETTERS = True   # default: 10/9/8 shown as K/Q/J
                                 # set to False for raw numbers 10/9/8
```

## Trust model
The opponent's hand and the deck's upcoming cards are **hidden in the
interface** - you see only your own cards plus public information. The renderer
receives only the redacted `player_view`, so it cannot draw hidden cards.

This is **display privacy on the honor system, not cryptographic secrecy**: the
token carries the full state, so a determined player could decode one. Note too
that auto-copy places the token on the clipboard, so anything that records
clipboard history (Windows' Win+V, third-party managers) retains a copy that
includes the hidden cards. Making the hidden cards genuinely un-decodable is the
next milestone (see *Roadmap*).

## Version history
- **v0.5.0** - clipboard auto-copy (Windows, write-only); figure cards shown as
  K/Q/J by default (toggle in the renderer). Token still v3.
- **v0.4.0** - ASCII-art board + labelled trump; per-trick screen reset with a
  last-trick header; paste-to-load default. Token v3 (adds `last_trick`).
- **v0.3** - opponent's hand and deck contents hidden at the interface.
- **v0.2** - automatic per-device identity, remembered per game. Token v2.
- **v0.1** - engine + CLI, honor-system full view. Token v1.

## Files
All filenames are lowercase with underscores (no spaces).
- `briscola_engine.py` - pure game logic (no I/O, deterministic).
- `briscola_render.py` - pure presentation: `player_view` dict -> ASCII-art
  text. Holds the `SHOW_FIGURES_AS_LETTERS` setting.
- `briscola_clipboard.py` - Windows write-only clipboard auto-copy.
- `briscola_cli.py` - control flow only: menu (paste-default), card selection,
  identity + session store, screen reset, game loop.
- `test_briscola_engine.py`, `test_briscola_render.py`,
  `test_briscola_clipboard.py`, `test_briscola_cli.py` - the test suite.

## Requirements
Python 3.8+ - **standard library only**, nothing to `pip install` to run.

## Run
```bash
python briscola_cli.py
```

## How to play (the async flow)
1. **Player 1** chooses `[1]` New game. The opening token is shown (and copied
   to the clipboard on Windows). Player 2 leads first.
2. Player 1 pastes that token to **Player 2** (e.g. in chat).
3. Player 2 **pastes the token straight at the menu**. The app recognises it,
   figures out they are Player 2, shows the board (own hand, the opponent as
   face-down backs, the trump, the last trick), and they play.
4. The app shows a new token (auto-copied) to send back. Players keep pasting
   the latest token they receive; each device remembers who it is. 61+ points
   wins; 60-60 is a *pareggio* (draw).

> Identity is stored in `~/.briscola_sessions.json` (one entry per active game,
> cleared at game end), so it survives quitting and relaunching between turns.
> The app runs fine even if that file can't be written.

## Run the tests
```bash
python -m unittest discover -p "test_*.py"
```

## Build a portable executable
Stdlib-only, so a single-file build is straightforward with
[PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile --name briscola briscola_cli.py
# result: dist\briscola.exe on Windows
```

Notes:
- All source modules bundle into **one** executable; multiple files cost
  nothing for the build.
- Clipboard auto-copy uses the built-in Windows `clip` command (no dependency);
  on other systems it simply does nothing and the token is still shown.
- The board is pure ASCII, so it renders even on a legacy console; the
  screen-clear is skipped automatically when output isn't an interactive
  terminal.

## Roadmap
- **Real secrecy (next milestone):** encrypted per-player state / mental-poker
  dealing so the token itself does not reveal the opponent's hand or the deck
  order. The `player_view` + serialization seams are in place for this.
- Match play (best-of-N), 4-player/team Briscola, colour, a GUI.
