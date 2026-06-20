# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A two-player, serverless Briscola card game where the **entire game state lives
in a token string** that players exchange manually (chat, email, etc.). No
server, no network code - the token *is* the save file. Single game, CLI,
two players, no following-suit rule. Targeted at Windows; stdlib only.

The authoritative design doc is `briscola_spec.md` - read it before making
rules or architecture changes, since it documents *why* things work the way
they do (trust model, token format, state fields).

## Commands

```bash
# Run the game
python briscola_cli.py

# Run the full test suite
python -m unittest discover -p "test_*.py"

# Run a single test file / class / method
python -m unittest test_briscola_engine
python -m unittest test_briscola_engine.TestApplyMove
python -m unittest test_briscola_engine.TestApplyMove.test_first_card_passes_turn

# Build a portable single-file executable (stdlib only, no extra deps)
pip install pyinstaller
pyinstaller --onefile --name briscola briscola_cli.py
```

There is no lint/format tooling configured in this repo - don't invent one.

## Architecture

Four modules with strictly one-directional dependencies; preserve this
separation when adding features:

- **`briscola_engine.py`** - pure game logic. No I/O, no printing,
  deterministic given its inputs. Owns the state dict, card notation, rules,
  and token serialization. Public API: `new_game(seed)`, `player_view(state,
  player)`, `legal_moves`, `apply_move`, `serialize`/`deserialize`,
  `is_terminal`, `result`.
- **`briscola_render.py`** - pure presentation. Converts a `player_view` dict
  into ASCII-art text. Imports `briscola_engine` for card helpers only;
  never touches the full state, so it physically cannot render hidden cards.
  Holds the `SHOW_FIGURES_AS_LETTERS` display toggle.
- **`briscola_clipboard.py`** - Windows-only, **write-only** clipboard
  auto-copy via the built-in `clip` command. By design it exposes only
  `copy_to_clipboard()` - never add a read/paste-from-clipboard function;
  this is a stated trust-model decision (no "peeking"), not an oversight.
- **`briscola_cli.py`** - control flow only: menu, paste-to-load, identity/
  session handling, input, the game loop. Delegates all drawing to `render`,
  all rules to `engine`, clipboard to `clipboard`. Don't put rendering or
  rule logic here.

### Card notation - critical invariant

A card is the string `"<SUIT>-<RANK>"` (e.g. `"D-1"`, `"S-10"`), suits `D`
(Denari) `S` (Spade) `C` (Coppe) `B` (Bastoni), ranks `1`-`10`. The numeric
rank is **neither** the point value **nor** the trick-strength order - the
three concepts are deliberately kept in separate tables (`POINTS`,
`STRENGTH`) in `briscola_engine.py`. Never compare or sort cards by rank
label directly; always go through `card_points()` / `STRENGTH[card_rank(c)]`.
Strength order (1=highest) is: Asso, Tre, Re(10), Cavallo(9), Fante(8), 7, 6,
5, 4, 2 - not numeric order.

### State and token format

The full game state is a plain dict (see `new_game()` in
`briscola_engine.py` for every field) and is the unit that gets serialized:
`state -> JSON -> zlib -> urlsafe base64`, wrapped with a sha256-derived
8-char checksum for corruption detection (not security - `TokenError` is
raised on a bad checksum or unsupported `version`). The token `VERSION`
constant only bumps when the state shape changes; the human-facing app
version (e.g. v0.5.0) is independent and just labels module docstrings.

The shuffle seed is intentionally **never stored** in state - it's used once
in `new_game(seed)` and discarded, otherwise the opponent's token would leak
the entire future deck order.

### Trust model - honor system, not cryptography

The opponent's hand and remaining deck contents are redacted only at the
*interface* level, via `player_view(state, player)`. The token itself still
carries the full, unredacted state (the opponent's device needs it to keep
playing). `briscola_render.py` only ever receives the output of
`player_view`, never the raw state - that's what makes hiding enforceable in
code rather than just a UI convention. When adding any new rendering or
display code, route it through `player_view`, not the raw state dict.

Real cryptographic secrecy (mental-poker-style dealing) is an explicit,
deferred roadmap item (see spec S10) - don't attempt to bolt on encryption
piecemeal; it needs the dedicated milestone.

### Identity model

There's no login: a device sees a token only when it's that player's turn,
so on first sight of a `game_id` the device adopts `state["turn"]` as its own
identity (`resolve_identity` in `briscola_cli.py`) and persists it to
`~/.briscola_sessions.json`, keyed by `game_id`. This file is optional
runtime state, not configuration - the app must keep working if it can't be
read or written (see `SessionStore` swallowing I/O errors).

## Testing conventions

`unittest`, one test file per module (`test_<module>.py`), grouped into
`TestCase` classes by feature/behavior (e.g. `TestTrickResolution`,
`TestSerialization`, `TestPlayerView`). Tests cover deck/deal, every trick-
resolution case, draw order, scoring, end-of-deck briscola draw, terminal/
result, serialize/deserialize round-trips and tamper rejection, `player_view`
redaction, rendering, the clipboard helper, the session store, auto-identity,
menu parsing, and full randomized two-device playthroughs. Match this
structure for new tests rather than introducing a different layout.

## Project conventions (from `briscola_spec.md` S11)

- Filenames: lowercase with underscores, no spaces.
- Source files are pure ASCII (safe on legacy Windows consoles).
- Keep the app version (module docstring headers) and the token `VERSION`
  separate - only bump token `VERSION` when the serialized state shape
  actually changes.
