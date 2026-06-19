# Briscola — string-passing edition (v0.1)

A two-player, serverless [Briscola](https://en.wikipedia.org/wiki/Briscola)
where the **entire game lives in a token string** that players exchange
manually (chat, email, etc.). No server, no live connection — the token *is*
the game and the save file.

This is **v0.1**: honor system (no hidden information yet — both hands are
shown), single game, CLI, two players, no following-suit rule. See the spec for
the full scope and the planned upgrade path to real secrecy.

## Files
- `briscola_engine.py` — pure game logic (no I/O, deterministic). The token
  format, rules, scoring and trick resolution all live here.
- `briscola_cli.py` — the command-line interface (import/export tokens, pick
  cards). All display is routed through `engine.player_view`.
- `test_briscola_engine.py` — unit tests + 200 randomized full playthroughs.

## Requirements
Python 3.8+ — **standard library only**, nothing to `pip install` to run.

## Run
```bash
python briscola_cli.py
```

## How to play (the async flow)
1. **Player 1** chooses **New game**. The program creates the opening token.
   (Player 2 leads the first trick, so the opening token is Player 2's move.)
2. Player 1 sends that token to **Player 2** by any channel.
3. Player 2 chooses **Load token**, pastes it, picks "2" as their player, and
   plays. When the turn passes back, the program prints a new token to send.
4. Players keep exchanging tokens until the game ends. 61+ points wins; 60–60
   is a *pareggio* (draw).

A token looks like a long line of base64 text. Paste the whole thing on one
line. A garbled or truncated token is rejected by a checksum rather than
silently corrupting the game.

> Honor system: v0.1 puts the full state in the token, so a player *could*
> inspect the opponent's hand. The agreement is simply not to. Hiding hands is
> the planned next step (see the spec).

## Run the tests
```bash
python -m unittest test_briscola_engine -v
```

## Build a portable executable
The app is stdlib-only, so a single-file build is straightforward with
[PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile --name briscola briscola_cli.py
# result: dist/briscola  (or dist\briscola.exe on Windows)
```

Notes:
- "Portable" means **no Python install needed on the target machine** — it does
  **not** mean one binary for every OS. Build separately on/for each platform
  (Windows `.exe`, Linux, macOS).
- The app needs **no external files at runtime** — tokens are pasted in and
  printed out — so the single binary is fully self-contained.
- `briscola_engine.py` must sit next to `briscola_cli.py` at build time (the CLI
  imports it); PyInstaller bundles it automatically.
