# Briscola (String-Passing) - Specification v0.5.0

*Current spec. Reflects what is implemented.*

## 1. Purpose & Concept

A two-player, serverless implementation of **Briscola**. No server and no live
connection: the **complete game state is serialized into a single token
string** that players exchange manually. The token *is* the source of truth and
the save file. Turns are asynchronous - load the latest token, move, emit a new
token to send to the opponent. Target platform: Windows.

## 2. Trust Model

**Honor system with interface-level hiding.** The opponent's hand and the deck's
upcoming cards are redacted from everything displayed (via `player_view`); a
player sees only their own cards plus public information (table, trump, scores,
the previous trick). The renderer receives only the redacted view, so it cannot
draw hidden cards.

This is **display privacy, not cryptographic secrecy**: the token still carries
the full state. A determined player could decode a token; and auto-copy puts the
token on the clipboard, so clipboard-history tools retain copies that include
the hidden cards. Genuine secrecy is a separate, larger milestone (S10).

## 3. Scope

### Implemented (through v0.5.0)
- Two players, a **single** game to completion. **No following-suit** rule.
- **CLI** with an **ASCII-art board** and manual token import/export.
- Hidden opponent hand + hidden deck contents.
- Automatic per-device identity, remembered per game (S8).
- Per-trick **screen reset** + **last-trick header** (S7).
- **Paste-to-load** as the default menu action (S6).
- **Clipboard auto-copy** of shown tokens (Windows, write-only) (S6).
- **Figure-card display setting**: 10/9/8 shown as K/Q/J by default (S7).
- Buildable as a **portable single-file executable**.

### Out of scope (deferred - S10)
- Cryptographic secrecy; clipboard reading ("peeking"); match play / best-of-N;
  4-player / team; following-suit variants; colour; GUI; automated transport.

## 4. Game Rules

### 4.1 Deck & Notation
40-card Italian deck. Suits by first letter: `D` Denari, `S` Spade, `C` Coppe,
`B` Bastoni. Ranks `1`-`10` (1 = Asso ... 10 = Re). Card encoding `<SUIT>-<RANK>`
with a delimiter (e.g. `D-1`, `S-10`). NOTE: ranks are stored numerically; the
K/Q/J display (S7) is presentation only and does not change the notation.

### 4.2 Card Values & Strength - CRITICAL
The numeric rank is neither the point value nor the trick strength; the engine
keeps the three concepts separate and never compares by label.

| Label | Card | Italian | Points | Strength (1 = highest) | Default display |
|:-----:|------|---------|:------:|:----------------------:|:---------------:|
| 1  | Ace      | Asso     | 11 | 1  | 1 |
| 3  | Three    | Tre      | 10 | 2  | 3 |
| 10 | King     | Re       | 4  | 3  | K |
| 9  | Knight   | Cavallo  | 3  | 4  | Q |
| 8  | Jack     | Fante    | 2  | 5  | J |
| 7  | Seven    | Sette    | 0  | 6  | 7 |
| 6  | Six      | Sei      | 0  | 7  | 6 |
| 5  | Five     | Cinque   | 0  | 8  | 5 |
| 4  | Four     | Quattro  | 0  | 9  | 4 |
| 2  | Two      | Due      | 0  | 10 | 2 |

Total 120 points; 61+ wins; 60-60 is a draw (*pareggio*).

### 4.3 Setup, Trick Flow, Draws, End
Deal 3 each; flip the next card for the briscola (trump), which sits at the
bottom of the draw pile as the last card drawn. Player 2 leads first. Each
trick: leader plays any card, opponent plays any card. Winner: same suit ->
higher strength; one briscola -> briscola; two different non-briscola suits ->
leader. Winner draws first then loser (flipping the lead). Last draw takes the
exposed briscola. Game ends after 20 tricks.

## 5. Architecture

Four modules, cleanly separated:

- **`briscola_engine.py`** - pure logic, no I/O, deterministic. API:
  `new_game(seed)`, `player_view(state, player)`, `legal_moves`, `apply_move`,
  `serialize`/`deserialize`, `is_terminal`, `result`. The seed is used once and
  never stored.
- **`briscola_render.py`** - pure presentation: `player_view` dict -> ASCII-art
  text; receives only the redacted view. Holds the `SHOW_FIGURES_AS_LETTERS`
  display setting.
- **`briscola_clipboard.py`** - Windows write-only auto-copy (`copy_to_clipboard`
  via the built-in `clip` command). No read capability by design.
- **`briscola_cli.py`** - control flow only: menu, paste-default, identity/
  session, screen reset, input, game loop.

### 5.1 State Model (carried in the token)
`version`, `game_id`, ordered `deck`, `briscola_suit`, `briscola_card`,
`hands` (both), `table`, `last_trick` (`{plays, winner, points}` or null),
`leader`, `turn`, `captured_points`, `captured_cards`, `trick_no`. The shuffle
**seed is not stored**.

### 5.2 Token Format - version 3
`state -> JSON -> zlib -> urlsafe base64`, wrapped with an 8-char checksum for
corruption detection (not security). `deserialize` rejects bad checksums and
unsupported versions with clear errors.

### 5.3 `player_view` redaction
Exposes: `you`, `your_hand`, `opponent_hand_count`, `deck_count`, `table`,
`last_trick`, `captured_points/cards`, `turn`, `leader`, `trick_no`,
`briscola_suit`, `briscola_card`, `briscola_in_deck`. Omits the raw `hands` and
`deck` contents.

## 6. Interface - CLI & Clipboard

- The menu prompt accepts a **pasted token directly** (the common case), or the
  keys `[1]` new, `[2]` load, `[q]` quit. Known keys are commands; otherwise the
  input is attempted as a token (`deserialize`).
- When the app shows a token to send, it **auto-copies it to the clipboard**
  (Windows). This is write-only; the app never reads the clipboard, and loading
  is always an explicit paste. If the copy fails or the platform isn't Windows,
  the token is still shown and play continues.
- A device plays while it is its turn; when the turn passes it shows the token
  and stops. Errors (garbled/old token, illegal card, out-of-turn) are handled
  without crashing.

## 7. Board Rendering, Per-Trick Reset, Figures Setting

- The screen is cleared at the top of each rendered trick view (ANSI clear with
  a Windows enable-shim; skipped when output is not an interactive terminal).
  The token is printed after the board and is never cleared away before copying.
- A one-line last-trick header recalls the previous trick (both plays and the
  winner with points); the first trick shows "game start".
- Cards are ASCII boxes with **5 interior rows**. Italian suit glyphs:
  `(o)` Denari, `\_/` Coppe, `-+>` Spade, `o==` Bastoni. The trump card is always
  drawn and labelled `TRUMP (suit)`. The opponent's hand is drawn as face-down
  backs (count only); their played card, when present, is shown face-up.
- **Figures setting** (`SHOW_FIGURES_AS_LETTERS`, default True): the figure
  cards display as K (10/Re), Q (9/Cavallo), J (8/Fante); pip cards stay
  numeric. Set False for raw numbers. Display only.

## 8. Automatic Identity
A token reaches a player only on their turn, so on first sight of a `game_id`
the device adopts `state["turn"]` as its identity and stores it; thereafter the
stored identity is authoritative. Persisted to `~/.briscola_sessions.json` (one
entry per active game, cleared at game end); degrades to in-memory if unwritable.

## 9. Non-Functional Requirements
- **Portable executable:** `PyInstaller --onefile`; stdlib only; all four modules
  bundle into one binary. Clipboard uses the built-in `clip` command. ASCII-only
  board renders on legacy consoles. The only runtime file is the session file;
  the app runs without it.
- **Quality:** deterministic engine; exact serialize/deserialize round-trips;
  versioned tokens. Test suite (stdlib `unittest`, 52 tests) covers deck/deal,
  all trick-resolution cases, draw order, scoring, end-of-deck briscola draw,
  terminal/result, serialization + tamper rejection, `player_view` redaction,
  `last_trick`, card/board rendering, the figures setting, the clipboard helper,
  session store, auto-identity, menu parsing, and full randomized + two-device
  playthroughs.

## 10. Roadmap
- **Real secrecy (next milestone):** encrypted per-player state / mental-poker
  dealing so the token itself does not reveal the opponent's hand or the deck
  order. The `player_view` and serialization seams absorb this without changing
  game logic.
- Match play / cumulative scoring; 4-player / team; following-suit variant;
  colour; GUI; automated token transport.

## 11. Project Conventions
- **File names:** lowercase with underscores, no spaces (e.g.
  `briscola_render.py`, `test_briscola_cli.py`).
- **Source encoding:** pure ASCII in `.py` files (safe on legacy consoles and
  immune to re-encoding issues).
- **Versioning:** the app/release version (e.g. v0.5.0) labels every module
  header; the token format has its own integer `version` (currently 3) that only
  changes when the token structure changes.

## 12. Glossary
**Briscola** - trump suit (and the game). **Carico** - a high-value card
(Asso/Tre). **Liscio** - a low/zero-point card. **Pareggio** - a 60-60 draw.
**Token** - the base64 string encoding the full game state.
