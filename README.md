# Briscola — string-passing edition (v0.3)

A two-player, serverless [Briscola](https://en.wikipedia.org/wiki/Briscola)
where the **entire game lives in a token string** that players exchange
manually (chat, email, etc.). No server, no live connection — the token *is*
the game and the save file.

Single game, CLI, two players, no following-suit rule.

## Trust model (read this)
The opponent's hand and the deck's upcoming cards are **hidden in the
interface** — you only ever see your own cards. This is done by routing all
display through `engine.player_view`, which redacts everything that isn't
yours or public.

However, this is **display privacy on the honor system, not cryptographic
secrecy.** The token still contains the full game state (the opponent's device
needs it to keep playing), so a determined player could decode a token and read
the hidden cards. The agreement is simply not to. Making the hidden cards
genuinely un-decodable requires encrypting per-player state / mental-poker-style
dealing — a separate, larger step (see *Roadmap*). Because all display already
goes through `player_view`, that upgrade will not touch the game logic.

## Version history
- **v0.3** — opponent's hand and deck contents hidden at the interface
  (`player_view` redaction). Token format unchanged (still v2).
- **v0.2** — automatic per-device player identity, remembered per game; token
  format v2 (adds `game_id`).
- **v0.1** — engine + CLI, honor-system full view; token format v1.

## Files
- `briscola_engine.py` — pure game logic (no I/O, deterministic): rules,
  scoring, trick resolution, `player_view` redaction, token serialize/
  deserialize.
- `briscola_cli.py` — the command-line interface: token import/export, card
  selection, automatic per-device identity + session store.
- `test_briscola_engine.py` — engine tests, `player_view` redaction tests, and
  200 randomized full playthroughs.
- `test_briscola_cli.py` — session store, auto-identity, and a two-device game.

## Requirements
Python 3.8+ — **standard library only**, nothing to `pip install` to run.

## Run
```bash
python briscola_cli.py
```

## How to play (the async flow)
1. **Player 1** chooses **New game**. The program creates the opening token and
   records this device as Player 1. (Player 2 leads first, so the opening token
   is Player 2's move.)
2. Player 1 sends that token to **Player 2**.
3. Player 2 chooses **Load token** and pastes it. The app figures out they are
   Player 2 automatically; they see **only their own hand** (the opponent's is
   shown as a hidden count), play, and the app prints a new token to send back.
4. Players keep exchanging tokens until the game ends. 61+ points wins; 60–60
   is a *pareggio* (draw). Each device just keeps choosing **Load token** with
   the latest token it receives — it always remembers who it is.

A token is a single long line of base64 text — paste the whole thing. Garbled
or truncated tokens are rejected by a checksum rather than corrupting the game.

> Identity is stored in `~/.briscola_sessions.json` (one tiny entry per active
> game, cleared when a game ends). The executable itself remains self-contained;
> this file lives in the user's home directory, not in the bundle, and the app
> runs fine even if it can't be created.

## Run the tests
```bash
python -m unittest test_briscola_engine test_briscola_cli -v
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
- "Portable" means **no Python install needed on the target** — not one binary
  for every OS. Build separately on/for each platform.
- `briscola_engine.py` must sit next to `briscola_cli.py` at build time (the CLI
  imports it); PyInstaller bundles it automatically.

## Roadmap
- **Real secrecy (next milestone):** replace honor-system display hiding with
  encrypted per-player state / mental-poker dealing so the token genuinely does
  not reveal the opponent's hand or the deck order. The `player_view` +
  `serialize`/`deserialize` seams are in place for this.
- Match play (best-of-N), 4-player/team Briscola, a GUI.
