# Briscola — string-passing edition (v0.4.0)

A two-player, serverless [Briscola](https://en.wikipedia.org/wiki/Briscola)
where the **entire game lives in a token string** that players exchange
manually (chat, email, etc.). No server, no live connection — the token *is*
the game and the save file.

Single game, CLI, two players, no following-suit rule.

## What's new in v0.4.0
- **ASCII-art board** (`briscola_render.py`): cards drawn as boxes (5 interior
  rows) with simple glyphs for the four Italian suits —
  `(o)` Denari · `\_/` Coppe · `-+>` Spade · `o==` Bastoni.
- **Trump card** is always drawn and labelled (`TRUMP (suit)`).
- **Screen resets each trick**, with a one-line header recalling the previous
  trick: who played what and who won. Stored in the token as `last_trick`
  (public info), so the player who led and then waited still sees the outcome.
- **Paste-to-load is the default**: at the menu you can just paste a token to
  continue — no need to choose `[2]` first. `[1]`, `[2]`, `[q]` still work.
- Token format is now **version 3** (adds `last_trick`); older tokens are
  rejected with a clear message.

## Trust model
The opponent's hand and the deck's upcoming cards are **hidden in the
interface** — you only see your own cards plus public information (the table,
the trump, scores, the last trick). The renderer receives only the redacted
`player_view`, so it structurally cannot draw hidden cards.

This is **display privacy on the honor system, not cryptographic secrecy**: the
token still contains the full state (the opponent's device needs it), so a
determined player could decode one. Making the hidden cards genuinely
un-decodable is the next milestone (see *Roadmap*).

## Version history
- **v0.4.0** — ASCII-art board + labelled trump; per-trick screen reset with a
  last-trick header; paste-to-load default. Token v3 (adds `last_trick`).
- **v0.3** — opponent's hand and deck contents hidden at the interface.
- **v0.2** — automatic per-device identity, remembered per game. Token v2.
- **v0.1** — engine + CLI, honor-system full view. Token v1.

## Files
- `briscola_engine.py` — pure game logic (no I/O, deterministic): rules,
  scoring, trick resolution, `player_view` redaction, token serialize/
  deserialize.
- `briscola_render.py` — pure presentation: `player_view` dict -> ASCII-art
  text. No I/O, no logic, view-only.
- `briscola_cli.py` — control flow only: menu (paste-default), card selection,
  identity + session store, screen reset, game loop.
- `test_briscola_engine.py` — engine + `player_view` + `last_trick` + 200
  randomized full playthroughs.
- `test_briscola_render.py` — card/board rendering.
- `test_briscola_cli.py` — session store, auto-identity, menu parsing, and a
  two-device game.

## Requirements
Python 3.8+ — **standard library only**, nothing to `pip install` to run.

## Run
```bash
python briscola_cli.py
```

## How to play (the async flow)
1. **Player 1** chooses `[1]` New game. The program records this device as
   Player 1 and prints the opening token. (Player 2 leads first.)
2. Player 1 sends that token to **Player 2**.
3. Player 2 **pastes the token straight at the menu**. The app recognises it,
   figures out they are Player 2, shows the board (their own hand, the opponent
   as face-down backs, the trump, the last trick), and they play.
4. The app prints a new token to send back. Players keep pasting the latest
   token they receive; each device remembers who it is. 61+ points wins; 60-60
   is a *pareggio* (draw).

> Identity is stored in `~/.briscola_sessions.json` (one entry per active game,
> cleared at game end), so it survives quitting and relaunching between turns.
> The app runs fine even if that file can't be written.

## Run the tests
```bash
python -m unittest test_briscola_engine test_briscola_render test_briscola_cli -v
```

## Build a portable executable
Stdlib-only, so a single-file build is straightforward with
[PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile --name briscola briscola_cli.py
# result: dist/briscola  (or dist\briscola.exe on Windows)
```

Notes:
- The three source modules bundle into **one** executable — multiple files cost
  nothing for the build.
- "Portable" means no Python install needed on the target, built per OS (not one
  binary for all platforms).
- The board uses only ASCII, so it renders even on a legacy console; the
  screen-clear is skipped automatically when output isn't an interactive
  terminal.

## Roadmap
- **Real secrecy (next milestone):** encrypted per-player state / mental-poker
  dealing so the token itself does not reveal the opponent's hand or the deck
  order. The `player_view` + serialization seams are in place for this.
- Match play (best-of-N), 4-player/team Briscola, colour, a GUI.
